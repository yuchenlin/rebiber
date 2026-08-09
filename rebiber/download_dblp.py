#!/usr/bin/env python3
"""Download DBLP BibTeX for major conferences and convert it for rebiber.

Works as::

    python -m rebiber.download_dblp
    python rebiber/download_dblp.py

After a successful download this writes ``raw_data/{conf}{year}.bib``, converts
it to ``data/{conf}{year}.bib.json`` (unless ``--no-convert``), and appends the
json path to ``bib_list.txt`` when missing.

DBLP toc query shapes::

    conf (default):     toc:db/conf/{short}/{file}.bht:
    journal_year:       toc:db/journals/{short}/{short}{year}.bht:
    journal_vol (jmlr): toc:db/journals/jmlr/jmlr{year-1999}.bht:
    conf_multivol:      bare {conf}{year}.bht, else {conf}{year}-1, -2, ...

NeurIPS lives under the historical ``nips`` key: ``neurips{year}`` from 2020
onwards and ``nips{year}`` before that. ECCV / KDD / MICCAI fall back to
numbered LNCS-style volumes when the bare toc is empty. ECML is skipped
(renamed toc paths). COLM falls back to OpenReview when DBLP is empty.

Be polite to DBLP: a descriptive User-Agent, ``--sleep`` between requests, and
exponential backoff on HTTP 429 / "Too Many Requests".
"""

import argparse
import datetime
import json
import os
import sys
import time

try:
    import requests
except ImportError:  # pragma: no cover - optional unless you actually download
    requests = None


PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_AGENT = "rebiber/1.3.0 (+https://github.com/yuchenlin/rebiber)"
DBLP_API = "https://dblp.org/search/publ/api"
OPENREVIEW_API = "https://api2.openreview.net/notes"
PAGE_SIZE = 1000
MULTIVOL_MAX = 100
THIN_RATIO = 0.4
LARGE_MIN_COUNT = 1500
LARGE_MIN_YEAR = 2020
LARGE_CONFS = frozenset(
    {"neurips", "icml", "iclr", "cvpr", "aaai", "icra", "iros"}
)

KIND_CONF = "conf"
KIND_JOURNAL_YEAR = "journal_year"
KIND_JOURNAL_VOL = "journal_vol"
KIND_CONF_MULTIVOL = "conf_multivol"

# Conferences whose DBLP toc path is ``db/conf/{short}/{conf}{year}.bht``,
# plus journals / multi-volume venues listed in VENUE_SPEC.
DEFAULT_CONFS = [
    "neurips",
    "icml",
    "iclr",
    "iccv",
    "bmvc",
    "cvpr",
    "accv",
    "miccai",  # medical imaging; see issues #6 / #54
    "aaai",
    "ijcai",
    "kdd",
    "interspeech",
    "icassp",
    "chi",
    "sigir",
    "sigmod",
    "aistats",
    "uai",
    "www",
    "wacv",  # issue #54
    "colm",  # OpenReview fallback when the DBLP toc is empty
    "tmlr",
    "jmlr",
    "mlsys",
    "eccv",
    "icra",  # robotics (main track only)
    "iros",
    "rss",
    "corl",
]

# DBLP folder name when it differs from the rebiber filename prefix.
SHORT_CONF_NAMES = {
    "neurips": "nips",
}

# Multi-volume / renamed proceedings that this script cannot fetch.
SKIPPED_CONFS = {
    "ecml": "ECML/PKDD toc paths are renamed (e.g. ecmlpkdd{year})",
}

# Per-venue download recipe. Unlisted names default to kind=conf.
VENUE_SPEC = {
    "neurips": {"kind": KIND_CONF, "short": "nips"},
    "tmlr": {"kind": KIND_JOURNAL_YEAR, "short": "tmlr"},
    "jmlr": {"kind": KIND_JOURNAL_VOL, "short": "jmlr"},
    "kdd": {"kind": KIND_CONF_MULTIVOL, "short": "kdd"},
    "miccai": {"kind": KIND_CONF_MULTIVOL, "short": "miccai"},
    "eccv": {"kind": KIND_CONF_MULTIVOL, "short": "eccv"},
    "wacv": {"kind": KIND_CONF, "short": "wacv"},
    "colm": {"kind": KIND_CONF, "short": "colm", "openreview_fallback": True},
    "mlsys": {"kind": KIND_CONF, "short": "mlsys"},
    "icra": {"kind": KIND_CONF, "short": "icra"},
    "iros": {"kind": KIND_CONF, "short": "iros"},
    "rss": {"kind": KIND_CONF, "short": "rss"},
    "corl": {"kind": KIND_CONF, "short": "corl"},
}

for _conf in DEFAULT_CONFS:
    VENUE_SPEC.setdefault(
        _conf,
        {"kind": KIND_CONF, "short": SHORT_CONF_NAMES.get(_conf, _conf)},
    )


def venue_spec(conf):
    """Return a copy of the venue recipe, defaulting to a single conf toc."""
    spec = VENUE_SPEC.get(conf)
    if spec is None:
        return {
            "kind": KIND_CONF,
            "short": SHORT_CONF_NAMES.get(conf, conf),
        }
    out = dict(spec)
    out.setdefault("kind", KIND_CONF)
    out.setdefault("short", SHORT_CONF_NAMES.get(conf, conf))
    return out


def jmlr_volume(year):
    """DBLP volume for JMLR (vol 1 = 2000 → year 2024 is jmlr25)."""
    return year - 1999


def min_count(conf, year):
    """Minimum accepted dump size used by the skip-existing gate."""
    if conf in LARGE_CONFS and year >= LARGE_MIN_YEAR:
        return LARGE_MIN_COUNT
    return 0


def _import_bib2json():
    """Import build_json/load_bib_file even if the package is not installed."""
    try:
        from rebiber.bib2json import build_json, load_bib_file

        return build_json, load_bib_file
    except ImportError:
        pass

    repo_root = os.path.dirname(PACKAGE_DIR)
    for path in (repo_root, PACKAGE_DIR):
        if path not in sys.path:
            sys.path.insert(0, path)

    try:
        from rebiber.bib2json import build_json, load_bib_file

        return build_json, load_bib_file
    except ImportError:
        from bib2json import build_json, load_bib_file

        return build_json, load_bib_file


def parse_confs(value):
    if not value:
        return list(DEFAULT_CONFS)
    confs = []
    seen = set()
    for part in value.split(","):
        name = part.strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        confs.append(name)
    return confs


def toc_file_stem(conf, year, volume=None):
    """Return the DBLP ``.bht`` basename (without extension) for a venue/year."""
    spec = venue_spec(conf)
    kind = spec["kind"]
    short = spec["short"]
    if kind == KIND_JOURNAL_YEAR:
        stem = "{short}{year}".format(short=short, year=year)
    elif kind == KIND_JOURNAL_VOL:
        stem = "{short}{vol}".format(short=short, vol=jmlr_volume(year))
    elif conf == "neurips":
        stem = ("neurips{year}" if year >= 2020 else "nips{year}").format(year=year)
    else:
        stem = "{conf}{year}".format(conf=conf, year=year)
    if volume is not None:
        stem = "{stem}-{volume}".format(stem=stem, volume=volume)
    return stem


def _format_toc_query(conf, year, volume=None):
    spec = venue_spec(conf)
    kind = spec["kind"]
    short = spec["short"]
    stem = toc_file_stem(conf, year, volume=volume)
    if kind in (KIND_JOURNAL_YEAR, KIND_JOURNAL_VOL):
        return "toc:db/journals/{short}/{stem}.bht:".format(short=short, stem=stem)
    return "toc:db/conf/{short}/{stem}.bht:".format(short=short, stem=stem)


def toc_queries(conf, year):
    """Yield one or more DBLP toc query strings."""
    yield _format_toc_query(conf, year)


def toc_query(conf, year):
    """Return the primary DBLP toc query string (first item of toc_queries)."""
    return next(iter(toc_queries(conf, year)))


def json_filename(conf, year):
    """Output dump name; always ``{conf}{year}.bib.json`` (year, not volume)."""
    return "{conf}{year}.bib.json".format(conf=conf, year=year)


def bib_filename(conf, year):
    return "{conf}{year}.bib".format(conf=conf, year=year)


def bib_list_entry(json_path, bib_list_path):
    """Return the path as it should appear in bib_list.txt."""
    bib_list_dir = os.path.dirname(os.path.abspath(bib_list_path))
    rel = os.path.relpath(os.path.abspath(json_path), bib_list_dir)
    return rel.replace(os.sep, "/")


def ensure_bib_list_entry(bib_list_path, entry):
    existing = set()
    if os.path.isfile(bib_list_path):
        with open(bib_list_path, encoding="utf-8") as handle:
            existing = {line.strip() for line in handle if line.strip()}
    if entry in existing:
        return False
    parent = os.path.dirname(bib_list_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(bib_list_path, "a", encoding="utf-8") as handle:
        handle.write(entry + "\n")
    print("Appended {entry} to {path}".format(entry=entry, path=bib_list_path))
    return True


def load_json_db(path):
    """Load a rebiber dump dict, or None if missing / unreadable."""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, TypeError) as exc:
        print("Could not read {path}: {exc}".format(path=path, exc=exc))
        return None
    if not isinstance(data, dict):
        print("Unexpected JSON shape in {path}; treating as incomplete".format(path=path))
        return None
    return data


def dump_count(path):
    data = load_json_db(path)
    if data is None:
        return None
    return len(data)


def bib_to_json_data(bib_path):
    build_json, load_bib_file = _import_bib2json()
    entries = load_bib_file(bib_path)
    return build_json(entries)


def write_json_data(json_path, data):
    json_dir = os.path.dirname(json_path)
    if json_dir:
        os.makedirs(json_dir, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    print("Wrote {path} ({n} entries)".format(path=json_path, n=len(data)))
    return len(data)


def convert_bib(bib_path, json_path):
    data = bib_to_json_data(bib_path)
    return write_json_data(json_path, data)


def _is_rate_limited(response):
    if response.status_code == 429:
        return True
    text = response.text or ""
    return "Too Many Requests" in text


def fetch_page(session, query_string, page, sleep_s, max_retries=10):
    """Fetch one DBLP page; retry with backoff on 429 / transient errors."""
    return fetch_page_at_offset(
        session, query_string, page * PAGE_SIZE, sleep_s, max_retries=max_retries
    )


def fetch_page_at_offset(session, query_string, offset, sleep_s, max_retries=10):
    """Fetch one DBLP page starting at hit offset ``f``."""
    params = {
        "q": query_string,
        "h": PAGE_SIZE,
        "f": int(offset),
        "format": "bib",
    }
    backoff = max(60.0, float(sleep_s))
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(
                DBLP_API,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=90,
            )
        except requests.RequestException as exc:
            last_error = exc
            print(
                "Request error ({exc}); retry {attempt}/{max_retries} in {backoff:.0f}s".format(
                    exc=exc,
                    attempt=attempt,
                    max_retries=max_retries,
                    backoff=backoff,
                )
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
            continue

        if _is_rate_limited(response):
            last_error = "HTTP {code} rate limit".format(code=response.status_code)
            print(
                "DBLP rate limited ({err}); backing off {backoff:.0f}s "
                "(retry {attempt}/{max_retries})".format(
                    err=last_error,
                    backoff=backoff,
                    attempt=attempt,
                    max_retries=max_retries,
                )
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
            continue

        ok = getattr(getattr(requests, "codes", None), "ok", 200)
        if response.status_code != ok:
            last_error = "HTTP {code}".format(code=response.status_code)
            print(
                "{err}; retry {attempt}/{max_retries} in {backoff:.0f}s".format(
                    err=last_error,
                    attempt=attempt,
                    max_retries=max_retries,
                    backoff=backoff,
                )
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
            continue

        time.sleep(sleep_s)
        return response.text or ""

    raise RuntimeError(
        "Exceeded {n} retries talking to DBLP ({err})".format(
            n=max_retries, err=last_error
        )
    )


def download_query_pages(session, query_string, max_pages, sleep_s, label=""):
    """Return concatenated BibTeX for one toc query, or '' if page 0 is empty.

    DBLP may silently cap ``h`` below 1000 (often 100). Advance ``f`` by the
    number of hits actually returned. Treat the first page size as the server
    cap: a later shorter page is the last page.
    """
    chunks = []
    prefix = (label + " ") if label else ""
    offset = 0
    page_cap = None
    for page in range(max_pages):
        print(
            "Fetching {prefix}page {page} (f={offset}) q={query}".format(
                prefix=prefix,
                page=page,
                offset=offset,
                query=query_string,
            )
        )
        text = fetch_page_at_offset(session, query_string, offset, sleep_s)
        if not text.strip() or "@" not in text:
            if page == 0:
                return ""
            print("stop (empty page)")
            break
        chunks.append(text)
        hits = text.count("@")
        print("  got {n} hits (offset {offset})".format(n=hits, offset=offset))
        if hits <= 0:
            break
        if page_cap is None:
            page_cap = hits
        offset += hits
        if page_cap and hits < page_cap:
            break
    return "".join(chunks)


def download_conf_year(session, conf, year, max_pages, sleep_s):
    """Return concatenated BibTeX, or '' if DBLP has no entries."""
    spec = venue_spec(conf)
    primary = toc_query(conf, year)
    label = "{conf} {year}".format(conf=conf, year=year)
    text = download_query_pages(session, primary, max_pages, sleep_s, label=label)
    if text or spec.get("kind") != KIND_CONF_MULTIVOL:
        return text

    print(
        "Bare toc empty for {conf} {year}; trying numbered volumes".format(
            conf=conf, year=year
        )
    )
    chunks = []
    for vol in range(1, MULTIVOL_MAX + 1):
        query = _format_toc_query(conf, year, volume=vol)
        vol_label = "{conf} {year} vol {vol}".format(conf=conf, year=year, vol=vol)
        vol_text = download_query_pages(
            session, query, max_pages, sleep_s, label=vol_label
        )
        if not vol_text:
            if vol == 1:
                print(
                    "No numbered volumes for {conf} {year}".format(conf=conf, year=year)
                )
            else:
                print(
                    "stop volumes at {conf} {year}-{vol} (empty first page)".format(
                        conf=conf, year=year, vol=vol
                    )
                )
            break
        chunks.append(vol_text)
    return "".join(chunks)


def _openreview_value(field):
    """Unwrap an OpenReview content field (API1 scalar/list or API2 {value: ...})."""
    if field is None:
        return None
    if isinstance(field, dict) and "value" in field:
        return field.get("value")
    return field


def _openreview_text(field):
    value = _openreview_value(field)
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(part) for part in value if part)
    return str(value)


def _openreview_authors(field):
    value = _openreview_value(field)
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " and ".join(str(name).strip() for name in value if str(name).strip())
    return str(value).strip()


def is_accepted_colm_note(note, year=None):
    """True if an OpenReview note looks like an accepted COLM paper."""
    if not isinstance(note, dict):
        return False
    if note.get("ddate"):
        return False
    content = note.get("content") or {}
    if not isinstance(content, dict):
        content = {}
    venue = _openreview_text(content.get("venue")).lower()
    venueid = _openreview_text(content.get("venueid"))
    expected_id = "colmweb.org/COLM/{year}/Conference".format(year=year) if year else ""

    if venue:
        if any(bad in venue for bad in ("reject", "withdraw", "desk", "submitted to")):
            return False
        if "accept" in venue or "colm" in venue:
            return True
    if expected_id and expected_id in venueid:
        return True
    return False


def colm_notes_to_bib(notes, year):
    """Turn OpenReview note dicts into a concatenated @inproceedings BibTeX string."""
    chunks = []
    for note in notes or []:
        if not is_accepted_colm_note(note, year=year):
            continue
        content = note.get("content") or {}
        if not isinstance(content, dict):
            content = {}
        title = _openreview_text(content.get("title")).strip()
        if not title:
            continue
        authors = _openreview_authors(content.get("authors"))
        note_id = note.get("forum") or note.get("id") or ""
        url = "https://openreview.net/forum?id={nid}".format(nid=note_id)
        cite_key = "colm{year}_{nid}".format(year=year, nid=note_id or "anon")
        chunks.append(
            "@inproceedings{{{key},\n"
            "  title={{{title}}},\n"
            "  author={{{authors}}},\n"
            "  booktitle={{The Conference on Language Modeling}},\n"
            "  year={{{year}}},\n"
            "  url={{{url}}}\n"
            "}}\n".format(
                key=cite_key,
                title=title,
                authors=authors,
                year=year,
                url=url,
            )
        )
    return "".join(chunks)


def _openreview_get(session, params):
    headers = {"User-Agent": USER_AGENT}
    if session is not None:
        return session.get(OPENREVIEW_API, params=params, headers=headers, timeout=90)
    if requests is None:
        raise RuntimeError("The 'requests' package is required to fetch OpenReview notes")
    return requests.get(OPENREVIEW_API, params=params, headers=headers, timeout=90)


def _fetch_openreview_note_pages(session, base_params):
    """Paginate OpenReview /notes; return a list of note dicts."""
    notes = []
    offset = 0
    limit = int(base_params.get("limit") or 1000)
    while True:
        params = dict(base_params)
        params["limit"] = limit
        params["offset"] = offset
        response = _openreview_get(session, params)
        status = getattr(response, "status_code", None)
        if status is not None and status != 200:
            raise RuntimeError("OpenReview HTTP {code}".format(code=status))
        payload = response.json() if hasattr(response, "json") else {}
        if not isinstance(payload, dict):
            break
        batch = payload.get("notes") or []
        if not isinstance(batch, list) or not batch:
            break
        notes.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
        if offset > 20000:
            break
    return notes


def fetch_colm_openreview(year, session=None):
    """Fetch accepted COLM papers from OpenReview and return BibTeX.

    Venue id: ``colmweb.org/COLM/{year}/Conference``. Tries ``content.venueid``
    then ``invitation``. On any API/parse error prints a warning and returns ''.
    """
    venueid = "colmweb.org/COLM/{year}/Conference".format(year=year)
    param_sets = [
        {"content.venueid": venueid},
        {"invitation": venueid + "/-/Submission"},
        {"invitations": venueid},
    ]
    try:
        notes = []
        errors = []
        for params in param_sets:
            try:
                notes = _fetch_openreview_note_pages(session, params)
            except Exception as exc:
                errors.append(exc)
                notes = []
            if notes:
                break
        if not notes:
            extra = ""
            if errors:
                extra = " ({exc})".format(exc=errors[-1])
            print(
                "Warning: COLM {year} OpenReview returned no notes for {vid}{extra}".format(
                    year=year, vid=venueid, extra=extra
                )
            )
            return ""
        return colm_notes_to_bib(notes, year)
    except Exception as exc:
        print(
            "Warning: COLM {year} OpenReview fetch failed ({exc}); skipping".format(
                year=year, exc=exc
            )
        )
        return ""


def _is_thin(new_count, ref_count):
    if ref_count is None or ref_count <= 0:
        return False
    return new_count < THIN_RATIO * ref_count


def maybe_write_converted(conf, year, json_path, data, existing_count, prev_count):
    """Write ``data`` unless it is a thin overwrite of a larger dump.

    Returns (status_suffix_or_None, new_count). ``rejected_thin`` means the
    existing file was kept. A prev-year thin dump still writes (unless also
    thinner than the existing file) but prints ERROR.
    """
    new_count = len(data)
    if _is_thin(new_count, existing_count):
        print(
            "ERROR: {conf} {year} new dump has {new} entries, < {ratio:.0%} of "
            "existing {old}; keeping the larger file and returning rejected_thin".format(
                conf=conf,
                year=year,
                new=new_count,
                ratio=THIN_RATIO,
                old=existing_count,
            )
        )
        return "rejected_thin", new_count

    if _is_thin(new_count, prev_count):
        print(
            "ERROR: {conf} {year} has {new} entries, < {ratio:.0%} of {prev_year} "
            "({prev}); treating as incomplete".format(
                conf=conf,
                year=year,
                new=new_count,
                ratio=THIN_RATIO,
                prev_year=year - 1,
                prev=prev_count,
            )
        )

    write_json_data(json_path, data)
    return None, new_count


def process_conf_year(session, conf, year, args):
    json_path = os.path.join(args.data_dir, json_filename(conf, year))
    bib_path = os.path.join(args.raw_dir, bib_filename(conf, year))
    prev_path = os.path.join(args.data_dir, json_filename(conf, year - 1))
    entry = bib_list_entry(json_path, args.bib_list)

    existing_db = load_json_db(json_path)
    existing_count = len(existing_db) if existing_db is not None else None
    prev_count = dump_count(prev_path)
    json_exists = existing_db is not None
    bib_exists = os.path.isfile(bib_path)
    spec = venue_spec(conf)

    if json_exists and args.skip_existing and not args.force:
        threshold = min_count(conf, year)
        if existing_count >= threshold:
            print(
                "Skipping {conf} {year} (json exists, {n} >= min_count {m})".format(
                    conf=conf, year=year, n=existing_count, m=threshold
                )
            )
            ensure_bib_list_entry(args.bib_list, entry)
            return "skipped"
        print(
            "Existing {conf} {year} dump looks incomplete ({n} < min_count {m}); "
            "re-downloading".format(
                conf=conf, year=year, n=existing_count, m=threshold
            )
        )

    if (
        bib_exists
        and args.skip_existing
        and not args.force
        and not json_exists
        and args.convert
    ):
        print(
            "Reusing existing {bib}; converting without re-download".format(bib=bib_path)
        )
        data = bib_to_json_data(bib_path)
        rejected, _ = maybe_write_converted(
            conf, year, json_path, data, existing_count, prev_count
        )
        if rejected:
            return rejected
        ensure_bib_list_entry(args.bib_list, entry)
        return "converted"

    if bib_exists and args.skip_existing and not args.force and not json_exists:
        print("Skipping {conf} {year} (bib exists)".format(conf=conf, year=year))
        return "skipped"

    if session is None:
        raise RuntimeError(
            "Internal error: DBLP download required for {conf} {year} but no HTTP session is available".format(
                conf=conf, year=year
            )
        )
    cites = download_conf_year(session, conf, year, args.max_pages, args.sleep)
    if not cites.strip() and spec.get("openreview_fallback"):
        print(
            "No DBLP entries for {conf} {year}; trying OpenReview fallback".format(
                conf=conf, year=year
            )
        )
        cites = fetch_colm_openreview(year, session=session) or ""
    if not cites.strip():
        print(
            "No DBLP entries for {conf} {year}; skipping".format(conf=conf, year=year)
        )
        return "empty"

    os.makedirs(args.raw_dir, exist_ok=True)
    with open(bib_path, "w", encoding="utf-8") as handle:
        handle.write(cites)
    print("Wrote {path}".format(path=bib_path))

    if args.convert:
        data = bib_to_json_data(bib_path)
        rejected, _ = maybe_write_converted(
            conf, year, json_path, data, existing_count, prev_count
        )
        if rejected:
            return rejected
        ensure_bib_list_entry(args.bib_list, entry)
    return "downloaded"


def build_parser():
    current_year = datetime.date.today().year
    parser = argparse.ArgumentParser(
        prog="rebiber.download_dblp",
        description="Download DBLP BibTeX for major conferences and convert it for rebiber.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Default conferences:\n  {confs}\n\n"
            "NeurIPS uses DBLP short name 'nips' "
            "(neurips{{year}} from 2020, nips{{year}} before).\n"
            "TMLR / JMLR use journal toc paths; JMLR volume = year-1999 "
            "(jmlr2024 ← jmlr25.bht).\n"
            "KDD / MICCAI / ECCV try numbered volumes when the bare toc is empty.\n"
            "ECML is skipped: toc paths are renamed.\n"
            "COLM falls back to OpenReview when DBLP returns nothing.\n"
        ).format(confs=", ".join(DEFAULT_CONFS)),
    )
    parser.add_argument("--start-year", type=int, default=2024, help="First year (inclusive). Default: 2024")
    parser.add_argument(
        "--end-year",
        type=int,
        default=current_year,
        help="Last year (inclusive). Default: current year ({year})".format(year=current_year),
    )
    parser.add_argument(
        "--confs",
        type=str,
        default=None,
        help="Comma-separated conference list. Default: a built-in ML/CV/NLP set.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the json (or bib) already exists.",
    )
    parser.add_argument(
        "--skip-existing",
        dest="skip_existing",
        action="store_true",
        default=True,
        help="Skip conferences that already have a complete json (default: true).",
    )
    parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Download even when json/bib already exists (same as --force for skipping).",
    )
    parser.add_argument(
        "--raw-dir",
        default=os.path.join(PACKAGE_DIR, "raw_data"),
        help="Directory for downloaded .bib files (not committed). Default: <package>/raw_data",
    )
    parser.add_argument(
        "--data-dir",
        default=os.path.join(PACKAGE_DIR, "data"),
        help="Directory for converted .bib.json files. Default: <package>/data",
    )
    parser.add_argument(
        "--bib-list",
        default=os.path.join(PACKAGE_DIR, "bib_list.txt"),
        help="Path to bib_list.txt. Default: <package>/bib_list.txt",
    )
    parser.add_argument(
        "--convert",
        dest="convert",
        action="store_true",
        default=True,
        help="Convert downloaded bib files to json (default).",
    )
    parser.add_argument(
        "--no-convert",
        dest="convert",
        action="store_false",
        help="Only write raw .bib files; do not convert or update bib_list.txt.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=5,
        help="Seconds to wait after each successful DBLP request. Default: 5",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=60,
        help="Max DBLP pages per toc (f advances by actual hits; DBLP often "
        "returns 100/page). Default: 60 (~6000 papers).",
    )
    return parser


def _needs_http(confs, years, args):
    if args.force or (not args.skip_existing):
        return True
    for conf in confs:
        if conf in SKIPPED_CONFS:
            continue
        for year in years:
            json_path = os.path.join(args.data_dir, json_filename(conf, year))
            bib_path = os.path.join(args.raw_dir, bib_filename(conf, year))
            existing = load_json_db(json_path)
            if existing is None:
                if not os.path.isfile(bib_path):
                    return True
                continue
            if len(existing) < min_count(conf, year):
                return True
    return False


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.end_year < args.start_year:
        parser.error("--end-year must be >= --start-year")
    if args.max_pages < 1:
        parser.error("--max-pages must be >= 1")
    if args.sleep < 0:
        parser.error("--sleep must be >= 0")

    confs = parse_confs(args.confs)
    years = list(range(args.start_year, args.end_year + 1))

    os.makedirs(args.raw_dir, exist_ok=True)
    os.makedirs(args.data_dir, exist_ok=True)

    need_download = _needs_http(confs, years, args)

    session = None
    if need_download:
        if requests is None:
            parser.error(
                "The 'requests' package is required to download from DBLP. "
                "Install it with: pip install requests"
            )
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})

    counts = {
        "downloaded": 0,
        "converted": 0,
        "skipped": 0,
        "empty": 0,
        "failed": 0,
        "rejected_thin": 0,
    }
    for conf in confs:
        if conf in SKIPPED_CONFS:
            print("Skipping {conf}: {reason}".format(conf=conf, reason=SKIPPED_CONFS[conf]))
            counts["skipped"] += len(years)
            continue
        for year in years:
            try:
                status = process_conf_year(session, conf, year, args)
            except Exception as exc:
                print(
                    "Failed {conf} {year}: {exc}".format(conf=conf, year=year, exc=exc)
                )
                counts["failed"] += 1
                continue
            counts[status] = counts.get(status, 0) + 1

    print(
        "Done. downloaded={downloaded} converted={converted} skipped={skipped} "
        "empty={empty} failed={failed} rejected_thin={rejected_thin}".format(**counts)
    )
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

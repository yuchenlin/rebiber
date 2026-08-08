#!/usr/bin/env python3
"""Download DBLP BibTeX for major conferences and convert it for rebiber.

Works as::

    python -m rebiber.download_dblp
    python rebiber/download_dblp.py

After a successful download this writes ``raw_data/{conf}{year}.bib``, converts
it to ``data/{conf}{year}.bib.json`` (unless ``--no-convert``), and appends the
json path to ``bib_list.txt`` when missing.

DBLP toc query (same style as the original script)::

    toc:db/conf/{dblp_short}/{conf}{year}.bht:

NeurIPS lives under the historical ``nips`` key, so the toc path is
``db/conf/nips/neurips{year}.bht``. ECCV and ECML use multi-volume / renamed
toc paths that do not match this pattern; they are skipped unless you download
those volumes by hand and run ``scripts/add_conf.sh``.

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
PAGE_SIZE = 1000

# Conferences whose DBLP toc path is ``db/conf/{short}/{conf}{year}.bht``.
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
    "colm",  # skip quietly when the toc is empty
]

# DBLP folder name when it differs from the rebiber filename prefix.
SHORT_CONF_NAMES = {
    "neurips": "nips",
}

# Multi-volume / renamed proceedings; the standard toc query does not work.
SKIPPED_CONFS = {
    "eccv": "ECCV is split across db/conf/eccv/eccv{year}-N.bht volumes",
    "ecml": "ECML/PKDD toc paths are renamed (e.g. ecmlpkdd{year})",
}


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


def toc_query(conf, year):
    short = SHORT_CONF_NAMES.get(conf, conf)
    return "toc:db/conf/{short}/{conf}{year}.bht:".format(
        short=short, conf=conf, year=year
    )


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


def convert_bib(bib_path, json_path):
    build_json, load_bib_file = _import_bib2json()
    entries = load_bib_file(bib_path)
    data = build_json(entries)
    json_dir = os.path.dirname(json_path)
    if json_dir:
        os.makedirs(json_dir, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    print("Wrote {path} ({n} entries)".format(path=json_path, n=len(data)))
    return len(data)


def _is_rate_limited(response):
    if response.status_code == 429:
        return True
    text = response.text or ""
    return "Too Many Requests" in text


def fetch_page(session, query_string, page, sleep_s, max_retries=10):
    """Fetch one DBLP page; retry with backoff on 429 / transient errors."""
    params = {
        "q": query_string,
        "h": PAGE_SIZE,
        "f": page * PAGE_SIZE,
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

        if response.status_code != requests.codes.ok:
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


def download_conf_year(session, conf, year, max_pages, sleep_s):
    """Return concatenated BibTeX, or '' if DBLP has no entries."""
    query = toc_query(conf, year)
    chunks = []
    for page in range(max_pages):
        print(
            "Fetching {conf} {year} page {page} (f={offset})".format(
                conf=conf, year=year, page=page, offset=page * PAGE_SIZE
            )
        )
        text = fetch_page(session, query, page, sleep_s)
        if not text.strip() or "@" not in text:
            if page == 0:
                return ""
            print("stop (empty page)")
            break
        chunks.append(text)
        if text.count("@") < PAGE_SIZE:
            break
    return "".join(chunks)


def process_conf_year(session, conf, year, args):
    json_path = os.path.join(args.data_dir, "{conf}{year}.bib.json".format(conf=conf, year=year))
    bib_path = os.path.join(args.raw_dir, "{conf}{year}.bib".format(conf=conf, year=year))
    entry = bib_list_entry(json_path, args.bib_list)

    json_exists = os.path.isfile(json_path)
    bib_exists = os.path.isfile(bib_path)

    if json_exists and args.skip_existing and not args.force:
        print("Skipping {conf} {year} (json exists)".format(conf=conf, year=year))
        ensure_bib_list_entry(args.bib_list, entry)
        return "skipped"

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
        convert_bib(bib_path, json_path)
        ensure_bib_list_entry(args.bib_list, entry)
        return "converted"

    if bib_exists and args.skip_existing and not args.force:
        print("Skipping {conf} {year} (bib exists)".format(conf=conf, year=year))
        return "skipped"

    if session is None:
        raise RuntimeError(
            "Internal error: DBLP download required for {conf} {year} but no HTTP session is available".format(
                conf=conf, year=year
            )
        )
    cites = download_conf_year(session, conf, year, args.max_pages, args.sleep)
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
        convert_bib(bib_path, json_path)
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
            "(toc: db/conf/nips/neurips{{year}}.bht).\n"
            "ECCV / ECML are skipped: their toc paths are multi-volume or renamed.\n"
            "COLM (and any missing year) is skipped quietly when DBLP returns nothing.\n"
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
        help="Skip conferences that already have json (default: true).",
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
        default=8,
        help="Max DBLP pages per conference/year (h=1000). Default: 8",
    )
    return parser


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

    need_download = args.force or (not args.skip_existing)
    if not need_download:
        for conf in confs:
            if conf in SKIPPED_CONFS:
                continue
            for year in years:
                json_path = os.path.join(
                    args.data_dir, "{conf}{year}.bib.json".format(conf=conf, year=year)
                )
                bib_path = os.path.join(
                    args.raw_dir, "{conf}{year}.bib".format(conf=conf, year=year)
                )
                if not os.path.isfile(json_path) and not os.path.isfile(bib_path):
                    need_download = True
                    break
            if need_download:
                break

    session = None
    if need_download:
        if requests is None:
            parser.error(
                "The 'requests' package is required to download from DBLP. "
                "Install it with: pip install requests"
            )
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})

    counts = {"downloaded": 0, "converted": 0, "skipped": 0, "empty": 0, "failed": 0}
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
        "empty={empty} failed={failed}".format(**counts)
    )
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

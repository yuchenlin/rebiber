from rebiber.bib2json import normalize_title, load_bib_file
import argparse
import json
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile


ARXIV_SCAN_FIELDS = (
    "url",
    "doi",
    "eprint",
    "archiveprefix",
    "journal",
    "volume",
    "howpublished",
    "note",
)

# IDs that are clearly marked as arXiv / abs URLs.
ARXIV_PREFIX_RE = re.compile(
    r"(?:arxiv(?:\.org/(?:abs|pdf)?)?|abs)[\s:./\-]*"
    r"([0-9]{4})(?:\.|-)([0-9]{4,5})(?:v[0-9]+)?",
    re.IGNORECASE,
)
# Bare eprint values such as 2005.00683 or 2005.00683v2.
BARE_ARXIV_ID_RE = re.compile(r"^([0-9]{4}\.[0-9]{4,5})(?:v[0-9]+)?$")
CITEKEY_ARXIV_RE = re.compile(
    r"(?:abs|arxiv)[\-:_]([0-9]{4})[\-._]([0-9]{4,5})",
    re.IGNORECASE,
)
ARXIV_VENUE_RE = re.compile(r"arxiv|\bcorr\b|preprint", re.IGNORECASE)
PLACEHOLDER_VENUE_RE = re.compile(r"^[\s~\-{}]*$")


def str2bool(value):
    """Parse common boolean CLI strings. ``bool("False")`` is True; this is not."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "y", "t"):
        return True
    if text in ("false", "0", "no", "n", "f"):
        return False
    raise argparse.ArgumentTypeError(
        "Boolean value expected (true/false/1/0/yes/no), got %r" % (value,)
    )


def construct_bib_db(bib_list_file, start_dir=""):
    with open(bib_list_file) as f:
        filenames = f.readlines()
    bib_db = {}
    for filename in filenames:
        filename = filename.strip()
        if not filename:
            continue
        if filename.startswith("#") or filename.startswith("%") or filename.startswith("//"):
            continue
        path = os.path.join(start_dir, filename) if start_dir else filename
        if not os.path.isfile(path):
            print("WARNING: bib list file not found, skipping: %s" % path)
            continue
        with open(path) as f:
            db = json.load(f)
            print("Loaded:", f.name, "Size:", len(db))
        bib_db.update(db)
    return bib_db


def has_integer(line):
    return any(char.isdigit() for char in line)


def is_contain_var(line):
    # Never treat a full entry (single-line @article{...}) as a variable assignment.
    # Skipping those was dropping whole records that happened to contain month=.
    if line.lstrip().startswith("@"):
        return False
    if "month=" in line.lower().replace(" ", ""):
        return True  # special case
    line_clean = line.lower().replace(" ", "")
    if "=" in line_clean:
        # We ask if there is {, ', ", or if there is an integer in the line (since integer input is allowed)
        if ("{" in line_clean or '"' in line_clean or "'" in line_clean) or has_integer(
            line
        ):
            return False
        else:
            return True
    return False


def post_processing(output_bib_entries, removed_value_names, abbr_dict, sort):
    bibparser = bibtexparser.bparser.BibTexParser(ignore_nonstandard_types=False)
    bib_entry_str = ""
    for entry in output_bib_entries:
        for line in entry:
            if is_contain_var(line):
                continue
            bib_entry_str += line
        bib_entry_str += "\n"
    parsed_entries = bibtexparser.loads(bib_entry_str, bibparser)
    if len(parsed_entries.entries) != len(output_bib_entries) or (
        len(parsed_entries.entries) == 0 and len(output_bib_entries) > 0
    ):
        print(
            "Warning: len(parsed_entries.entries) != len(output_bib_entries) -->",
            len(parsed_entries.entries),
            len(output_bib_entries),
        )
        output_str = ""
        for entry in output_bib_entries:
            for line in entry:
                output_str += line
            output_str += "\n"
        return output_str
    for output_entry in parsed_entries.entries:
        for remove_name in removed_value_names:
            if remove_name in output_entry:
                del output_entry[remove_name]
        for short, pattern in abbr_dict:
            for place in ["booktitle", "journal"]:
                if place in output_entry:
                    if re.match(pattern, output_entry[place], flags=re.DOTALL):
                        output_entry[place] = short

    writer = BibTexWriter()
    if not sort:
        writer.order_entries_by = None
    return bibtexparser.dumps(parsed_entries, writer=writer)


def load_abbr_tsv(abbr_tsv_file):
    abbr_dict = []
    with open(abbr_tsv_file) as f:
        for line in f.read().splitlines():
            ls = line.split("|")
            if len(ls) == 2:
                abbr_dict.append((ls[0].strip(), ls[1].strip()))
    return abbr_dict


def strip_latex_markup(text):
    """Remove braces and common LaTeX accent commands from a name/title fragment."""
    if not text:
        return ""
    text = re.sub(r"\\[`'\"^~=.]", "", text)
    text = re.sub(r"\\[a-zA-Z]+\s*", "", text)
    text = text.replace("{", "").replace("}", "")
    return text.strip()


def extract_last_names(author_field):
    """Return a set of lowercased last names from a BibTeX author field.

    Handles ``Last, First``, ``First Last``, and ``Last1 and Last2``.
    """
    if not author_field:
        return set()
    last_names = set()
    parts = re.split(r"\s+and\s+", str(author_field).strip(), flags=re.IGNORECASE)
    for part in parts:
        part = strip_latex_markup(part)
        part = re.sub(r"\s+", " ", part).strip(" ,")
        # Strip trailing "et al." / "and others" before taking the last token.
        part = re.sub(r",?\s+et\s+al\.?\s*$", "", part, flags=re.IGNORECASE)
        part = re.sub(r",?\s+and\s+others\s*$", "", part, flags=re.IGNORECASE)
        part = part.strip(" ,")
        if not part:
            continue
        if part.lower() in ("others", "et al", "et al.", "etal"):
            continue
        if "," in part:
            last = part.split(",", 1)[0].strip()
        else:
            tokens = part.split()
            last = tokens[-1] if tokens else ""
        last = re.sub(r"[^0-9a-zA-Z\-']", "", last).lower()
        # Compare without punctuation so LeCun / lec.un still overlap.
        last = re.sub(r"[^a-z]", "", last)
        if last:
            last_names.add(last)
    return last_names


def authors_overlap(input_authors, db_authors):
    """True if last names overlap. Empty on either side is not a match."""
    input_names = extract_last_names(input_authors)
    db_names = extract_last_names(db_authors)
    if not input_names or not db_names:
        return False
    return bool(input_names & db_names)


def _meaningful_venue(value):
    if value is None:
        return False
    text = str(value).strip()
    if not text or PLACEHOLDER_VENUE_RE.match(text):
        return False
    return True


def looks_published(entry):
    """True when journal/booktitle look like a real venue, not an arXiv preprint."""
    for field in ("journal", "booktitle"):
        value = entry.get(field)
        if _meaningful_venue(value) and not ARXIV_VENUE_RE.search(value):
            return True
    return False


def entry_venue(entry_dict):
    """Return journal or booktitle (first meaningful value), else empty string."""
    if not entry_dict:
        return ""
    for field in ("journal", "booktitle"):
        value = entry_dict.get(field)
        if _meaningful_venue(value):
            return str(value).strip()
    return ""


def format_change_report(rows):
    """Format change rows as human-readable text. Pure: no I/O."""
    lines = ["===== Changes ====="]
    if not rows:
        lines.append("(none)")
        return "\n".join(lines) + "\n"
    for row in rows:
        cite_key = (row.get("cite_key") if row else None) or "<unknown>"
        reason = (row.get("reason") if row else None) or ""
        before = (row.get("before_venue") if row else None) or ""
        after = (row.get("after_venue") if row else None) or ""
        if after:
            venue_part = "%s -> %s" % (before or "-", after)
        elif before:
            venue_part = before
        else:
            venue_part = "-"
        if reason:
            lines.append("%s: %s (%s)" % (cite_key, venue_part, reason))
        else:
            lines.append("%s: %s" % (cite_key, venue_part))
    return "\n".join(lines) + "\n"


def _change_row(cite_key, before_venue, after_venue, reason):
    return {
        "cite_key": cite_key or "",
        "before_venue": before_venue or "",
        "after_venue": after_venue or "",
        "reason": reason or "",
    }


def _venue_from_lines(entry_lines):
    parsed, _warning = parse_bib_entry(entry_lines)
    if not parsed:
        return ""
    return entry_venue(parsed)


_CITE_COMMAND_RE = re.compile(
    r"\\(?:cite|citep|citet|citealp|citeyear|nocite)\s*\*?"
    r"(?:\s*\[[^\]]*\]){0,2}\s*\{([^}]*)\}",
    re.IGNORECASE,
)


def extract_cite_keys_from_tex(text):
    """Parse cite keys from LaTeX citation commands.

    Supports ``\\cite``, ``\\citep``, ``\\citet``, ``\\citealp``, ``\\citeyear``,
    and ``\\nocite``, including starred and optional-argument variants.
    Comma-separated lists are split. A bare ``*`` (as in ``\\nocite{*}``) is
    ignored rather than treated as a cite key.
    """
    if not text:
        return set()
    keys = set()
    for match in _CITE_COMMAND_RE.finditer(text):
        inner = match.group(1) or ""
        for part in inner.split(","):
            key = part.strip()
            if not key or key == "*":
                continue
            keys.add(key)
    return keys


def extract_cite_keys_from_tex_files(paths):
    """Read ``.tex`` files and return the union of their cite keys."""
    keys = set()
    for path in paths or []:
        with open(path, encoding="utf8") as handle:
            keys |= extract_cite_keys_from_tex(handle.read())
    return keys


def _normalize_arxiv_id(year_part, num_part):
    return "%s.%s" % (year_part, num_part)


def extract_arxiv_ids(entry):
    """Find arXiv ids only in allowed fields plus the cite key. Never scan abstracts."""
    found = set()

    def add_from_text(text, allow_bare=False):
        if not text:
            return
        text = str(text)
        for match in ARXIV_PREFIX_RE.finditer(text):
            found.add(_normalize_arxiv_id(match.group(1), match.group(2)))
        if allow_bare:
            bare = BARE_ARXIV_ID_RE.match(text.strip())
            if bare:
                found.add(bare.group(1))

    for field in ARXIV_SCAN_FIELDS:
        value = entry.get(field)
        if value is None:
            continue
        add_from_text(value, allow_bare=(field == "eprint"))

    cite_key = entry.get("ID") or ""
    if cite_key:
        for match in CITEKEY_ARXIV_RE.finditer(cite_key):
            found.add(_normalize_arxiv_id(match.group(1), match.group(2)))
        add_from_text(cite_key, allow_bare=False)

    return found


def fetch_arxiv_metadata(arxiv_id, timeout=5):
    """Query the arXiv API. Returns {} on any failure (never raises)."""
    url = "http://export.arxiv.org/api/query?id_list=%s&max_results=1" % arxiv_id
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "rebiber/1.3.0 (+https://github.com/yuchenlin/rebiber)"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
        root = ET.fromstring(payload)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        entry = root.find("atom:entry", ns)
        if entry is None:
            return {}
        meta = {}
        published = entry.find("atom:published", ns)
        if published is not None and published.text:
            meta["year"] = published.text[:4]
        primary = entry.find("arxiv:primary_category", ns)
        if primary is not None:
            term = primary.get("term")
            if term:
                meta["primary_class"] = term
        if "primary_class" not in meta:
            category = entry.find("atom:category", ns)
            if category is not None and category.get("term"):
                meta["primary_class"] = category.get("term")
        return meta
    except Exception as exc:
        print("WARNING: arXiv API query failed for %s (%s); continuing without metadata." % (arxiv_id, exc))
        return {}


def infer_year_from_arxiv_id(arxiv_id):
    try:
        yy = int(arxiv_id.split(".", 1)[0][:2])
    except (ValueError, IndexError):
        return ""
    return str(2000 + yy)


def build_arxiv_entry(entry, arxiv_id, meta=None):
    """Official arXiv @misc with archivePrefix/eprint/primaryClass/url."""
    meta = meta or {}
    year = meta.get("year") or entry.get("year") or infer_year_from_arxiv_id(arxiv_id)
    primary = meta.get("primary_class") or entry.get("primaryclass") or ""
    title = entry.get("title", "")
    author = entry.get("author", "")
    cite_key = entry.get("ID", "arxiv%s" % arxiv_id.replace(".", ""))

    lines = ["@misc{%s," % cite_key]
    lines.append("  title={%s}," % title)
    if author:
        lines.append("  author={%s}," % author)
    if year:
        lines.append("  year={%s}," % year)
    lines.append("  archivePrefix={arXiv},")
    lines.append("  eprint={%s}," % arxiv_id)
    if primary:
        lines.append("  primaryClass={%s}," % primary)
    lines.append("  url={https://arxiv.org/abs/%s}" % arxiv_id)
    lines.append("}")
    return [line + "\n" for line in lines]


def parse_bib_entry(bib_entry):
    """Parse a list-of-lines bib entry. Returns (entry_dict or None, warning_or_None)."""
    bibparser = bibtexparser.bparser.BibTexParser(ignore_nonstandard_types=False)
    filtered = [line for line in bib_entry if not is_contain_var(line)]
    bib_entry_str = " ".join(filtered)
    try:
        parsed = bibtexparser.loads(bib_entry_str, bibparser)
    except Exception as exc:
        return None, "failed to parse (%s)" % exc
    if not parsed.entries:
        # Retry on the raw text; month= filtering can gut single-line entries.
        try:
            parsed = bibtexparser.loads(" ".join(bib_entry), bibparser)
        except Exception as exc:
            return None, "failed to parse (%s)" % exc
    if not parsed.entries:
        return None, "failed to parse (empty result)"
    return parsed.entries[0], None


def replace_citation_key(entry_lines, new_key):
    """Rewrite the cite key of a DB entry to the user's original key."""
    new_lines = list(entry_lines)
    for line_idx, line in enumerate(new_lines):
        if not line.lstrip().startswith("@"):
            continue
        brace = line.find("{")
        if brace == -1:
            continue
        after = line[brace + 1 :]
        match = re.match(r"\s*([^,\s}]+)", after)
        if match and match.group(1):
            old_key = match.group(1)
            prefix = line[: brace + 1] + after[: match.start(1)]
            suffix = after[match.end(1) :]
            if suffix.lstrip().startswith(",") or suffix.lstrip().startswith("}"):
                new_lines[line_idx] = prefix + new_key + suffix
            else:
                new_lines[line_idx] = prefix + new_key + "," + suffix
            return new_lines
        # Key lives on the next line (rare DBLP style).
        if line_idx + 1 < len(new_lines):
            next_line = new_lines[line_idx + 1]
            match = re.match(r"\s*([^,\s}]+)", next_line)
            if match:
                old_key = match.group(1)
                new_lines[line_idx + 1] = next_line.replace(old_key, new_key, 1)
                return new_lines
        # No key found; insert one.
        new_lines[line_idx] = line[: brace + 1] + new_key + "," + after
        return new_lines
    return new_lines


def parse_db_authors(entry_lines):
    parsed, _warning = parse_bib_entry(entry_lines)
    if not parsed:
        return None
    return parsed.get("author")


def print_summary(stats):
    print("===== Summary =====")
    print("converted (official): %s" % stats["converted"])
    print("skipped_author_mismatch: %s" % stats["skipped_author_mismatch"])
    print("arxiv_normalized: %s" % stats["arxiv_normalized"])
    print("unchanged: %s" % stats["unchanged"])
    print("parse_warnings: %s" % stats["parse_warnings"])
    print("duplicates_removed: %s" % stats["duplicates_removed"])


def normalize_bib(
    bib_db,
    all_bib_entries,
    output_bib_path,
    deduplicate=True,
    removed_value_names=[],
    abbr_dict=[],
    sort=False,
    check_authors=True,
    format_only=False,
    dry_run=False,
    used_keys=None,
):
    removed_value_names = list(removed_value_names or [])
    abbr_dict = list(abbr_dict or [])
    if bib_db is None:
        bib_db = {}

    output_bib_entries = []
    bib_keys = set()
    changes = []
    stats = {
        "converted": 0,
        "skipped_author_mismatch": 0,
        "arxiv_normalized": 0,
        "unchanged": 0,
        "parse_warnings": 0,
        "duplicates_removed": 0,
    }

    for bib_entry in all_bib_entries:
        parsed_entry, parse_warning = parse_bib_entry(bib_entry)

        if parsed_entry is None or "title" not in parsed_entry:
            reason = parse_warning or "entry has no title"
            entry_id = ""
            if parsed_entry is not None:
                entry_id = parsed_entry.get("ID", "")
            else:
                joined = "".join(bib_entry)
                match = re.search(r"@\w+\{([^,\s}]+)", joined)
                if match:
                    entry_id = match.group(1)
            print(
                "WARNING: %s; keeping original. ID: %s"
                % (reason, entry_id or "<unknown>")
            )
            stats["parse_warnings"] += 1
            output_bib_entries.append(bib_entry)
            continue

        original_title = parsed_entry["title"]
        original_bibkey = parsed_entry.get("ID", "")
        if deduplicate and original_bibkey and original_bibkey in bib_keys:
            stats["duplicates_removed"] += 1
            continue
        if original_bibkey:
            bib_keys.add(original_bibkey)

        if format_only:
            output_bib_entries.append(bib_entry)
            stats["unchanged"] += 1
            continue

        if used_keys is not None and original_bibkey not in used_keys:
            output_bib_entries.append(bib_entry)
            stats["unchanged"] += 1
            continue

        if original_title:
            key_new = normalize_title(original_title, keep_digits=True)
            key_old = normalize_title(original_title, keep_digits=False)
            title = key_new if key_new in bib_db else key_old
        else:
            title = ""
        if title and title in bib_db:
            db_item = bib_db[title]
            db_authors = parse_db_authors(db_item)
            input_authors = parsed_entry.get("author")
            if check_authors and not authors_overlap(input_authors, db_authors):
                print(
                    "WARNING: title matched but no common author; keeping original. "
                    "ID: %s Title: %s DB authors: %s input authors: %s"
                    % (
                        original_bibkey,
                        original_title,
                        db_authors if db_authors is not None else "<none>",
                        input_authors if input_authors is not None else "<none>",
                    )
                )
                stats["skipped_author_mismatch"] += 1
                changes.append(
                    _change_row(
                        original_bibkey,
                        entry_venue(parsed_entry),
                        "",
                        "author_mismatch",
                    )
                )
                output_bib_entries.append(bib_entry)
                continue

            found_bibitem = replace_citation_key(db_item, original_bibkey)
            print(
                "Converted. ID: %s ; Title: %s" % (original_bibkey, original_title)
            )
            stats["converted"] += 1
            changes.append(
                _change_row(
                    original_bibkey,
                    entry_venue(parsed_entry),
                    _venue_from_lines(found_bibitem),
                    "converted",
                )
            )
            output_bib_entries.append(found_bibitem)
            continue

        arxiv_ids = extract_arxiv_ids(parsed_entry)
        if len(arxiv_ids) > 1:
            print(
                "WARNING: multiple arXiv IDs found; keeping original. ID: %s Title: %s IDs: %s"
                % (original_bibkey, original_title, sorted(arxiv_ids))
            )
            output_bib_entries.append(bib_entry)
            stats["unchanged"] += 1
            continue

        if len(arxiv_ids) == 1 and not looks_published(parsed_entry):
            arxiv_id = next(iter(arxiv_ids))
            meta = fetch_arxiv_metadata(arxiv_id)
            bib_entry = build_arxiv_entry(parsed_entry, arxiv_id, meta)
            print(
                "Converted arXiv entry. ID: %s ; Title: %s"
                % (original_bibkey, original_title)
            )
            stats["arxiv_normalized"] += 1
            changes.append(
                _change_row(
                    original_bibkey,
                    entry_venue(parsed_entry),
                    _venue_from_lines(bib_entry),
                    "arxiv_normalized",
                )
            )
            output_bib_entries.append(bib_entry)
            continue

        output_bib_entries.append(bib_entry)
        stats["unchanged"] += 1

    stats["changes"] = changes
    stats["report"] = format_change_report(changes)
    print_summary(stats)
    print(stats["report"], end="")
    output_string = post_processing(
        output_bib_entries, removed_value_names, abbr_dict, sort
    )
    stats["output"] = output_string

    if dry_run:
        print("Dry run: output not written.")
    elif output_bib_path:
        out_dir = os.path.dirname(output_bib_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(output_bib_path, "w", encoding="utf8") as output_file:
            output_file.write(output_string)
        print("Written to:", output_bib_path)

    return stats


def update(filepath):
    """Refresh packaged bib data from GitHub using stdlib only (Windows-friendly)."""
    url = "https://github.com/yuchenlin/rebiber/archive/refs/heads/main.zip"
    dest_dir = filepath
    tmpdir = tempfile.mkdtemp(prefix="rebiber_update_")
    try:
        zip_path = os.path.join(tmpdir, "rebiber.zip")
        print("Downloading", url)
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)

        extracted = os.path.join(tmpdir, "rebiber-main", "rebiber")
        if not os.path.isdir(extracted):
            extracted = None
            for root, dirs, _files in os.walk(tmpdir):
                if os.path.basename(root) == "rebiber" and "bib_list.txt" in _files:
                    extracted = root
                    break
        if extracted is None or not os.path.isdir(extracted):
            print("ERROR: could not find rebiber/ directory in downloaded archive.")
            return

        for name in ("bib_list.txt", "abbr.tsv"):
            src = os.path.join(extracted, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(dest_dir, name))
                print("Updated", name)
            else:
                print("WARNING: %s missing from archive" % name)

        data_src = os.path.join(extracted, "data")
        data_dst = os.path.join(dest_dir, "data")
        if os.path.isdir(data_src):
            os.makedirs(data_dst, exist_ok=True)
            for name in os.listdir(data_src):
                src = os.path.join(data_src, name)
                dst = os.path.join(data_dst, name)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
            print("Updated data/")
        else:
            print("WARNING: data/ missing from archive")
        print("Done Updating.")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def resolve_output_path(input_path, output_arg, num_inputs):
    if output_arg in (None, "same", ""):
        return input_path
    if os.path.isdir(output_arg):
        return os.path.join(output_arg, os.path.basename(input_path))
    if num_inputs > 1:
        raise ValueError(
            "When providing multiple input files, -o must be a directory "
            "or omitted/'same' (in-place)."
        )
    return output_arg


def build_parser(filepath=None):
    if filepath is None:
        filepath = os.path.dirname(os.path.abspath(__file__)) + "/"
    parser = argparse.ArgumentParser(
        description="Normalize BibTeX entries using official conference data."
    )
    parser.add_argument(
        "-u", "--update", action="store_true", help="Update the data of bib and abbr."
    )
    parser.add_argument(
        "-v", "--version", action="store_true", help="Print the version of Rebiber."
    )
    parser.add_argument(
        "-i",
        "--input_bib",
        nargs="+",
        type=str,
        help="The input bib file(s). Multiple paths are written in place "
        "or into -o if -o is a directory.",
    )
    parser.add_argument(
        "-o", "--output_bib", default="same", type=str, help="The output bib file or directory"
    )
    parser.add_argument(
        "-l",
        "--bib_list",
        default=filepath + "bib_list.txt",
        type=str,
        help="The list of candidate bib data.",
    )
    parser.add_argument(
        "-a",
        "--abbr_tsv",
        default=filepath + "abbr.tsv",
        type=str,
        help="The list of conference abbreviation data.",
    )
    parser.add_argument(
        "-d",
        "--deduplicate",
        default=True,
        type=str2bool,
        help="True to remove entries with duplicate keys.",
    )
    parser.add_argument(
        "-s",
        "--shorten",
        default=False,
        type=str2bool,
        help="True to shorten the conference names.",
    )
    parser.add_argument(
        "-r",
        "--remove",
        default="",
        type=str,
        help="A comma-separated list of values you want to remove, such as "
        "'--remove url,biburl,address,publisher'.",
    )
    parser.add_argument(
        "-st",
        "--sort",
        default=False,
        type=str2bool,
        help="True to sort the output BibTeX entries alphabetically by ID",
    )
    parser.add_argument(
        "--no-check-authors",
        action="store_true",
        help="Disable the same-author safety check for title matches.",
    )
    parser.add_argument(
        "--format-only",
        action="store_true",
        help="Only pretty-print / apply abbreviations; skip DB matching and arXiv rewrite.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the conversion report but do not write output files.",
    )
    parser.add_argument(
        "--report",
        metavar="PATH",
        default=None,
        type=str,
        help="Optional file to also write the human-readable change report.",
    )
    parser.add_argument(
        "--used-in",
        nargs="+",
        metavar="FILE",
        default=None,
        help="Only convert or arXiv-normalize entries whose cite keys appear "
        "in these .tex files. Unused bib keys are left unchanged.",
    )
    return parser


def main(argv=None):
    filepath = os.path.dirname(os.path.abspath(__file__)) + "/"
    parser = build_parser(filepath)
    args = parser.parse_args(argv)

    if args.update:
        update(filepath)
        return

    if args.version:
        try:
            import importlib.metadata

            print(importlib.metadata.version("rebiber"))
        except Exception:
            print("unknown")
        return

    if not args.input_bib:
        parser.error("You need to specify an input path by -i xxx.bib")

    input_paths = args.input_bib
    try:
        output_paths = [
            resolve_output_path(path, args.output_bib, len(input_paths))
            for path in input_paths
        ]
    except ValueError as exc:
        parser.error(str(exc))

    if args.format_only:
        bib_db = {}
    else:
        bib_db = construct_bib_db(args.bib_list, start_dir=filepath)

    removed_value_names = [s.strip() for s in args.remove.split(",") if s.strip()]
    if args.shorten:
        abbr_dict = load_abbr_tsv(args.abbr_tsv)
    else:
        abbr_dict = []

    used_keys = None
    if args.used_in:
        used_keys = extract_cite_keys_from_tex_files(args.used_in)

    reports = []
    for input_path, output_path in zip(input_paths, output_paths):
        if len(input_paths) > 1:
            print("----- Processing:", input_path, "->", output_path, "-----")
        all_bib_entries = load_bib_file(input_path)
        stats = normalize_bib(
            bib_db,
            all_bib_entries,
            output_path,
            args.deduplicate,
            removed_value_names,
            abbr_dict,
            args.sort,
            check_authors=not args.no_check_authors,
            format_only=args.format_only,
            dry_run=args.dry_run,
            used_keys=used_keys,
        )
        reports.append(stats.get("report") or "")

    if args.report:
        report_dir = os.path.dirname(args.report)
        if report_dir:
            os.makedirs(report_dir, exist_ok=True)
        with open(args.report, "w", encoding="utf8") as report_file:
            report_file.write("".join(reports))
        print("Report written to:", args.report)


if __name__ == "__main__":
    main()

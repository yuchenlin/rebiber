import json
import re
import unicodedata
import bibtexparser
import argparse
from tqdm import tqdm
import os


filepath = os.path.dirname(os.path.abspath(__file__)) + "/"

_SKIP_ENTRY_PREFIXES = ("@string", "@comment", "@preamble")


def normalize_title(title_str, keep_digits=False):
    """Normalize a title to a lowercase key.

    Apply NFKD first so precomposed characters decompose (é → e + accent),
    then drop combining marks and strip non-letter characters.
    By default only ASCII letters are kept (compatible with existing dumps).
    Pass ``keep_digits=True`` to also keep ASCII digits (new dumps).
    """
    title_str = unicodedata.normalize("NFKD", title_str)
    title_str = "".join(ch for ch in title_str if not unicodedata.combining(ch))
    if keep_digits:
        title_str = re.sub(r"[^a-zA-Z0-9]", r"", title_str)
    else:
        title_str = re.sub(r"[^a-zA-Z]", r"", title_str)
    return title_str.lower().replace(" ", "").strip()


def _is_comment_line(stripped):
    return (
        stripped.startswith("%")
        or stripped.startswith("#")
        or stripped.startswith("//")
    )


def _is_skip_entry(stripped_lower):
    return any(stripped_lower.startswith(prefix) for prefix in _SKIP_ENTRY_PREFIXES)


def _is_month_field_line(line):
    """True only for a month= field assignment, not a whole @ entry."""
    stripped = line.lstrip()
    if stripped.startswith("@"):
        return False
    return re.match(r"month\s*=", stripped, flags=re.IGNORECASE) is not None


def _flush_entry(all_bib_entries, bib_entry_buffer):
    if bib_entry_buffer and bib_entry_buffer not in (["\n"], [""]):
        all_bib_entries.append(bib_entry_buffer)


def load_bib_file(bibpath):
    all_bib_entries = []
    with open(bibpath, encoding="utf-8-sig") as f:
        bib_entry_buffer = []
        lines = f.readlines() + ["\n"]

        brace_count = 0  # Keep track of opened and closed braces
        # When skipping @string/@comment/@preamble, track remaining braces.
        skip_brace_count = None

        for line in lines:
            stripped = line.strip()
            stripped_lower = stripped.lower()

            # Ignore comment lines only; do not wipe an in-progress entry.
            if _is_comment_line(stripped):
                continue

            if skip_brace_count is not None:
                skip_brace_count += line.count("{") - line.count("}")
                if skip_brace_count <= 0:
                    skip_brace_count = None
                continue

            # A line starting with @ starts a new entry (or a skip block).
            # If an unclosed leftover buffer exists, split there.
            if stripped.startswith("@"):
                if bib_entry_buffer:
                    print(
                        "WARNING: unclosed braces before next @ in %s; "
                        "splitting leftover buffer." % bibpath
                    )
                    _flush_entry(all_bib_entries, bib_entry_buffer)
                    bib_entry_buffer = []
                    brace_count = 0
                if _is_skip_entry(stripped_lower):
                    skip_brace_count = line.count("{") - line.count("}")
                    if skip_brace_count <= 0:
                        skip_brace_count = None
                    continue
                bib_entry_buffer = [line]
                brace_count = line.count("{") - line.count("}")
                if brace_count <= 0:
                    _flush_entry(all_bib_entries, bib_entry_buffer)
                    bib_entry_buffer = []
                    brace_count = 0
                continue

            if _is_skip_entry(stripped_lower):
                skip_brace_count = line.count("{") - line.count("}")
                if skip_brace_count <= 0:
                    skip_brace_count = None
                continue

            # Leading / between-entry junk: do not start a buffer.
            if not bib_entry_buffer:
                continue

            bib_entry_buffer.append(line)
            brace_count += line.count("{") - line.count("}")

            # End-of-entry when brace_count <= 0; reset to recover from extra }.
            if brace_count <= 0:
                _flush_entry(all_bib_entries, bib_entry_buffer)
                bib_entry_buffer = []
                brace_count = 0

    if bib_entry_buffer and bib_entry_buffer not in (["\n"], [""]):
        print(
            "WARNING: unclosed braces at end of %s; keeping leftover buffer."
            % bibpath
        )
        all_bib_entries.append(bib_entry_buffer)

    return all_bib_entries


def build_json(all_bib_entries):
    all_bib_dict = {}
    num_exceptions = 0
    for bib_entry in tqdm(all_bib_entries[:]):
        # Filter month= field lines only; never drop a whole @... line.
        bib_entry_str = " ".join(
            line for line in bib_entry if not _is_month_field_line(line)
        )
        try:
            bibparser = bibtexparser.bparser.BibTexParser(
                ignore_nonstandard_types=False
            )
            bib_entry_parsed = bibtexparser.loads(bib_entry_str, bibparser)
            bib_key = normalize_title(
                bib_entry_parsed.entries[0]["title"], keep_digits=True
            )
            if bib_key in all_bib_dict:
                print(
                    "WARNING: duplicate normalize_title key %r; keeping last."
                    % bib_key
                )
            all_bib_dict[bib_key] = bib_entry
        except Exception as e:
            print(bib_entry)
            print(e)
            num_exceptions += 1

    print("Number of exceptions:", num_exceptions)
    return all_bib_dict


def main():
    parser = argparse.ArgumentParser(
        prog="bib2json",
        description="Convert a BibTeX file into a title-keyed JSON dictionary.",
    )
    parser.add_argument(
        "-i",
        "--input_bib",
        default=os.path.join(filepath, "data", "acl.bib"),
        type=str,
        help="The input bib file",
    )
    parser.add_argument(
        "-o",
        "--output_json",
        default=os.path.join(filepath, "data", "acl.json"),
        type=str,
        help="The output json file",
    )
    args = parser.parse_args()

    all_bib_entries = load_bib_file(args.input_bib)
    all_bib_dict = build_json(all_bib_entries)
    with open(args.output_json, "w", encoding="utf8") as f:
        json.dump(all_bib_dict, f, indent=2)


if __name__ == "__main__":
    main()

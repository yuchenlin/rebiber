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

    Combining marks are dropped, then non-letter characters are stripped.
    By default only ASCII letters are kept (compatible with existing dumps).
    Pass ``keep_digits=True`` to also keep ASCII digits (new dumps).
    """
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


def load_bib_file(bibpath):
    all_bib_entries = []
    with open(bibpath, encoding="utf8") as f:
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

            if _is_skip_entry(stripped_lower):
                skip_brace_count = line.count("{") - line.count("}")
                if skip_brace_count <= 0:
                    skip_brace_count = None
                continue

            bib_entry_buffer.append(line)
            brace_count += line.count("{") - line.count("}")

            # If brace_count is zero, then all opened braces have been closed
            if brace_count == 0:
                # Filter out the entries that only contain ['\n'] or ['']
                if bib_entry_buffer != ["\n"] and bib_entry_buffer != [""]:
                    all_bib_entries.append(bib_entry_buffer)
                bib_entry_buffer = []

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
        bib_entry_str = " ".join(
            [
                line
                for line in bib_entry
                if not re.search(r"month\s*=", line, flags=re.IGNORECASE)
            ]
        ).lower()
        try:
            bib_entry_parsed = bibtexparser.loads(bib_entry_str)
            bib_key = normalize_title(
                bib_entry_parsed.entries[0]["title"], keep_digits=True
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

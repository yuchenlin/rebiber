from rebiber.bib2json import normalize_title, load_bib_file
import argparse
import json
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase # Corrected import
import os
import re


filepath = os.path.dirname(os.path.abspath(__file__)) + "/"


def construct_bib_db(bib_list_file, start_dir=""):
    with open(bib_list_file) as f:
        filenames = f.readlines()
    bib_db = {}
    for filename in filenames:
        with open(start_dir + filename.strip()) as f:
            db = json.load(f)
            print("Loaded:", f.name, "Size:", len(db))
        bib_db.update(db)
    return bib_db


def has_integer(line):
    return any(char.isdigit() for char in line)


def is_contain_var(line):
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


def post_processing(bib_database, removed_value_names, abbr_dict, sort): # Changed signature
    # bib_database is now a bibtexparser.BibDatabase object
    for output_entry in bib_database.entries: # Iterate through entries (dictionaries)
        for remove_name in removed_value_names:
            if remove_name in output_entry: # Access as dictionary
                del output_entry[remove_name]
        for short, pattern in abbr_dict:
            for place in ["booktitle", "journal"]:
                if place in output_entry: # Access as dictionary
                    if re.match(pattern, output_entry[place], flags=re.DOTALL): # Access as dictionary
                        output_entry[place] = short # Access as dictionary

    writer = BibTexWriter()
    if not sort:
        writer.order_entries_by = None
    return bibtexparser.dumps(bib_database, writer=writer) # Dump the BibDatabase object


def normalize_bib(
    bib_db,
    all_bib_entries,
    output_bib_path,
    deduplicate=True,
    removed_value_names=[],
    abbr_dict=[],
    sort=False,
):
    final_processed_entries = [] # List to store processed entry dictionaries
    num_converted = 0
    bib_keys = set()

    for bib_entry_lines in all_bib_entries:
        bibparser = bibtexparser.bparser.BibTexParser(ignore_nonstandard_types=False) # Moved inside loop
        bib_entry_str = " ".join(
            [line for line in bib_entry_lines if not is_contain_var(line)]
        )
        bib_entry_parsed = bibtexparser.loads(bib_entry_str, bibparser)

        if (
            len(bib_entry_parsed.entries) == 0
            or "title" not in bib_entry_parsed.entries[0] # Access as dictionary
        ):
            continue

        original_entry = bib_entry_parsed.entries[0] # This is a dictionary
        original_title = original_entry["title"] # Access as dictionary
        original_bibkey = original_entry["ID"] # Access as dictionary

        if deduplicate and original_bibkey in bib_keys:
            continue
        bib_keys.add(original_bibkey)

        # ArXiv reformatting logic
        arxiv_id_found = None
        arxiv_primary_class = None

        for field in ["url", "eprint", "note"]:
            if field in original_entry: # Access as dictionary
                # Regex to capture new style (YYMM.NNNNN) and old style (category/YYMMNNN) arXiv IDs
                # and optionally the category for new style, or the category for old style.
                match = re.search(
                    r"arxiv.org/(?:abs|pdf)/(?:([a-zA-Z.-]+)/)?([0-9]{4}\.[0-9]{5}(?:v[0-9]+)?|[a-zA-Z-]+/[0-9]{7})", # Changed regex
                    original_entry[field].lower(), # Access as dictionary
                )
                if match:
                    arxiv_id_found = match.group(2)
                    if match.group(1):
                        arxiv_primary_class = match.group(1)
                    print(f"arxiv_id_found: {arxiv_id_found}, arxiv_primary_class: {arxiv_primary_class}") # Debug print
                    break # Found it, no need to search other fields

        if arxiv_id_found:
            # Remove existing lowercase arXiv fields before adding new ones
            keys_to_remove_arxiv = []
            for key in original_entry.keys():
                if key.lower() in ["archiveprefix", "eprint", "primaryclass"]:
                    keys_to_remove_arxiv.append(key)
            for key in keys_to_remove_arxiv:
                del original_entry[key]

            original_entry["archivePrefix"] = "arXiv" # Access as dictionary
            original_entry["eprint"] = arxiv_id_found.split('v')[0] # Remove version
            if arxiv_primary_class:
                original_entry["primaryClass"] = arxiv_primary_class # Access as dictionary

            # Remove potentially redundant fields if they are just pointing to arXiv
            keys_to_delete = []
            for key in original_entry.keys():
                if key.lower() == "journal" and "arxiv" in original_entry[key].lower():
                    keys_to_delete.append(key)
                if key.lower() == "volume" and "abs/" in original_entry[key].lower():
                    keys_to_delete.append(key)
                if key.lower() == "url" and "arxiv.org" in original_entry[key].lower():
                    keys_to_delete.append(key)
            for key in set(keys_to_delete): # Use set to avoid deleting same key multiple times
                del original_entry[key]

            log_str = "Converted arXiv entry. ID: %s ; Title: %s" % (
                original_bibkey,
                original_title,
            )
            num_converted += 1
            print(log_str)
        
        # Handle bib_db mapping (if any) - smart merge
        title = normalize_title(original_title)
        if title in bib_db and title:
            found_bibitem = None
            for line_idx in range(len(bib_db[title])):
                line = bib_db[title][line_idx]
                if line.strip().startswith("@"):
                    bibkey = line[line.find("{") + 1 : -1]
                    if not bibkey:
                        bibkey = bib_db[title][line_idx + 1].strip()[:-1]
                    line = line.replace(bibkey, original_bibkey + ",")
                    found_bibitem = bib_db[title].copy()
                    found_bibitem[line_idx] = line
                    break
            if found_bibitem:
                found_entry_str = " ".join(
                    [line for line in found_bibitem if not is_contain_var(line)]
                )
                found_entry_parsed = bibtexparser.loads(found_entry_str, bibparser)
                if found_entry_parsed.entries:
                    # Remove arXiv-related fields from bib_db entry before merging
                    # to avoid conflicts and ensure our reformatting takes precedence.
                    keys_to_remove_from_found = []
                    for key in found_entry_parsed.entries[0].keys():
                        if key.lower() in ["archiveprefix", "eprint", "primaryclass"]:
                            keys_to_remove_from_found.append(key)
                    for key in keys_to_remove_from_found:
                        del found_entry_parsed.entries[0][key]

                    # Now merge the remaining fields from bib_db entry
                    original_entry.update(found_entry_parsed.entries[0])
                    
                    log_str = "Converted. ID: %s ; Title: %s" % (
                        original_bibkey,
                        original_title,
                    )
                    num_converted += 1
                    print(log_str)
            
        final_processed_entries.append(original_entry) # Append the modified dictionary

    print("Num of converted items:", num_converted)
    # Create a BibDatabase object from the list of processed entries
    final_bib_database = BibDatabase() # Use the imported BibDatabase
    final_bib_database.entries = final_processed_entries

    # post-formatting
    output_string = post_processing(
        final_bib_database, removed_value_names, abbr_dict, sort # Pass BibDatabase object
    )
    with open(output_bib_path, "w", encoding="utf8") as output_file:
        output_file.write(output_string)
    print("Written to:", output_bib_path)


def load_abbr_tsv(abbr_tsv_file):
    abbr_dict = []
    with open(abbr_tsv_file) as f:
        for line in f.read().splitlines():
            ls = line.split("|")
            if len(ls) == 2:
                abbr_dict.append((ls[0].strip(), ls[1].strip()))
    return abbr_dict


def update(filepath):
    def execute(cmd):
        print(cmd)
        os.system(cmd)

    execute(
        "wget https://github.com/yuchenlin/rebiber/archive/main.zip -O /tmp/rebiber.zip"
    )
    execute("unzip -o /tmp/rebiber.zip -d /tmp/")
    execute(f"cp /tmp/rebiber-main/rebiber/bib_list.txt {filepath}/bib_list.txt")
    execute(f"cp /tmp/rebiber-main/rebiber/abbr.tsv {filepath}/abbr.tsv")
    execute(f"cp /tmp/rebiber-main/rebiber/data/* {filepath}/data/")
    print("Done Updating.")


def main():
    filepath = os.path.dirname(os.path.abspath(__file__)) + "/"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-u", "--update", action="store_true", help="Update the data of bib and abbr."
    )
    parser.add_argument(
        "-v", "--version", action="store_true", help="Print the version of Rebiber."
    )
    parser.add_argument("-i", "--input_bib", type=str, help="The input bib file")
    parser.add_argument(
        "-o", "--output_bib", default="same", type=str, help="The output bib file"
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
        type=bool,
        help="True to remove entries with duplicate keys.",
    )
    parser.add_argument(
        "-s",
        "--shorten",
        default=False,
        type=bool,
        help="True to shorten the conference names.",
    )
    parser.add_argument(
        "-r",
        "--remove",
        default="",
        type=str,
        help="A comma-separated list of values you want to remove, such as '--remove url,biburl,address,publisher'.",
    )
    parser.add_argument(
        "-st",
        "--sort",
        default=False,
        type=bool,
        help="True to sort the output BibTeX entries alphabetically by ID",
    )
    args = parser.parse_args()

    if args.update:
        update(filepath)
        return

    if args.version:
        import importlib.metadata

        print(importlib.metadata.version("rebiber"))
        return

    assert args.input_bib is not None, "You need to specify an input path by -i xxx.bib"
    bib_db = construct_bib_db(args.bib_list, start_dir=filepath)
    all_bib_entries = load_bib_file(args.input_bib)
    output_path = args.input_bib if args.output_bib == "same" else args.output_bib
    removed_value_names = [s.strip() for s in args.remove.split(",")]
    if args.shorten:
        abbr_dict = load_abbr_tsv(args.abbr_tsv)
    else:
        abbr_dict = []
    normalize_bib(
        bib_db,
        all_bib_entries,
        output_path,
        args.deduplicate,
        removed_value_names,
        abbr_dict,
        args.sort,
    )


if __name__ == "__main__":
    main()
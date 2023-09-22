import json
import re
import sys
import bibtexparser
import argparse
from tqdm import tqdm
import os


filepath = os.path.dirname(os.path.abspath(__file__)) + '/'


def normalize_title(title_str):
    title_str = re.sub(r'[^a-zA-Z]',r'', title_str) 
    return title_str.lower().replace(" ", "").strip()


def load_bib_file(bibpath):
    all_bib_entries = []
    with open(bibpath, encoding='utf8') as f:
        bib_entry_buffer = []
        lines = f.readlines() + ["\n"]

        brace_count = 0  # Keep track of opened and closed braces

        for line in lines:
            if "@string" in line:
                continue
            if line.strip().startswith("%") or line.strip().startswith("#") or line.strip().startswith("//"):
                bib_entry_buffer = []
                continue
            
            bib_entry_buffer.append(line)
            brace_count += line.count("{") - line.count("}")

            # If brace_count is zero, then all opened braces have been closed
            if brace_count == 0:
                # Filter out the entries that only contain ['\n'] or ['']
                if bib_entry_buffer != ['\n'] and bib_entry_buffer != ['']:
                    all_bib_entries.append(bib_entry_buffer)
                bib_entry_buffer = []

    # print(all_bib_entries)
    return all_bib_entries


def build_json(all_bib_entries):
    all_bib_dict = {}
    num_expections = 0
    for bib_entry in tqdm(all_bib_entries[:]):
        bib_entry_str = " ".join([line for line in bib_entry if "month" not in line.lower()]).lower()
        try:
            bib_entry_parsed = bibtexparser.loads(bib_entry_str)
            bib_key = normalize_title(bib_entry_parsed.entries[0]["title"])
            all_bib_dict[bib_key] = bib_entry
        except Exception as e:
            print(bib_entry)
            print(e)
            num_expections += 1
            
    return all_bib_dict


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input_bib", default=filepath+"data/acl.bib",
                        type=str, help="The input bib file")
    parser.add_argument("-o", "--output_json", default=filepath+"data/acl.json",
                        type=str, help="The output json file")
    args = parser.parse_args()
    
    all_bib_entries = load_bib_file(args.input_bib)
    all_bib_dict = build_json(all_bib_entries)
    with open(args.output_json, "w") as f:
        json.dump(all_bib_dict, f, indent=2)

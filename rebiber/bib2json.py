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
    with open(bibpath) as f:
        bib_entry_buffer = []
        lines = f.readlines() + ["\n"]
        for ind, line in enumerate(lines):
            # line = line.strip()
            if "@string" in line:
                continue
            bib_entry_buffer.append(line)
            if line.strip() == "}" or (line.strip().endswith("}") and "{" not in line and ind+1<len(lines) and lines[ind+1]=="\n"):
                all_bib_entries.append(bib_entry_buffer)
                bib_entry_buffer = []
            
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

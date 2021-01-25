from bib2json import normalize_title, load_bib_file
import argparse
import json
import sys

def normalize_bib(bib_db, all_bib_entries):
    output_bib_entries = []
    log_text = ""
    for bib_entry in all_bib_entries:
        # read the title from this bib_entry
        original_title = ""
        original_bibkey = ""
        for entry in bib_entry:
            if entry.strip().startswith("@"):
                key_start_idx = entry.find('{')+1
                key_end_idx = len(entry)-2
                original_bibkey = entry[key_start_idx:key_end_idx].strip()
            if entry.strip().startswith("title"):
                start_idx = entry.find('=')+1
                while not entry[start_idx].isalpha():
                    start_idx += 1
                end_idx = len(entry)-1
                while not entry[end_idx].isalpha():
                    end_idx -= 1
                original_title = entry[start_idx:end_idx+1]
                break
        title = normalize_title(original_title)    
        # try to map the bib_entry to the keys in all_bib_entries
        if title in bib_db:
            output_bib_entries.append(bib_db[title])
            log_str = "Converted to the official format. ID: %s ; Title: %s" % (original_bibkey, original_title)
            print(log_str)
            log_text += log_str
        else:
            output_bib_entries.append(bib_entry)
            
    # TODO: write the log_text to a file 


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        bib_db = json.load(f)
    all_bib_entries = load_bib_file(sys.argv[2])
    normalize_bib(bib_db, all_bib_entries)
from bib2json import normalize_title, load_bib_file
import argparse
import json

with open("anthology.json") as f:
    acl_db = json.load(f)
all_bib_entries = load_bib_file("example_input.bib")


output_bib_entries = []
log_text = ""
for bib_entry in all_bib_entries:
    # read the title from this bib_entry
    original_title = ""
    original_bibkey = ""
    title = normalize_title(original_title)    
    # try to map the bib_entry to the keys in all_bib_entries
    if title in all_bib_entries:
        output_bib_entries.append(all_bib_entries[title])
        log_str = "Converted to the official format. ID: %s ; Title: %s" % (original_bibkey, original_title)
        print(log_str)
        log_text += log_str
    else:
        output_bib_entries.append(bib_entry)
        
# TODO: write the log_text to a file 


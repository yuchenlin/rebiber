from bib2json import normalize_title, load_bib_file
import argparse
import json
import bibtexparser
from tqdm import tqdm

def construct_bib_db(bib_list_file):
    with open(bib_list_file) as f:
        filenames = f.readlines()
    bib_db = {}
    for filename in filenames:
        print("Loading ... ", filename)
        with open(filename.strip()) as f:
            db = json.load(f)
            print(" Size: ", len(db))
        bib_db.update(db)        
    return bib_db


def normalize_bib(args, bib_db, all_bib_entries):
    output_bib_entries = []
    num_converted = 0
    for bib_entry in all_bib_entries:
        # read the title from this bib_entry
        original_title = ""
        original_bibkey = ""
        # for entry_idx in range(len(bib_entry)):
        #     entry = bib_entry[entry_idx]
        #     if entry.strip().startswith("@"):
        #         original_bibkey = entry[entry.find('{')+1:-1]
        #         if not original_bibkey:
        #             # the bib id is in the second line
        #             original_bibkey = bib_entry[entry_idx+1].strip()[:-1]
        #             print(original_bibkey)
        #     if entry.strip().lower().startswith("title"):
        #         start_idx = entry.find('=')+1
        #         while not entry[start_idx].isalpha():
        #             start_idx += 1
        #         end_idx = len(entry)-1
        #         while not entry[end_idx].isalpha():
        #             end_idx -= 1
        #         original_title = entry[start_idx:end_idx+1]
        #         break
        bib_entry_str = " ".join([line for line in bib_entry if "month" not in line.lower()]).lower()
        bib_entry_parsed = bibtexparser.loads(bib_entry_str)
        if "title" not in bib_entry_parsed.entries[0]:
            continue
        original_title = bib_entry_parsed.entries[0]["title"]
        original_bibkey = bib_entry_parsed.entries[0]["ID"]
        title = normalize_title(original_title)    
        # try to map the bib_entry to the keys in all_bib_entries
        if title in bib_db and title:
            # update the bib_key to be the original_bib_key
            for line_idx in range(len(bib_db[title])):
                if bib_db[title][line_idx].strip().startswith("@"):
                    bibkey = bib_db[title][line_idx][bib_db[title][line_idx].find('{')+1:-1]
                    if not bibkey:
                        bibkey = bib_db[title][line_idx+1].strip()[:-1]
                    bib_db[title][line_idx] = bib_db[title][line_idx].replace(bibkey, original_bibkey)
                    break
            log_str = "Converted. ID: %s ; Title: %s" % (original_bibkey, original_title)
            num_converted += 1
            print(log_str) 
            output_bib_entries.append(bib_db[title])
        else:
            output_bib_entries.append(bib_entry)
    print("Num of converted items:", num_converted)
    with open(args.output_bib, "w") as output_file:
        for entry in output_bib_entries:
            for line in entry:
                output_file.write(line)
            output_file.write("\n")
    print("Written to:", args.output_bib)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input_bib", default="example_input.bib",
                        type=str, help="The input bib file")
    parser.add_argument("-o", "--output_bib", default="example_output.bib",
                        type=str, help="The output bib file")
    parser.add_argument("-l", "--bib_list", default="bib_list.txt",
                        type=str, help="The list of candidate bib data.")
    args = parser.parse_args()

    bib_db = construct_bib_db(args.bib_list)
    all_bib_entries = load_bib_file(args.input_bib)
    normalize_bib(args, bib_db, all_bib_entries)
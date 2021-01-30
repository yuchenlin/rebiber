from rebiber.bib2json import normalize_title, load_bib_file
import argparse
import json
import bibtexparser
import os





def construct_bib_db(bib_list_file, start_dir=""):
    with open(bib_list_file) as f:
        filenames = f.readlines()
    bib_db = {}
    for filename in filenames:
        with open(start_dir+filename.strip()) as f:
            db = json.load(f)
            print("Loaded:", f.name, "Size:", len(db))
        bib_db.update(db)        
    return bib_db


def is_contain_var(line):
    if "month=" in line.lower().replace(" ",""):
        return True # special case
    line_clean = line.lower().replace(" ","")
    if "=" in line_clean:
        if '{' in line_clean or '"' in line_clean or "'" in line_clean:
            return False
        else:
            return True
    return False


def normalize_bib(bib_db, all_bib_entries, output_bib_path):
    output_bib_entries = []
    num_converted = 0
    for bib_entry in all_bib_entries:
        # read the title from this bib_entry
        original_title = ""
        original_bibkey = ""
        bib_entry_str = " ".join([line for line in bib_entry if not is_contain_var(line)])
        bib_entry_parsed = bibtexparser.loads(bib_entry_str)
        if len(bib_entry_parsed.entries)==0 or "title" not in bib_entry_parsed.entries[0]:
            continue
        original_title = bib_entry_parsed.entries[0]["title"]
        original_bibkey = bib_entry_parsed.entries[0]["ID"]
        title = normalize_title(original_title)    
        # try to map the bib_entry to the keys in all_bib_entries
        found_bibitem = None
        if title in bib_db and title:
            # update the bib_key to be the original_bib_key
            for line_idx in range(len(bib_db[title])):
                line = bib_db[title][line_idx]
                if line.strip().startswith("@"):
                    bibkey = line[line.find('{')+1:-1]
                    if not bibkey:
                        bibkey = bib_db[title][line_idx+1].strip()[:-1]
                    line = line.replace(bibkey, original_bibkey+",")
                    found_bibitem = bib_db[title].copy()
                    found_bibitem[line_idx] = line
                    break
            if found_bibitem:
                log_str = "Converted. ID: %s ; Title: %s" % (original_bibkey, original_title)
                num_converted += 1
                print(log_str)
                output_bib_entries.append(found_bibitem)
        else:
            output_bib_entries.append(bib_entry)
    print("Num of converted items:", num_converted)
    with open(output_bib_path, "w") as output_file:
        for entry in output_bib_entries:
            for line in entry:
                output_file.write(line)
            output_file.write("\n")
    print("Written to:", output_bib_path)



def main():
    filepath = os.path.dirname(os.path.abspath(__file__)) + '/'
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input_bib",
                        type=str, help="The input bib file")
    parser.add_argument("-o", "--output_bib", default="same",
                        type=str, help="The output bib file")
    parser.add_argument("-l", "--bib_list", default=filepath+"bib_list.txt",
                        type=str, help="The list of candidate bib data.")
    args = parser.parse_args()
    
    assert args.input_bib is not None, "You need to specify an input path by -i xxx.bib"
    bib_db = construct_bib_db(args.bib_list, start_dir=filepath)
    all_bib_entries = load_bib_file(args.input_bib)
    output_path = args.input_bib if args.output_bib == "same" else args.output_bib
    normalize_bib(bib_db, all_bib_entries, output_path)


if __name__ == "__main__":
    main()

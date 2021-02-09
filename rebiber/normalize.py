import rebiber
from rebiber.bib2json import normalize_title, load_bib_file
import argparse
import json
import bibtexparser
import os
import re



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

def post_processing(output_bib_entries, removed_value_names, abbr_dict):
    bibparser = bibtexparser.bparser.BibTexParser(ignore_nonstandard_types=False)
    bib_entry_str = ""
    for entry in output_bib_entries:
        for line in entry:
            if is_contain_var(line):
                continue
            bib_entry_str += line
        bib_entry_str += "\n"
    parsed_entries  = bibtexparser.loads(bib_entry_str, bibparser)
    if len(parsed_entries.entries) < len(output_bib_entries)-5:
        print("Warning: len(parsed_entries.entries) < len(output_bib_entries) -5 -->", len(parsed_entries.entries), len(output_bib_entries))
        output_str = "" 
        for entry in output_bib_entries:
            for line in entry:
                # if any([re.match(r".*%s.*=.*"%n, line) for n in removed_value_names if len(n)>1]):
                #     continue
                output_str += line
            output_str += "\n"
        return output_str
    for output_entry in parsed_entries.entries:
        for remove_name in removed_value_names:
            if remove_name in output_entry:
                del output_entry[remove_name]
        for short, pattern in abbr_dict.items():
            if "booktitle" in output_entry:
                if re.match(pattern, output_entry["booktitle"]):
                    output_entry["booktitle"] = short
                
    return bibtexparser.dumps(parsed_entries)


def normalize_bib(bib_db, all_bib_entries, output_bib_path, deduplicate=True, removed_value_names=[], abbr_dict={}):
    output_bib_entries = []
    num_converted = 0
    bib_keys = set()
    for bib_entry in all_bib_entries:
        # read the title from this bib_entry
        bibparser = bibtexparser.bparser.BibTexParser(ignore_nonstandard_types=False)
        original_title = ""
        original_bibkey = ""
        bib_entry_str = " ".join([line for line in bib_entry if not is_contain_var(line)])
        bib_entry_parsed = bibtexparser.loads(bib_entry_str, bibparser)
        if len(bib_entry_parsed.entries)==0 or "title" not in bib_entry_parsed.entries[0]:
            continue
        original_title = bib_entry_parsed.entries[0]["title"]
        original_bibkey = bib_entry_parsed.entries[0]["ID"]
        if deduplicate and original_bibkey in bib_keys:
            continue        
        bib_keys.add(original_bibkey)
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
    # post-formatting 
    output_string = post_processing(output_bib_entries, removed_value_names, abbr_dict)
    with open(output_bib_path, "w") as output_file:
        output_file.write(output_string)
    print("Written to:", output_bib_path)

def load_abbr_tsv(abbr_tsv_file):
    abbr_dict = {}
    with open(abbr_tsv_file) as f:
        for line in f.read().splitlines():
            ls = line.split("|")
            if len(ls) == 2:
                abbr_dict[ls[0].strip()] = ls[1].strip()
    return abbr_dict

def update(filepath):
    def execute(cmd):
        print(cmd)
        os.system(cmd)         
    execute("wget https://github.com/yuchenlin/rebiber/archive/main.zip -O /tmp/rebiber.zip")
    execute("unzip -o /tmp/rebiber.zip -d /tmp/")
    execute(f"cp /tmp/rebiber-main/rebiber/bib_list.txt {filepath}/bib_list.txt")
    execute(f"cp /tmp/rebiber-main/rebiber/abbr.tsv {filepath}/abbr.tsv")
    execute(f"cp /tmp/rebiber-main/rebiber/data/* {filepath}/data/")
    print("Done Updating.")

def main():
    filepath = os.path.dirname(os.path.abspath(__file__)) + '/'
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--update", action='store_true', help="Update the data of bib and abbr.")
    parser.add_argument("-v", "--version", action='store_true', help="Print the version of Rebiber.")
    parser.add_argument("-i", "--input_bib",
                        type=str, help="The input bib file")
    parser.add_argument("-o", "--output_bib", default="same",
                        type=str, help="The output bib file")
    parser.add_argument("-l", "--bib_list", default=filepath+"bib_list.txt",
                        type=str, help="The list of candidate bib data.")
    parser.add_argument("-a", "--abbr_tsv", default=filepath+"abbr.tsv",
                        type=str, help="The list of conference abbreviation data.")
    parser.add_argument("-d", "--deduplicate", default=True,
                        type=bool, help="True to remove entries with duplicate keys.")
    parser.add_argument("-s", "--shorten", default=False,
                        type=bool, help="True to shorten the conference names.")
    parser.add_argument("-r", "--remove", default="",
                        type=str, help="A comma-seperated list of values you want to remove, such as '--remove url,biburl,address,publisher'.")
    args = parser.parse_args()
    
    
    if args.update:
        update(filepath)
        return
    if args.version:
        print(rebiber.__version__)
        return
    
    
    assert args.input_bib is not None, "You need to specify an input path by -i xxx.bib"
    bib_db = construct_bib_db(args.bib_list, start_dir=filepath)
    all_bib_entries = load_bib_file(args.input_bib)
    output_path = args.input_bib if args.output_bib == "same" else args.output_bib
    removed_value_names = [s.strip() for s in args.remove.split(",")]
    if args.shorten:
        abbr_dict = load_abbr_tsv(args.abbr_tsv)
    else:
        abbr_dict = {}
    normalize_bib(bib_db, all_bib_entries, output_path, args.deduplicate, removed_value_names, abbr_dict)


if __name__ == "__main__":
    main()

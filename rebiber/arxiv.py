import json
import pickle
from typing import Dict

import bibtexparser
import typer
from functional import pseq
from rich.console import Console
from tqdm import tqdm

console = Console()


def construct_paper_db(bib_list_file, start_dir=""):
    with open(bib_list_file) as f:
        filenames = f.readlines()
    console.log(f"Loading bibs for {len(filenames)} conferences")
    entries = []
    for file in filenames:
        conf_entries = parse_conference_bib(start_dir + file.strip())
        entries.extend(conf_entries)

    console.log(f"Loaded {len(entries)} entries")
    console.log("Parsing entries")
    bib_db = pseq(entries).smap(parse_entry).dict()

    return bib_db


def parse_entry(title: str, entry: Dict):
    parser = bibtexparser.bparser.BibTexParser(interpolate_strings=False)
    return title, parser.parse("".join(entry)).entries[0]


def parse_conference_bib(data_path: str):
    with open(data_path) as f:
        db = json.load(f)
        return list(db.items())


def load_bibfile(bib_path: str):
    parser = bibtexparser.bparser.BibTexParser(interpolate_strings=False)
    return parser.parse(bib_path)


def main(
    bib_path: str = "/tmp/pedro.bib",
    bib_list: str = "rebiber/bib_list.txt",
    filepath: str = "rebiber/",
):
    bib_db = construct_paper_db(bib_list, start_dir=filepath)

    console.log("Caching papers")
    with open("/tmp/papers_bib.picle", "wb") as f:
        pickle.dump(bib_db, f)
    bibliography = load_bibfile(bib_path)

    console.log(f"Read bibliography: {len(bibliography)} Entries")

    for entry in bibliography.entries:
        pass


if __name__ == "__main__":
    typer.run(main)

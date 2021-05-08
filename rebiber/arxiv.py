import json
import os
import pickle
from typing import Dict

import bibtexparser
import typer
from functional import pseq
from rich.console import Console

from rebiber.bib2json import normalize_title

console = Console()

app = typer.Typer()


def construct_paper_db(bib_list_file, start_dir=""):
    with open(bib_list_file) as f:
        filenames = f.readlines()
    console.log(f"Loading bibs for {len(filenames)} conferences")
    entries = []
    original_entries = {}
    for file in filenames:
        with open(start_dir + file.strip()) as f:
            conf_entries = json.load(f)
        for title, str_entry in conf_entries.items():
            entries.append((title, str_entry))
            original_entries[title] = str_entry

    console.log(f"Loaded {len(entries)} entries")
    console.log("Parsing entries")
    bib_db = pseq(entries).smap(parse_entry).dict()

    return bib_db, original_entries


def parse_entry(title: str, entry: Dict):
    parser = bibtexparser.bparser.BibTexParser(interpolate_strings=False)
    return title, parser.parse("".join(entry)).entries[0]


def load_bibfile(bib_path: str):
    parser = bibtexparser.bparser.BibTexParser(
        interpolate_strings=False, ignore_nonstandard_types=False
    )
    with open(bib_path) as f:
        contents = f.read()
    return parser.parse(contents)


def load_or_build_db(bib_list: str, start_dir: str, force: bool = False):
    if force or not os.path.exists("/tmp/papers_bib.pickle"):
        bib_db, original_entries = construct_paper_db(bib_list, start_dir=start_dir)
        console.log("Caching papers")
        with open("/tmp/papers_bib.pickle", "wb") as f:
            pickle.dump({"bib_db": bib_db, "original_entries": original_entries}, f)
    else:
        console.log("Loading cached papers")
        with open("/tmp/papers_bib.pickle", "rb") as f:
            cached = pickle.load(f)
            bib_db = cached["bib_db"]
            original_entries = cached["original_entries"]

    return bib_db, original_entries


@app.command()
def unarxiv(
    user_bib_path: str,
    bib_list: str = "rebiber/bib_list.txt",
    filepath: str = "rebiber/",
):
    console.log("Loading bibliography database")
    bib_db, original_entries = load_or_build_db(bib_list, start_dir=filepath)

    console.log("Loading user bibliography")
    bibliography = load_bibfile(user_bib_path)

    console.log(f"Read bibliography: {len(bibliography.entries)} Entries")

    writer = bibtexparser.bwriter.BibTexWriter()
    for entry in bibliography.entries:
        if entry["ENTRYTYPE"] == "article":
            if "archiveprefix" in entry or "arxiv" in entry.get("url", ""):
                entry_title = normalize_title(entry["title"])

                if entry_title in bib_db:
                    new_entry = "".join(original_entries[entry_title])
                    console.print("[bold red]Original entry:[/bold red]")
                    user_entry = "".join(writer._entry_to_bibtex(entry))
                    console.print(f"{user_entry}")
                    console.print("[bold green]New Entry:[/bold green]")
                    console.print(f"{new_entry}")
                    console.print(
                        "[bold yellow]-------------------------------------------[/bold yellow]"
                    )


@app.command()
def doi(
    user_bib_path: str,
    bib_list: str = "rebiber/bib_list.txt",
    filepath: str = "rebiber/",
):
    console.log("Loading bibliography database")
    bib_db, original_entries = load_or_build_db(bib_list, start_dir=filepath)

    console.log("Loading user bibliography")
    user_bibliography = load_bibfile(user_bib_path)

    console.log(f"Read bibliography: {len(user_bibliography.entries)} Entries")

    writer = bibtexparser.bwriter.BibTexWriter()
    for user_entry in user_bibliography.entries:
        entry_title = normalize_title(user_entry["title"])
        if "doi" not in user_entry:
            if entry_title in bib_db:
                db_entry = bib_db[entry_title]
                if "doi" in db_entry:
                    text_user_entry = "".join(writer._entry_to_bibtex(user_entry))
                    console.print("[bold red]Entry missing DOI:[/bold red]")
                    console.print(f"{text_user_entry}")

                    text_db_entry = "".join(original_entries[entry_title])
                    console.print("[bold green]Entry with DOI:[/bold green]")
                    console.print(f"DOI: {db_entry['doi']}")
                    console.print(f"{text_db_entry}")
                    console.print(
                        "[bold yellow]-----------------------------------------------------------------[/bold yellow]"
                    )


if __name__ == "__main__":
    app()

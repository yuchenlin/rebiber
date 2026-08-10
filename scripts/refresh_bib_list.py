#!/usr/bin/env python3
"""Refresh rebiber/bib_list.txt from JSON files in the data directory.

Drops ``data/acl.json`` (the full ACL dump can exceed GitHub's 100 MB limit),
includes ``data/acl_*.json`` chunks and ``data/*.bib.json``, unique and sorted.

Usage (from repo root)::

    python scripts/refresh_bib_list.py
    python scripts/refresh_bib_list.py --split-acl --chunk-size 50000
    python scripts/refresh_bib_list.py --dry-run
"""

import argparse
import json
import math
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_DATA_DIR = os.path.join(REPO_ROOT, "rebiber", "data")
DEFAULT_BIB_LIST = os.path.join(REPO_ROOT, "rebiber", "bib_list.txt")

# Workshop dumps are not part of the main index (cvprw / iccvw).
_WORKSHOP_PREFIXES = ("cvprw", "iccvw")


def is_workshop_dump(name):
    """True for CVPR/ICCV workshop dump filenames (not WACV, not www)."""
    base = os.path.basename(name).lower()
    return base.startswith(_WORKSHOP_PREFIXES)


def split_acl_json(data_dir, chunk_size=50000):
    """Split data/acl.json into data/acl_N.json chunks and remove acl.json."""
    acl_path = os.path.join(data_dir, "acl.json")
    if not os.path.isfile(acl_path):
        print("No {path} to split".format(path=acl_path))
        return 0

    with open(acl_path, encoding="utf-8") as handle:
        data = json.load(handle)

    for name in os.listdir(data_dir):
        if name.startswith("acl_") and name.endswith(".json"):
            os.remove(os.path.join(data_dir, name))

    items = list(data.items())
    if not items:
        print("acl.json is empty; removing it")
        os.remove(acl_path)
        return 0

    num_chunks = int(math.ceil(len(items) / float(chunk_size)))
    for index in range(num_chunks):
        chunk = dict(items[index * chunk_size : (index + 1) * chunk_size])
        fname = os.path.join(data_dir, "acl_{n}.json".format(n=index + 1))
        with open(fname, "w", encoding="utf-8") as handle:
            json.dump(chunk, handle, indent=2)
        print("Created {fname} with {n} entries".format(fname=fname, n=len(chunk)))

    os.remove(acl_path)
    print("Removed {path}".format(path=acl_path))
    return num_chunks


def collect_entries(data_dir, bib_list_path):
    """Build unique bib_list paths relative to the bib_list directory."""
    bib_list_dir = os.path.dirname(os.path.abspath(bib_list_path))
    data_dir = os.path.abspath(data_dir)
    entries = set()

    if os.path.isfile(bib_list_path):
        with open(bib_list_path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line == "data/acl.json" or line.endswith("/acl.json"):
                    continue
                if is_workshop_dump(line):
                    continue
                abs_path = os.path.normpath(os.path.join(bib_list_dir, line))
                if os.path.isfile(abs_path):
                    rel = os.path.relpath(abs_path, bib_list_dir).replace(os.sep, "/")
                    if rel == "data/acl.json" or rel.endswith("/acl.json"):
                        continue
                    if is_workshop_dump(rel):
                        continue
                    entries.add(rel)

    if os.path.isdir(data_dir):
        for name in os.listdir(data_dir):
            if name == "acl.json" or is_workshop_dump(name):
                continue
            path = os.path.join(data_dir, name)
            if not os.path.isfile(path):
                continue
            keep = name.endswith(".bib.json") or (
                name.startswith("acl_") and name.endswith(".json")
            )
            if not keep:
                continue
            rel = os.path.relpath(path, bib_list_dir).replace(os.sep, "/")
            entries.add(rel)

    return sorted(entries)


def write_bib_list(bib_list_path, entries, dry_run=False):
    text = "".join(entry + "\n" for entry in entries)
    if dry_run:
        print("Dry run: would write {n} entries to {path}".format(n=len(entries), path=bib_list_path))
        for entry in entries:
            print(entry)
        return
    parent = os.path.dirname(bib_list_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(bib_list_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("Wrote {n} unique entries to {path}".format(n=len(entries), path=bib_list_path))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Refresh rebiber/bib_list.txt from JSON files in data/."
    )
    parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        help="Directory containing conference JSON files. Default: rebiber/data",
    )
    parser.add_argument(
        "--bib-list",
        default=DEFAULT_BIB_LIST,
        help="Path to bib_list.txt. Default: rebiber/bib_list.txt",
    )
    parser.add_argument(
        "--split-acl",
        action="store_true",
        help="Split data/acl.json into data/acl_N.json chunks, then refresh the list.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=50000,
        help="Entries per acl_N.json chunk (keeps each file under ~100 MB). Default: 50000",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the refreshed list without writing bib_list.txt.",
    )
    args = parser.parse_args(argv)

    if args.chunk_size < 1:
        parser.error("--chunk-size must be >= 1")

    if args.split_acl and not args.dry_run:
        split_acl_json(args.data_dir, chunk_size=args.chunk_size)
    elif args.split_acl and args.dry_run:
        acl_path = os.path.join(args.data_dir, "acl.json")
        print("Dry run: would split {path} if present".format(path=acl_path))

    entries = collect_entries(args.data_dir, args.bib_list)
    write_bib_list(args.bib_list, entries, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())

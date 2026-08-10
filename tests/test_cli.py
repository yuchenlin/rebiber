"""CLI integration tests: default is offline; flags follow the advertised paths."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import bibtexparser

from rebiber.bib2json import normalize_title
from rebiber.normalize import build_parser, main


USED_TITLE = "A Completely Unique CLI Used Title Not In Packaged Dumps"
UNUSED_TITLE = "A Completely Unique CLI Unused Title Not In Packaged Dumps"
MISS_TITLE = "A Completely Unique CLI Local Miss Title Not In Packaged Dumps"

USED_KEY = "keepme"
UNUSED_KEY = "skipme"
MISS_KEY = "workshopmiss"


def _entry_lines(bibtex_str):
    return [line + "\n" for line in bibtex_str.strip().split("\n")]


def official_entry(title, author, booktitle):
    return """@inproceedings{official,
  title={%s},
  author={%s},
  booktitle={%s},
  year={2020}
}
""" % (
        title,
        author,
        booktitle,
    )


def article_entry(key, title, author, journal):
    return """@article{%s,
  title={%s},
  author={%s},
  journal={%s},
  year={2020}
}
""" % (
        key,
        title,
        author,
        journal,
    )


def write_tiny_bib_list(directory, title_to_official):
    """Write a one-file index that ``main`` can load via ``-l`` (absolute paths)."""
    db = {}
    for title, bibtex_str in title_to_official.items():
        db[normalize_title(title, keep_digits=True)] = _entry_lines(bibtex_str)
    json_path = os.path.join(directory, "tiny.json")
    with open(json_path, "w", encoding="utf8") as handle:
        json.dump(db, handle)
    list_path = os.path.join(directory, "bib_list.txt")
    with open(list_path, "w", encoding="utf8") as handle:
        handle.write(json_path + "\n")
    return list_path


def write_text(directory, name, text):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf8") as handle:
        handle.write(text)
    return path


def read_text(path):
    with open(path, encoding="utf8") as handle:
        return handle.read()


def parse_by_id(bib_text):
    parsed = bibtexparser.loads(bib_text)
    return {entry["ID"]: entry for entry in parsed.entries}


def raise_if_dblp_called(*_args, **_kwargs):
    raise AssertionError("search_dblp_by_title must not be called by default")


class TestCliMain(unittest.TestCase):
    def test_default_main_does_not_call_dblp(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = write_text(
                tmp,
                "in.bib",
                article_entry(
                    MISS_KEY,
                    MISS_TITLE,
                    "Ada Lovelace",
                    "Some Workshop Notes",
                ),
            )
            out_path = os.path.join(tmp, "out.bib")
            list_path = write_tiny_bib_list(tmp, {})
            with patch(
                "rebiber.normalize.search_dblp_by_title",
                side_effect=raise_if_dblp_called,
            ):
                main(["-i", in_path, "-o", out_path, "-l", list_path])
            self.assertTrue(os.path.isfile(out_path))
            entry = parse_by_id(read_text(out_path))[MISS_KEY]
            self.assertEqual(entry.get("journal"), "Some Workshop Notes")
            self.assertNotIn("booktitle", entry)

    def test_live_lookup_reaches_search_empty_keeps_original(self):
        calls = []

        def mock_search(title, timeout=10, opener=None):
            calls.append(title)
            return []

        with tempfile.TemporaryDirectory() as tmp:
            in_path = write_text(
                tmp,
                "in.bib",
                article_entry(
                    MISS_KEY,
                    MISS_TITLE,
                    "Ada Lovelace",
                    "Some Workshop Notes",
                ),
            )
            out_path = os.path.join(tmp, "out.bib")
            list_path = write_tiny_bib_list(tmp, {})
            with patch(
                "rebiber.normalize.search_dblp_by_title",
                side_effect=mock_search,
            ):
                main(
                    [
                        "-i",
                        in_path,
                        "-o",
                        out_path,
                        "-l",
                        list_path,
                        "--live-lookup",
                    ]
                )
            self.assertEqual(len(calls), 1)
            self.assertIn("Unique CLI Local Miss", calls[0])
            entry = parse_by_id(read_text(out_path))[MISS_KEY]
            self.assertEqual(entry.get("journal"), "Some Workshop Notes")
            self.assertNotIn("booktitle", entry)

    def test_dry_run_does_not_create_output_and_reports_converted_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = write_text(
                tmp,
                "in.bib",
                article_entry(
                    USED_KEY,
                    USED_TITLE,
                    "Ada Lovelace",
                    "Some Workshop Notes",
                ),
            )
            out_path = os.path.join(tmp, "out.bib")
            report_path = os.path.join(tmp, "report.txt")
            list_path = write_tiny_bib_list(
                tmp,
                {
                    USED_TITLE: official_entry(
                        USED_TITLE, "Ada Lovelace", "Proc. of ICML"
                    )
                },
            )
            with patch(
                "rebiber.normalize.search_dblp_by_title",
                side_effect=raise_if_dblp_called,
            ):
                main(
                    [
                        "-i",
                        in_path,
                        "-o",
                        out_path,
                        "-l",
                        list_path,
                        "--dry-run",
                        "--report",
                        report_path,
                    ]
                )
            self.assertFalse(os.path.isfile(out_path))
            report = read_text(report_path)
            self.assertIn(USED_KEY, report)
            self.assertIn("converted", report)
            self.assertIn("Proc. of ICML", report)

    def test_used_in_unused_key_not_converted(self):
        two_papers = article_entry(
            USED_KEY,
            USED_TITLE,
            "Ada Lovelace",
            "Some Workshop Notes",
        ) + article_entry(
            UNUSED_KEY,
            UNUSED_TITLE,
            "Alan Turing",
            "Some Workshop Notes",
        )
        with tempfile.TemporaryDirectory() as tmp:
            in_path = write_text(tmp, "in.bib", two_papers)
            out_path = os.path.join(tmp, "out.bib")
            tex_path = write_text(tmp, "paper.tex", r"See \cite{keepme}." + "\n")
            list_path = write_tiny_bib_list(
                tmp,
                {
                    USED_TITLE: official_entry(
                        USED_TITLE, "Ada Lovelace", "Proc. of ICML"
                    ),
                    UNUSED_TITLE: official_entry(
                        UNUSED_TITLE, "Alan Turing", "Proc. of NeurIPS"
                    ),
                },
            )
            with patch(
                "rebiber.normalize.search_dblp_by_title",
                side_effect=raise_if_dblp_called,
            ):
                main(
                    [
                        "-i",
                        in_path,
                        "-o",
                        out_path,
                        "-l",
                        list_path,
                        "--used-in",
                        tex_path,
                    ]
                )
            by_id = parse_by_id(read_text(out_path))
            self.assertEqual(by_id[USED_KEY].get("booktitle"), "Proc. of ICML")
            self.assertEqual(
                by_id[UNUSED_KEY].get("journal"), "Some Workshop Notes"
            )
            self.assertNotIn("booktitle", by_id[UNUSED_KEY])


class TestCliHelp(unittest.TestCase):
    def test_help_epilog_has_examples_and_arxiv_api_note(self):
        help_text = build_parser().format_help()
        self.assertIn("--dry-run", help_text)
        self.assertIn("--used-in", help_text)
        self.assertIn("--live-lookup", help_text)
        self.assertIn("--format-only", help_text)
        self.assertIn("rebiber -i input.bib --dry-run", help_text)
        self.assertIn("rebiber -i input.bib --used-in paper.tex", help_text)
        self.assertIn("rebiber -i input.bib --live-lookup", help_text)
        self.assertIn("rebiber -i input.bib -o pretty.bib --format-only", help_text)
        self.assertIn("arXiv API", help_text)


if __name__ == "__main__":
    unittest.main()

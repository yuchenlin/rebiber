import os
import tempfile
import unittest
from unittest.mock import patch

import bibtexparser

from rebiber.bib2json import load_bib_file, normalize_title
from rebiber.normalize import (
    authors_overlap,
    build_parser,
    construct_bib_db,
    extract_arxiv_ids,
    extract_last_names,
    looks_published,
    normalize_bib,
    str2bool,
)


NATURE_DEEP_LEARNING = """@article{deeplearning,
  title = {Deep Learning},
  author = {LeCun, Yann and Bengio, Yoshua and Hinton, Geoffrey},
  year = {2015},
  journal = {Nature},
  volume = {521},
  pages = {436--444}
}
"""

SHARED_AUTHOR_DEEP_LEARNING = """@article{mydeeplearning,
  title = {Deep Learning},
  author = {Salakhutdinov, Ruslan and Murray, Iain},
  year = {2013},
  journal = {arXiv preprint arXiv:1312.0001}
}
"""

NO_TITLE_ENTRY = """@misc{notitle,
  author = {Someone, A},
  year = {2020}
}
"""

ISSUE67_SINGLE_LINE = (
    "@article{X, title={X}, volume={X}, url={X}, DOI={X}, number={X}, "
    "journal={X}, author={X}, year={X}, month={X} }\n"
)

PUBLISHED_WITH_ARXIV_IN_ABSTRACT = """@article{Lu_2023,
  doi = {10.1088/1361-6544/acf988},
  url = {https://dx.doi.org/10.1088/1361-6544/acf988},
  year = {2023},
  journal = {Nonlinearity},
  author = {Yulong Lu and Dejan Slepcev and Lihan Wang},
  title = {Birth-death dynamics for sampling},
  abstract = {We improve results in previous works (Lu et al 2019 arXiv:1905.09863).}
}
"""

ARXIV_PREPRINT = """@article{lin2020birds,
  title = {Birds have four legs?! NumerSense},
  author = {Lin, Bill Yuchen and Lee, Seyeon and Khanna, Rahul and Ren, Xiang},
  journal = {arXiv preprint arXiv:2005.00683},
  year = {2020}
}
"""

DUP_KEY_BIB = """@article{samekey,
  title = {First Paper},
  author = {Ada Lovelace},
  year = {1843}
}

@article{samekey,
  title = {Second Paper},
  author = {Alan Turing},
  year = {1950}
}
"""


def _db_entry_lines(bibtex_str):
    lines = bibtex_str.strip().split("\n")
    return [line + "\n" for line in lines]


def deep_learning_db():
    key = normalize_title("Deep Learning")
    entry = """@inproceedings{kdd_dl,
  title={Deep Learning},
  author={Ruslan Salakhutdinov},
  booktitle={Proceedings of the 20th ACM SIGKDD International Conference on Knowledge Discovery and Data Mining},
  year={2014}
}
"""
    return {key: _db_entry_lines(entry)}


def official_title_db():
    """DB whose official title differs from a typical arXiv-style input title."""
    key = normalize_title("Deep Learning")
    entry = """@inproceedings{kdd_dl,
  title={Deep Learning: Official Title From DBLP},
  author={Ruslan Salakhutdinov},
  booktitle={KDD},
  year={2014}
}
"""
    return {key: _db_entry_lines(entry)}


def write_and_load(directory, bib_text, name="in.bib"):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf8") as handle:
        handle.write(bib_text)
    return load_bib_file(path), path


def parse_first_entry(bib_text):
    parsed = bibtexparser.loads(bib_text)
    if not parsed.entries:
        return None
    return parsed.entries[0]


def run_normalize(bib_text, bib_db, **kwargs):
    with tempfile.TemporaryDirectory() as tmp:
        entries, _inp = write_and_load(tmp, bib_text)
        out_path = os.path.join(tmp, "out.bib")
        stats = normalize_bib(bib_db, entries, out_path, **kwargs)
        output = ""
        if os.path.isfile(out_path):
            with open(out_path, encoding="utf8") as handle:
                output = handle.read()
        return output, stats


class TestStr2Bool(unittest.TestCase):
    def test_false_string_is_false(self):
        self.assertIs(str2bool("False"), False)
        self.assertIs(str2bool("false"), False)
        self.assertIs(str2bool("0"), False)
        self.assertIs(str2bool("no"), False)

    def test_true_string_is_true(self):
        self.assertIs(str2bool("True"), True)
        self.assertIs(str2bool("1"), True)
        self.assertIs(str2bool("yes"), True)

    def test_argparse_false_string(self):
        parser = build_parser()
        args = parser.parse_args(
            ["-i", "a.bib", "-s", "False", "-d", "False", "-st", "False"]
        )
        self.assertIs(args.shorten, False)
        self.assertIs(args.deduplicate, False)
        self.assertIs(args.sort, False)
        self.assertEqual(args.input_bib, ["a.bib"])

    def test_argparse_true_string(self):
        parser = build_parser()
        args = parser.parse_args(["-i", "a.bib", "-s", "True", "-d", "True", "-st", "True"])
        self.assertIs(args.shorten, True)
        self.assertIs(args.deduplicate, True)
        self.assertIs(args.sort, True)


class TestAuthorLastNames(unittest.TestCase):
    def test_last_comma_first(self):
        self.assertEqual(
            extract_last_names("LeCun, Yann and Bengio, Yoshua"),
            {"lecun", "bengio"},
        )

    def test_first_last(self):
        self.assertEqual(
            extract_last_names("Ruslan Salakhutdinov"),
            {"salakhutdinov"},
        )

    def test_last_and_last(self):
        self.assertEqual(extract_last_names("LeCun and Bengio"), {"lecun", "bengio"})

    def test_latex_braces(self):
        names = extract_last_names("Doll{\\'a}r, Piotr and Lin, Tsung-Yi")
        self.assertIn("dollar", names)
        self.assertIn("lin", names)

    def test_overlap_unknown_when_missing(self):
        self.assertTrue(authors_overlap("", "Ada Lovelace"))
        self.assertTrue(authors_overlap("Ada Lovelace", None))


class TestIssue50AuthorCheck(unittest.TestCase):
    def test_mismatch_keeps_original_when_check_authors(self):
        output, stats = run_normalize(
            NATURE_DEEP_LEARNING, deep_learning_db(), check_authors=True
        )
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["ID"], "deeplearning")
        self.assertIn("lecun", extract_last_names(entry.get("author", "")))
        self.assertNotIn("salakhutdinov", extract_last_names(entry.get("author", "")))
        self.assertEqual(entry.get("journal", "").lower(), "nature")
        self.assertEqual(stats["skipped_author_mismatch"], 1)
        self.assertEqual(stats["converted"], 0)

    def test_mismatch_converts_when_check_authors_disabled(self):
        output, stats = run_normalize(
            NATURE_DEEP_LEARNING, deep_learning_db(), check_authors=False
        )
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["ID"], "deeplearning")
        self.assertIn("salakhutdinov", extract_last_names(entry.get("author", "")))
        self.assertIn("booktitle", entry)
        self.assertEqual(stats["converted"], 1)
        self.assertEqual(stats["skipped_author_mismatch"], 0)

    def test_shared_author_converts_and_preserves_key(self):
        output, stats = run_normalize(
            SHARED_AUTHOR_DEEP_LEARNING, deep_learning_db(), check_authors=True
        )
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["ID"], "mydeeplearning")
        self.assertIn("salakhutdinov", extract_last_names(entry.get("author", "")))
        self.assertIn("booktitle", entry)
        self.assertEqual(stats["converted"], 1)


class TestIssue67KeepBrokenEntries(unittest.TestCase):
    def test_entry_without_title_is_kept(self):
        output, stats = run_normalize(NO_TITLE_ENTRY, {}, check_authors=True)
        self.assertIn("notitle", output)
        self.assertGreaterEqual(stats["parse_warnings"], 1)
        parsed = bibtexparser.loads(output)
        ids = [entry.get("ID") for entry in parsed.entries]
        self.assertIn("notitle", ids)

    def test_single_line_month_entry_not_dropped(self):
        output, stats = run_normalize(ISSUE67_SINGLE_LINE, {})
        self.assertTrue(output.strip(), "entry was silently dropped")
        self.assertIn("title", output.lower())
        entry = parse_first_entry(output)
        if entry is None:
            # Fallback raw dump still must contain the original key.
            self.assertIn("@article{X", output.replace(" ", ""))
        else:
            self.assertEqual(entry["ID"], "X")
            self.assertEqual(entry.get("title"), "X")


class TestIssue59ArxivFromAbstract(unittest.TestCase):
    def test_published_paper_not_rewritten_from_abstract(self):
        output, stats = run_normalize(PUBLISHED_WITH_ARXIV_IN_ABSTRACT, {})
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["ID"], "Lu_2023")
        self.assertEqual(entry.get("journal"), "Nonlinearity")
        self.assertNotEqual(entry.get("ENTRYTYPE"), "misc")
        self.assertNotIn("eprint", entry)
        url = entry.get("url", "")
        self.assertNotIn("arxiv.org", url.lower())
        self.assertEqual(stats["arxiv_normalized"], 0)
        self.assertFalse(looks_published({"journal": "arXiv preprint arXiv:1905.09863"}))
        ids = extract_arxiv_ids(
            {
                "ID": "Lu_2023",
                "journal": "Nonlinearity",
                "abstract": "see arXiv:1905.09863",
                "url": "https://dx.doi.org/10.1088/1361-6544/acf988",
            }
        )
        self.assertEqual(ids, set())


class TestIssue61OfficialArxivFormat(unittest.TestCase):
    @patch("rebiber.normalize.fetch_arxiv_metadata", return_value={})
    def test_journal_arxiv_becomes_eprint_form(self, _mock):
        output, stats = run_normalize(ARXIV_PREPRINT, {})
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["ENTRYTYPE"], "misc")
        self.assertEqual(entry["ID"], "lin2020birds")
        self.assertEqual(entry.get("eprint"), "2005.00683")
        self.assertEqual(entry.get("archiveprefix"), "arXiv")
        self.assertEqual(entry.get("url"), "https://arxiv.org/abs/2005.00683")
        self.assertIn("lin", extract_last_names(entry.get("author", "")))
        self.assertIn("NumerSense", entry.get("title", ""))
        self.assertNotIn("journal", entry)
        self.assertEqual(stats["arxiv_normalized"], 1)

    @patch(
        "rebiber.normalize.fetch_arxiv_metadata",
        return_value={"primary_class": "cs.CL", "year": "2020"},
    )
    def test_primary_class_from_api(self, _mock):
        output, _stats = run_normalize(ARXIV_PREPRINT, {})
        entry = parse_first_entry(output)
        self.assertEqual(entry.get("primaryclass"), "cs.CL")
        self.assertEqual(entry.get("year"), "2020")


class TestFormatOnlyAndDedup(unittest.TestCase):
    def test_format_only_does_not_replace_from_db(self):
        output, stats = run_normalize(
            NATURE_DEEP_LEARNING,
            official_title_db(),
            format_only=True,
            check_authors=False,
        )
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["ID"], "deeplearning")
        self.assertEqual(entry.get("title"), "Deep Learning")
        self.assertEqual(entry.get("journal"), "Nature")
        self.assertNotIn("booktitle", entry)
        self.assertNotIn("Official Title", entry.get("title", ""))
        self.assertEqual(stats["converted"], 0)
        self.assertEqual(stats["arxiv_normalized"], 0)

    def test_dedup_by_key(self):
        output, stats = run_normalize(DUP_KEY_BIB, {}, deduplicate=True)
        parsed = bibtexparser.loads(output)
        self.assertEqual(len(parsed.entries), 1)
        self.assertEqual(parsed.entries[0]["ID"], "samekey")
        self.assertIn("First Paper", parsed.entries[0].get("title", ""))
        self.assertEqual(stats["duplicates_removed"], 1)

    def test_dedup_disabled_keeps_both(self):
        output, stats = run_normalize(DUP_KEY_BIB, {}, deduplicate=False)
        parsed = bibtexparser.loads(output)
        self.assertEqual(len(parsed.entries), 2)
        self.assertEqual(stats["duplicates_removed"], 0)

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries, _inp = write_and_load(tmp, NATURE_DEEP_LEARNING)
            out_path = os.path.join(tmp, "out.bib")
            stats = normalize_bib(
                deep_learning_db(),
                entries,
                out_path,
                check_authors=True,
                dry_run=True,
            )
            self.assertFalse(os.path.isfile(out_path))
            self.assertIn("output", stats)


class TestConstructBibDb(unittest.TestCase):
    def test_skips_comments_blanks_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = os.path.join(tmp, "good.json")
            with open(good, "w", encoding="utf8") as handle:
                handle.write('{"hello": ["@article{a,\\n", "  title={Hello}\\n", "}\\n"]}')
            list_path = os.path.join(tmp, "bib_list.txt")
            with open(list_path, "w", encoding="utf8") as handle:
                handle.write("\n".join([
                    "",
                    "# a comment",
                    "% another",
                    "// also a comment",
                    "good.json",
                    "missing.json",
                    "",
                ]))
            db = construct_bib_db(list_path, start_dir=tmp)
            self.assertIn("hello", db)
            self.assertEqual(len(db), 1)


class TestBatchOutputPaths(unittest.TestCase):
    def test_multiple_inputs_require_directory_output(self):
        parser = build_parser()
        args = parser.parse_args(["-i", "a.bib", "b.bib", "-o", "out.bib"])
        from rebiber.normalize import resolve_output_path

        with self.assertRaises(ValueError):
            resolve_output_path("a.bib", args.output_bib, num_inputs=2)

    def test_multiple_inputs_same_are_inplace(self):
        from rebiber.normalize import resolve_output_path

        self.assertEqual(
            resolve_output_path("a.bib", "same", num_inputs=2), "a.bib"
        )


if __name__ == "__main__":
    unittest.main()

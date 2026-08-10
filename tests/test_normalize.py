import os
import tempfile
import unittest
from unittest.mock import patch

import bibtexparser

from rebiber.bib2json import load_bib_file, normalize_title
from rebiber.normalize import (
    DBLP_API,
    REBIBER_USER_AGENT,
    authors_overlap,
    build_parser,
    construct_bib_db,
    entry_venue,
    extract_arxiv_ids,
    extract_cite_keys_from_tex,
    extract_cite_keys_from_tex_files,
    extract_last_names,
    format_change_report,
    looks_published,
    main,
    normalize_bib,
    parse_bib_entry,
    post_processing,
    preserve_eprint,
    search_dblp_by_title,
    select_dblp_hit,
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

    def test_et_al_stripped_before_last_token(self):
        self.assertEqual(extract_last_names("De-An Huang et al."), {"huang"})
        self.assertEqual(extract_last_names("De-An Huang, et al."), {"huang"})
        self.assertEqual(extract_last_names("Huang, De-An et al."), {"huang"})
        self.assertEqual(extract_last_names("De-An Huang and others"), {"huang"})
        self.assertEqual(
            extract_last_names("De-An Huang et al. and Yann LeCun"),
            {"huang", "lecun"},
        )
        # Exact et al / others parts are still skipped.
        self.assertEqual(
            extract_last_names("Huang, De-An and et al."),
            {"huang"},
        )
        self.assertEqual(
            extract_last_names("Huang, De-An and others"),
            {"huang"},
        )
        self.assertTrue(authors_overlap("De-An Huang et al.", "Huang, De-An"))

    def test_overlap_empty_is_false(self):
        self.assertFalse(authors_overlap("", "Ada Lovelace"))
        self.assertFalse(authors_overlap("Ada Lovelace", None))
        self.assertFalse(authors_overlap("", None))


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


PREFACE_EDITOR_ONLY = """@inproceedings{preface,
  title={Preface},
  editor={Someone Editor},
  booktitle={Proceedings of Something},
  year={2020}
}
"""

JANE_DOE_PREFACE = """@article{janedoe,
  title={Preface},
  author={Jane Doe},
  year={2020}
}
"""


class TestFailClosedAuthorOverlap(unittest.TestCase):
    def test_preface_editor_only_does_not_convert_jane_doe(self):
        key = normalize_title("Preface")
        db = {key: _db_entry_lines(PREFACE_EDITOR_ONLY)}
        output, stats = run_normalize(
            JANE_DOE_PREFACE, db, check_authors=True
        )
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["ID"], "janedoe")
        self.assertIn("doe", extract_last_names(entry.get("author", "")))
        self.assertNotIn("booktitle", entry)
        self.assertEqual(stats["converted"], 0)
        self.assertEqual(stats["skipped_author_mismatch"], 1)


class TestDigitTitleKeys(unittest.TestCase):
    def test_16x16_matches_16x16_not_32x32(self):
        title_16 = "A 16x16 Convolution Network"
        title_32 = "A 32x32 Convolution Network"
        key_16 = normalize_title(title_16, keep_digits=True)
        key_32 = normalize_title(title_32, keep_digits=True)
        self.assertNotEqual(key_16, key_32)
        self.assertEqual(
            normalize_title(title_16, keep_digits=False),
            normalize_title(title_32, keep_digits=False),
        )
        entry_16 = """@inproceedings{n16,
  title={A 16x16 Convolution Network Official},
  author={Ada Lovelace},
  booktitle={TMLR},
  year={2024}
}
"""
        entry_32 = """@inproceedings{n32,
  title={A 32x32 Convolution Network Official},
  author={Ada Lovelace},
  booktitle={COLM},
  year={2024}
}
"""
        db = {
            key_16: _db_entry_lines(entry_16),
            key_32: _db_entry_lines(entry_32),
        }
        input_bib = """@article{mine,
  title={A 16x16 Convolution Network},
  author={Ada Lovelace},
  year={2024}
}
"""
        output, stats = run_normalize(input_bib, db, check_authors=True)
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(stats["converted"], 1)
        self.assertIn("16x16", entry.get("title", ""))
        self.assertNotIn("32x32", entry.get("title", ""))
        self.assertEqual(entry.get("booktitle"), "TMLR")


class TestPostProcessingCount(unittest.TestCase):
    def test_count_mismatch_dumps_raw(self):
        good = _db_entry_lines(
            """@article{ok,
  title={Ok},
  author={Ada},
  year={2020}
}
"""
        )
        bad = ["@article{broken,\n", "  title={No closing\n"]
        output = post_processing([good, bad], [], [], sort=False)
        self.assertIn("@article{ok", output.replace(" ", ""))
        self.assertIn("broken", output)
        self.assertIn("No closing", output)


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


class TestChangeReport(unittest.TestCase):
    def test_entry_venue_prefers_journal_then_booktitle(self):
        self.assertEqual(entry_venue({"journal": "Nature"}), "Nature")
        self.assertEqual(
            entry_venue({"booktitle": "Proceedings of EMNLP"}),
            "Proceedings of EMNLP",
        )
        self.assertEqual(
            entry_venue({"journal": "Nature", "booktitle": "KDD"}),
            "Nature",
        )
        self.assertEqual(entry_venue({"journal": " ~ "}), "")
        self.assertEqual(entry_venue({}), "")
        self.assertEqual(entry_venue(None), "")

    def test_format_change_report_is_pure_and_readable(self):
        text = format_change_report(
            [
                {
                    "cite_key": "abc",
                    "before_venue": "arXiv preprint",
                    "after_venue": "EMNLP",
                    "reason": "converted",
                }
            ]
        )
        self.assertIn("abc", text)
        self.assertIn("arXiv preprint", text)
        self.assertIn("EMNLP", text)
        self.assertIn("converted", text)
        empty = format_change_report([])
        self.assertIn("Changes", empty)
        self.assertIn("(none)", empty)

    def test_converted_row_names_cite_key_and_venues(self):
        output, stats = run_normalize(
            SHARED_AUTHOR_DEEP_LEARNING, deep_learning_db(), check_authors=True
        )
        entry = parse_first_entry(output)
        self.assertEqual(entry["ID"], "mydeeplearning")
        self.assertEqual(stats["converted"], 1)
        rows = stats["changes"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["cite_key"], "mydeeplearning")
        self.assertEqual(row["reason"], "converted")
        self.assertIn("arxiv", row["before_venue"].lower())
        self.assertTrue(row["after_venue"])
        self.assertIn("kdd", row["after_venue"].lower())
        self.assertIn("mydeeplearning", stats["report"])
        self.assertIn(row["before_venue"], stats["report"])
        self.assertIn(row["after_venue"], stats["report"])

    def test_author_mismatch_row(self):
        output, stats = run_normalize(
            NATURE_DEEP_LEARNING, deep_learning_db(), check_authors=True
        )
        entry = parse_first_entry(output)
        self.assertEqual(entry.get("journal", "").lower(), "nature")
        self.assertEqual(stats["skipped_author_mismatch"], 1)
        rows = stats["changes"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["cite_key"], "deeplearning")
        self.assertEqual(row["reason"], "author_mismatch")
        self.assertEqual(row["before_venue"].lower(), "nature")
        self.assertFalse(row["after_venue"])
        self.assertIn("deeplearning", stats["report"])
        self.assertIn("author_mismatch", stats["report"])

    @patch("rebiber.normalize.fetch_arxiv_metadata", return_value={})
    def test_arxiv_normalized_row(self, _mock):
        output, stats = run_normalize(ARXIV_PREPRINT, {})
        entry = parse_first_entry(output)
        self.assertEqual(entry["ID"], "lin2020birds")
        self.assertEqual(entry.get("eprint"), "2005.00683")
        self.assertEqual(stats["arxiv_normalized"], 1)
        rows = stats["changes"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["cite_key"], "lin2020birds")
        self.assertEqual(row["reason"], "arxiv_normalized")
        self.assertIn("arxiv", row["before_venue"].lower())
        self.assertIn("lin2020birds", stats["report"])
        self.assertIn("arxiv_normalized", stats["report"])

    def test_dry_run_does_not_create_output_bib(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries, _inp = write_and_load(tmp, SHARED_AUTHOR_DEEP_LEARNING)
            out_path = os.path.join(tmp, "out.bib")
            stats = normalize_bib(
                deep_learning_db(),
                entries,
                out_path,
                check_authors=True,
                dry_run=True,
            )
            self.assertFalse(os.path.isfile(out_path))
            self.assertEqual(stats["converted"], 1)
            self.assertTrue(stats["changes"])
            self.assertIn("mydeeplearning", stats["report"])
            self.assertIn("output", stats)

    def test_cli_report_flag_and_file(self):
        parser = build_parser()
        args = parser.parse_args(["-i", "a.bib", "--report", "changes.txt"])
        self.assertEqual(args.report, "changes.txt")
        with tempfile.TemporaryDirectory() as tmp:
            in_path = os.path.join(tmp, "in.bib")
            with open(in_path, "w", encoding="utf8") as handle:
                handle.write(NATURE_DEEP_LEARNING)
            report_path = os.path.join(tmp, "subdir", "report.txt")
            out_path = os.path.join(tmp, "out.bib")
            main(
                [
                    "-i",
                    in_path,
                    "-o",
                    out_path,
                    "--format-only",
                    "--dry-run",
                    "--report",
                    report_path,
                ]
            )
            self.assertFalse(os.path.isfile(out_path))
            self.assertTrue(os.path.isfile(report_path))
            with open(report_path, encoding="utf8") as handle:
                text = handle.read()
            self.assertIn("Changes", text)


TWO_PAPER_INPUT = """@article{alpha,
  title={Alpha Unique Title},
  author={Ada Lovelace},
  journal={arXiv preprint arXiv:2001.00001},
  year={2020}
}

@article{beta,
  title={Beta Unique Title},
  author={Alan Turing},
  journal={arXiv preprint arXiv:2002.00002},
  year={2020}
}
"""


def two_paper_db():
    entry_a = """@inproceedings{p1,
  title={Alpha Unique Title},
  author={Ada Lovelace},
  booktitle={ICML},
  year={2020}
}
"""
    entry_b = """@inproceedings{p2,
  title={Beta Unique Title},
  author={Alan Turing},
  booktitle={NeurIPS},
  year={2020}
}
"""
    return {
        normalize_title("Alpha Unique Title"): _db_entry_lines(entry_a),
        normalize_title("Beta Unique Title"): _db_entry_lines(entry_b),
    }


class TestExtractCiteKeys(unittest.TestCase):
    def test_cite_comma_list(self):
        self.assertEqual(extract_cite_keys_from_tex(r"\cite{a,b}"), {"a", "b"})
        self.assertEqual(extract_cite_keys_from_tex(r"\cite{a, b, c}"), {"a", "b", "c"})

    def test_citep_optional_arg(self):
        self.assertEqual(extract_cite_keys_from_tex(r"\citep[p.1]{c}"), {"c"})
        self.assertEqual(
            extract_cite_keys_from_tex(r"\citep[see][p.1]{opt}"), {"opt"}
        )

    def test_starred_and_other_macros(self):
        text = r"\cite*{starred} \citet{d} \citealp{e} \citeyear{f}"
        self.assertEqual(
            extract_cite_keys_from_tex(text), {"starred", "d", "e", "f"}
        )

    def test_nocite_star_ignored(self):
        self.assertEqual(extract_cite_keys_from_tex(r"\nocite{*}"), set())
        self.assertEqual(
            extract_cite_keys_from_tex(r"\nocite{keepme} \nocite{*}"),
            {"keepme"},
        )

    def test_extract_from_tex_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "paper.tex")
            with open(path, "w", encoding="utf8") as handle:
                handle.write(r"See \cite{a,b} and \citep[p.1]{c}." + "\n")
            extra = os.path.join(tmp, "app.tex")
            with open(extra, "w", encoding="utf8") as handle:
                handle.write(r"\citet{d}" + "\n")
            self.assertEqual(
                extract_cite_keys_from_tex_files([path, extra]),
                {"a", "b", "c", "d"},
            )


class TestUsedInFilter(unittest.TestCase):
    def test_unused_entries_stay_unchanged(self):
        output, stats = run_normalize(
            TWO_PAPER_INPUT,
            two_paper_db(),
            check_authors=True,
            used_keys={"alpha"},
        )
        parsed = bibtexparser.loads(output)
        by_id = {entry["ID"]: entry for entry in parsed.entries}
        self.assertEqual(by_id["alpha"].get("booktitle"), "ICML")
        self.assertIn("lovelace", extract_last_names(by_id["alpha"].get("author", "")))
        self.assertEqual(
            by_id["beta"].get("journal"), "arXiv preprint arXiv:2002.00002"
        )
        self.assertIn("turing", extract_last_names(by_id["beta"].get("author", "")))
        self.assertNotIn("booktitle", by_id["beta"])
        self.assertEqual(stats["converted"], 1)
        self.assertEqual(stats["unchanged"], 1)

    def test_used_entries_still_convert(self):
        output, stats = run_normalize(
            TWO_PAPER_INPUT,
            two_paper_db(),
            check_authors=True,
            used_keys={"alpha", "beta"},
        )
        parsed = bibtexparser.loads(output)
        by_id = {entry["ID"]: entry for entry in parsed.entries}
        self.assertEqual(by_id["alpha"].get("booktitle"), "ICML")
        self.assertEqual(by_id["beta"].get("booktitle"), "NeurIPS")
        self.assertEqual(stats["converted"], 2)
        self.assertEqual(stats["unchanged"], 0)

    def test_empty_used_keys_converts_nothing(self):
        output, stats = run_normalize(
            TWO_PAPER_INPUT,
            two_paper_db(),
            check_authors=True,
            used_keys=set(),
        )
        parsed = bibtexparser.loads(output)
        by_id = {entry["ID"]: entry for entry in parsed.entries}
        self.assertEqual(
            by_id["alpha"].get("journal"), "arXiv preprint arXiv:2001.00001"
        )
        self.assertEqual(
            by_id["beta"].get("journal"), "arXiv preprint arXiv:2002.00002"
        )
        self.assertEqual(stats["converted"], 0)
        self.assertEqual(stats["arxiv_normalized"], 0)
        self.assertEqual(stats["unchanged"], 2)

    def test_none_used_keys_keeps_current_behavior(self):
        output, stats = run_normalize(
            TWO_PAPER_INPUT,
            two_paper_db(),
            check_authors=True,
            used_keys=None,
        )
        self.assertEqual(stats["converted"], 2)

    def test_cli_used_in_flag(self):
        parser = build_parser()
        args = parser.parse_args(
            ["-i", "a.bib", "--used-in", "paper.tex", "extra.tex"]
        )
        self.assertEqual(args.used_in, ["paper.tex", "extra.tex"])

    @patch("rebiber.normalize.fetch_arxiv_metadata", return_value={})
    def test_unused_arxiv_not_normalized(self, mock_fetch):
        output, stats = run_normalize(
            ARXIV_PREPRINT, {}, used_keys={"someoneelse"}
        )
        entry = parse_first_entry(output)
        self.assertEqual(entry.get("journal"), "arXiv preprint arXiv:2005.00683")
        self.assertNotIn("eprint", entry)
        self.assertEqual(stats["arxiv_normalized"], 0)
        self.assertEqual(stats["unchanged"], 1)
        mock_fetch.assert_not_called()

    @patch("rebiber.normalize.fetch_arxiv_metadata", return_value={})
    def test_used_arxiv_still_normalized(self, _mock):
        output, stats = run_normalize(
            ARXIV_PREPRINT, {}, used_keys={"lin2020birds"}
        )
        entry = parse_first_entry(output)
        self.assertEqual(entry.get("eprint"), "2005.00683")
        self.assertEqual(stats["arxiv_normalized"], 1)


LIVE_UNIQUE_TITLE = "A Completely Unique Live Lookup Title That Is Not In Any Dump"
LIVE_PREPRINT_INPUT = """@article{mylivekey,
  title={A Completely Unique Live Lookup Title That Is Not In Any Dump},
  author={Ada Lovelace},
  journal={arXiv preprint arXiv:2101.01234},
  year={2021},
  eprint={2101.01234},
  archivePrefix={arXiv}
}
"""
LIVE_WORKSHOP_INPUT = """@article{mylivekey,
  title={A Completely Unique Live Lookup Title That Is Not In Any Dump},
  author={Ada Lovelace},
  journal={Some Workshop Notes},
  year={2021}
}
"""


def live_official_lines(with_eprint=False):
    extra = ""
    year_comma = ""
    if with_eprint:
        year_comma = ","
        extra = "  archivePrefix={arXiv},\n  eprint={9999.99999},\n"
    entry = """@inproceedings{dblpkey,
  title={A Completely Unique Live Lookup Title That Is Not In Any Dump},
  author={Ada Lovelace},
  booktitle={Proceedings of the 38th International Conference on Machine Learning},
  year={2021}%s
%s}
""" % (year_comma, extra)
    return _db_entry_lines(entry)


class TestLiveDblpLookup(unittest.TestCase):
    def test_local_miss_converts_from_mock_dblp(self):
        calls = []

        def mock_search(title, timeout=10, opener=None):
            calls.append(title)
            return [live_official_lines()]

        output, stats = run_normalize(
            LIVE_PREPRINT_INPUT,
            {},
            live_lookup=True,
            dblp_search=mock_search,
        )
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["ID"], "mylivekey")
        self.assertIn(
            "International Conference on Machine Learning",
            entry.get("booktitle", ""),
        )
        self.assertIn("lovelace", extract_last_names(entry.get("author", "")))
        self.assertEqual(stats["converted"], 1)
        self.assertEqual(stats["arxiv_normalized"], 0)
        self.assertEqual(len(calls), 1)
        self.assertIn("Unique Live Lookup", calls[0])
        rows = stats["changes"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cite_key"], "mylivekey")
        self.assertEqual(rows[0]["reason"], "converted_live")
        self.assertIn("machine learning", rows[0]["after_venue"].lower())

    def test_empty_hits_keep_original(self):
        def mock_search(title, timeout=10, opener=None):
            return []

        output, stats = run_normalize(
            LIVE_WORKSHOP_INPUT,
            {},
            live_lookup=True,
            dblp_search=mock_search,
        )
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["ID"], "mylivekey")
        self.assertEqual(entry.get("journal"), "Some Workshop Notes")
        self.assertNotIn("booktitle", entry)
        self.assertEqual(stats["converted"], 0)
        self.assertEqual(stats["unchanged"], 1)

    def test_raising_dblp_search_keeps_original(self):
        def boom(title, timeout=10, opener=None):
            raise RuntimeError("simulated network failure")

        output, stats = run_normalize(
            LIVE_WORKSHOP_INPUT,
            {},
            live_lookup=True,
            dblp_search=boom,
        )
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.get("journal"), "Some Workshop Notes")
        self.assertEqual(stats["converted"], 0)
        self.assertEqual(stats["unchanged"], 1)

    def test_search_dblp_by_title_opener_timeout_returns_empty(self):
        def boom(request, timeout=None):
            raise TimeoutError("simulated timeout")

        self.assertEqual(
            search_dblp_by_title(LIVE_UNIQUE_TITLE, opener=boom), []
        )

    def test_search_dblp_by_title_uses_api_and_user_agent(self):
        captured = {}

        class FakeResp(object):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return (
                    b"@inproceedings{x,\n"
                    b"  title={A Completely Unique Live Lookup Title That Is Not In Any Dump},\n"
                    b"  author={Ada Lovelace},\n"
                    b"  booktitle={ICML},\n"
                    b"  year={2021}\n"
                    b"}\n"
                )

        def fake_open(request, timeout=None):
            captured["url"] = request.full_url
            captured["ua"] = request.get_header("User-agent") or request.headers.get(
                "User-Agent"
            )
            captured["timeout"] = timeout
            return FakeResp()

        hits = search_dblp_by_title(LIVE_UNIQUE_TITLE, opener=fake_open)
        self.assertTrue(hits)
        self.assertIn(DBLP_API, captured["url"])
        self.assertIn("format=bibtex", captured["url"])
        self.assertIn("h=5", captured["url"])
        self.assertEqual(captured["ua"], REBIBER_USER_AGENT)
        parsed, _warning = parse_bib_entry(hits[0])
        self.assertEqual(parsed.get("booktitle"), "ICML")

    def test_eprint_preserved_when_official_lacks_it(self):
        def mock_search(title, timeout=10, opener=None):
            return [live_official_lines(with_eprint=False)]

        output, stats = run_normalize(
            LIVE_PREPRINT_INPUT,
            {},
            live_lookup=True,
            dblp_search=mock_search,
        )
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["ID"], "mylivekey")
        self.assertIn(
            "International Conference on Machine Learning",
            entry.get("booktitle", ""),
        )
        self.assertEqual(entry.get("eprint"), "2101.01234")
        self.assertEqual(entry.get("archiveprefix"), "arXiv")
        self.assertEqual(stats["converted"], 1)
        # Direct helper: official already has eprint -> leave it.
        kept = preserve_eprint(
            live_official_lines(with_eprint=True),
            {
                "title": LIVE_UNIQUE_TITLE,
                "eprint": "2101.01234",
                "journal": "arXiv preprint arXiv:2101.01234",
            },
        )
        parsed_kept = parse_first_entry("".join(kept))
        self.assertEqual(parsed_kept.get("eprint"), "9999.99999")

    def test_default_live_lookup_false_never_calls_spy(self):
        calls = []

        def spy(title, timeout=10, opener=None):
            calls.append(title)
            raise AssertionError("dblp_search must not be invoked by default")

        output, stats = run_normalize(
            LIVE_WORKSHOP_INPUT, {}, dblp_search=spy
        )
        self.assertEqual(calls, [])
        entry = parse_first_entry(output)
        self.assertEqual(entry.get("journal"), "Some Workshop Notes")
        self.assertEqual(stats["converted"], 0)
        self.assertEqual(stats["unchanged"], 1)

        output_false, stats_false = run_normalize(
            LIVE_WORKSHOP_INPUT,
            {},
            live_lookup=False,
            dblp_search=spy,
        )
        self.assertEqual(calls, [])
        self.assertEqual(
            parse_first_entry(output_false).get("journal"), "Some Workshop Notes"
        )
        self.assertEqual(stats_false["converted"], 0)

    def test_author_mismatch_does_not_apply_live_hit(self):
        def mock_search(title, timeout=10, opener=None):
            return [
                _db_entry_lines(
                    """@inproceedings{other,
  title={A Completely Unique Live Lookup Title That Is Not In Any Dump},
  author={Someone Else},
  booktitle={Proceedings of ICML},
  year={2021}
}
"""
                )
            ]

        output, stats = run_normalize(
            LIVE_WORKSHOP_INPUT,
            {},
            check_authors=True,
            live_lookup=True,
            dblp_search=mock_search,
        )
        entry = parse_first_entry(output)
        self.assertEqual(entry.get("journal"), "Some Workshop Notes")
        self.assertNotIn("booktitle", entry)
        self.assertEqual(stats["converted"], 0)
        selected = select_dblp_hit(
            {"title": LIVE_UNIQUE_TITLE, "author": "Ada Lovelace"},
            mock_search(LIVE_UNIQUE_TITLE),
            check_authors=True,
        )
        self.assertIsNone(selected)

    def test_local_hit_skips_live_search(self):
        calls = []

        def spy(title, timeout=10, opener=None):
            calls.append(title)
            return [live_official_lines()]

        output, stats = run_normalize(
            SHARED_AUTHOR_DEEP_LEARNING,
            deep_learning_db(),
            live_lookup=True,
            dblp_search=spy,
            check_authors=True,
        )
        self.assertEqual(calls, [])
        entry = parse_first_entry(output)
        self.assertEqual(entry["ID"], "mydeeplearning")
        self.assertIn("booktitle", entry)
        self.assertEqual(stats["converted"], 1)

    def test_cli_live_lookup_flag_default_off(self):
        parser = build_parser()
        args = parser.parse_args(["-i", "a.bib"])
        self.assertFalse(args.live_lookup)
        args = parser.parse_args(["-i", "a.bib", "--live-lookup"])
        self.assertTrue(args.live_lookup)


CAMERA_READY_INPUT = """@article{deeplearning,
  title = {Deep Learning with BERT and NLP},
  author = {LeCun, Yann},
  year = {2015},
  journal = {Nature},
  volume = {521},
  pages = {436--444},
  url = {https://example.com},
  note = {drop me},
  doi = {10.1038/nature14539}
}
"""


class TestCameraReadyNormalize(unittest.TestCase):
    def test_keep_fields_allowlist(self):
        output, _stats = run_normalize(
            CAMERA_READY_INPUT,
            {},
            format_only=True,
            keep_names=["author", "title", "journal", "year", "doi"],
        )
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["ID"], "deeplearning")
        self.assertEqual(entry["ENTRYTYPE"], "article")
        self.assertEqual(entry.get("title"), "Deep Learning with BERT and NLP")
        self.assertIn("author", entry)
        self.assertEqual(entry.get("journal"), "Nature")
        self.assertEqual(entry.get("doi"), "10.1038/nature14539")
        self.assertNotIn("url", entry)
        self.assertNotIn("note", entry)
        self.assertNotIn("pages", entry)
        self.assertNotIn("volume", entry)

    def test_protect_titles_wraps_acronyms(self):
        output, _stats = run_normalize(
            CAMERA_READY_INPUT, {}, format_only=True, protect_titles=True
        )
        entry = parse_first_entry(output)
        self.assertIsNotNone(entry)
        title = entry.get("title", "")
        self.assertIn("{BERT}", title)
        self.assertIn("{NLP}", title)
        self.assertNotEqual(title, "{Deep Learning with BERT and NLP}")
        self.assertIn("url", entry)

    def test_cli_keep_and_protect_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["-i", "a.bib"])
        self.assertEqual(args.keep, "")
        self.assertFalse(args.protect_titles)
        args = parser.parse_args(
            [
                "-i",
                "a.bib",
                "--keep",
                "author,title,booktitle,journal,year,volume,number,pages,doi",
                "--protect-titles",
            ]
        )
        self.assertEqual(
            args.keep,
            "author,title,booktitle,journal,year,volume,number,pages,doi",
        )
        self.assertTrue(args.protect_titles)


if __name__ == "__main__":
    unittest.main()

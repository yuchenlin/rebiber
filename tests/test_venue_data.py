"""Tests against real ICLR / ICML / NeurIPS / AAAI / ACL papers.

Two layers:

1. ``tests/fixtures/real_venues.json`` — 8 official 2025–2026 entries copied
   from the packaged dumps. Always runs in CI.
2. Optional full dump tests — load ``iclr2025.bib.json`` etc. when present so
   a data-update PR cannot ship a dump that no longer contains these papers.
"""

import json
import os
import tempfile
import unittest

import bibtexparser

from rebiber.bib2json import load_bib_file, normalize_title
from rebiber.normalize import extract_last_names, normalize_bib


PACKAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rebiber"))
DATA_DIR = os.path.join(PACKAGE_DIR, "data")
FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "real_venues.json")

# Scholar / arXiv-style inputs that should match the official dump entries.
ARXIV_STYLE_CASES = [
    {
        "id": "xu2025magpie",
        "title": "Magpie: Alignment Data Synthesis from Scratch by Prompting Aligned LLMs with Nothing",
        "author": "Zhangchen Xu and Fengqing Jiang and Luyao Niu and Yuntian Deng and Radha Poovendran and Yejin Choi and Bill Yuchen Lin",
        "venue_must_include": "ICLR",
        "year": "2025",
        "data_file": "iclr2025.bib.json",
        "fixture_key": "magpiealignmentdatasynthesisfromscratchbypromptingalignedllmswithnothing",
    },
    {
        "id": "zhang2025bfpo",
        "title": "Bi-Factorial Preference Optimization: Balancing Safety-Helpfulness in Language Models",
        "author": "Wenxuan Zhang and Philip Torr and Mohamed Elhoseiny and Adel Bibi",
        "venue_must_include": "ICLR",
        "year": "2025",
        "data_file": "iclr2025.bib.json",
        "fixture_key": "bifactorialpreferenceoptimizationbalancingsafetyhelpfulnessinlanguagemodels",
    },
    {
        "id": "chen2025gmflow",
        "title": "Gaussian Mixture Flow Matching Models",
        "author": "Hansheng Chen and Kai Zhang and Hao Tan and Zexiang Xu and Fujun Luan and Leonidas J. Guibas and Gordon Wetzstein and Sai Bi",
        "venue_must_include": "ICML",
        "year": "2025",
        "data_file": "icml2025.bib.json",
        "fixture_key": "gaussianmixtureflowmatchingmodels",
    },
    {
        "id": "li2025dataflow",
        "title": "Dataflow-Guided Neuro-Symbolic Language Models for Type Inference",
        "author": "Ge Li and Yao Wan and Hongyu Zhang and Zhou Zhao and Wenbin Jiang and Xuanhua Shi and Hai Jin and Zheng Wang",
        "venue_must_include": "ICML",
        "year": "2025",
        "data_file": "icml2025.bib.json",
        "fixture_key": "dataflowguidedneurosymboliclanguagemodelsfortypeinference",
    },
    {
        "id": "qin2025incentivize",
        "title": "Incentivizing Reasoning for Advanced Instruction-Following of Large Language Models",
        "author": "Yulei Qin and Gang Li and Zongyi Li and Zihan Xu and Yuchen Shi and Zhekai Lin and Xiao Cui and Ke Li and Xing Sun",
        "venue_must_include": "NeurIPS",
        "year": "2025",
        "data_file": "neurips2025.bib.json",
        "fixture_key": "incentivizingreasoningforadvancedinstructionfollowingoflargelanguagemodels",
    },
    {
        "id": "abate2026besteffort",
        "title": "Best-Effort Policies for Robust Markov Decision Processes",
        "author": "Alessandro Abate and Thom Badings and Giuseppe De Giacomo and Francesco Fabiano",
        "venue_must_include": "AAAI",
        "year": "2026",
        "data_file": "aaai2026.bib.json",
        "fixture_key": "besteffortpoliciesforrobustmarkovdecisionprocesses",
    },
    {
        "id": "le2026causal",
        "title": "Causal Direct Preference Optimization for Language Model Alignment",
        "author": "Le, Uyen and Nguyen, Thin and Nguyen, Toan and Doan, Toan and Le, Trung and Le, Bac",
        "venue_must_include": "EACL",
        "year": "2026",
        "data_file": "acl_1.json",
        "fixture_key": "causaldirectpreferenceoptimizationforlanguagemodelalignment",
    },
    {
        "id": "sun2025finegrained",
        "title": "Fine-Grained and Multi-Dimensional Metrics for Document-Level Machine Translation",
        "author": "Sun, Yirong and Zhu, Dawei and Chen, Yanjun and Xiao, Erjia and Chen, Xinghao and Shen, Xiaoyu",
        "venue_must_include": "Nations of the Americas",
        "year": "2025",
        "data_file": "acl_1.json",
        "fixture_key": "finegrainedandmultidimensionalmetricsfordocumentlevelmachinetranslation",
    },
]


def _as_article(case):
    return """@article{%s,
  title={%s},
  author={%s},
  journal={arXiv preprint},
  year={%s}
}
""" % (
        case["id"],
        case["title"],
        case["author"],
        case["year"],
    )


def _load_fixture_db():
    with open(FIXTURE_PATH, encoding="utf8") as handle:
        raw = json.load(handle)
    bib_db = {}
    for _stored_key, lines in raw.items():
        parsed = bibtexparser.loads("".join(lines))
        title = parsed.entries[0]["title"]
        bib_db[normalize_title(title)] = lines
    return bib_db, raw


def _run(bib_text, bib_db, **kwargs):
    with tempfile.TemporaryDirectory() as tmp:
        in_path = os.path.join(tmp, "in.bib")
        out_path = os.path.join(tmp, "out.bib")
        with open(in_path, "w", encoding="utf8") as handle:
            handle.write(bib_text)
        entries = load_bib_file(in_path)
        stats = normalize_bib(bib_db, entries, out_path, **kwargs)
        with open(out_path, encoding="utf8") as handle:
            output = handle.read()
    parsed = bibtexparser.loads(output)
    return output, parsed.entries, stats


def _data_path(name):
    return os.path.join(DATA_DIR, name)


class TestRealVenueFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bib_db, cls.raw = _load_fixture_db()

    def test_fixture_keys_match_normalize_title(self):
        for stored_key, lines in self.raw.items():
            parsed = bibtexparser.loads("".join(lines))
            title = parsed.entries[0]["title"]
            self.assertEqual(normalize_title(title), stored_key)

    def test_each_arxiv_style_input_becomes_official_venue(self):
        for case in ARXIV_STYLE_CASES:
            with self.subTest(paper=case["id"]):
                output, entries, stats = _run(_as_article(case), self.bib_db)
                self.assertEqual(len(entries), 1, output)
                entry = entries[0]
                self.assertEqual(entry["ID"], case["id"])
                self.assertEqual(stats["converted"], 1)
                self.assertEqual(stats["skipped_author_mismatch"], 0)
                venue = entry.get("booktitle") or entry.get("journal") or ""
                self.assertIn(case["venue_must_include"], venue)
                self.assertEqual(str(entry.get("year")), case["year"])
                self.assertTrue(
                    extract_last_names(case["author"])
                    & extract_last_names(entry.get("author", "")),
                    "official authors should overlap the input authors",
                )
                # Cite key must stay the user's key, not the DBLP/Anthology key.
                self.assertNotIn("DBLP:", entry["ID"])

    def test_batch_file_converts_all_fixture_papers(self):
        bib = "\n".join(_as_article(case) for case in ARXIV_STYLE_CASES)
        output, entries, stats = _run(bib, self.bib_db)
        self.assertEqual(len(entries), len(ARXIV_STYLE_CASES), output)
        self.assertEqual(stats["converted"], len(ARXIV_STYLE_CASES))
        self.assertEqual(stats["skipped_author_mismatch"], 0)
        ids = {entry["ID"] for entry in entries}
        self.assertEqual(ids, {case["id"] for case in ARXIV_STYLE_CASES})

    def test_wrong_author_not_converted_even_if_title_matches(self):
        magpie = ARXIV_STYLE_CASES[0]
        fake = """@article{imposter,
  title={%s},
  author={Doe, Jane and Smith, John},
  journal={arXiv preprint},
  year={2025}
}
""" % magpie["title"]
        output, entries, stats = _run(fake, self.bib_db, check_authors=True)
        self.assertEqual(len(entries), 1)
        self.assertEqual(stats["converted"], 0)
        self.assertEqual(stats["skipped_author_mismatch"], 1)
        self.assertEqual(entries[0].get("journal", "").lower(), "arxiv preprint")
        self.assertNotIn("ICLR", entries[0].get("booktitle", ""))


class TestPackagedConferenceDumps(unittest.TestCase):
    """Run only when the corresponding data file is in the package (data PR)."""

    def test_dump_contains_fixture_paper(self):
        seen = 0
        for case in ARXIV_STYLE_CASES:
            path = _data_path(case["data_file"])
            if not os.path.isfile(path):
                continue
            seen += 1
            with self.subTest(data_file=case["data_file"], paper=case["id"]):
                with open(path, encoding="utf8") as handle:
                    db = json.load(handle)
                key = normalize_title(case["title"])
                self.assertIn(
                    key,
                    db,
                    "%s is missing %s (%s)"
                    % (case["data_file"], case["title"], key),
                )
        if seen == 0:
            self.skipTest("no 2025/2026 conference dumps present")

    def test_full_iclr2025_dump_converts_magpie(self):
        path = _data_path("iclr2025.bib.json")
        if not os.path.isfile(path):
            self.skipTest("iclr2025.bib.json not packaged")
        with open(path, encoding="utf8") as handle:
            dump = json.load(handle)
        magpie = ARXIV_STYLE_CASES[0]
        output, entries, stats = _run(_as_article(magpie), dump)
        self.assertEqual(stats["converted"], 1)
        self.assertIn("ICLR", entries[0].get("booktitle", ""))
        self.assertEqual(entries[0]["ID"], "xu2025magpie")
        self.assertIn("lin", extract_last_names(entries[0].get("author", "")))

    def test_full_icml2025_dump_converts_gmflow(self):
        path = _data_path("icml2025.bib.json")
        if not os.path.isfile(path):
            self.skipTest("icml2025.bib.json not packaged")
        with open(path, encoding="utf8") as handle:
            dump = json.load(handle)
        case = ARXIV_STYLE_CASES[2]
        output, entries, stats = _run(_as_article(case), dump)
        self.assertEqual(stats["converted"], 1)
        self.assertIn("ICML", entries[0].get("booktitle", ""))

    def test_bib_list_paths_exist(self):
        list_path = os.path.join(PACKAGE_DIR, "bib_list.txt")
        if not os.path.isfile(list_path):
            self.skipTest("bib_list.txt missing")
        missing = []
        listed = 0
        with open(list_path, encoding="utf8") as handle:
            for line in handle:
                name = line.strip()
                if not name or name.startswith(("#", "%", "//")):
                    continue
                listed += 1
                path = os.path.join(PACKAGE_DIR, name)
                if not os.path.isfile(path):
                    missing.append(name)
        self.assertTrue(listed, "bib_list.txt is empty")
        self.assertEqual(missing, [], "bib_list.txt points at missing files")


if __name__ == "__main__":
    unittest.main()

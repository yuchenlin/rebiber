"""Unit tests for rebiber.download_dblp (HTTP is always mocked)."""

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOWNLOAD_PATH = _REPO_ROOT / "rebiber" / "download_dblp.py"
_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
_COLM_FIXTURE = _FIXTURE_DIR / "colm_openreview.json"

try:
    from rebiber import download_dblp as dd
except (ImportError, SyntaxError):
    _spec = importlib.util.spec_from_file_location("rebiber.download_dblp", _DOWNLOAD_PATH)
    dd = importlib.util.module_from_spec(_spec)
    sys.modules.setdefault("rebiber.download_dblp", dd)
    _spec.loader.exec_module(dd)


class FakeResponse:
    def __init__(self, text="", status_code=200, json_data=None):
        self.text = text
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json


def _args(tmp_path, **over):
    ns = argparse.Namespace(
        data_dir=str(tmp_path / "data"),
        raw_dir=str(tmp_path / "raw"),
        bib_list=str(tmp_path / "bib_list.txt"),
        skip_existing=True,
        force=False,
        convert=True,
        max_pages=2,
        sleep=0,
    )
    for key, value in over.items():
        setattr(ns, key, value)
    os.makedirs(ns.data_dir, exist_ok=True)
    os.makedirs(ns.raw_dir, exist_ok=True)
    return ns


def _write_json(path, n=0, data=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if data is None:
        data = {
            "title{i}".format(i=i): [
                "@article{{k{i},\n  title={{Title {i}}},\n}}\n".format(i=i)
            ]
            for i in range(n)
        }
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def _two_paper_bib(prefix="Paper"):
    return (
        "@inproceedings{{one,\n"
        "  title={{{prefix} Alpha}},\n"
        "  author={{Alice}},\n"
        "  year={{2024}}\n"
        "}}\n"
        "@inproceedings{{two,\n"
        "  title={{{prefix} Beta}},\n"
        "  author={{Bob}},\n"
        "  year={{2024}}\n"
        "}}\n"
    ).format(prefix=prefix)


def test_pagination_follows_server_cap_not_requested_h():
    """DBLP often returns 100 hits even when h=1000; keep paging by actual hit count."""

    def fake_get(url, params=None, headers=None, timeout=None):
        offset = int((params or {}).get("f", 0))
        if offset == 0:
            body = "".join(
                "@inproceedings{{p{i},\n  title={{P {i}}},\n}}\n".format(i=i)
                for i in range(100)
            )
            return FakeResponse(body)
        if offset == 100:
            body = "".join(
                "@inproceedings{{p{i},\n  title={{P {i}}},\n}}\n".format(i=i)
                for i in range(100, 200)
            )
            return FakeResponse(body)
        if offset == 200:
            body = "".join(
                "@inproceedings{{p{i},\n  title={{P {i}}},\n}}\n".format(i=i)
                for i in range(200, 220)
            )
            return FakeResponse(body)
        return FakeResponse("")

    session = mock.Mock()
    session.get.side_effect = fake_get
    text = dd.download_query_pages(
        session, "toc:db/conf/nips/neurips2025.bht:", max_pages=8, sleep_s=0
    )
    assert text.count("@") == 220
    offsets = [call.kwargs["params"]["f"] for call in session.get.call_args_list]
    assert offsets == [0, 100, 200]


def test_toc_queries_neurips_2019_vs_2025():
    assert list(dd.toc_queries("neurips", 2019)) == [
        "toc:db/conf/nips/nips2019.bht:"
    ]
    assert list(dd.toc_queries("neurips", 2025)) == [
        "toc:db/conf/nips/neurips2025.bht:"
    ]


def test_toc_queries_tmlr_2024():
    assert list(dd.toc_queries("tmlr", 2024)) == [
        "toc:db/journals/tmlr/tmlr2024.bht:"
    ]


def test_toc_queries_jmlr_2024_is_volume_25():
    assert list(dd.toc_queries("jmlr", 2024)) == [
        "toc:db/journals/jmlr/jmlr25.bht:"
    ]
    assert dd.jmlr_volume(2023) == 24
    assert dd.json_filename("jmlr", 2023) == "jmlr2023.bib.json"


def test_eccv_not_skipped_ecml_is():
    assert "eccv" not in dd.SKIPPED_CONFS
    assert "ecml" in dd.SKIPPED_CONFS
    assert dd.venue_spec("eccv")["kind"] == dd.KIND_CONF_MULTIVOL
    assert "tmlr" in dd.DEFAULT_CONFS
    assert "jmlr" in dd.DEFAULT_CONFS
    assert "wacv" in dd.DEFAULT_CONFS
    assert "miccai" in dd.DEFAULT_CONFS
    assert "colm" in dd.DEFAULT_CONFS
    assert "icra" in dd.DEFAULT_CONFS
    assert "iros" in dd.DEFAULT_CONFS
    assert "rss" in dd.DEFAULT_CONFS
    assert "corl" in dd.DEFAULT_CONFS


def test_toc_queries_robotics_main_tracks_not_workshops():
    assert list(dd.toc_queries("icra", 2025)) == ["toc:db/conf/icra/icra2025.bht:"]
    assert list(dd.toc_queries("iros", 2025)) == ["toc:db/conf/iros/iros2025.bht:"]
    assert list(dd.toc_queries("rss", 2025)) == ["toc:db/conf/rss/rss2025.bht:"]
    assert list(dd.toc_queries("corl", 2024)) == ["toc:db/conf/corl/corl2024.bht:"]
    assert dd.min_count("icra", 2025) == 1500
    assert dd.min_count("iros", 2024) == 1500
    assert dd.min_count("rss", 2025) == 0
    assert dd.min_count("corl", 2024) == 0


def test_multivol_yields_numbered_volumes_after_empty_bare():
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        query = (params or {}).get("q", "")
        calls.append(query)
        if query.endswith("eccv2022.bht:"):
            return FakeResponse("")
        if query.endswith("eccv2022-1.bht:"):
            return FakeResponse(
                "@inproceedings{a,\n  title={Volume One Paper},\n  author={A},\n  year={2022}\n}\n"
            )
        if query.endswith("eccv2022-2.bht:"):
            return FakeResponse(
                "@inproceedings{b,\n  title={Volume Two Paper},\n  author={B},\n  year={2022}\n}\n"
            )
        if query.endswith("eccv2022-3.bht:"):
            return FakeResponse("")
        return FakeResponse("")

    session = mock.Mock()
    session.get.side_effect = fake_get
    text = dd.download_conf_year(session, "eccv", 2022, max_pages=2, sleep_s=0)

    assert "Volume One Paper" in text
    assert "Volume Two Paper" in text
    assert "toc:db/conf/eccv/eccv2022.bht:" in calls
    assert "toc:db/conf/eccv/eccv2022-1.bht:" in calls
    assert "toc:db/conf/eccv/eccv2022-2.bht:" in calls
    assert "toc:db/conf/eccv/eccv2022-3.bht:" in calls
    # stopped after the first empty numbered volume
    assert not any(q.endswith("eccv2022-4.bht:") for q in calls)


def test_skip_incomplete_small_json_redownloads(tmp_path, monkeypatch):
    args = _args(tmp_path)
    json_path = Path(args.data_dir) / "neurips2024.bib.json"
    _write_json(json_path, n=5)
    assert len(json.loads(json_path.read_text(encoding="utf-8"))) == 5
    assert dd.min_count("neurips", 2024) == 1500

    called = []

    def fake_dl(session, conf, year, max_pages, sleep_s):
        called.append((conf, year))
        return _two_paper_bib("NeurIPS")

    monkeypatch.setattr(dd, "download_conf_year", fake_dl)
    status = dd.process_conf_year(object(), "neurips", 2024, args)

    assert called == [("neurips", 2024)]
    assert status == "downloaded"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(data) == 2


def test_skip_existing_complete_json_does_not_download(tmp_path, monkeypatch):
    args = _args(tmp_path)
    json_path = Path(args.data_dir) / "neurips2024.bib.json"
    _write_json(json_path, n=1500)

    def boom(*_a, **_k):
        raise AssertionError("download_conf_year should not be called")

    monkeypatch.setattr(dd, "download_conf_year", boom)
    status = dd.process_conf_year(None, "neurips", 2024, args)
    assert status == "skipped"
    assert len(json.loads(json_path.read_text(encoding="utf-8"))) == 1500


def test_reject_overwrite_with_thinner_download(tmp_path, monkeypatch):
    args = _args(tmp_path, force=True)
    json_path = Path(args.data_dir) / "wacv2024.bib.json"
    original = _write_json(json_path, n=100)

    monkeypatch.setattr(dd, "download_conf_year", lambda *_a, **_k: _two_paper_bib("Thin"))
    status = dd.process_conf_year(object(), "wacv", 2024, args)

    assert status == "rejected_thin"
    kept = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(kept) == 100
    assert kept == original


def test_colm_openreview_fixture_two_bib_entries():
    payload = json.loads(_COLM_FIXTURE.read_text(encoding="utf-8"))
    notes = payload["notes"]
    assert len(notes) == 2

    bib = dd.colm_notes_to_bib(notes, 2024)
    assert bib.count("@inproceedings") == 2
    assert "First COLM Paper" in bib
    assert "Second COLM Paper" in bib
    assert "Ada Lovelace and Alan Turing" in bib
    assert "Grace Hopper" in bib
    assert "booktitle={The Conference on Language Modeling}" in bib
    assert "year={2024}" in bib
    assert "https://openreview.net/forum?id=NoteAAA" in bib
    assert "https://openreview.net/forum?id=NoteBBB" in bib

    session = mock.Mock()
    session.get.return_value = FakeResponse(json_data=payload)
    fetched = dd.fetch_colm_openreview(2024, session=session)
    assert fetched.count("@inproceedings") == 2
    session.get.assert_called()
    _, kwargs = session.get.call_args
    assert kwargs["params"]["content.venueid"] == "colmweb.org/COLM/2024/Conference"


def test_colm_openreview_error_prints_warning_and_skips(capsys):
    session = mock.Mock()
    session.get.side_effect = RuntimeError("boom")
    bib = dd.fetch_colm_openreview(2024, session=session)
    assert bib == ""
    err = capsys.readouterr().out
    assert "Warning" in err
    assert "COLM 2024" in err


def test_colm_falls_back_to_openreview_when_dblp_empty(tmp_path, monkeypatch):
    args = _args(tmp_path)
    monkeypatch.setattr(dd, "download_conf_year", lambda *_a, **_k: "")
    monkeypatch.setattr(
        dd,
        "fetch_colm_openreview",
        lambda year, session=None: (
            "@inproceedings{colm2024_x,\n"
            "  title={Colm Fallback Paper},\n"
            "  author={A Author},\n"
            "  booktitle={The Conference on Language Modeling},\n"
            "  year={2024},\n"
            "  url={https://openreview.net/forum?id=x}\n"
            "}\n"
        ),
    )
    status = dd.process_conf_year(object(), "colm", 2024, args)
    assert status == "downloaded"
    json_path = Path(args.data_dir) / "colm2024.bib.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert any("Colm Fallback Paper" in "".join(v) for v in data.values())


def test_prev_year_thin_prints_error_but_writes_when_no_existing(
    tmp_path, monkeypatch, capsys
):
    args = _args(tmp_path, force=True)
    prev_path = Path(args.data_dir) / "icml2023.bib.json"
    _write_json(prev_path, n=100)
    monkeypatch.setattr(dd, "download_conf_year", lambda *_a, **_k: _two_paper_bib("ICML"))
    status = dd.process_conf_year(object(), "icml", 2024, args)
    assert status == "downloaded"
    out = capsys.readouterr().out
    assert "ERROR" in out
    json_path = Path(args.data_dir) / "icml2024.bib.json"
    assert json_path.is_file()
    assert len(json.loads(json_path.read_text(encoding="utf-8"))) == 2

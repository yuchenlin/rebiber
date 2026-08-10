"""Unit tests for camera-ready helpers (pure; no I/O)."""

from rebiber.camera import apply_keep_fields, protect_title_caps


def test_protect_acronyms_not_title_case_words():
    assert protect_title_caps("Deep Learning") == "Deep Learning"
    assert protect_title_caps("BERT") == "{BERT}"
    assert protect_title_caps("BERT: Pre-training of NLP") == (
        "{BERT}: Pre-training of {NLP}"
    )
    assert protect_title_caps("A BERT Model") == "A {BERT} Model"


def test_protect_does_not_double_brace_whole_title():
    # The usual anti-pattern is {{Whole Title Here}}.
    result = protect_title_caps("BERT for NLP")
    assert result == "{BERT} for {NLP}"
    assert result != "{BERT for NLP}"
    assert result != "{{BERT} for {NLP}}"

    already_whole = "{Deep Learning with BERT}"
    assert protect_title_caps(already_whole) == already_whole

    already_token = "{BERT}: Pre-training"
    assert protect_title_caps(already_token) == already_token
    assert protect_title_caps("{BERT}") == "{BERT}"


def test_protect_mixed_case_and_digits():
    assert protect_title_caps("ResNet and PyTorch") == "{ResNet} and {PyTorch}"
    assert protect_title_caps("GPT-2 and 3D vision") == "{GPT-2} and {3D} vision"
    assert protect_title_caps("C++ parsers") == "{C++} parsers"


def test_protect_empty_and_none():
    assert protect_title_caps("") == ""
    assert protect_title_caps(None) == ""


def test_apply_keep_always_keeps_id_and_entrytype():
    entry = {
        "ID": "x",
        "ENTRYTYPE": "article",
        "title": "Hello",
        "author": "Ada",
        "note": "drop me",
        "url": "http://x",
    }
    kept = apply_keep_fields(entry, ["title", "author"])
    assert kept == {
        "ID": "x",
        "ENTRYTYPE": "article",
        "title": "Hello",
        "author": "Ada",
    }
    # Pure: original is unchanged.
    assert "note" in entry
    assert "url" in entry


def test_apply_keep_empty_is_noop():
    entry = {"ID": "x", "ENTRYTYPE": "article", "note": "keep"}
    assert apply_keep_fields(entry, []) == entry
    assert apply_keep_fields(entry, None) == entry
    assert apply_keep_fields(entry, "") == entry


def test_apply_keep_case_insensitive_and_comma_string():
    entry = {
        "ID": "x",
        "ENTRYTYPE": "article",
        "title": "T",
        "doi": "10.1",
        "note": "no",
    }
    kept = apply_keep_fields(entry, ["Title", "DOI"])
    assert set(kept) == {"ID", "ENTRYTYPE", "title", "doi"}
    kept_str = apply_keep_fields(entry, "author,title,booktitle,journal,year,volume,number,pages,doi")
    assert "title" in kept_str
    assert "doi" in kept_str
    assert "note" not in kept_str
    assert kept_str["ID"] == "x"


def test_apply_keep_none_entry():
    assert apply_keep_fields(None, ["title"]) == {}
    assert apply_keep_fields({}, ["title"]) == {}

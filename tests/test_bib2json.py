import importlib.util
import os
import sys
import tempfile
from pathlib import Path

try:
    from rebiber.bib2json import build_json, load_bib_file, normalize_title
except (ImportError, SyntaxError):
    # Load the module file directly so these tests do not depend on
    # rebiber/__init__.py importing normalize.py.
    _path = Path(__file__).resolve().parents[1] / "rebiber" / "bib2json.py"
    _spec = importlib.util.spec_from_file_location("rebiber.bib2json", _path)
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules.setdefault("rebiber.bib2json", _mod)
    _spec.loader.exec_module(_mod)
    build_json = _mod.build_json
    load_bib_file = _mod.load_bib_file
    normalize_title = _mod.normalize_title


def _write_bib(content):
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".bib", delete=False, encoding="utf8"
    )
    try:
        handle.write(content)
        handle.flush()
        return handle.name
    finally:
        handle.close()


def test_normalize_title_strips_punctuation_lowercases_letters_only():
    assert normalize_title("Hello, World!") == "helloworld"
    assert normalize_title("Birds have four legs?!") == "birdshavefourlegs"
    assert normalize_title("Foo-Bar_Baz 123") == "foobarbaz"
    assert normalize_title("  {ACL} 2020  ") == "acl"
    assert normalize_title("Deep Learning") == "deeplearning"
    # combining marks are dropped; ASCII letters remain
    assert normalize_title("naive") == "naive"
    assert normalize_title("naive\u0301") == "naive"
    # default keep_digits=False drops digits
    assert normalize_title("A 16x16 Network") == "axnetwork"
    assert normalize_title("A 16x16 Network", keep_digits=False) == "axnetwork"


def test_normalize_title_keep_digits_distinguishes_16x16_and_32x32():
    t16 = "A 16x16 Network"
    t32 = "A 32x32 Network"
    assert normalize_title(t16, keep_digits=False) == "axnetwork"
    assert normalize_title(t32, keep_digits=False) == "axnetwork"
    assert normalize_title(t16, keep_digits=True) == "a16x16network"
    assert normalize_title(t32, keep_digits=True) == "a32x32network"
    assert normalize_title(t16, keep_digits=True) != normalize_title(
        t32, keep_digits=True
    )


def test_load_bib_file_parses_two_entries_ignores_comments():
    path = _write_bib(
        """
% file-level comment should not drop the next entry
@article{one,
  title={First Title},
  author={Alice},
  year={2020}
}
# hash comment
@inproceedings{two,
  title={Second Title},
  author={Bob},
  year={2021}
}
"""
    )
    try:
        entries = load_bib_file(path)
        assert len(entries) == 2
        first = "".join(entries[0])
        second = "".join(entries[1])
        assert "First Title" in first
        assert "Second Title" in second
        assert "@article" in first.lower()
        assert "@inproceedings" in second.lower()
    finally:
        os.unlink(path)


def test_load_bib_file_comment_inside_entry_does_not_drop_it():
    path = _write_bib(
        """
@article{one,
  title={Kept Title},
  % this used to reset the buffer and drop the entry
  author={Alice},
  year={2020}
}
@article{two,
  title={Next Title},
  year={2021}
}
"""
    )
    try:
        entries = load_bib_file(path)
        assert len(entries) == 2
        assert "Kept Title" in "".join(entries[0])
        assert "Next Title" in "".join(entries[1])
    finally:
        os.unlink(path)


def test_load_bib_file_skips_comment_and_preamble():
    path = _write_bib(
        """
@preamble{"\\\\newcommand{\\\\blah}{}" }
@comment{ignore this whole block}
@article{keepme,
  title={Real Paper},
  year={2022}
}
"""
    )
    try:
        entries = load_bib_file(path)
        assert len(entries) == 1
        joined = "".join(entries[0]).lower()
        assert "real paper" in joined
        assert "@preamble" not in joined
        assert "@comment" not in joined
    finally:
        os.unlink(path)


def test_brace_nested_fields_stay_in_one_entry():
    path = _write_bib(
        """
@article{nested,
  title={Nested {Braces} Title},
  author={Someone},
  note={outer {inner {deep}} still one},
  year={2020}
}
"""
    )
    try:
        entries = load_bib_file(path)
        assert len(entries) == 1
        joined = "".join(entries[0])
        assert "Nested {Braces} Title" in joined
        assert "inner {deep}" in joined
        assert joined.count("{") == joined.count("}")
    finally:
        os.unlink(path)


def test_build_json_keys_by_normalize_title():
    path = _write_bib(
        """
@inproceedings{lin2020birds,
  title={Birds have four legs?! NumerSense},
  author={Lin},
  year={2020}
}
@article{other,
  title={Hello, World!},
  year={2021}
}
"""
    )
    try:
        entries = load_bib_file(path)
        db = build_json(entries)
        key_birds = normalize_title("Birds have four legs?! NumerSense")
        key_hello = normalize_title("Hello, World!")
        assert key_birds == "birdshavefourlegsnumersense"
        assert key_hello == "helloworld"
        assert key_birds in db
        assert key_hello in db
        assert db[key_birds] == entries[0]
        assert db[key_hello] == entries[1]
    finally:
        os.unlink(path)


def test_build_json_uses_keep_digits_keys():
    path = _write_bib(
        """
@article{a,
  title={A 16x16 Network},
  year={2020}
}
@article{b,
  title={A 32x32 Network},
  year={2021}
}
"""
    )
    try:
        entries = load_bib_file(path)
        db = build_json(entries)
        key16 = normalize_title("A 16x16 Network", keep_digits=True)
        key32 = normalize_title("A 32x32 Network", keep_digits=True)
        key_old = normalize_title("A 16x16 Network", keep_digits=False)
        assert key16 == "a16x16network"
        assert key32 == "a32x32network"
        assert key_old == "axnetwork"
        assert key16 in db
        assert key32 in db
        assert key_old not in db
        assert db[key16] == entries[0]
        assert db[key32] == entries[1]
    finally:
        os.unlink(path)


def test_build_json_keeps_title_containing_month():
    path = _write_bib(
        """
@article{m,
  title={A Month of Sundays},
  author={Alice},
  month={jan},
  year={2020}
}
"""
    )
    try:
        entries = load_bib_file(path)
        db = build_json(entries)
        key = normalize_title("A Month of Sundays", keep_digits=True)
        assert key == "amonthofsundays"
        assert key in db
        assert "A Month of Sundays" in "".join(db[key])
    finally:
        os.unlink(path)


def test_load_bib_file_keeps_unclosed_entry():
    path = _write_bib(
        """@article{broken,
  title={Unclosed Title},
  author={Alice}
"""
    )
    try:
        entries = load_bib_file(path)
        assert len(entries) == 1
        joined = "".join(entries[0])
        assert "Unclosed Title" in joined
        assert "broken" in joined
    finally:
        os.unlink(path)

"""
Rebiber: A tool for normalizing bibtex with official info.
"""

from rebiber.bib2json import load_bib_file
from rebiber.normalize import construct_bib_db, normalize_bib
from ._version import __version__

__all__ = [
    "__version__",
    "load_bib_file",
    "construct_bib_db",
    "normalize_bib"
]
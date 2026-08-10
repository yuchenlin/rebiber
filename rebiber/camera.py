"""Camera-ready BibTeX helpers (pure functions; no I/O).

These are opt-in post-processing steps for ``normalize_bib``. They do not
change title matching, live DBLP lookup, or bib2json.
"""

import re


# Token characters that may sit inside an acronym (GPT-2, C++, NLP/CL).
_TOKEN_INNER = set("-+/")
# Hyphen/slash at the end of a span are separators; '+' is part of C++.
_TOKEN_TRAIL_STRIP = set("-/")

# Leading backslash + letters is a LaTeX command; leave it untouched.
_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z]+")


def _as_keep_names(keep_names):
    """Normalize a keep-list from None / str / iterable to a list of names."""
    if not keep_names:
        return []
    if isinstance(keep_names, str):
        return [part.strip() for part in keep_names.split(",") if part.strip()]
    return [str(name).strip() for name in keep_names if str(name).strip()]


def _is_protectable_token(token):
    """True for uppercase tokens / acronyms that BibTeX styles would smash.

    Regular Title-Case words (``Deep``, ``Learning``) are left alone. Single
    letters (``A``, ``I``) are not acronyms.
    """
    if not token:
        return False
    uppers = sum(1 for char in token if char.isupper())
    if uppers >= 2:
        return True
    # CamelCase / internal capital: ResNet, PyTorch, iPhone.
    if len(token) >= 2 and any(char.isupper() for char in token[1:]):
        return True
    # One capital plus a digit or plus: 3D, C++.
    if uppers >= 1 and any(char.isdigit() or char == "+" for char in token):
        return True
    return False


def protect_title_caps(title):
    """Wrap uppercase tokens / acronyms in braces.

    Does **not** wrap the entire title in one pair of braces (the usual
    ``{{Whole Title}}`` anti-pattern). Tokens already inside ``{...}`` are
    left unchanged so ``{BERT}`` is not turned into ``{{BERT}}``.
    """
    if title is None:
        return ""
    title = str(title)
    if not title:
        return title

    out = []
    i = 0
    n = len(title)
    depth = 0
    while i < n:
        char = title[i]
        if char == "{":
            depth += 1
            out.append(char)
            i += 1
            continue
        if char == "}":
            if depth:
                depth -= 1
            out.append(char)
            i += 1
            continue
        if depth > 0:
            out.append(char)
            i += 1
            continue
        if char == "\\":
            match = _LATEX_CMD_RE.match(title, i)
            if match:
                out.append(match.group(0))
                i = match.end()
                continue
        if char.isalnum():
            j = i + 1
            while j < n and (title[j].isalnum() or title[j] in _TOKEN_INNER):
                j += 1
            token_end = j
            while token_end > i and title[token_end - 1] in _TOKEN_TRAIL_STRIP:
                token_end -= 1
            token = title[i:token_end]
            if _is_protectable_token(token):
                out.append("{" + token + "}")
            else:
                out.append(token)
            out.append(title[token_end:j])
            i = j
            continue
        out.append(char)
        i += 1
    return "".join(out)


def apply_keep_fields(entry_dict, keep_names):
    """Return a new entry dict restricted to an allowlist of fields.

    ``ID`` and ``ENTRYTYPE`` are always kept. An empty ``keep_names`` is a
    no-op (all fields are copied) so the CLI default matches current
    behavior. Field-name matching is case-insensitive.
    """
    if not entry_dict:
        return {} if entry_dict is None else dict(entry_dict)
    entry = dict(entry_dict)
    names = _as_keep_names(keep_names)
    if not names:
        return entry
    allow = {name.lower() for name in names}
    always = ("ID", "ENTRYTYPE")
    kept = {}
    for key, value in entry.items():
        if key in always or str(key).lower() in allow:
            kept[key] = value
    return kept

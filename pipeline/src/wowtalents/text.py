"""The one slug rule and the one text normaliser (docs/DATA-SCHEMA.md sections 2-3).

Before this module there were three slug implementations (``ranks.slug``,
``ui.slug`` and a copy inlined in ``reader.py``); the naive two neither collapsed
punctuation runs nor stripped accents, so ``"Nature's Grace"`` became
``nature-s-grace`` in stage-4 crop names and ``natures-grace`` in the exported id.
``ranks.slug`` and ``ui.slug`` now re-export the function defined here.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["slug", "clean_text"]

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"[ \t\r\n]+")


def slug(name: str) -> str:
    """DATA-SCHEMA.md section 3: NFKD, drop combining marks, drop apostrophes, collapse the rest to ``-``."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("'", "").replace("’", "")
    return _NON_ALNUM.sub("-", s).strip("-")


def clean_text(s: str) -> str:
    """Section 2 normalisation: nbsp/curly quotes to ASCII, collapse whitespace runs, trim."""
    s = s.replace(" ", " ").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return _WS.sub(" ", s).strip()

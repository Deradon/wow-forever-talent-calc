"""One slug rule (wowtalents.text), shared by ranks, ui and reader."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wowtalents import ranks as R  # noqa: E402
from wowtalents import reader as RD  # noqa: E402
from wowtalents import text as T  # noqa: E402
from wowtalents import ui  # noqa: E402


@pytest.mark.parametrize("name,expected", [
    ("Nature's Grace", "natures-grace"),            # apostrophe dropped, not turned into a separator
    ("Improved Power Word: Shield", "improved-power-word-shield"),   # punctuation run collapses to one dash
    ("Anti-Magic  Shell", "anti-magic-shell"),      # double space collapses
    ("Élan Vital", "elan-vital"),                   # NFKD + combining marks stripped
    ("  Frost Warding  ", "frost-warding"),         # leading/trailing separators trimmed
    ("Beast Mastery", "beast-mastery"),
    ("5 Rage", "5-rage"),
    ("", ""),
])
def test_slug_rule(name, expected):
    assert T.slug(name) == expected


def test_every_module_uses_the_same_slug():
    """The bug this replaces: stage-4 crop names and exported ids disagreed on the same talent."""
    assert R.slug is T.slug
    assert ui.slug is T.slug
    tricky = ["Nature's Grace", "Improved Power Word: Shield", "Anti-Magic  Shell", "Élan Vital"]
    assert {ui.slug(n) for n in tricky} == {R.slug(n) for n in tricky} == {T.slug(n) for n in tricky}


def test_reader_record_ids_use_the_shared_slug():
    assert RD._text.slug("Nature's Grace") == "natures-grace"


@pytest.mark.parametrize("raw,expected", [
    ("a b", "a b"),
    ("Nature’s Grace", "Nature's Grace"),
    ("“quoted”", '"quoted"'),
    ("  two   spaces\nand a newline  ", "two spaces and a newline"),
])
def test_clean_text_normalisation(raw, expected):
    assert T.clean_text(raw) == expected
    assert R.clean_text(raw) == expected

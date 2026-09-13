"""Pure helpers behind ``stages/05_read.py run --add`` (no VLM, no files)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("stage5", ROOT / "stages" / "05_read.py")
st5 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(st5)


def _rec(tree: str, row0: int, col0: int, name: str, conf: float = 1.0) -> dict:
    slug = tree.lower()
    return {"id": f"mage/{slug}/r{row0}c{col0}", "tree": tree, "page": "Primary", "row": row0, "col": col0,
            "name": name, "cut_off": False, "source": {"confidence": conf}}


def test_record_key_is_the_merge_hovers_key():
    idx = {"Arcane": 1, "Fire": 2, "Frost": 3}
    assert st5.record_key(_rec("Fire", 3, 2, "Hot Streak"), idx) == ("Primary", 2, 4, 3)
    assert st5.record_key(_rec("Shadow", 0, 0, "x"), idx) is None       # tree not in this class's map
    rec = _rec("Frost", 0, 0, "Frost Warding")
    rec["page"] = None
    assert st5.record_key(rec, idx) == ("Primary", 3, 1, 1)


def test_additive_merge_appends_without_touching_existing_records():
    existing = {
        "class": "mage", "generated_at": "old", "reader": "qwen",
        "segments": [{"segment_id": "08-mage-14970", "hovers": 13}],
        "trees": {"1": "Arcane", "2": "Fire", "3": "Frost"},
        "missing_cells": [{"cell": "fire-r1c3"}],
        "stats": {"read": 1},
        "candidates": [_rec("Fire", 3, 3, "Master of Elements", 0.3)],
        "recovery": {"added": ["mage/fire/r3c3"]},
    }
    new = [_rec("Fire", 0, 2, "Flame Throwing"), _rec("Fire", 3, 2, "Hot Streak")]
    segs = [{"segment_id": "08-mage-14970", "hovers": 99}, {"segment_id": "m07-mage-14825", "hovers": 4}]
    stats = {"read": 3, "reader": "qwen+v3"}
    doc = st5.additive_merge(existing, new, segs, {"1": "Arcane", "2": "Fire", "3": "Frost", "4": "Bogus"},
                             [], stats, at="2026-09-13T12:00:00Z")
    assert [r["id"] for r in doc["candidates"]] == ["mage/fire/r3c3", "mage/fire/r0c2", "mage/fire/r3c2"]
    assert doc["candidates"][0] is existing["candidates"][0]           # existing records untouched
    assert doc["segments"] == [{"segment_id": "08-mage-14970", "hovers": 13}, {"segment_id": "m07-mage-14825", "hovers": 4}]
    assert doc["trees"] == {"1": "Arcane", "2": "Fire", "3": "Frost", "4": "Bogus"}
    assert doc["missing_cells"] == [] and doc["stats"] == stats and doc["generated_at"] == "2026-09-13T12:00:00Z"
    assert doc["recovery"] == existing["recovery"]                     # earlier provenance blocks survive
    assert doc["additions"] == [{"at": "2026-09-13T12:00:00Z", "source": "05_read.py run --add", "reader": "qwen+v3",
                                 "segments": ["08-mage-14970", "m07-mage-14825"],
                                 "added": ["mage/fire/r0c2", "mage/fire/r3c2"]}]
    assert existing["generated_at"] == "old" and "additions" not in existing   # input not mutated


def test_additive_merge_accumulates_additions():
    base = {"candidates": [], "segments": [], "trees": {}, "additions": [{"at": "t0", "added": ["a"]}]}
    doc = st5.additive_merge(base, [_rec("Fire", 1, 1, "Ignite")], [], {}, [], {}, at="t1")
    assert [a["at"] for a in doc["additions"]] == ["t0", "t1"]
    assert len(base["additions"]) == 1

"""Pure parts of stage 5 (wowtalents.reader): reading clean-up, confidence, record assembly, merging.

Run: cd pipeline && uv run pytest -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wowtalents import reader as RD  # noqa: E402

READING = {
    "name": "Toughness", "rank_current": 0, "rank_max": 5, "kind": "Passive", "extra_lines": [],
    "requires": [], "description": "Increases your armor value from items by 2%.", "footer": "Click to learn",
    "cut_off": False,
}

HOVER = {
    "run": 3, "t": 13660.25, "sq": 13660, "offset": 15, "frames": 11, "bbox": [534, 121, 210, 117],
    "cell": [2, 1, 2], "sharpness": 3364.5, "hash": "7399838514410141", "cut_off": False,
    "id": "protection-r1c2", "tree": 2, "tree_name": "protection", "row": 1, "col": 2, "page": "Primary",
    "files": {"tooltip": "01-paladin-13640/protection-r1c2.png", "icon": "01-paladin-13640/protection-r1c2-icon.png"},
}


def test_confidence_levels():
    a = dict(READING)
    assert RD.confidence(a, dict(READING)) == 1.0
    b = dict(READING, description="Increases your armor value from items by 2%.  ")
    assert RD.confidence(RD.clean_reading(a), RD.clean_reading(b)) == 1.0, "whitespace must not count"
    c = dict(READING, description="Increases your armor value from items by 3%.")
    assert RD.confidence(a, c) == 0.7
    d = dict(READING, rank_max=3)
    assert RD.confidence(a, d) == 0.3
    e = dict(READING, name="Toughnes")
    assert RD.confidence(a, e) == 0.3
    assert RD.disagreements(a, c) == ["description"]


def test_clean_reading_refiles_misplaced_lines():
    messy = {
        "name": " Improved Holy Strike ", "rank_current": 0, "rank_max": 2, "kind": None,
        "extra_lines": ["Click to learn", "Requires Shields", "30 yd range"],
        "requires": ["Click to learn"],
        "description": "Passive Requires 5 points in Holy Talents. Reduces the cooldown by 1 sec. Click to learn",
        "footer": None, "cut_off": True,
    }
    r = RD.clean_reading(messy)
    assert r["name"] == "Improved Holy Strike"
    assert r["kind"] == "Passive"
    assert r["extra_lines"] == ["30 yd range"]
    assert r["requires"] == ["Requires Shields", "Requires 5 points in Holy Talents."]
    assert r["description"] == "Reduces the cooldown by 1 sec."
    assert r["footer"] == "Click to learn"
    assert r["cut_off"] is True


def test_clean_reading_keeps_clean_input():
    r = RD.clean_reading(READING)
    assert r == dict(READING)


def test_choose_primary_prefers_usable_pass():
    good = dict(READING)
    empty = dict(READING, name="", rank_max=None)
    assert RD.choose_primary(good, dict(READING, description="x"))[0] is good
    p, s = RD.choose_primary(empty, good)
    assert p is good and s is empty


def test_assemble_record_shape():
    other = dict(READING, description="Increases your armor value from items by 3%.")
    rec = RD.assemble_record("paladin", HOVER, "01-paladin-13640", "Protection", "Primary", READING, other,
                             reader="qwen-test", tree_source={"t": 13640, "frame_index": 818400})
    assert rec["id"] == "paladin/protection/r0c1"
    assert (rec["row"], rec["col"]) == (0, 1), "export.py expects 0-based rows and columns"
    assert rec["tree"] == "Protection" and rec["page"] == "Primary"
    assert rec["rank"] == {"current": 0, "max": 5}
    assert rec["description_rank1"] == READING["description"]
    assert rec["kind"] == "Passive" and rec["footer"] == "Click to learn"
    assert rec["requires"] == [] and rec["extra_lines"] == []
    assert rec["cut_off"] is False
    src = rec["source"]
    assert src["crop_path"] == "work/hovers/01-paladin-13640/protection-r1c2.png"
    assert src["icon_crop_path"].endswith("protection-r1c2-icon.png")
    assert src["t"] == 13660.25 and src["timestamp"] == "03:47:40.250"
    assert src["frame_index"] == 13660 * 60 + 15
    assert src["confidence"] == 0.7 and src["agreement"]["differs_in"] == ["description"]
    assert src["reviewed"] is False and src["reader"] == "qwen-test"
    assert [r["reader"] for r in src["readings"]] == ["qwen-test/3x", "qwen-test/2x"]
    assert src["readings"][1]["description"] == other["description"]
    assert src["cell"] == [2, 1, 2]
    assert rec["tree_source"]["frame_index"] == 818400


def test_assemble_record_hover_cut_off_wins():
    rec = RD.assemble_record("paladin", dict(HOVER, cut_off=True), "s", "Holy", "Primary", READING, READING, reader="r")
    assert rec["cut_off"] is True and rec["source"]["confidence"] == 1.0


def test_merge_hovers_prefers_uncut_then_sharpest():
    h1 = dict(HOVER, sharpness=100.0, t=1.0)
    h2 = dict(HOVER, sharpness=500.0, t=2.0, cut_off=True)
    h3 = dict(HOVER, sharpness=300.0, t=3.0)
    other = dict(HOVER, row=3, col=1, id="protection-r3c1", sharpness=10.0)
    best, everything = RD.merge_hovers([("a", {"page": "Primary", "hovers": [h1, h2]}),
                                        ("b", {"page": "Primary", "hovers": [h3, other]})])
    key = ("Primary", 2, 1, 2)
    assert best[key]["t"] == 3.0 and best[key]["_segment"] == "b"
    assert len(everything[key]) == 3
    assert best[("Primary", 2, 3, 1)]["_segment"] == "b"


def test_upscale_and_png_roundtrip():
    img = np.zeros((10, 20, 3), np.uint8)
    up = RD.upscale(img, 2.0)
    assert up.shape == (20, 40, 3)
    assert RD.upscale(img, 1.0) is img
    assert RD.png_bytes(img)[:8] == b"\x89PNG\r\n\x1a\n"
    assert RD.data_url(b"abc").startswith("data:image/png;base64,")


def test_reader_cache_path_is_content_addressed(tmp_path):
    r = RD.Reader(cache_dir=tmp_path)
    a = r._cache_path(b"png", "s", "u", {"x": 1})
    assert a == r._cache_path(b"png", "s", "u", {"x": 1})
    assert a != r._cache_path(b"png2", "s", "u", {"x": 1})
    assert a != r._cache_path(b"png", "s2", "u", {"x": 1})
    assert RD.Reader()._cache_path(b"png", "s", "u", {}) is None


def test_consensus_cells_ignores_small_grids_and_strays():
    def grid(keys):
        return [{"tree": t, "row": r, "col": c} for t, r, c in keys]
    base = {(1, 1, 1), (1, 1, 2), (2, 1, 1)} | {(3, r, c) for r in range(1, 8) for c in range(1, 4)} | \
           {(1, r, c) for r in range(2, 8) for c in range(1, 4)}
    assert len(base) >= 40
    a = grid(base)
    b = grid(base | {(2, 4, 4)})          # one stray cell
    c = grid({(1, 1, 1), (2, 1, 2)})      # spellbook: too small to vote
    consensus, disputed = RD.consensus_cells([a, b, c])
    assert consensus == base
    assert disputed == {(2, 4, 4)}
    only_small, _ = RD.consensus_cells([c])
    assert only_small == {(1, 1, 1), (2, 1, 2)}

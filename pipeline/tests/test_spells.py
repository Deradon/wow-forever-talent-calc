"""Pure helpers of ``wowtalents.spells``, ``stages/11_spellbook.py`` and ``validate_spells.py``.

No video, no ffmpeg, no llama-server: the pixel functions get synthetic frames,
everything else gets the strings the reader really produced on 2026-09-13.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from wowtalents import spells as SP  # noqa: E402

import validate_spells as VS  # noqa: E402

_spec = importlib.util.spec_from_file_location("stage11", ROOT / "stages" / "11_spellbook.py")
st11 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(st11)


# --------------------------------------------------------------------------- geometry

def test_window_boxes_translate_with_the_window():
    a = SP.Window(232, 32, 0.98)
    b = SP.Window(1013, 32, 0.9)
    dx = b.x - a.x
    for fn in (SP.window_box, SP.list_box, SP.page_title_box, SP.page_nav_box, SP.chrome_box):
        xa0, ya0, xa1, ya1 = fn(a)
        xb0, yb0, xb1, yb1 = fn(b)
        assert (xb0 - xa0, xb1 - xa1) == (dx, dx)
        assert (ya0, ya1) == (yb0, yb1)


def test_window_box_has_the_measured_size():
    x0, y0, x1, y1 = SP.window_box(SP.Window(232, 32, 1.0))
    assert (x1 - x0, y1 - y0) == (SP.WINDOW_W, SP.WINDOW_H)


def test_cells_are_a_regular_grid():
    win = SP.Window(0, 0, 1.0)
    tops = [SP.icon_box(win, 0, r)[1] for r in range(SP.ROWS)]
    assert [b - a for a, b in zip(tops, tops[1:])] == [63] * (SP.ROWS - 1)
    lefts = [SP.icon_box(win, c, 0)[0] for c in range(SP.COLUMNS)]
    assert lefts == list(SP.COL_X)
    # a row box starts left of its icon and is wide enough for the name beside it
    rx0, ry0, rx1, ry1 = SP.row_box(win, 1, 2)
    ix0, iy0, ix1, iy1 = SP.icon_box(win, 1, 2)
    assert rx0 < ix0 and rx1 > ix1 + SP.TEXT_DX and ry0 < iy0 and ry1 > iy1


def test_column_box_covers_every_row_of_that_column():
    win = SP.Window(100, 50, 1.0)
    cx0, cy0, cx1, cy1 = SP.column_box(win, 2)
    for r in range(SP.ROWS):
        ix0, iy0, ix1, iy1 = SP.icon_box(win, 2, r)
        assert cx0 <= ix0 and cx1 >= ix1 and cy0 <= iy0 and cy1 >= iy1


def test_work_roi_reaches_past_the_window_and_stays_in_frame():
    x0, y0, x1, y1 = SP.work_roi(SP.Window(232, 32, 1.0))
    assert x1 - (232 + SP.WINDOW_W) == SP.TOOLTIP_MARGIN
    x0, y0, x1, y1 = SP.work_roi(SP.Window(1600, 32, 1.0))
    assert x1 <= SP.FRAME_W and y1 <= SP.FRAME_H


def test_crop_clips_at_the_frame_edge():
    frame = np.zeros((100, 100, 3), np.uint8)
    assert SP.crop(frame, (-10, -10, 20, 20)).shape[:2] == (20, 20)
    assert SP.crop(frame, (90, 90, 200, 200)).shape[:2] == (10, 10)


# --------------------------------------------------------------------------- window locator

def _frame_with_template(tpl: np.ndarray, at: tuple[int, int]) -> np.ndarray:
    rng = np.random.default_rng(7)
    frame = rng.integers(0, 90, (300, 1200), dtype=np.uint8)
    x, y = at
    frame[y:y + tpl.shape[0], x:x + tpl.shape[1]] = tpl
    return frame


def test_locate_window_finds_the_title_bar_and_maps_it_to_the_origin():
    rng = np.random.default_rng(3)
    tpl = rng.integers(0, 255, (26, 400), dtype=np.uint8)
    frame = _frame_with_template(tpl, (500, 102))
    win = SP.locate_window(frame, tpl)
    assert win is not None
    # the template is the title strip, which starts TITLE_STRIP[1] px below the window top
    assert (win.x, win.y) == (500, 102 - SP.TITLE_STRIP[1])
    assert win.score > 0.99


def test_locate_window_returns_none_without_the_title_bar():
    rng = np.random.default_rng(11)
    tpl = rng.integers(0, 255, (26, 400), dtype=np.uint8)
    other = np.full((300, 1200), 60, np.uint8)
    assert SP.locate_window(other, tpl) is None


def test_locate_window_handles_a_frame_smaller_than_the_template():
    tpl = np.zeros((26, 400), np.uint8)
    assert SP.locate_window(np.zeros((10, 10), np.uint8), tpl) is None


def test_window_near_absorbs_jitter():
    assert SP.Window(234, 33, 1.0).near(SP.Window(232, 32, 1.0))
    assert not SP.Window(300, 32, 1.0).near(SP.Window(232, 32, 1.0))
    assert not SP.Window(232, 32, 1.0).near(None)


# --------------------------------------------------------------------------- change metrics

def test_change_fraction_counts_only_real_differences():
    a = np.zeros((10, 10), np.uint8)
    b = a.copy()
    assert SP.change_fraction(a, b) == 0.0
    b[:, :5] = 200
    assert SP.change_fraction(a, b) == pytest.approx(0.5)
    b[:, 5:] = 10           # below CHANGE_LEVEL, so it does not count
    assert SP.change_fraction(a, b) == pytest.approx(0.5)


def test_change_fraction_of_mismatched_shapes_is_total():
    assert SP.change_fraction(np.zeros((4, 4), np.uint8), np.zeros((5, 5), np.uint8)) == 1.0


def _page(fill: int = 200) -> np.ndarray:
    return np.full((SP.WINDOW_H, SP.WINDOW_W), fill, np.uint8)


def test_list_change_ignores_a_tooltip_over_a_few_cells():
    win = SP.Window(0, 0, 1.0)
    a = _page()
    b = a.copy()
    # a tooltip blots out five cells of one column; the other sixteen are untouched
    for row in range(5):
        x0, y0, x1, y1 = SP.row_box(win, 2, row)
        b[y0:y1, x0:x1] = 20
    assert SP.list_change(a, win, b, win) == 0.0
    assert max(SP.row_change_fractions(a, win, b, win)) == pytest.approx(1.0)


def test_list_change_sees_a_new_page():
    win = SP.Window(0, 0, 1.0)
    a = _page()
    b = a.copy()
    for col in range(SP.COLUMNS):
        for row in range(SP.ROWS):
            x0, y0, x1, y1 = SP.row_box(win, col, row)
            b[y0:y1, x0:x1] = 20
    assert SP.list_change(a, win, b, win) > SP.STATE_CHANGE


def test_page_changed_is_true_for_each_of_its_three_signals():
    win = SP.Window(0, 0, 1.0)
    base = _page()
    for rel in (SP.TITLE_TEXT, SP.SEARCH_TEXT):
        other = base.copy()
        x0, y0, x1, y1 = SP._box(win, rel)
        other[y0:y1, x0:x1] = 20
        assert SP.page_changed(base, win, other, win)
    assert not SP.page_changed(base, win, base.copy(), win)


def test_composite_drops_a_dark_box_that_covers_most_frames():
    clean = np.full((20, 20, 3), 200, np.uint8)
    covered = clean.copy()
    covered[5:15, 5:15] = 30
    frames = [covered] * 7 + [clean] * 3        # the tooltip is up 70 % of the time
    out = SP.composite(frames, 0.85)
    assert out[10, 10].tolist() == [200, 200, 200]
    assert np.median(np.stack(frames), axis=0)[10, 10, 0] == 30   # a median would have kept it


# --------------------------------------------------------------------------- cells and tooltips

def test_filled_cells_finds_the_icons_and_nothing_else():
    win = SP.Window(0, 0, 1.0)
    page = np.full((SP.WINDOW_H, SP.WINDOW_W, 3), 200, np.uint8)
    want = [(0, 0), (0, 1), (1, 0), (2, 4)]
    rng = np.random.default_rng(5)
    for col, row in want:
        x0, y0, x1, y1 = SP.icon_box(win, col, row)
        page[y0:y1, x0:x1] = rng.integers(0, 255, (y1 - y0, x1 - x0, 3), dtype=np.uint8)
    assert SP.filled_cells(page, win) == sorted(want)
    assert SP.column_counts(want) == [2, 1, 1]


def test_tooltip_cell_anchors_to_the_row_the_box_grew_out_of():
    win = SP.Window(232, 32, 1.0)
    for col in range(SP.COLUMNS):
        for row in range(SP.ROWS):
            x = win.x + SP.COL_X[col] + SP.TOOLTIP_ANCHOR_DX
            bottom = win.y + SP.ROW_Y[row] - SP.TOOLTIP_ANCHOR_DY
            assert SP.tooltip_cell(win, (x, bottom - 140, 230, 140)) == (col, row)


def test_tooltip_cell_is_none_when_the_box_fits_no_row():
    win = SP.Window(232, 32, 1.0)
    assert SP.tooltip_cell(win, (win.x + 900, win.y + 300, 230, 140)) is None
    assert SP.tooltip_cell(win, (win.x + SP.COL_X[0] + SP.TOOLTIP_ANCHOR_DX, 0, 230, 20)) is None


def test_find_tooltip_needs_change_darkness_and_an_anchor():
    win = SP.Window(0, 0, 1.0)
    bg = np.full((SP.WINDOW_H, SP.WINDOW_W), 200, np.uint8)
    frame = bg.copy()
    x = SP.COL_X[1] + SP.TOOLTIP_ANCHOR_DX
    bottom = SP.ROW_Y[3] - SP.TOOLTIP_ANCHOR_DY
    frame[bottom - 150:bottom, x:x + 230] = 40
    box = SP.find_tooltip(frame, bg, win)
    assert box is not None
    bx, by, bw, bh = box
    assert SP.tooltip_cell(win, box) == (1, 3)
    assert 140 <= bw <= 380 and bh >= 50
    # the same box where no row anchors it is not a tooltip
    stray = bg.copy()
    stray[300:450, 5:235] = 40
    assert SP.find_tooltip(stray, bg, win) is None
    # and an unchanged frame has none at all
    assert SP.find_tooltip(bg.copy(), bg, win) is None


def test_grow_right_follows_the_box_past_the_window_edge():
    gray = np.full((400, 1000), 220, np.uint8)
    gray[100:200, 300:560] = 40
    x, y, w, h = SP.grow_right(gray, (300, 100, 200, 100))
    assert x + w == 560
    # it stops at the limit even if the dark region runs on
    gray[100:200, 300:999] = 40
    _, _, w2, _ = SP.grow_right(gray, (300, 100, 200, 100), limit=250)
    assert w2 == 250


def test_tooltip_mask_needs_both_tests():
    bg = np.full((40, 40), 200, np.uint8)
    frame = bg.copy()
    frame[10:20, 10:20] = 30        # changed and dark  -> in the mask
    frame[25:35, 25:35] = 255       # changed but bright -> out
    mask = SP.tooltip_mask(frame, bg)
    assert mask[15, 15] == 255 and mask[30, 30] == 0
    # a dark region that did not change (an icon, the window frame) is out too
    both = np.full((40, 40), 30, np.uint8)
    assert SP.tooltip_mask(both, both).sum() == 0


# --------------------------------------------------------------------------- list text

@pytest.mark.parametrize("subtitle,rank", [
    ("Rank 4", 4), ("rank 12", 12), ("Rank1", 1), ("", None), ("Passive", None),
    ("Racial Passive", None), ("Rank", None),
])
def test_parse_rank(subtitle, rank):
    assert SP.parse_rank(subtitle) == rank


@pytest.mark.parametrize("subtitle,kind", [
    ("", "active"), ("Passive", "passive"), ("Racial", "racial"),
    ("Racial Passive", "racial-passive"), ("racial passive", "racial-passive"),
])
def test_entry_kind(subtitle, kind):
    assert SP.entry_kind(subtitle) == kind


def test_strip_rank_and_spell_id():
    assert SP.strip_rank("Holy Strike Rank 5") == "Holy Strike"
    assert SP.strip_rank("Seal of the Crusader") == "Seal of the Crusader"
    assert SP.spell_id("Blessing of Might Rank 4") == "blessing-of-might"
    assert SP.spell_id("Hunter's Mark") == "hunters-mark"


def test_normalise_entry_repairs_the_shapes_the_model_produces():
    assert SP.normalise_entry({"name": "Blessing of Might", "subtitle": "Rank 4"}) == {
        "name": "Blessing of Might", "rank": 4, "kind": "active", "cut_off": False}
    # rank glued onto the name
    assert SP.normalise_entry({"name": "Holy Strike Rank 5", "subtitle": ""})["rank"] == 5
    # bare number in the subtitle
    assert SP.normalise_entry({"name": "Fire Ward", "subtitle": "2"})["rank"] == 2
    # a kind subtitle survives as the kind
    e = SP.normalise_entry({"name": "Touch of the Grave", "subtitle": "Racial Passive"})
    assert (e["rank"], e["kind"]) == (None, "racial-passive")


def test_clean_page_reading_drops_headings_and_duplicates():
    doc = {"entries": [
        {"name": "General", "subtitle": "", "cut_off": False},
        {"name": "Attack", "subtitle": "", "cut_off": False},
        {"name": "Attack", "subtitle": "", "cut_off": False},
        {"name": "Cannibalize", "subtitle": "Racial", "cut_off": False},
        {"name": "  ", "subtitle": "", "cut_off": False},
    ]}
    out = SP.clean_page_reading(doc)
    assert [e["name"] for e in out] == ["Attack", "Cannibalize"]
    assert out[1]["kind"] == "racial"


@pytest.mark.parametrize("name,prose", [
    ("Shadow Resistance Aura", False),
    ("Power Word: Fortitude", False),
    ("Faerie Fire (Feral)", False),
    ("Place a Fire trap that explodes when an enemy approaches, causing Fire damage.", True),
    ("Instant. 30 sec cooldown", True),
    ("Absorbs 285 Fire damage.", True),
    ("Afflicts the target with agony", True),
    ("Seal of the Crusader", False),
    ("Call of the Ancestors", False),
])
def test_looks_like_prose(name, prose):
    assert SP.looks_like_prose(name) is prose


def test_clean_page_reading_drops_a_tooltip_body_read_as_a_row():
    doc = {"entries": [
        {"name": "Freezing Trap", "subtitle": "Rank 2", "cut_off": False},
        {"name": "Place a Fire trap that explodes when an enemy approaches, causing Fire damage "
                 "and 150 additional damage over 20 sec.", "subtitle": "", "cut_off": False},
    ]}
    assert [e["name"] for e in SP.clean_page_reading(doc)] == ["Freezing Trap"]


def test_clean_page_reading_keeps_two_ranks_of_one_spell():
    doc = {"entries": [{"name": "Blessing of Might", "subtitle": f"Rank {n}", "cut_off": False}
                       for n in (1, 2, 3)]}
    assert [e["rank"] for e in SP.clean_page_reading(doc)] == [1, 2, 3]


@pytest.mark.parametrize("a,b,conf", [
    ({"name": "Fire Ward", "rank": 2, "kind": "active"},
     {"name": "Fire Ward", "rank": 2, "kind": "active"}, 1.0),
    ({"name": "Fire Ward", "rank": 2, "kind": "active"},
     {"name": "Fire Ward", "rank": 3, "kind": "active"}, 0.7),
    ({"name": "Fire Ward", "rank": 2, "kind": "active"},
     {"name": "Frost Ward", "rank": 2, "kind": "active"}, 0.3),
    ({"name": "Fire Ward", "rank": 2, "kind": "active"}, None, 0.0),
])
def test_confidence(a, b, conf):
    assert SP.confidence(a, b) == conf


def test_show_all_ranks():
    assert SP.show_all_ranks([{"name": "Holy Strike", "rank": 1}, {"name": "Holy Strike", "rank": 2}])
    assert not SP.show_all_ranks([{"name": "Holy Strike", "rank": 5}, {"name": "Judgement", "rank": None}])


@pytest.mark.parametrize("title,tab", [
    ("Retribution", "retribution"), ("Elemental Combat", "elemental-combat"),
    ("General", "general"), ("Name Matches", None), ("Exact Matches", None), ("", None),
])
def test_tab_from_title(title, tab):
    assert SP.tab_from_title(title) == tab


@pytest.mark.parametrize("read,want,snapped", [
    ("Marksmananship", "Marksmanship", True),
    ("Marksmanship", "Marksmanship", False),
    ("Retributlon", "Retribution", True),
    ("Name Matches", "Name Matches", False),
    ("general", "General", False),
    ("", "", False),
])
def test_snap_title_fixes_a_near_miss_only(read, want, snapped):
    cands = ["General", "Beast Mastery", "Marksmanship", "Survival", "Retribution"]
    assert SP.snap_title(read, cands) == (want, snapped)


def test_snap_title_leaves_a_real_rename_alone():
    # Classic's tree is "Elemental"; Forever renamed it, and that must survive
    assert SP.snap_title("Elemental Combat", ["Elemental", "Enhancement", "Restoration"]) == \
        ("Elemental Combat", False)


def test_merge_entries_keeps_the_best_reading_and_the_page_order():
    recs = [
        {"name": "Judgement", "rank": None, "kind": "active", "col": 1, "row": 6,
         "source": {"confidence": 1.0, "sharpness": 10.0}},
        {"name": "Blessing of Might", "rank": 1, "kind": "active", "col": 0, "row": 0, "cut_off": True,
         "source": {"confidence": 1.0, "sharpness": 99.0}},
        {"name": "Blessing of Might", "rank": 2, "kind": "active", "col": 0, "row": 0,
         "source": {"confidence": 0.7, "sharpness": 3.0}},
    ]
    out = SP.merge_entries(recs)
    assert [r["name"] for r in out] == ["Blessing of Might", "Judgement"]
    assert out[0]["cell"] == [0, 0] and out[0]["ranks"] == [1, 2]

    # two readings of the same (spell, rank): the complete one wins over the sharper but
    # clipped one, which survives as an alternate
    same = [recs[1], dict(recs[1], cut_off=False, source={"confidence": 0.7, "sharpness": 3.0},
                          kind="passive")]
    merged = SP.merge_entries(same)
    assert len(merged) == 1
    assert merged[0]["source"]["confidence"] == 0.7
    assert len(merged[0]["alternates"]) == 1


def test_merge_entries_collects_the_ranks_of_one_spell():
    recs = [{"name": "Holy Strike", "rank": n, "kind": "active", "col": 1, "row": n,
             "source": {"confidence": 1.0, "sharpness": 1.0}} for n in (3, 1, 2)]
    out = SP.merge_entries(recs)
    assert len(out) == 1
    assert out[0]["ranks"] == [1, 2, 3]
    assert out[0]["cell"] == [1, 1]


def test_merge_entries_leaves_a_rankless_spell_without_ranks():
    out = SP.merge_entries([{"name": "Judgement", "rank": None, "kind": "active", "col": 0, "row": 0,
                             "source": {"confidence": 1.0, "sharpness": 1.0}}])
    assert out[0]["ranks"] == []


def test_dedupe_states_keeps_the_sharpest_of_each_page():
    win = SP.Window(0, 0, 1.0)
    page_a = _page(200)
    page_b = _page(200)
    x0, y0, x1, y1 = SP._box(win, SP.TITLE_TEXT)
    page_b[y0:y1, x0:x1] = 20
    pages = {"a1": page_a, "a2": page_a.copy(), "b": page_b}
    states = [{"id": "a1", "class": "mage", "t": 1.0, "sharpness": 5.0},
              {"id": "a2", "class": "mage", "t": 2.0, "sharpness": 50.0},
              {"id": "b", "class": "mage", "t": 3.0, "sharpness": 9.0}]
    kept = SP.dedupe_states(states, lambda s: pages[s["id"]])
    assert [s["id"] for s in kept] == ["a2", "b"]


def test_dedupe_states_does_not_merge_two_classes():
    page = _page(200)
    states = [{"id": "x", "class": "mage", "t": 1.0, "sharpness": 5.0},
              {"id": "y", "class": "druid", "t": 2.0, "sharpness": 6.0}]
    assert len(SP.dedupe_states(states, lambda s: page)) == 2


def test_dedupe_tooltips_keeps_the_sharpest_copy():
    rng = np.random.default_rng(2)
    same = rng.integers(0, 255, (120, 230, 3), dtype=np.uint8)
    other = rng.integers(0, 255, (120, 230, 3), dtype=np.uint8)
    imgs = {"a": same, "b": same.copy(), "c": other}
    items = [{"id": "a", "_class": "hunter", "t": 1.0, "sharpness": 3.0},
             {"id": "b", "_class": "hunter", "t": 2.0, "sharpness": 30.0},
             {"id": "c", "_class": "hunter", "t": 3.0, "sharpness": 4.0}]
    kept = SP.dedupe_tooltips(items, lambda i: imgs[i["id"]])
    assert [i["id"] for i in kept] == ["b", "c"]


# --------------------------------------------------------------------------- stage 11 helpers

def test_clean_tooltip_normalises_and_strips_the_tools_label():
    out = st11.clean_tooltip({
        "name": " Stoneclaw Totem ", "cost": "75 Mana", "range": "", "cast_time": "Instant",
        "cooldown": "30 sec cooldown", "tools": "Tools: Earth Totem", "requires": ["", "Requires Shields"],
        "description": "Summons  a totem.", "footer": None, "cut_off": False})
    assert out["name"] == "Stoneclaw Totem"
    assert out["range"] is None
    assert out["tools"] == "Earth Totem"
    assert out["requires"] == ["Requires Shields"]
    assert out["description"] == "Summons a totem."


def test_tooltip_confidence():
    a = st11.clean_tooltip({"name": "Fire Ward", "description": "Absorbs 285 Fire damage.",
                            "cost": "135 Mana"})
    b = dict(a)
    assert st11.tooltip_confidence(a, b) == 1.0
    assert st11.tooltip_confidence(a, {**a, "cost": "130 Mana"}) == 0.7
    assert st11.tooltip_confidence(a, {**a, "description": "Absorbs 280 Fire damage."}) == 0.3
    assert st11.tooltip_confidence(a, None) == 0.0


def test_pair_entries_matches_by_position_then_by_id():
    a = [{"name": "Blessing of Might", "rank": 1, "kind": "active"},
         {"name": "Blessing of Might", "rank": 2, "kind": "active"},
         {"name": "Holy Strike", "rank": 1, "kind": "active"}]
    b = [{"name": "Blessing of Might", "rank": 1, "kind": "active"},
         {"name": "Blessing of Might", "rank": 2, "kind": "active"},
         {"name": "Holy Strike", "rank": 1, "kind": "active"}]
    out = st11._pair_entries(a, b)
    assert [e["confidence"] for e in out] == [1.0, 1.0, 1.0]
    # a pass that skipped a row still matches the rest
    out = st11._pair_entries(a, b[1:])
    assert [e["confidence"] for e in out] == [0.0, 1.0, 1.0]


def test_pair_entries_reports_a_row_only_one_pass_saw():
    out = st11._pair_entries([], [{"name": "Judgement", "rank": None, "kind": "active"}])
    assert len(out) == 1 and out[0]["confidence"] == 0.0


def test_apply_third_caps_two_agreeing_passes_when_codex_differs():
    e = {"name": "Fire Ward", "rank": 2, "kind": "active", "confidence": 1.0,
         "readings": [{"name": "Fire Ward", "rank": 2, "kind": "active"},
                      {"name": "Fire Ward", "rank": 2, "kind": "active"}]}
    out = st11._apply_third([e], [{"name": "Fire Ward", "rank": 3, "kind": "active"}])
    assert out[0]["confidence"] == 0.9
    # two of three verbatim lifts a disagreeing pair
    e2 = {**e, "confidence": 0.3}
    out = st11._apply_third([e2], [{"name": "Fire Ward", "rank": 2, "kind": "active"}])
    assert out[0]["confidence"] == 0.85


def test_rank_at_cell_lines_the_entries_up_with_the_icons():
    state = {"cells": [[0, 0], [0, 1], [0, 3], [1, 0]],
             "columns": [{"col": 0, "entries": [{"rank": 4}, {"rank": 5}, {"rank": 1}]},
                         {"col": 1, "entries": [{"rank": None}]}]}
    assert st11._rank_at_cell(state, [0, 0]) == 4
    assert st11._rank_at_cell(state, [0, 3]) == 1      # row 2 is empty, so row 3 is the third entry
    assert st11._rank_at_cell(state, [1, 0]) is None
    assert st11._rank_at_cell(state, [2, 0]) is None   # column never read
    assert st11._rank_at_cell(None, [0, 0]) is None
    assert st11._rank_at_cell(state, None) is None


@pytest.mark.parametrize("spec,want", [
    ("03:59:00-04:02:00", (14340, 14520)),
    ("14340-14520", (14340, 14520)),
    ("59:00-1:02:00", (3540, 3720)),
])
def test_parse_window(spec, want):
    assert st11.parse_window(spec) == want


def test_hms():
    assert st11.hms(14380.5) == "03:59:40"


def test_classic_for_marks_an_unknown_name_new_and_a_known_one_unknown():
    prior = {"paladin": {"spells": ["Blessing of Might"]}, "_shared": {"spells": ["Attack"]}}
    assert st11._classic_for(prior, "paladin", "Seal of Fury")["status"] == "new"
    known = st11._classic_for(prior, "paladin", "Blessing of Might")
    assert known["status"] == "unknown" and known["classicName"] == "Blessing of Might"
    assert st11._classic_for(prior, "paladin", "Attack")["status"] == "unknown"
    assert "note" in st11._classic_for(prior, "paladin", "Seal of Fury")


def test_classic_for_does_not_call_a_classic_talent_new():
    prior = {"hunter": {"spells": ["Arcane Shot"]}}
    talents = {"hunter": {"aimed-shot": "Marksmanship"}}
    out = st11._classic_for(prior, "hunter", "Aimed Shot", talents)
    assert out["status"] == "unknown"
    assert "Marksmanship talent" in out["note"]
    assert "not evidence" in out["note"]
    # without the talent table the same name would have been called new
    assert st11._classic_for(prior, "hunter", "Aimed Shot")["status"] == "new"


def test_classic_for_claims_nothing_without_a_prior():
    assert st11._classic_for({}, "rogue", "Sinister Strike")["status"] == "unknown"


def test_json_object_finds_a_fenced_answer():
    text = 'Sure!\n```json\n{"entries":[{"name":"Attack","subtitle":"","cut_off":false}]}\n```\n'
    assert st11._json_object(text, "entries")["entries"][0]["name"] == "Attack"
    assert st11._json_object('{"other":1}', "entries") is None


# --------------------------------------------------------------------------- validator

def _doc(**over) -> dict:
    src = {"kind": "video", "video": "X", "t": 1.0, "frame": 60, "crop": "data/review/spells/mage/a.png",
           "panel": "spell-list", "confidence": 1.0, "reader": "r", "reviewed": False}
    doc = {
        "$schema": "../schema/spell.schema.json", "schemaVersion": 1, "class": "mage",
        "className": "Mage", "dataSource": "video", "generatedAt": "2026-09-13T10:00:00Z",
        "observedLevel": 38,
        "tabs": [{"id": "arcane", "name": "Arcane", "order": 0}],
        "spells": [{"id": "blink", "name": "Blink", "kind": "active", "tab": "arcane",
                    "classic": {"status": "unknown", "classicName": "Blink", "note": "unverified"},
                    "source": dict(src)}],
        "coverage": {"pagesSeen": ["Arcane"], "tabsSeen": ["arcane"],
                     "tabsMissing": ["fire", "frost", "general"], "states": 1, "entriesRead": 1,
                     "tooltipsRead": 0, "tooltipsUnmatched": 0, "showAllSpellRanks": "not observed", "observedLevel": 38,
                     "windows": ["04:18:00"]},
        "complete": False, "notes": ["Fire and Frost were never opened."],
    }
    doc.update(over)
    return doc


def _findings(doc: dict, fn, *args) -> list[str]:
    ctx = VS.Ctx(VS.FileResult(Path("mage.json")), None)
    fn(ctx, doc, *args)
    return [f.code for f in ctx.result.findings]


def test_validator_accepts_a_well_formed_file():
    doc = _doc()
    schema = json.loads((ROOT.parent / "data" / "schema" / "spell.schema.json").read_text())
    ctx = VS.Ctx(VS.FileResult(Path("mage.json")), None)
    assert VS.rule_1_schema(ctx, doc, schema)
    for rule in (VS.rule_3_spells_unique, VS.rule_4_tabs, VS.rule_5_coverage, VS.rule_6_ranks,
                 VS.rule_7_classic, VS.rule_8_sources, VS.rule_10_complete, VS.rule_11_tooltips,
                 VS.rule_15_counts):
        assert _findings(doc, rule) == [], rule.__name__


def test_validator_catches_a_coverage_count_that_drifted():
    doc = _doc()
    doc["coverage"]["entriesRead"] = 7
    assert "COVERAGE-COUNT" in _findings(doc, VS.rule_5_coverage)


def test_validator_catches_a_tab_that_is_both_seen_and_missing():
    doc = _doc()
    doc["coverage"]["tabsMissing"] = ["arcane", "fire", "frost", "general"]
    assert "COVERAGE-TABS" in _findings(doc, VS.rule_5_coverage)


def test_validator_requires_show_all_ranks_when_a_spell_has_two_ranks():
    doc = _doc()
    doc["spells"] = [dict(doc["spells"][0], ranksSeen=[1, 2])]
    assert "SHOW-ALL-RANKS" in _findings(doc, VS.rule_6_ranks)
    doc["coverage"]["showAllSpellRanks"] = "on"
    assert _findings(doc, VS.rule_6_ranks) == []


def test_validator_rejects_show_all_ranks_without_evidence():
    doc = _doc()
    doc["coverage"]["showAllSpellRanks"] = "on"
    assert "SHOW-ALL-RANKS" in _findings(doc, VS.rule_6_ranks)


def test_validator_requires_a_note_on_a_spell_without_a_tab():
    doc = _doc()
    doc["spells"][0].pop("tab")
    assert "NO-TAB-NOTE" in _findings(doc, VS.rule_4_tabs)
    doc["spells"][0]["source"]["note"] = "read from a search-results page"
    assert _findings(doc, VS.rule_4_tabs) == []


def test_validator_rejects_complete_with_missing_tabs():
    doc = _doc(complete=True)
    assert "COMPLETE-MISSING-TABS" in _findings(doc, VS.rule_10_complete)


def test_validator_rejects_a_classic_block_without_a_note():
    doc = _doc()
    doc["spells"][0]["classic"] = {"status": "new"}
    assert "CLASSIC-NOTE" in _findings(doc, VS.rule_7_classic)


def test_validator_rejects_a_tooltip_rank_outside_ranks_seen():
    doc = _doc()
    doc["spells"][0]["ranksSeen"] = [2]
    doc["spells"][0]["tooltips"] = [{"rank": 3, "description": "x",
                                     "source": {"kind": "video", "reviewed": False}}]
    assert "TOOLTIP-RANK" in _findings(doc, VS.rule_11_tooltips)


def test_validator_rejects_a_duplicate_spell_and_rank():
    doc = _doc()
    doc["spells"] = [doc["spells"][0], dict(doc["spells"][0])]
    assert "DUPLICATE-SPELL" in _findings(doc, VS.rule_3_spells_unique)


def test_canonical_dumps_is_stable_and_orders_keys():
    doc = _doc()
    once = VS.canonical_dumps(doc)
    assert VS.canonical_dumps(json.loads(once)) == once
    keys = list(json.loads(once).keys())
    assert keys == [k for k in VS.KEY_ORDER["top"] if k in keys]
    assert once.endswith("\n")


def test_canonical_dumps_sorts_spells_by_tab_then_id():
    doc = _doc()
    base = doc["spells"][0]
    doc["tabs"].append({"id": "fire", "name": "Fire", "order": 1})
    doc["spells"] = [dict(base, id="scorch", name="Scorch", tab="fire"),
                     dict(base, id="blink", name="Blink", tab="arcane")]
    out = json.loads(VS.canonical_dumps(doc))
    assert [s["id"] for s in out["spells"]] == ["blink", "scorch"]

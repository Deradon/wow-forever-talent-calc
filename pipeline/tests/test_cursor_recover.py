"""Unit tests for scripts/cursor_recover.py (pure helpers; no video, no network)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wowtalents import ui  # noqa: E402

_spec = importlib.util.spec_from_file_location("cursor_recover", ROOT / "scripts" / "cursor_recover.py")
cr = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["cursor_recover"] = cr      # dataclasses resolve annotations through sys.modules
_spec.loader.exec_module(cr)


# --------------------------------------------------------------------------- ids / geometry


def test_parse_cell_id_round_trip():
    slugs = {1: "arcane", 2: "fire", 3: "frost"}
    assert cr.cell_id(slugs, (2, 3, 1)) == "fire-r3c1"
    assert cr.parse_cell_id("fire-r3c1") == ("fire", 3, 1)
    assert cr.parse_cell_id("elemental-combat-r2c3") == ("elemental-combat", 2, 3)


def test_tree_slugs_matches_stage4_rule():
    assert cr.tree_slugs({"trees_visible": ["Elemental Combat", "Enhancement"]}) == {
        1: "elemental-combat", 2: "enhancement", 3: "tree3"}


def test_generous_rect_is_clipped_to_roi():
    c = ui.Cell(1, 1, 1, 499, 238, 36, 36)
    x0, y0, x1, y1 = cr.generous_rect(c)
    assert (x0, y0) == (ui.WORK_ROI[0], 0)            # cell +/- 400/300 leaves the ROI on the left and top
    assert x1 == 499 + 18 + 400 and y1 == 238 + 18 + 300
    far = ui.Cell(3, 7, 4, 1388, 562, 36, 36)
    assert cr.generous_rect(far)[2:] == (ui.WORK_ROI[2], ui.WORK_ROI[3])


def test_hotspot_is_template_top_left_inside_margin():
    assert cr.hotspot(100, 50, margin=2) == (101, 51)
    assert cr.hotspot(100, 50, margin=0) == (100, 50)


# --------------------------------------------------------------------------- dwells


def test_dwell_events_groups_frames_and_tolerates_short_gaps():
    a, b = (1, 2, 3), (1, 2, 4)
    fps = 60.0
    seq = [(i / fps, c) for i, c in enumerate([a, a, None, None, a, a, None, None, None, None, b, b, b])]
    ev = cr.dwell_events(seq, max_gap=3)
    assert [(e.cell, e.first, e.last, e.frames) for e in ev] == [(a, 0, 5, 4), (b, 10, 12, 3)]
    assert abs(ev[0].ms - 5 / fps * 1000) < 0.1          # Dwell.ms is rounded to 0.1 ms
    assert ev[0].to_json(fps)["ms"] == round(6 / fps * 1000, 1)     # inclusive of the last frame


def test_dwell_events_switch_cell_without_gap_and_single_frames():
    a, b = (2, 1, 1), (2, 1, 2)
    ev = cr.dwell_events([(0.0, a), (0.1, b), (0.2, b), (0.3, a)])
    assert [(e.cell, e.frames) for e in ev] == [(a, 1), (b, 2), (a, 1)]


def test_candidate_indices_window_and_clipping():
    idx = cr.candidate_indices(first=100, fps=60, lead_ms=100, span_ms=400, step=3)
    assert idx[0] == 106 and idx[-1] == 124 and all(b - a == 3 for a, b in zip(idx, idx[1:]))
    assert cr.candidate_indices(100, 60, step=3, n_frames=110) == [106, 109]
    assert cr.candidate_indices(0, 30, lead_ms=100, span_ms=400, step=1) == list(range(3, 13))


def test_track_to_events_uses_cell_columns():
    tr = {"fps": 60.0, "track": [[10, 0, 0.9, 5, 5, 1, 1, 1], [10, 1, 0.9, 5, 5, 1, 1, 1],
                                 [10, 2, 0.5, 5, 5, -1, -1, -1], [10, 3, 0.9, 9, 9, 2, 3, 4]]}
    ev = cr.track_to_events(tr)
    assert [(e.cell, e.frames) for e in ev] == [((1, 1, 1), 2), ((2, 3, 4), 1)]


# --------------------------------------------------------------------------- pointer template


def _glove(size=(22, 25)) -> np.ndarray:
    """A white glove-ish blob with a dark outline on a mid-grey background."""
    h, w = size
    img = np.full((h, w, 3), 60, np.uint8)
    cv2.circle(img, (12, 12), 7, (20, 20, 20), -1)
    cv2.circle(img, (12, 12), 5, (230, 230, 230), -1)
    cv2.line(img, (3, 3), (10, 10), (240, 240, 240), 2)
    return img


def test_build_template_and_find_cursor_locate_the_blob():
    bg = np.full((200, 300, 3), 60, np.uint8)
    frame = bg.copy()
    glove = _glove()
    frame[100:122, 150:175] = glove
    tpl, mask = cr.build_template(frame, bg, (120, 80, 220, 160), margin=2)
    assert mask.max() == 255 and tpl.shape[0] >= 10
    score, x, y = cr.find_cursor(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY))
    assert score > 0.95
    assert abs(x - (150 - 2)) <= 3 and abs(y - (100 - 2)) <= 3


def test_find_cursor_scores_low_when_absent():
    tpl = cv2.cvtColor(_glove(), cv2.COLOR_BGR2GRAY)
    rng = np.random.default_rng(0)
    noise = rng.integers(40, 80, (200, 300), dtype=np.uint8)
    score, _, _ = cr.find_cursor(noise, tpl)
    assert score < cr.MATCH_MIN


# --------------------------------------------------------------------------- dark boxes


def _synthetic_window() -> np.ndarray:
    """Dark tree art (gray 8-30, irregular) plus one tooltip (interior gray 3, bright text, grey border)."""
    rng = np.random.default_rng(1)
    img = rng.integers(8, 30, (400, 600, 3), dtype=np.uint8)
    cv2.rectangle(img, (40, 250), (140, 390), (5, 5, 5), -1)       # a black blob of art, 100 px wide
    cv2.rectangle(img, (300, 100), (520, 220), (95, 95, 95), 2)    # border
    cv2.rectangle(img, (302, 102), (518, 218), (3, 3, 3), -1)      # interior 217 x 117
    for k in range(5):
        cv2.putText(img, "Improved Fire Blast rank 0/3", (310, 120 + 18 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (230, 230, 230), 1, cv2.LINE_AA)
    return img


def test_dark_boxes_finds_the_tooltip_interior_only():
    img = _synthetic_window()
    boxes = cr.dark_boxes(img)
    assert len(boxes) == 1
    x, y, w, h = boxes[0]
    assert abs(x - 302) <= 1 and abs(y - 102) <= 1 and abs(w - 217) <= 2 and abs(h - 117) <= 2


def test_dark_boxes_ignores_boxes_that_touch_dark_art_when_not_rectangular():
    img = _synthetic_window()
    # an irregular near-black region as wide as a tooltip but far from rectangular
    pts = np.array([[380, 300], [560, 260], [590, 380], [450, 395], [400, 340]], np.int32)
    cv2.fillPoly(img, [pts], (4, 4, 4))
    boxes = cr.dark_boxes(img)
    assert len(boxes) == 1 and abs(boxes[0][1] - 102) <= 1


def test_dark_boxes_rejects_black_art_rectangles_without_text():
    img = _synthetic_window()
    cv2.rectangle(img, (60, 300), (270, 360), (4, 4, 4), -1)      # 211 x 61 black patch, no text
    boxes = cr.dark_boxes(img)
    assert len(boxes) == 1 and abs(boxes[0][0] - 302) <= 1
    assert cr.text_rows(cv2.cvtColor(img[300:361, 60:271], cv2.COLOR_BGR2GRAY)) == 0


def test_tight_crop_includes_the_border():
    img = _synthetic_window()
    crop = cr.tight_crop(img, cr.dark_boxes(img)[0], margin=4)
    assert crop.shape[0] >= 117 + 8 and crop.shape[1] >= 217 + 8
    assert ui.darkness(crop) >= ui.TOOLTIP_MIN_DARK


def test_diff_fill_low_over_dark_art_high_over_bright_art():
    frame = _synthetic_window()
    bg_dark = frame.copy()
    bg_dark[100:222, 300:522] = 15          # tree art under the tooltip is nearly black
    bg_bright = frame.copy()
    bg_bright[100:222, 300:522] = 120
    box = cr.dark_boxes(frame)[0]
    assert cr.diff_fill(frame, bg_dark, box) < 0.45
    assert cr.diff_fill(frame, bg_bright, box) > 0.8


# --------------------------------------------------------------------------- consensus / verdicts


def _calib(trees, cells):
    return {"trees_visible": trees, "cells": [{"tree": t, "row": r, "col": c} for t, r, c in cells]}


def test_consensus_missing_uses_majority_of_calibrations_and_all_hovers():
    calibs = [_calib(["Arcane", "Fire", "Frost"], [(1, 1, 1), (1, 1, 2), (2, 1, 1)]),
              _calib(["Arcane", "Fire", "Frost"], [(1, 1, 1), (1, 1, 2), (2, 1, 1), (3, 7, 2)]),
              _calib(["Arcane", "Fire", "Frost"], [(1, 1, 1), (1, 1, 2)])]
    hovers = [{"hovers": [{"id": "arcane-r1c1"}]}, {"hovers": [{"id": "fire-r1c1"}]}]
    missing, counts = cr.consensus_missing(hovers, calibs)
    assert missing == ["arcane-r1c2"]            # frost-r7c2 is in 1 of 3 calibrations: not consensus
    assert counts["frost-r7c2"] == 1 and counts["arcane-r1c1"] == 3


def test_hovered_in_segment_includes_superseded_runs():
    hov = {"hovers": [{"cell": [1, 1, 1]}], "all_runs": [{"cell": [1, 1, 1]}, {"cell": [2, 3, 1]}, {"cell": None}]}
    assert cr.hovered_in_segment(hov) == {(1, 1, 1), (2, 3, 1)}


def _cand(cid, key, cursor, boxes, sharp=1.0, sid="08-mage-14970"):
    return cr.Candidate(cid, key, {"frames": 10, "ms": 150.0, "t_first": 0.0, "t_last": 0.15}, 0, 100, 0, 100.0,
                        cursor, (0, 0), 0.9, (0, 0, 10, 10), boxes, {}, sharp,
                        {"crop": f"candidates/mage/{cid}/{sid}-100-00.png"})


def test_choose_recoveries_requires_cursor_on_cell_and_a_box_per_segment():
    key = (2, 3, 1)
    cands = [_cand("fire-r3c1", key, key, [(10, 10, 200, 90)], 5.0),
             _cand("fire-r3c1", key, key, [(10, 10, 200, 90)], 9.0),
             _cand("fire-r3c1", key, (2, 3, 2), [(10, 10, 200, 90)], 50.0),   # cursor elsewhere
             _cand("fire-r3c1", key, key, [], 99.0),                           # no box
             _cand("fire-r3c1", key, key, [(10, 10, 200, 90)], 2.0, sid="09-mage-15040")]
    best = cr.choose_recoveries(cands)
    assert list(best) == ["fire-r3c1"]
    assert best["fire-r3c1"]["08-mage-14970"].sharpness == 9.0
    assert best["fire-r3c1"]["09-mage-15040"].sharpness == 2.0
    assert cr.primary_segment(best["fire-r3c1"]) == "08-mage-14970"
    assert cr.candidate_segment(cands[-1]) == "09-mage-15040"


def test_verdict_for_distinguishes_never_fast_and_dwelt():
    fps = 60.0
    key = (2, 1, 3)
    assert cr.verdict_for("x", [], [], False, fps)["verdict"].startswith("cursor never")
    one = cr.Dwell(key, 0, 0, 1, 0.0, 0.0)
    v = cr.verdict_for("x", [one], [_cand("x", key, (2, 1, 1), [(1, 1, 200, 80)])], False, fps)["verdict"]
    assert v.startswith("cursor passed too fast") and "another cell's tooltip" in v
    long = cr.Dwell(key, 0, 30, 31, 0.0, 0.5)
    v = cr.verdict_for("x", [long], [_cand("x", key, key, [])], False, fps)
    assert v["verdict"] == "cursor dwelt, no tooltip rendered" and v["dwell_ms_longest"] > 500
    # a long dwell whose candidate frames all show the pointer elsewhere is still "too fast"
    v = cr.verdict_for("x", [long], [_cand("x", key, (2, 1, 1), [])], False, fps)["verdict"]
    assert v.startswith("cursor passed too fast")
    assert cr.verdict_for("x", [long], [], True, fps)["verdict"] == "tooltip present"


def test_find_cursor_with_mask_ignores_surroundings():
    bg = np.full((120, 160, 3), 60, np.uint8)
    frame = bg.copy()
    frame[40:62, 70:95] = _glove()
    tpl, mask = cr.build_template(frame, bg, (50, 20, 120, 90), margin=2)
    bright = frame.copy()                                    # the same glove on a lit icon instead of dark art
    bright[(frame == 60).all(axis=2)] = 200
    g = cv2.cvtColor(bright, cv2.COLOR_BGR2GRAY)
    s_plain, _, _ = cr.find_cursor(g, cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY))
    s_mask, x, y = cr.find_cursor(g, cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY), mask)
    assert s_mask > s_plain + 0.1 and s_mask > 0.7
    assert abs(x - 68) <= 3 and abs(y - 38) <= 3

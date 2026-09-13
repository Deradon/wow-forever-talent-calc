"""Unit tests for wowtalents.arrows on a synthetic tree (no footage needed).

The synthetic frame mimics the stream: a mid-grey art background with a soft
gradient, 36 px cells at the prior pitch, and arrows drawn the way the client
draws them (a 2 px dark stroke with a 1 px lighter core, a filled triangle at
the dependent's edge). A plain dark line without an arrowhead stands in for
tree art that happens to run between two cells.
Run: cd pipeline && uv run pytest -q tests/test_arrows.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wowtalents import arrows as A  # noqa: E402

PITCH, ICON = 54, 36
X0, Y0 = 500, 236


def cell(tree: int, row: int, col: int) -> A.Rect:
    return (X0 + (col - 1) * PITCH, Y0 + (row - 1) * PITCH, ICON, ICON)


def background() -> np.ndarray:
    h, w = 720, 1200
    yy, xx = np.mgrid[0:h, 0:w]
    art = 70 + 25 * np.sin(xx / 60.0) * np.cos(yy / 45.0)
    return art.astype(np.uint8)


def draw_cells(img: np.ndarray, cells: dict[A.Key, A.Rect]) -> None:
    for (x, y, w, h) in cells.values():
        cv2.rectangle(img, (x, y), (x + w - 1, y + h - 1), 30, -1)
        cv2.rectangle(img, (x, y), (x + w - 1, y + h - 1), 110, 1)


def stroke(img: np.ndarray, p0: tuple[int, int], p1: tuple[int, int]) -> None:
    """2 px dark outline with a lighter 1 px core, like the client's bevelled arrow texture."""
    cv2.line(img, p0, p1, 38, 3)
    cv2.line(img, p0, p1, 58, 1)


def arrowhead(img: np.ndarray, tip: tuple[int, int], direction: str) -> None:
    x, y = tip
    if direction == "down":
        pts = [(x - 4, y - 8), (x + 4, y - 8), (x, y)]
    elif direction == "left":
        pts = [(x + 8, y - 4), (x + 8, y + 4), (x, y)]
    else:  # right
        pts = [(x - 8, y - 4), (x - 8, y + 4), (x, y)]
    cv2.fillPoly(img, [np.array(pts, dtype=np.int32)], 40)
    cv2.polylines(img, [np.array(pts, dtype=np.int32)], True, 10, 1)


def scene() -> tuple[np.ndarray, dict[A.Key, A.Rect]]:
    cells = {k: cell(*k) for k in [(1, 1, 1), (1, 1, 2), (1, 1, 3), (1, 2, 1), (1, 2, 2), (1, 3, 2), (1, 3, 3),
                                    (1, 4, 1), (1, 5, 1), (1, 5, 2), (1, 5, 3), (1, 7, 2)]}
    img = background()
    draw_cells(img, cells)

    def centre(k: A.Key) -> tuple[int, int]:
        x, y, w, h = cells[k]
        return x + w // 2, y + h // 2

    # straight arrow r1c2 -> r3c2 through the empty r2c2? no: r2c2 exists, so r1c2 -> r2c2 (one row)
    cx, _ = centre((1, 1, 2))
    stroke(img, (cx, cells[(1, 1, 2)][1] + ICON), (cx, cells[(1, 2, 2)][1] - 1))
    arrowhead(img, (cx, cells[(1, 2, 2)][1] - 1), "down")
    # long straight arrow r5c2 -> r7c2 through the empty r6c2
    cx, _ = centre((1, 5, 2))
    stroke(img, (cx, cells[(1, 5, 2)][1] + ICON), (cx, cells[(1, 7, 2)][1] - 1))
    arrowhead(img, (cx, cells[(1, 7, 2)][1] - 1), "down")
    # same-row arrow pointing LEFT: r5c3 requires nothing, r5c2 requires r5c3
    _, cy = centre((1, 5, 2))
    stroke(img, (cells[(1, 5, 2)][0] + ICON, cy), (cells[(1, 5, 3)][0] - 1, cy))
    arrowhead(img, (cells[(1, 5, 2)][0] + ICON, cy), "left")
    # art: a plain dark line between r2c1 and r4c1 (through the empty r3c1) with no arrowhead
    cx, _ = centre((1, 2, 1))
    cv2.line(img, (cx, cells[(1, 2, 1)][1] + ICON), (cx, cells[(1, 4, 1)][1] - 1), 25, 2)
    # the stream is soft: blur like the 1080p capture does
    return cv2.GaussianBlur(img, (0, 0), 0.9), cells


def test_templates_offer_only_free_paths():
    _, cells = scene()
    shapes = {s for s, _, _, _ in A.templates(cells, (1, 1, 2), (1, 3, 2))}
    assert shapes == set()                       # r2c2 sits between: no straight path
    shapes = {s for s, _, _, _ in A.templates(cells, (1, 5, 2), (1, 7, 2))}
    assert shapes == {"straight"}
    assert A.templates(cells, (1, 1, 1), (1, 3, 2)) == []   # both L variants would cross a cell
    shapes = {s for s, _, _, _ in A.templates(cells, (1, 2, 1), (1, 3, 2))}
    assert shapes == {"L-bottom"}                # L-top would cross r2c2
    assert A.templates(cells, (1, 1, 1), (2, 1, 1)) == []   # other tree


def test_detect_frame_finds_arrows_and_direction():
    img, cells = scene()
    hits = A.detect_frame(img, cells)
    edges = {(h["from"], h["to"], h["shape"]) for h in hits}
    assert ((1, 1, 2), (1, 2, 2), "straight") in edges
    assert ((1, 5, 2), (1, 7, 2), "straight") in edges
    row = [h for h in hits if h["shape"] == "row"]
    assert len(row) == 1 and row[0]["from"] == (1, 5, 3) and row[0]["to"] == (1, 5, 2) and not row[0]["ambiguous"]
    # the art line is covered like a stroke but has no arrowhead energy
    art = [h for h in hits if h["from"] == (1, 2, 1) and h["to"] == (1, 4, 1)]
    assert art and art[0]["head"] < A.HEAD_MIN
    assert all(h["head"] >= A.HEAD_MIN for h in hits if (h["from"], h["to"]) != ((1, 2, 1), (1, 4, 1)))


def test_detect_class_votes_and_gates(tmp_path):
    img, cells = scene()
    p1, p2 = tmp_path / "a.png", tmp_path / "b.png"
    cv2.imwrite(str(p1), cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
    # second median: same tree with a tooltip ghost over the long arrow
    ghost = img.copy()
    cv2.rectangle(ghost, (520, 500), (760, 560), 2, -1)
    cv2.imwrite(str(p2), cv2.cvtColor(ghost, cv2.COLOR_GRAY2BGR))
    calibs = [{"segment_id": "s1", "_median_path": p1}, {"segment_id": "s2", "_median_path": p2}]
    arrows = A.detect_class(calibs, cells)
    edges = {(tuple(a["from"]), tuple(a["to"])) for a in arrows}
    assert ((1, 1, 2), (1, 2, 2)) in edges and ((1, 5, 3), (1, 5, 2)) in edges
    assert ((1, 2, 1), (1, 4, 1)) not in edges            # art line: no arrowhead
    long = [a for a in arrows if tuple(a["to"]) == (1, 7, 2)]
    # seen in one of two medians only: not a majority, dropped by the vote
    assert not long
    one = A.detect_class(calibs[:1], cells)
    assert any(tuple(a["to"]) == (1, 7, 2) for a in one)    # the single-median case keeps it
    for a in one:
        assert set(a) >= {"from", "to", "shape", "confidence", "head_energy", "path", "segments"}
        assert 0 < a["confidence"] <= 1


def test_consensus_rects_majority_and_median():
    calibs = [
        {"cells": [{"tree": 1, "row": 1, "col": 1, "x": 500, "y": 236, "w": 36, "h": 36},
                   {"tree": 1, "row": 2, "col": 1, "x": 500, "y": 290, "w": 36, "h": 36}]},
        {"cells": [{"tree": 1, "row": 1, "col": 1, "x": 502, "y": 236, "w": 36, "h": 36}]},
        {"cells": [{"tree": 1, "row": 1, "col": 1, "x": 501, "y": 237, "w": 36, "h": 36}]},
    ]
    rects = A.consensus_rects(calibs)
    assert rects == {(1, 1, 1): (501, 236, 36, 36)}       # r2c1 seen once of three: out

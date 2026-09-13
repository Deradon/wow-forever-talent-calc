"""Prerequisite arrows read from the un-hovered talent tree (stage 7).

In the Classic-style tree a prerequisite is drawn as a thin line from the
required talent to the dependent one, with an arrowhead at the dependent's
edge: straight down the column, along a row, or L-shaped. In the stream the
lines are a ~2 px semi-transparent black stroke over the tree art (the
locked-talent look: every hover in the footage is at rank 0), so a pixel on
an arrow is roughly half as bright as the art 4-7 px to either side. A
satisfied arrow would be gold; the same ridge test on the bright side covers
that case.

Positional only (OpenCV/numpy); nothing here talks to the VLM. Input is the
median background of each Primary-page calibration (``work/calib``) and the
consensus grid of the class; output is a list of arrows keyed by 1-based
``(tree, row, col)`` cells, with per-segment coverage so a tooltip ghost in
one median cannot invent or hide an arrow on its own.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

Key = tuple[int, int, int]           # (tree, row, col), 1-based like ``ui.Cell``
Rect = tuple[int, int, int, int]     # x, y, w, h
Leg = tuple[str, int, int, int]      # ('v', x, y0, y1) or ('h', y, x0, x1), exclusive upper bound

RIDGE_SIDE = (4, 7)      # the art is sampled 4..7 px to either side of the candidate line
RIDGE_ABS = 5            # a line must be at least this much darker (or brighter) than both sides ...
RIDGE_REL = 0.22         # ... and this fraction of the side brightness (line ~0.5 x art in the stream)
LEG_MIN_COVER = 0.5      # share of a leg's pixels on the ridge for the leg to count (0.58 seen on a real arrow)
LEG_MARGIN = 3           # px kept clear of the cell borders (glow of lit cells)
HEAD_HALF = 4            # arrowhead energy is the mean |Laplacian| over a 9 px band across the line ...
HEAD_WINDOW = 8          # ... taken as the top-3 mean of the 8 px next to the dependent's cell ...
HEAD_SKIP = 3            # ... skipping the cell's own border and glow
HEAD_MIN = 9.5           # an arrowhead scores at least this (measured 9.6-22; tree art in the gaps 2-8.4)
# Horizontal arrows between neighbouring cells are a short stub ending in a small round
# head rather than the tall triangle a vertical arrow gets, so they score lower: the two
# real ones in the footage measure 8.3 (priest Mind Flay -> Improved Mind Flay) and 15.9
# (paladin Holy Shock -> Divine Precision). Of the twelve same-row candidates that clear
# LEG_MIN_COVER across the nine classes, the strongest piece of art scores 6.8 (paladin
# Retribution r5c1-c2, a diagonal highlight, checked by eye), so the floor sits between.
# See docs/handover/2026-09-13-cell-attribution-audit.md.
HEAD_MIN_ROW = 7.5
HEAD_GOOD = 11.0         # below this, or below HEAD_GAIN x the stroke, confidence is capped at 0.7
HEAD_GAIN = 1.3
ROW_MIN_RATIO = 1.15     # same-row arrows: the head end must beat the tail end by this factor to fix the direction
MAX_ROW_SPAN = 4         # longest straight arrow considered (Classic: 3 rows)
MAX_COL_SPAN = 3
MIN_CALIB_CELLS = 40     # calibrations with fewer cells (spellbook over the window) do not vote


# --------------------------------------------------------------------------- calibrations and cells


def class_calibs(cls: str, calib_dir: Path) -> list[dict]:
    """Own (not borrowed) Primary-page calibrations of a class with a plausible grid and a median file."""
    out = []
    for p in sorted(calib_dir.glob(f"*-{cls}-*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("class") != cls or d.get("borrowed_from"):
            continue
        if (d.get("page") or "Primary") != "Primary" or len(d.get("cells") or []) < MIN_CALIB_CELLS:
            continue
        median = (d.get("files") or {}).get("median")
        if not median or not (calib_dir / median).is_file():
            continue
        d["_median_path"] = calib_dir / median
        out.append(d)
    return out


def consensus_rects(calibs: list[dict]) -> dict[Key, Rect]:
    """Cells seen in more than half of the calibrations, with the median of their rects."""
    votes: dict[Key, list[Rect]] = defaultdict(list)
    for d in calibs:
        for c in d["cells"]:
            votes[(c["tree"], c["row"], c["col"])].append((c["x"], c["y"], c["w"], c["h"]))
    need = len(calibs) / 2
    return {k: tuple(int(round(float(np.median([v[i] for v in vs])))) for i in range(4))  # type: ignore[misc]
            for k, vs in votes.items() if len(vs) > need}


# --------------------------------------------------------------------------- ridge maps


def ridge_masks(gray: np.ndarray, side: tuple[int, int] = RIDGE_SIDE, abs_min: int = RIDGE_ABS,
                rel_min: float = RIDGE_REL) -> tuple[np.ndarray, np.ndarray]:
    """Boolean maps of thin vertical and horizontal lines (dark or bright against the art beside them).

    For a vertical line the centre is the darkest of x-1..x+1 and the sides are the
    mean of x-7..x-4 and x+4..x+7; a pixel is on a dark ridge when both sides exceed the
    centre by ``max(abs_min, rel_min * side)`` and on a bright ridge symmetrically.
    """
    g = gray.astype(np.float32)
    h, w = g.shape
    pad = side[1] + 1
    gp = np.pad(g, pad, mode="edge")

    def shifted(dx: int, dy: int) -> np.ndarray:
        return gp[pad + dy:pad + dy + h, pad + dx:pad + dx + w]

    def mask(axis: str) -> np.ndarray:
        if axis == "v":
            centre_min = np.minimum.reduce([shifted(d, 0) for d in (-1, 0, 1)])
            centre_max = np.maximum.reduce([shifted(d, 0) for d in (-1, 0, 1)])
            a = np.mean([shifted(-d, 0) for d in range(side[0], side[1] + 1)], axis=0)
            b = np.mean([shifted(d, 0) for d in range(side[0], side[1] + 1)], axis=0)
        else:
            centre_min = np.minimum.reduce([shifted(0, d) for d in (-1, 0, 1)])
            centre_max = np.maximum.reduce([shifted(0, d) for d in (-1, 0, 1)])
            a = np.mean([shifted(0, -d) for d in range(side[0], side[1] + 1)], axis=0)
            b = np.mean([shifted(0, d) for d in range(side[0], side[1] + 1)], axis=0)
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        dark = (lo - centre_min) >= np.maximum(abs_min, rel_min * lo)
        bright = (centre_max - hi) >= np.maximum(abs_min, rel_min * np.maximum(centre_max, 1.0))
        return dark | bright

    return mask("v"), mask("h")


def leg_coverage(mask_v: np.ndarray, mask_h: np.ndarray, leg: Leg, jitter: int = 2) -> float:
    """Share of a leg's pixels that sit on a ridge, allowing ``jitter`` px of positional slack."""
    kind, pos, a, b = leg
    if b <= a:
        return 0.0
    if kind == "v":
        band = mask_v[a:b, max(0, pos - jitter):pos + jitter + 1].any(axis=1)
    else:
        band = mask_h[max(0, pos - jitter):pos + jitter + 1, a:b].any(axis=0)
    return float(band.mean()) if band.size else 0.0


STROKE_BAND = 9          # px sampled either side of a row leg when measuring the stroke's own darkness
STROKE_REL = 0.18        # a stroke pixel is at least this much darker than the local background
STROKE_MIN = 0.6         # share of a same-row leg that must sit on one connected dark stroke


def stroke_cover(gray: np.ndarray, leg: Leg, band: int = STROKE_BAND, rel: float = STROKE_REL) -> float:
    """Share of a horizontal leg whose own pixel is darker than the art around it.

    :func:`ridge_masks` answers "is there *a* line here", and it says yes to a bright
    diagonal highlight crossing the gap as readily as to an arrow (paladin Retribution
    r5c1-c2 is exactly that, and its head energy alone does not rule it out). A
    prerequisite arrow, by contrast, physically connects the two cells with an unlit -
    that is, dark - stroke: every hover in the footage is at rank 0, so no arrow in any
    median is the gold "satisfied" variant. Measured over the twelve same-row candidates
    of the nine classes: 1.00 and 0.78 for the two real arrows, 0.06 or less for every
    piece of art that survived the head test.

    Vertical legs return 1.0 - straight arrows are judged by ``HEAD_MIN`` alone, which
    separates them cleanly, and this test is not calibrated for them.
    """
    kind, pos, a, b = leg
    if kind != "h" or b <= a:
        return 1.0 if kind != "h" else 0.0
    y0, y1 = max(0, pos - band), min(gray.shape[0], pos + band + 1)
    strip = gray[y0:y1, a:b].astype(np.float32)
    if strip.size == 0 or pos - y0 >= strip.shape[0]:
        return 0.0
    bg = np.median(strip, axis=0)
    line = strip[pos - y0]
    return float((line <= bg - rel * np.maximum(bg, 1.0)).mean())


def energy_profile(lap: np.ndarray, leg: Leg, half: int = HEAD_HALF) -> np.ndarray:
    """Mean |Laplacian| in a band of ``2 * half + 1`` px across the line, at every position along a leg."""
    kind, pos, a, b = leg
    if kind == "v":
        return lap[a:b, max(0, pos - half):pos + half + 1].mean(axis=1) if b > a else np.zeros(0)
    return lap[max(0, pos - half):pos + half + 1, a:b].mean(axis=0) if b > a else np.zeros(0)


def _window(prof: np.ndarray, window: int = HEAD_WINDOW, skip: int = HEAD_SKIP) -> int:
    """End window that never overlaps the other end: at most half of the path between the cell borders."""
    return max(1, min(window, (prof.size - 2 * skip) // 2))


def _end_score(prof: np.ndarray, high: bool, window: int = HEAD_WINDOW, skip: int = HEAD_SKIP, top: int = 3) -> float:
    """Mean of the ``top`` highest values in the ``window`` px next to one end (``skip`` px of cell border dropped)."""
    if prof.size <= 2 * skip:
        return 0.0
    window = _window(prof, window, skip)
    core = prof[skip:prof.size - skip]
    part = core[-window:] if high else core[:window]
    if part.size == 0:
        return 0.0
    return float(np.sort(part)[-top:].mean())


def end_energies(lap: np.ndarray, legs: list[Leg], tail_high: bool, head_high: bool) -> tuple[float, float, float]:
    """(tail, mid, head) edge energy of a path, from a |Laplacian| map of the frame.

    The arrow texture is a bevelled stroke (bright core, dark outline) ending in a small
    filled triangle, so the arrowhead is the one place along the path with dense sharp
    edges in a 9 px band; the plain stroke and the tree art (smooth gradients) score far
    lower (measured: heads 11-22, stroke 8-12, art in the gaps 2-8). Legs are stored with
    increasing coordinates; ``tail_high`` / ``head_high`` say whether the required
    talent's edge is at the high end of the first leg and the dependent's at the high end
    of the last leg. ``head`` and ``tail`` are :func:`_end_score` of the ``HEAD_WINDOW``
    px next to the respective cell (``HEAD_SKIP`` px of the cell's own border dropped;
    the window shrinks so the two ends never overlap on a short path), ``mid`` the median
    over the rest of the path (0 when the path is too short to have a middle). Legs must
    run from cell border to cell border (``templates(..., margin=0)``).
    """
    profs = [energy_profile(lap, leg) for leg in legs]
    tail = _end_score(profs[0], tail_high)
    head = _end_score(profs[-1], head_high)
    inner: list[float] = []
    for i, prof in enumerate(profs):
        core = prof[HEAD_SKIP:max(HEAD_SKIP, prof.size - HEAD_SKIP)]
        win = _window(prof)
        if i == 0:
            core = core[win:] if not tail_high else core[:max(0, core.size - win)]
        if i == len(profs) - 1:
            core = core[:max(0, core.size - win)] if head_high else core[win:]
        inner.extend(core.tolist())
    mid = float(np.median(inner)) if inner else 0.0
    return tail, mid, head


def laplacian(gray: np.ndarray) -> np.ndarray:
    return np.abs(cv2.Laplacian(gray.astype(np.float32), cv2.CV_32F, ksize=1))


# --------------------------------------------------------------------------- path templates


def _centre(r: Rect) -> tuple[int, int]:
    return r[0] + r[2] // 2, r[1] + r[3] // 2


def templates(cells: dict[Key, Rect], a: Key, b: Key, margin: int = LEG_MARGIN) -> list[tuple[str, list[Leg], bool, bool]]:
    """Candidate paths from cell ``a`` (required) to ``b`` (dependent) in the same tree.

    Returns ``(shape, legs, tail_high, head_high)``; legs are stored with increasing
    coordinates and the two flags tell :func:`end_energies` at which end of the first / last
    leg the required talent / the arrowhead sits.
    Shapes: ``straight`` (same column), ``row`` (same row), ``L-top`` (along the required
    talent's row, then down), ``L-bottom`` (down from the required talent, then along the
    dependent's row). A path is offered only when no cell sits on it.
    """
    (ta, ra, ca), (tb, rb, cb) = a, b
    if ta != tb or a == b:
        return []
    ax, ay, aw, ah = cells[a]
    bx, by, bw, bh = cells[b]
    acx, acy = _centre(cells[a])
    bcx, bcy = _centre(cells[b])
    occ = cells.__contains__
    out: list[tuple[str, list[Leg], bool, bool]] = []
    if ca == cb and rb > ra:
        if not any(occ((ta, r, ca)) for r in range(ra + 1, rb)):
            x = (acx + bcx) // 2
            out.append(("straight", [("v", x, ay + ah + margin, by - margin)], False, True))
    elif rb == ra and cb != ca:
        if not any(occ((ta, ra, c)) for c in range(min(ca, cb) + 1, max(ca, cb))):
            y = (acy + bcy) // 2
            if cb > ca:
                out.append(("row", [("h", y, ax + aw + margin, bx - margin)], False, True))
            else:
                out.append(("row", [("h", y, bx + bw + margin, ax - margin)], True, False))
    elif rb > ra and cb != ca:
        if not any(occ((ta, ra, c)) for c in range(min(ca, cb) + 1, max(ca, cb))) and \
           not any(occ((ta, r, cb)) for r in range(ra, rb)):
            h_leg: Leg = ("h", acy, ax + aw + margin, bcx) if cb > ca else ("h", acy, bcx, ax - margin)
            out.append(("L-top", [h_leg, ("v", bcx, acy, by - margin)], cb < ca, True))
        if not any(occ((ta, r, ca)) for r in range(ra + 1, rb + 1)) and \
           not any(occ((ta, rb, c)) for c in range(min(ca, cb) + 1, max(ca, cb))):
            v_leg: Leg = ("v", acx, ay + ah + margin, bcy)
            if cb > ca:
                out.append(("L-bottom", [v_leg, ("h", bcy, acx, bx - margin)], False, True))
            else:
                out.append(("L-bottom", [v_leg, ("h", bcy, bx + bw + margin, acx)], False, False))
    return out


def pairs(cells: dict[Key, Rect]) -> list[tuple[Key, Key]]:
    """Ordered (required, dependent) cell pairs worth testing: same tree, dependent not above."""
    keys = sorted(cells)
    out = []
    for a in keys:
        for b in keys:
            if a[0] != b[0] or a == b:
                continue
            drow, dcol = b[1] - a[1], b[2] - a[2]
            if drow < 0 or drow > MAX_ROW_SPAN or abs(dcol) > MAX_COL_SPAN:
                continue
            if drow == 0 and dcol < 0:
                continue      # same-row pairs are tested once; the arrowhead decides the direction
            out.append((a, b))
    return out


# --------------------------------------------------------------------------- detection


def detect_frame(gray: np.ndarray, cells: dict[Key, Rect], min_cover: float = LEG_MIN_COVER) -> list[dict]:
    """Arrows visible in one background frame.

    One entry per (required, dependent, shape) whose every leg is covered at least
    ``min_cover``: ``cover`` (length-weighted), ``legs`` (per-leg coverage), ``tail`` and
    ``head`` edge energies (:func:`end_energies`), and for a same-row path ``stroke``
    (:func:`stroke_cover`). Same-row arrows point at the end with the stronger edge energy.
    The arrowhead itself is judged in :func:`detect_class` after voting.
    """
    mask_v, mask_h = ridge_masks(gray)
    lap = laplacian(gray)
    found = []
    for a, b in pairs(cells):
        full = templates(cells, a, b, margin=0)      # same shapes, legs running border to border
        for (shape, legs, tail_high, head_high), (_, legs_full, _, _) in zip(templates(cells, a, b), full):
            covers = [leg_coverage(mask_v, mask_h, leg) for leg in legs]
            if min(covers) < min_cover:
                continue
            lengths = [max(1, leg[3] - leg[2]) for leg in legs]
            cover = float(sum(c * n for c, n in zip(covers, lengths)) / sum(lengths))
            tail, mid, head = end_energies(lap, legs_full, tail_high, head_high)
            src, dst, ambiguous, stroke = a, b, False, 1.0
            if shape == "row":
                stroke = stroke_cover(gray, legs_full[0])
                if tail > head:
                    src, dst, tail, head = b, a, head, tail   # the arrowhead sits at the left cell
                ambiguous = head < ROW_MIN_RATIO * tail
            found.append({"from": src, "to": dst, "shape": shape, "cover": round(cover, 3),
                          "legs": [round(c, 3) for c in covers], "tail": round(tail, 1), "mid": round(mid, 1),
                          "head": round(head, 1), "stroke": round(stroke, 3), "ambiguous": ambiguous,
                          "path": [list(leg) for leg in legs]})
    return found


def detect_class(calibs: list[dict], cells: dict[Key, Rect], min_cover: float = LEG_MIN_COVER) -> list[dict]:
    """Run :func:`detect_frame` on every calibration median and vote.

    An arrow is kept when it is seen in more than half of the medians (or in the only
    one) and the median of its per-frame head energies reaches ``HEAD_MIN`` (``HEAD_MIN_ROW``
    for a horizontal one, whose head is a smaller shape): a dark line of the tree art
    between two cells has no arrowhead. A same-row path must additionally sit on a dark
    stroke (``stroke_cover`` >= ``STROKE_MIN``), which is what tells an arrow from the
    bright art diagonals that cross a gap. ``segments`` lists the per-median
    coverage; ``confidence`` is the mean coverage times the share of medians that saw it,
    capped at 0.7 when the arrowhead is weak (below ``HEAD_GOOD`` or not ``HEAD_GAIN`` x
    the stroke's energy) and at 0.5 for a same-row arrow whose direction could not be read.
    """
    seen: dict[tuple[Key, Key, str], list[tuple[str, dict]]] = defaultdict(list)
    for d in calibs:
        img = cv2.imread(str(d["_median_path"]))
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        for hit in detect_frame(gray, cells, min_cover):
            seen[(hit["from"], hit["to"], hit["shape"])].append((d["segment_id"], hit))
    n = len(calibs)
    out = []
    for (src, dst, shape), hits in sorted(seen.items()):
        if len(hits) * 2 <= n and n > 1:
            continue
        covers = [h["cover"] for _, h in hits]
        head = float(np.median([h["head"] for _, h in hits]))
        mid = float(np.median([h["mid"] for _, h in hits]))
        tail = float(np.median([h["tail"] for _, h in hits]))
        if head < (HEAD_MIN_ROW if shape == "row" else HEAD_MIN):
            continue
        stroke = float(np.median([h.get("stroke", 1.0) for _, h in hits]))
        if shape == "row" and stroke < STROKE_MIN:
            continue
        conf = float(np.mean(covers)) * (len(hits) / n)
        if head < HEAD_GOOD or (mid > 0 and head < HEAD_GAIN * mid):
            conf = min(conf, 0.7)
        ambiguous = sum(1 for _, h in hits if h["ambiguous"]) * 2 > len(hits)
        if ambiguous:
            conf = min(conf, 0.5)
        out.append({"from": list(src), "to": list(dst), "shape": shape, "confidence": round(conf, 3),
                    "head_energy": round(head, 1), "mid_energy": round(mid, 1), "tail_energy": round(tail, 1),
                    "stroke": round(stroke, 3),
                    "ambiguous": ambiguous, "path": hits[0][1]["path"],
                    "segments": {sid: h["cover"] for sid, h in hits}})
    return resolve_overlaps(out)


def resolve_overlaps(arrows: list[dict]) -> list[dict]:
    """Drop an L-shaped reading whose vertical leg merely re-uses a straight arrow's line.

    An ``L-bottom`` leaves the required cell downwards and an ``L-top`` enters the
    dependent cell from above; when a straight arrow already leaves that same cell
    (``L-bottom``) or ends at that same cell (``L-top``), the L's vertical leg is that
    arrow's stroke and its short horizontal leg is art next to it (seen: a fern behind
    the warlock Demonology tree).
    """
    starts = {tuple(x["from"]) for x in arrows if x["shape"] == "straight"}
    ends = {tuple(x["to"]) for x in arrows if x["shape"] == "straight"}
    kept = []
    for x in arrows:
        if x["shape"] == "L-bottom" and tuple(x["from"]) in starts:
            continue
        if x["shape"] == "L-top" and tuple(x["to"]) in ends:
            continue
        kept.append(x)
    return kept


# --------------------------------------------------------------------------- overlay


def draw_overlay(img: np.ndarray, cells: dict[Key, Rect], arrows: list[dict]) -> np.ndarray:
    """Cells in grey, detected arrows in green (tail dot) with a magenta ring at the head."""
    out = img.copy()
    for (x, y, w, h) in cells.values():
        cv2.rectangle(out, (x, y), (x + w, y + h), (160, 160, 160), 1)
    for a in arrows:
        colour = (0, 255, 0) if a["confidence"] >= 0.8 else (0, 200, 255)
        for kind, pos, p0, p1 in a["path"]:
            if kind == "v":
                cv2.line(out, (pos, p0), (pos, p1), colour, 1)
            else:
                cv2.line(out, (p0, pos), (p1, pos), colour, 1)
        bx, by, bw, bh = cells[tuple(a["to"])]  # type: ignore[index]
        ax, ay, aw, ah = cells[tuple(a["from"])]  # type: ignore[index]
        cv2.circle(out, (bx + bw // 2, by + bh // 2), 6, (255, 0, 255), 1)
        cv2.circle(out, (ax + aw // 2, ay + ah // 2), 3, colour, -1)
    return out

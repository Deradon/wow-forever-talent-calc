"""Cursor-centric recovery of talent hovers that the tooltip detector never recorded.

Independent of stage 4's tooltip blob detector: the mouse pointer (the WoW
gauntlet, a white glove with a dark outline, about 21x18 px) is located on
every frame by normalised template matching inside the work ROI; the
fingertip (template top-left) is the hotspot and the calibrated cell rects say
which talent icon it is over. Consecutive frames on one cell form a *dwell*.

For every cell the pipeline reports as never hovered, the frames 100-400 ms
after each cursor arrival are decoded again at native resolution and a
generous region around the cell (cell +/- 400 px horizontally, +/- 300 px
vertically, clipped to the work ROI) is saved for inspection. A tooltip
present in that region while the cursor sits on the cell belongs to that
cell (the game shows exactly one tooltip, for the hovered button), so the
recovery does not depend on where the box was anchored or clamped.

Outputs (all under ``work/cursor/``):
``cursor_template.png`` / ``cursor_template_mask.png``   the pointer template
``tracks/<segment_id>.json``      per-frame cursor position, score and cell
``dwells/<segment_id>.json``      dwell events (cell, first/last frame, ms)
``candidates/<class>/<cell>/``    generous crops + full frame of the best candidate
``candidates/<class>.json``       per candidate frame: cursor, dark-box and
                                  stage-4 detector results
``recovered/<class>/<cell>.png``  tight tooltip crop where one was found
``recovered.json``                hovers-JSON shaped records of the recovered cells
``report.md``                     per missing cell: verdict, dwell time, evidence

Run from ``pipeline/``: ``uv run scripts/cursor_recover.py --class mage``.
Reads ``work/frags/`` through ``FragmentCache`` (one request at a time when a
fragment is not cached; the parallel decoders only ever read cached files).
"""

from __future__ import annotations

import json
import multiprocessing as mp
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import typer

from wowtalents import fragments as fr  # noqa: E402
from wowtalents import ui  # noqa: E402
from wowtalents.fsio import write_json_atomic, write_text_atomic  # noqa: E402

app = typer.Typer(add_completion=False)

SEGMENTS_JSON = fr.PIPELINE_DIR.parent / "data" / "extracted" / "segments.json"
CALIB_DIR = fr.WORK / "calib"
HOVERS_DIR = fr.WORK / "hovers"
CURSOR_DIR = fr.WORK / "cursor"
FPS = 60

# Pointer template source: mage segment 6, fragment 14810, frame 30, where the
# glove sits alone on the dark tree background under Arcane r1c2.
TEMPLATE_SOURCE = {"segment": "06-mage-14760", "sq": 14810, "offset": 30, "region": (560, 245, 640, 305)}
TEMPLATE_MARGIN = 2
MATCH_MIN = 0.75            # TM_CCOEFF_NORMED; true pointer >= 0.84 on 95 % of frames, false peaks <= 0.69
CELL_MARGIN = 3             # px around the icon rect that still counts as "on the cell"
DWELL_MAX_GAP = 3           # frames without a detection that do not end a dwell
LEAD_MS, SPAN_MS = 100, 400 # candidate window after the cursor arrived
CANDIDATE_STEP = 3          # keep every N-th 60 fps frame of the window
EVENTS_PER_CELL = 6         # longest dwells per missing cell that get candidate crops
GENEROUS = (400, 300)       # half-extents of the inspection crop around a cell
DARK_LEVEL = 12             # tooltip interior is gray 1-7; the darkest tree art starts at ~7-12
DARK_BOX_FILL = 0.6         # fraction of the bbox covered by one near-black component
DARK_BOX_W = (110, 300)     # tooltip interior width (border excluded; 177-228 px seen)
DARK_BOX_H = 45
TEXT_LEVEL = 110            # tooltip text is white/gold/grey (> 110); black art has no such rows
TEXT_ROWS_MIN = 6           # rows containing >= 3 bright pixels (a name line alone gives ~9)


# --------------------------------------------------------------------------- pure helpers


def tree_slugs(calib: dict) -> dict[int, str]:
    """Same rule as stage 4: slug of the visible tree name, ``treeN`` as fallback."""
    names = calib.get("trees_visible") or []
    return {t: (ui.slug(names[t - 1]) if len(names) >= t else f"tree{t}") for t in (1, 2, 3)}


def cell_id(slugs: dict[int, str], key: tuple[int, int, int]) -> str:
    tree, row, col = key
    return f"{slugs[tree]}-r{row}c{col}"


def parse_cell_id(cid: str) -> tuple[str, int, int]:
    """``fire-r3c2`` -> (``fire``, 3, 2)."""
    stem, _, rc = cid.rpartition("-")
    r, c = rc[1:].split("c")
    return stem, int(r), int(c)


def find_cursor(gray_roi: np.ndarray, template: np.ndarray, mask: np.ndarray | None = None) -> tuple[float, int, int]:
    """Best match ``(score, x, y)`` of the pointer template inside ``gray_roi``.

    (x, y) is the template's top-left in ROI coordinates; the fingertip
    hotspot is at ``TEMPLATE_MARGIN - 1`` px from that corner. With ``mask``
    (the glove's own pixels) only the glove is correlated, so the pointer is
    still found over the bright, green-framed row-1 icons, where the unmasked
    template (dark surroundings included) drops to the false-match floor.
    """
    if mask is not None:
        res = cv2.matchTemplate(gray_roi, template, cv2.TM_CCOEFF_NORMED, mask=mask)
        res = np.nan_to_num(res, nan=0.0, posinf=0.0, neginf=0.0)
    else:
        res = cv2.matchTemplate(gray_roi, template, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(res)
    return float(mx), int(loc[0]), int(loc[1])


def hotspot(x: int, y: int, margin: int = TEMPLATE_MARGIN) -> tuple[int, int]:
    """Fingertip of a template placed at (x, y): the glove points up-left."""
    return (x + max(margin - 1, 0), y + max(margin - 1, 0))


@dataclass
class Dwell:
    cell: tuple[int, int, int]
    first: int          # frame index (segment-relative, in decoded frames)
    last: int
    frames: int         # frames with a detection on the cell
    t_first: float
    t_last: float

    @property
    def ms(self) -> float:
        return round((self.t_last - self.t_first) * 1000.0, 1)

    def to_json(self, fps: float) -> dict:
        return {"cell": list(self.cell), "first": self.first, "last": self.last, "frames": self.frames,
                "t_first": round(self.t_first, 3), "t_last": round(self.t_last, 3),
                "ms": round(self.ms + 1000.0 / fps, 1)}


def dwell_events(track: list[tuple[float, tuple[int, int, int] | None]], max_gap: int = DWELL_MAX_GAP) -> list[Dwell]:
    """Group a frame-ordered ``[(t, cell_or_None), ...]`` into dwells per cell.

    A dwell continues across up to ``max_gap`` consecutive frames without a
    detection (pointer briefly lost, e.g. over a bright icon) but ends as soon
    as another cell is seen. Single-frame dwells are kept: the caller decides
    what is long enough.
    """
    out: list[Dwell] = []
    cur: Dwell | None = None
    gap = 0
    for i, (t, cell) in enumerate(track):
        if cell is None:
            if cur is not None:
                gap += 1
                if gap > max_gap:
                    out.append(cur)
                    cur, gap = None, 0
            continue
        if cur is not None and cell == cur.cell:
            cur.last, cur.t_last, cur.frames = i, t, cur.frames + 1
            gap = 0
            continue
        if cur is not None:
            out.append(cur)
        cur = Dwell(cell, i, i, 1, t, t)
        gap = 0
    if cur is not None:
        out.append(cur)
    return out


def candidate_indices(first: int, fps: float, lead_ms: int = LEAD_MS, span_ms: int = SPAN_MS,
                      step: int = CANDIDATE_STEP, n_frames: int | None = None) -> list[int]:
    """Frame indices ``lead_ms .. span_ms`` after arrival at ``first``, every ``step``."""
    a = first + int(round(lead_ms * fps / 1000.0))
    b = first + int(round(span_ms * fps / 1000.0))
    idx = list(range(a, b + 1, step))
    if n_frames is not None:
        idx = [i for i in idx if i < n_frames]
    return idx


def generous_rect(cell: ui.Cell, half: tuple[int, int] = GENEROUS,
                  clip: tuple[int, int, int, int] = ui.WORK_ROI) -> tuple[int, int, int, int]:
    """(x0, y0, x1, y1) around ``cell`` clipped to ``clip`` (exclusive upper bounds)."""
    hx, hy = half
    cx, cy = cell.centre
    x0, y0 = max(clip[0], int(cx - hx)), max(clip[1], int(cy - hy))
    x1, y1 = min(clip[2], int(cx + hx)), min(clip[3], int(cy + hy))
    return x0, y0, x1, y1


def dark_boxes(bgr: np.ndarray, level: int = DARK_LEVEL, w_range: tuple[int, int] = DARK_BOX_W,
               h_min: int = DARK_BOX_H, min_fill: float = DARK_BOX_FILL) -> list[tuple[int, int, int, int]]:
    """Tooltip-shaped near-black rectangles in ``bgr`` (crop coordinates), largest first.

    Independent of any background model: the tooltip interior is the only
    large, nearly pure-black (gray < 12) rectangle in the talent window; the
    tree art bottoms out around gray 7-12 and is never rectangular. The text
    lines float inside black margins, so one connected component covers the
    interior around them (fill >= 0.8 measured) with no morphology at all;
    a closing must not be used, it bridges the 2 px border into dark art
    outside. The returned box is the interior; the border is 2-3 px outside.
    A box must also hold text (bright rows), which separates it from the
    rectangular black patches of the tree art (Arcane, bottom left).
    """
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    dark = (g < level).astype(np.uint8) * 255
    n, _, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if not (w_range[0] <= w <= w_range[1] and h >= h_min):
            continue
        if area / float(w * h) < min_fill:
            continue
        if text_rows(g[y:y + h, x:x + w]) < TEXT_ROWS_MIN:
            continue
        out.append((x, y, w, h))
    out.sort(key=lambda b: b[2] * b[3], reverse=True)
    return out


def text_rows(gray: np.ndarray, level: int = TEXT_LEVEL, min_px: int = 3) -> int:
    """Number of rows with at least ``min_px`` bright pixels (text lines of a tooltip)."""
    if gray.size == 0:
        return 0
    return int(((gray > level).sum(axis=1) >= min_px).sum())


def diff_fill(frame: np.ndarray, bg: np.ndarray, box: tuple[int, int, int, int], thresh: int = 25) -> float:
    """Fraction of ``box`` that stage 4's absdiff mask lights up (< ~0.45 means the box is
    invisible to the diff detector: a black tooltip over near-black tree art)."""
    x, y, w, h = box
    d = cv2.absdiff(frame[y:y + h, x:x + w], bg[y:y + h, x:x + w])
    return float((cv2.cvtColor(d, cv2.COLOR_BGR2GRAY) > thresh).mean()) if w > 0 and h > 0 else 0.0


def consensus_missing(hovers: list[dict], calibs: list[dict]) -> tuple[list[str], dict[str, int]]:
    """Cells in the majority of calibrations that no segment's hovers recorded.

    Returns ``(missing ids, id -> count of calibrations containing the cell)``.
    Ids use the tree slugs of each calibration (stage 4 naming).
    """
    counts: dict[str, int] = {}
    for calib in calibs:
        slugs = tree_slugs(calib)
        for c in calib["cells"]:
            counts[cell_id(slugs, (c["tree"], c["row"], c["col"]))] = counts.get(
                cell_id(slugs, (c["tree"], c["row"], c["col"])), 0) + 1
    seen = {h["id"] for hv in hovers for h in hv.get("hovers", [])}
    need = len(calibs) / 2.0
    missing = sorted(cid for cid, n in counts.items() if n > need and cid not in seen)
    return missing, counts


def hovered_in_segment(hov: dict) -> set[tuple[int, int, int]]:
    """Cells any run (kept or superseded) of a stage-4 result resolved to."""
    keys: set[tuple[int, int, int]] = set()
    for r in hov.get("all_runs", []) or hov.get("hovers", []):
        if r.get("cell"):
            keys.add(tuple(r["cell"]))
    for r in hov.get("hovers", []):
        if r.get("cell"):
            keys.add(tuple(r["cell"]))
    return keys


# --------------------------------------------------------------------------- template


def build_template(frame: np.ndarray, bg: np.ndarray, region: tuple[int, int, int, int],
                   margin: int = TEMPLATE_MARGIN, thresh: int = 25) -> tuple[np.ndarray, np.ndarray]:
    """Pointer template (BGR) and mask from the largest diff blob inside ``region``."""
    x0, y0, x1, y1 = region
    d = cv2.cvtColor(cv2.absdiff(frame, bg), cv2.COLOR_BGR2GRAY)
    m = (d[y0:y1, x0:x1] > thresh).astype(np.uint8) * 255
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n < 2:
        raise ValueError("no diff blob in the template region")
    i = max(range(1, n), key=lambda k: stats[k, 4])
    x, y, w, h, _ = (int(v) for v in stats[i])
    tpl = frame[y0 + y - margin:y0 + y + h + margin, x0 + x - margin:x0 + x + w + margin].copy()
    mask = np.zeros(tpl.shape[:2], np.uint8)
    mask[margin:margin + h, margin:margin + w] = (lab[y:y + h, x:x + w] == i).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    return tpl, mask


def load_template(cursor_dir: Path = CURSOR_DIR, cache: fr.FragmentCache | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Grey pointer template and its mask; built from ``TEMPLATE_SOURCE`` on first use."""
    p = cursor_dir / "cursor_template.png"
    pm = cursor_dir / "cursor_template_mask.png"
    if not p.exists() or not pm.exists():
        src = TEMPLATE_SOURCE
        bg = cv2.imread(str(CALIB_DIR / f"{src['segment']}-median.png"))
        cache = cache or fr.FragmentCache()
        frame = None
        for off, f in ui.decode_frames(cache.get(src["sq"])):
            if off == src["offset"]:
                frame = f.copy()
                break
        if frame is None or bg is None:
            raise FileNotFoundError("template source frame or median not available")
        tpl, mask = build_template(frame, bg, src["region"])
        ui.ensure_dir(cursor_dir)
        cv2.imwrite(str(p), tpl)
        cv2.imwrite(str(pm), mask)
    tpl = cv2.imread(str(p))
    return cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY), cv2.imread(str(pm), cv2.IMREAD_GRAYSCALE)


# --------------------------------------------------------------------------- tracking (parallel over fragments)

_W: dict = {}


def _init_worker(template: tuple[np.ndarray, np.ndarray], cells_json: list[dict], every: int, cache_dir: str):
    _W["tpl"], _W["mask"] = template
    _W["cells"] = [ui.Cell.from_json(c) for c in cells_json]
    _W["every"] = every
    _W["cache_dir"] = Path(cache_dir)


def _track_fragment(sq: int) -> list[list]:
    """Per decoded frame: [sq, offset, score, hx, hy, tree, row, col] (cell fields -1 when off-grid)."""
    data = (_W["cache_dir"] / f"{sq}.bin").read_bytes()
    x0, y0, x1, y1 = ui.WORK_ROI
    rows = []
    for off, frame in ui.decode_frames(data, every=_W["every"]):
        g = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        score, x, y = find_cursor(g, _W["tpl"], _W["mask"])
        hx, hy = hotspot(x + x0, y + y0)
        key = (-1, -1, -1)
        if score >= MATCH_MIN:
            c = ui.cell_at_point(_W["cells"], (hx, hy), margin=CELL_MARGIN)
            if c is not None:
                key = (c.tree, c.row, c.col)
        rows.append([sq, off, round(score, 3), hx, hy, *key])
    return rows


def track_segment(sid: str, seg: dict, calib: dict, template: tuple[np.ndarray, np.ndarray], every: int, workers: int,
                  cache: fr.FragmentCache, out: Path) -> dict:
    t0, t1 = seg["t_start"], seg["t_end"]
    for sq in range(t0, t1):          # serial: one network request at a time, usually all cached
        cache.get(sq)
    wall = time.time()
    with mp.Pool(workers, initializer=_init_worker,
                 initargs=(template, calib["cells"], every, str(cache.cache_dir))) as pool:
        per_sq = pool.map(_track_fragment, range(t0, t1), chunksize=2)
    frames = [row for rows in per_sq for row in rows]
    scores = np.array([r[2] for r in frames]) if frames else np.zeros(1)
    on_cell = sum(1 for r in frames if r[5] > 0)
    result = {
        "segment_id": sid, "class": seg["class"], "t_start": t0, "t_end": t1, "every": every,
        "fps": FPS / every, "frames": len(frames), "frames_on_cell": on_cell,
        "score_pct": {str(p): round(float(np.percentile(scores, p)), 3) for p in (5, 25, 50, 75, 95)},
        "match_min": MATCH_MIN, "cell_margin": CELL_MARGIN, "matcher": "ccoeff_normed_masked",
        "columns": ["sq", "offset", "score", "hx", "hy", "tree", "row", "col"],
        "track": frames, "seconds": round(time.time() - wall, 1),
    }
    ui.ensure_dir(out)
    write_text_atomic(out / f"{sid}.json", json.dumps(result, separators=(",", ":")) + "\n")
    return result


def track_to_events(tr: dict) -> list[Dwell]:
    fps = tr["fps"]
    seq = []
    for sq, off, score, hx, hy, tree, row, col in tr["track"]:
        seq.append((sq + off / FPS, (tree, row, col) if tree > 0 else None))
    return dwell_events(seq)


# --------------------------------------------------------------------------- candidates


@dataclass
class Candidate:
    cell_id: str
    key: tuple[int, int, int]
    event: dict
    frame_index: int
    sq: int
    offset: int
    t: float
    cursor_cell: tuple[int, int, int] | None
    cursor_xy: tuple[int, int]
    cursor_score: float
    generous: tuple[int, int, int, int]
    dark_boxes: list[tuple[int, int, int, int]] = field(default_factory=list)   # full-frame coords
    detector: dict = field(default_factory=dict)
    sharpness: float = 0.0
    files: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {"cell_id": self.cell_id, "cell": list(self.key), "event": self.event,
                "frame_index": self.frame_index, "sq": self.sq, "offset": self.offset, "t": round(self.t, 3),
                "cursor_cell": list(self.cursor_cell) if self.cursor_cell else None,
                "cursor_xy": list(self.cursor_xy), "cursor_score": self.cursor_score,
                "generous": list(self.generous), "dark_boxes": [list(b) for b in self.dark_boxes],
                "detector": self.detector, "sharpness": round(self.sharpness, 1), "files": self.files}


def stage4_view(frame: np.ndarray, bg: np.ndarray, cells: list[ui.Cell]) -> dict:
    """What stage 4's detector would make of this frame (diagnostic only)."""
    mask = ui.diff_mask(frame, bg)
    rejected: list[tuple[int, int, int, int]] = []
    bbox, small = ui.find_tooltip(mask, rejected=rejected)
    if bbox is None:
        return {"bbox": None, "rejected": [list(b) for b in rejected][:6], "reason": "no tooltip-shaped blob"}
    x, y, w, h = bbox
    dark = ui.darkness(frame[max(0, y - 2):y + h + 2, max(0, x - 2):x + w + 2])
    cell, dist, method = ui.cell_for_tooltip(cells, bbox)
    return {"bbox": list(bbox), "darkness": round(dark, 2), "dark_ok": dark >= ui.TOOLTIP_MIN_DARK,
            "cell": [cell.tree, cell.row, cell.col] if cell else None, "dist": round(dist, 1), "method": method,
            "rejected": [list(b) for b in rejected][:6]}


def collect_candidates(cls: str, sid: str, tr: dict, calib: dict, missing_keys: dict[str, tuple[int, int, int]],
                       cache: fr.FragmentCache, out_dir: Path, every: int) -> list[Candidate]:
    """Decode the candidate frames of every dwell on a missing cell and save the crops."""
    cells = [ui.Cell.from_json(c) for c in calib["cells"]]
    by_key = {(c.tree, c.row, c.col): c for c in cells}
    bg = cv2.imread(str(CALIB_DIR / calib["files"]["median"]))
    track = tr["track"]
    fps = tr["fps"]
    events = track_to_events(tr)
    wanted: dict[int, list[tuple[str, Dwell]]] = {}       # frame index -> (cell_id, dwell)
    per_cell: dict[str, list[Dwell]] = {}
    for cid, key in missing_keys.items():
        evs = sorted((e for e in events if e.cell == key), key=lambda e: (-e.frames, e.first))[:EVENTS_PER_CELL]
        per_cell[cid] = evs
        for e in evs:
            for i in candidate_indices(e.first, fps, n_frames=len(track)):
                wanted.setdefault(i, []).append((cid, e))
    cands: list[Candidate] = []
    if not wanted:
        return cands
    by_sq: dict[int, list[int]] = {}
    for i in wanted:
        by_sq.setdefault(track[i][0], []).append(i)
    frame_of_offset: dict[tuple[int, int], int] = {(r[0], r[1]): i for i, r in enumerate(track)}
    for sq in sorted(by_sq):
        need = {track[i][1] for i in by_sq[sq]}
        for off, frame in ui.decode_frames(cache.get(sq), every=every):
            if off not in need:
                continue
            i = frame_of_offset[(sq, off)]
            row = track[i]
            cur_key = (row[5], row[6], row[7]) if row[5] > 0 else None
            for cid, e in wanted[i]:
                c = by_key[e.cell]
                gx0, gy0, gx1, gy1 = generous_rect(c)
                crop = frame[gy0:gy1, gx0:gx1]
                boxes = [(gx0 + x, gy0 + y, w, h) for x, y, w, h in dark_boxes(crop)]
                cand = Candidate(cid, e.cell, e.to_json(fps), i, sq, off, sq + off / FPS, cur_key,
                                 (row[3], row[4]), row[2], (gx0, gy0, gx1, gy1), boxes,
                                 stage4_view(frame, bg, cells))
                if boxes:
                    bx, by, bw, bh = boxes[0]
                    cand.sharpness = ui.sharpness(frame[by:by + bh, bx:bx + bw])
                    cand.detector["diff_fill_in_box"] = round(diff_fill(frame, bg, boxes[0]), 2)
                d = ui.ensure_dir(out_dir / cls / cid)
                stem = f"{sid}-{sq}-{off:02d}"
                cv2.imwrite(str(d / f"{stem}.png"), crop)
                cand.files["crop"] = f"candidates/{cls}/{cid}/{stem}.png"
                cand.files["_frame"] = frame.copy()      # dropped after the best is chosen
                cands.append(cand)
    # keep only one full frame per cell: the sharpest tooltip with the cursor on the cell,
    # else the longest dwell's mid frame
    for cid in per_cell:
        mine = [k for k in cands if k.cell_id == cid]
        if not mine:
            continue
        good = [k for k in mine if k.dark_boxes and k.cursor_cell == k.key]
        best = max(good, key=lambda k: k.sharpness) if good else max(
            mine, key=lambda k: (k.event["frames"], -abs(k.frame_index - k.event["first"] - 12)))
        d = out_dir / cls / cid
        fn = f"{sid}-{best.sq}-{best.offset:02d}-full.png"
        cv2.imwrite(str(d / fn), best.files["_frame"])
        best.files["full"] = f"candidates/{cls}/{cid}/{fn}"
        for k in mine:
            k.files.pop("_frame", None)
    return cands


# --------------------------------------------------------------------------- recovery + report


def median_tooltip(calib: dict, calib_dir: Path = CALIB_DIR) -> dict | None:
    """A tooltip baked into the segment's median background (the pointer rested on one cell
    while stage 3 sampled its frames). Stage 4 then sees a permanent tooltip-shaped diff blob
    wherever the real tooltip is not, and ``find_tooltip`` keeps the largest blob."""
    bg = cv2.imread(str(calib_dir / calib["files"]["median"]))
    if bg is None:
        return None
    x0, y0, x1, y1 = ui.WORK_ROI
    boxes = dark_boxes(bg[y0:y1, x0:x1])
    if not boxes:
        return None
    x, y, w, h = boxes[0]
    box = (x + x0, y + y0, w, h)
    cells = [ui.Cell.from_json(c) for c in calib["cells"]]
    cell, dist, method = ui.cell_for_tooltip(cells, box)
    return {"bbox": list(box), "cell": [cell.tree, cell.row, cell.col] if cell else None, "method": method}


def tight_crop(frame: np.ndarray, box: tuple[int, int, int, int], margin: int = 4) -> np.ndarray:
    x, y, w, h = box
    return frame[max(0, y - margin):y + h + margin, max(0, x - margin):x + w + margin].copy()


def candidate_segment(k: Candidate) -> str:
    """Segment id encoded in the candidate's crop file name (``<sid>-<sq>-<off>.png``)."""
    return k.files["crop"].split("/")[-1].rsplit("-", 2)[0]


def choose_recoveries(cands: list[Candidate]) -> dict[str, dict[str, Candidate]]:
    """Per cell and segment: the sharpest candidate with a dark box while the cursor sits on
    the cell. Segments are kept apart because later passes may show points already spent
    (rank > 0); stage 5's rank-0 ordering can then choose between them."""
    best: dict[str, dict[str, Candidate]] = {}
    for k in cands:
        if not k.dark_boxes or k.cursor_cell != k.key:
            continue
        sid = candidate_segment(k)
        prev = best.setdefault(k.cell_id, {}).get(sid)
        if prev is None or k.sharpness > prev.sharpness:
            best[k.cell_id][sid] = k
    return best


def primary_segment(per_segment: dict[str, Candidate]) -> str:
    """The earliest segment (by id prefix) with a recovery: the first hover pass of a class
    is the one with unspent points."""
    return min(per_segment)


def verdict_for(cid: str, events: list[Dwell], cands: list[Candidate], recovered: bool, fps: float) -> dict:
    """One of: tooltip present / cursor never over the cell / cursor passed too fast (longest
    dwell shorter than the candidate lead, so no tooltip could be attributed) / cursor dwelt,
    no tooltip rendered (the pointer sat on the cell >= LEAD_MS and no tooltip box was visible
    in the generous crop at any candidate frame)."""
    total_ms = round(sum(e.ms + 1000.0 / fps for e in events), 1)
    longest = max((e.ms + 1000.0 / fps for e in events), default=0.0)
    on_cell = [k for k in cands if k.cursor_cell == k.key]
    other_tip = any(k.dark_boxes for k in cands if k.cursor_cell != k.key)
    if recovered:
        v = "tooltip present"
    elif not events:
        v = "cursor never over the cell"
    elif longest < LEAD_MS or not on_cell:
        v = f"cursor passed too fast (< {LEAD_MS} ms), no tooltip for it"
        if other_tip:
            v += "; another cell's tooltip in the crop"
    else:
        v = "cursor dwelt, no tooltip rendered"
    return {"verdict": v, "events": len(events), "dwell_ms_total": total_ms, "dwell_ms_longest": round(longest, 1)}


def hover_record(k: Candidate, sid: str, calib: dict, page: str | None, cls: str, cell: ui.Cell,
                 png_rel: str, crop: np.ndarray) -> dict:
    """A record shaped like ``work/hovers/<segment>.json`` ``hovers[]`` entries."""
    tree, row, col = k.key
    bx, by, bw, bh = k.dark_boxes[0]
    det = k.detector
    tooltip_cell, dist, method = ui.cell_for_tooltip([ui.Cell.from_json(c) for c in calib["cells"]], (bx, by, bw, bh))
    return {
        "run": None, "t": round(k.t, 3), "sq": k.sq, "offset": k.offset,
        "frames": k.event["frames"], "t_first": k.event["t_first"], "t_last": k.event["t_last"],
        "bbox": [bx - 4, by - 4, bw + 8, bh + 8], "cell": [tree, row, col],
        "sharpness": round(k.sharpness, 1), "hash": f"{ui.dhash(crop):016x}",
        "dist": round(dist, 1), "method": f"cursor ({method}: {[tooltip_cell.tree, tooltip_cell.row, tooltip_cell.col] if tooltip_cell else None})",
        "cursor_cell": list(k.cursor_cell) if k.cursor_cell else None,
        "darkness": round(ui.darkness(crop), 2),
        "cut_off": bx + bw >= ui.WORK_ROI[2] - 1 or by + bh >= ui.WORK_ROI[3] - 1,
        "superseded": 0, "id": k.cell_id, "tree": tree, "tree_name": k.cell_id.rpartition("-")[0],
        "row": row, "col": col, "page": page, "cell_rect": list(cell.rect),
        "segment_id": sid, "class": cls, "dwell_ms": k.event["ms"],
        "stage4": {kk: det.get(kk) for kk in ("bbox", "cell", "method", "dist", "darkness", "reason", "diff_fill_in_box")},
        "files": {"tooltip": png_rel, "candidate": k.files.get("crop"), "frame": k.files.get("full")},
    }


def validate_against_stage4(tr: dict, hov: dict | None, min_frames: int = 6) -> dict:
    """How the cursor track agrees with stage 4's own runs (recall check of the tracker and a
    list of runs whose cell the pointer contradicts).

    For every stage-4 run of >= ``min_frames`` frames: the fraction of track frames inside
    ``t_first..t_last`` whose cell is the run's cell (``coverage``), and whether the pointer
    was detected but sat on another cell for most of the run (``disagree``: the run's cell
    was resolved from a blob that is not this hover's tooltip, e.g. one baked into the median).
    """
    out = {"runs": 0, "coverage_mean": None, "by_row": {}, "disagree": []}
    if not hov:
        return out
    by_sq: dict[int, list[list]] = {}
    for r in tr["track"]:
        by_sq.setdefault(r[0], []).append(r)
    covs: list[float] = []
    rows: dict[int, list[float]] = {}
    for run in hov.get("all_runs", []):
        if not run.get("cell") or run.get("frames", 0) < min_frames:
            continue
        a, b, key = run["t_first"], run["t_last"], tuple(run["cell"])
        frames = [r for sq in range(int(a), int(b) + 1) for r in by_sq.get(sq, [])
                  if a - 1e-6 <= r[0] + r[1] / FPS <= b + 1e-6]
        if not frames:
            continue
        on = sum(1 for r in frames if (r[5], r[6], r[7]) == key) / len(frames)
        detected = sum(1 for r in frames if r[5] > 0) / len(frames)
        covs.append(on)
        rows.setdefault(key[1], []).append(on)
        if detected >= 0.8 and on <= 0.2:
            other = {}
            for r in frames:
                if r[5] > 0:
                    other[(r[5], r[6], r[7])] = other.get((r[5], r[6], r[7]), 0) + 1
            top = max(other, key=other.get)
            out["disagree"].append({"run": run.get("run"), "t": run["t"], "stage4_cell": list(key),
                                    "stage4_id": run.get("id"), "cursor_cell": list(top),
                                    "cursor_share": round(other[top] / len(frames), 2), "frames": run["frames"]})
    out["runs"] = len(covs)
    out["coverage_mean"] = round(float(np.mean(covs)), 2) if covs else None
    out["by_row"] = {str(r): {"runs": len(v), "coverage": round(float(np.mean(v)), 2)} for r, v in sorted(rows.items())}
    return out


def class_segments(segs: list[dict], cls: str) -> list[tuple[int, dict]]:
    return [(i, s) for i, s in enumerate(segs, 1) if s["class"] == cls]


def load_json(p: Path) -> dict | None:
    return json.loads(p.read_text()) if p.exists() else None


@app.command()
def main(
    cls: str = typer.Option(..., "--class", help="class name as in segments.json (e.g. mage)"),
    every: int = typer.Option(1, help="decode every N-th frame (1 = 60 fps, 2 = 30 fps)"),
    workers: int = typer.Option(max(1, min(8, (mp.cpu_count() or 2) - 2)), help="decoder processes"),
    segment: list[str] = typer.Option(None, "--segment", help="restrict to these segment keys"),
    force: bool = typer.Option(False, help="re-track segments that already have a track file"),
    cursor_dir: Path = typer.Option(CURSOR_DIR),
):
    """Track the pointer through every segment of --class, then collect and classify candidate
    frames for the class's missing cells; write tracks, dwells, candidates, recovered crops and the report."""
    segs = json.loads(SEGMENTS_JSON.read_text())
    pairs = class_segments(segs, cls)
    if segment:
        keep = {ui.find_segment(segs, k)[0] for k in segment}
        pairs = [(i, s) for i, s in pairs if i in keep]
    if not pairs:
        typer.echo(f"no segments for class {cls!r}", err=True)
        raise typer.Exit(code=2)
    ui.ensure_dir(cursor_dir)
    cache = fr.FragmentCache()
    if cache.health_warning:
        typer.echo(cache.health_warning)
    template = load_template(cursor_dir, cache)
    typer.echo(f"template {template[0].shape[1]}x{template[0].shape[0]} px (masked), match >= {MATCH_MIN}")

    # 1. tracks + dwells
    tracks: dict[str, dict] = {}
    calibs: dict[str, dict] = {}
    for idx, seg in pairs:
        sid = ui.segment_id(seg, idx)
        calib = load_json(CALIB_DIR / f"{sid}.json")
        if calib is None:
            typer.echo(f"{sid}: no calibration, skipped")
            continue
        calibs[sid] = calib
        tp = cursor_dir / "tracks" / f"{sid}.json"
        tr = None if force else load_json(tp)
        if tr is None or tr.get("every") != every or tr.get("matcher") != "ccoeff_normed_masked":
            tr = track_segment(sid, seg, calib, template, every, workers, cache, cursor_dir / "tracks")
            typer.echo(f"{sid}: {tr['frames']} frames, {tr['frames_on_cell']} on a cell, "
                       f"score p5/p50 {tr['score_pct']['5']}/{tr['score_pct']['50']}, {tr['seconds']}s")
        else:
            typer.echo(f"{sid}: track cached ({tr['frames']} frames)")
        tracks[sid] = tr
        events = track_to_events(tr)
        ui.ensure_dir(cursor_dir / "dwells")
        write_json_atomic(cursor_dir / "dwells" / f"{sid}.json",
                          {"segment_id": sid, "fps": tr["fps"], "events": [e.to_json(tr["fps"]) for e in events]}, indent=1)

    # 2. missing cells (consensus over the class's stage-4 results and calibrations)
    hovers = {sid: load_json(HOVERS_DIR / f"{sid}.json") for sid in tracks}
    missing, _ = consensus_missing([h for h in hovers.values() if h], list(calibs.values()))
    typer.echo(f"{cls}: {len(missing)} missing cells: {', '.join(missing) or '-'}")

    # 3. candidates per segment
    cand_dir = cursor_dir / "candidates"
    all_cands: list[Candidate] = []
    events_by_cell: dict[str, list[Dwell]] = {cid: [] for cid in missing}
    dwelt_unrecorded: list[dict] = []
    for sid, tr in tracks.items():
        calib = calibs[sid]
        slugs = tree_slugs(calib)
        keys = {cell_id(slugs, (c["tree"], c["row"], c["col"])): (c["tree"], c["row"], c["col"]) for c in calib["cells"]}
        missing_keys = {cid: keys[cid] for cid in missing if cid in keys}
        events = track_to_events(tr)
        for cid, key in missing_keys.items():
            events_by_cell[cid].extend(e for e in events if e.cell == key)
        # 4. dwells (>= 200 ms) on cells stage 4 never resolved in this segment
        recorded = hovered_in_segment(hovers[sid]) if hovers[sid] else set()
        agg: dict[tuple[int, int, int], list[Dwell]] = {}
        for e in events:
            agg.setdefault(e.cell, []).append(e)
        for key, evs in sorted(agg.items()):
            longest = max(e.ms + 1000.0 / tr["fps"] for e in evs)
            if key not in recorded and longest >= 200:
                dwelt_unrecorded.append({"segment_id": sid, "cell": list(key), "id": cell_id(slugs, key),
                                         "events": len(evs), "dwell_ms_longest": round(longest, 1),
                                         "t": round(max(evs, key=lambda e: e.frames).t_first, 3),
                                         "missing_overall": cell_id(slugs, key) in missing})
        cands = collect_candidates(cls, sid, tr, calib, missing_keys, cache, cand_dir, every)
        typer.echo(f"{sid}: {len(cands)} candidate frames for {len({k.cell_id for k in cands})} cells")
        all_cands.extend(cands)
    ui.ensure_dir(cand_dir)
    write_json_atomic(cand_dir / f"{cls}.json", [k.to_json() for k in all_cands], indent=1)

    # 5. recovery: cursor on the cell + a dark box in the generous crop
    best = choose_recoveries(all_cands)
    rec_dir = ui.ensure_dir(cursor_dir / "recovered" / cls)
    recovered_all = load_json(cursor_dir / "recovered.json") or {}
    class_block = {"class": cls, "segments": list(tracks), "page": next(iter(calibs.values())).get("page") if calibs else None,
                   "hovers": [], "missing_cells": [], "cells_dwelt_unrecorded": dwelt_unrecorded, "files": {}}
    for old in rec_dir.glob("*.png"):
        old.unlink()
    for cid, per_seg in sorted(best.items()):
        primary = primary_segment(per_seg)
        for sid, k in sorted(per_seg.items()):
            calib = calibs[sid]
            cell = next(ui.Cell.from_json(c) for c in calib["cells"] if (c["tree"], c["row"], c["col"]) == k.key)
            frame = cv2.imread(str(cursor_dir / k.files["full"])) if "full" in k.files else None
            if frame is None:
                # the best frame is not the one whose full frame was saved: decode it again
                for off, f in ui.decode_frames(cache.get(k.sq), every=every):
                    if off == k.offset:
                        frame = f.copy()
                        break
            crop = tight_crop(frame, k.dark_boxes[0])
            name = cid if sid == primary else f"{cid}.{sid}"
            cv2.imwrite(str(rec_dir / f"{name}.png"), crop)
            cv2.imwrite(str(rec_dir / f"{name}-icon.png"),
                        cv2.imread(str(CALIB_DIR / calib["files"]["median"]))[cell.y:cell.y + cell.h, cell.x:cell.x + cell.w])
            rec = hover_record(k, sid, calib, calib.get("page"), cls, cell, f"recovered/{cls}/{name}.png", crop)
            rec["files"]["icon"] = f"recovered/{cls}/{name}-icon.png"
            rec["primary"] = sid == primary
            class_block["hovers"].append(rec)
    class_block["missing_cells"] = [cid for cid in missing if cid not in best]
    recovered_all[cls] = class_block
    write_json_atomic(cursor_dir / "recovered.json", recovered_all)

    # 6. report rows (one per missing cell), merged into report.md per class
    fps = FPS / every
    rows = []
    for cid in missing:
        evs = events_by_cell.get(cid, [])
        cands = [k for k in all_cands if k.cell_id == cid]
        v = verdict_for(cid, evs, cands, cid in best, fps)
        ev_best = max(evs, key=lambda e: e.frames) if evs else None
        evidence = (f"recovered/{cls}/{cid}.png" if cid in best else
                    (cands[0].files.get("full") or cands[0].files.get("crop")) if cands else "-")
        if cid in best and len(best[cid]) > 1:
            evidence += " (+" + ", ".join(sid for sid in sorted(best[cid]) if sid != primary_segment(best[cid])) + ")"
        rows.append({"cell": cid, **v, "segments": sorted({candidate_segment(k) for k in cands}),
                     "t_longest": fr.hms(ev_best.t_first) if ev_best else "-", "evidence": evidence,
                     "stage4": stage4_summary(best[cid][primary_segment(best[cid])]) if cid in best else "-"})
    medians = {sid: median_tooltip(calibs[sid]) for sid in tracks}
    validation = {sid: validate_against_stage4(tr, hovers[sid]) for sid, tr in tracks.items()}
    recovered_all[cls]["validation"] = validation
    recovered_all[cls]["median_tooltips"] = medians
    write_json_atomic(cursor_dir / "recovered.json", recovered_all)
    write_report(cursor_dir / "report.md", cls, rows, dwelt_unrecorded, tracks, medians, validation)
    n_rec = sum(1 for r in rows if r["verdict"] == "tooltip present")
    n_never = sum(1 for r in rows if r["verdict"].startswith("cursor never"))
    typer.echo(f"{cls}: {n_rec} recovered, {len(rows) - n_rec - n_never} cursor-dwelt-but-no-tooltip, "
               f"{n_never} cursor-never-there; {len(dwelt_unrecorded)} dwelt-but-unrecorded cells; "
               f"report {cursor_dir / 'report.md'}")


REPORT_HEAD = """# Cursor-track recovery report

Independent of the tooltip detector: the pointer is template-matched on every
decoded frame, the calibrated cell rects say which icon it is over, and for
every cell stage 4 never recorded the frames 100-400 ms after each arrival
are inspected for a tooltip box. Paths are relative to `pipeline/work/cursor/`.
Verdicts: *tooltip present* (recovered crop written), *cursor dwelt, no
tooltip rendered*, *cursor passed too fast* (dwell shorter than the 100 ms lead), *cursor never over
the cell*. Regenerated per class by `scripts/cursor_recover.py --class <name>`.
"""


def stage4_summary(k: Candidate) -> str:
    """One phrase on why stage 4 did not record this frame's tooltip."""
    d = k.detector
    fill = d.get("diff_fill_in_box")
    real = k.dark_boxes[0]
    if d.get("bbox") is None:
        why = f"no tooltip-shaped diff blob (diff fill inside the real box {fill})"
        if d.get("rejected"):
            why += f", blobs rejected by shape: {d['rejected'][:2]}"
        return why
    bx, by = d["bbox"][0], d["bbox"][1]
    same = abs(bx - real[0]) <= 8 and abs(by - real[1]) <= 8
    if same:
        return f"blob found -> cell {d.get('cell')} ({d.get('method')}, dark {d.get('darkness')})"
    return f"took another blob {d['bbox']} -> cell {d.get('cell')} instead (real box {list(real)}, diff fill {fill})"


def write_report(path: Path, cls: str, rows: list[dict], dwelt: list[dict], tracks: dict[str, dict],
                 medians: dict[str, dict | None] | None = None, validation: dict[str, dict] | None = None) -> None:
    marker = f"\n## {cls}\n"
    text = path.read_text() if path.exists() else REPORT_HEAD
    # replace this class's section, keep the others
    head, _, rest = text.partition(marker)
    if rest:
        nxt = rest.find("\n## ")
        rest = rest[nxt:] if nxt >= 0 else ""
    lines = [marker.rstrip("\n"), ""]
    lines.append("Segments tracked: " + ", ".join(
        f"{sid} ({tr['frames']} frames at {tr['fps']:.0f} fps, pointer on a cell in {tr['frames_on_cell']}, "
        f"score p5 {tr['score_pct']['5']})" for sid, tr in tracks.items()))
    bad = {sid: m for sid, m in (medians or {}).items() if m}
    if bad:
        lines += ["", "Medians with a tooltip baked in (stage 4 sees a permanent fake blob there and keeps the "
                  "largest blob per frame): " + "; ".join(
                      f"{sid} box {m['bbox']} anchored at cell {m['cell']}" for sid, m in bad.items())]
    lines += ["", "| cell | verdict | events | dwell total (ms) | longest (ms) | at | evidence | stage-4 view of the best frame |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['cell']} | {r['verdict']} | {r['events']} | {r['dwell_ms_total']} | {r['dwell_ms_longest']} | "
                     f"{r['t_longest']} | {r['evidence']} | {r['stage4']} |")
    lines += ["", "Cells the pointer dwelt on for >= 200 ms that the segment's stage-4 result has no run for "
              "(kept or superseded); `overall` marks cells missing from every segment:", ""]
    if dwelt:
        lines += ["| segment | cell | events | longest (ms) | at | overall missing |", "|---|---|---|---|---|---|"]
        for d in dwelt:
            lines.append(f"| {d['segment_id']} | {d['id']} | {d['events']} | {d['dwell_ms_longest']} | "
                         f"{fr.hms(d['t'])} | {'yes' if d['missing_overall'] else ''} |")
    else:
        lines.append("none")
    if validation:
        lines += ["", "Tracker check against stage 4's own runs (>= 6 frames): share of each run's frames on which "
                  "the pointer was on the run's cell, per segment and per row:", ""]
        for sid, v in validation.items():
            if not v["runs"]:
                continue
            by_row = ", ".join(f"r{r} {d['coverage']} ({d['runs']})" for r, d in v["by_row"].items())
            lines.append(f"- {sid}: {v['runs']} runs, mean {v['coverage_mean']}; {by_row}")
        dis = [(sid, d) for sid, v in validation.items() for d in v["disagree"]]
        if dis:
            lines += ["", "Stage-4 runs whose cell the pointer contradicts (pointer detected on >= 80 % of the run's "
                      "frames, on another cell): the run's cell came from a blob that is not this hover's tooltip.", "",
                      "| segment | at | stage-4 cell | frames | pointer on | share |", "|---|---|---|---|---|---|"]
            for sid, d in dis:
                lines.append(f"| {sid} | {fr.hms(d['t'])} | {d['stage4_id'] or d['stage4_cell']} | {d['frames']} | "
                             f"{d['cursor_cell']} | {d['cursor_share']} |")
    section = "\n".join(lines) + "\n"
    write_text_atomic(path, head + section + rest)


if __name__ == "__main__":
    app()

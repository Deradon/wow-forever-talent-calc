"""Talent-window geometry and the pure helpers behind stages 3 and 4.

Everything positional is OpenCV/numpy; nothing here talks to the network or
the VLM. Pixel priors come from ``docs/handover/2026-09-13-pipeline-probe.md``
(1920x1080 direct capture, window fixed at x 410-1510, y 30-678).
"""

from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

FRAME_W, FRAME_H = 1920, 1080
ICON = 36
PITCH = 54

# Prior grid geometry (left edges of the 4 columns per tree, top edges of the 7 rows).
PRIOR_COLS: dict[int, list[int]] = {
    1: [500, 552, 608, 664],
    2: [860, 912, 966, 1020],
    3: [1226, 1278, 1332, 1388],
}
PRIOR_ROWS: list[int] = [236, 292, 346, 400, 454, 510, 562]

# Named regions (x0, y0, x1, y1), exclusive upper bounds.
WINDOW = (410, 30, 1510, 678)
WORK_ROI = (400, 0, 1780, 720)          # window plus room for tooltips past the right frame edge
HEADER = (410, 30, 1510, 150)           # title, tabs, search, unspent talents
TREE_NAME_ROWS = (165, 210)             # y-range of the tree icon + name line
TREE_X = {1: (445, 770), 2: (780, 1140), 3: (1150, 1490)}
TAB_PRIMARY = (478, 80, 608, 100)
TAB_SECONDARY = (615, 80, 742, 100)
# Regions that never hold talent UI but move a lot; masked out of every diff.
MASKS = [
    (0, 590, 480, 960),      # webcam overlay + chat text
    (0, 950, 1920, 1080),    # bottom action bars
    (1820, 0, 1920, 1080),   # right-hand action bars
    (1640, 0, 1920, 260),    # minimap
    (860, 0, 1060, 30),      # "Time Left: NN min" demo timer above the window
]

TOOLTIP_W_RANGE = (120, 270)            # up to ~228 px wide, narrower for short text (177 seen), height by content
TOOLTIP_H_MIN = 50
TOOLTIP_MIN_DARK = 0.65                 # fraction of near-black pixels inside a real tooltip (>= 0.69 measured; junk <= 0.59)
TOOLTIP_DARK_LEVEL = 40
TOOLTIP_BLACK_LEVEL = 16                # the tooltip body is grey 1-3 in the stream; dark UI panels rarely go below 16


@dataclass
class Cell:
    tree: int
    row: int          # 1-based
    col: int          # 1-based
    x: int
    y: int
    w: int
    h: int
    score: float = 0.0

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)

    @property
    def top_right(self) -> tuple[int, int]:
        return (self.x + self.w, self.y)

    @property
    def centre(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)

    def to_json(self) -> dict:
        return {"tree": self.tree, "row": self.row, "col": self.col,
                "x": self.x, "y": self.y, "w": self.w, "h": self.h,
                "score": round(float(self.score), 2)}

    @classmethod
    def from_json(cls, d: dict) -> "Cell":
        return cls(d["tree"], d["row"], d["col"], d["x"], d["y"], d["w"], d["h"], d.get("score", 0.0))


# --------------------------------------------------------------------------- segments


def segment_id(seg: dict, index: int) -> str:
    """Stable id for a row of ``data/extracted/segments.json`` (1-based index)."""
    return f"{index:02d}-{seg['class']}-{seg['t_start']}"


def find_segment(segments: list[dict], key: str) -> tuple[int, dict]:
    """Resolve ``key`` (1-based index, id, or t_start seconds) to (index, segment)."""
    for i, seg in enumerate(segments, 1):
        if key in (str(i), segment_id(seg, i), str(seg["t_start"])):
            return i, seg
    raise KeyError(f"no segment matching {key!r}")


# --------------------------------------------------------------------------- decoding


def decode_frames(data: bytes, every: int = 1, width: int = FRAME_W, height: int = FRAME_H,
                  max_frames: int | None = None) -> Iterator[tuple[int, np.ndarray]]:
    """Stream ``(frame_offset, bgr)`` from one fragment via ffmpeg rawvideo.

    ``every`` keeps every N-th decoded frame (``select=not(mod(n,N))``); the
    offset yielded is the original frame index inside the fragment. Frames are
    yielded one at a time so the caller never holds a whole fragment in RAM.
    """
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", "pipe:0"]
    if every > 1:
        cmd += ["-vf", f"select=not(mod(n\\,{every}))", "-vsync", "0"]
    if max_frames:
        cmd += ["-frames:v", str(max_frames)]
    cmd += ["-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert proc.stdin is not None and proc.stdout is not None

    def feed(stdin=proc.stdin):
        try:
            stdin.write(data)
            stdin.close()
        except (BrokenPipeError, OSError):
            pass

    # Feed stdin from a thread: ffmpeg blocks on its (6 MB per frame) stdout
    # pipe long before it has consumed a whole fragment, so a serial
    # write-then-read deadlocks.
    threading.Thread(target=feed, daemon=True).start()
    nbytes = width * height * 3
    k = 0
    while True:
        buf = proc.stdout.read(nbytes)
        if len(buf) < nbytes:
            break
        yield k * every, np.frombuffer(buf, np.uint8).reshape(height, width, 3)
        k += 1
    proc.stdout.close()
    proc.wait()


# --------------------------------------------------------------------------- grid


def gradient_maps(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    g = gray.astype(np.float32)
    return (np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)),
            np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)))


def square_score(gx: np.ndarray, gy: np.ndarray, x: int, y: int, s: int) -> float:
    """Weakest of the four edge responses of an ``s`` px square outline at (x, y).

    Using the minimum means all four edges must exist, which rejects the
    background art's long vertical lines and the prerequisite arrows.
    """
    if x < 1 or y < 1 or x + s + 1 > gx.shape[1] or y + s + 1 > gx.shape[0]:
        return 0.0
    left = gx[y:y + s, x - 1:x + 2].sum()
    right = gx[y:y + s, x + s - 2:x + s + 1].sum()
    top = gy[y - 1:y + 2, x:x + s].sum()
    bottom = gy[y + s - 2:y + s + 1, x:x + s].sum()
    return float(min(left, right, top, bottom)) / 1000.0


def refine_cell(gx: np.ndarray, gy: np.ndarray, x0: int, y0: int, search: int = 5,
                sizes: tuple[int, ...] = (35, 36, 37)) -> tuple[float, int, int, int]:
    """Best (score, x, y, size) of a square outline near the prior (x0, y0)."""
    best = (0.0, x0, y0, ICON)
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            for s in sizes:
                v = square_score(gx, gy, x0 + dx, y0 + dy, s)
                if v > best[0]:
                    best = (v, x0 + dx, y0 + dy, s)
    return best


def detect_grid(background: np.ndarray, threshold: float = 3.5,
                cols: dict[int, list[int]] | None = None, rows: list[int] | None = None,
                normalize: bool = True) -> list[Cell]:
    """Locate the icon cells of all three trees on a clean (median) frame.

    Starts from the prior column/row edges and keeps a position when a 35-37 px
    square outline scores above ``threshold`` (present cells scored >= 4.0 and
    empty positions <= 2.7 on the reference frame).
    """
    cols = cols or PRIOR_COLS
    rows = rows or PRIOR_ROWS
    gray = cv2.cvtColor(background, cv2.COLOR_BGR2GRAY)
    gx, gy = gradient_maps(gray)
    cells: list[Cell] = []
    for tree, xs in cols.items():
        for r, y0 in enumerate(rows, 1):
            for c, x0 in enumerate(xs, 1):
                score, x, y, s = refine_cell(gx, gy, x0, y0)
                if score >= threshold:
                    if normalize and s != ICON:
                        # the outline scores best at 35-37 px because of the rim's
                        # anti-aliasing; record a fixed 36 px box centred on it
                        x -= (ICON - s) // 2
                        y -= (ICON - s) // 2
                        s = ICON
                    cells.append(Cell(tree, r, c, x, y, s, s, score))
    return cells


def tab_state(frame: np.ndarray) -> dict:
    """Which page tab is lit: the active tab is gold (saturated), the other grey."""
    out = {}
    for name, (x0, y0, x1, y1) in (("Primary", TAB_PRIMARY), ("Secondary", TAB_SECONDARY)):
        hsv = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
        out[name] = {"saturation": round(float(hsv[..., 1].mean()), 1),
                     "value": round(float(hsv[..., 2].mean()), 1)}
    active = max(out, key=lambda k: out[k]["saturation"])
    return {"active": active, "tabs": out}


# --------------------------------------------------------------------------- cell lookup


def nearest_cell(cells: list[Cell], point: tuple[float, float], max_dist: float = 40.0) -> tuple[Cell | None, float]:
    """Cell whose top-right corner is nearest ``point`` (a tooltip's bottom-left).

    Returns ``(None, dist)`` when nothing is within ``max_dist`` px. Ties on
    distance are broken by the smaller x-offset, because the tooltip's left
    edge is pinned to the cell's right edge even when the game clamps the box
    vertically to keep it on screen.
    """
    px, py = point
    best: Cell | None = None
    best_key = (max_dist, 0.0)
    for cell in cells:
        cx, cy = cell.top_right
        d = float(np.hypot(cx - px, cy - py))
        key = (d, abs(cx - px))
        if key < best_key:
            best, best_key = cell, key
    return best, best_key[0]


def cell_for_tooltip(cells: list[Cell], bbox: tuple[int, int, int, int],
                     max_dist: float = 40.0, x_tol: float = 8.0) -> tuple[Cell | None, float, str]:
    """Hovered cell for a tooltip ``bbox`` (x, y, w, h).

    First by corner distance; if that fails (the box was clamped vertically),
    fall back to the column whose right edge matches the tooltip's left edge
    and the row whose top is nearest the tooltip's bottom. Returns
    ``(cell, distance, method)``.
    """
    x, y, w, h = bbox
    anchor = (x, y + h)
    cell, d = nearest_cell(cells, anchor, max_dist)
    if cell is not None:
        return cell, d, "corner"
    column = [c for c in cells if abs(c.top_right[0] - x) <= x_tol]
    if not column:
        return None, d, "none"
    cell = min(column, key=lambda c: abs(c.y - anchor[1]))
    return cell, float(abs(cell.y - anchor[1])), "column"


def cell_at_point(cells: list[Cell], point: tuple[float, float], margin: int = 6) -> Cell | None:
    """Cell whose rect (grown by ``margin``) contains ``point`` (cursor cross-check)."""
    px, py = point
    for c in cells:
        if c.x - margin <= px < c.x + c.w + margin and c.y - margin <= py < c.y + c.h + margin:
            return c
    return None


# --------------------------------------------------------------------------- tooltip detection


def diff_mask(frame: np.ndarray, background: np.ndarray, thresh: int = 25,
              roi: tuple[int, int, int, int] = WORK_ROI, masks: list[tuple[int, int, int, int]] = MASKS) -> np.ndarray:
    """Binary change mask inside ``roi`` (full-frame sized), overlays masked out."""
    x0, y0, x1, y1 = roi
    d = cv2.absdiff(frame[y0:y1, x0:x1], background[y0:y1, x0:x1])
    d = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    m = np.zeros(frame.shape[:2], np.uint8)
    m[y0:y1, x0:x1] = (d > thresh).astype(np.uint8) * 255
    for mx0, my0, mx1, my1 in masks:
        m[my0:my1, mx0:mx1] = 0
    return m


def trim_bbox(mask: np.ndarray, bbox: tuple[int, int, int, int], fill: float = 0.45) -> tuple[int, int, int, int]:
    """Shrink ``bbox`` to the rows/columns of ``mask`` that are mostly filled.

    A tooltip is a solid rectangle in the diff mask; a cursor or icon highlight
    touching it adds sparse rows/columns at the edges, which this trims away.
    """
    x, y, w, h = bbox
    sub = mask[y:y + h, x:x + w] > 0
    if sub.size == 0:
        return bbox
    rows = sub.mean(1)
    cols = sub.mean(0)
    ys = np.where(rows >= fill)[0]
    xs = np.where(cols >= fill)[0]
    if len(ys) == 0 or len(xs) == 0:
        return bbox
    return (x + int(xs[0]), y + int(ys[0]), int(xs[-1] - xs[0] + 1), int(ys[-1] - ys[0] + 1))


def _longest_dark_run(frac: np.ndarray, min_frac: float, smooth: int = 9) -> tuple[int, int] | None:
    """[start, end) of the longest run where the ``smooth``-px moving average of ``frac`` >= ``min_frac``."""
    raw = frac
    if smooth > 1 and len(frac) >= smooth:
        frac = np.convolve(frac, np.ones(smooth) / smooth, mode="same")
    ok = frac >= min_frac
    best = None
    start = None
    for i, v in enumerate(list(ok) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if best is None or i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    if best is None:
        return None
    # the smoothing widened the run by up to smooth // 2: tighten on the raw profile
    a, b = best
    while a < b - 1 and raw[a] < min_frac:
        a += 1
    while b > a + 1 and raw[b - 1] < min_frac:
        b -= 1
    return (a, b)


def dark_trim(gray: np.ndarray, bbox: tuple[int, int, int, int], row_level: int = TOOLTIP_BLACK_LEVEL,
              row_frac: float = 0.35, col_level: int = TOOLTIP_DARK_LEVEL, col_frac: float = 0.4) -> tuple[int, int, int, int]:
    """Shrink ``bbox`` to the dark rows/columns of the *frame*.

    The diff mask cannot separate a tooltip from a changed region glued to it
    (a ghost tooltip left in the median, the game world past the window's
    right edge, a brightened or dark panel), but the tooltip's own body can.
    Rows are kept from the outermost ones whose fraction of pixels below
    ``row_level`` (truly black: a dark panel under the box is not) reaches
    ``row_frac``; rows through dense text are only about half black, so the
    bar is low and the outermost rule never cuts a box through its text.
    Columns take the longest run whose 9 px smoothed fraction below
    ``col_level`` reaches ``col_frac`` (text is left-aligned, so the left
    columns are the least black and need the softer level), which drops an
    appendage on either side. The box is returned unchanged when nothing
    qualifies; :func:`border_snap` then settles the exact edges.
    """
    x, y, w, h = bbox
    g = gray[y:y + h, x:x + w]
    if g.size == 0:
        return bbox
    ys = np.where((g < row_level).mean(1) >= row_frac)[0]
    if len(ys) == 0:
        return bbox
    y0, y1 = int(ys[0]), int(ys[-1]) + 1
    cols = _longest_dark_run((g[y0:y1] < col_level).mean(0), col_frac)
    if cols is None:
        return bbox
    x0, x1 = cols
    return (x + x0, y + y0, x1 - x0, y1 - y0)


BORDER_MIN_MEAN = 55        # the tooltip's 1 px border line is grey 80-130 in the stream ...
BORDER_UNIFORM = 0.85       # ... and uniform: this share of its pixels lies in 40-220 (a text line has black gaps)


def border_snap(gray: np.ndarray, bbox: tuple[int, int, int, int], search: int = 60, min_size: int = 40,
                level: int = TOOLTIP_BLACK_LEVEL) -> tuple[int, int, int, int]:
    """Snap each edge of ``bbox`` to the tooltip's border line when one is found.

    A border row/column has a mean of at least ``BORDER_MIN_MEAN``, is
    uniformly grey (``BORDER_UNIFORM`` of its pixels in 40-220, which a
    bright text line with black gaps between the glyphs is not), and has a
    black interior neighbour (>= 80 % below ``level``) and a not-black outer
    neighbour (< 70 %). Scanning from the outside inward over at most
    ``search`` px finds the outermost such line, so a dark panel or ghost
    glued to the box is cut off exactly at the border; an edge without a
    border line keeps its trimmed position.
    """
    x, y, w, h = bbox
    H, W = gray.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)

    def black(a: np.ndarray) -> float:
        return float((a < level).mean()) if a.size else 0.0

    def is_border(line: np.ndarray, inner: np.ndarray, outer: np.ndarray | None) -> bool:
        return (line.mean() >= BORDER_MIN_MEAN and ((line >= 40) & (line <= 220)).mean() >= BORDER_UNIFORM
                and black(inner) >= 0.8 and (outer is None or black(outer) < 0.7))

    # bottom
    for yy in range(y1 - 1, max(y0 + min_size, y1 - search) - 1, -1):
        if yy - 1 >= 0 and is_border(gray[yy, x0:x1], gray[yy - 1, x0:x1], gray[yy + 1, x0:x1] if yy + 1 < H else None):
            y1 = yy
            break
    # top
    for yy in range(y0, min(y1 - min_size, y0 + search)):
        if yy + 1 < H and is_border(gray[yy, x0:x1], gray[yy + 1, x0:x1], gray[yy - 1, x0:x1] if yy - 1 >= 0 else None):
            y0 = yy + 1
            break
    # right
    for xx in range(x1 - 1, max(x0 + min_size, x1 - search) - 1, -1):
        if xx - 1 >= 0 and is_border(gray[y0:y1, xx], gray[y0:y1, xx - 1], gray[y0:y1, xx + 1] if xx + 1 < W else None):
            x1 = xx
            break
    # left
    for xx in range(x0, min(x1 - min_size, x0 + search)):
        if xx + 1 < W and is_border(gray[y0:y1, xx], gray[y0:y1, xx + 1], gray[y0:y1, xx - 1] if xx - 1 >= 0 else None):
            x0 = xx + 1
            break
    return (x0, y0, x1 - x0, y1 - y0)


def find_tooltip(mask: np.ndarray, w_range: tuple[int, int] = TOOLTIP_W_RANGE,
                 h_min: int = TOOLTIP_H_MIN, min_area: int = 9000,
                 rejected: list[tuple[int, int, int, int]] | None = None,
                 gray: np.ndarray | None = None, close: int = 7,
                 reasons: list[str] | None = None) -> tuple[tuple[int, int, int, int] | None, list[tuple[int, int, int, int]]]:
    """Largest tooltip-shaped blob in ``mask`` plus the other blobs (cursor candidates).

    Returns ``(bbox or None, small_blobs)`` where bbox is (x, y, w, h). A blob
    is a candidate when its *bounding box* covers ``min_area`` px: over a dark
    panel the tooltip body hardly differs from the median and only the grey
    border and the text are in the mask, so the pixel count of a real tooltip
    can be a third of its box. Each candidate is trimmed on the mask
    (:func:`trim_bbox`) and, when ``gray`` (the frame) is given, on the
    frame's dark core (:func:`dark_trim`, then :func:`border_snap` to the
    tooltip's border line) before the width/height test, and
    only candidates whose crop is at least ``TOOLTIP_MIN_DARK`` near-black
    compete (a large sparse blob of game-world change must not outrank the
    tooltip). Candidates failing a test are appended to ``rejected`` (and a
    short reason to ``reasons``) when given.
    """
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    best = None
    best_area = 0
    small: list[tuple[int, int, int, int]] = []
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if w * h < min_area:
            if 80 <= area <= 3000:
                small.append((x, y, w, h))
            continue
        bb = trim_bbox(mask, (x, y, w, h))
        if gray is not None:
            bb = border_snap(gray, dark_trim(gray, bb))
        bx, by, bw, bh = bb
        why = None
        if not (w_range[0] <= bw <= w_range[1] and bh >= h_min):
            why = "narrow" if bw < w_range[0] else "wide" if bw > w_range[1] else "short"
        elif gray is not None:
            dark = darkness(gray[by:by + bh, bx:bx + bw])
            if dark < TOOLTIP_MIN_DARK:
                why = f"not_dark {dark:.2f}"
        if why is not None:
            if rejected is not None:
                rejected.append(bb)
            if reasons is not None:
                reasons.append(why)
            continue
        if bw * bh > best_area:
            best, best_area = bb, bw * bh
    return best, small


def darkness(crop: np.ndarray, border: int = 4, level: int = TOOLTIP_DARK_LEVEL) -> float:
    """Fraction of near-black pixels inside ``crop`` (border stripped).

    A tooltip is a near-black box with light text; a diff blob that is
    really a dimmed part of the grid (search box, spellbook) is not.
    """
    g = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    inner = g[border:-border, border:-border] if min(g.shape[:2]) > 2 * border + 1 else g
    return float((inner < level).mean()) if inner.size else 0.0


def looks_like_tooltip(crop: np.ndarray, min_dark: float = TOOLTIP_MIN_DARK) -> bool:
    return darkness(crop) >= min_dark


# --------------------------------------------------------------------------- median ghosts


GHOST_MIN_FRAC = 0.1        # a pixel is unstable when it differs from the median in this share of frames
GHOST_MIN_FRAMES = 3
GHOST_BG_LEVEL = 60         # median pixels darker than this can belong to a ghost box (a blend is not fully black)
GHOST_DARK_LEVEL = 16       # "black box" test for ghosts: a tooltip body is grey 1-3, dark panels rarely go below 16
GHOST_TOOLTIP_DARK = 0.45   # a region at least this black (at GHOST_DARK_LEVEL) shows a tooltip
GHOST_FREE_DARK = 0.3       # frames whose region is at most this black are used for the repair
GHOST_MIN_GAIN = 0.15       # a repair must lower the region's blackness by this much to be kept
GHOST_SHAPE = ((100, 340), 40, 6000)   # (w_range, h_min, min bbox area) of a ghost candidate
DONOR_MAX_DIFF = 8.0        # mean |median - donor| over the window (candidate excluded) for the same UI state
DONOR_MAX_DARK = GHOST_FREE_DARK        # the donor's region must not hold a tooltip itself


def blackness(crop: np.ndarray) -> float:
    """:func:`darkness` at ``GHOST_DARK_LEVEL``: separates a tooltip body from a dark UI panel."""
    return darkness(crop, level=GHOST_DARK_LEVEL)


def unstable_mask(frames: list[np.ndarray], bg: np.ndarray, thresh: int = 25,
                  min_frac: float = GHOST_MIN_FRAC, min_frames: int = GHOST_MIN_FRAMES) -> np.ndarray:
    """Pixels that differ from ``bg`` in at least ``max(min_frames, min_frac * n)`` of ``frames``.

    All arrays share one shape (a ROI crop is fine). A tooltip that sat on
    screen for most of the sampled frames wins the median and then differs in
    every frame that does *not* show it, while the real background is stable.
    """
    cnt = np.zeros(bg.shape[:2], np.int32)
    bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
    for f in frames:
        d = cv2.absdiff(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), bg_gray)
        cnt += (d > thresh)
    need = max(min_frames, int(np.ceil(min_frac * len(frames))))
    return ((cnt >= need).astype(np.uint8) * 255)


def _shaped_boxes(mask: np.ndarray, fill: float = 0.45) -> list[tuple[int, int, int, int]]:
    (w_lo, w_hi), h_min, min_area = GHOST_SHAPE
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, _ = (int(v) for v in stats[i])
        if w * h < min_area:
            continue
        bx, by, bw, bh = trim_bbox(mask, (x, y, w, h), fill=fill)
        if w_lo <= bw <= w_hi and bh >= h_min:
            out.append((bx, by, bw, bh))
    return out


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    return ix * iy > 0.5 * min(aw * ah, bw * bh)


def ghost_candidates(bg: np.ndarray, frames: list[np.ndarray], donors: list[np.ndarray] = (),
                     thresh: int = 25) -> list[dict]:
    """Tooltip-shaped boxes where the median ``bg`` may hold a ghost tooltip.

    Two sources, deduplicated on overlap: (1) the difference between ``bg``
    and each donor median (another segment of the same class: the talent
    window is static, so a tooltip-shaped dark difference is a ghost in one
    of the two; kept when ``bg`` is dark there and the donor is not), (2) the
    tooltip-shaped components of the unstable pixels that are dark in ``bg``
    (the only source when no donor exists). Each dict has ``bbox`` and
    ``source``.
    """
    out: list[dict] = []
    bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)

    def add(bbox, source):
        for o in out:
            if _overlaps(o["bbox"], bbox):
                return
        out.append({"bbox": bbox, "source": source})

    for k, donor in enumerate(donors):
        if donor.shape != bg.shape:
            continue
        d = (cv2.absdiff(bg_gray, cv2.cvtColor(donor, cv2.COLOR_BGR2GRAY)) > thresh).astype(np.uint8) * 255
        for x, y, w, h in _shaped_boxes(d):
            if blackness(bg[y:y + h, x:x + w]) >= GHOST_TOOLTIP_DARK and blackness(donor[y:y + h, x:x + w]) <= DONOR_MAX_DARK:
                add((x, y, w, h), f"donor{k}")
    if frames:
        dark_bg = (bg_gray < GHOST_BG_LEVEL).astype(np.uint8) * 255
        cand = cv2.bitwise_and(unstable_mask(frames, bg, thresh=thresh), dark_bg)
        for bbox in _shaped_boxes(cand):
            add(bbox, "frames")
    return out


def ghost_boxes(frames: list[np.ndarray], bg: np.ndarray, donors: list[np.ndarray] = (),
                min_dark: float = GHOST_TOOLTIP_DARK, min_tooltip_frames: int = 2) -> list[dict]:
    """:func:`ghost_candidates` that are a black box in at least ``min_tooltip_frames`` frames.

    Adds ``tooltip_frames`` (frames whose region is at least ``min_dark``
    black, see :func:`blackness`), ``free_frames`` (region at most
    ``GHOST_FREE_DARK`` black: the in-segment repair source, empty when the
    spot was under some tooltip in every frame) and ``median_darkness`` (the
    median's blackness there).
    """
    out = []
    for c in ghost_candidates(bg, frames, donors):
        bx, by, bw, bh = c["bbox"]
        darks = [blackness(f[by:by + bh, bx:bx + bw]) for f in frames]
        tooltip = [k for k, d in enumerate(darks) if d >= min_dark]
        if len(tooltip) < min_tooltip_frames:
            continue
        c.update({"tooltip_frames": tooltip, "free_frames": [k for k, d in enumerate(darks) if d <= GHOST_FREE_DARK],
                  "median_darkness": round(blackness(bg[by:by + bh, bx:bx + bw]), 2)})
        out.append(c)
    return out


def patch_from_donor(bg: np.ndarray, donor: np.ndarray, bbox: tuple[int, int, int, int],
                     window: tuple[int, int, int, int], max_diff: float = DONOR_MAX_DIFF,
                     max_dark: float = DONOR_MAX_DARK) -> tuple[np.ndarray | None, float, float]:
    """Region ``bbox`` of ``donor`` (another segment's median of the same class), if usable.

    The donor is accepted when its window (``bbox`` excluded) matches ours
    within ``max_diff`` mean grey difference (same page, same points spent,
    no dialog) and its own region is not dark. Returns ``(patch or None,
    window_diff, donor_darkness)``.
    """
    x, y, w, h = bbox
    wx0, wy0, wx1, wy1 = window
    a = cv2.cvtColor(bg[wy0:wy1, wx0:wx1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    b = cv2.cvtColor(donor[wy0:wy1, wx0:wx1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    keep = np.ones(a.shape, bool)
    keep[max(0, y - wy0):max(0, y + h - wy0), max(0, x - wx0):max(0, x + w - wx0)] = False
    diff = float(np.abs(a - b)[keep].mean()) if keep.any() else 255.0
    region = donor[y:y + h, x:x + w]
    dark = blackness(region)
    if diff > max_diff or dark > max_dark or region.shape[:2] != (h, w):
        return None, round(diff, 1), round(dark, 2)
    return region.copy(), round(diff, 1), round(dark, 2)


def repair_ghosts(bg: np.ndarray, frames: list[np.ndarray], donors: list[np.ndarray] = (),
                  window: tuple[int, int, int, int] | None = None, boxes: list[dict] | None = None,
                  min_gain: float = GHOST_MIN_GAIN, min_free_frames: int = 3) -> tuple[np.ndarray, list[dict]]:
    """Replace every ghost box of ``bg`` by real background.

    Two sources are tried and the blacker-free one wins: the median of this
    segment's tooltip-free frames (at least ``min_free_frames``; other
    tooltips half covering the spot leave a residue there) and the same
    region of the first donor median that :func:`patch_from_donor` accepts
    (``window`` in the arrays' coordinates). A patch must lower the region's
    blackness by ``min_gain``. Returns the repaired copy and the boxes, each
    with ``darkness_after`` and ``repaired`` (``"frames"``, ``"donor"`` +
    ``donor`` index, or ``False``).
    """
    boxes = ghost_boxes(frames, bg, donors) if boxes is None else boxes
    out = bg.copy()
    for g in boxes:
        x, y, w, h = g["bbox"]
        g["repaired"] = False
        g["darkness_after"] = g["median_darkness"]
        options: list[tuple[float, str, np.ndarray, dict]] = []
        if len(g["free_frames"]) >= min_free_frames:
            stack = np.stack([frames[k][y:y + h, x:x + w] for k in g["free_frames"]])
            patch = np.median(stack, axis=0).astype(np.uint8)
            options.append((blackness(patch), "frames", patch, {}))
        if window is not None:
            for k, donor in enumerate(donors):
                patch, diff, dark = patch_from_donor(out, donor, (x, y, w, h), window)
                if patch is not None:
                    options.append((dark, "donor", patch, {"donor": k, "donor_window_diff": diff}))
                    break
        if not options:
            continue
        dark, how, patch, extra = min(options, key=lambda o: o[0])
        if dark <= g["median_darkness"] - min_gain:
            out[y:y + h, x:x + w] = patch
            g.update({"darkness_after": round(dark, 2), "repaired": how, **extra})
    return out, boxes


# --------------------------------------------------------------------------- hashing / grouping


def dhash(img: np.ndarray, size: int = 8) -> int:
    """64-bit difference hash of a BGR or grey image."""
    g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(g, (size + 1, size), interpolation=cv2.INTER_AREA)
    bits = small[:, 1:] > small[:, :-1]
    return int("".join("1" if b else "0" for b in bits.flatten()), 2)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def sharpness(img: np.ndarray) -> float:
    g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


@dataclass
class Observation:
    """One frame with a tooltip on it (what stage 4 sees before grouping)."""
    t: float
    sq: int
    offset: int
    bbox: tuple[int, int, int, int]
    hash: int
    sharpness: float
    cell_key: tuple[int, int, int] | None = None
    payload: object = field(default=None, repr=False)   # the crop, kept only for the run's best frame


class RunTracker:
    """Online grouping of tooltip observations into hovers.

    ``None`` (a frame without a tooltip) ends the current run. A frame joins
    the run when its hash is within ``max_dist`` of the run's last frame and it
    resolves to the same cell. Only the sharpest frame's ``payload`` (the crop)
    is kept, so memory stays flat however long a hover lasts. Runs shorter than
    ``min_len`` frames are dropped.
    """

    def __init__(self, max_dist: int = 2, min_len: int = 3):
        self.max_dist = max_dist
        self.min_len = min_len
        self.cur: list[Observation] = []
        self.best: Observation | None = None
        self.dropped_short = 0      # runs shorter than min_len (diagnostics)
        self.dropped: list[dict] = []

    def _flush(self) -> list[Observation] | None:
        run = self.cur
        self.cur, self.best = [], None
        if run and len(run) < self.min_len:
            self.dropped_short += 1
            self.dropped.append({"t": run[0].t, "frames": len(run), "cell": run[0].cell_key})
            return None
        return run if run else None

    def push(self, o: Observation | None) -> list[Observation] | None:
        """Add one frame; return a finished run when this frame closed one."""
        done = None
        if o is None:
            return self._flush()
        if self.cur:
            last = self.cur[-1]
            same = hamming(last.hash, o.hash) <= self.max_dist and last.cell_key == o.cell_key
            if not same:
                done = self._flush()
        if self.best is None or o.sharpness > self.best.sharpness:
            if self.best is not None:
                self.best.payload = None
            self.best = o
        else:
            o.payload = None
        self.cur.append(o)
        return done

    def finish(self) -> list[Observation] | None:
        return self._flush()


def group_runs(obs: list[Observation | None], max_dist: int = 2, min_len: int = 3) -> list[list[Observation]]:
    """Split a frame-ordered stream into hovers (see :class:`RunTracker`)."""
    tracker = RunTracker(max_dist, min_len)
    runs: list[list[Observation]] = []
    for o in obs:
        done = tracker.push(o)
        if done:
            runs.append(done)
    done = tracker.finish()
    if done:
        runs.append(done)
    return runs


def sharpest(run: list[Observation]) -> Observation:
    return max(run, key=lambda o: o.sharpness)


def contact_sheet(images: list[tuple[str, np.ndarray]], cols: int = 6, cell: tuple[int, int] = (240, 300),
                  label_h: int = 18) -> np.ndarray:
    """Tile labelled crops (BGR) into one image; crops are fitted, never cropped."""
    cw, ch = cell
    rows = max(1, (len(images) + cols - 1) // cols)
    sheet = np.full((rows * (ch + label_h), cols * cw, 3), 30, np.uint8)
    for k, (label, im) in enumerate(images):
        h, w = im.shape[:2]
        scale = min(cw / w, ch / h, 1.0)
        fitted = cv2.resize(im, (max(1, int(w * scale)), max(1, int(h * scale)))) if scale < 1 else im
        x = (k % cols) * cw
        y = (k // cols) * (ch + label_h)
        fh, fw = fitted.shape[:2]
        sheet[y + label_h:y + label_h + fh, x:x + fw] = fitted
        cv2.putText(sheet, label, (x + 3, y + label_h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 230, 255), 1, cv2.LINE_AA)
        cv2.rectangle(sheet, (x, y), (x + cw - 1, y + ch + label_h - 1), (70, 70, 70), 1)
    return sheet


def draw_cells(frame: np.ndarray, cells: list[Cell]) -> np.ndarray:
    out = frame.copy()
    colours = {1: (80, 220, 80), 2: (80, 200, 255), 3: (255, 120, 220)}
    for c in cells:
        cv2.rectangle(out, (c.x, c.y), (c.x + c.w - 1, c.y + c.h - 1), colours[c.tree], 1)
        cv2.putText(out, f"{c.row}{c.col}", (c.x + 2, c.y + c.h - 3), cv2.FONT_HERSHEY_PLAIN, 0.8, colours[c.tree], 1, cv2.LINE_AA)
    return out


def slug(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

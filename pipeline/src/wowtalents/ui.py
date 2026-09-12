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


def find_tooltip(mask: np.ndarray, w_range: tuple[int, int] = TOOLTIP_W_RANGE,
                 h_min: int = TOOLTIP_H_MIN, min_area: int = 9000,
                 rejected: list[tuple[int, int, int, int]] | None = None) -> tuple[tuple[int, int, int, int] | None, list[tuple[int, int, int, int]]]:
    """Largest tooltip-shaped blob in ``mask`` plus the other blobs (cursor candidates).

    Returns ``(bbox or None, small_blobs)`` where bbox is (x, y, w, h). Big
    blobs that fail the shape test are appended to ``rejected`` when given.
    """
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    best = None
    best_area = 0
    small: list[tuple[int, int, int, int]] = []
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if area < min_area:
            if 80 <= area <= 3000:
                small.append((x, y, w, h))
            continue
        bb = trim_bbox(mask, (x, y, w, h))
        bx, by, bw, bh = bb
        if not (w_range[0] <= bw <= w_range[1] and bh >= h_min):
            if rejected is not None:
                rejected.append(bb)
            continue
        if bw * bh > best_area:
            best, best_area = bb, bw * bh
    return best, small


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

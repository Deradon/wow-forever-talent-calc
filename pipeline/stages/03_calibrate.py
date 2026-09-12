"""Stage 3: calibrate the talent window for one segment.

Fetches one frame per fragment (every ``--every`` seconds) over the segment,
builds a median background over up to ``--frames`` frames, locates the icon
grid of the three trees (prior geometry from the probe handover refined by a
square-outline search), records the tab state and saves header/tree-name
crops for the VLM (no OCR here).

Outputs under ``work/calib/``: ``<segment_id>.json`` (cells, tab state,
frames used), ``<segment_id>-median.png`` (full-frame background; black
outside the work ROI), ``<segment_id>-overlay.png`` (boxes drawn on the
median), ``<segment_id>-header.png`` and ``<segment_id>-tree{1,2,3}.png``.

Run from ``pipeline/``: ``uv run stages/03_calibrate.py run 1`` (segment by
1-based index, id, or t_start).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wowtalents import fragments as fr  # noqa: E402
from wowtalents import ui  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)

SEGMENTS_JSON = fr.PIPELINE_DIR.parent / "data" / "extracted" / "segments.json"
CALIB_DIR = fr.WORK / "calib"


def load_segments(path: Path = SEGMENTS_JSON) -> list[dict]:
    return json.loads(path.read_text())


def median_background(cache: fr.FragmentCache, sqs: list[int], roi=ui.WORK_ROI,
                      log=typer.echo) -> tuple[np.ndarray, list[int]]:
    """Median over the first decoded frame of each fragment, restricted to ``roi``.

    Only the ROI of each frame is stacked (about 2.8 MB per frame), so 30 frames
    stay under 100 MB. The result is a full-size frame, black outside the ROI.
    """
    x0, y0, x1, y1 = roi
    stack: list[np.ndarray] = []
    used: list[int] = []
    for sq in sqs:
        data = cache.get(sq)
        for _, frame in ui.decode_frames(data, max_frames=1):
            stack.append(frame[y0:y1, x0:x1].copy())
            used.append(sq)
        log(f"sq={sq} ({fr.hms(sq)}) frame ok" + ("" if cache.path(sq).exists() else " (fetched)"))
    if not stack:
        raise typer.Exit(code=2)
    med = np.median(np.stack(stack), axis=0).astype(np.uint8)
    bg = np.zeros((ui.FRAME_H, ui.FRAME_W, 3), np.uint8)
    bg[y0:y1, x0:x1] = med
    return bg, used


@app.callback()
def _main():
    """Stage 3: calibrate one segment."""


@app.command()
def run(
    segment: str = typer.Argument(..., help="segment index (1-based), id, or t_start seconds"),
    frames: int = typer.Option(30, help="frames in the median"),
    every: int = typer.Option(0, help="seconds between sampled fragments (0 = spread evenly over the segment)"),
    threshold: float = typer.Option(3.5, help="square-outline score for a cell to count as present"),
    out_dir: Path = typer.Option(CALIB_DIR),
):
    """Median background + icon grid + tab state + header crops for one segment."""
    segs = load_segments()
    idx, seg = ui.find_segment(segs, segment)
    sid = ui.segment_id(seg, idx)
    t0, t1 = seg["t_start"], seg["t_end"]
    step = every or max(1, (t1 - t0) // frames)
    sqs = list(range(t0, t1, step))[:frames]
    typer.echo(f"{sid}: {fr.hms(t0)}-{fr.hms(t1)}, {len(sqs)} frames every {step} s")

    cache = fr.FragmentCache()
    bg, used = median_background(cache, sqs)
    cells = ui.detect_grid(bg, threshold=threshold)
    tabs = ui.tab_state(bg)

    ui.ensure_dir(out_dir)
    cv2.imwrite(str(out_dir / f"{sid}-median.png"), bg)
    cv2.imwrite(str(out_dir / f"{sid}-overlay.png"), ui.draw_cells(bg, cells)[0:720, 400:1560])
    hx0, hy0, hx1, hy1 = ui.HEADER
    cv2.imwrite(str(out_dir / f"{sid}-header.png"), bg[hy0:hy1, hx0:hx1])
    ny0, ny1 = ui.TREE_NAME_ROWS
    for tree, (tx0, tx1) in ui.TREE_X.items():
        cv2.imwrite(str(out_dir / f"{sid}-tree{tree}.png"), bg[ny0:ny1, tx0:tx1])

    per_tree = {t: sum(1 for c in cells if c.tree == t) for t in (1, 2, 3)}
    rows_per_tree = {t: sorted({c.row for c in cells if c.tree == t}) for t in (1, 2, 3)}
    calib = {
        "segment_id": sid,
        "segment_index": idx,
        "class": seg["class"],
        "t_start": t0, "t_end": t1,
        "trees_visible": seg.get("trees_visible", []),
        "page": tabs["active"],
        "tab_state": tabs,
        "frames_used": used,
        "roi": list(ui.WORK_ROI),
        "window": list(ui.WINDOW),
        "masks": [list(m) for m in ui.MASKS],
        "icon_px": ui.ICON,
        "cells": [c.to_json() for c in cells],
        "cells_per_tree": per_tree,
        "rows_per_tree": rows_per_tree,
        "files": {
            "median": f"{sid}-median.png",
            "overlay": f"{sid}-overlay.png",
            "header": f"{sid}-header.png",
            "tree_names": [f"{sid}-tree{t}.png" for t in (1, 2, 3)],
        },
    }
    (out_dir / f"{sid}.json").write_text(json.dumps(calib, indent=2) + "\n")
    typer.echo(f"tab: {tabs['active']}  cells per tree: {per_tree}  total {len(cells)}")
    for c in cells:
        if c.w < ui.ICON - 1:
            typer.echo(f"  warn: cell {c.tree}-r{c.row}c{c.col} is {c.w} px")
    typer.echo(f"wrote {out_dir / (sid + '.json')} (+median/overlay/header crops), fetched {cache.fetched} fragments")


if __name__ == "__main__":
    app()

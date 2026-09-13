"""Stage 4: find every tooltip hover in a segment and crop it at native resolution.

Needs the segment's stage-3 calibration (``work/calib/<segment_id>.json`` and
median). Walks the segment's fragments (cached in ``work/frags/``), decodes
every ``--every``-th frame (4 -> 15 fps), diffs it against the median inside
the work ROI with the overlays masked, finds the tooltip blob (about 225 px
wide, near-black box with a grey border), hashes the crop and groups
consecutive near-identical frames into hovers. Each hover keeps its sharpest
frame; the hovered cell is the one whose top-right corner is nearest the
tooltip's bottom-left corner (cross-checked against the cursor blob). Hovers
are deduped on (tree, row, col), keeping the sharpest.

Outputs under ``work/hovers/``:
``<segment_id>/<tree-slug>-r<row>c<col>.png`` (tooltip crop),
``...-icon.png`` (the cell's icon from the median, un-hovered),
``<segment_id>/unresolved-<n>.png`` (tooltip without a matching cell),
``<segment_id>.json`` (per-hover metadata) and ``<segment_id>-sheet.png``
(contact sheet of all kept crops).

Run from ``pipeline/``: ``uv run stages/04_hovers.py run 1``.
"""

from __future__ import annotations

import json
import sys
import time
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
HOVERS_DIR = fr.WORK / "hovers"
FPS = 60
CROP_MARGIN = 2   # px around the trimmed diff box so the grey border is inside the crop


def tree_slugs(calib: dict) -> dict[int, str]:
    names = calib.get("trees_visible") or []
    return {t: (ui.slug(names[t - 1]) if len(names) >= t else f"tree{t}") for t in (1, 2, 3)}


def observe(frame: np.ndarray, bg: np.ndarray, cells: list[ui.Cell], t: float, sq: int, off: int,
            thresh: int) -> tuple[ui.Observation | None, dict]:
    """One frame -> Observation (or None when no tooltip) plus cursor cross-check info."""
    mask = ui.diff_mask(frame, bg, thresh=thresh)
    rejected: list[tuple[int, int, int, int]] = []
    bbox, small = ui.find_tooltip(mask, rejected=rejected)
    if bbox is None:
        return None, {"rejected": rejected}
    x, y, w, h = bbox
    m = CROP_MARGIN
    x0, y0 = max(0, x - m), max(0, y - m)
    x1, y1 = min(ui.FRAME_W, x + w + m), min(ui.FRAME_H, y + h + m)
    crop = frame[y0:y1, x0:x1].copy()
    dark = ui.darkness(crop)
    if dark < ui.TOOLTIP_MIN_DARK:
        # a dimmed part of the grid (search box, spellbook), not a black tooltip box
        rejected.append(bbox)
        return None, {"rejected": rejected, "not_dark": round(dark, 2)}
    cell, dist, method = ui.cell_for_tooltip(cells, bbox)
    cursor_cell = None
    for sx, sy, sw, sh in small:
        c = ui.cell_at_point(cells, (sx + sw / 2, sy + sh / 2))
        if c is not None and (cell is None or (c.tree, c.row, c.col) != (cell.tree, cell.row, cell.col)):
            cursor_cell = c
            break
    if method == "column" and cursor_cell is not None:
        # the corner rule failed and the cursor sits on another cell: do not guess
        cell, method = None, "column-vs-cursor"
    obs = ui.Observation(
        t=t, sq=sq, offset=off, bbox=(x0, y0, x1 - x0, y1 - y0),
        hash=ui.dhash(crop), sharpness=ui.sharpness(crop),
        cell_key=(cell.tree, cell.row, cell.col) if cell else None, payload=crop,
    )
    info = {"dist": round(dist, 1), "method": method,
            "cursor_cell": [cursor_cell.tree, cursor_cell.row, cursor_cell.col] if cursor_cell else None,
            "darkness": round(dark, 2),
            "cut_off": x1 >= ui.WORK_ROI[2] - 1 or y1 >= ui.WORK_ROI[3] - 1 or w >= ui.TOOLTIP_W_RANGE[1] - 3}
    return obs, info


@app.callback()
def _main():
    """Stage 4: tooltip hovers of one segment."""


@app.command()
def run(
    segment: str = typer.Argument(..., help="segment index (1-based), id, or t_start seconds"),
    every: int = typer.Option(4, help="decode every N-th frame (4 = 15 fps)"),
    thresh: int = typer.Option(25, help="absdiff threshold"),
    max_dist: int = typer.Option(2, help="max dHash distance between consecutive frames of one hover"),
    min_frames: int = typer.Option(3, help="minimum frames per hover"),
    start: int | None = typer.Option(None, help="first fragment (default: segment start)"),
    end: int | None = typer.Option(None, help="last fragment, exclusive (default: segment end)"),
    calib_dir: Path = typer.Option(CALIB_DIR),
    out_dir: Path = typer.Option(HOVERS_DIR),
):
    """Detect, group and crop tooltip hovers for one calibrated segment."""
    segs = json.loads(SEGMENTS_JSON.read_text())
    idx, seg = ui.find_segment(segs, segment)
    sid = ui.segment_id(seg, idx)
    calib_path = calib_dir / f"{sid}.json"
    if not calib_path.exists():
        typer.echo(f"no calibration at {calib_path}; run stages/03_calibrate.py first")
        raise typer.Exit(code=2)
    calib = json.loads(calib_path.read_text())
    cells = [ui.Cell.from_json(c) for c in calib["cells"]]
    bg = cv2.imread(str(calib_dir / calib["files"]["median"]))
    slugs = tree_slugs(calib)
    t0 = start if start is not None else seg["t_start"]
    t1 = end if end is not None else seg["t_end"]
    typer.echo(f"{sid}: {fr.hms(t0)}-{fr.hms(t1)}, every {every}th frame, {len(cells)} cells")

    cache = fr.FragmentCache()
    tracker = ui.RunTracker(max_dist=max_dist, min_len=min_frames)
    infos: dict[tuple[int, int], dict] = {}
    runs: list[list[ui.Observation]] = []
    rejected_frames: list[dict] = []
    n_frames = n_tooltip = 0
    wall = time.time()
    for sq in range(t0, t1):
        data = cache.get(sq)
        for off, frame in ui.decode_frames(data, every=every):
            n_frames += 1
            obs, info = observe(frame, bg, cells, sq + off / FPS, sq, off, thresh)
            if obs is not None:
                n_tooltip += 1
                infos[(sq, off)] = info
            elif info.get("rejected"):
                rejected_frames.append({"t": round(sq + off / FPS, 3), "sq": sq, "offset": off,
                                        "blobs": [list(b) for b in info["rejected"]]})
            done = tracker.push(obs)
            if done:
                runs.append(done)
        typer.echo(f"sq={sq} ({fr.hms(sq)}) frames {n_frames} tooltip-frames {n_tooltip} hovers {len(runs)} "
                   f"({time.time() - wall:.0f}s)")
    done = tracker.finish()
    if done:
        runs.append(done)

    # Per run: sharpest frame; dedupe on cell keeping the sharpest.
    seg_dir = ui.ensure_dir(out_dir / sid)
    for old in seg_dir.glob("*.png"):
        old.unlink()
    best_by_cell: dict[tuple[int, int, int], dict] = {}
    unresolved: list[dict] = []
    all_hovers: list[dict] = []
    for k, run_ in enumerate(runs):
        best = ui.sharpest(run_)
        info = infos.get((best.sq, best.offset), {})
        rec = {
            "run": k, "t": round(best.t, 3), "sq": best.sq, "offset": best.offset,
            "frames": len(run_), "t_first": round(run_[0].t, 3), "t_last": round(run_[-1].t, 3),
            "bbox": list(best.bbox), "cell": list(best.cell_key) if best.cell_key else None,
            "sharpness": round(best.sharpness, 1), "hash": f"{best.hash:016x}",
            **info, "_crop": best.payload,
        }
        all_hovers.append(rec)
        if best.cell_key is None:
            unresolved.append(rec)
            continue
        prev = best_by_cell.get(best.cell_key)
        if prev is None or rec["sharpness"] > prev["sharpness"]:
            if prev is not None:
                rec["superseded"] = prev.get("superseded", 0) + 1
            best_by_cell[best.cell_key] = rec
        else:
            prev["superseded"] = prev.get("superseded", 0) + 1

    cell_by_key = {(c.tree, c.row, c.col): c for c in cells}
    hovers_out: list[dict] = []
    sheet_items: list[tuple[str, np.ndarray]] = []
    for key in sorted(best_by_cell):
        rec = best_by_cell[key]
        tree, row, col = key
        c = cell_by_key[key]
        name = f"{slugs[tree]}-r{row}c{col}"
        crop = rec.pop("_crop")
        cv2.imwrite(str(seg_dir / f"{name}.png"), crop)
        icon = bg[c.y:c.y + c.h, c.x:c.x + c.w]
        cv2.imwrite(str(seg_dir / f"{name}-icon.png"), icon)
        rec.update({"id": name, "tree": tree, "tree_name": slugs[tree], "row": row, "col": col,
                    "page": calib.get("page"), "cell_rect": list(c.rect),
                    "files": {"tooltip": f"{sid}/{name}.png", "icon": f"{sid}/{name}-icon.png"}})
        hovers_out.append(rec)
        sheet_items.append((f"{name} {fr.hms(rec['t'])} f{rec['frames']}", crop))
    unresolved_out: list[dict] = []
    for n, rec in enumerate(unresolved, 1):
        crop = rec.pop("_crop")
        fn = f"unresolved-{n}.png"
        cv2.imwrite(str(seg_dir / fn), crop)
        rec.update({"id": fn[:-4], "files": {"tooltip": f"{sid}/{fn}"}})
        unresolved_out.append(rec)
        sheet_items.append((f"unresolved-{n} {fr.hms(rec['t'])}", crop))
    for rec in all_hovers:
        rec.pop("_crop", None)

    if sheet_items:
        cv2.imwrite(str(out_dir / f"{sid}-sheet.png"), ui.contact_sheet(sheet_items))
    per_tree = {slugs[t]: sum(1 for h in hovers_out if h["tree"] == t) for t in (1, 2, 3)}
    expected = {slugs[t]: calib["cells_per_tree"].get(str(t), calib["cells_per_tree"].get(t)) for t in (1, 2, 3)}
    missing = [f"{slugs[c.tree]}-r{c.row}c{c.col}" for c in cells if (c.tree, c.row, c.col) not in best_by_cell]
    result = {
        "segment_id": sid, "class": seg["class"], "page": calib.get("page"),
        "t_start": t0, "t_end": t1, "every": every, "fps": FPS / every,
        "frames_seen": n_frames, "tooltip_frames": n_tooltip, "runs": len(runs),
        "runs_dropped_short": tracker.dropped_short,
        "dropped_runs": [{"t": round(d["t"], 3), "frames": d["frames"], "cell": list(d["cell"]) if d["cell"] else None}
                         for d in tracker.dropped],
        "rejected_frames": rejected_frames,
        "hovers": hovers_out, "unresolved": unresolved_out,
        "all_runs": [{k: v for k, v in r.items() if k != "_crop"} for r in all_hovers],
        "per_tree": per_tree, "cells_per_tree": expected, "missing_cells": missing,
        "files": {"sheet": f"{sid}-sheet.png"},
    }
    (out_dir / f"{sid}.json").write_text(json.dumps(result, indent=2) + "\n")
    typer.echo(f"{tracker.dropped_short} short runs dropped, {len(rejected_frames)} frames with a big non-tooltip blob")
    typer.echo(f"{len(runs)} runs -> {len(hovers_out)} unique cells {per_tree} of {expected}; "
               f"{len(unresolved_out)} unresolved; missing {len(missing)}: {', '.join(missing) or '-'}")
    typer.echo(f"wrote {out_dir / (sid + '.json')}, crops in {seg_dir}, sheet {sid}-sheet.png; "
               f"fetched {cache.fetched} fragments, {time.time() - wall:.0f}s")


if __name__ == "__main__":
    app()

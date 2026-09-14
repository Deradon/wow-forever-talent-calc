"""Stage 7: prerequisite arrows from the un-hovered tree background.

``detect`` reads every own Primary-page calibration median of a class
(``work/calib/<segment>-median.png``, stage 3), takes the consensus grid, and
runs ``wowtalents.arrows`` (ridge coverage along straight / row / L-shaped
paths between cells, Laplacian edge energy at the head end for the arrowhead,
a vote across medians). Output ``work/arrows/<class>.json`` plus an overlay
PNG to eyeball.

``merge`` writes the arrows into ``data/extracted/<class>.candidates.json``:
the dependent record gets ``requires_arrows`` (target cell, name, ``rank`` =
the target's max rank, shape, confidence, number of medians) and the file an
``arrows`` block with the stats. Tooltip-derived ``requires`` strings are left
alone; stage 8 (``export.merge_arrow_requires``) resolves both and never lets
an arrow overwrite a conflicting tooltip requirement (``ARROW-CONFLICT`` in
its log). Conflicts already visible here (a tooltip naming another talent or
another rank) are printed too. Cells are 1-based in the arrows file (like
``work/calib``) and 0-based in the candidates (like stage 5).

Commands (from ``pipeline/``)::

    uv run stages/07_arrows.py detect warrior            # -> work/arrows/warrior.json, warrior-overlay.png
    uv run stages/07_arrows.py merge warrior             # candidates file updated in place
    uv run stages/07_arrows.py all warrior               # both
    uv run stages/07_arrows.py all all                   # every class with a candidates file
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import cv2
import typer

from wowtalents import arrows as A  # noqa: E402
from wowtalents import export as X  # noqa: E402
from wowtalents.fsio import write_candidates_atomic, write_json_atomic  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parent
WORK = PIPELINE / "work"
CALIB_DIR = WORK / "calib"
ARROWS_DIR = WORK / "arrows"
EXTRACTED = REPO / "data" / "extracted"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classes_for(cls: str) -> list[str]:
    if cls != "all":
        return [cls]
    return sorted(p.name.split(".")[0] for p in EXTRACTED.glob("*.candidates.json"))


def cell_key(c: dict) -> tuple[int, int, int]:
    return (int(c["tree"]), int(c["row"]), int(c["col"]))


def _detect(cls: str, overlay: bool) -> dict:
    calibs = A.class_calibs(cls, CALIB_DIR)
    if not calibs:
        typer.echo(f"{cls}: no Primary-page calibration with a median under {CALIB_DIR}", err=True)
        raise typer.Exit(code=2)
    cells = A.consensus_rects(calibs)
    arrows = A.detect_class(calibs, cells)
    doc = {
        "class": cls,
        "generated_at": now(),
        "calibrations": [d["segment_id"] for d in calibs],
        "cells": len(cells),
        "params": {"leg_min_cover": A.LEG_MIN_COVER, "head_min": A.HEAD_MIN, "head_good": A.HEAD_GOOD,
                   "ridge_abs": A.RIDGE_ABS, "ridge_rel": A.RIDGE_REL},
        "arrows": [{
            "from": dict(zip(("tree", "row", "col"), a["from"])),
            "to": dict(zip(("tree", "row", "col"), a["to"])),
            "shape": a["shape"], "confidence": a["confidence"], "ambiguous": a["ambiguous"],
            "head_energy": a["head_energy"], "mid_energy": a["mid_energy"], "tail_energy": a["tail_energy"],
            "path": a["path"], "segments": a["segments"],
        } for a in arrows],
    }
    A_DIR = ARROWS_DIR
    A_DIR.mkdir(parents=True, exist_ok=True)
    write_json_atomic(A_DIR / f"{cls}.json", doc)
    if overlay:
        img = cv2.imread(str(calibs[0]["_median_path"]))
        if img is not None:
            x0, y0, x1, y1 = 440, 150, 1500, 640
            ov = A.draw_overlay(img, cells, arrows)[y0:y1, x0:x1]
            cv2.imwrite(str(A_DIR / f"{cls}-overlay.png"), cv2.resize(ov, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC))
    typer.echo(f"{cls}: {len(calibs)} medians, {len(cells)} cells, {len(arrows)} arrows "
               f"({sum(1 for a in arrows if a['confidence'] >= 0.8)} at confidence >= 0.8)")
    for a in arrows:
        typer.echo(f"  {a['shape']:8} t{a['from'][0]} r{a['from'][1]}c{a['from'][2]} -> r{a['to'][1]}c{a['to'][2]}"
                   f"  conf={a['confidence']:.2f} head={a['head_energy']} n={len(a['segments'])}")
    return doc


def _merge(cls: str) -> dict:
    arrows_path = ARROWS_DIR / f"{cls}.json"
    cand_path = EXTRACTED / f"{cls}.candidates.json"
    if not arrows_path.is_file():
        typer.echo(f"{cls}: no {arrows_path}; run detect first", err=True)
        raise typer.Exit(code=2)
    if not cand_path.is_file():
        typer.echo(f"{cls}: no candidates file {cand_path}", err=True)
        raise typer.Exit(code=2)
    arrows_doc = json.loads(arrows_path.read_text(encoding="utf-8"))
    cand = json.loads(cand_path.read_text(encoding="utf-8"))
    records = cand["candidates"] if isinstance(cand, dict) else cand
    n_before = len(records)
    tree_index = {v: int(k) for k, v in ((cand.get("trees") or {}) if isinstance(cand, dict) else {}).items()}
    if not tree_index:
        for rec in records:
            tree_index.setdefault(str(rec.get("tree")), len(tree_index) + 1)
    at: dict[tuple[int, int, int], dict] = {}
    for rec in records:
        if str(rec.get("page") or "Primary") != "Primary" or rec.get("tree") not in tree_index:
            continue
        at[(tree_index[rec["tree"]], int(rec["row"]) + 1, int(rec["col"]) + 1)] = rec
    for rec in records:
        rec.pop("requires_arrows", None)

    stats = {"arrows": len(arrows_doc["arrows"]), "merged": 0, "unmatched": [], "conflicts": []}
    for a in arrows_doc["arrows"]:
        src, dst = cell_key(a["from"]), cell_key(a["to"])
        if src not in at or dst not in at:
            missing = [f"t{k[0]}r{k[1]}c{k[2]}" for k in (src, dst) if k not in at]
            stats["unmatched"].append({"from": a["from"], "to": a["to"], "missing": missing})
            typer.echo(f"  warn: arrow t{src[0]} r{src[1]}c{src[2]} -> r{dst[1]}c{dst[2]}: no record for {missing}")
            continue
        s, d = at[src], at[dst]
        rank = int((s.get("rank") or {}).get("max") or s.get("rank_max") or 1)
        entry = {"tree": s["tree"], "row": int(s["row"]), "col": int(s["col"]), "name": s.get("name"),
                 "rank": rank, "shape": a["shape"], "confidence": a["confidence"], "medians": len(a["segments"])}
        d.setdefault("requires_arrows", []).append(entry)
        stats["merged"] += 1
        # tooltip cross-check (names only; stage 8 resolves ids)
        for req in X.parse_requires(d.get("requires") or []):
            if req["name"] is None or req["tier"]:
                continue
            same = X.R.slug(req["name"]) == X.R.slug(str(s.get("name") or ""))
            if not same or req["points"] != rank:
                stats["conflicts"].append({"talent": d.get("name"), "arrow": entry, "tooltip": req["text"]})
                typer.echo(f"  conflict: {d.get('name')}: arrow from {s.get('name')} rank {rank} vs tooltip {req['text']!r}")
    if isinstance(cand, dict):
        cand["arrows"] = {"generated_at": now(), "source": str(arrows_path.relative_to(PIPELINE)),
                          "calibrations": arrows_doc["calibrations"], **stats}
    write_candidates_atomic(cand_path, cand, before=n_before)
    typer.echo(f"{cls}: {stats['merged']} of {stats['arrows']} arrows merged into {cand_path.name}, "
               f"{len(stats['unmatched'])} unmatched, {len(stats['conflicts'])} tooltip conflicts")
    return stats


@app.command()
def detect(cls: str = typer.Argument(..., help="class id or 'all'"),
           overlay: bool = typer.Option(True, help="write work/arrows/<class>-overlay.png")):
    """Detect arrows on the calibration medians; write work/arrows/<class>.json."""
    for c in classes_for(cls):
        _detect(c, overlay)


@app.command()
def merge(cls: str = typer.Argument(..., help="class id or 'all'")):
    """Write requires_arrows into data/extracted/<class>.candidates.json."""
    for c in classes_for(cls):
        _merge(c)


@app.command("all")
def run_all(cls: str = typer.Argument(..., help="class id or 'all'"),
            overlay: bool = typer.Option(True, help="write work/arrows/<class>-overlay.png")):
    """detect + merge."""
    for c in classes_for(cls):
        _detect(c, overlay)
        _merge(c)


if __name__ == "__main__":
    app()

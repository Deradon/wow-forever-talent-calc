"""Stage 5: read every tooltip crop of a class with the local VLM.

Input: every ``work/hovers/<segment_id>.json`` of the class (stage 4) plus the
matching ``work/calib/<segment_id>.json`` and header/tree strips (stage 3).
Hovers are merged across segments on (page, tree, row, col), keeping the crop
that is not cut off and then the sharpest. Each crop is sent twice (3x and
2x cubic upscale, temperature 0, JSON schema; the brief's 2x/1.5x pair
agreed on a dropped '%' that 3x reads correctly); the confidence is the
agreement of the two passes (1.0 / 0.7 / 0.3, brief section 3). The header
strip and the three tree strips of each segment are read once so ``page``
and ``tree`` carry the display names seen in the footage.

Output: ``data/extracted/<class>.candidates.json`` (object with ``candidates``
in the brief's section-1 shape, plus ``segments``, ``missing_cells`` and
``stats``). Readings are cached in ``work/read/cache/`` by content hash, so a
re-run only pays for new crops. Crops are copied to
``data/review/<class>/<tree>/r<row>c<col>.png`` (1-based, provisional ids).

Run from ``pipeline/`` with llama-server up (``scripts/llama-server.sh``)::

    uv run stages/05_read.py run paladin
    uv run stages/05_read.py run paladin --segments 1,25 --limit 5 --dry-run
    uv run stages/05_read.py one ../data/review/paladin/holy/r1c1.png
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wowtalents import reader as RD  # noqa: E402
from wowtalents import ui  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parent
WORK = PIPELINE / "work"
HOVERS_DIR = WORK / "hovers"
CALIB_DIR = WORK / "calib"
READ_DIR = WORK / "read"
EXTRACTED = REPO / "data" / "extracted"
REVIEW = REPO / "data" / "review"
SEGMENTS_JSON = EXTRACTED / "segments.json"


def hover_docs(cls: str, only: set[str] | None) -> list[tuple[str, dict]]:
    out = []
    for p in sorted(HOVERS_DIR.glob(f"*-{cls}-*.json")):
        sid = p.stem
        if only and not ({sid, sid.split("-")[0].lstrip("0") or "0", sid.split("-")[-1]} & only):
            continue
        out.append((sid, json.loads(p.read_text())))
    return out


def read_segment_header(reader: RD.Reader, sid: str, calib: dict, log=typer.echo) -> dict:
    """VLM read of the header strip and the three tree strips of one segment."""
    files = calib.get("files") or {}
    header = cv2.imread(str(CALIB_DIR / files.get("header", f"{sid}-header.png")))
    hdr = reader.read_header(header) if header is not None else {}
    trees: dict[int, dict] = {}
    for k, fn in enumerate(files.get("tree_names") or [f"{sid}-tree{t}.png" for t in (1, 2, 3)], 1):
        strip = cv2.imread(str(CALIB_DIR / fn))
        trees[k] = reader.read_tree(strip) if strip is not None else {"name": None, "points": None}
    cv_page = (calib.get("tab_state") or {}).get("active") or calib.get("page") or "Primary"
    vlm_page = RD.norm_text(hdr.get("active_tab"))
    page = vlm_page if vlm_page and vlm_page.lower() == cv_page.lower() else cv_page
    if vlm_page and vlm_page.lower() != cv_page.lower():
        log(f"  warn: {sid}: header read says active tab {vlm_page!r}, tab saturation says {cv_page!r}; using the latter")
    expected = calib.get("trees_visible") or []
    names: dict[int, str] = {}
    for k in (1, 2, 3):
        name = RD.norm_text(trees[k].get("name"))
        exp = expected[k - 1] if len(expected) >= k else None
        if not name:
            log(f"  warn: {sid}: tree {k} name unread; falling back to {exp!r}")
            name = exp or f"Tree {k}"
        elif exp and name.lower() != exp.lower():
            log(f"  note: {sid}: tree {k} reads {name!r} (segments.md said {exp!r})")
        names[k] = name
    return {"segment_id": sid, "page": page, "page_read": hdr, "tab_state": calib.get("tab_state"),
            "trees": names, "trees_read": trees, "t": calib.get("t_start"),
            "frame_index": int(calib.get("t_start", 0)) * RD.FPS}


def missing_with_reasons(cells: set[tuple[int, int, int]], best: dict, docs: list[tuple[str, dict]],
                         names: dict[int, str], page: str) -> list[dict]:
    dropped: dict[tuple, list] = {}
    for sid, d in docs:
        for r in d.get("dropped_runs") or []:
            if r.get("cell"):
                dropped.setdefault(tuple(r["cell"]), []).append(f"{sid}@{r['t']} ({r['frames']} frames)")
    out = []
    for tree, row, col in sorted(cells):
        if (page, tree, row, col) in best:
            continue
        key = (tree, row, col)
        reason = "never hovered in any segment"
        if key in dropped:
            reason = "only hovered for < 3 frames: " + ", ".join(dropped[key][:3])
        out.append({"tree": names.get(tree, str(tree)), "row": row - 1, "col": col - 1,
                    "cell": f"{ui.slug(names.get(tree, str(tree)))}-r{row}c{col}", "reason": reason})
    return out


def copy_review(cls: str, rec: dict, hover: dict, tree_strip: Path | None) -> int:
    """Copy tooltip + icon crops (and the tree header strip once) into data/review/<class>/<tree>/."""
    tree_dir = REVIEW / cls / ui.slug(rec["tree"])
    tree_dir.mkdir(parents=True, exist_ok=True)
    row1, col1 = rec["source"]["cell"][1], rec["source"]["cell"][2]
    n = 0
    for key, suffix in (("crop_path", ".png"), ("icon_crop_path", ".icon.png")):
        src = rec["source"].get(key)
        if src and (PIPELINE / src).is_file():
            shutil.copyfile(PIPELINE / src, tree_dir / f"r{row1}c{col1}{suffix}")
            n += 1
    if tree_strip and tree_strip.is_file() and not (tree_dir / "_header.png").is_file():
        shutil.copyfile(tree_strip, tree_dir / "_header.png")
        n += 1
    return n


@app.callback()
def _main():
    """Stage 5: VLM reading of tooltip crops."""


@app.command()
def one(
    crop: Path = typer.Argument(..., help="a tooltip crop PNG"),
    server: str = typer.Option(RD.DEFAULT_SERVER, help="llama-server base URL"),
    passes: str = typer.Option("3,2", help="upscale factors of the two passes (primary first)"),
):
    """Read one crop twice and print both readings (smoke test)."""
    f1, f2 = (float(x) for x in passes.split(","))
    reader = RD.Reader(server=server)
    img = cv2.imread(str(crop))
    a, b = reader.read_tooltip(img, f1), reader.read_tooltip(img, f2)
    typer.echo(json.dumps({"pass1": a, "pass2": b, "confidence": RD.confidence(RD.clean_reading(a), RD.clean_reading(b)),
                           "differs_in": RD.disagreements(a, b)}, indent=1, ensure_ascii=False))


@app.command()
def run(
    cls: str = typer.Argument(..., help="class id, e.g. paladin"),
    segments: str | None = typer.Option(None, help="comma-separated segment indices/ids/t_start to restrict to"),
    limit: int | None = typer.Option(None, help="read at most N cells (smoke runs)"),
    passes: str = typer.Option("3,2", help="upscale factors of the two passes (primary first)"),
    server: str = typer.Option(RD.DEFAULT_SERVER, help="llama-server base URL"),
    cache: bool = typer.Option(True, help="cache readings in work/read/cache by content hash"),
    copy: bool = typer.Option(True, "--copy/--no-copy", help="copy crops into data/review/<class>/"),
    out: Path | None = typer.Option(None, help="output (default data/extracted/<class>.candidates.json)"),
    dry_run: bool = typer.Option(False, help="merge hovers and list them; no VLM calls, nothing written"),
):
    """Read every merged hover of a class; write data/extracted/<class>.candidates.json."""
    only = {s.strip() for s in segments.split(",")} if segments else None
    docs = hover_docs(cls, only)
    if not docs:
        typer.echo(f"no hovers JSON for {cls} under {HOVERS_DIR}; run stages/04_hovers.py first")
        raise typer.Exit(code=2)
    f1, f2 = (float(x) for x in passes.split(","))
    calibs = {sid: json.loads((CALIB_DIR / f"{sid}.json").read_text()) for sid, _ in docs}
    best, everything = RD.merge_hovers(docs)
    cells, odd = RD.consensus_cells([c["cells"] for c in calibs.values()])
    for sid, c in calibs.items():
        own = {(x["tree"], x["row"], x["col"]) for x in c["cells"]}
        if own != cells:
            typer.echo(f"  note: {sid}: grid differs from consensus (+{sorted(own - cells)} -{sorted(cells - own)})")
    stray = [k for k in best if k[1:] not in cells]
    for k in stray:
        typer.echo(f"  warn: hover {best[k]['_segment']}/{best[k]['id']} sits on a cell outside the consensus grid; dropped")
        best.pop(k)
    typer.echo(f"{cls}: {len(docs)} segments ({', '.join(s for s, _ in docs)}), "
               f"{sum(len(v) for v in everything.values())} hovers -> {len(best)} unique cells of {len(cells)}")
    if dry_run:
        for key in sorted(best):
            h = best[key]
            alts = len(everything[key]) - 1
            typer.echo(f"  {key} {h['_segment']}/{h['id']} t={h['t']} sharp={h['sharpness']} cut_off={h.get('cut_off')} +{alts} alt")
        return

    reader = RD.Reader(server=server, cache_dir=(READ_DIR / "cache") if cache else None)
    model = reader.model_name()
    reader_label = f"{model}+{RD.PROMPT_VERSION}"
    wall = time.time()

    # header and tree names, once per segment
    headers: dict[str, dict] = {}
    for sid, _ in docs:
        headers[sid] = read_segment_header(reader, sid, calibs[sid])
        typer.echo(f"{sid}: page {headers[sid]['page']}, trees {headers[sid]['trees']}")
    votes: dict[int, Counter] = {k: Counter() for k in (1, 2, 3)}
    for h in headers.values():
        for k, n in h["trees"].items():
            votes[k][n] += 1
    names = {k: votes[k].most_common(1)[0][0] for k in (1, 2, 3) if votes[k]}
    for k in names:
        if len(votes[k]) > 1:
            typer.echo(f"  warn: tree {k} names differ across segments {dict(votes[k])}; using {names[k]!r}")
    first_sid = docs[0][0]
    first_calib = calibs[first_sid]

    # read
    records: list[dict] = []
    keys = sorted(best)
    if limit:
        keys = keys[:limit]
    conf_counts: Counter = Counter()
    for i, key in enumerate(keys, 1):
        h = best[key]
        page, tree, row, col = key
        sid = h["_segment"]
        crop_rel = f"work/hovers/{h['files']['tooltip']}"
        img = cv2.imread(str(PIPELINE / crop_rel))
        if img is None:
            typer.echo(f"  {sid}/{h['id']}: crop missing at {crop_rel}; skipped")
            continue
        t0 = time.time()
        a = reader.read_tooltip(img, f1)
        b = reader.read_tooltip(img, f2)
        primary, secondary = RD.choose_primary(a, b)
        tree_name = names.get(tree, headers[sid]["trees"].get(tree, f"Tree {tree}"))
        page_name = headers[sid]["page"]
        tree_source = {"t": headers[sid]["t"], "frame_index": headers[sid]["frame_index"], "video": RD.VIDEO_ID,
                       "reader": reader_label, "confidence": 1.0 if votes[tree][tree_name] == len(headers) else 0.7}
        rec = RD.assemble_record(cls, {k: v for k, v in h.items() if k != "_segment"}, sid, tree_name, page_name,
                                 primary, secondary, reader=reader_label, passes=(f"{f1:g}x", f"{f2:g}x"),
                                 tree_source=tree_source)
        rec["source"]["alternates"] = [{"segment_id": x["_segment"], "t": x["t"], "sharpness": x["sharpness"],
                                        "cut_off": x.get("cut_off", False)}
                                       for x in everything[key] if x is not h]
        records.append(rec)
        conf = rec["source"]["confidence"]
        conf_counts[conf] += 1
        flag = "" if conf == 1.0 else f"  <- differs in {rec['source']['agreement']['differs_in']}"
        typer.echo(f"  [{i}/{len(keys)}] {ui.slug(tree_name)}-r{row}c{col} {rec['name']!r} {rec['rank']['current']}/{rec['rank']['max']} "
                   f"conf {conf} ({time.time() - t0:.1f}s){flag}")
        if copy:
            k = (first_calib.get("files") or {}).get("tree_names", [None] * 3)
            strip = CALIB_DIR / k[tree - 1] if k and k[tree - 1] else None
            copy_review(cls, rec, h, strip)

    # the same name twice in one tree is a cell-attribution error (junk glued to the box moves its anchor)
    by_name: dict[tuple[str, str], list[dict]] = {}
    for rec in records:
        if rec["name"]:
            by_name.setdefault((rec["tree"], rec["name"].lower()), []).append(rec)
    dupes = 0
    for (tree, _), group in by_name.items():
        if len(group) > 1:
            cells_txt = ", ".join(f"r{r['source']['cell'][1]}c{r['source']['cell'][2]}@{r['source']['segment_id']}" for r in group)
            for r in group:
                r["source"]["note"] = f"name also read at {cells_txt}; cell attribution needs review"
                r["source"]["confidence"] = min(r["source"]["confidence"], 0.3)
                dupes += 1
            typer.echo(f"  warn: {tree}: {group[0]['name']!r} read at {len(group)} cells ({cells_txt}); confidence capped at 0.3")

    missing = missing_with_reasons(cells, best, docs, names, headers[first_sid]["page"])
    stats = {
        "cells": len(cells), "hovered": len(best), "read": len(records), "missing": len(missing),
        "confidence": {str(k): v for k, v in sorted(conf_counts.items())},
        "cut_off": sum(1 for r in records if r["cut_off"]),
        "duplicate_names": dupes,
        "vlm_calls": reader.calls, "cache_hits": reader.cache_hits, "vlm_seconds": round(reader.seconds, 1),
        "wall_seconds": round(time.time() - wall, 1),
    }
    doc = {
        "class": cls,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reader": reader_label,
        "prompt_version": RD.PROMPT_VERSION,
        "passes": [f1, f2],
        "segments": [{"segment_id": s, "page": headers[s]["page"], "trees": headers[s]["trees"],
                      "unspent_talents": headers[s]["page_read"].get("unspent_talents"),
                      "hovers": len(d.get("hovers") or [])} for s, d in docs],
        "trees": {str(k): v for k, v in names.items()},
        "missing_cells": missing,
        "stats": stats,
        "candidates": records,
    }
    dest = out or (EXTRACTED / f"{cls}.candidates.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    typer.echo(f"{len(records)} records, confidence {stats['confidence']}, {stats['cut_off']} cut off, "
               f"{len(missing)} cells missing; {reader.calls} VLM calls ({reader.seconds:.0f}s), "
               f"{reader.cache_hits} cache hits, {stats['wall_seconds']}s wall")
    typer.echo(f"wrote {dest}")
    if missing:
        typer.echo("missing: " + ", ".join(m["cell"] for m in missing))


if __name__ == "__main__":
    app()

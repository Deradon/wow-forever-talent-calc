"""Stage 4b: tooltip hovers from a stream-time range of the merged mkv.

Stage 4 walks cached fragments of a probed segment; the footage between
segments (10 s probe boundaries, ranges whose live fragments were never
cached) exists only in ``work/video/<vod>.mkv``. This stage decodes such a
range with ``ffmpeg -ss -i -t -vf fps=60`` (streamed frame by frame, nothing
buffered), runs stage 4's detector (``observe``) against the calibration of a
neighbouring segment of the same class and writes the same outputs as stage
4 under a synthetic segment id ``m<NN>-<class>-<t_start>`` (``NN`` = index of
the borrowed segment), plus ``work/calib/m<NN>-...json`` (the borrowed
calibration with the range's times and ``borrowed_from``) so that stage 5
picks the hovers up like any other segment.

Stream time vs file time: see ``wowtalents.mkv`` (constant offset, measured
against a stage-0 probe frame; ``pts_gaps`` is checked for the range first).

Run from ``pipeline/``::

    uv run stages/04b_hovers_mkv.py run mage --calib 7 --start 04:07:05 --end 04:09:35
    uv run stages/04b_hovers_mkv.py offset            # re-measure the offset (probe sample of fragment 13680)
    uv run stages/04b_hovers_mkv.py gaps 04:07:00 04:10:00
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import cv2
import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wowtalents import fragments as fr  # noqa: E402
from wowtalents import mkv as MK  # noqa: E402
from wowtalents import ui  # noqa: E402

_spec = importlib.util.spec_from_file_location("stage4", Path(__file__).resolve().with_name("04_hovers.py"))
st4 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(st4)

app = typer.Typer(add_completion=False, no_args_is_help=True)

SEGMENTS_JSON = fr.PIPELINE_DIR.parent / "data" / "extracted" / "segments.json"
CALIB_DIR = fr.WORK / "calib"
HOVERS_DIR = fr.WORK / "hovers"
PROBE_SAMPLE = fr.WORK / "probe" / "samples" / "13680.png"


def mkv_segment_id(donor_index: int, cls: str, t_start: int) -> str:
    """``m07-mage-14825``: stage 5 globs ``*-<class>-*.json``, so the shape must stay ``<x>-<class>-<t>``."""
    return f"m{donor_index:02d}-{cls}-{t_start}"


def borrowed_calib(calib: dict, sid: str, t0: int, t1: int, source: str) -> dict:
    """The donor's calibration re-labelled for the mkv range (files still point at the donor's PNGs)."""
    out = dict(calib)
    out.update({"segment_id": sid, "t_start": t0, "t_end": t1, "borrowed_from": calib.get("segment_id"),
                "source": source, "frames_used": []})
    return out


@app.callback()
def _main():
    """Stage 4b: tooltip hovers from a stream-time range of the mkv."""


@app.command()
def offset(
    mkv: Path = typer.Option(MK.MKV),
    probe: Path = typer.Option(PROBE_SAMPLE, help="stage-0 native sample <sq>.png (first frame of fragment sq)"),
    window: float = typer.Option(3.0, help="seconds searched either side of sq"),
):
    """Measure file time minus stream time by matching a probe frame against the mkv."""
    sq = int(probe.stem)
    off, diff = MK.measure_offset(mkv, probe, sq, window)
    typer.echo(f"fragment {sq} ({fr.hms(sq)}) first frame found at file time {sq + off:.3f}: "
               f"offset {off:+.3f} s, mean |diff| {diff:.2f} (module constant {MK.OFFSET:+.3f})")


@app.command()
def gaps(
    start: str = typer.Argument(..., help="stream time HH:MM:SS or seconds"),
    end: str = typer.Argument(...),
    mkv: Path = typer.Option(MK.MKV),
    offset: float = typer.Option(MK.OFFSET),
):
    """List packet-timestamp gaps of the range (empty = contiguous, the constant offset holds)."""
    t0, t1 = fr.parse_hms(start), fr.parse_hms(end)
    pts = MK.packet_pts(mkv, MK.file_time(t0, offset), t1 - t0)
    g = MK.pts_gaps(pts)
    typer.echo(f"{fr.hms(t0)}-{fr.hms(t1)}: {len(pts)} video packets, first {pts[0]:.3f} last {pts[-1]:.3f} (file time), "
               f"{len(g)} gaps" + (": " + ", ".join(f"{t:.3f}+{d}" for t, d in g[:10]) if g else ""))


@app.command()
def run(
    cls: str = typer.Argument(..., help="class id, e.g. mage"),
    calib: str = typer.Option(..., help="segment whose calibration to borrow (index, id or t_start)"),
    start: str = typer.Option(..., help="stream time HH:MM:SS or seconds, inclusive"),
    end: str = typer.Option(..., help="stream time HH:MM:SS or seconds, exclusive"),
    fps: int = typer.Option(60, help="frames per second to analyse (60 = every frame)"),
    thresh: int = typer.Option(25, help="absdiff threshold"),
    max_dist: int = typer.Option(2, help="max dHash distance between consecutive frames of one hover"),
    min_frames: int = typer.Option(3, help="minimum frames per hover"),
    offset: float = typer.Option(MK.OFFSET, help="file time minus stream time (see `offset`)"),
    mkv: Path = typer.Option(MK.MKV),
    calib_dir: Path = typer.Option(CALIB_DIR),
    out_dir: Path = typer.Option(HOVERS_DIR),
    check_gaps: bool = typer.Option(True, help="refuse a range whose packets are not contiguous"),
):
    """Detect, group and crop tooltip hovers in a stream-time range of the mkv."""
    segs = json.loads(SEGMENTS_JSON.read_text())
    idx, seg = ui.find_segment(segs, calib)
    if seg["class"] != cls:
        typer.echo(f"segment {calib} is {seg['class']}, not {cls}")
        raise typer.Exit(code=2)
    donor_sid = ui.segment_id(seg, idx)
    calib_path = calib_dir / f"{donor_sid}.json"
    if not calib_path.exists():
        typer.echo(f"no calibration at {calib_path}; run stages/03_calibrate.py first")
        raise typer.Exit(code=2)
    if not mkv.is_file():
        typer.echo(f"no mkv at {mkv}")
        raise typer.Exit(code=2)
    cal = json.loads(calib_path.read_text())
    cells = [ui.Cell.from_json(c) for c in cal["cells"]]
    bg = cv2.imread(str(calib_dir / cal["files"]["median"]))
    slugs = st4.tree_slugs(cal)
    t0, t1 = fr.parse_hms(start), fr.parse_hms(end)
    if t1 <= t0:
        typer.echo("end must be after start")
        raise typer.Exit(code=2)
    sid = mkv_segment_id(idx, cls, t0)
    typer.echo(f"{sid}: {fr.hms(t0)}-{fr.hms(t1)} at {fps} fps from {mkv.name} (offset {offset:+.3f} s), "
               f"calibration {donor_sid}, {len(cells)} cells")
    if check_gaps:
        g = MK.pts_gaps(MK.packet_pts(mkv, MK.file_time(t0, offset), t1 - t0))
        if g:
            typer.echo(f"{len(g)} packet gaps in the range (first at file time {g[0][0]:.3f}, +{g[0][1]} s); "
                       f"the constant offset does not hold here, re-measure or split the range")
            raise typer.Exit(code=3)

    tracker = ui.RunTracker(max_dist=max_dist, min_len=min_frames)
    infos: dict[tuple[int, int], dict] = {}
    runs: list[list[ui.Observation]] = []
    rejected_frames: list[dict] = []
    n_frames = n_tooltip = 0
    wall = time.time()
    last_sq = None
    for t, frame in MK.decode_range(mkv, t0, t1, fps=fps, offset=offset):
        sq, off = MK.split_sq(t)
        n_frames += 1
        obs, info = st4.observe(frame, bg, cells, t, sq, off, thresh)
        if obs is not None:
            n_tooltip += 1
            infos[(sq, off)] = info
        elif info.get("rejected"):
            rejected_frames.append({"t": round(t, 3), "sq": sq, "offset": off,
                                    "blobs": [list(b) for b in info["rejected"]],
                                    "reasons": info.get("reasons", [])})
        done = tracker.push(obs)
        if done:
            runs.append(done)
        if sq != last_sq and sq % 10 == 0:
            typer.echo(f"t={sq} ({fr.hms(sq)}) frames {n_frames} tooltip-frames {n_tooltip} hovers {len(runs)} "
                       f"({time.time() - wall:.0f}s)")
        last_sq = sq
    done = tracker.finish()
    if done:
        runs.append(done)
    if n_frames == 0:
        typer.echo("ffmpeg produced no frames (range outside the file?)")
        raise typer.Exit(code=1)

    meta = {"t_start": t0, "t_end": t1, "every": MK.STREAM_FPS // fps, "fps": fps,
            "frames_seen": n_frames, "tooltip_frames": n_tooltip,
            "source": {"kind": "mkv", "file": mkv.name, "offset": offset, "calibration": donor_sid}}
    finish = getattr(st4, "finish")
    finish(sid, cls, cal, bg, cells, slugs, runs, infos, tracker, rejected_frames, out_dir, meta)
    cpath = calib_dir / f"{sid}.json"
    cpath.write_text(json.dumps(borrowed_calib(cal, sid, t0, t1, f"mkv {fr.hms(t0)}-{fr.hms(t1)}"), indent=2) + "\n")
    typer.echo(f"wrote {out_dir / (sid + '.json')}, crops in {out_dir / sid}, calibration copy {cpath.name}; "
               f"{time.time() - wall:.0f}s")


if __name__ == "__main__":
    app()

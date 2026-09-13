"""Stage 0: find the talent footage in the live stream before the mkv exists.

Commands (run with ``uv run stages/00_probe_live.py <cmd>`` from ``pipeline/``):

* ``scan``     fetch one fragment per N in [start, end] step ``step`` (or an
               explicit ``--times`` list), decode one 640-px frame each into
               ``work/probe/frames/<N>.jpg``. Resumable; refreshes the URL after
               3 consecutive failures; aborts if the main download starts
               skipping fragments.
* ``sheets``   build contact sheets (grid of frames, timestamp burned in) under
               ``work/probe/sheets/`` for visual classification.
* ``sample``   fetch given times at native 1920x1080 as PNG into
               ``work/probe/samples/``.
* ``segments`` turn hand-made ``work/probe/labels.json`` observations into
               ``data/extracted/segments.json`` and ``segments.md``.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wowtalents import fragments as fr  # noqa: E402
from wowtalents.fsio import write_json_atomic, write_text_atomic  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)

FRAMES_DIR = fr.PROBE_DIR / "frames"
SHEETS_DIR = fr.PROBE_DIR / "sheets"
SAMPLES_DIR = fr.PROBE_DIR / "samples"
LABELS_JSON = fr.PROBE_DIR / "labels.json"
DATA_EXTRACTED = fr.PIPELINE_DIR.parent / "data" / "extracted"


def _times(start: int, end: int, step: int, times: str | None) -> list[int]:
    if times:
        return sorted({fr.parse_hms(t.strip()) for t in times.split(",") if t.strip()})
    return list(range(start, end + 1, step))


_HEALTH: fr.DownloadHealth | None = None


def _guard_download(label: str) -> None:
    global _HEALTH
    if _HEALTH is None:
        _HEALTH = fr.DownloadHealth()
    try:
        warn = _HEALTH.check()
    except fr.FragmentError as e:
        typer.echo(f"ABORT ({label}): {e}", err=True)
        raise typer.Exit(code=3) from e
    if warn:
        typer.echo(f"  warn ({label}): {warn}")


def _fetch_loop(client: fr.FragmentClient, ns: list[int], dest_for, width: int | None,
                fmt: str, sleep: float, force: bool, max_failures: int = 3) -> dict[int, Path]:
    """Shared fetch/decode loop with failure counting, refresh and abort rules."""
    done: dict[int, Path] = {}
    failures = 0
    refreshed_in_streak = False
    i = 0
    typer.echo(f"url from {client.source.name}, expires {client.expiry:%Y-%m-%d %H:%M:%S} UTC")
    while i < len(ns):
        n = ns[i]
        dest: Path = dest_for(n)
        if dest.exists() and not force:
            done[n] = dest
            i += 1
            continue
        if i % 10 == 0:
            _guard_download(f"before sq={n}")
        t0 = time.time()
        try:
            data = client.fetch(n)
            img = fr.decode_frame(data, width=width, fmt=fmt)
        except Exception as e:  # noqa: BLE001 - any failure counts toward the streak
            failures += 1
            typer.echo(f"sq={n} ({fr.hms(n)}) FAIL {failures}/{max_failures}: {e}")
            if failures >= max_failures:
                if refreshed_in_streak:
                    typer.echo("ABORT: still failing after a URL refresh.", err=True)
                    raise typer.Exit(code=2)
                typer.echo("refreshing fragment URL via yt-dlp -j ...")
                try:
                    client.refresh()
                except Exception as re_:  # noqa: BLE001
                    typer.echo(f"ABORT: refresh failed: {re_}", err=True)
                    raise typer.Exit(code=2)
                typer.echo(f"new url expires {client.expiry:%Y-%m-%d %H:%M:%S} UTC")
                refreshed_in_streak = True
                failures = 0
            time.sleep(max(sleep, 1.0))
            continue  # retry the same n
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(img)
        done[n] = dest
        failures = 0
        refreshed_in_streak = False
        typer.echo(f"sq={n} ({fr.hms(n)}) ok {len(data) // 1024} KB frag -> {dest.name} ({time.time() - t0:.2f}s)")
        i += 1
        time.sleep(sleep)
    return done


@app.command()
def scan(
    start: int = typer.Option(10800, help="first stream second (03:00:00)"),
    end: int = typer.Option(22800, help="last stream second (06:20:00)"),
    step: int = typer.Option(60, help="seconds between probes"),
    times: str | None = typer.Option(None, help="explicit comma list of seconds or HH:MM:SS; overrides start/end/step"),
    out: Path = typer.Option(FRAMES_DIR, help="frame output directory"),
    width: int = typer.Option(640, help="frame width in px (0 = native)"),
    sleep: float = typer.Option(0.3, help="pause between requests (s)"),
    force: bool = typer.Option(False, help="re-fetch existing frames"),
):
    """Fetch one frame per probe time into work/probe/frames/<N>.jpg."""
    ns = _times(start, end, step, times)
    client = fr.FragmentClient()
    _guard_download("start")
    done = _fetch_loop(client, ns, lambda n: out / f"{n}.jpg", width or None, "jpg", sleep, force)
    typer.echo(f"{len(done)} frames in {out}")
    _guard_download("end")


@app.command()
def sample(
    times: str = typer.Argument(..., help="comma list of seconds or HH:MM:SS"),
    out: Path = typer.Option(SAMPLES_DIR),
    sleep: float = typer.Option(0.3),
    force: bool = typer.Option(False),
):
    """Fetch given times at native resolution as PNG into work/probe/samples/."""
    ns = _times(0, 0, 1, times)
    client = fr.FragmentClient()
    _guard_download("start")
    _fetch_loop(client, ns, lambda n: out / f"{n}.png", None, "png", sleep, force)


@app.command()
def sheets(
    frames: Path = typer.Option(FRAMES_DIR),
    out: Path = typer.Option(SHEETS_DIR),
    start: int = typer.Option(0),
    end: int = typer.Option(10**9),
    cols: int = typer.Option(4),
    rows: int = typer.Option(5),
    cell_width: int = typer.Option(640),
    prefix: str = typer.Option("sheet"),
    clean: bool = typer.Option(False, help="delete existing sheets with this prefix first"),
):
    """Build contact sheets with the stream timestamp burned into every cell."""
    from PIL import Image, ImageDraw, ImageFont

    paths = sorted(
        (int(p.stem), p) for p in frames.glob("*.jpg") if p.stem.isdigit() and start <= int(p.stem) <= end
    )
    if not paths:
        typer.echo("no frames", err=True)
        raise typer.Exit(code=1)
    out.mkdir(parents=True, exist_ok=True)
    if clean:
        for old in out.glob(f"{prefix}_*.jpg"):
            old.unlink()
    try:
        font = ImageFont.load_default(size=max(18, cell_width // 22))
    except TypeError:  # very old Pillow
        font = ImageFont.load_default()
    per = cols * rows
    written = []
    for s in range(0, len(paths), per):
        chunk = paths[s:s + per]
        first = Image.open(chunk[0][1])
        cw, ch = cell_width, round(first.height * cell_width / first.width)
        sheet = Image.new("RGB", (cols * cw, rows * ch), (20, 20, 20))
        draw = ImageDraw.Draw(sheet)
        for k, (n, p) in enumerate(chunk):
            im = Image.open(p).convert("RGB")
            if im.width != cw:
                im = im.resize((cw, ch))
            x, y = (k % cols) * cw, (k // cols) * ch
            sheet.paste(im, (x, y))
            label = f"{n}  {fr.hms(n)}"
            tw = draw.textlength(label, font=font)
            draw.rectangle([x, y, x + tw + 12, y + font.size + 8], fill=(0, 0, 0))
            draw.text((x + 6, y + 3), label, fill=(255, 230, 80), font=font)
            draw.rectangle([x, y, x + cw - 1, y + ch - 1], outline=(90, 90, 90))
        name = out / f"{prefix}_{chunk[0][0]}-{chunk[-1][0]}.jpg"
        sheet.save(name, quality=88)
        written.append(name)
        typer.echo(f"{name.name}: {len(chunk)} frames")
    typer.echo(f"{len(written)} sheets in {out}")


@app.command()
def segments(
    labels: Path = typer.Option(LABELS_JSON, help="observations: [{t, open, class, trees, page, notes}]"),
    out_dir: Path = typer.Option(DATA_EXTRACTED),
    tail: int = typer.Option(10, help="seconds appended after the last observation of a run"),
):
    """Collapse per-frame observations into talent segments (JSON + Markdown)."""
    obs = sorted(json.loads(labels.read_text()), key=lambda o: o["t"])
    if not obs:
        typer.echo("no observations", err=True)
        raise typer.Exit(code=1)

    def key(o):
        return (bool(o.get("open")), o.get("class"), o.get("page"))

    runs: list[list[dict]] = []
    for o in obs:
        if runs and key(runs[-1][-1]) == key(o):
            runs[-1].append(o)
        else:
            runs.append([o])

    segs = []
    for idx, run in enumerate(runs):
        if not run[0].get("open"):
            continue
        t_start = run[0]["t"]
        t_end = runs[idx + 1][0]["t"] if idx + 1 < len(runs) else run[-1]["t"] + tail
        trees: list[str] = []
        notes: list[str] = []
        for o in run:
            for tr in o.get("trees") or []:
                if tr not in trees:
                    trees.append(tr)
            if o.get("notes") and o["notes"] not in notes:
                notes.append(o["notes"])
        segs.append({
            "t_start": t_start, "t_end": t_end,
            "start": fr.hms(t_start), "end": fr.hms(t_end),
            "class": run[0].get("class"), "trees_visible": trees,
            "page": run[0].get("page"), "notes": "; ".join(notes),
            "observations": len(run),
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_dir / "segments.json", segs)
    total = sum(s["t_end"] - s["t_start"] for s in segs)
    lines = [
        "# Talent segments in DxtVEhjyROU (stage 0 probe)",
        "",
        f"Generated from `pipeline/work/probe/labels.json` ({len(obs)} observations). "
        f"Boundaries are accurate to the probe step at that point (10 s where refined). "
        f"Total talent-window time: {total} s ({total / 60:.1f} min) in {len(segs)} segments.",
        "",
        "| # | start | end | dur (s) | class | page | trees visible | notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, s in enumerate(segs, 1):
        lines.append(
            f"| {i} | {s['start']} | {s['end']} | {s['t_end'] - s['t_start']} | {s['class']} | {s['page']} | "
            f"{', '.join(s['trees_visible'])} | {s['notes']} |"
        )
    write_text_atomic(out_dir / "segments.md", "\n".join(lines) + "\n")
    typer.echo(f"{len(segs)} segments, {total} s total -> {out_dir}")


if __name__ == "__main__":
    app()

"""Stage 11: spell lists and hover tooltips from the spellbook windows.

Three commands, the shape stage 12 established:

``scan``   decodes the spellbook windows of the mkv a few frames per second,
           locates the window by its title bar (it moves around the screen),
           and reduces the frames to *page states*: one median-background crop
           per (window position, tab, search text) run, plus every hover
           tooltip found in that run by differencing against the same median.
``read``   sends each state's three list columns to llama-server twice (3x and
           2x cubic upscale, temperature 0, JSON schema) and each tooltip crop
           twice, and turns the readings into entry records with stage 5's
           agreement confidence. ``--codex`` adds a third opinion from the codex
           CLI on one state per page.
``opinions`` fills that third opinion in for *every* column and tooltip that
           still lacks one. Two passes of the same VLM agree on their own
           mistakes, so the merge in ``build`` needs an independent reader
           before a confidence of 1.0 means anything (review round two, D-1).
``build``  merges the states per class into ``data/spells/<class>.json``, diffs
           the names against ``data/prior/classic-era/spells-baseline.json``,
           and writes the review crops, ``data/extracted/spells.json`` and
           ``data/extracted/spells.md``.

The windows themselves come from ``work/spells/windows.json``, which
``scripts/spell_windows.py`` derives from the whole-VOD keyframe sweep (50
spellbook runs, none missed); :data:`WINDOWS`, the hand-built table the stage
shipped with, is the fallback when that file is absent. The class is not written
anywhere in the spellbook, so it comes from the window table either way (the
demo character of that stream minute); ``read`` cross-checks every label against
the page headings, which are the class's talent tree names.

Run from ``pipeline/`` with llama-server up (``scripts/llama-server.sh``)::

    uv run stages/11_spellbook.py scan
    uv run stages/11_spellbook.py read --codex page
    uv run stages/11_spellbook.py opinions            # codex CLI, no llama-server needed
    uv run stages/11_spellbook.py build
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np
import typer

# ``wowtalents`` is this project's own installed package (``uv run`` puts it on the path), so no
# sys.path surgery is needed for it. ``validate_spells`` is a top-level module next to the
# stages rather than part of the package, and the canonical serializer lives there so that
# ``--check`` compares bytes against exactly what this stage writes; one path entry, added once
# at import, is what that costs (round two, K-9).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wowtalents import mkv as MK  # noqa: E402
from wowtalents import reader as RD  # noqa: E402
from wowtalents import spells as SP  # noqa: E402
from wowtalents import stagekit as SK  # noqa: E402
from wowtalents import ui  # noqa: E402
from wowtalents.fsio import write_json_atomic, write_text_atomic  # noqa: E402
from wowtalents.text import clean_text, slug  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parent
WORK = PIPELINE / "work"
SPELLS_WORK = WORK / "spells"
STATES_JSON = SPELLS_WORK / "states.json"
WINDOWS_JSON = SPELLS_WORK / "windows.json"
READINGS_JSON = SPELLS_WORK / "readings.json"
DATA = REPO / "data"
EXTRACTED = DATA / "extracted"
REVIEW = DATA / "review" / "spells"
SPELLS_DIR = DATA / "spells"
PRIOR = DATA / "prior" / "classic-era" / "spells-baseline.json"

VIDEO_ID = RD.VIDEO_ID
FPS = RD.FPS

#: **Fallback only.** Every stream range whose stage-0 probe minute matches the
#: spellbook title bar (normalised cross-correlation >= 0.85 over all 541 probe
#: frames), padded by 30 s either side and merged. A spellbook open for less than
#: a probe step is invisible to it: the 2026-09-14 keyframe sweep found 50 runs in
#: the VOD and this table covers 29 of them, missing among others the warlock
#: Demonology page at 06:21 and mage Arcane page 2/2 at 04:39. ``scan`` prefers
#: :data:`WINDOWS_JSON` and only falls back here when that file is missing.
#: ``cls`` is the demo character of that minute, labelled by hand from the page
#: headings and the General page's racials; it is the only thing the spellbook
#: itself never shows. ``read`` re-checks it against the tree names in
#: data/talents/<class>.json and complains on a mismatch.
WINDOWS: list[tuple[int, int, str, str]] = [
    (14340, 14520, "paladin", "Horde paladin in Durotar: Retribution, Holy, and a 'seal of fury' search"),
    (15270, 15340, "mage", "Undead mage: General page"),
    (15450, 15530, "mage", "Undead mage: Arcane page"),
    (18060, 18220, "warrior", "warrior: Fury page"),
    (19090, 19170, "warlock", "warlock: 'Bane of Agony' search, all four ranks listed; "
                              "not in the other-content.md survey at all"),
    (19980, 20160, "shaman", "Orc shaman: Elemental Combat page"),
    (20300, 20440, "shaman", "Orc shaman: General page and 'wind'/'windfury' searches"),
    (20490, 20560, "shaman", "Orc shaman: General page"),
    (20890, 20980, "druid", "Tauren druid: Restoration page"),
    (21290, 21400, "hunter", "Night Elf hunter: Marksmanship page"),
    (21590, 21770, "paladin", "Human paladin: General page and 'seal of fury' / 'blessing' searches"),
    (22110, 22180, "mage", "Gnome mage: Fire page"),
    (22400, 22480, "rogue", "Night Elf rogue: General page, window dragged to the right"),
    (22620, 22720, "warrior", "warrior: 'thunder clap' search"),
    (22760, 22840, "warrior", "warrior: 'whirl' search, window dragged to the right"),
]

def load_windows(path: Path) -> list[tuple[int, int, str, str]]:
    """The window table in ``path``, as ``(t0, t1, class, note)`` tuples.

    Accepts both shapes a windows file can carry: the object
    ``scripts/spell_windows.py`` writes (``{"windows": [{"t0", "t1", "class",
    "note"}, ...]}``) and a bare list of 4-element arrays. Raises ``ValueError``
    on anything else rather than silently scanning the wrong ranges.
    """
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("windows") if isinstance(doc, dict) else doc
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: no windows in the file")
    out: list[tuple[int, int, str, str]] = []
    for i, row in enumerate(rows):
        if isinstance(row, dict):
            t0, t1 = row.get("t0"), row.get("t1")
            cls, note = row.get("class") or "unknown", row.get("note") or ""
        elif isinstance(row, (list, tuple)) and len(row) >= 3:
            t0, t1, cls = row[0], row[1], row[2]
            note = row[3] if len(row) > 3 else ""
        else:
            raise ValueError(f"{path}: window {i} is neither an object nor a [t0, t1, class, note] row")
        if not isinstance(t0, (int, float)) or not isinstance(t1, (int, float)) or t1 <= t0:
            raise ValueError(f"{path}: window {i} has no usable range ({t0!r}, {t1!r})")
        out.append((int(t0), int(t1), str(cls), str(note)))
    out.sort()
    return out


def windows_from(path: Path | None) -> tuple[list[tuple[int, int, str, str]], str]:
    """``(windows, source)``: the file when it exists, else the hand-built fallback."""
    if path is not None and path.is_file():
        return load_windows(path), str(path.name)
    return list(WINDOWS), "WINDOWS (hand-built fallback)"


#: Review crops are evidence, not artwork: maximum lossless compression.
PNG = [cv2.IMWRITE_PNG_COMPRESSION, 9]

#: Frames a page state must survive to be kept (at 4 fps, half a second).
MIN_STATE_FRAMES = 2
#: Frames of one state buffered before it is flushed (100 s at 4 fps).
MAX_STATE_FRAMES = 400
#: Frames taken from a state for the median background.
BG_SAMPLES = 15

#: Lowest merged confidence a list row may carry and still be published. A row only one reader
#: ever saw scores 0.0 and is evidence of nothing; four such rows shipped as "new in Forever"
#: names before round two's review caught them (D-2). 0.5 keeps every 0.7 row.
MIN_PUBLISHABLE = 0.5


# --------------------------------------------------------------------------- scan


@app.callback()
def _main():
    """Stage 11: spell lists and spellbook tooltips."""


class _StateRun:
    """One (window position, tab, search text) run, buffered as JPEG to stay small."""

    def __init__(self, win: SP.Window, key: tuple, t: float):
        # key is (greyscale reference frame, its window) -- the page this run is of
        self.win = win
        self.key = key
        self.t_start = self.t_end = t
        self.times: list[float] = []
        self.buf: list[bytes] = []
        self.roi = SP.work_roi(win)
        self.truncated = False

    def add(self, t: float, frame: np.ndarray) -> None:
        self.t_end = t
        self.times.append(t)
        ok, enc = cv2.imencode(".jpg", SP.crop(frame, self.roi), [cv2.IMWRITE_JPEG_QUALITY, 97])
        if ok:
            self.buf.append(enc.tobytes())

    def frames(self) -> list[np.ndarray]:
        return [cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR) for b in self.buf]


def _state_id(cls: str, t: float) -> str:
    return f"{cls}-{int(round(t))}"


def _finish_state(run: _StateRun, cls: str, note: str, crops: Path,
                  min_frames: int, diff_thresh: int, quantile: float) -> dict | None:
    """Page composite, list geometry and hover tooltips of one page state."""
    if len(run.buf) < min_frames:
        return None
    frames = run.frames()
    idx = np.linspace(0, len(frames) - 1, min(BG_SAMPLES, len(frames))).round().astype(int)
    bg = SP.composite([frames[i] for i in sorted(set(idx.tolist()))], quantile)
    rx0, ry0, _, _ = run.roi
    # the composite is a ROI crop; rebase the window to it so every SP.* box lands right
    local = SP.Window(run.win.x - rx0, run.win.y - ry0, run.win.score)
    page = SP.crop(bg, SP.window_box(local))
    sharp = ui.sharpness(page)
    t_best = run.times[len(run.times) // 2]
    sid = _state_id(cls, t_best)
    cv2.imwrite(str(crops / f"{sid}.page.png"), page)

    origin = SP.Window(0, 0, run.win.score)
    cells = SP.filled_cells(page, origin)
    return {
        "id": sid, "class": cls, "t": round(t_best, 3), "t_start": round(run.t_start, 3),
        "t_end": round(run.t_end, 3), "frames": len(run.buf),
        "frame": int(round(t_best * FPS)), "sharpness": round(sharp, 2),
        "window": [run.win.x, run.win.y], "window_score": run.win.score,
        "list_hash": ui.dhash(SP.crop(page, SP.list_box(origin))),
        "page_crop": f"{sid}.page.png",
        "cells": [[c, r] for c, r in cells],
        "note": note, "truncated": run.truncated,
        "tooltips": _find_tooltips(frames, bg, local, run, sid, crops, diff_thresh),
    }


def _find_tooltips(frames: list[np.ndarray], bg: np.ndarray, local: SP.Window, run: _StateRun,
                   sid: str, crops: Path, diff_thresh: int) -> list[dict]:
    """Hover tooltips of one state: diff against the state's own page composite.

    Detection runs on the window crop only -- outside it the world moves, and
    against a high-quantile composite that motion masses into blobs bigger than
    any tooltip -- and the box is then grown rightwards on the wider ROI, which
    is where a third-column tooltip keeps its cooldown and range.

    Frames are grouped by the *anchored cell*, not by image similarity: the box
    fades in over two or three frames, so a hash-based run tracker files one
    hover as five, four of them half-drawn (measured on the rogue's Shadowmeld:
    14 "hovers" of one). The largest box of a cell is the fully drawn one, and
    among equals the sharpest wins.
    """
    wx0, wy0, wx1, wy1 = SP.window_box(local)
    origin = SP.Window(0, 0, local.score)
    bg_win = cv2.cvtColor(bg[wy0:wy1, wx0:wx1], cv2.COLOR_BGR2GRAY)
    best: dict[tuple[int, int], dict] = {}

    for t, fr in zip(run.times, frames):
        gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        bbox = SP.find_tooltip(gray[wy0:wy1, wx0:wx1], bg_win, origin, diff_thresh)
        if bbox is None:
            continue
        x, y, w, h = SP.grow_right(gray, (bbox[0] + wx0, bbox[1] + wy0, bbox[2], bbox[3]))
        cell = SP.tooltip_cell(local, (x, y, w, h))
        if cell is None:
            continue
        crop_img = fr[y:y + h, x:x + w]
        if crop_img.size == 0:
            continue
        score = (w * h, ui.sharpness(crop_img))
        cur = best.get(cell)
        if cur is None:
            best[cell] = {"score": score, "t": t, "bbox": (x, y, w, h), "img": crop_img.copy(), "n": 1}
        else:
            cur["n"] += 1
            if score > cur["score"]:
                cur.update(score=score, t=t, bbox=(x, y, w, h), img=crop_img.copy())

    out = []
    rx0, ry0, _, _ = run.roi
    for i, (cell, hit) in enumerate(sorted(best.items())):
        x, y, w, h = hit["bbox"]
        name = f"{sid}.tt{i}.png"
        cv2.imwrite(str(crops / name), hit["img"])
        out.append({"id": f"{sid}-tt{i}", "t": round(hit["t"], 3), "frame": int(round(hit["t"] * FPS)),
                    "bbox": [x + rx0, y + ry0, w, h], "cell": list(cell),
                    "frames": hit["n"], "sharpness": round(hit["score"][1], 2), "crop": name})
    return out


@app.command()
def scan(
    fps: int = typer.Option(4, help="frames per second analysed inside each window (must divide 60)"),
    window: list[str] = typer.Option(None, help="stream-time range HH:MM:SS-HH:MM:SS (repeatable); default: all"),
    windows: Path = typer.Option(WINDOWS_JSON, help="window table to scan; falls back to the built-in "
                                                    "WINDOWS list when the file does not exist"),
    mkv: Path = typer.Option(MK.MKV),
    offset: float = typer.Option(MK.OFFSET, help="file time minus stream time"),
    out: Path = typer.Option(SPELLS_WORK),
    change: float = typer.Option(SP.STATE_CHANGE, help="changed-pixel fraction above which the page changed"),
    min_frames: int = typer.Option(MIN_STATE_FRAMES, help="frames a page state must survive to be kept"),
    diff_thresh: int = typer.Option(25, help="per-pixel change threshold for tooltip detection"),
    quantile: float = typer.Option(0.85, help="per-pixel quantile of a state's frames used as its page"),
):
    """Find the distinct page states and hover tooltips in the spellbook windows."""
    if MK.STREAM_FPS % fps:
        typer.echo(f"--fps must divide {MK.STREAM_FPS}", err=True)
        raise typer.Exit(code=2)
    if not mkv.is_file():
        typer.echo(f"no mkv at {mkv}", err=True)
        raise typer.Exit(code=2)
    table, source = windows_from(windows)
    typer.echo(f"{len(table)} windows from {source}")
    wins: list[tuple[int, int, str, str]]
    if window:
        wins = []
        for spec in window:
            a, b = SK.parse_window(spec)
            match = next((w for w in table if w[0] <= a < w[1]), None)
            wins.append((a, b, match[2] if match else "unknown", match[3] if match else ""))
    else:
        wins = table
    crops = out / "crops"
    crops.mkdir(parents=True, exist_ok=True)
    template = SP.load_template()
    states: list[dict] = []
    wall = time.time()
    seen = open_frames = 0

    for t0, t1, cls, note in wins:
        typer.echo(f"window {SK.hms(t0)}-{SK.hms(t1)} ({cls}) at {fps} fps")
        run: _StateRun | None = None
        before = len(states)

        def close(run: _StateRun | None) -> None:
            if run is None:
                return
            st = _finish_state(run, cls, note, crops, min_frames, diff_thresh, quantile)
            if st:
                states.append(st)

        for t, frame in MK.decode_range(mkv, t0, t1, offset=offset, every=MK.STREAM_FPS // fps):
            seen += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            win = SP.locate_window(gray, template)
            if win is None:
                close(run)
                run = None
                continue
            open_frames += 1
            same = (run is not None and win.near(run.win)
                    and not SP.page_changed(run.key[0], run.key[1], gray, win, change)
                    and len(run.buf) < MAX_STATE_FRAMES)
            if not same:
                if run is not None and len(run.buf) >= MAX_STATE_FRAMES:
                    run.truncated = True
                close(run)
                run = _StateRun(win, (gray.copy(), win), t)
            run.add(t, frame)
        close(run)
        typer.echo(f"  {len(states) - before} states, {sum(len(s['tooltips']) for s in states[before:])} "
                   f"tooltips ({time.time() - wall:.0f}s)")

    doc = {"generatedAt": SK.now(), "video": VIDEO_ID, "fps": fps, "windowsFrom": source,
           "windows": [[a, b, c, n] for a, b, c, n in wins],
           "frames_seen": seen, "spellbook_frames": open_frames, "states": states}
    write_json_atomic(out / "states.json", doc)
    typer.echo(f"{len(states)} page states, {sum(len(s['tooltips']) for s in states)} tooltips "
               f"-> {out / 'states.json'} ({time.time() - wall:.0f}s)")
    per_class: dict[str, int] = {}
    for s in states:
        per_class[s["class"]] = per_class.get(s["class"], 0) + 1
    for cls, n in sorted(per_class.items()):
        typer.echo(f"  {cls:10} {n} states")


# --------------------------------------------------------------------------- read


#: The codex CLI reads one spellbook list column. It is the *shape authority* of the merge
#: (``wowtalents.spells.merge_tooltip``): a second, independent reader, not a second pass.
COLUMN_PROMPT = (
    "The image is one column of the World of Warcraft spellbook page: up to seven entries, each a "
    "square icon, a spell name beside it and a smaller grey subtitle under the name ('Rank N', "
    "'Passive', 'Racial', 'Racial Passive' or nothing). Transcribe every entry top to bottom. Copy the "
    "text exactly; do not paraphrase and do not invent entries. Do not create any file and do not "
    "explain. Your entire final message must be one JSON object and nothing else: "
    '{"entries":[{"name":"","subtitle":"","cut_off":false}]}'
)

#: The same reader on one hover tooltip. "do not correct spelling" is load-bearing: the point of
#: the authority is what the pixels say, not what a plausible tooltip would say.
TOOLTIP_PROMPT = (
    "The image is one World of Warcraft spell tooltip: a name, optional cost / range / cast time / "
    "cooldown / tools lines, optional 'Requires ...' lines, a yellow description and sometimes a "
    "green footer line. Transcribe it verbatim. Copy the text exactly as the pixels show it; do not "
    "correct spelling, capitalisation or punctuation, do not paraphrase, do not invent. Set cut_off "
    "true only if the text is clipped at an edge of the image. Do not create any file and do not "
    "explain. Your entire final message must be one JSON object and nothing else: "
    '{"name":"","cost":"","range":"","cast_time":"","cooldown":"","tools":"","requires":[],'
    '"description":"","footer":"","cut_off":false}'
)


def _pair_entries(a: list[dict], b: list[dict]) -> list[dict]:
    """Match the two passes of one column by position, then by id, and score the agreement.

    Position first because a column is an ordered list and the same spell can
    appear twice at different ranks; the id fallback catches a pass that skipped
    a row and shifted everything below it.
    """
    used: set[int] = set()
    match: dict[int, int] = {}

    def claim(i: int, pick) -> None:
        j = next((j for j in sorted(range(len(b)), key=lambda j: (abs(j - i), j))
                  if j not in used and pick(b[j])), None)
        if j is not None:
            used.add(j)
            match[i] = j

    # exact agreement first, nearest position wins; only then a same-name row at a
    # different rank, which is a real disagreement and scores 0.7, not 1.0
    for i, e in enumerate(a):
        claim(i, lambda cand, e=e: SP.entry_key(cand) == SP.entry_key(e))
    for i, e in enumerate(a):
        if i not in match:
            claim(i, lambda cand, e=e: SP.spell_id(cand["name"]) == SP.spell_id(e["name"]))
    out = []
    for i, e in enumerate(a):
        other = b[match[i]] if i in match else None
        out.append({**e, "confidence": SP.confidence(e, other),
                    "readings": [e] + ([other] if other else [])})
    for j, e in enumerate(b):
        if j not in used:
            out.append({**e, "confidence": 0.0, "readings": [e]})
    return out


def _apply_third(entries: list[dict], third: list[dict]) -> list[dict]:
    """A codex reading that matches one of the two passes lifts that row's confidence."""
    return SK.apply_third(entries, third, ident=lambda e: SP.spell_id(e.get("name") or ""),
                          agreement=SP.confidence)


def clean_tooltip(doc: dict) -> dict:
    """One spellbook tooltip reading, field contract enforced (the spell analogue of ``reader.clean_reading``)."""
    def s(key: str) -> str | None:
        v = clean_text(doc.get(key) or "")
        return v or None
    out = {"name": clean_text(doc.get("name") or ""), "cost": s("cost"), "range": s("range"),
           "cast_time": s("cast_time"), "cooldown": s("cooldown"), "tools": s("tools"),
           "requires": [clean_text(x) for x in (doc.get("requires") or []) if clean_text(x)],
           "description": clean_text(doc.get("description") or ""), "footer": s("footer"),
           "cut_off": bool(doc.get("cut_off"))}
    if out["tools"]:
        out["tools"] = out["tools"].split(":", 1)[-1].strip() if ":" in out["tools"] else out["tools"]
    return out


def tooltip_key(t: dict) -> tuple:
    return (SP.spell_id(t.get("name") or ""), t.get("cost"), t.get("range"), t.get("cast_time"),
            t.get("cooldown"), t.get("tools"), tuple(t.get("requires") or []),
            clean_text(t.get("description") or ""))


def tooltip_confidence(a: dict, b: dict | None) -> float:
    """1.0 identical, 0.7 same name and description, 0.3 otherwise."""
    if b is None:
        return 0.0
    if tooltip_key(a) == tooltip_key(b):
        return 1.0
    if (SP.spell_id(a.get("name") or "") == SP.spell_id(b.get("name") or "")
            and clean_text(a.get("description") or "") == clean_text(b.get("description") or "")):
        return 0.7
    return 0.3


#: Spellbook tabs that are not talent trees. The hunter has a Pet page (its pet's
#: abilities: Claw, Dive, Growl, the stances and the training passives), seen once at
#: 05:56:17. No other class showed a tab outside General plus its three trees.
EXTRA_TABS: dict[str, list[str]] = {"hunter": ["Pet"]}


def _tree_titles() -> dict[str, list[str]]:
    """class -> the page headings its spellbook can show: General plus its tree names.

    Read from ``data/talents/<class>.json`` so the two datasets cannot drift apart.
    Used twice: to snap a misread heading back onto the tab it must be, and to
    warn when a window's hand-labelled class does not match what is on the page.
    """
    out: dict[str, list[str]] = {}
    for p in sorted((DATA / "talents").glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cls = doc.get("class") or p.stem
        out[cls] = (["General"] + [t.get("name") or "" for t in doc.get("trees") or []]
                    + EXTRA_TABS.get(cls, []))
    return out


def _tree_names() -> dict[str, set[str]]:
    """class -> the slugs of its spellbook tab names (General included)."""
    return {cls: {slug(n) for n in names} for cls, names in _tree_titles().items()}


@app.command()
def read(
    states: Path = typer.Option(STATES_JSON),
    server: str = typer.Option(RD.DEFAULT_SERVER),
    out: Path = typer.Option(READINGS_JSON),
    limit: int = typer.Option(0, help="read at most N states (0 = all)"),
    only: str = typer.Option("", help="comma-separated class ids"),
    codex: str = typer.Option("off", help="codex CLI third opinion: off | page (one column per class and tab) | all"),
    dedupe: float = typer.Option(SP.STATE_CHANGE, help="changed-pixel fraction at which two states differ"),
):
    """Read every page state's three columns and every tooltip twice with the VLM."""
    if not states.is_file():
        typer.echo(f"no {states}; run `scan` first", err=True)
        raise typer.Exit(code=2)
    doc = json.loads(states.read_text())
    crops = states.parent / "crops"
    want = {s.strip() for s in only.split(",") if s.strip()}
    todo = SP.dedupe_states([s for s in doc["states"] if not want or s["class"] in want],
                            lambda st: cv2.imread(str(crops / st["page_crop"])), dedupe)
    typer.echo(f"{len(doc['states'])} states -> {len(todo)} distinct pages")
    if limit:
        todo = todo[:limit]
    rd = RD.Reader(server=server, cache_dir=WORK / "read" / "cache", max_tokens=1400)
    model = rd.model_name()
    codex_dir = states.parent / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    trees = _tree_names()
    titles = _tree_titles()
    out_states: list[dict] = []
    codex_done: set[tuple[str, str]] = set()
    warnings: list[str] = []
    wall = time.time()

    for i, st in enumerate(todo, 1):
        page = cv2.imread(str(crops / st["page_crop"]))
        if page is None:
            typer.echo(f"  warn: missing crop {st['page_crop']}")
            continue
        local = SP.Window(0, 0, st.get("window_score") or 1.0)
        head_a = rd.read_page_head(_head_strip(page, local), 2.0)
        raw_title = clean_text(head_a.get("title") or "")
        title, snapped = SP.snap_title(raw_title, titles.get(st["class"], []))
        if snapped:
            warnings.append(f"{st['id']}: heading {raw_title!r} snapped to {title!r}")
        cls = st["class"]
        tab = SP.tab_from_title(title)
        if tab and tab not in trees.get(cls, set()):
            # the heading names a tab of exactly one other class: the window's hand label is
            # wrong for this state, because Xaryu switched demo character inside it (seen at
            # 05:42:34, a druid Feral Combat page inside the shaman window). Reassign.
            owners = [c for c, tabs in trees.items() if tab in tabs]
            if len(owners) == 1:
                warnings.append(f"{st['id']}: heading {title!r} is a {owners[0]} tab, not a {cls} one; "
                                f"state reassigned to {owners[0]}")
                cls = owners[0]
            else:
                # usually a tooltip standing over the heading ("Instant"). The entries are
                # still real, they just cannot be filed under a tab; build says so in source.note.
                warnings.append(f"{st['id']}: heading {title!r} is not a {cls} tab; entries filed tab-less")
                tab = None
        columns: list[dict] = []
        for col in range(SP.COLUMNS):
            n_cells = sum(1 for c, _ in st["cells"] if c == col)
            if not n_cells:
                columns.append({"col": col, "cells": 0, "entries": []})
                continue
            strip = SP.crop(page, SP.column_box(local, col))
            a = SP.clean_page_reading(rd.read_spell_list(strip, 3.0))
            b = SP.clean_page_reading(rd.read_spell_list(strip, 2.0))
            entries = _pair_entries(a, b)
            key = (st["class"], tab or SP.page_slug(title))
            if codex == "all" or (codex == "page" and key not in codex_done and col == 0):
                codex_done.add(key)
                name = f"{st['id']}.c{col}.png"
                cv2.imwrite(str(codex_dir / name), strip)
                extra = SK.codex_opinion(codex_dir / name, codex_dir, COLUMN_PROMPT, "entries")
                if extra:
                    entries = _apply_third(entries, SP.clean_page_reading(extra))
            columns.append({"col": col, "cells": n_cells, "entries": entries})
        out_states.append({**{k: st[k] for k in ("id", "t", "frame", "sharpness", "window",
                                                 "list_hash", "page_crop", "cells", "note")},
                           "class": cls, "title": title or None, "tab": tab,
                           "page_current": head_a.get("page_current"), "page_max": head_a.get("page_max"),
                           "search": SP.page_slug(title) in {"name-matches", "exact-matches", "related-matches"},
                           "columns": columns})
        n_entries = sum(len(c["entries"]) for c in columns)
        typer.echo(f"[{i}/{len(todo)}] {st['id']:22} {title or '?':18} {n_entries:3} entries, "
                   f"{len(st['cells']):3} icons ({time.time() - wall:.0f}s)")

    # tooltips are deduplicated across states, not within one: a hover outlives the
    # list state it started in, and the same spell is usually hovered more than once
    reassigned = {st["id"]: st["class"] for st in out_states}
    raw_tips = [{**tt, "_class": reassigned.get(st["id"], st["class"]), "state": st["id"]}
                for st in doc["states"] if not want or st["class"] in want
                for tt in st["tooltips"]]
    tips_todo = SP.dedupe_tooltips(raw_tips, lambda t: cv2.imread(str(crops / t["crop"])))
    typer.echo(f"{len(raw_tips)} tooltips -> {len(tips_todo)} distinct")
    tooltips: list[dict] = []
    for i, tt in enumerate(tips_todo, 1):
        img = cv2.imread(str(crops / tt["crop"]))
        if img is None:
            continue
        ta = clean_tooltip(rd.read_spell_tooltip(img, 3.0))
        tb = clean_tooltip(rd.read_spell_tooltip(img, 2.0))
        conf = tooltip_confidence(ta, tb)
        primary = ta if ta.get("description") or not tb.get("description") else tb
        rec = {k: tt[k] for k in ("id", "t", "frame", "bbox", "cell", "frames", "sharpness", "crop", "state")}
        rec["class"] = tt["_class"]
        tooltips.append({**rec, **primary, "confidence": conf, "readings": [ta, tb]})
        typer.echo(f"[tt {i}/{len(tips_todo)}] {tt['_class']:8} {primary['name'][:34]:34} "
                   f"conf {conf} ({time.time() - wall:.0f}s)")

    write_json_atomic(out, {"generatedAt": SK.now(), "reader": model, "server": server,
                            "prompt": RD.PROMPT_VERSION, "warnings": warnings, "states": out_states,
                            "tooltips": tooltips})
    for w in warnings:
        typer.echo(f"  warn: {w}")
    typer.echo(f"{len(out_states)} states read by {model} in {time.time() - wall:.0f}s "
               f"({rd.calls} calls, {rd.cache_hits} cached) -> {out}")


def _head_strip(page: np.ndarray, local: SP.Window) -> np.ndarray:
    """Page heading and the 'Page N/M' line stacked into one image for a single call."""
    title = SP.crop(page, SP.page_title_box(local))
    nav = SP.crop(page, SP.page_nav_box(local))
    w = max(title.shape[1], nav.shape[1])
    out = np.zeros((title.shape[0] + nav.shape[0] + 6, w, 3), np.uint8)
    out[:title.shape[0], :title.shape[1]] = title
    out[title.shape[0] + 6:, :nav.shape[1]] = nav
    return out


# --------------------------------------------------------------------------- opinions


#: Reader labels stored in ``readings[]``. ``pass1``/``pass2`` are the two upscales of the one
#: VLM; ``codex`` is the independent reader the merge treats as the shape authority.
PASS_LABEL = "pass"
CODEX_LABEL = SP.AUTHORITY_READER


def _label_readings(readings: list[dict]) -> list[dict]:
    """Give every stored reading a ``reader`` label, preserving one already set.

    ``read --codex`` appended its codex reading without a label, marking the row ``codex: True``
    instead; that row's last reading is the authority. Everything else is a VLM pass.
    """
    out = []
    for i, r in enumerate(readings, 1):
        if not isinstance(r, dict):
            continue
        out.append(r if r.get("reader") else {**r, "reader": f"{PASS_LABEL}{i}"})
    return out


def _attach_codex(entries: list[dict], third: list[dict]) -> int:
    """Match a codex column reading onto the rows of that column; returns how many landed."""
    pool = list(third)
    n = 0
    for e in entries:
        if any(SP.is_authority(r) for r in e.get("readings") or []):
            continue
        match = next((c for c in pool if SP.entry_key(c) == SP.entry_key(e)), None)
        if match is None:
            match = next((c for c in pool if SP.spell_id(c["name"]) == SP.spell_id(e["name"])), None)
        if match is None:
            continue
        pool.remove(match)
        e["readings"] = (e.get("readings") or []) + [{**match, "reader": CODEX_LABEL}]
        e["codex"] = True
        n += 1
    return n


def _codex_jobs(rdoc: dict, sdoc: dict, crops: Path, codex_dir: Path, want: set[str],
                what: str) -> list[tuple]:
    """``(png, prompt, key, sink)`` per crop still missing an independent reading."""
    jobs: list[tuple] = []
    by_state = {st["id"]: st for st in sdoc["states"]}
    if what in ("all", "columns"):
        for st in rdoc["states"]:
            if want and st["class"] not in want:
                continue
            page = None
            for column in st["columns"]:
                entries = column.get("entries") or []
                if not entries or all(any(SP.is_authority(r) for r in e.get("readings") or [])
                                      for e in entries):
                    continue
                name = f"{st['id']}.c{column['col']}.png"
                png = codex_dir / name
                if not png.is_file():
                    if page is None:
                        src = by_state.get(st["id"], {}).get("page_crop")
                        page = cv2.imread(str(crops / src)) if src else None
                    if page is None:
                        typer.echo(f"  warn: no page crop for {st['id']}, column skipped", err=True)
                        continue
                    cv2.imwrite(str(png), SP.crop(page, SP.column_box(SP.Window(0, 0, 1.0), column["col"])))
                jobs.append((png, COLUMN_PROMPT, "entries", ("column", st["id"], column["col"])))
    if what in ("all", "tooltips"):
        for tt in rdoc.get("tooltips") or []:
            if want and tt["class"] not in want:
                continue
            if any(SP.is_authority(r) for r in tt.get("readings") or []):
                continue
            png = crops / tt["crop"]
            if not png.is_file():
                typer.echo(f"  warn: tooltip crop {tt['crop']} is missing, skipped", err=True)
                continue
            jobs.append((png, TOOLTIP_PROMPT, "name", ("tooltip", tt["id"], None)))
    return jobs


@app.command()
def opinions(
    readings: Path = typer.Option(READINGS_JSON),
    states: Path = typer.Option(STATES_JSON),
    only: str = typer.Option("", help="comma-separated class ids"),
    what: str = typer.Option("all", help="all | columns | tooltips"),
    jobs: int = typer.Option(6, help="codex CLI processes to run at once"),
    limit: int = typer.Option(0, help="at most N codex calls (0 = all)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="list the work, call nothing, write nothing"),
):
    """Add an independent codex reading to every list column and tooltip that lacks one.

    Two passes of one VLM over the same pixels agree on their own mistakes, so stage 11's
    agreement score said 1.0 for tooltips that were wrong (review round two, D-1). The merge in
    ``build`` needs a *second reader* to have anything to adjudicate; this is where that reading
    comes from. Results are cached per crop under ``work/spells/codex/``, so a re-run is free.
    """
    if not readings.is_file():
        typer.echo(f"no {readings}; run `read` first", err=True)
        raise typer.Exit(code=2)
    if not states.is_file():
        typer.echo(f"no {states}; run `scan` first", err=True)
        raise typer.Exit(code=2)
    rdoc = json.loads(readings.read_text())
    sdoc = json.loads(states.read_text())
    crops = states.parent / "crops"
    codex_dir = SK.ensure(states.parent / "codex")
    want = {x.strip() for x in only.split(",") if x.strip()}

    for st in rdoc["states"]:
        for column in st["columns"]:
            for e in column.get("entries") or []:
                e["readings"] = _label_readings(e.get("readings") or [])
    for tt in rdoc.get("tooltips") or []:
        tt["readings"] = _label_readings(tt.get("readings") or [])

    todo = _codex_jobs(rdoc, sdoc, crops, codex_dir, want, what)
    if limit:
        todo = todo[:limit]
    cached = sum(1 for png, _, _, _ in todo if (codex_dir / (png.stem + ".codex.json")).is_file())
    typer.echo(f"{len(todo)} crops need an independent reading ({cached} already cached)")
    if dry_run:
        typer.echo("dry run, nothing called and nothing written")
        return

    wall = time.time()
    results: dict[Path, dict | None] = {}
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = {pool.submit(SK.codex_opinion, png, codex_dir, prompt, key): png
                   for png, prompt, key, _ in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            png = futures[fut]
            try:
                results[png] = fut.result()
            except Exception as exc:                        # noqa: BLE001 - best effort per crop
                typer.echo(f"  warn: codex failed on {png.name}: {exc}", err=True)
                results[png] = None
            if i % 10 == 0 or i == len(todo):
                typer.echo(f"  [{i}/{len(todo)}] {time.time() - wall:.0f}s")

    tips = {tt["id"]: tt for tt in rdoc.get("tooltips") or []}
    by_state = {st["id"]: st for st in rdoc["states"]}
    rows = tooltips = failed = 0
    for png, _, _, (what_it_is, ident, col) in todo:
        doc = results.get(png)
        if doc is None:
            failed += 1
            continue
        if what_it_is == "column":
            st = by_state.get(ident)
            column = next((c for c in (st or {}).get("columns") or [] if c["col"] == col), None)
            if column is None:
                continue
            rows += _attach_codex(column["entries"], SP.clean_page_reading(doc))
        else:
            tt = tips.get(ident)
            if tt is None:
                continue
            tt["readings"] = (tt.get("readings") or []) + [{**clean_tooltip(doc), "reader": CODEX_LABEL}]
            tt["codex"] = True
            tooltips += 1

    covered = sum(1 for tt in rdoc.get("tooltips") or []
                  if any(SP.is_authority(r) for r in tt.get("readings") or []))
    rdoc["opinionsAt"] = SK.now()
    _write_readings(readings, rdoc)
    typer.echo(f"attached {rows} list rows and {tooltips} tooltips from codex "
               f"({failed} crops gave no answer) in {time.time() - wall:.0f}s")
    typer.echo(f"{covered}/{len(rdoc.get('tooltips') or [])} tooltips now have an independent reading")


def _write_readings(path: Path, doc: dict) -> None:
    """Atomic write of ``readings.json``, refused if the run lost states or tooltips.

    ``readings.json`` is hours of VLM time and is not tracked, so there is no way back from a
    shorter file. Same guard as ``fsio.write_candidates_atomic`` on the talent side.
    """
    if path.is_file():
        try:
            old = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            old = {}
        for key in ("states", "tooltips"):
            before, after = len(old.get(key) or []), len(doc.get(key) or [])
            if after < before:
                raise ValueError(f"{path.name}: {key} would shrink {before} -> {after}; refusing to write")
    write_json_atomic(path, doc)


# --------------------------------------------------------------------------- build


def _source(t: float, frame: int, crop: str, conf: float, reader: str, panel: str = "spell-list",
            readings: list[dict] | None = None, note: str | None = None) -> dict:
    """This stage's video id bound into :func:`wowtalents.stagekit.source`."""
    return SK.source(VIDEO_ID, t, frame, crop, conf, reader, panel, readings, note)


UNVERIFIED = ("Classic side is a baseline spell list written from memory and unverified "
              "(data/prior/classic-era/spells-baseline.json)")


def _prior() -> dict:
    if not PRIOR.is_file():
        return {}
    return json.loads(PRIOR.read_text()).get("classes") or {}


def _racial_names() -> dict[str, str]:
    """spell id -> race id, from the race files stage 12 produced.

    The spellbook's General page lists the character's racials among its rows, and
    they must not be diffed against a *class* spell list: every one of them would
    come out "new". The vs-Classic verdict for a racial already exists, in
    ``data/races/<race>.json``, so the spell record points there instead.
    """
    out: dict[str, str] = {}
    for p in sorted((DATA / "races").glob("*.json")):
        if p.stem == "matrix":
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for t in doc.get("traits") or []:
            out.setdefault(SP.spell_id(t.get("name") or ""), doc.get("race") or p.stem)
    return out


def _classic_talents() -> dict[str, dict[str, str]]:
    """class -> spell id -> "<tree name>", from the *sourced* Classic talent prior.

    A spellbook entry whose name is a Classic talent is the interesting case, but
    it proves nothing on its own: the demo characters have points spent, so the
    ability may simply be one they talented into. The note says exactly that.
    """
    path = DATA / "prior" / "classic-era" / "talents.json"
    if not path.is_file():
        return {}
    doc = json.loads(path.read_text())
    out: dict[str, dict[str, str]] = {}
    for cls, entry in (doc.get("classes") or {}).items():
        table = out.setdefault(cls, {})
        for tree in entry.get("trees") or []:
            for t in tree.get("talents") or []:
                table.setdefault(SP.spell_id(t.get("name") or ""), tree.get("name") or "")
    return out


def _classic_for(prior: dict, cls: str, name: str, talents: dict | None = None,
                 kind: str = "active", racials: dict | None = None) -> dict:
    """Status of one Forever spell name against the hand-written Classic Era baseline.

    Only the *name* is compared: the prior holds no tooltip text, so "changed"
    can never be claimed here. A name in the baseline is ``unknown`` (it exists
    in Classic, whether its numbers moved is not decided by this file); a name
    that is not is ``new``.
    """
    sid0 = SP.spell_id(name)
    race = (racials or {}).get(sid0)
    if kind.startswith("racial") or race:
        where = f"data/races/{race}.json" if race else "data/races/"
        return {"status": "unknown", "note": f"a racial ability, not a class spell; whether it is new or "
                                             f"changed versus Classic Era is recorded in {where}"}
    entry = prior.get(cls) or {}
    names = {SP.spell_id(n): n for n in (entry.get("spells") or [])}
    shared = {SP.spell_id(n): n for n in (prior.get("_shared") or {}).get("spells") or []}
    if cls == "hunter":
        shared |= {SP.spell_id(n): n for n in (prior.get("_pet") or {}).get("spells") or []}
    sid = sid0
    if not names and not shared:
        return {"status": "unknown", "note": "no Classic Era baseline for this class"}
    hit = names.get(sid) or shared.get(sid)
    tree = ((talents or {}).get(cls) or {}).get(sid)
    if hit is None:
        if tree:
            return {"status": "unknown", "classicName": name,
                    "note": f"not a Classic Era trainer spell, but a Classic Era {tree} talent of the same "
                            "name exists; the demo character may simply have spent a point on it, so this is "
                            "not evidence that Forever made it baseline. " + UNVERIFIED,
                    }
        return {"status": "new", "note": f"no Classic Era spell called {name} for this class; " + UNVERIFIED}
    return {"status": "unknown", "classicName": hit,
            "note": "name exists in Classic Era; whether the text or the numbers changed needs the "
                    "tooltip side by side. " + UNVERIFIED}


# --------------------------------------------------------------------------- additive merge


#: Characters of a coverage note that decide whether a published note and a freshly
#: generated one are about the same thing.
NOTE_HEAD = 48


def _tip_key(tip: dict) -> str:
    """What makes two published tooltips the same tooltip: their description text."""
    return clean_text(tip.get("description") or "")


def _merge_spell(old: dict, fresh: dict | None) -> dict:
    """One published spell, brought forward. Everything the old record has, it keeps.

    The old record owns its id, name, tab, icon and ``source`` (which names the review
    crop a reviewer has already looked at), so a re-run cannot renumber a record or
    re-point it at a crop that no longer exists. A ``reviewed`` record is returned
    untouched, full stop; any other one may gain ranks, a tab it did not have and
    tooltips whose text is new.
    """
    out = dict(old)
    if fresh is None or (old.get("source") or {}).get("reviewed"):
        return out
    ranks = sorted(set(old.get("ranksSeen") or []) | set(fresh.get("ranksSeen") or []))
    if ranks:
        out["ranksSeen"] = ranks
    if not out.get("tab") and fresh.get("tab"):
        out["tab"] = fresh["tab"]
    seen = {_tip_key(t) for t in old.get("tooltips") or []}
    added = [t for t in (fresh.get("tooltips") or []) if _tip_key(t) and _tip_key(t) not in seen]
    if added:
        out["tooltips"] = (old.get("tooltips") or []) + added
    return out


def merge_class_doc(cls: str, old: dict, fresh: dict) -> dict:
    """Merge a freshly built class document *into* the published one, additively.

    A wider window table makes ``build`` see pages it has never seen, but it must not
    make it forget the ones it has: a state id is a timestamp, so a scan at a different
    fps or over slightly different ranges renames states, and a wholesale rewrite would
    then drop every record and crop that came from the old ids. The merge is therefore
    union-only -- new tabs, new entries, new tooltips, wider coverage -- and never
    rewrites, reorders or removes what is already published (D-3's "a class file may
    never shrink", now enforced by construction).
    """
    out = dict(fresh)
    tabs: dict[str, dict] = {}
    for t in (old.get("tabs") or []) + (fresh.get("tabs") or []):
        tabs.setdefault(t["id"], dict(t))
    ordered = sorted(tabs.values(), key=lambda t: (t["id"] != "general", t["id"]))
    for i, t in enumerate(ordered):
        t["order"] = i
    out["tabs"] = ordered

    by_id = {s["id"]: s for s in fresh.get("spells") or []}
    old_ids = {s["id"] for s in old.get("spells") or []}
    spells = [_merge_spell(s, by_id.get(s["id"])) for s in old.get("spells") or []]
    spells += [s for s in (fresh.get("spells") or []) if s["id"] not in old_ids]
    out["spells"] = spells

    cov_old, cov = old.get("coverage") or {}, dict(fresh.get("coverage") or {})
    cov["pagesSeen"] = sorted(set(cov_old.get("pagesSeen") or []) | set(cov.get("pagesSeen") or []))
    cov["tabsSeen"] = sorted(tabs)
    cov["tabsMissing"] = sorted(_missing_tabs(cls, tabs))
    cov["windows"] = sorted(set(cov_old.get("windows") or []) | set(cov.get("windows") or []))
    cov["states"] = max(int(cov_old.get("states") or 0), int(cov.get("states") or 0))
    cov["entriesRead"] = len(spells)
    cov["tooltipsRead"] = sum(len(s.get("tooltips") or []) for s in spells)
    if "on" in {cov_old.get("showAllSpellRanks"), cov.get("showAllSpellRanks")}:
        cov["showAllSpellRanks"] = "on"
    out["coverage"] = cov

    # notes are prose, so an old note is kept only when the new run has nothing on the same
    # subject; matching on the opening clause is what tells "superseded" from "additional"
    heads = {n[:NOTE_HEAD]: True for n in fresh.get("notes") or []}
    notes = list(fresh.get("notes") or [])
    notes += [n for n in (old.get("notes") or []) if n[:NOTE_HEAD] not in heads and n not in notes]
    out["notes"] = notes
    return out


@app.command()
def build(
    readings: Path = typer.Option(READINGS_JSON),
    states: Path = typer.Option(STATES_JSON),
    out_dir: Path = typer.Option(SPELLS_DIR),
    review: Path = typer.Option(REVIEW),
    min_confidence: float = typer.Option(MIN_PUBLISHABLE,
                                         help="drop list rows below this merged confidence"),
    merge: bool = typer.Option(True, "--merge/--no-merge",
                               help="merge into the published class files instead of replacing them"),
    dry_run: bool = typer.Option(False, "--dry-run", help="report only; write no file and delete no crop"),
):
    """Merge the page states into data/spells/<class>.json plus the review crops and inventory.

    Two things happen here that did not before round two's review:

    * every list row and every tooltip goes through the shape-aware reader merge
      (``wowtalents.spells.merge_tooltip`` / ``merge_entry``), so the published text is the
      adjudicated one and ``source.confidence`` says whether an *independent* reader agreed;
    * a row no second reader ever saw is **not published**. ``--min-confidence 0`` brings the
      old behaviour back, which is how the four fabricated "new in Forever" spells of D-2 got
      onto the site in the first place.
    """
    if not readings.is_file():
        typer.echo(f"no {readings}; run `read` first", err=True)
        raise typer.Exit(code=2)
    rdoc = json.loads(readings.read_text())
    sdoc = json.loads(states.read_text())
    reader = rdoc.get("reader") or "unknown"
    crops = states.parent / "crops"
    prior = _prior()
    talents = _classic_talents()
    racials = _racial_names()
    out_dir.mkdir(parents=True, exist_ok=True)

    per_class: dict[str, dict] = {}
    unrowed: list[str] = []
    unpublishable: list[str] = []
    merge_shapes: Counter = Counter()
    for st in rdoc["states"]:
        cls = st["class"]
        unit = per_class.setdefault(cls, {"records": [], "states": [], "tooltips": []})
        unit["states"].append(st)
        page = cv2.imread(str(crops / st["page_crop"]))
        local = SP.Window(0, 0, 1.0)
        cells = [tuple(c) for c in st["cells"]]
        for column in st["columns"]:
            col = column["col"]
            rows = [r for c, r in cells if c == col]
            for k, e in enumerate(column["entries"]):
                m = SP.merge_entry(e.get("readings") or [])
                conf = m["confidence"] if (e.get("readings") or []) else float(e["confidence"])
                name = m["fields"].get("name") or e["name"]
                if conf < min_confidence:
                    unpublishable.append(f"{cls}/{name} ({conf}, {len(e.get('readings') or [])} reading(s))")
                    continue
                if k >= len(rows):
                    # more names than the column has icons: OpenCV counted the discs, the
                    # model invented the surplus (usually by reading a tooltip standing over
                    # the column). The icon count is a fact; the extra reading is dropped.
                    unrowed.append(f"{cls}/{st['id']}/c{col}: {e['name']}")
                    continue
                row = rows[k]
                rec = {"name": name, "rank": e["rank"], "kind": e["kind"],
                       "cut_off": bool(e["cut_off"]), "col": col, "row": row,
                       "tab": st.get("tab"), "title": st.get("title"), "search": bool(st.get("search")),
                       "state": st["id"], "t": st["t"], "frame": st["frame"],
                       "source": {"confidence": conf, "sharpness": st["sharpness"],
                                  "t": st["t"], "frame": st["frame"], "state": st["id"]},
                       "readings": e.get("readings") or [], "codex": bool(e.get("codex")),
                       "disputed": m["disputed"], "shapes": m["shapes"]}
                merge_shapes.update(m["shapes"])
                unit["records"].append(rec)
                # --dry-run must not touch data/review/ either: a crop written for a reading the
                # merge later discards is the litter _prune_crops exists to remove, and on a dry
                # run nothing prunes it
                if page is not None and not e["cut_off"] and not dry_run:
                    _write_row_crops(page, local, col, row, cls, SP.spell_id(name), review)

    by_state = {st["id"]: st for st in rdoc["states"]}
    for tt in rdoc.get("tooltips") or []:
        cls = tt["class"]
        unit = per_class.setdefault(cls, {"records": [], "states": [], "tooltips": []})
        rank = _rank_at_cell(by_state.get(tt.get("state")), tt.get("cell"))
        m = SP.merge_tooltip(tt.get("readings") or [])
        tt = {**tt,
              "name": m["fields"].get("name") or tt.get("name") or "",
              "description": m["fields"].get("description") or tt.get("description") or "",
              "footer": m["fields"].get("footer") or None,
              "confidence": m["confidence"] if (tt.get("readings") or []) else tt.get("confidence", 0.0),
              "disputed": m["disputed"], "shapes": m["shapes"]}
        merge_shapes.update(m["shapes"])
        unit["tooltips"].append({**tt, "rank": rank})
        src = crops / tt["crop"]
        sid = SP.spell_id(tt.get("name") or "")
        if src.is_file() and sid and not dry_run:
            suffix = f".r{rank}" if rank else ""
            cv2.imwrite(str(SK.ensure(review / cls) / f"{sid}{suffix}.tooltip.png"), cv2.imread(str(src)), PNG)

    counts: dict[str, dict] = {}
    docs: dict[str, dict] = {}
    for cls in sorted(per_class):
        doc = _class_doc(cls, per_class[cls], prior, reader, review, talents, crops, racials, dry_run)
        if not doc["spells"]:
            # an empty class file is never a legitimate outcome; it would pass the schema, the
            # validator and CI, and _prune_crops would then delete that class's crops (K-1)
            typer.echo(f"  {cls}: no publishable spells; the existing file is left alone", err=True)
            continue
        published = out_dir / f"{cls}.json"
        before = {"spells": 0, "tooltips": 0, "tabs": 0}
        if published.is_file():
            old_doc = json.loads(published.read_text())
            before = {"spells": len(old_doc.get("spells") or []),
                      "tooltips": sum(len(s.get("tooltips") or []) for s in old_doc.get("spells") or []),
                      "tabs": len(old_doc.get("tabs") or [])}
            if merge:
                doc = merge_class_doc(cls, old_doc, doc)
            elif len(doc["spells"]) < before["spells"]:
                # D-3: a shorter file is a regression, not a result. --no-merge keeps the guard.
                typer.echo(f"  {cls}: {len(doc['spells'])} spells against {before['spells']} on disk; "
                           f"the existing file is left alone", err=True)
                continue
        docs[cls] = doc
        counts[cls] = {"spells": len(doc["spells"]),
                       "tooltips": sum(len(s.get("tooltips") or []) for s in doc["spells"]),
                       "pages": len(doc["tabs"]),
                       "spellsBefore": before["spells"], "tooltipsBefore": before["tooltips"],
                       "tabsBefore": before["tabs"]}
    if not counts:
        typer.echo("no class produced a publishable spell list; nothing written", err=True)
        raise typer.Exit(code=1)

    if unrowed:
        typer.echo(f"  dropped {len(unrowed)} readings with no icon behind them")
        for u in unrowed[:10]:
            typer.echo(f"    {u}")
    if unpublishable:
        typer.echo(f"  dropped {len(unpublishable)} rows below the {min_confidence} publishable "
                   f"threshold (no independent reading)")
        for u in unpublishable[:10]:
            typer.echo(f"    {u}")
    typer.echo("  reader merge applied: "
               + (", ".join(f"{k} {v}" for k, v in sorted(merge_shapes.items())) or "no shape"))
    if dry_run:
        typer.echo("dry run: no file written, no crop deleted")
        for cls, n in sorted(counts.items()):
            typer.echo(f"  {cls:10} {n['spellsBefore']:3} -> {n['spells']:3} spells, "
                       f"{n['tooltipsBefore']:3} -> {n['tooltips']:3} tooltips, "
                       f"{n['tabsBefore']} -> {n['pages']} tabs")
        return

    for cls, doc in docs.items():
        write_text_atomic(out_dir / f"{cls}.json", canonical_spell_dumps(doc))
    write_json_atomic(EXTRACTED / "spells.json",
                      {"generatedAt": SK.now(), "video": VIDEO_ID, "reader": reader,
                       "states": len(rdoc["states"]), "counts": counts,
                       "candidates": {c: u["records"] for c, u in sorted(per_class.items())}})
    gone = SK.prune_crops(review, _referenced_crops(out_dir), REPO)
    write_text_atomic(EXTRACTED / "spells.md", _inventory_md(out_dir, sdoc, rdoc))
    for g in gone:
        typer.echo(f"  removed unreferenced crop {g}")
    typer.echo(f"wrote {len(counts)} class files ({'merged into' if merge else 'replacing'} the published "
               f"ones), data/extracted/spells.json and data/extracted/spells.md")
    for cls, n in sorted(counts.items()):
        typer.echo(f"  {cls:10} {n['spellsBefore']:3} -> {n['spells']:3} spells, "
                   f"{n['tooltipsBefore']:3} -> {n['tooltips']:3} tooltips, "
                   f"{n['tabsBefore']} -> {n['pages']} tabs")


def _rank_at_cell(state: dict | None, cell: list | None) -> int | None:
    """The rank of the list row a tooltip was anchored to, when that page was read.

    The anchor gives ``(col, row)``; the reader gives the column's entries in
    order and ``scan`` gives which rows of that column held an icon, so the two
    line up by position. Returns None when the page behind the hover was not one
    of the pages read (deduplication keeps one state per page, not per hover).
    """
    if not state or not cell:
        return None
    col, row = int(cell[0]), int(cell[1])
    rows = [r for c, r in (tuple(x) for x in state.get("cells") or []) if c == col]
    column = next((c for c in state.get("columns") or [] if c["col"] == col), None)
    if column is None or row not in rows:
        return None
    k = rows.index(row)
    entries = column.get("entries") or []
    return entries[k].get("rank") if k < len(entries) else None


def _write_row_crops(page: np.ndarray, local: SP.Window, col: int, row: int, cls: str,
                     sid: str, review: Path) -> None:
    """Per-entry review crops: the list row and its icon, at native resolution."""
    if not sid:
        return
    d = SK.ensure(review / cls)
    block = SP.crop(page, SP.row_box(local, col, row))
    if block.size == 0:
        return
    old = d / f"{sid}.png"
    prev = cv2.imread(str(old)) if old.is_file() else None
    if prev is not None and ui.sharpness(prev) >= ui.sharpness(block):
        return
    cv2.imwrite(str(d / f"{sid}.png"), block, PNG)
    cv2.imwrite(str(d / f"{sid}.icon.png"), SP.crop(page, SP.icon_box(local, col, row)), PNG)


CLASS_NAMES = {"druid": "Druid", "hunter": "Hunter", "mage": "Mage", "paladin": "Paladin",
               "priest": "Priest", "rogue": "Rogue", "shaman": "Shaman", "warlock": "Warlock",
               "warrior": "Warrior"}
#: The demo characters were all level 38, which is what bounds every list here.
OBSERVED_LEVEL = 38


def _class_doc(cls: str, unit: dict, prior: dict, reader: str, review: Path,
               talents: dict | None = None, crops: Path | None = None,
               racials: dict | None = None, dry_run: bool = False) -> dict:
    merged = SP.merge_entries(unit["records"])
    tabs: dict[str, dict] = {}
    for st in unit["states"]:
        tab = st.get("tab")
        if not tab:
            continue
        tabs.setdefault(tab, {"id": tab, "name": clean_text(st["title"]), "order": len(tabs)})
    by_spell: dict[str, list[dict]] = {}
    for tt in unit["tooltips"]:
        sid = SP.spell_id(tt.get("name") or "")
        if sid:
            by_spell.setdefault(sid, []).append(tt)

    spells = []
    for rec in merged:
        sid = SP.spell_id(rec["name"])
        tab = rec.get("tab")
        conf = float(rec["source"]["confidence"])
        note = None
        crop_rel = f"data/review/spells/{cls}/{sid}.png"
        if not (review / cls / f"{sid}.png").is_file():
            crop_rel = f"data/review/spells/{cls}/_page-{rec['state']}.png"
            note = "no clean single-row crop; the whole page is the evidence"
            if crops is not None and not dry_run:
                src = crops / f"{rec['state']}.page.png"
                page_img = cv2.imread(str(src)) if src.is_file() else None
                if page_img is not None:
                    # heading plus list only: the frame, tabs and search box add half the
                    # bytes and none of the evidence
                    x0, y0, x1, y1 = SP.PAGE_TITLE[0], SP.PAGE_TITLE[1], SP.LIST[2], SP.LIST[3]
                    cv2.imwrite(str(SK.ensure(review / cls) / f"_page-{rec['state']}.png"),
                                page_img[y0:y1, x0:x1], PNG)
        if rec.get("cut_off"):
            note = ((note + "; ") if note else "") + "the row was clipped in the best frame"
        if not tab:
            where = f"a search-results page ({rec.get('title')})" if rec.get("search") else \
                f"a page whose heading did not name a tab ({rec.get('title') or 'unreadable'})"
            note = ((note + "; ") if note else "") + f"read from {where}, so it has no tab"
        s: dict = {"id": sid, "name": rec["name"], "kind": rec["kind"]}
        if tab:
            s["tab"] = tab
        if rec.get("ranks"):
            s["ranksSeen"] = list(rec["ranks"])
        if (review / cls / f"{sid}.icon.png").is_file():
            s["icon"] = f"crop-{sid}"
            s["iconSource"] = "crop"
            s["iconCrop"] = f"data/review/spells/{cls}/{sid}.icon.png"
        tips = []
        for tt in by_spell.get(sid, []):
            tip = {k: v for k, v in (("cost", tt.get("cost")), ("range", tt.get("range")),
                                     ("castTime", tt.get("cast_time")), ("cooldown", tt.get("cooldown")),
                                     ("tools", tt.get("tools"))) if v}
            if tt.get("requires"):
                tip["requires"] = list(tt["requires"])
            tip["description"] = clean_text(tt.get("description") or "")
            if tt.get("footer"):
                tip["footer"] = clean_text(tt["footer"])
            if not tip["description"]:
                continue
            if tt.get("rank") is not None and tt["rank"] in (s.get("ranksSeen") or []):
                tip["rank"] = tt["rank"]
            suffix = f".r{tt['rank']}" if tt.get("rank") else ""
            tcrop = f"data/review/spells/{cls}/{sid}{suffix}.tooltip.png"
            if "rank" in tip:
                tnote = "hover tooltip; rank taken from the list row the box was anchored to"
            elif tt.get("cell"):
                tnote = ("hover tooltip, anchored to a list row, but that page state was not one of the "
                         "pages read, so the rank of the row is unknown")
            else:
                tnote = "hover tooltip; could not be anchored to a list row, matched to the spell by name"
            tnote = "; ".join([tnote, *_merge_note(tt)])
            tip["source"] = _source(tt["t"], tt["frame"], tcrop, tt.get("confidence", 0.0), reader,
                                    "tooltip", _readings(tt.get("readings") or [], reader), tnote)
            tips.append(tip)
        if tips:
            s["tooltips"] = sorted(tips, key=lambda x: x["description"])
        s["classic"] = _classic_for(prior, cls, rec["name"], talents, rec["kind"], racials)
        if s["classic"]["status"] == "new":
            s["tags"] = ["new"]
        note = "; ".join([x for x in [note, *_merge_note(rec)] if x]) or None
        s["source"] = _source(rec["t"], rec["frame"], crop_rel, conf, reader, "spell-list",
                              _readings(rec.get("readings") or [], reader), note)
        spells.append(s)

    matched = {SP.spell_id(s["name"]) for s in spells if s.get("tooltips")}
    unmatched = sorted({clean_text(t.get("name") or "") or "(no name read)"
                        for t in unit["tooltips"] if SP.spell_id(t.get("name") or "") not in matched})
    tab_names = {t["id"]: t["name"] for t in tabs.values()}
    pages, unreadable = set(), set()
    for st in unit["states"]:
        title = clean_text(st.get("title") or "")
        if st.get("tab"):
            pages.add(tab_names.get(st["tab"], title))
        elif SP.page_slug(title) in {"name-matches", "exact-matches", "related-matches"}:
            pages.add(title)
        else:
            unreadable.add(title or "(blank)")
    pages = sorted(pages)
    all_ranks = SP.show_all_ranks([{"name": s["name"], "rank": r}
                                   for s in spells for r in s.get("ranksSeen") or []])
    coverage = {
        "pagesSeen": pages,
        "tabsSeen": sorted(tabs),
        "tabsMissing": sorted(_missing_tabs(cls, tabs)),
        "states": len(unit["states"]),
        "entriesRead": len(spells),
        "tooltipsRead": sum(len(s.get("tooltips") or []) for s in spells),
        "tooltipsUnmatched": len(unmatched),
        "showAllSpellRanks": "on" if all_ranks else "not observed",
        "observedLevel": OBSERVED_LEVEL,
        "windows": sorted({SK.hms(st["t"]) for st in unit["states"]}),
    }
    notes = [
        "The spellbook never names the class; it comes from the window table in "
        "pipeline/work/spells/windows.json, derived from a 1 fps keyframe sweep of the whole VOD "
        "and hand-labelled from the page headings, the tab icons and the General page's racials. "
        "Every label is cross-checked against the page headings.",
        f"Lists are bounded by the demo character's level ({OBSERVED_LEVEL}) and by which tabs were "
        "opened on stream; a tab in coverage.tabsMissing was never shown, so its spells are absent, "
        "not missing from the game.",
        "BlizzCon demo build 2026-09-12, read from stream video; nothing here is reviewed.",
    ]
    if coverage["showAllSpellRanks"] != "on":
        notes.append("No page listed one spell at two ranks, so 'Show all spell ranks' was off or "
                     "the character knew one rank; ranksSeen is the highest rank known, not the full set.")
    if unreadable:
        notes.append("Page headings the reader could not resolve to a tab, because a hover tooltip stood "
                     "over them: " + ", ".join(sorted(unreadable))
                     + ". Their entries are in this file without a tab and say so in source.note.")
    if unmatched:
        notes.append("Hover tooltips whose header matched no list entry, so they are not in this file: "
                     + ", ".join(unmatched[:12]) + ("..." if len(unmatched) > 12 else "")
                     + ". Most are a half-drawn box caught during the fade-in; the crops are in "
                     "pipeline/work/spells/crops/.")
    if any(s.get("source", {}).get("note") for s in spells):
        notes.append("Entries with a source note were read from a clipped row or a search page; check "
                     "the crop before quoting them.")

    doc: dict = {"$schema": "../schema/spell.schema.json", "schemaVersion": 1, "class": cls,
                 "className": CLASS_NAMES.get(cls, cls.title()), "dataSource": "video",
                 "generatedAt": SK.now(), "observedLevel": OBSERVED_LEVEL,
                 "tabs": sorted(tabs.values(), key=lambda t: (t["id"] != "general", t["id"])),
                 "spells": spells, "coverage": coverage, "complete": False, "notes": notes}
    for i, t in enumerate(doc["tabs"]):
        t["order"] = i
    return doc


#: How many stored readings reach ``source.readings``. The shape authority is always one of
#: them, however many passes ran, because it is the reading a reviewer needs to see.
MAX_STORED_READINGS = 3


def _merge_note(rec: dict) -> list[str]:
    """The ``source.note`` clauses the reader merge owns, for one record."""
    out = []
    if rec.get("disputed"):
        out.append("the two readers disagree on " + "; ".join(rec["disputed"][:3])
                   + " - the reading shown is the first reader's")
    if rec.get("shapes"):
        out.append("the shape-aware reader merge corrected "
                   + ", ".join(f"{v} {k}" for k, v in sorted(rec["shapes"].items())))
    return out


def _readings(raw: list[dict], reader: str) -> list[dict]:
    """``source.readings`` for one record: the VLM passes plus the authority, never truncating it."""
    passes = [r for r in raw if not SP.is_authority(r)]
    authority = [r for r in raw if SP.is_authority(r)]
    raw = passes[:MAX_STORED_READINGS - len(authority[:1])] + authority[:1]
    out = []
    for i, r in enumerate(raw, 1):
        label = SP.AUTHORITY_READER if SP.is_authority(r) else f"{reader}/pass{i}"
        entry = {"reader": label, "name": clean_text(r.get("name") or "")}
        text = clean_text(r.get("description") or "")
        if text:
            entry["description"] = text
        if r.get("rank") is not None:
            entry["rank"] = r["rank"]
        out.append(entry)
    return out


def _missing_tabs(cls: str, tabs: dict) -> set[str]:
    trees = _tree_names().get(cls, set())
    return ({"general"} | trees) - set(tabs)


def _referenced_crops(out_dir: Path) -> set[str]:
    """Every review crop the published class files point at."""
    keep: set[str] = set()
    for f in sorted(out_dir.glob("*.json")):
        doc = json.loads(f.read_text())
        for s in doc["spells"]:
            keep.add(s["source"]["crop"])
            if s.get("iconCrop"):
                keep.add(s["iconCrop"])
            for t in s.get("tooltips") or []:
                keep.add(t["source"]["crop"])
    return keep


def _inventory_md(out_dir: Path, sdoc: dict, rdoc: dict) -> str:
    """data/extracted/spells.md: what exists, how sure we are and where it came from."""
    docs = [json.loads(p.read_text()) for p in sorted(out_dir.glob("*.json"))]
    total = sum(len(d["spells"]) for d in docs)
    tips = sum(len(s.get("tooltips") or []) for d in docs for s in d["spells"])
    new = sum(1 for d in docs for s in d["spells"] if s["classic"]["status"] == "new")
    never = sorted(set(CLASS_NAMES) - {d["class"] for d in docs})
    lines = [
        "# Spell lists and spellbook tooltips (stage 11, generated)",
        "",
        f"Generated {SK.now()} by `pipeline/stages/11_spellbook.py build` from "
        f"{sdoc['spellbook_frames']} spellbook frames ({len(sdoc['states'])} page states, "
        f"{len(rdoc['states'])} distinct pages read). Do not edit by hand; re-run the stage.",
        "",
        f"**{total} spell entries over {len(docs)} classes, {tips} full hover tooltips, "
        f"{new} names with no Classic Era counterpart.** Classes never shown on stream: "
        + (", ".join(CLASS_NAMES[c] for c in never) if never else "none") + ".",
        "",
        "## Coverage",
        "",
        "| Class | Pages seen | Tabs missing | Entries | Tooltips | Show all ranks | Min confidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in docs:
        cov = d["coverage"]
        confs = [s["source"]["confidence"] for s in d["spells"]]
        lines.append(f"| {d['className']} | {', '.join(cov['pagesSeen'])} | "
                     f"{', '.join(cov['tabsMissing']) or '-'} | {cov['entriesRead']} | "
                     f"{cov['tooltipsRead']} | {cov['showAllSpellRanks']} | "
                     f"{min(confs) if confs else '-'} |")
    lines += ["", "## Entries", "",
              "| Class | Tab | Spell | Rank(s) | Kind | vs Classic | Confidence | Stream time | Tooltip |",
              "|---|---|---|---|---|---|---|---|---|"]
    for d in docs:
        for s in d["spells"]:
            src = s["source"]
            ranks = ",".join(str(r) for r in s.get("ranksSeen") or []) or "-"
            lines.append(f"| {d['class']} | {s.get('tab') or '-'} | {s['name']} | {ranks} | {s['kind']} | "
                         f"{s['classic']['status']} | {src['confidence']} | {SK.hms(src['t'])} | "
                         f"{'yes' if s.get('tooltips') else '-'} |")
    lines += ["", "## Confidence", "",
              "`source.confidence` is the agreement of the two VLM passes (3x and 2x upscale) on the same "
              "crop: 1.0 identical, 0.7 same name but a different rank or kind, 0.3 otherwise. One column "
              "per page also went to the codex CLI as a third opinion; a codex reading that differs from "
              "two agreeing passes caps the row at 0.9.",
              "",
              "Nothing here is reviewed (`source.reviewed` is false everywhere). Review with "
              "`uv run python validate_spells.py --report ../data/spells/*.json` and the crops in "
              "`data/review/spells/<class>/`.",
              ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------- serializer

def canonical_spell_dumps(doc: dict) -> str:
    """The one spell serializer, which lives in ``validate_spells.py`` so ``--check`` compares bytes."""
    from validate_spells import canonical_dumps  # noqa: PLC0415
    return canonical_dumps(doc)


if __name__ == "__main__":
    app()

"""Stage 12: racial traits, lore and the race/class matrix from the character-creation windows.

Three commands, one per phase of ``docs/briefs/beyond-talents.md`` section (b):

``scan``   decodes the character-creation windows of the mkv at a few frames per
           second, keeps only frames showing the race picker, and reduces them to
           *panel states*: one crop per (race, scroll position) run, the sharpest
           frame of the run, at native resolution. The class bar is read from the
           same frames (no VLM: greyed-out icons are grey).
``read``   sends every state's race box to llama-server twice (3x and 2x cubic
           upscale, temperature 0, JSON schema) and turns the two readings into
           trait records with stage 5's agreement confidence. ``--codex`` adds a
           third opinion from the codex CLI on the states that disagree.
``build``  merges the states into one record per trait, diffs against
           ``data/prior/classic-era/racials.json``, writes ``data/races/<race>.json``,
           ``data/races/matrix.json``, the review crops and ``data/extracted/races.md``.

Undead never had its race box on screen; its four racials are listed on the
spellbook General page instead (``--undead-frame``), which gives names and the
"Racial"/"Racial Passive" subtitle but no description. Those records carry
``source.panel: "spellbook-general"`` and no ``description``.

Run from ``pipeline/`` with llama-server up (``scripts/llama-server.sh``)::

    uv run stages/12_races.py scan
    uv run stages/12_races.py scan --window 03:11:00-03:16:40 --fps 4
    uv run stages/12_races.py read
    uv run stages/12_races.py read --codex
    uv run stages/12_races.py build
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wowtalents import mkv as MK  # noqa: E402
from wowtalents import races as RC  # noqa: E402
from wowtalents import reader as RD  # noqa: E402
from wowtalents import fsio as _fsio  # noqa: E402
from wowtalents import ui  # noqa: E402
from wowtalents.fsio import write_json_atomic, write_text_atomic  # noqa: E402
from wowtalents.text import clean_text  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parent
WORK = PIPELINE / "work"
RACES_WORK = WORK / "races"
STATES_JSON = RACES_WORK / "states.json"
READINGS_JSON = RACES_WORK / "readings.json"
DATA = REPO / "data"
EXTRACTED = DATA / "extracted"
REVIEW = DATA / "review" / "races"
RACES_DIR = DATA / "races"
PRIOR = DATA / "prior" / "classic-era" / "racials.json"
PRIOR_DIFF = DATA / "prior" / "classic-era" / "racial-diff.json"

VIDEO_ID = RD.VIDEO_ID
FPS = RD.FPS

#: Every minute of 03:00:00-06:20:00 whose stage-0 probe frame shows both faction
#: banners, padded by a minute either side. 19420 and 21010 are not in the survey
#: in data/extracted/other-content.md; they were found by classifying all 541
#: probe frames and hold the Gnome and Tauren boxes at scroll positions the
#: documented windows never show.
WINDOWS: list[tuple[int, int]] = [
    (11460, 11800),   # 03:11:00-03:16:40
    (13440, 13620),   # 03:44:00-03:47:00
    (14580, 14760),   # 04:03:00-04:06:00
    (19360, 19500),   # 05:22:40-05:25:00
    (19740, 19880),   # 05:29:00-05:31:20
    (20950, 21100),   # 05:49:10-05:51:40
    (21900, 22260),   # 06:05:00-06:11:00
]

#: Undead's racials, from the spellbook General page of the Undead mage.
UNDEAD_FRAME = 15300
#: The list area of that page at 1920x1080 (three columns of entries on parchment).
UNDEAD_BOX = (300, 190, 940, 440)


def hms(t: float) -> str:
    s = int(t)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def parse_window(spec: str) -> tuple[int, int]:
    a, _, b = spec.partition("-")
    def p(x: str) -> int:
        x = x.strip()
        if ":" in x:
            parts = [int(v) for v in x.split(":")]
            while len(parts) < 3:
                parts.insert(0, 0)
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return int(x)
    return p(a), p(b)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def state_id(sel: RC.Selection, t: float) -> str:
    return f"{sel.key.replace('/', '-')}-{int(round(t))}"


# --------------------------------------------------------------------------- scan


@app.callback()
def _main():
    """Stage 12: racial traits and the race/class matrix."""


@app.command()
def scan(
    fps: int = typer.Option(2, help="frames per second analysed inside each window (must divide 60)"),
    window: list[str] = typer.Option(None, help="stream-time range HH:MM:SS-HH:MM:SS (repeatable); default: all"),
    mkv: Path = typer.Option(MK.MKV),
    offset: float = typer.Option(MK.OFFSET, help="file time minus stream time"),
    out: Path = typer.Option(RACES_WORK),
    max_hamming: int = typer.Option(6, help="dHash distance below which two frames are the same scroll position"),
    min_frames: int = typer.Option(2, help="frames a scroll position must survive to be kept"),
):
    """Find the distinct (race, scroll position) states in the character-creation windows."""
    wins = [parse_window(w) for w in window] if window else WINDOWS
    if MK.STREAM_FPS % fps:
        typer.echo(f"--fps must divide {MK.STREAM_FPS}", err=True)
        raise typer.Exit(code=2)
    if not mkv.is_file():
        typer.echo(f"no mkv at {mkv}", err=True)
        raise typer.Exit(code=2)
    (out / "crops").mkdir(parents=True, exist_ok=True)
    states: list[dict] = []
    bars: dict[str, dict] = {}
    wall = time.time()
    seen_frames = cc_frames = 0

    for t0, t1 in wins:
        typer.echo(f"window {hms(t0)}-{hms(t1)} at {fps} fps")
        run: dict | None = None

        def close(run: dict | None) -> None:
            if run and run["frames"] >= min_frames:
                states.append(_finish_run(run, out / "crops"))

        for t, frame in MK.decode_range(mkv, t0, t1, offset=offset, every=MK.STREAM_FPS // fps):
            seen_frames += 1
            if not RC.is_character_creation(frame):
                close(run)
                run = None
                continue
            cc_frames += 1
            sel = RC.selected_race(frame)
            if sel is None:
                close(run)
                run = None
                continue
            panel = RC.panel_crop(frame)
            h = ui.dhash(panel)
            sharp = ui.sharpness(panel)
            lit, margin = RC.class_availability(frame)
            cur = bars.get(sel.key)
            if cur is None or margin > cur["margin"]:
                bar = frame[RC.CLASS_BAR["y0"] - 8:RC.CLASS_BAR["y0"] + RC.CLASS_BAR["h"] + 30,
                            RC.CLASS_BAR["x0"] - 12:RC.CLASS_BAR["x0"] + RC.CLASS_BAR["pitch"] * 9 + 12]
                name = f"{sel.key.replace('/', '-')}-classbar.png"
                cv2.imwrite(str(out / "crops" / name), bar)
                bars[sel.key] = {"race": sel.race, "variant": sel.variant, "faction": sel.faction,
                                 "classes": lit, "margin": margin, "t": round(t, 3),
                                 "frame": int(round(t * FPS)), "crop": name}
            if run is not None and run["key"] == sel.key and ui.hamming(run["hash"], h) <= max_hamming:
                run["frames"] += 1
                run["t_end"] = round(t, 3)
                if sharp > run["sharpness"]:
                    run.update(sharpness=sharp, t=round(t, 3), hash=h,
                               panel=panel.copy(), box=RC.panel_box_crop(frame).copy())
                continue
            close(run)
            run = {"key": sel.key, "race": sel.race, "variant": sel.variant, "faction": sel.faction,
                   "hash": h, "sharpness": sharp, "t": round(t, 3), "t_start": round(t, 3),
                   "t_end": round(t, 3), "frames": 1, "score": sel.score, "margin": sel.margin,
                   "panel": panel.copy(), "box": RC.panel_box_crop(frame).copy()}
        close(run)
        typer.echo(f"  {len(states)} states so far ({time.time() - wall:.0f}s)")

    doc = {"generatedAt": now(), "video": VIDEO_ID, "fps": fps,
           "windows": [[a, b] for a, b in wins],
           "frames_seen": seen_frames, "character_creation_frames": cc_frames,
           "states": states, "class_bars": bars}
    write_json_atomic(out / "states.json", doc)
    typer.echo(f"{len(states)} panel states over {len(bars)} races -> {out / 'states.json'} "
               f"({time.time() - wall:.0f}s)")
    for key, b in sorted(bars.items()):
        typer.echo(f"  {key:24} classes {','.join(b['classes'])} (margin {b['margin']})")


def _finish_run(run: dict, crops: Path) -> dict:
    sid = state_id(RC.Selection(run["faction"], 0, run["race"], run["variant"], 0.0, 0.0), run["t"])
    panel_name, box_name = f"{sid}.panel.png", f"{sid}.box.png"
    cv2.imwrite(str(crops / panel_name), run["panel"])
    cv2.imwrite(str(crops / box_name), run["box"])
    bands = RC.trait_icon_bands(run["panel"])
    return {"id": sid, "race": run["race"], "variant": run["variant"], "faction": run["faction"],
            "t": run["t"], "t_start": run["t_start"], "t_end": run["t_end"], "frames": run["frames"],
            "frame": int(round(run["t"] * FPS)), "sharpness": round(run["sharpness"], 2),
            "hash": run["hash"], "panel_crop": panel_name, "box_crop": box_name,
            "icon_bands": [[a, b] for a, b in bands]}


# --------------------------------------------------------------------------- read


def distinct_states(states: list[dict], max_hamming: int) -> list[dict]:
    """The same scroll position recurs across windows; read the sharpest copy of each once."""
    keep: list[dict] = []
    for st in sorted(states, key=lambda s: -float(s.get("sharpness") or 0.0)):
        if any(k["race"] == st["race"] and k.get("variant") == st.get("variant")
               and ui.hamming(int(k["hash"]), int(st["hash"])) <= max_hamming for k in keep):
            continue
        keep.append(st)
    return sorted(keep, key=lambda s: (s["race"], s.get("variant") or "", s["t"]))


def codex_opinion(image: Path, out_dir: Path) -> dict | None:
    """Second opinion from the codex CLI on one race box crop (best effort)."""
    out = out_dir / (image.stem + ".codex.json")
    if out.is_file():
        try:
            return json.loads(out.read_text())
        except json.JSONDecodeError:
            out.unlink()
    prompt = (
        "The image is the race box of the World of Warcraft character-creation screen. "
        "Transcribe every racial trait row (round icon, then 'Name: description' or "
        "'Name (Passive): description'). Copy the text exactly; do not paraphrase. Ignore the "
        "lore paragraph and the race name. Do not create any file and do not explain. Your entire "
        "final message must be one JSON object and nothing else: "
        '{"traits":[{"name":"","kind":"Passive" or null,"description":"","cut_off":false}]}'
    )
    raw = out.with_suffix(".txt")
    try:
        subprocess.run(["codex", "exec", "--ephemeral", "--skip-git-repo-check",
                        "-o", str(raw), "-i", str(image), "-"],
                       input=prompt, text=True, capture_output=True, timeout=420, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    doc = _json_object(raw.read_text()) if raw.is_file() else None
    if doc is not None:
        _fsio.write_json_atomic(out, doc)
    return doc


def _json_object(text: str) -> dict | None:
    """The first balanced JSON object in a free-form CLI answer (fenced or bare)."""
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        doc = json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(doc, dict) and "traits" in doc:
                        return doc
                    break
        start = text.find("{", start + 1)
    return None


@app.command()
def read(
    states: Path = typer.Option(STATES_JSON),
    server: str = typer.Option(RD.DEFAULT_SERVER),
    out: Path = typer.Option(READINGS_JSON),
    limit: int = typer.Option(0, help="read at most N states (0 = all)"),
    only: str = typer.Option("", help="comma-separated race ids"),
    codex: str = typer.Option("off", help="codex CLI third opinion: off | disagree | race (one state per race) | all"),
    dedupe: int = typer.Option(6, help="dHash distance at which two states of one race are the same scroll position"),
    undead_frame: int = typer.Option(UNDEAD_FRAME, help="stream second of the Undead spellbook General page"),
    mkv: Path = typer.Option(MK.MKV),
    offset: float = typer.Option(MK.OFFSET),
):
    """Read every panel state twice with the VLM and write the trait readings."""
    if not states.is_file():
        typer.echo(f"no {states}; run `scan` first", err=True)
        raise typer.Exit(code=2)
    doc = json.loads(states.read_text())
    want = {s.strip() for s in only.split(",") if s.strip()}
    todo = distinct_states([s for s in doc["states"] if not want or s["race"] in want], dedupe)
    typer.echo(f"{len(doc['states'])} states -> {len(todo)} distinct scroll positions")
    if limit:
        todo = todo[:limit]
    rd = RD.Reader(server=server, cache_dir=WORK / "read" / "cache", max_tokens=1400)
    model = rd.model_name()
    crops = states.parent / "crops"
    codex_dir = states.parent / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    out_states: list[dict] = []
    codex_done: set[str] = set()
    wall = time.time()

    for i, st in enumerate(todo, 1):
        panel = cv2.imread(str(crops / st["panel_crop"]))
        if panel is None:
            typer.echo(f"  warn: missing crop {st['panel_crop']}")
            continue
        a = RC.clean_race_panel(rd.read_race_panel(panel, 3.0))
        b = RC.clean_race_panel(rd.read_race_panel(panel, 2.0))
        traits = _pair_traits(a["traits"], b["traits"])
        unit = f"{st['race']}/{st.get('variant') or ''}"
        want_codex = (codex == "all"
                      or (codex == "disagree" and any(t["confidence"] < 1.0 for t in traits))
                      or (codex == "race" and unit not in codex_done))
        extra = None
        if want_codex:
            codex_done.add(unit)
            extra = codex_opinion(crops / st["panel_crop"], codex_dir)
            if extra:
                traits = _apply_third(traits, [RC.normalise_trait(t) for t in (extra.get("traits") or [])])
        out_states.append({**{k: st[k] for k in ("id", "race", "variant", "faction", "t", "frame",
                                                 "sharpness", "panel_crop", "box_crop", "icon_bands")},
                           "race_name_read": a["race_name"] or b["race_name"],
                           "lore": a["lore"] if len(a["lore"]) >= len(b["lore"]) else b["lore"],
                           "lore_cut_off": bool(a["lore_cut_off"] and b["lore_cut_off"]),
                           "lore_agreement": 1.0 if RC.norm(a["lore"]) == RC.norm(b["lore"]) else 0.5,
                           "codex": bool(extra), "traits": traits})
        typer.echo(f"[{i}/{len(todo)}] {st['id']:28} {len(traits)} traits, "
                   f"{len(st['icon_bands'])} icons ({time.time() - wall:.0f}s)")

    undead = _read_undead(rd, mkv, undead_frame, offset, crops)
    write_json_atomic(out, {"generatedAt": now(), "reader": model, "server": server,
                            "prompt": RD.PROMPT_VERSION, "states": out_states, "undead": undead})
    typer.echo(f"{len(out_states)} states read by {model} in {time.time() - wall:.0f}s "
               f"({rd.calls} calls, {rd.cache_hits} cached) -> {out}")


def _pair_traits(a: list[dict], b: list[dict]) -> list[dict]:
    """Match the two passes by trait id and score their agreement."""
    by_id = {RC.trait_id(t["name"]): t for t in b if RC.trait_id(t["name"])}
    out = []
    for t in a:
        tid = RC.trait_id(t["name"])
        if not tid:
            continue
        other = by_id.pop(tid, None)
        out.append({**t, "confidence": RC.confidence(t, other),
                    "readings": [t] + ([other] if other else [])})
    for tid, t in by_id.items():   # seen only by the second pass
        out.append({**t, "confidence": 0.0, "readings": [t]})
    return out


def _apply_third(traits: list[dict], third: list[dict]) -> list[dict]:
    """A codex reading that matches one of the two passes lifts that trait's confidence."""
    by_id = {RC.trait_id(t["name"]): t for t in third if RC.trait_id(t["name"])}
    out = []
    for t in traits:
        c = by_id.get(RC.trait_id(t["name"]))
        if c is None:
            out.append(t)
            continue
        readings = t["readings"] + [c]
        best = max(RC.confidence(r, c) for r in t["readings"])
        conf = t["confidence"]
        if conf >= 1.0 and best < 1.0:
            conf = 0.9                      # both VLM passes agree, codex words it differently
        elif best >= 1.0:
            conf = max(conf, 0.85)          # two of three agree verbatim
        elif best >= 0.7:
            conf = max(conf, 0.7)
        out.append({**t, "confidence": conf, "readings": readings, "codex": True})
    for tid, c in by_id.items():
        if not any(RC.trait_id(t["name"]) == tid for t in traits):
            out.append({**c, "confidence": 0.3, "readings": [c], "codex": True})
    return out


def _read_undead(rd: RD.Reader, mkv: Path, second: int, offset: float, crops: Path) -> dict | None:
    """Undead's racials from the spellbook General page (names and subtitles only)."""
    sample = PIPELINE / "work" / "probe" / "extra" / f"{second}.png"
    frame = cv2.imread(str(sample)) if sample.is_file() else None
    if frame is None:
        for _, f in MK.decode_range(mkv, second, second + 0.2, fps=1, offset=offset, max_frames=1):
            frame = f
            break
    if frame is None:
        return None
    x0, y0, x1, y1 = UNDEAD_BOX
    crop = frame[y0:y1, x0:x1]
    name = f"undead-general-{second}.png"
    cv2.imwrite(str(crops / name), crop)
    a = rd.read_racial_list(crop, 3.0)
    b = rd.read_racial_list(crop, 2.0)
    def keep(doc: dict) -> list[dict]:
        out = []
        for e in doc.get("entries") or []:
            sub = clean_text(e.get("subtitle") or "").lower()
            if "racial" not in sub:
                continue
            out.append({"name": clean_text(e.get("name") or ""),
                        "kind": "passive" if "passive" in sub else "active"})
        return out
    ka, kb = keep(a), keep(b)
    agree = {(RC.trait_id(x["name"]), x["kind"]) for x in ka} == {(RC.trait_id(x["name"]), x["kind"]) for x in kb}
    return {"t": float(second), "frame": second * FPS, "crop": name,
            "confidence": 1.0 if agree else 0.5, "traits": ka or kb,
            "readings": {"pass3x": ka, "pass2x": kb}}


# --------------------------------------------------------------------------- build


def _source(t: float, frame: int, crop: str, conf: float, reader: str, panel: str = "race-panel",
            readings: list[dict] | None = None, note: str | None = None) -> dict:
    src: dict = {"kind": "video", "video": VIDEO_ID, "t": round(float(t), 3), "frame": int(frame),
                 "crop": crop, "panel": panel, "confidence": round(float(conf), 2), "reader": reader}
    if readings:
        src["readings"] = readings
    src["reviewed"] = False
    if note:
        src["note"] = note
    return src


def _prior() -> tuple[dict, dict]:
    """``(Classic racials, hand verdicts)``; either may be empty, in which case nothing is claimed."""
    races = json.loads(PRIOR.read_text()).get("races") or {} if PRIOR.is_file() else {}
    diff = json.loads(PRIOR_DIFF.read_text()).get("races") or {} if PRIOR_DIFF.is_file() else {}
    return races, diff


UNVERIFIED = ("Classic side written from memory and unverified "
              "(data/prior/classic-era/racials.json)")


def _classic_for(prior: tuple[dict, dict], race: str, trait: dict) -> dict:
    """Status of one Forever trait against the hand-written Classic Era prior.

    "new" is the only verdict the data can carry on its own (the name is not in
    the Classic racial list). "same" and "changed" are the hand verdicts in
    racial-diff.json, because racials.json holds paraphrases and a text diff of a
    paraphrase says "changed" every time. Without a verdict the status is
    "unknown" rather than a guess.
    """
    races, diff = prior
    entry = races.get(race) or {}
    entries = entry.get("traits") or []
    tid = RC.trait_id(trait["name"])
    match = next((e for e in entries if RC.trait_id(e["name"]) == tid), None)
    if not entries:
        return {"status": "new", "note": entry.get("note") or "no Classic Era counterpart for this race"}
    if match is None:
        return {"status": "new", "note": f"no Classic Era racial called {trait['name']} for this race"}
    out = {"status": "unknown", "classicName": match["name"], "classicText": match["description"]}
    verdict = (diff.get(race) or {}).get(tid)
    notes = [UNVERIFIED]
    if verdict:
        out["status"] = verdict["status"]
        if verdict.get("note"):
            notes.insert(0, verdict["note"])
    else:
        notes.insert(0, "no hand verdict yet; compare the texts yourself")
    if trait.get("kind") != match.get("kind"):
        notes.insert(0, f"Classic Era version is {match.get('kind')}")
    out["note"] = "; ".join(notes)
    return out


def _unit_key(st: dict) -> tuple[str, str | None]:
    return st["race"], st.get("variant")


@app.command()
def build(
    readings: Path = typer.Option(READINGS_JSON),
    states: Path = typer.Option(STATES_JSON),
    out_dir: Path = typer.Option(RACES_DIR),
    review: Path = typer.Option(REVIEW),
    min_confidence: float = typer.Option(0.0, help="drop trait readings below this confidence"),
):
    """Merge the panel states into data/races/<race>.json plus matrix.json and the review crops."""
    if not readings.is_file():
        typer.echo(f"no {readings}; run `read` first", err=True)
        raise typer.Exit(code=2)
    rdoc = json.loads(readings.read_text())
    sdoc = json.loads(states.read_text())
    reader = rdoc.get("reader") or "unknown"
    crops = states.parent / "crops"
    prior = _prior()
    out_dir.mkdir(parents=True, exist_ok=True)

    per_unit: dict[tuple[str, str | None], dict] = {}
    for st in rdoc["states"]:
        unit = per_unit.setdefault(_unit_key(st), {"records": [], "sequences": [], "lore": None,
                                                   "saw_top": False, "saw_lore": False})
        traits = [RC.normalise_trait(t) | {"confidence": t["confidence"],
                                            "readings": t.get("readings") or [],
                                            "codex": bool(t.get("codex"))}
                  for t in st["traits"] if t["confidence"] >= min_confidence]
        unit["sequences"].append([RC.trait_id(t["name"]) for t in traits])
        unit["saw_top"] = unit["saw_top"] or bool(st.get("race_name_read"))
        unit["saw_lore"] = unit["saw_lore"] or bool(st.get("lore"))
        panel = cv2.imread(str(crops / st["panel_crop"]))
        bands = [tuple(b) for b in st.get("icon_bands") or []]
        pairs = RC.align_bands(bands, [RC.normalise_trait(x) for x in st["traits"]])
        blocks = dict(zip((i for i, _ in pairs), RC.trait_blocks([b for _, b in pairs]))) if pairs else {}
        band_of = dict(pairs)
        by_id = {RC.trait_id(t["name"]): i for i, t in enumerate(st["traits"])}
        for t in traits:
            tid = RC.trait_id(t["name"])
            k = by_id.get(tid)
            unit["records"].append({
                "id": tid, "name": t["name"], "kind": t["kind"],
                "description": clean_text(t["description"]), "cut_off": bool(t["cut_off"]),
                "variants": [st["variant"]] if st.get("variant") else [],
                "state": st["id"], "t": st["t"], "frame": st["frame"],
                "sharpness": st["sharpness"], "codex": bool(t.get("codex")),
                "block": list(blocks[k]) if k in blocks else None,
                "icon_band": list(band_of[k]) if k in band_of else None,
                "source": {"confidence": t["confidence"], "sharpness": st["sharpness"],
                           "t": st["t"], "frame": st["frame"], "state": st["id"]},
                "readings": t.get("readings") or []})
        if blocks and panel is not None:
            norm_traits = [RC.normalise_trait(x) for x in st["traits"]]
            _write_block_crops(panel, [(norm_traits[k], blocks[k], band_of[k]) for k in sorted(blocks)],
                               st["race"], review)
        if panel is not None:
            box = cv2.imread(str(crops / st["box_crop"]))
            if box is not None and (st.get("race_name_read") or unit["lore"] is None):
                cv2.imwrite(str(_ensure(review / st["race"]) / "_panel.png"), box)
        if st.get("lore"):
            cur = unit["lore"]
            if cur is None or len(st["lore"]) > len(cur["text"]):
                unit["lore"] = {"text": clean_text(st["lore"]), "cut_off": bool(st.get("lore_cut_off")),
                                "t": st["t"], "frame": st["frame"],
                                "confidence": st.get("lore_agreement", 0.5)}

    undead_extra = rdoc.get("undead")
    if undead_extra and (crops / undead_extra["crop"]).is_file():
        shutil.copyfile(crops / undead_extra["crop"], _ensure(review / "undead") / "_general.png")
    bars = sdoc.get("class_bars") or {}
    matrix: dict[str, dict] = {}
    counts: dict[str, int] = {}
    for race in sorted({r for r, _ in per_unit} | {k.split("/")[0] for k in bars}):
        units = {v: u for (r, v), u in per_unit.items() if r == race}
        doc, mrow = _race_doc(race, units, bars, prior, reader, review, undead_extra, crops)
        write_text_atomic(out_dir / f"{race}.json", canonical_race_dumps(doc))
        matrix[race] = mrow
        counts[race] = len(doc["traits"])
    write_text_atomic(out_dir / "matrix.json", canonical_race_dumps(_matrix_doc(matrix, bars)))
    write_json_atomic(EXTRACTED / "races.json",
                      {"generatedAt": now(), "video": VIDEO_ID, "reader": reader,
                       "states": len(rdoc["states"]), "traits": counts,
                       "candidates": {f"{r}/{v}" if v else r: u["records"]
                                      for (r, v), u in sorted(per_unit.items(), key=lambda kv: (kv[0][0], kv[0][1] or ""))}})
    gone = _prune_crops(out_dir, review)
    write_text_atomic(EXTRACTED / "races.md", _inventory_md(out_dir, sdoc, rdoc))
    for g in gone:
        typer.echo(f"  removed unreferenced crop {g}")
    typer.echo(f"wrote {len(counts)} race files ({sum(counts.values())} traits), matrix.json, "
               f"data/extracted/races.json and data/extracted/races.md")
    for race, n in sorted(counts.items()):
        typer.echo(f"  {race:12} {n} traits")


def _ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _prune_crops(out_dir: Path, review: Path) -> list[str]:
    """Delete row and icon crops no race file names any more.

    A fragment ("damage-to-beasts") gets a crop written before the merge knows it
    is a fragment. Files whose name starts with ``_`` are the box, class bar and
    spellbook evidence that the notes and docs point at, and are kept.
    """
    keep: set[str] = set()
    for f in sorted(out_dir.glob("*.json")):
        if f.stem == "matrix":
            continue
        doc = json.loads(f.read_text())
        for t in doc["traits"]:
            keep.add(t["source"]["crop"])
            if t.get("iconCrop"):
                keep.add(t["iconCrop"])
        for k in ("classesSource", "loreSource"):
            if doc.get(k):
                keep.add(doc[k]["crop"])
    gone = []
    for png in sorted(review.rglob("*.png")):
        if png.name.startswith("_"):
            continue
        rel = str(png.relative_to(REPO))
        if rel not in keep:
            png.unlink()
            gone.append(rel)
    return gone


def _inventory_md(out_dir: Path, sdoc: dict, rdoc: dict) -> str:
    """data/extracted/races.md: what exists, how sure we are and where it came from."""
    docs = [json.loads(p.read_text()) for p in sorted(out_dir.glob("*.json")) if p.stem != "matrix"]
    total = sum(len(d["traits"]) for d in docs)
    status: dict[str, int] = {}
    for d in docs:
        for t in d["traits"]:
            k = t["classic"]["status"]
            status[k] = status.get(k, 0) + 1
    lines = [
        "# Racial traits and the race/class matrix (stage 12, generated)",
        "",
        f"Generated {now()} by `pipeline/stages/12_races.py build` from "
        f"{sdoc['character_creation_frames']} character-creation frames "
        f"({len(sdoc['states'])} panel states, {len(rdoc['states'])} distinct scroll positions read). "
        "Do not edit by hand; re-run the stage.",
        "",
        f"**{total} traits over {len(docs)} races**, "
        + ", ".join(f"{n} {k}" for k, n in sorted(status.items())) + " versus Classic Era.",
        "",
        "## Per race",
        "",
        "| Race | Faction | Traits | Complete | Min confidence | Classes | Lore |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in docs:
        confs = [t["source"]["confidence"] for t in d["traits"]]
        lore = "yes" if d.get("lore") or any(v.get("lore") for v in d.get("variants") or []) else "-"
        if d.get("loreComplete") is False:
            lore = "partial"
        lines.append(f"| {d['raceName']} | {d['faction']} | {len(d['traits'])} | "
                     f"{'yes' if d['complete'] else 'no'} | {min(confs) if confs else '-'} | "
                     f"{len(d['classes'])} | {lore} |")
    lines += ["", "## Traits", "",
              "| Race | # | Trait | Kind | vs Classic | Confidence | Stream time | Crop |",
              "|---|---|---|---|---|---|---|---|"]
    for d in docs:
        for t in d["traits"]:
            src = t["source"]
            lines.append(f"| {d['race']} | {t['order']} | {t['name']} | {t['kind']} | "
                         f"{t['classic']['status']} | {src['confidence']} | {hms(src['t'])} | "
                         f"`{src['crop'].split('/')[-1]}` |")
    lines += ["", "## Race/class matrix", "",
              "| Race | " + " | ".join(c.title() for c in RC.CLASS_ORDER) + " |",
              "|---|" + "---|" * len(RC.CLASS_ORDER)]
    matrix = json.loads((out_dir / "matrix.json").read_text())
    for row in matrix["races"]:
        cells = ["x" if c in row["classes"] else "." for c in RC.CLASS_ORDER]
        lines.append(f"| {row['raceName']} | " + " | ".join(cells) + " |")
    lines += ["",
              "Skyborne differs by variant: High Order (Alliance) has Mage and no Shaman, "
              "Windshaper (Horde) has Shaman and no Mage. The row above is the union.",
              "",
              "## Confidence",
              "",
              "`source.confidence` is the agreement of the two VLM passes (3x and 2x upscale) on the "
              "same crop, 1.0 identical / 0.7 same name and kind / 0.3 otherwise. One scroll position "
              "per race also went to the codex CLI as a third opinion; a codex reading that differs "
              "from two agreeing passes caps the trait at 0.9.",
              "",
              "Nothing here is reviewed (`source.reviewed` is false everywhere). Review with "
              "`uv run python validate_races.py --report ../data/races/*.json` and the crops in "
              "`data/review/races/<race>/`.",
              ""]
    return "\n".join(lines)


def _write_block_crops(panel, rows, race: str, review: Path) -> None:
    """Per-trait review crops: the text block and the icon, at native resolution."""
    d = _ensure(review / race)
    px0, py0, _, _ = RC.PANEL
    ix0, ix1 = RC.ICON_COLUMN
    for t, (b0, b1), (i0, i1) in rows:
        tid = RC.trait_id(t["name"])
        if not tid or t.get("cut_off"):
            continue
        block = panel[b0 - py0:b1 - py0, :]
        old = d / f"{tid}.png"
        prev = cv2.imread(str(old)) if old.is_file() else None
        if prev is not None and prev.shape[0] >= block.shape[0] and ui.sharpness(prev) >= ui.sharpness(block):
            continue
        cv2.imwrite(str(d / f"{tid}.png"), block)
        cv2.imwrite(str(d / f"{tid}.icon.png"), panel[i0 - py0:i1 - py0, ix0 - px0:ix1 - px0])


def _variant_name(variant: str, race: str) -> str:
    return f"{variant.replace('-', ' ').title()} {RC.RACE_NAMES[race]}"


def _race_doc(race: str, units: dict, bars: dict, prior: dict, reader: str, review: Path,
              undead_extra: dict | None, crops: Path) -> tuple[dict, dict]:
    keys = sorted(k for k in bars if k.split("/")[0] == race)
    variants = []
    for k in keys:
        b = bars[k]
        if b.get("variant"):
            variants.append({"id": b["variant"], "name": _variant_name(b["variant"], race),
                             "faction": b["faction"], "classes": b["classes"]})
    factions = sorted({bars[k]["faction"] for k in keys}) or ["neutral"]
    faction = factions[0] if len(factions) == 1 else "neutral"
    classes = sorted({c for k in keys for c in bars[k]["classes"]})

    records, fragments = RC.drop_fragments(r for u in units.values() for r in u["records"])
    dropped_ids = {r["id"] for r in fragments} - {r["id"] for r in records}
    order = [tid for tid in RC.stitch_order([s for u in units.values() for s in u["sequences"]])
             if tid not in dropped_ids]
    merged = RC.merge_traits(records, order)
    complete = bool(merged) and all(u["saw_top"] and u["saw_lore"] for u in units.values())

    seen_ids = {r["id"] for r in merged}
    extra_note = None
    if race == "undead" and undead_extra:
        cross = [RC.trait_id(t["name"]) for t in undead_extra.get("traits") or []]
        missing = [t for t in (undead_extra.get("traits") or []) if RC.trait_id(t["name"]) not in seen_ids]
        if cross:
            extra_note = ("cross-checked against the spellbook General page of the Undead mage at 04:15:00, "
                          f"which lists {', '.join(sorted(cross))}")
        for t in missing:   # a racial the box never scrolled to, but the spellbook names
            merged.append({"id": RC.trait_id(t["name"]), "name": RC.strip_kind(t["name"]), "kind": t["kind"],
                           "description": "", "cut_off": False, "variants": [],
                           "source": {"confidence": undead_extra["confidence"], "sharpness": 0.0,
                                      "t": undead_extra["t"], "frame": undead_extra["frame"],
                                      "state": "undead-general", "panel": "spellbook-general"},
                           "readings": []})

    traits = []
    for rec in merged:
        tid = rec["id"]
        conf = float(rec["source"]["confidence"])
        panel_kind = rec["source"].get("panel", "race-panel")
        note = None
        crop = f"data/review/races/{race}/{tid}.png"
        if panel_kind == "spellbook-general":
            crop = f"data/review/races/{race}/_general.png"
            note = ("read from the spellbook General page, which gives the name and the Racial subtitle "
                    "but no description; the race box never scrolled to this row")
        elif not (review / race / f"{tid}.png").is_file():
            crop = f"data/review/races/{race}/_panel.png"
            note = "no clean single-row crop; the whole box is the evidence"
        if rec.get("cut_off"):
            note = ((note + "; ") if note else "") + "best crop still clipped by the box edge"
        t: dict = {"id": tid, "name": rec["name"], "kind": rec["kind"],
                   "order": order.index(tid) if tid in order else len(order) + len(traits)}
        if variants:
            t["variants"] = sorted(rec.get("variants") or [v["id"] for v in variants])
        if rec["description"]:
            t["description"] = rec["description"]
        if (review / race / f"{tid}.icon.png").is_file():
            t["icon"] = f"crop-{tid}"
            t["iconSource"] = "crop"
            t["iconCrop"] = f"data/review/races/{race}/{tid}.icon.png"
        t["classic"] = _classic_for(prior, race, rec)
        tag = {"new": "new", "changed": "reworked", "same": "classic-unchanged"}.get(t["classic"]["status"])
        if tag:
            t["tags"] = [tag]
        rs = [{"reader": f"{reader}/pass{i}", "name": RC.strip_kind(r.get("name") or ""),
               "description": clean_text(r.get("description") or ""), "confidence": conf}
              for i, r in enumerate(rec.get("readings") or [], 1)]
        t["source"] = _source(rec["source"]["t"], rec["source"]["frame"], crop, conf, reader,
                              panel_kind, rs[:3], note)
        traits.append(t)

    notes: list[str] = []
    if variants:
        notes.append("Skyborne is one race with an Alliance variant (High Order) and a Horde variant "
                     "(Windshaper). Shared traits carry both variant ids; the class lists differ, see "
                     "variants[].classes.")
    if race == "undead":
        notes.append("The survey in data/extracted/other-content.md says the Undead race box was never on "
                     "screen. It was: 05:23:40-05:24:20 and 03:15:06, windows the 60 s probe grid missed.")
        if extra_note:
            notes.append(f"Traits {extra_note}.")
    if not complete:
        notes.append("Not every scroll position was seen; the trait list may be short of a row.")
    if any(t["source"].get("note") for t in traits):
        notes.append("Traits with a source note were read from a clipped or shared crop; check the crop "
                     "before quoting them.")
    notes.append("BlizzCon demo build 2026-09-12, read from stream video; nothing here is reviewed.")

    doc: dict = {"$schema": "../schema/race.schema.json", "schemaVersion": 1, "race": race,
                 "raceName": RC.RACE_NAMES[race], "faction": faction, "dataSource": "video",
                 "generatedAt": now()}
    if variants:
        doc["variants"] = variants
    doc["classes"] = classes
    if keys:
        b = bars[sorted(keys)[0]]
        src = crops / b["crop"]
        if src.is_file():
            shutil.copyfile(src, _ensure(review / race) / "_classbar.png")
        doc["classesSource"] = _source(b["t"], b["frame"], f"data/review/races/{race}/_classbar.png",
                                       1.0 if b["margin"] >= 5 else 0.5, "opencv-classbar", "class-bar",
                                       None, f"lit/greyed separation margin {b['margin']}")
    lore_units = [(v, u["lore"]) for v, u in sorted(units.items(), key=lambda kv: kv[0] or "") if u["lore"]]
    if lore_units:
        if variants:
            for v, lo in lore_units:
                for entry in doc["variants"]:
                    if entry["id"] == v:
                        entry["lore"] = lo["text"]
                        entry["loreComplete"] = not lo["cut_off"]
        else:
            lo = max((l for _, l in lore_units), key=lambda l: len(l["text"]))
            doc["lore"] = lo["text"]
            doc["loreComplete"] = not lo["cut_off"]
            doc["loreSource"] = _source(lo["t"], lo["frame"], f"data/review/races/{race}/_panel.png",
                                        lo["confidence"], reader, "race-panel", None,
                                        None if not lo["cut_off"] else "paragraph continues past the box edge")
    doc["traits"] = traits
    doc["complete"] = complete
    doc["notes"] = notes

    mrow = {"faction": faction, "classes": classes,
            "byVariant": {v["id"]: v["classes"] for v in variants} if variants else None}
    return doc, mrow


#: Race/class combinations Warcraft Tavern reported after the reveal
#: (docs/research/2026-09-13-talent-system.md section 2). It published no full table,
#: only these call-outs, so the cross-check is one-directional.
TAVERN_REPORTED = {
    "undead": ["paladin"],
    "dwarf": ["shaman"],
    "tauren": ["shaman", "druid"],
}


def _matrix_doc(matrix: dict, bars: dict) -> dict:
    rows = []
    for race in sorted(matrix):
        row = {"race": race, "raceName": RC.RACE_NAMES[race], "faction": matrix[race]["faction"],
               "classes": matrix[race]["classes"]}
        if matrix[race]["byVariant"]:
            row["byVariant"] = matrix[race]["byVariant"]
        row["observed"] = bool(matrix[race]["classes"])
        reported = TAVERN_REPORTED.get(race)
        if reported:
            row["reportedElsewhere"] = reported
            missing = [c for c in reported if c not in matrix[race]["classes"]]
            if missing:
                row["disagreement"] = (f"Warcraft Tavern reports {race} {'/'.join(missing)}; "
                                       "the class bar on stream does not light it")
            else:
                row["agreement"] = "confirmed on screen"
        rows.append(row)
    return {"$schema": "../schema/race-matrix.schema.json", "schemaVersion": 1, "dataSource": "video",
            "generatedAt": now(), "classes": RC.CLASS_ORDER, "races": rows,
            "notes": ["Read from the lit/greyed class icons under the character preview; no VLM involved.",
                      "Cross-checked against the combinations Warcraft Tavern reported "
                      "(docs/research/2026-09-13-talent-system.md); disagreements are recorded per race."]}


# --------------------------------------------------------------------------- serializer

def canonical_race_dumps(doc: dict) -> str:
    """The one race serializer, which lives in ``validate_races.py`` so ``--check`` compares bytes."""
    sys.path.insert(0, str(PIPELINE))
    from validate_races import canonical_dumps  # noqa: PLC0415
    return canonical_dumps(doc)


if __name__ == "__main__":
    app()

"""Derive stage 11's spellbook windows from the whole-VOD keyframe sweep.

Stage 11 used to take its window table from the 541 stage-0 probe minutes, so a
spellbook open for less than a probe step was invisible to it: the 1 fps
keyframe sweep of 2026-09-14 (``docs/handover/2026-09-14-priest-search.md``)
found **50** spellbook runs in the 8.5 h VOD, 21 of them outside that table.

This script turns the sweep's per-frame title-bar scores into
``work/spells/windows.json``, which ``11_spellbook.py scan --windows`` reads.

Two things are *not* derivable from the sweep and stay hand-written here:

``ANCHORS``  the 15 ranges stage 11 already scanned. They are copied through
             byte-identical, because a state id is ``<class>-<round(t)>`` of the
             frames a window contains: widening an existing range would rename
             every state in it, orphan its review crops and cost another full
             VLM read. New windows are therefore clipped against the anchors
             and never overlap them.
``LABELS``   the demo character's class per stream range. The spellbook never
             names the class; it was read off the page headings, the tab-strip
             icons and the General page's racials of the sweep crops in
             ``work/priest-search/new-windows/``. ``scan`` keeps the label,
             ``read`` cross-checks it against the page heading and reassigns a
             state whose heading names exactly one other class's tab.

Run from ``pipeline/``::

    uv run python scripts/spell_windows.py                       # write work/spells/windows.json
    uv run python scripts/spell_windows.py --check               # report, write nothing
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from wowtalents import stagekit as SK
from wowtalents.fsio import write_json_atomic

PIPELINE = Path(__file__).resolve().parents[1]
SWEEP = PIPELINE / "work" / "priest-search" / "full-stream.json"
OUT = PIPELINE / "work" / "spells" / "windows.json"

#: Title-bar correlation at which a keyframe counts as "the spellbook is open".
#: The sweep measured 842 frames >= 0.95, 34 in 0.90-0.95 and 2 in 0.85-0.90:
#: there is no ambiguous band, so the exact cut does not matter. 0.90 reproduces
#: the 876 frames / 50 runs of the report.
SCORE = 0.90
#: Seconds of missing keyframes that still count as one continuous opening.
GAP = 5
#: Seconds added either side of a run, as the hand-built table did.
PAD = 30

#: The window table stage 11 shipped with, unchanged. ``(t0, t1, class, note)``.
ANCHORS: list[tuple[int, int, str, str]] = [
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

#: Class of the demo character per stream range, for the runs no anchor covers.
#: Every entry was read off the sweep crop named in the note.
LABELS: list[tuple[int, int, str, str]] = [
    (12200, 12450, "mage", "level-1 Skyborne mage: General page with the four Skyborne racials "
                           "(Walk on Air, Read Ley Line, Elemental Insight, Wind Blessed); "
                           "tab strip is General + Arcane + Fire only"),
    (12450, 12700, "mage", "level-1 Skyborne mage: Fire page, Fireball Rank 1 alone"),
    (12900, 13100, "mage", "level-1 Skyborne mage: Fire page, Fireball Rank 1 alone"),
    (15500, 15660, "mage", "Undead mage in the dungeon demo: Frost page (Frostbolt 1-7, Blizzard 1-3) "
                           "and the Undead General page"),
    (15660, 15800, "mage", "Undead mage: Frost page"),
    (16600, 16739, "mage", "Undead mage: Frost page"),
    (16739, 16900, "mage", "Undead mage: Arcane page 2/2 (Conjure Water/Food, Dampen Magic, Mage Armor, "
                           "Mana Shield, Polymorph, Slow Fall); page 2 shows no heading"),
    (17100, 17300, "mage", "Undead mage: Frost page"),
    (20560, 20620, "druid", "Tauren druid: General page (War Stomp, Cultivation, Endurance, "
                            "Plainsrunning); druid tab strip, inside what the old table called "
                            "the Orc shaman window"),
    (20800, 20890, "druid", "Tauren druid: General page"),
    (21400, 21500, "rogue", "Troll rogue: General page (Pick Lock, Berserking, Rapid Regeneration, "
                            "Beast Slaying, Dual Wield)"),
    (21800, 22000, "druid", "Skyborne druid: General page with the full Skysight racial tooltip"),
    (22180, 22300, "rogue", "Night Elf rogue: General page with the Elune's Light racial tooltip"),
    (22480, 22620, "warrior", "warrior: 'Shield Wall' exact-match and 'Retaliation' name-match "
                              "search pages"),
    (22720, 22760, "warrior", "warrior: the tail of the 'thunder clap' opening and the head of the "
                              "'whirl' one, between the two anchored warrior windows"),
    (22840, 23000, "warlock", "warlock Demonology page with the Summon Succubus tooltip - 90 s after "
                              "the 06:20 source-window cutoff"),
]


def runs(sweep: Path, score: float = SCORE, gap: int = GAP) -> list[tuple[float, float]]:
    """Continuous spellbook openings in the sweep, as ``(t0, t1)`` stream seconds."""
    doc = json.loads(sweep.read_text(encoding="utf-8"))
    out: list[list[float]] = []
    for row in doc["hits"]:
        t, full = row[0], row[1]
        if full < score:
            continue
        if out and t - out[-1][1] <= gap:
            out[-1][1] = t
        else:
            out.append([t, t])
    return [(a, b) for a, b in out]


def _subtract(seg: tuple[float, float], blocks: list[tuple[int, int]]) -> list[tuple[float, float]]:
    parts = [seg]
    for a, b in blocks:
        nxt: list[tuple[float, float]] = []
        for x0, x1 in parts:
            if x1 <= a or x0 >= b:
                nxt.append((x0, x1))
                continue
            if x0 < a:
                nxt.append((x0, a))
            if x1 > b:
                nxt.append((b, x1))
        parts = nxt
    return parts


def label_for(t0: float, t1: float) -> tuple[str, str]:
    for a, b, cls, note in LABELS:
        if a <= t0 < b or a < t1 <= b:
            return cls, note
    return "unknown", "no hand label for this range; scan will not know the class"


def derive(sweep: Path, pad: int = PAD, score: float = SCORE,
           gap: int = GAP) -> tuple[list[tuple[int, int, str, str]], list[tuple[float, float]]]:
    """``(windows, runs)``: the anchors plus one window per uncovered run, merged."""
    found = runs(sweep, score, gap)
    anchor_spans = [(a, b) for a, b, _, _ in ANCHORS]
    extra: list[list[float]] = []
    for t0, t1 in found:
        for u0, u1 in _subtract((t0, t1), anchor_spans):
            for p0, p1 in _subtract((u0 - pad, u1 + pad), anchor_spans):
                if p1 - p0 < 2:
                    continue
                if extra and p0 <= extra[-1][1]:
                    extra[-1][1] = max(extra[-1][1], p1)
                else:
                    extra.append([p0, p1])
    extra.sort()
    merged: list[list[float]] = []
    for p0, p1 in extra:
        if merged and p0 <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], p1)
        else:
            merged.append([p0, p1])
    windows = list(ANCHORS)
    for p0, p1 in merged:
        cls, note = label_for(p0, p1)
        windows.append((int(round(p0)), int(round(p1)), cls, note))
    windows.sort()
    return windows, found


def document(sweep: Path, pad: int = PAD, score: float = SCORE, gap: int = GAP) -> dict:
    windows, found = derive(sweep, pad, score, gap)
    covered = sum(1 for t0, t1 in found
                  if any(a <= t0 and t1 <= b for a, b, _, _ in windows)
                  or not _subtract((t0, t1), [(a, b) for a, b, _, _ in windows]))
    return {
        "generatedAt": SK.now(),
        "video": "xaryu-blizzcon-day1",
        "source": "whole-VOD keyframe sweep, 1 fps over 30798 keyframes "
                  "(work/priest-search/full-stream.json, see docs/handover/2026-09-14-priest-search.md)",
        "score": score,
        "gap": gap,
        "pad": pad,
        "runs": len(found),
        "runsCovered": covered,
        "anchors": len(ANCHORS),
        "windows": [{"t0": t0, "t1": t1, "class": cls, "note": note} for t0, t1, cls, note in windows],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sweep", type=Path, default=SWEEP, help="per-frame sweep scores")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--pad", type=int, default=PAD)
    ap.add_argument("--score", type=float, default=SCORE)
    ap.add_argument("--gap", type=int, default=GAP)
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args()
    if not args.sweep.is_file():
        print(f"no sweep at {args.sweep}")
        return 2
    doc = document(args.sweep, args.pad, args.score, args.gap)
    new = [w for w in doc["windows"] if (w["t0"], w["t1"]) not in {(a, b) for a, b, _, _ in ANCHORS}]
    print(f"{doc['runs']} spellbook runs, {doc['runsCovered']} covered by "
          f"{len(doc['windows'])} windows ({len(ANCHORS)} anchors + {len(new)} new)")
    for w in new:
        print(f"  {SK.hms(w['t0'])}-{SK.hms(w['t1'])}  {w['class']:8} {w['note'][:64]}")
    unknown = [w for w in doc["windows"] if w["class"] == "unknown"]
    for w in unknown:
        print(f"  warn: no label for {SK.hms(w['t0'])}-{SK.hms(w['t1'])}")
    if args.check:
        return 1 if unknown or doc["runsCovered"] != doc["runs"] else 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.out, doc)
    print(f"-> {args.out.relative_to(PIPELINE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

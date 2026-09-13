"""Character-creation screen: selected race, racial trait panel, class bar.

Phase 2b (``docs/briefs/beyond-talents.md`` section (b)) reuses stage 4/5's
machinery but not its geometry: the character-creation screen has no talent
grid. What it has is fixed furniture at 1920x1080, measured 2026-09-13 from
the stage-0 native samples in ``work/probe/extra/``:

* two faction columns of five race portraits each on the left; the selected
  portrait carries a bright gold frame (border mean ~125 against ~58 for the
  others, measured over 22 frames), which is how we know *which* race the
  panel describes -- no VLM call needed;
* three stacked boxes on the right, of which the middle one is the race box:
  race name, the gold heading "Racial Traits", one row per trait (round icon
  in a fixed column plus a wrapped "Name: description" line), then the lore
  paragraph. The box scrolls, so one frame shows three or four of four to six
  traits and the rest arrives from another scroll position;
* a nine-slot class bar at the bottom whose greyed-out icons are the classes
  the race cannot play.

Everything here is pure: pixels in, numbers or strings out. The stage driver
(``stages/12_races.py``) owns ffmpeg, the VLM and the files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

import cv2
import numpy as np

from .text import clean_text, slug

__all__ = [
    "FACTION_COLUMNS", "RACE_SLOTS", "SKYBORNE_VARIANT", "RACE_NAMES", "CLASS_ORDER",
    "PANEL", "PANEL_BOX", "ICON_COLUMN", "TEXT_COLUMN", "CLASS_BAR",
    "Selection", "is_character_creation", "selected_race", "race_of_slot",
    "class_availability", "panel_crop", "panel_box_crop", "trait_icon_bands",
    "trait_blocks", "parse_trait_line", "trait_kind", "trait_id", "strip_kind",
    "normalise_trait", "clean_race_panel", "merge_traits", "reading_key",
    "confidence", "variant_of", "norm", "drop_fragments", "stitch_order", "align_bands",
]

# --------------------------------------------------------------------------- geometry (1920x1080)

FRAME_W, FRAME_H = 1920, 1080

#: x-range of each faction's portrait column.
FACTION_COLUMNS: dict[str, tuple[int, int]] = {"alliance": (36, 124), "horde": (207, 295)}
PORTRAIT_Y0 = 102          # top of the first portrait
PORTRAIT_PITCH = 88
PORTRAIT_H = 76
PORTRAIT_SLOTS = 5
#: a selected portrait's border ring is this bright; the runners-up sit near 58.
SELECTED_MIN = 90

#: Portrait order per column, top to bottom (constant in every observed frame).
RACE_SLOTS: dict[str, list[str]] = {
    "alliance": ["human", "dwarf", "night-elf", "gnome", "skyborne"],
    "horde": ["orc", "undead", "tauren", "troll", "skyborne"],
}
#: Skyborne is one race with a faction-specific variant; every other race has none.
SKYBORNE_VARIANT = {"alliance": "high-order", "horde": "windshaper"}

RACE_NAMES = {
    "human": "Human", "dwarf": "Dwarf", "night-elf": "Night Elf", "gnome": "Gnome",
    "skyborne": "Skyborne", "orc": "Orc", "undead": "Undead", "tauren": "Tauren", "troll": "Troll",
}

#: Class bar order, left to right.
CLASS_ORDER = ["warrior", "hunter", "mage", "rogue", "priest", "warlock", "paladin", "druid", "shaman"]
CLASS_BAR = {"x0": 583, "pitch": 87, "w": 70, "y0": 978, "h": 62}
#: mean of saturation*value over an icon: available icons sit at 19..101, greyed ones at 5..9.
CLASS_AVAILABLE_MIN = 15.0

#: Race box: content area without the scrollbar (x1) and the ornate frame.
PANEL = (1604, 288, 1890, 502)
#: The same box with the frame, for the "what the panel looked like" review crop.
PANEL_BOX = (1596, 282, 1912, 508)
#: Column holding the round trait icons, and where the wrapped text starts.
ICON_COLUMN = (1605, 1651)
TEXT_COLUMN = (1652, 1890)

#: The faction banners: blue on the left column, red on the right one. Nothing else
#: in the source window shows both at once (checked against all 541 probe minutes).
BANNER_ALLIANCE = (30, 60, 130, 520)
BANNER_HORDE = (200, 60, 300, 520)
BANNER_MIN_FRACTION = 0.18

TRAIT_ICON_MIN_H, TRAIT_ICON_MAX_H = 24, 44
TRAIT_ICON_MIN_W, TRAIT_ICON_MAX_W = 26, 42
TRAIT_ICON_MIN_FILL = 0.45
TRAIT_ICON_MIN_AREA = 450


# --------------------------------------------------------------------------- screen classification

def _hsv(frame: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = box
    return cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)


def banner_fractions(frame: np.ndarray) -> tuple[float, float]:
    """``(blue fraction, red fraction)`` of the two faction banner columns."""
    a = _hsv(frame, BANNER_ALLIANCE)
    h = _hsv(frame, BANNER_HORDE)
    blue = float(((a[..., 0] > 100) & (a[..., 0] < 130) & (a[..., 1] > 90)).mean())
    red = float((((h[..., 0] < 12) | (h[..., 0] > 168)) & (h[..., 1] > 90)).mean())
    return blue, red


def is_character_creation(frame: np.ndarray, min_fraction: float = BANNER_MIN_FRACTION) -> bool:
    """True when both faction banners are on screen, i.e. this is the race picker."""
    blue, red = banner_fractions(frame)
    return blue > min_fraction and red > min_fraction


# --------------------------------------------------------------------------- which race is selected

@dataclass(frozen=True)
class Selection:
    faction: str
    slot: int
    race: str
    variant: str | None
    score: float
    margin: float

    @property
    def key(self) -> str:
        """``skyborne/windshaper`` or plain ``orc`` -- the unit a panel reading belongs to."""
        return f"{self.race}/{self.variant}" if self.variant else self.race


def portrait_box(faction: str, slot: int) -> tuple[int, int, int, int]:
    x0, x1 = FACTION_COLUMNS[faction]
    y0 = PORTRAIT_Y0 + PORTRAIT_PITCH * slot
    return x0, y0, x1, y0 + PORTRAIT_H


def border_brightness(frame: np.ndarray, faction: str, slot: int, band: int = 5) -> float:
    """Mean grey of the portrait's border ring (the selected one is framed in gold)."""
    x0, y0, x1, y1 = portrait_box(faction, slot)
    g = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(float)
    if g.size == 0:
        return 0.0
    ring = np.concatenate([g[:band, :].ravel(), g[-band:, :].ravel(),
                           g[:, :band].ravel(), g[:, -band:].ravel()])
    return float(ring.mean())


def race_of_slot(faction: str, slot: int) -> tuple[str, str | None]:
    """``(race id, variant id or None)`` for a portrait position."""
    race = RACE_SLOTS[faction][slot]
    return race, SKYBORNE_VARIANT[faction] if race == "skyborne" else None


def variant_of(race: str, faction: str) -> str | None:
    return SKYBORNE_VARIANT[faction] if race == "skyborne" else None


def selected_race(frame: np.ndarray, min_score: float = SELECTED_MIN) -> Selection | None:
    """The highlighted portrait, or None when no portrait is clearly framed."""
    scores = {(f, k): border_brightness(frame, f, k)
              for f in FACTION_COLUMNS for k in range(PORTRAIT_SLOTS)}
    (faction, slot), best = max(scores.items(), key=lambda kv: kv[1])
    rest = sorted((v for k, v in scores.items() if k != (faction, slot)), reverse=True)
    if best < min_score:
        return None
    race, variant = race_of_slot(faction, slot)
    return Selection(faction, slot, race, variant, round(best, 1), round(best - rest[0], 1))


# --------------------------------------------------------------------------- class bar

def class_box(index: int) -> tuple[int, int, int, int]:
    b = CLASS_BAR
    x = b["x0"] + b["pitch"] * index
    return x, b["y0"], x + b["w"], b["y0"] + b["h"]


def class_colourfulness(frame: np.ndarray) -> list[float]:
    """Mean saturation*value per class icon; a greyed-out icon scores under 10."""
    out = []
    for k in range(len(CLASS_ORDER)):
        x0, y0, x1, y1 = class_box(k)
        hsv = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
        s = hsv[..., 1].astype(float)
        v = hsv[..., 2].astype(float)
        out.append(float((s * v / 255).mean()) if s.size else 0.0)
    return out


def class_availability(frame: np.ndarray, threshold: float = CLASS_AVAILABLE_MIN) -> tuple[list[str], float]:
    """``(sorted class ids the race can play, separation margin)``.

    The margin is the gap between the dimmest available icon and the brightest
    unavailable one; below ~5 the reading is not trustworthy.
    """
    scores = class_colourfulness(frame)
    lit = [c for c, s in zip(CLASS_ORDER, scores) if s > threshold]
    on = [s for s in scores if s > threshold]
    off = [s for s in scores if s <= threshold]
    margin = (min(on) - max(off)) if on and off else float("inf")
    return sorted(lit), round(float(margin), 1)


# --------------------------------------------------------------------------- the race box

def panel_crop(frame: np.ndarray) -> np.ndarray:
    x0, y0, x1, y1 = PANEL
    return frame[y0:y1, x0:x1]


def panel_box_crop(frame: np.ndarray) -> np.ndarray:
    x0, y0, x1, y1 = PANEL_BOX
    return frame[y0:y1, x0:x1]


def trait_icon_bands(panel: np.ndarray, value_threshold: int = 32, open_kernel: int = 5,
                     close_height: int = 9) -> list[tuple[int, int]]:
    """``(y0, y1)`` of every round trait icon in a :data:`PANEL` crop, in frame coordinates.

    The icon column also carries the first characters of the lore paragraph,
    which starts at the box's left edge. Morphological opening breaks the thin
    strokes of that text apart, so only the discs survive as components of
    roughly 35x35 with a fill ratio near 0.78; a text line never does. The
    filter is deliberately precise rather than complete: an icon half-faded by
    the box's top or bottom gradient is dropped, and the trait it belongs to
    is read from another scroll position instead. Over 33 panel states it finds
    exactly the reader's row count 25 times, too few 6 times and too many twice;
    :func:`align_bands` refuses the last two cases rather than guess.
    """
    px0, y0, _, _ = PANEL
    x0, x1 = ICON_COLUMN[0] - px0, ICON_COLUMN[1] - px0
    hsv = cv2.cvtColor(panel[:, x0:x1], cv2.COLOR_BGR2HSV)
    mask = (hsv[..., 2] > value_threshold).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((open_kernel, open_kernel), np.uint8))
    # a dark band across a disc (the tauren Endurance bull) splits it in two; closing
    # vertically rejoins the halves without reconnecting the text the opening removed
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((close_height, 3), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    bands: list[tuple[int, int]] = []
    for i in range(1, n):
        _, y, w, h, area = (int(v) for v in stats[i])
        if not (TRAIT_ICON_MIN_H <= h <= TRAIT_ICON_MAX_H and TRAIT_ICON_MIN_W <= w <= TRAIT_ICON_MAX_W):
            continue
        if area < TRAIT_ICON_MIN_AREA or area / float(w * h) < TRAIT_ICON_MIN_FILL:
            continue
        bands.append((y0 + y, y0 + y + h))
    return sorted(bands)


def align_bands(bands: Sequence[tuple[int, int]], traits: Sequence[dict]) -> list[tuple[int, tuple[int, int]]]:
    """``(trait index, icon band)`` pairs, or ``[]`` when the two lists cannot be reconciled.

    :func:`trait_icon_bands` drops an icon the box's fade has eaten, and the
    reader still reports that row (with ``cut_off``). Peeling clipped rows off
    the ends until the counts match recovers the alignment for the rows that
    matter; anything else is left unaligned rather than guessed, because a
    wrong pairing would file one trait's crop under another trait's id.
    """
    idx = list(range(len(traits)))
    while len(idx) > len(bands):
        if traits[idx[0]].get("cut_off"):
            idx.pop(0)
        elif traits[idx[-1]].get("cut_off"):
            idx.pop()
        else:
            return []
    if len(idx) != len(bands):
        return []
    return list(zip(idx, bands))


def trait_blocks(bands: Sequence[tuple[int, int]], pad: int = 6) -> list[tuple[int, int]]:
    """``(y0, y1)`` of the text block belonging to each icon band.

    A trait's wrapped description runs from just above its icon to just above
    the next one; the last block ends at the bottom of the box.
    """
    _, top, _, bottom = PANEL
    out: list[tuple[int, int]] = []
    for i, (b0, _) in enumerate(bands):
        start = max(top, b0 - pad)
        end = bands[i + 1][0] - pad if i + 1 < len(bands) else bottom
        out.append((start, min(bottom, end)))
    return out


# --------------------------------------------------------------------------- trait text

_PASSIVE_RE = re.compile(r"\s*\((passive)\)\s*$", re.I)
#: "Perception: Detect Stealthed enemies for 20 sec" / "The Human Spirit (Passive): 5% increased Spirit"
_LINE_RE = re.compile(r"^(?P<name>[^:]{2,60}?)\s*:\s*(?P<desc>.+)$", re.S)


def trait_kind(name: str) -> str:
    """``passive`` when the name carries the "(Passive)" suffix, else ``active``."""
    return "passive" if _PASSIVE_RE.search(name or "") else "active"


def strip_kind(name: str) -> str:
    return _PASSIVE_RE.sub("", clean_text(name or "")).strip()


def trait_id(name: str) -> str:
    return slug(strip_kind(name))


def parse_trait_line(line: str) -> dict | None:
    """Split one panel line into ``{name, kind, description}``.

    ``None`` when the line has no "Name: description" shape (a lore sentence
    or a heading that slipped into the reading).
    """
    line = clean_text(line)
    m = _LINE_RE.match(line)
    if not m:
        return None
    raw = m.group("name").strip()
    name = strip_kind(raw)
    if not name or not trait_id(name):
        return None
    return {"name": name, "kind": trait_kind(raw), "description": clean_text(m.group("desc"))}


def normalise_trait(t: dict) -> dict:
    """One reader trait dict -> the fields the record keeps, names and kinds normalised.

    The VLM is asked for ``name`` and ``description`` separately but often
    returns the whole "Name: description" line as the name; that case is split
    here rather than in the prompt, where it would cost a retry.
    """
    name = clean_text(t.get("name") or "")
    desc = clean_text(t.get("description") or "")
    kind = (t.get("kind") or "").strip().lower()
    if ":" in name and not desc:
        parsed = parse_trait_line(name)
        if parsed:
            return dict(parsed, cut_off=bool(t.get("cut_off")))
    if ":" in name:
        head, _, tail = name.partition(":")
        if trait_id(head) and clean_text(tail) and clean_text(tail).lower() in desc.lower():
            name = head
        elif trait_id(head):
            name, desc = head, (clean_text(tail) + " " + desc).strip()
    out_kind = "passive" if kind == "passive" or trait_kind(name) == "passive" else "active"
    return {"name": strip_kind(name), "kind": out_kind, "description": desc,
            "cut_off": bool(t.get("cut_off"))}


#: Headings and labels the box shows that are not traits; a reader that files one
#: as a trait row would otherwise mint an id for it.
NON_TRAIT_NAMES = {"racial-traits", "racial-trait", "traits", "lore"}


def clean_race_panel(doc: dict) -> dict:
    """One race-box reading, field contract enforced (the panel analogue of ``reader.clean_reading``)."""
    traits = []
    seen: set[str] = set()
    for t in doc.get("traits") or []:
        n = normalise_trait(t)
        tid = trait_id(n["name"])
        if not tid or tid in NON_TRAIT_NAMES or tid in seen:
            continue
        seen.add(tid)
        traits.append(n)
    return {"race_name": clean_text(doc.get("race_name") or "") or None,
            "traits": traits,
            "lore": clean_text(doc.get("lore") or ""),
            "lore_cut_off": bool(doc.get("lore_cut_off"))}


# --------------------------------------------------------------------------- agreement and merging

def norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def reading_key(t: dict) -> tuple:
    return (trait_id(t.get("name") or ""), t.get("kind"), norm(t.get("description")).lower())


def confidence(a: dict, b: dict) -> float:
    """Stage 5's three-valued agreement, on a trait instead of a tooltip.

    1.0 both passes read the same trait the same way, 0.7 same name and kind
    but different wording, 0.3 otherwise (0.0 when only one pass saw it).
    """
    if b is None:
        return 0.0
    if reading_key(a) == reading_key(b):
        return 1.0
    if trait_id(a.get("name") or "") == trait_id(b.get("name") or "") and a.get("kind") == b.get("kind"):
        return 0.7
    return 0.3


def _fragment_of(small: dict, big: dict) -> bool:
    """True when ``small`` is the tail of ``big``'s row, read as if it were its own trait.

    A row whose name has scrolled above the box edge still shows an icon, so the
    reader dutifully files "Damage to Beasts: increased by 5%" next to the real
    "Beast Slaying (Passive): Damage to Beasts increased by 5%". The fragment is
    always contained in the row it came from, which is what this tests.
    """
    def n(s: str) -> str:
        return re.sub(r"[^a-z0-9 ]+", "", norm(s).lower())
    sn, sd = n(small.get("name", "")), n(small.get("description", ""))
    bn, bd = n(big.get("name", "")), n(big.get("description", ""))
    if not sn or trait_id(small.get("name", "")) == trait_id(big.get("name", "")):
        return False
    if f"{sn} {sd}".strip() and f"{sn} {sd}".strip() in f"{bn} {bd}":
        return True
    return sn in bd and bool(sd) and bd.endswith(sd)


def drop_fragments(records: Iterable[dict]) -> tuple[list[dict], list[dict]]:
    """``(kept, dropped)`` -- records that are only the tail of another record's row."""
    recs = list(records)
    kept, dropped = [], []
    for r in recs:
        if any(_fragment_of(r, o) for o in recs if o is not r):
            dropped.append(r)
        else:
            kept.append(r)
    return kept, dropped


def stitch_order(sequences: Iterable[Sequence[str]]) -> list[str]:
    """Panel order of trait ids from the overlapping windows each scroll position shows.

    Each sequence is one state's ids top to bottom; they overlap, so a stable
    topological sort over the "directly above" pairs recovers the full list.
    Cycles (a misread that puts two traits in both orders) fall back to first
    appearance, which is what a reviewer would see anyway.
    """
    order: list[str] = []
    after: dict[str, set[str]] = {}
    for seq in sequences:
        for x in seq:
            if x not in after:
                after[x] = set()
                order.append(x)
        for a, b in zip(seq, seq[1:]):
            if a != b:
                after[b].add(a)
    out: list[str] = []
    remaining = list(order)
    while remaining:
        ready = [x for x in remaining if not (after[x] - set(out))]
        if not ready:
            ready = [remaining[0]]
        out.append(ready[0])
        remaining.remove(ready[0])
    return out


def _score(rec: dict) -> tuple:
    """Ranking of two readings of the same trait: complete text, then agreement, then sharpness."""
    src = rec.get("source") or {}
    return (0 if rec.get("cut_off") else 1,
            len(norm(rec.get("description"))) > 0,
            float(src.get("confidence") or 0.0),
            float(src.get("sharpness") or 0.0))


def merge_traits(records: Iterable[dict], order: Sequence[str] | None = None) -> list[dict]:
    """One record per trait id, keeping the sharpest complete reading.

    Rejected readings of the same trait are kept under ``source.readings`` so
    the review page can show what the other scroll positions said, and the
    variants a trait was seen in are unioned.
    """
    best: dict[str, dict] = {}
    others: dict[str, list[dict]] = {}
    variants: dict[str, list[str]] = {}
    for rec in records:
        key = trait_id(rec.get("name") or "")
        if not key:
            continue
        for v in rec.get("variants") or []:
            if v not in variants.setdefault(key, []):
                variants[key].append(v)
        cur = best.get(key)
        if cur is None or _score(rec) > _score(cur):
            if cur is not None:
                others.setdefault(key, []).append(cur)
            best[key] = rec
        else:
            others.setdefault(key, []).append(rec)
    out = []
    for key, rec in best.items():
        rec = dict(rec)
        if variants.get(key):
            rec["variants"] = sorted(variants[key])
        seen = {reading_key(rec)}
        alts = []
        for o in others.get(key, []):
            k = reading_key(o)
            if k in seen:
                continue
            seen.add(k)
            alts.append(o)
        if alts:
            rec["alternates"] = alts
        out.append(rec)
    if order:
        rank = {tid: i for i, tid in enumerate(order)}
        return sorted(out, key=lambda r: (rank.get(trait_id(r["name"]), len(rank)), trait_id(r["name"])))
    return sorted(out, key=lambda r: (r["kind"] != "active", trait_id(r["name"])))

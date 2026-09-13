"""Stage 5: read tooltip crops with the local VLM (llama-server, OpenAI-compatible).

Pure parts (no network): prompt and schema, crop preparation, confidence
between two readings, candidate-record assembly in the shape of
``docs/briefs/pipeline.md`` section 1 (as ``wowtalents.export`` consumes it:
0-based ``row``/``col``, ``rank {current, max}``, ``description_rank1``,
``source.crop_path`` relative to ``pipeline/``).

Network part: :class:`Reader` posts a base64 PNG plus the schema to
``/v1/chat/completions`` with ``response_format: json_schema`` and
temperature 0. Readings are cached on disk by content hash so re-runs cost
nothing.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import requests

from . import fsio as _fsio
from . import text as _text

PIPELINE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SERVER = "http://127.0.0.1:8089"
VIDEO_ID = "DxtVEhjyROU"
FPS = 60
PROMPT_VERSION = "tooltip-v3"

# --------------------------------------------------------------------------- prompts and schemas

TOOLTIP_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "rank_current", "rank_max", "kind", "extra_lines", "requires",
                 "description", "footer", "cut_off"],
    "properties": {
        "name": {"type": "string"},
        "rank_current": {"type": ["integer", "null"]},
        "rank_max": {"type": ["integer", "null"]},
        "kind": {"type": ["string", "null"], "enum": ["Passive", None]},
        "extra_lines": {"type": "array", "items": {"type": "string"}},
        "requires": {"type": "array", "items": {"type": "string"}},
        "description": {"type": "string"},
        "footer": {"type": ["string", "null"]},
        "cut_off": {"type": "boolean"},
    },
}

TOOLTIP_SYSTEM = (
    "You transcribe World of Warcraft talent tooltips from screenshots. Copy the text exactly, "
    "including punctuation, capitalisation and numbers. Never paraphrase and never add words that "
    "are not in the image. Icons or colours bleeding through the dark box are artefacts; ignore them.\n"
    "A tooltip has these lines, top to bottom:\n"
    "1. the talent name (large white text);\n"
    "2. 'Rank N/M';\n"
    "3. optional white lines: 'Passive', or a cost, range or cast time;\n"
    "4. optional red lines starting with 'Requires';\n"
    "5. the gold description: one or more paragraphs, sometimes separated by a blank line; all of them belong "
    "to the description, down to the last gold line;\n"
    "6. an optional green footer such as 'Click to learn'.\n"
    "Fill the JSON fields as follows.\n"
    "name: line 1. rank_current, rank_max: the two integers N and M of the Rank line, or null when there is "
    "no Rank line. kind: 'Passive' when a line reads exactly Passive, else null. extra_lines: the other white "
    "lines between the Rank line and the description (cost, range, cast time); never the name, description "
    "or footer. requires: only lines that start with 'Requires', one string each. description: all gold "
    "paragraphs in order, line breaks and blank lines joined with single spaces, nothing left out; it must not "
    "contain the Passive line, the Requires lines or the footer. Keep the original capitalisation: words in "
    "the middle of a sentence are lowercase unless they are names (spells, abilities, stats). footer: the green bottom line ('Click to learn'), else null. cut_off: true only "
    "when a text line is visibly truncated or runs into the image border so that words or a whole line are "
    "missing; a complete tooltip with a margin on every side is not cut off, even when the box fills the "
    "image. Return JSON only."
)

TOOLTIP_USER = (
    "Example: a tooltip whose lines read 'Toughness', 'Rank 0/5', 'Passive', "
    "'Increases your armor value from items by 2%.', 'Click to learn' becomes\n"
    '{"name":"Toughness","rank_current":0,"rank_max":5,"kind":"Passive","extra_lines":[],"requires":[],'
    '"description":"Increases your armor value from items by 2%.","footer":"Click to learn","cut_off":false}\n'
    "Now return the content of this tooltip as JSON."
)

HEADER_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "tabs", "active_tab", "unspent_talents"],
    "properties": {
        "title": {"type": ["string", "null"]},
        "tabs": {"type": "array", "items": {"type": "string"}},
        "active_tab": {"type": ["string", "null"]},
        "unspent_talents": {"type": ["integer", "null"]},
    },
}

HEADER_SYSTEM = (
    "You read the header strip of the World of Warcraft talent window. It shows a window title, two page "
    "tabs (the lit gold one is active, the grey one with a padlock is locked), a search box and an "
    "'Unspent Talents' counter. Copy the text exactly. tabs: the tab labels left to right without the check "
    "mark or padlock symbols. active_tab: the label of the lit tab. unspent_talents: the number in the green "
    "box, or null. Return JSON only."
)
HEADER_USER = "Return the header content as JSON."

TREE_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "points"],
    "properties": {"name": {"type": "string"}, "points": {"type": ["integer", "null"]}},
}

TREE_SYSTEM = (
    "You read the title strip of one talent tree in the World of Warcraft talent window: a round icon with a "
    "small points badge, then the tree name in white text. Copy the name exactly as written (it may be two "
    "words). points: the number in the badge, or null. Return JSON only."
)
TREE_USER = "Return the tree name as JSON."

# Stage 12 (races): the race box of the character-creation screen. Same contract as the
# tooltip reader -- copy, never paraphrase -- but the unit is a scrollable list, so the
# schema carries an array and every entry says whether the box cut it off.
RACE_PANEL_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["race_name", "traits", "lore", "lore_cut_off"],
    "properties": {
        "race_name": {"type": ["string", "null"]},
        "traits": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "kind", "description", "cut_off"],
                "properties": {
                    "name": {"type": "string"},
                    "kind": {"type": ["string", "null"], "enum": ["Passive", None]},
                    "description": {"type": "string"},
                    "cut_off": {"type": "boolean"},
                },
            },
        },
        "lore": {"type": "string"},
        "lore_cut_off": {"type": "boolean"},
    },
}

RACE_PANEL_SYSTEM = (
    "You transcribe the race box of the World of Warcraft character-creation screen. Copy the text exactly, "
    "including punctuation, capitalisation and numbers. Never paraphrase and never add words that are not in "
    "the image.\n"
    "The box scrolls, so the image is a window onto a longer page. Top to bottom it can show:\n"
    "1. the race name in large white text (only when the box is scrolled to the top);\n"
    "2. the gold heading 'Racial Traits';\n"
    "3. one row per racial trait: a round icon on the left, then a line of the form "
    "'Name: description' or 'Name (Passive): description', the name in white and the description in gold, "
    "wrapped over two or three lines;\n"
    "4. a gold lore paragraph about the race, starting at the left edge with no icon.\n"
    "Fill the JSON fields as follows. race_name: line 1 if present, else null. traits: one entry per trait row "
    "with an icon, in the order shown. name: the white part before the colon, without the '(Passive)' suffix. "
    "kind: 'Passive' when the name carries the '(Passive)' suffix, else null. description: the gold text after "
    "the colon, line breaks joined with single spaces, exactly as written and nothing else -- never the lore "
    "paragraph. cut_off: true when that row's icon or text is clipped or faded out by the top or bottom edge of "
    "the box so that words are missing, false when the whole row is legible. lore: the lore paragraph as shown, "
    "or an empty string when none is visible; lore_cut_off: true when it is clipped. A row is a trait only if it "
    "has its own round icon. Return JSON only."
)

RACE_PANEL_USER = (
    "Example: a box showing 'Dwarf', 'Racial Traits', a row 'Stoneform: Immunity to Bleeds, Poisons, and "
    "Diseases and reduce Physical damage taken for 8 sec', a row 'Mace Specialization (Passive): Maces "
    "increase spell and ability critical chance by 1%' and no lore becomes\n"
    '{"race_name":"Dwarf","traits":[{"name":"Stoneform","kind":null,"description":"Immunity to Bleeds, '
    'Poisons, and Diseases and reduce Physical damage taken for 8 sec","cut_off":false},'
    '{"name":"Mace Specialization","kind":"Passive","description":"Maces increase spell and ability critical '
    'chance by 1%","cut_off":false}],"lore":"","lore_cut_off":false}\n'
    "Now return the content of this race box as JSON."
)

RACIAL_LIST_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["entries"],
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "subtitle"],
                "properties": {"name": {"type": "string"}, "subtitle": {"type": "string"}},
            },
        },
    },
}

RACIAL_LIST_SYSTEM = (
    "You read entries of the General page of the World of Warcraft spellbook: a parchment list where each entry "
    "is a square icon, a name in dark text and a smaller grey subtitle under it ('Racial', 'Racial Passive', "
    "'Passive', or nothing). Copy both exactly. Return one entry per icon, in reading order, as JSON only."
)
RACIAL_LIST_USER = "Return the entries of this spellbook page as JSON."


# --------------------------------------------------------------------------- image preparation

def upscale(img: np.ndarray, factor: float) -> np.ndarray:
    """Cubic upscale (the brief's 2x / 1.5x passes)."""
    if factor == 1.0:
        return img
    h, w = img.shape[:2]
    return cv2.resize(img, (int(round(w * factor)), int(round(h * factor))), interpolation=cv2.INTER_CUBIC)


def png_bytes(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("PNG encoding failed")
    return buf.tobytes()


def data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


# --------------------------------------------------------------------------- readings and confidence

def norm_text(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def norm_name(s: str | None) -> str:
    return norm_text(s).lower()


def clean_reading(r: dict) -> dict:
    """Whitespace-normalise a reading and enforce the field contract the prompt asks for.

    Lines that start with 'Requires' are moved from ``extra_lines``/``description`` head into
    ``requires``; a lone 'Passive' anywhere else becomes ``kind``; 'Click to learn' anywhere
    else becomes ``footer``; a ``requires`` entry without the literal "Requires " prefix gets it
    back. Nothing else is invented, only re-filed.
    """
    out = {
        "name": norm_text(r.get("name")),
        "rank_current": r.get("rank_current"),
        "rank_max": r.get("rank_max"),
        "kind": r.get("kind") or None,
        "extra_lines": [norm_text(x) for x in (r.get("extra_lines") or []) if norm_text(x)],
        "requires": [norm_text(x) for x in (r.get("requires") or []) if norm_text(x)],
        "description": norm_text(r.get("description")),
        "footer": norm_text(r.get("footer")) or None,
        "cut_off": bool(r.get("cut_off")),
    }
    keep: list[str] = []
    for line in out["extra_lines"]:
        low = line.lower()
        if low.startswith("requires"):
            out["requires"].append(line)
        elif low == "passive":
            out["kind"] = "Passive"
        elif low.startswith("click to learn"):
            out["footer"] = out["footer"] or line
        else:
            keep.append(line)
    out["extra_lines"] = keep
    reqs: list[str] = []
    for line in out["requires"]:
        low = line.lower()
        if low.startswith("click to learn"):
            out["footer"] = out["footer"] or line
        elif low == "passive":
            out["kind"] = "Passive"
        elif line:
            # the field holds only red "Requires ..." lines by contract; a model that files
            # "Shields" here has dropped the literal prefix, so restore it (nothing else is added)
            if not low.startswith("requires"):
                line = "Requires " + line
            if line not in reqs:
                reqs.append(line)
    out["requires"] = reqs
    d = out["description"]
    if d.lower().startswith("passive "):
        out["kind"] = "Passive"
        d = d[len("passive "):]
    # a 'Requires ... .' sentence glued to the front of the description (only with a period,
    # anything else is left for the review queue)
    while True:
        m = re.match(r"^(Requires [^.]*\.)\s+(\S.*)$", d)
        if not m:
            break
        out["requires"].append(m.group(1))
        d = m.group(2)
    for tail in ("Click to learn", "Click to learn."):
        if d.endswith(" " + tail):
            out["footer"] = out["footer"] or tail
            d = d[: -len(tail) - 1].rstrip()
    out["description"] = d
    return out


def reading_key(r: dict) -> tuple:
    return (norm_name(r.get("name")), r.get("rank_current"), r.get("rank_max"), r.get("kind"),
            tuple(r.get("extra_lines") or []), tuple(r.get("requires") or []), norm_text(r.get("description")))


def confidence(a: dict, b: dict) -> float:
    """Brief section 3, stage 5: 1.0 identical, 0.7 name and rank identical, else 0.3."""
    if reading_key(a) == reading_key(b):
        return 1.0
    if norm_name(a.get("name")) == norm_name(b.get("name")) and norm_name(a.get("name")) \
            and a.get("rank_max") == b.get("rank_max") and a.get("rank_current") == b.get("rank_current"):
        return 0.7
    return 0.3


def disagreements(a: dict, b: dict) -> list[str]:
    fields = ("name", "rank_current", "rank_max", "kind", "extra_lines", "requires", "description", "footer", "cut_off")
    ka, kb = clean_reading(a), clean_reading(b)
    return [f for f in fields if ka.get(f) != kb.get(f)]


def choose_primary(a: dict, b: dict) -> tuple[dict, dict]:
    """Pass 1 (2x) is primary unless it is unusable and pass 2 is not."""
    bad_a = not norm_text(a.get("name")) or a.get("rank_max") is None
    bad_b = not norm_text(b.get("name")) or b.get("rank_max") is None
    if bad_a and not bad_b:
        return b, a
    return a, b


# --------------------------------------------------------------------------- record assembly

def hms_ms(t: float) -> str:
    t = float(t)
    s = int(t)
    ms = int(round((t - s) * 1000))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}.{ms:03d}"


def frame_index(hover: dict, fps: int = FPS) -> int:
    if "sq" in hover and "offset" in hover:
        return int(hover["sq"]) * fps + int(hover["offset"])
    return int(round(float(hover.get("t", 0.0)) * fps))


def assemble_record(cls: str, hover: dict, segment_id: str, tree_name: str, page_name: str,
                    primary: dict, secondary: dict, *, reader: str, passes: tuple[str, str] = ("3x", "2x"),
                    hovers_dir: str = "work/hovers", tree_source: dict | None = None,
                    video: str = VIDEO_ID) -> dict:
    """One candidate record (brief section 1, export.py field names, 0-based row/col)."""
    p = clean_reading(primary)
    s = clean_reading(secondary)
    conf = confidence(p, s)
    row1, col1 = int(hover["row"]), int(hover["col"])
    row, col = row1 - 1, col1 - 1
    tree_slug = _text.slug(tree_name)
    files = hover.get("files") or {}
    t = float(hover["t"])
    rec: dict[str, Any] = {
        "id": f"{cls}/{tree_slug}/r{row}c{col}",
        "class": cls,
        "tree": tree_name,
        "page": page_name,
        "row": row,
        "col": col,
        "name": p["name"],
        "rank": {"current": p["rank_current"], "max": p["rank_max"]},
        "kind": p["kind"],
        "extra_lines": p["extra_lines"],
        "requires": p["requires"],
        "description_rank1": p["description"],
        "footer": p["footer"],
        "cut_off": bool(p["cut_off"] or hover.get("cut_off")),
        "source": {
            "video": video,
            "t": round(t, 3),
            "timestamp": hms_ms(t),
            "frame_index": frame_index(hover),
            "crop_path": f"{hovers_dir}/{files.get('tooltip')}" if files.get("tooltip") else None,
            "icon_crop_path": f"{hovers_dir}/{files.get('icon')}" if files.get("icon") else None,
            "reader": reader,
            "confidence": conf,
            "reviewed": False,
            "segment_id": segment_id,
            "hover_id": hover.get("id"),
            "cell": [int(hover.get("tree", 0)), row1, col1],
            "bbox": list(hover.get("bbox") or []),
            "sharpness": hover.get("sharpness"),
            "frames": hover.get("frames"),
            "agreement": {"confidence": conf, "differs_in": disagreements(p, s)},
            "readings": [
                {"reader": f"{reader}/{passes[0]}", "name": p["name"], "description": p["description"],
                 "maxRank": p["rank_max"], "confidence": conf, "kind": p["kind"], "requires": p["requires"],
                 "extra_lines": p["extra_lines"], "footer": p["footer"], "cut_off": p["cut_off"]},
                {"reader": f"{reader}/{passes[1]}", "name": s["name"], "description": s["description"],
                 "maxRank": s["rank_max"], "confidence": conf, "kind": s["kind"], "requires": s["requires"],
                 "extra_lines": s["extra_lines"], "footer": s["footer"], "cut_off": s["cut_off"]},
            ],
        },
    }
    if p["rank_max"] is None:
        # the tooltip carried no "Rank N/M" line (seen 2026-09-13: druid Feral Charge, a dual-form
        # ability whose box starts at the cost line); name and maxRank are unverifiable
        rec["source"]["confidence"] = min(conf, 0.3)
        rec["source"]["note"] = "no Rank line in the tooltip; name and maxRank unverified (maxRank exported as 1)"
    if tree_source:
        rec["tree_source"] = dict(tree_source)
    return rec


def merge_hovers(per_segment: list[tuple[str, dict]]) -> tuple[dict[tuple, dict], dict[tuple, list[dict]]]:
    """Union of hovers over segments keyed by (page, tree index, row, col).

    Keeps the crop that is not cut off and then the sharpest; returns
    ``(best, all_by_key)`` with the segment id stored under ``_segment``.
    """
    best: dict[tuple, dict] = {}
    everything: dict[tuple, list[dict]] = {}
    for sid, doc in per_segment:
        page = doc.get("page") or "Primary"
        for h in doc.get("hovers") or []:
            key = (page, int(h["tree"]), int(h["row"]), int(h["col"]))
            h = dict(h, _segment=sid)
            everything.setdefault(key, []).append(h)
            cur = best.get(key)
            score = (0 if h.get("cut_off") else 1, float(h.get("sharpness") or 0.0))
            if cur is None or score > (0 if cur.get("cut_off") else 1, float(cur.get("sharpness") or 0.0)):
                best[key] = h
    return best, everything


TREE_NAME_SNAP = 90.0


def same_tree_name(read: str, label: str) -> bool:
    """True when a tree-strip reading is a near-miss of the human label from segments.md
    (token_sort_ratio >= 90: "Marksmananship" vs "Marksmanship" 92), False for a real rename
    ("Shadow Magic" vs "Shadow" 63, "Elemental Combat" vs "Elemental" 72)."""
    from rapidfuzz import fuzz
    return fuzz.token_sort_ratio(norm_name(read), norm_name(label)) >= TREE_NAME_SNAP


def rank0_order(best: dict, candidates: list[dict]) -> list[dict]:
    """The crops of one cell in reading order: ``best`` first, then the others by
    (not cut off, sharpness, earlier time). Stage 5 walks this list until a crop
    reads ``rank_current == 0``, so a segment recorded after points were spent
    does not win a cell just because its crop is the sharpest."""
    rest = [h for h in candidates if h is not best]
    rest.sort(key=lambda h: (0 if h.get("cut_off") else 1, float(h.get("sharpness") or 0.0), -float(h.get("t") or 0.0)),
              reverse=True)
    return [best] + rest


def consensus_cells(grids: list[list[dict]], min_cells: int = 40) -> tuple[set[tuple[int, int, int]], set[tuple[int, int, int]]]:
    """Cells (tree, row, col) seen in more than half of the plausible calibrations.

    A calibration with fewer than ``min_cells`` cells (spellbook or search box
    over the window) does not vote. Returns ``(consensus, disputed)`` where
    disputed are cells seen by some but not enough calibrations.
    """
    voters = [{(c["tree"], c["row"], c["col"]) for c in g} for g in grids if len(g) >= min_cells]
    if not voters:
        voters = [{(c["tree"], c["row"], c["col"]) for c in g} for g in grids]
    seen: dict[tuple[int, int, int], int] = {}
    for v in voters:
        for key in v:
            seen[key] = seen.get(key, 0) + 1
    need = len(voters) / 2
    consensus = {k for k, n in seen.items() if n > need}
    return consensus, set(seen) - consensus


# --------------------------------------------------------------------------- server client

@dataclass
class Reader:
    server: str = DEFAULT_SERVER
    model: str = "qwen3-vl"
    cache_dir: Path | None = None
    timeout: float = 120.0
    max_tokens: int = 600
    calls: int = 0
    cache_hits: int = 0
    seconds: float = 0.0
    session: requests.Session = field(default_factory=requests.Session)

    def model_name(self) -> str:
        """Short model label from ``/v1/models`` (file stem), for ``source.reader``."""
        try:
            r = self.session.get(f"{self.server}/v1/models", timeout=10)
            r.raise_for_status()
            name = (r.json().get("models") or r.json().get("data") or [{}])[0]
            path = name.get("name") or name.get("id") or ""
            return Path(path).stem or self.model
        except Exception:  # noqa: BLE001
            return self.model

    def _cache_path(self, png: bytes, system: str, user: str, schema: dict) -> Path | None:
        if self.cache_dir is None:
            return None
        h = hashlib.sha1()
        h.update(png)
        h.update(json.dumps([PROMPT_VERSION, system, user, schema], sort_keys=True).encode())
        return self.cache_dir / f"{h.hexdigest()}.json"

    def ask(self, img: np.ndarray, system: str, user: str, schema: dict, name: str = "tooltip") -> dict:
        png = png_bytes(img)
        cp = self._cache_path(png, system, user, schema)
        if cp is not None and cp.is_file():
            self.cache_hits += 1
            return json.loads(cp.read_text(encoding="utf-8"))
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": data_url(png)}},
                    {"type": "text", "text": user},
                ]},
            ],
            "response_format": {"type": "json_schema", "json_schema": {"name": name, "schema": schema}},
        }
        t0 = time.time()
        r = self.session.post(f"{self.server}/v1/chat/completions", json=payload, timeout=self.timeout)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        self.calls += 1
        self.seconds += time.time() - t0
        try:
            out = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"reader returned invalid JSON: {content[:200]!r}") from e
        if cp is not None:
            cp.parent.mkdir(parents=True, exist_ok=True)
            _fsio.write_json_atomic(cp, out, indent=1)
        return out

    def read_tooltip(self, crop: np.ndarray, factor: float = 3.0) -> dict:
        return self.ask(upscale(crop, factor), TOOLTIP_SYSTEM, TOOLTIP_USER, TOOLTIP_SCHEMA, "tooltip")

    def read_header(self, strip: np.ndarray, factor: float = 1.0) -> dict:
        return self.ask(upscale(strip, factor), HEADER_SYSTEM, HEADER_USER, HEADER_SCHEMA, "header")

    def read_tree(self, strip: np.ndarray, factor: float = 2.0) -> dict:
        return self.ask(upscale(strip, factor), TREE_SYSTEM, TREE_USER, TREE_SCHEMA, "tree")

    def read_race_panel(self, panel: np.ndarray, factor: float = 3.0) -> dict:
        return self.ask(upscale(panel, factor), RACE_PANEL_SYSTEM, RACE_PANEL_USER, RACE_PANEL_SCHEMA, "race_panel")

    def read_racial_list(self, crop: np.ndarray, factor: float = 3.0) -> dict:
        return self.ask(upscale(crop, factor), RACIAL_LIST_SYSTEM, RACIAL_LIST_USER, RACIAL_LIST_SCHEMA, "racial_list")

"""Spellbook window: find it, cut the list page into rows, anchor hover tooltips.

Phase 2d (``docs/PLAN.md``; ``docs/briefs/beyond-talents.md`` section (b), priority 2). The
spellbook is the second non-talent window in the source video and, unlike the
character-creation screen of stage 12, it **moves**: Xaryu drags it around, so
every geometry here is relative to a located window origin rather than to the
frame. Measured 2026-09-13 from the stage-0 native samples in
``work/probe/extra/``:

* a 733x658 window whose dark title bar carries the word "Spellbook"; the bar
  is class-independent, which makes it the locator template
  (``assets/spellbook-title.png``, normalised cross-correlation >= 0.85 on every
  spellbook frame seen, <= 0.82 on everything else in the 541 probe minutes);
* a tab strip (General plus one tab per talent tree) and a search box below it.
  Which list is on screen follows from the page heading, the search text and the
  list itself, compared as changed-pixel fractions rather than hashed
  (:func:`page_changed`); the first two are flat parchment, where a dHash is noise;
* a three-column list of at most seven rows, column pitch 208.5 px, row pitch
  63 px, each row an icon of about 36 px plus a name line and a smaller grey
  subtitle ("Rank 4", "Passive", "Racial", "Racial Passive" or nothing);
* "Page N/M" at the bottom right. Every page seen on stream says 1/1 and no
  list scrolled, so page flips -- not scroll positions -- are the only way a
  list can continue.

Everything here is pure: pixels or strings in, numbers or dicts out. The stage
driver (``stages/11_spellbook.py``) owns ffmpeg, the VLM and the files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import cv2
import numpy as np

from .text import clean_text, slug

__all__ = [
    "FRAME_W", "FRAME_H", "WINDOW_W", "WINDOW_H", "COL_X", "ROW_Y", "COLUMNS", "ROWS",
    "TITLE_TEMPLATE", "Window", "load_template", "locate_window",
    "window_box", "chrome_box", "page_title_box", "page_nav_box", "list_box",
    "column_box", "icon_box", "row_box", "work_roi", "crop",
    "change_fraction", "row_change_fractions", "list_change", "page_changed", "composite",
    "column_counts", "tooltip_mask", "find_tooltip", "grow_right",
    "cell_filled", "filled_cells", "tooltip_cell",
    "parse_rank", "entry_kind", "strip_rank", "spell_id", "normalise_entry",
    "clean_page_reading", "looks_like_prose", "entry_key", "confidence", "merge_entries", "page_slug",
    "strip_kind",
    "show_all_ranks", "dedupe_states", "dedupe_tooltips", "tab_from_title", "snap_title",
    "SEARCH_TITLES",
    "AUTHORITY_READER", "is_authority", "split_readings", "merge_tooltip", "merge_entry",
    "merged_confidence", "SETTLED_CONFIDENCE", "ADJUDICATED_CONFIDENCE",
    "UNCORROBORATED_CONFIDENCE", "DISPUTED_CONFIDENCE",
]

# --------------------------------------------------------------------------- geometry

FRAME_W, FRAME_H = 1920, 1080

#: The window as a whole, measured at its default position (232, 32).
WINDOW_W, WINDOW_H = 733, 658

#: The title-bar strip used as the locator template, relative to the window origin.
TITLE_STRIP = (0, 2, 733, 28)
TITLE_TEMPLATE = Path(__file__).resolve().parents[2] / "assets" / "spellbook-title.png"
#: Normalised cross-correlation above which the strip is the spellbook title bar.
MIN_TITLE_SCORE = 0.85

#: Tab icons (General + one per tree), search box, and the two together.
TABS = (60, 34, 240, 78)
SEARCH = (404, 32, 702, 60)
CHROME = (60, 32, 702, 78)
#: The page heading ("Retribution", "General", "Name Matches", ...).
PAGE_TITLE = (52, 92, 490, 142)
#: The two boxes that decide *which* list is on screen, cropped tight around the
#: glyphs. Tight matters: over the generous PAGE_TITLE box the words "Retribution"
#: and "Protection" differ in only 3.8 % of the pixels, which is the level at which
#: the stream's one-second keyframes make unchanged text flicker; over these two
#: the same page scores 0.000-0.002 and a different one 0.069-0.093.
TITLE_TEXT = (60, 96, 330, 136)
SEARCH_TEXT = (424, 36, 690, 58)
#: Fraction of changed pixels above which two frames show different lists.
STATE_CHANGE = 0.02
#: A pixel counts as changed at this greyscale distance.
CHANGE_LEVEL = 30
#: "Page N/M" and its two arrows.
PAGE_NAV = (500, 578, 680, 616)
#: The list area as a whole.
LIST = (52, 152, 706, 604)

#: Left edge of each icon column and top edge of each row, relative to the window.
COL_X = (67, 275, 484)
ROW_Y = (166, 229, 292, 355, 418, 481, 544)
COLUMNS, ROWS = len(COL_X), len(ROW_Y)
ICON = 40
#: Row box: icon plus the name and subtitle lines up to the next column.
ROW_W, ROW_H = 206, 58
#: A row's text starts this far right of its icon.
TEXT_DX = 46

#: How far a tooltip may reach past the window's right edge (measured 238 px wide
#: tooltips anchored at the third column, which ends 43 px inside the frame).
TOOLTIP_MARGIN = 340

#: A cell holds an icon when its box is this much busier than bare parchment
#: (Laplacian variance; parchment measures 3-30, an icon 400-3000).
ICON_MIN_VARIANCE = 120.0


@dataclass(frozen=True)
class Window:
    """Where the spellbook window sits in a frame."""

    x: int
    y: int
    score: float

    @property
    def origin(self) -> tuple[int, int]:
        return self.x, self.y

    def near(self, other: "Window | None", tolerance: int = 6) -> bool:
        """True when two locations are the same window, a few pixels of jitter apart."""
        return (other is not None and abs(self.x - other.x) <= tolerance
                and abs(self.y - other.y) <= tolerance)


def load_template(path: Path = TITLE_TEMPLATE) -> np.ndarray:
    """The grey title-bar template; raises when the asset is missing."""
    tpl = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if tpl is None:
        raise FileNotFoundError(path)
    return tpl


def locate_window(gray: np.ndarray, template: np.ndarray,
                  min_score: float = MIN_TITLE_SCORE) -> Window | None:
    """The spellbook window in a greyscale frame, or None when it is not open.

    The match is on the title bar, which is the same pixels for every class and
    every page; ``score`` is the normalised cross-correlation of the best match.
    """
    if gray.shape[0] < template.shape[0] or gray.shape[1] < template.shape[1]:
        return None
    res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    if score < min_score:
        return None
    return Window(int(loc[0]) - TITLE_STRIP[0], int(loc[1]) - TITLE_STRIP[1], round(float(score), 3))


def _box(win: Window, rel: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = rel
    return win.x + x0, win.y + y0, win.x + x1, win.y + y1


def window_box(win: Window) -> tuple[int, int, int, int]:
    return _box(win, (0, 0, WINDOW_W, WINDOW_H))


def chrome_box(win: Window) -> tuple[int, int, int, int]:
    return _box(win, CHROME)


def page_title_box(win: Window) -> tuple[int, int, int, int]:
    return _box(win, PAGE_TITLE)


def page_nav_box(win: Window) -> tuple[int, int, int, int]:
    return _box(win, PAGE_NAV)


def list_box(win: Window) -> tuple[int, int, int, int]:
    return _box(win, LIST)


def column_box(win: Window, col: int) -> tuple[int, int, int, int]:
    """The whole column of rows, the strip one VLM call reads."""
    x = COL_X[col]
    return _box(win, (x - 8, ROW_Y[0] - 10, x + ROW_W, ROW_Y[-1] + ROW_H))


def icon_box(win: Window, col: int, row: int) -> tuple[int, int, int, int]:
    x, y = COL_X[col], ROW_Y[row]
    return _box(win, (x, y, x + ICON, y + ICON))


def row_box(win: Window, col: int, row: int) -> tuple[int, int, int, int]:
    x, y = COL_X[col], ROW_Y[row]
    return _box(win, (x - 6, y - 8, x - 6 + ROW_W, y - 8 + ROW_H))


def work_roi(win: Window, margin: int = TOOLTIP_MARGIN) -> tuple[int, int, int, int]:
    """Window plus room to the right for a tooltip that overhangs the frame, clipped."""
    x0, y0, x1, y1 = window_box(win)
    return max(0, x0 - 20), max(0, y0), min(FRAME_W, x1 + margin), min(FRAME_H, y1 + 20)


def crop(frame: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = box
    h, w = frame.shape[:2]
    return frame[max(0, y0):min(h, y1), max(0, x0):min(w, x1)]


def change_fraction(a: np.ndarray, b: np.ndarray, level: int = CHANGE_LEVEL) -> float:
    """Share of pixels that differ by more than ``level``; 1.0 when the shapes differ.

    Preferred over a dHash everywhere a region is mostly flat parchment: a dHash
    of the search box is essentially noise (12-19 of 64 bits flip between two
    identical frames, because a blinking caret is the only structure in it),
    while this metric stays at 0.00 and rises to 0.03+ on a real keystroke.
    """
    if a.shape != b.shape or a.size == 0:
        return 1.0
    return float((cv2.absdiff(a, b) > level).mean())


def row_change_fractions(a: np.ndarray, wa: Window, b: np.ndarray, wb: Window) -> list[float]:
    """:func:`change_fraction` of each of the 21 list cells, in reading order."""
    return [change_fraction(crop(a, row_box(wa, c, r)), crop(b, row_box(wb, c, r)))
            for c in range(COLUMNS) for r in range(ROWS)]


def list_change(a: np.ndarray, wa: Window, b: np.ndarray, wb: Window) -> float:
    """Median per-cell change of the list -- how different two pages are, ignoring a tooltip.

    The median rather than the mean because a hover tooltip blots out four to six
    of the 21 cells: those cells change completely, the other fifteen do not, and
    a mean would sit halfway between "same page" and "different page". Measured
    over the paladin window: 0.000-0.003 while the page holds still (a tooltip
    coming and going included) and 0.14 when the list itself changes.
    """
    return float(np.median(row_change_fractions(a, wa, b, wb)))


def page_changed(a: np.ndarray, wa: Window, b: np.ndarray, wb: Window,
                 threshold: float = STATE_CHANGE) -> bool:
    """True when two frames show different spellbook lists.

    Three tests, because each catches what the others miss: the heading catches
    a tab switch, the search text catches a new query under the same heading
    ("Name Matches" twice), and the list catches a change with neither -- which
    is what toggling "Show all spell ranks" does.
    """
    for rel in (TITLE_TEXT, SEARCH_TEXT):
        if change_fraction(crop(a, _box(wa, rel)), crop(b, _box(wb, rel))) > threshold:
            return True
    return list_change(a, wa, b, wb) > threshold


def composite(frames: Sequence[np.ndarray], q: float = 0.85) -> np.ndarray:
    """Per-pixel ``q`` quantile of equally shaped frames: the page without its tooltip.

    A median would keep a tooltip that is up for more than half of a state, and
    several are (the paladin's Seal of the Crusader hover covers 20 of 38
    frames). The tooltip is *dark* and the parchment under it is bright, so a
    high quantile removes it whenever any frame of the state showed that pixel
    uncovered, while staying robust to the one bright frame a mouse cursor makes.
    ``np.partition`` keeps uint8, where ``np.quantile`` would copy to float64.
    """
    stack = np.stack(list(frames))
    k = int(round(q * (len(stack) - 1)))
    return np.partition(stack, k, axis=0)[k]


# --------------------------------------------------------------------------- which cells hold a spell

def cell_variance(frame: np.ndarray, win: Window, col: int, row: int) -> float:
    """Laplacian variance of one icon box; bare parchment is flat, an icon is not."""
    c = crop(frame, icon_box(win, col, row))
    if c.size == 0:
        return 0.0
    g = c if c.ndim == 2 else cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def cell_filled(frame: np.ndarray, win: Window, col: int, row: int,
                threshold: float = ICON_MIN_VARIANCE) -> bool:
    return cell_variance(frame, win, col, row) >= threshold


def filled_cells(frame: np.ndarray, win: Window,
                 threshold: float = ICON_MIN_VARIANCE) -> list[tuple[int, int]]:
    """``(col, row)`` of every cell showing an icon, in reading order (column-major).

    The spellbook fills column by column, so the count is a cheap cross-check on
    the reader: a column that reports more names than it has icons invented one.
    """
    return [(c, r) for c in range(COLUMNS) for r in range(ROWS)
            if cell_filled(frame, win, c, r, threshold)]


def column_counts(cells: Iterable[tuple[int, int]]) -> list[int]:
    counts = [0] * COLUMNS
    for c, _ in cells:
        counts[c] += 1
    return counts


# --------------------------------------------------------------------------- hover anchoring

#: The tooltip grows upwards from the row it describes: its bottom edge lands within a
#: few pixels of that row's icon top and its left edge where the row's name starts
#: (measured on four hovers: paladin Seal of the Crusader, shaman Stoneclaw Totem,
#: mage Fire Ward, druid Tranquility -- bottom offsets -11..+2, left offsets 39..43).
TOOLTIP_ANCHOR_DY = 0
TOOLTIP_ANCHOR_DX = 41
ANCHOR_TOLERANCE_Y = 30
ANCHOR_TOLERANCE_X = 60


#: The tooltip body is a translucent box, grey 20-90 over parchment -- lighter than the
#: talent window's near-black tooltip, so ``ui.TOOLTIP_DARK_LEVEL`` (40) rejects it.
TOOLTIP_GREY = 95
TOOLTIP_MIN_DARK = 0.60
TOOLTIP_W_RANGE = (140, 380)
TOOLTIP_H_MIN = 50
TOOLTIP_MIN_BOX = 6000


def tooltip_mask(gray: np.ndarray, background: np.ndarray, thresh: int = 25,
                 grey: int = TOOLTIP_GREY) -> np.ndarray:
    """Pixels that both changed against the state's own page and are tooltip-dark.

    The change test alone keeps the mouse cursor and anything the world does
    behind a half-covered window; the darkness test alone keeps the window frame
    and every spell icon. Together they leave the tooltip.
    """
    changed = cv2.absdiff(gray, background) > thresh
    return ((changed) & (gray < grey)).astype(np.uint8) * 255


def find_tooltip(gray: np.ndarray, background: np.ndarray, win: Window,
                 thresh: int = 25) -> tuple[int, int, int, int] | None:
    """The hover tooltip in one frame, as ``(x, y, w, h)``, or None.

    Both images are the *window* crop (the world outside it moves, and against a
    high-quantile composite that motion masses into blobs larger than any
    tooltip). A box that reaches the window's right edge is then grown into the
    frame, because the third column's tooltips overhang it by up to 60 px.
    Anchoring is the last filter: a candidate that fits no list cell is dropped,
    which is what keeps a dark patch of world out of the results.
    """
    from .ui import trim_bbox

    mask = tooltip_mask(gray, background, thresh)
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(closed, 8)
    best, best_area = None, 0
    for i in range(1, n):
        x, y, w, h, _ = (int(v) for v in stats[i])
        if w * h < TOOLTIP_MIN_BOX:
            continue
        bx, by, bw, bh = trim_bbox(mask, (x, y, w, h), 0.45)
        if not (TOOLTIP_W_RANGE[0] <= bw <= TOOLTIP_W_RANGE[1] and bh >= TOOLTIP_H_MIN):
            continue
        inner = gray[by + 4:by + bh - 4, bx + 4:bx + bw - 4]
        if not inner.size or float((inner < TOOLTIP_GREY).mean()) < TOOLTIP_MIN_DARK:
            continue
        if tooltip_cell(win, (bx, by, bw, bh)) is None:
            continue
        if bw * bh > best_area:
            best, best_area = (bx, by, bw, bh), bw * bh
    return best


def grow_right(gray: np.ndarray, bbox: tuple[int, int, int, int], limit: int = TOOLTIP_W_RANGE[1],
               fill: float = 0.8, grey: int = TOOLTIP_GREY) -> tuple[int, int, int, int]:
    """Extend a tooltip box rightwards while the next column is still tooltip-dark.

    Called on the full frame after :func:`find_tooltip` found the box inside the
    window: a tooltip anchored at the third column runs past the window's right
    edge, and the text that is cut there is exactly the cooldown and range.
    """
    x, y, w, h = bbox
    x1 = x + w
    while x1 < gray.shape[1] and x1 - x < limit:
        col = gray[y:y + h, x1]
        if not col.size or float((col < grey).mean()) < fill:
            break
        x1 += 1
    return x, y, x1 - x, h


def tooltip_cell(win: Window, bbox: tuple[int, int, int, int]) -> tuple[int, int] | None:
    """``(col, row)`` of the list entry a tooltip box is anchored to, or None.

    The spellbook anchors the box above the hovered row and level with the start
    of its name, so the bottom-left corner identifies the cell. A box that fits
    no cell is left unanchored rather than assigned to the nearest one -- the
    reading still carries the spell name, which ``build`` matches by name.
    """
    x, y, w, h = bbox
    best: tuple[int, int] | None = None
    best_d = None
    for c in range(COLUMNS):
        ax = win.x + COL_X[c] + TOOLTIP_ANCHOR_DX
        if abs(x - ax) > ANCHOR_TOLERANCE_X:
            continue
        for r in range(ROWS):
            ay = win.y + ROW_Y[r] - TOOLTIP_ANCHOR_DY
            d = abs((y + h) - ay)
            if d > ANCHOR_TOLERANCE_Y:
                continue
            score = (d, abs(x - ax))
            if best_d is None or score < best_d:
                best, best_d = (c, r), score
    return best


# --------------------------------------------------------------------------- list text

_RANK_RE = re.compile(r"^\s*rank\s*([0-9]{1,2})\s*$", re.I)
_RANK_TAIL_RE = re.compile(r"\s*[-,]?\s*rank\s*([0-9]{1,2})\s*$", re.I)
#: The grey subtitle glued onto the end of the name, the way ``Rank N`` is. ``races.py`` has had
#: ``strip_kind`` since it shipped; the spellbook did not, which is exactly how the fabricated
#: ``shaman/reincarnation-passive`` was minted (review round two, K-4 / V-4).
_KIND_TAIL_RE = re.compile(r"\s*[-,(]?\s*(racial\s+passive|racial|passive)\s*\)?\s*$", re.I)
#: Subtitles the list shows that are a kind, not a rank.
_KINDS = {
    "passive": "passive",
    "racial": "racial",
    "racial passive": "racial-passive",
    "racial (passive)": "racial-passive",
}


def parse_rank(subtitle: str | None) -> int | None:
    """``"Rank 4"`` -> 4; anything else -> None."""
    m = _RANK_RE.match(clean_text(subtitle or ""))
    return int(m.group(1)) if m else None


def entry_kind(subtitle: str | None) -> str:
    """List subtitle -> ``active`` | ``passive`` | ``racial`` | ``racial-passive``.

    A rank line means the entry is castable, so a spell with ranks is ``active``;
    the spellbook prints nothing under a plain active spell either.
    """
    s = clean_text(subtitle or "").lower().strip(" .")
    return _KINDS.get(s, "active")


def strip_rank(name: str) -> str:
    """Names sometimes arrive with the subtitle glued on ("Holy Strike Rank 5", "Reincarnation Passive")."""
    return clean_text(_KIND_TAIL_RE.sub("", clean_text(_RANK_TAIL_RE.sub("", clean_text(name or "")))))


def strip_kind(name: str) -> tuple[str, str | None]:
    """``("Reincarnation", "Passive")`` -- the name with its glued-on subtitle taken off.

    The spellbook prints the kind as a smaller grey line under the name; when the two run
    together in one reading the kind must go back to where it belongs rather than become part
    of the id. The analogue of ``races.strip_kind``.
    """
    text = clean_text(name or "")
    m = _KIND_TAIL_RE.search(text)
    if not m:
        return text, None
    return clean_text(text[:m.start()]), m.group(1).title()


def spell_id(name: str) -> str:
    return slug(strip_rank(name))


#: Page headings the spellbook shows for search results rather than a tab.
SEARCH_TITLES = {"name matches", "exact matches", "related matches", "no matches"}


def page_slug(title: str | None) -> str:
    return slug(clean_text(title or ""))


def tab_from_title(title: str | None) -> str | None:
    """The tab a page heading names, or None when the heading is a search result."""
    s = page_slug(title)
    if not s or clean_text(title or "").lower() in SEARCH_TITLES:
        return None
    return s


#: token_sort_ratio at which a page heading is a misread of a known tab name.
#: "Marksmananship" vs "Marksmanship" scores 92, "Survival" vs "Subtlety" 47.
TITLE_SNAP = 88


def snap_title(title: str | None, candidates: Iterable[str],
               threshold: float = TITLE_SNAP) -> tuple[str, bool]:
    """``(heading, snapped)`` -- a near-miss heading corrected to the tab name it must be.

    The reader turned the hunter's "Marksmanship" into "Marksmananship" on one
    page; left alone that mints a second tab id for the same tab. Only a
    near-miss is corrected, so a genuine Forever rename (Classic "Elemental" ->
    Forever "Elemental Combat", ratio 72) survives as itself.
    """
    from rapidfuzz import fuzz

    text = clean_text(title or "")
    if not text:
        return "", False
    best, score = None, 0.0
    for cand in candidates:
        r = fuzz.token_sort_ratio(text.lower(), cand.lower())
        if r > score:
            best, score = cand, r
    if best is None or score < threshold:
        return text, False
    if best.lower() == text.lower():
        return best, False      # same heading, canonical casing ("general" -> "General")
    return best, True


def normalise_entry(e: dict) -> dict:
    """One reader entry -> ``{name, rank, kind, cut_off}`` with the field contract enforced.

    The model likes to answer with the whole row as the name ("Blessing of Might
    Rank 4") or to put the rank in the subtitle field as a bare number; both are
    repaired here rather than in the prompt, where it would cost a retry.
    """
    raw_name, glued = strip_kind(clean_text(e.get("name") or ""))
    sub = clean_text(e.get("subtitle") or "") or (glued or "")
    rank = parse_rank(sub)
    if rank is None and re.fullmatch(r"[0-9]{1,2}", sub):
        rank = int(sub)
        sub = f"Rank {rank}"
    tail = _RANK_TAIL_RE.search(raw_name)
    if tail:
        rank = rank if rank is not None else int(tail.group(1))
        if not sub:
            sub = f"Rank {rank}"
    name = strip_rank(raw_name)
    return {"name": name, "rank": rank, "kind": entry_kind(sub) if rank is None else "active",
            "cut_off": bool(e.get("cut_off"))}


#: Headings and column labels the page shows that are not spells.
NON_SPELL_IDS = {"general", "name-matches", "exact-matches", "related-matches", "spellbook",
                 "page", "rank", "passive", "racial", "racial-passive"}
#: The longest spell name on any page seen is "Shadow Resistance Aura" (22). A reading
#: past this is a tooltip's body that the model filed as a list row, which happens when a
#: hover stands over the column it was reading.
MAX_NAME_LEN = 44


def looks_like_prose(name: str) -> bool:
    """True when a 'name' is really a sentence: too long, punctuated or cased like one.

    Three tests, all met by real spell names and failed by a tooltip body that the
    model filed as a list row. The casing test needs four words before it fires, so
    "Seal of the Crusader" (two of four capitalised, exactly half) is safe while
    "Afflicts the target with agony" (one of five) is not.
    """
    text = clean_text(name or "")
    if len(text) > MAX_NAME_LEN:
        return True
    if re.search(r"[.;]\s", text) or text.endswith("."):
        return True
    words = [w for w in re.split(r"\s+", text) if w]
    if len(words) >= 4:
        capitals = sum(1 for w in words if w[:1].isupper())
        return capitals * 2 < len(words)
    return False


def clean_page_reading(doc: dict) -> list[dict]:
    """One column reading, deduplicated and stripped of headings and stray prose."""
    out: list[dict] = []
    seen: set[tuple[str, int | None]] = set()
    for e in doc.get("entries") or []:
        n = normalise_entry(e)
        sid = spell_id(n["name"])
        if not sid or sid in NON_SPELL_IDS or looks_like_prose(n["name"]):
            continue
        key = (sid, n["rank"])
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
    return out


def entry_key(e: dict) -> tuple:
    return (spell_id(e.get("name") or ""), e.get("rank"), e.get("kind"))


def confidence(a: dict, b: dict | None) -> float:
    """Stage 5's three-valued agreement, on a list row.

    1.0 both passes read the same name, rank and kind, 0.7 the same name but a
    different rank or kind, 0.3 otherwise (0.0 when only one pass saw the row).
    """
    if b is None:
        return 0.0
    if entry_key(a) == entry_key(b):
        return 1.0
    if spell_id(a.get("name") or "") == spell_id(b.get("name") or ""):
        return 0.7
    return 0.3


def show_all_ranks(entries: Sequence[dict]) -> bool:
    """True when a page lists one spell more than once with different ranks.

    That is the visible effect of the spellbook option "Show all spell ranks";
    with it off the list holds one row per spell showing its highest rank.
    """
    seen: dict[str, set[int]] = {}
    for e in entries:
        rank = e.get("rank")
        if rank is None:
            continue
        seen.setdefault(spell_id(e.get("name") or ""), set()).add(int(rank))
    return any(len(v) > 1 for v in seen.values())


def _score(rec: dict) -> tuple:
    """Ranking of two readings of the same row: complete text, agreement, sharpness."""
    src = rec.get("source") or {}
    return (0 if rec.get("cut_off") else 1,
            float(src.get("confidence") or 0.0),
            float(src.get("sharpness") or 0.0))


def merge_entries(records: Iterable[dict]) -> list[dict]:
    """One record per spell, with every rank that spell was listed at.

    The list shows one row per *rank* when "Show all spell ranks" is on, so the
    four Blessing of Might rows of the paladin's Retribution page are one spell
    known at four ranks, not four spells. Entries keep the page's own order --
    column-major, which for every page seen is also alphabetical -- from the
    first cell the spell appeared in. Readings that lost are kept under
    ``alternates`` so a reviewer can see what the other states said.
    """
    best: dict[str, dict] = {}
    others: dict[str, list[dict]] = {}
    order: dict[str, tuple] = {}
    ranks: dict[str, set[int]] = {}
    for rec in records:
        key = spell_id(rec.get("name") or "")
        if not key:
            continue
        cell = (int(rec.get("col", 9)), int(rec.get("row", 9)))
        if key not in order or cell < order[key]:
            order[key] = cell
        if rec.get("rank") is not None:
            ranks.setdefault(key, set()).add(int(rec["rank"]))
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
        seen = {entry_key(rec)}
        alts = []
        for o in others.get(key, []):
            k = entry_key(o)
            if k in seen:
                continue
            seen.add(k)
            alts.append(o)
        if alts:
            rec["alternates"] = alts
        rec["cell"] = list(order[key])
        rec["ranks"] = sorted(ranks.get(key, ()))
        out.append(rec)
    return sorted(out, key=lambda r: (r["cell"], r["name"]))


def dedupe_tooltips(items: Sequence[dict], image_of, max_hamming: int = 6) -> list[dict]:
    """The sharpest copy of each distinct tooltip, per class.

    One hover survives several page states (the list under it does not have to
    hold still) and the same spell is often hovered twice, so without this the
    reader pays for the same box four or five times. dHash is safe here, unlike
    on the flat chrome: a tooltip is dense text on a dark ground.
    """
    from .ui import dhash, hamming

    keep: list[dict] = []
    for it in sorted(items, key=lambda i: -float(i.get("sharpness") or 0.0)):
        img = image_of(it)
        if img is None:
            continue
        h = dhash(cv2.resize(img, (64, 64), interpolation=cv2.INTER_AREA))
        if any(k["_class"] == it.get("_class") and hamming(k["_hash"], h) <= max_hamming for k in keep):
            continue
        keep.append({**it, "_hash": h})
    return sorted(keep, key=lambda i: float(i["t"]))


def dedupe_states(states: Sequence[dict], page_of, threshold: float = STATE_CHANGE) -> list[dict]:
    """The sharpest copy of each distinct page, at most one reading per page.

    The same page comes back in several windows and at both ends of every hover,
    so reading every state would pay the VLM three times for the same pixels.
    ``page_of(state)`` returns that state's median page crop (greyscale or BGR);
    a state whose crop cannot be loaded is kept rather than dropped.
    """
    keep: list[dict] = []
    cache: dict[str, np.ndarray | None] = {}

    def page(st: dict) -> np.ndarray | None:
        if st["id"] not in cache:
            img = page_of(st)
            if img is not None and img.ndim == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cache[st["id"]] = img
        return cache[st["id"]]

    for st in sorted(states, key=lambda s: -float(s.get("sharpness") or 0.0)):
        mine = page(st)
        if mine is not None and any(
                k.get("class") == st.get("class") and (other := page(k)) is not None
                and change_fraction(mine, other) <= threshold for k in keep):
            continue
        keep.append(st)
    return sorted(keep, key=lambda s: float(s["t"]))


# --------------------------------------------------------------------------- reader merge
#
# Round two (``docs/reviews/2026-09-14-data-code-perf.md`` D-1) found 10 of 12 sampled
# ``confidence: 1.0`` tooltips carrying the reader defects round one had already catalogued
# for talents. The cause is structural: stage 11 scores a tooltip by comparing two passes of
# *the same* VLM over the same pixels, so when both passes make the same mistake -- and at
# 1080p a comma and a full stop are the same two-pixel blob for both -- agreeing on the
# mistake scores 1.0. Two passes of one reader are a repeatability check, never corroboration.
#
# So the spellbook uses the shape-aware merge of ``wowtalents.merge``, with one rule tightened
# for this dataset:
#
# * **case, punctuation and percent** hunks go to the shape authority (the codex CLI reading),
#   exactly as for talents - the audit found it right ~100 % of the time on all three;
# * a **word** hunk is still voted on, but *any* word hunk left after the merge, settled or
#   not, drops the record to ``DISPUTED_CONFIDENCE`` and names both variants. The talent merge
#   could let a vote settle wording because its audit had measured the primary reader at ~70 %
#   on words; no such audit exists for the spellbook, so a wording disagreement between two
#   independent readers goes to a human instead of to a coin toss. That is what surfaced
#   ``mage/dampen-magic`` ("Dampons"), the two wrong footers and the flattened language list,
#   none of which any regex can find;
# * a record with **no independent reading at all** is capped at ``UNCORROBORATED_CONFIDENCE``:
#   still out of the review queue, but no longer claiming certainty it has not earned.

from . import merge as _merge  # noqa: E402

#: Reader label of the shape authority inside ``readings[]``.
AUTHORITY_READER = "codex"
#: Confidence of a record every reader agreed on verbatim.
SETTLED_CONFIDENCE = 1.0
#: Only shape hunks, all adjudicated by the authority: the text is corrected but unreviewed.
ADJUDICATED_CONFIDENCE = 0.9
#: Two passes of one reader agreeing, with no independent reading to corroborate them.
UNCORROBORATED_CONFIDENCE = 0.9
#: A word the readers do not agree on: review queue.
DISPUTED_CONFIDENCE = 0.7
#: Text fields of a tooltip the merge adjudicates.
TOOLTIP_TEXT_FIELDS = ("description", "footer")
#: Non-text tooltip fields; a disagreement here is a doubt the merge cannot settle.
TOOLTIP_FIELDS = ("cost", "range", "cast_time", "cooldown", "tools")


def is_authority(reading: dict) -> bool:
    return AUTHORITY_READER in str(reading.get("reader") or "").lower()


def split_readings(readings: Sequence[dict]) -> tuple[dict | None, dict | None, list[dict]]:
    """``(primary, authority, others)`` -- the authority is the first non-VLM reading."""
    rest = [r for r in readings if isinstance(r, dict) and not is_authority(r)]
    auth = next((r for r in readings if isinstance(r, dict) and is_authority(r)), None)
    if not rest:
        # a row only the authority saw: it is the primary and has nothing to merge against
        return auth, None, []
    return rest[0], auth, rest[1:]


def _merge_field(primary: str, authority: str, others: Sequence[str]) -> tuple[str, list, dict]:
    res = _merge.merge_readings(primary, authority, others)
    return res.text, res.hunks, res.counts()


def merge_tooltip(readings: Sequence[dict]) -> dict:
    """Shape-aware merge of one tooltip's readings.

    Returns ``{"fields": {...}, "confidence": float, "shapes": {...}, "disputed": [...]}``.
    ``fields`` holds only the keys the merge rewrote, so the caller can update the record it
    already has. Pure: no I/O, no network.
    """
    readings = [r for r in readings if isinstance(r, dict)]
    primary, auth, others = split_readings(readings)
    fields: dict[str, str] = {}
    shapes: dict[str, int] = {}
    disputed: list[str] = []
    if primary is None:
        return {"fields": fields, "confidence": 0.0, "shapes": shapes, "disputed": disputed}

    for field in TOOLTIP_TEXT_FIELDS:
        text = clean_text(primary.get(field) or "")
        if auth is not None:
            text, hunks, counts = _merge_field(
                text, clean_text(auth.get(field) or ""),
                [clean_text(o.get(field) or "") for o in others])
            for k, v in counts.items():
                shapes[k] = shapes.get(k, 0) + v
            for h in hunks:
                if h.kind == _merge.WORD:
                    disputed.append(f"{field} {h.primary!r} vs {h.other!r}")
        # belt and braces: a capital I both readers agreed on is still wrong
        text, lowered = _merge.normalise_capital_i(text, min_tail=1)
        if lowered:
            shapes["case"] = shapes.get("case", 0) + len(lowered)
        fields[field] = text

    name = clean_text(primary.get("name") or "")
    if auth is not None and (auth_name := clean_text(auth.get("name") or "")):
        if auth_name.lower() == name.lower() and auth_name != name:
            name = auth_name                    # same name, different case: the authority wins
            shapes["case"] = shapes.get("case", 0) + 1
        elif auth_name.lower() != name.lower():
            disputed.append(f"name {name!r} vs {auth_name!r}")
    fields["name"] = name

    if auth is not None:
        for field in TOOLTIP_FIELDS:
            a, b = clean_text(primary.get(field) or ""), clean_text(auth.get(field) or "")
            if a and b and a != b:
                disputed.append(f"{field} {a!r} vs {b!r}")

    return {"fields": fields, "shapes": shapes, "disputed": disputed,
            "confidence": merged_confidence(readings, disputed, shapes)}


def merge_entry(readings: Sequence[dict]) -> dict:
    """Shape-aware merge of one list row's readings (name only; rank and kind are not text)."""
    readings = [r for r in readings if isinstance(r, dict)]
    primary, auth, others = split_readings(readings)
    shapes: dict[str, int] = {}
    disputed: list[str] = []
    if primary is None:
        return {"fields": {}, "confidence": 0.0, "shapes": shapes, "disputed": disputed}
    name = strip_rank(primary.get("name") or "")
    if auth is not None and (auth_name := strip_rank(auth.get("name") or "")):
        if auth_name.lower() == name.lower():
            if auth_name != name:
                shapes["case"] = shapes.get("case", 0) + 1
            name = auth_name
        else:
            # a real name disagreement is never merged away: it is how "Rummel Whirlwind"
            # and "Evocation Dampen Magic" were minted in the first place
            disputed.append(f"name {name!r} vs {auth_name!r}")
    name, lowered = _merge.normalise_capital_i(name, min_tail=1)
    if lowered:
        shapes["case"] = shapes.get("case", 0) + len(lowered)
    if auth is not None:
        for field in ("rank", "kind"):
            if primary.get(field) != auth.get(field):
                disputed.append(f"{field} {primary.get(field)!r} vs {auth.get(field)!r}")
    return {"fields": {"name": name}, "shapes": shapes, "disputed": disputed,
            "confidence": merged_confidence(readings, disputed, shapes)}


def merged_confidence(readings: Sequence[dict], disputed: Sequence[str],
                      shapes: dict[str, int]) -> float:
    """Confidence that reflects *who* agreed, not how many passes ran.

    ``1.0`` needs an independent reading that agreed verbatim. Anything the authority had to
    correct is ``0.9`` (right, but nobody has looked at it); anything still disputed is ``0.7``
    and therefore in the review queue; a lone reading stays ``0.0`` as before.
    """
    if not readings:
        return 0.0
    if len(readings) == 1:
        return 0.0
    if disputed:
        return DISPUTED_CONFIDENCE
    if not any(is_authority(r) for r in readings):
        return UNCORROBORATED_CONFIDENCE
    return ADJUDICATED_CONFIDENCE if shapes else SETTLED_CONFIDENCE

"""Rank anticipation (stage 6): derive ranks 2..N of a Forever talent from its
rank-1 tooltip text and the Classic Era prior.

Implements docs/briefs/data-prior-and-review.md section (b). Pure functions
over ``data/prior/classic-era/talents.json``; no I/O except ``Prior.load``.

Entry point::

    prior = Prior.load()
    res = anticipate("Toughness", "Increases your armor value from items by 2%.", 5, "paladin", prior)
    res.to_fields()   # description, ranks, ranksObserved, ranksSource, ranksPrior/ranksNote, needsManual

Scaling rule (2026-09-13, revised): **anticipated ranks are ``v1 * k``.** A Forever talent
scales proportionally from its own rank 1, whatever shape Classic has. The single exception
is a verbatim copy: an **exact same-name** Classic talent with the **same rank count** whose
**rank 1 equals Forever's** — then Classic's own numbers are used, because they are
Blizzard's and not our arithmetic. Every other case is proportional; when the Classic slot
is not proportional (affine ``10/15/20 = 5k + 5``, or irregular ``15/30/45/65``) the pattern
that was *not* applied is named in ``ranksNote`` and the record drops to ``low`` confidence.
Classic's offset is never re-based onto a foreign rank 1: that is what produced
23/40.25/57.5 for priest ``Twilight Focus`` (owner report), values nobody would design.
Values that look like something Blizzard would round (51 -> 50) are reported in
``ranksNote`` ("Rounding: ...") and never rounded in the data.

Decision table (``ranksSource`` / confidence):

    maxRank == 1                                            observed       high
    exact same-class name, c1 == f1, same rank count        classic-prior  high   (copied)
    exact cross-class name, c1 == f1, same rank count       classic-prior  medium (copied, review queue)
    ("exact" is full-string key equality; the fuzzy tier uses token_sort_ratio, so a token subset
    such as "Divine Precision" vs "Precision" never scores 1.0 and never skips review)
    Classic match, proportional slot, other base/rank count classic-prior  medium (f1 * k, review queue)
    Classic match, non-proportional slot not copied         classic-prior  low    (f1 * k, pattern named
                                                                                   in the note, review queue)
    Classic shape-changing text, rank 1 identical           classic-prior  medium (per-rank strings copied)
    Classic duration in another unit (60 sec vs 1 min)      classic-prior  medium (Classic converted to Forever's unit, review queue)
    Classic duration unit does not convert whole (45 sec vs 1 min) manual  -      (rank 1 copied, review queue)
    Classic match but slot counts cannot be aligned         -> falls through to the no-match rows
    (a description-only match also requires the same rank count)
    no match, 1 or 2 numeric slots, none a duration         extrapolated   low    (v1 * k, review queue)
    no match, 0 or >= 3 slots, or any duration slot         manual         -      (review queue)

Templates follow docs/DATA-SCHEMA.md section 5 and the prior's ``build.py``:
numbers become ``{n}`` slots, ``%`` and ``sec``/``min`` stay in the template,
a word that pluralises with the number becomes a ``""``/``"s"`` slot
(``"{0} rage point{1}."``). Plural values are computed from the number,
never copied from Classic. A number preceded by ``Rank`` is never a slot.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from . import text as _text

PRIOR_PATH = Path(__file__).resolve().parents[3] / "data" / "prior" / "classic-era" / "talents.json"

# Same tokeniser as data/prior/classic-era/build.py so slot positions line up.
TOKEN_RE = re.compile(r"\d+(?:\.\d+)?|(?<!\d)\.\d+|[A-Za-z]+")
NUM_RE = re.compile(r"^(?:\d+(?:\.\d+)?|\.\d+)$")

DURATION_UNITS = {"sec", "secs", "second", "seconds", "min", "mins", "minute", "minutes", "hr", "hrs", "hour", "hours"}
DURATION_SECONDS = {"sec": 1, "secs": 1, "second": 1, "seconds": 1, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
                    "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600}
PLURAL_STOPWORDS = {"in", "of", "to", "for", "and", "or", "per", "from", "on", "by", "with", "while", "that", "when",
                    "the", "a", "an", "at", "is", "are", "if", "over", "up", "down", "than", "more", "less",
                    # comparatives never carry the plural: "2 levels higher", not "2 level highers"
                    "higher", "lower", "longer", "shorter", "faster", "slower", "further", "farther", "greater",
                    "smaller", "deeper", "closer", "wider", "stronger", "weaker"}

FRACTION_HINT_MIN = 5.0      # below this a fractional scaled value is taken at face value
NAME_THRESHOLD = 90.0        # rapidfuzz token_sort_ratio on names (brief (b), validator rule 15)
DESC_THRESHOLD = 85.0        # token_ratio on number-masked descriptions (brief (b) step 3)
MAXRANK_PENALTY = 10.0       # brief (b) step 2


# ----------------------------------------------------------------------------
# Text helpers (mirroring data/prior/classic-era/build.py)
# ----------------------------------------------------------------------------

# One slug rule and one text normaliser, both defined in wowtalents.text (DATA-SCHEMA sections 2-3).
# They stay importable from here because every stage and data/prior/.../build.py already call R.slug.
slug = _text.slug
clean_text = _text.clean_text


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 1 and word.endswith("s") else word


def skeleton(text: str) -> str:
    """Numbers masked, words stemmed: equal skeletons mean token-for-token alignment."""
    return TOKEN_RE.sub(lambda m: "\x00" if NUM_RE.match(m.group()) else _stem(m.group()), text)


def masked(text: str) -> str:
    """Numbers replaced by a marker, for description similarity."""
    return TOKEN_RE.sub(lambda m: "N" if NUM_RE.match(m.group()) else m.group(), text)


def num_value(s: str) -> int | float:
    return float(s) if "." in s else int(s)


def nice(x: float | int) -> int | float:
    """Integers stay integers, floats are rounded to 2 decimals (0.1 * 3 -> 0.3)."""
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, int):
        return x
    r = round(float(x), 2)
    return int(r) if r.is_integer() else r


def varying_positions(rank_texts: list[str]) -> list[int] | None:
    """Token positions that differ between the per-rank texts (None when the sentence shape changes)."""
    if len(rank_texts) < 2:
        return []
    if len({skeleton(t) for t in rank_texts}) != 1:
        return None
    toks = [TOKEN_RE.findall(t) for t in rank_texts]
    return [i for i in range(len(toks[0])) if len({row[i] for row in toks}) > 1]


# ----------------------------------------------------------------------------
# Tokens of the Forever rank-1 text
# ----------------------------------------------------------------------------

@dataclass
class Token:
    pos: int            # index among TOKEN_RE matches
    start: int
    end: int
    text: str

    @property
    def is_number(self) -> bool:
        return bool(NUM_RE.match(self.text))


def tokenize(text: str) -> list[Token]:
    return [Token(i, m.start(), m.end(), m.group()) for i, m in enumerate(TOKEN_RE.finditer(text))]


@dataclass
class NumberInfo:
    token: Token
    value: int | float
    is_duration: bool       # followed by sec/min (never extrapolated)
    is_percent: bool
    is_rank_ref: bool       # "(Rank 1)": never a slot
    head_word: Token | None  # candidate plural noun ("point" in "1 rage point")


def _following_words(tokens: list[Token], text: str, pos: int, limit: int = 3) -> list[Token]:
    """Word tokens after tokens[pos] up to a punctuation mark, a stop word, a unit or `limit` words."""
    out: list[Token] = []
    prev_end = tokens[pos].end
    for t in tokens[pos + 1:pos + 1 + limit]:
        gap = text[prev_end:t.start]
        if gap.strip(" ") != "":      # punctuation between tokens ends the phrase
            break
        if t.is_number or t.text[0].isupper() or t.text.lower() in PLURAL_STOPWORDS or t.text.lower() in DURATION_UNITS:
            break
        out.append(t)
        prev_end = t.end
    return out


def number_infos(text: str, tokens: list[Token] | None = None) -> list[NumberInfo]:
    tokens = tokens if tokens is not None else tokenize(text)
    out: list[NumberInfo] = []
    for t in tokens:
        if not t.is_number:
            continue
        after = text[t.end:t.end + 12]
        nxt = tokens[t.pos + 1] if t.pos + 1 < len(tokens) else None
        prev = tokens[t.pos - 1] if t.pos > 0 else None
        is_percent = after.startswith("%")
        is_duration = bool(nxt and nxt.text.lower() in DURATION_UNITS and text[t.end:nxt.start].strip() == "")
        is_rank_ref = bool(prev and prev.text.lower() == "rank" and text[prev.end:t.start].strip() == "")
        head = None
        if not is_percent and not is_duration and not is_rank_ref:
            words = _following_words(tokens, text, t.pos)
            head = words[-1] if words else None
        out.append(NumberInfo(t, num_value(t.text), is_duration, is_percent, is_rank_ref, head))
    return out


# ----------------------------------------------------------------------------
# Template building
# ----------------------------------------------------------------------------

@dataclass
class Slot:
    index: int                  # {index}
    kind: str                   # "num" | "plural"
    token: Token
    number_slot: int | None = None   # for plural: index of the governing numeric slot


def build_template(text: str, tokens: list[Token], slots: list[Slot]) -> str:
    """Replace slot tokens by {n}; plural slots keep their stem: "point{1}"."""
    by_pos = {s.token.pos: s for s in slots}
    parts: list[str] = []
    last = 0
    for t in tokens:
        parts.append(text[last:t.start])
        s = by_pos.get(t.pos)
        if s is None:
            parts.append(t.text)
        elif s.kind == "num":
            parts.append("{%d}" % s.index)
        else:
            parts.append(_stem(t.text) + "{%d}" % s.index)
        last = t.end
    parts.append(text[last:])
    return "".join(parts)


def plural_value(n: int | float) -> str:
    return "" if n == 1 else "s"


def render(template: str, values: list[Any]) -> str:
    return re.sub(r"\{(\d+)\}", lambda m: str(values[int(m.group(1))]), template)


# ----------------------------------------------------------------------------
# Classic Era prior
# ----------------------------------------------------------------------------

class Prior:
    """data/prior/classic-era/talents.json with per-record class/tree and a few caches."""

    def __init__(self, doc: dict):
        self.records: list[dict] = []
        self.by_class: dict[str, list[dict]] = {}
        self.by_id: dict[int, dict] = {}
        for cls, cdoc in (doc.get("classes") or {}).items():
            for tree in cdoc.get("trees", []):
                for t in tree.get("talents", []):
                    rec = dict(t)
                    rec["class"] = cls
                    rec["tree"] = tree.get("id")
                    rec["treeName"] = tree.get("name")
                    rec["_masked"] = masked(rec["ranks"][0]) if rec.get("ranks") else ""
                    self.records.append(rec)
                    self.by_class.setdefault(cls, []).append(rec)
                    if isinstance(rec.get("classicTalentId"), int):
                        self.by_id[rec["classicTalentId"]] = rec

    @classmethod
    def load(cls, path: Path = PRIOR_PATH) -> "Prior":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def find(self, cls: str, name: str) -> dict | None:
        key = slug(name)
        for r in self.by_class.get(cls, []):
            if r["id"] == key or slug(r["name"]) == key:
                return r
        return None


@dataclass
class Match:
    record: dict
    match: str          # exact-name | fuzzy-name | description
    similarity: float   # 0..1
    cross_class: bool

    @property
    def label(self) -> str:
        r = self.record
        return f"{r['class']}/{r['tree']}/{r['name']} (talent {r.get('classicTalentId')})"


def _name_key(name: str) -> str:
    return slug(clean_text(name))


def name_similarity(a: str, b: str) -> float:
    """0..100 name similarity for the fuzzy tier: ``token_sort_ratio``, never ``token_set_ratio``,
    so a token subset ("Divine Precision" vs Classic "Precision") does not score 100. Only the
    exact tier (full-string key equality) may report 1.0."""
    return float(fuzz.token_sort_ratio(clean_text(a), clean_text(b)))


def _best(cands: list[dict], score_fn, threshold: float, max_rank: int) -> tuple[dict | None, float]:
    best, best_raw, best_adj = None, 0.0, -1.0
    for c in cands:
        raw = float(score_fn(c))
        if raw < threshold:
            continue
        adj = raw - (MAXRANK_PENALTY if c.get("maxRank") != max_rank else 0.0)
        if adj > best_adj:
            best, best_raw, best_adj = c, raw, adj
    return best, best_raw


def match_classic(name: str, text: str, max_rank: int, cls: str, prior: Prior) -> Match | None:
    """Exact name in class -> fuzzy name in class -> exact/fuzzy name across classes -> description."""
    key = _name_key(name)
    same = prior.by_class.get(cls, [])
    others = [r for r in prior.records if r["class"] != cls]
    if key:
        exact = [r for r in same if _name_key(r["name"]) == key]
        if exact:
            rec, _ = _best(exact, lambda r: 100.0, 0.0, max_rank)
            return Match(rec, "exact-name", 1.0, False)
        rec, score = _best(same, lambda r: name_similarity(name, r["name"]), NAME_THRESHOLD, max_rank)
        if rec is not None:
            return Match(rec, "fuzzy-name", min(round(score / 100, 2), 0.99), False)
        exact = [r for r in others if _name_key(r["name"]) == key]
        if exact:
            rec, _ = _best(exact, lambda r: 100.0, 0.0, max_rank)
            return Match(rec, "exact-name", 1.0, True)
        rec, score = _best(others, lambda r: name_similarity(name, r["name"]), NAME_THRESHOLD, max_rank)
        if rec is not None:
            return Match(rec, "fuzzy-name", min(round(score / 100, 2), 0.99), True)
    m = masked(clean_text(text))
    if m:
        # a wording match alone is only trusted when the rank count agrees as well
        for pool, cross in ((same, False), (others, True)):
            pool = [r for r in pool if r.get("maxRank") == max_rank]
            rec, score = _best(pool, lambda r: fuzz.token_ratio(m, r["_masked"]) if r["_masked"] else 0.0,
                               DESC_THRESHOLD, max_rank)
            if rec is not None:
                return Match(rec, "description", min(round(score / 100, 2), 0.99), cross)
    return None


# ----------------------------------------------------------------------------
# Progression classification and scaling
# ----------------------------------------------------------------------------

def proportional_coefficient(values: list[int | float]) -> float | None:
    """The per-rank coefficient ``a`` of a proportional Classic progression (``c_k = a * k``),
    or ``None`` when no such ``a`` exists.

    Integer Classic values only have to sit within half a unit of ``a * k``: the client shows
    rounded numbers, so 16/33/50 is ``50/3`` per rank, not ``16 + 17k``, and 8/16/25 is ``8.2``
    per rank. Decimal values must hit the ray exactly.
    """
    if not values or any(float(v) <= 0 for v in values):
        return None
    ints = all(float(v).is_integer() for v in values)
    tol = 0.5 if ints else 1e-9
    lo, hi = 0.0, float("inf")
    for k, v in enumerate(values, start=1):
        lo = max(lo, (float(v) - tol) / k)
        hi = min(hi, (float(v) + tol) / k)
    if lo > hi or hi <= 0:
        return None
    return (lo + hi) / 2


def progression(values: list[int | float]) -> str:
    """constant | proportional | affine | irregular over Classic per-rank values of one slot.

    ``proportional``  c_k = a * k (5/10/15, 2/4/6/8/10, and 16/33/50 up to display rounding)
    ``affine``        arithmetic with a non-zero offset (10/15/20 = 5k + 5)
    ``irregular``     neither (15/30/45/65)
    """
    if len(values) < 2:
        return "constant"
    d = [round(float(b) - float(a), 6) for a, b in zip(values, values[1:])]
    if all(x == 0 for x in d):
        return "constant"
    if proportional_coefficient(values) is not None:
        return "proportional"
    return "affine" if len(set(d)) == 1 else "irregular"


def rounding_hint(values: list[int | float], first_rank: int = 2) -> str | None:
    """Where a scaled value looks like a number Blizzard would round on the tooltip.

    Two cases: a fraction (40.25 -> 40) and an integer just off a multiple of five
    (51 -> 50, 34 -> 35). Reported only, never applied: ``values`` keeps the raw scaled
    number so the reviewer sees what the rule produced.
    """
    hints = []
    for k, v in enumerate(values[first_rank - 1:], start=first_rank):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        f = float(v)
        if not f.is_integer():
            # a fraction only reads as a rounded tooltip number when the value is big enough
            # for the fraction to be noise (7.5 -> 8), never for a deliberate 0.4 sec
            if f >= FRACTION_HINT_MIN:
                hints.append((k, v, nice(_round_half_up(f))))
            continue
        n = int(f)
        if n < 10 or n % 5 == 0:
            continue
        m = 5 * int(_round_half_up(n / 5))
        if m > 0 and abs(n - m) / n <= 0.05:
            hints.append((k, v, m))
    if not hints:
        return None
    return ", ".join(f"rank {k} {v} may read {m}" for k, v, m in hints)


def _round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


@dataclass
class SlotPlan:
    values: list[int | float]
    rule: str            # constant | copied | proportional
    note: str | None = None
    rounding: str | None = None
    low: bool = False    # Classic's own progression was not proportional and was not applied


def duration_unit(tokens: list[Token], pos: int, text: str) -> str | None:
    """Unit word directly after the number at ``pos`` ("sec"/"min"/...), else None."""
    nxt = tokens[pos + 1] if pos + 1 < len(tokens) else None
    if nxt and nxt.text.lower() in DURATION_UNITS and text[tokens[pos].end:nxt.start].strip() == "":
        return nxt.text.lower()
    return None


def convert_duration(values: list[int | float], from_unit: str, to_unit: str) -> list[int | float] | None:
    """Re-express Classic per-rank durations in Forever's unit (60 sec -> 1 min). None when a value
    does not come out whole in the target unit (45 sec is not "0.75 min" on a tooltip)."""
    if from_unit == to_unit:
        return list(values)
    factor = DURATION_SECONDS[from_unit] / DURATION_SECONDS[to_unit]
    out: list[int | float] = []
    for v in values:
        c = float(v) * factor
        if abs(c - round(c)) > 1e-9:
            return None
        out.append(int(round(c)))
    return out


def scale_slot(f1: int | float, classic: list[int | float], max_rank: int,
               copy_allowed: bool = True) -> SlotPlan | None:
    """Scale Forever's rank-1 value across its ranks. None -> manual.

    A Forever talent scales proportionally from its own rank 1: rank k is ``f1 * k``.
    The one exception is a verbatim copy, and only when the caller says the Classic match is
    strong enough for it (``copy_allowed``: an exact same-name talent) *and* Classic has the
    same rank count *and* Classic's rank 1 is Forever's. Then Classic's own numbers are used;
    they are Blizzard's and beat any formula, including where the client's own rounding makes
    them miss the exact ray (8/16/25, 16/33/50).

    Classic's additive step and offset are **never** re-based onto a different rank 1. A
    Classic offset belongs to Classic's base; applied to Forever's it produces numbers nobody
    designed (Twilight Focus: 23 against Classic 40/70/100 gave 23/40.25/57.5). A
    non-proportional Classic slot is therefore scaled proportionally like everything else,
    with the unapplied pattern named in the note and one confidence notch off.
    """
    kind = progression(classic)
    c1 = classic[0]
    n = len(classic)
    c_str = "/".join(str(nice(c)) for c in classic)
    if kind == "constant":
        return SlotPlan([nice(f1)] * max_rank, "constant")
    if copy_allowed and n == max_rank and c1 == f1:
        # Forever starts where Classic starts, under the same name: Classic's own numbers win
        note = None if kind == "proportional" else "non-proportional Classic progression copied verbatim"
        return SlotPlan([nice(v) for v in classic], "copied", note)
    if float(f1) <= 0:
        return None
    vals = [nice(float(f1) * k) for k in range(1, max_rank + 1)]
    extra = f", Classic has {n} ranks" if n != max_rank else ""
    if kind == "proportional":
        note = (f"Classic {c_str} is proportional{extra}; Forever rank 1 is {nice(f1)}: "
                f"scaled proportionally ({nice(f1)} x rank)")
        return SlotPlan(vals, "proportional", note, rounding_hint(vals))
    # affine or irregular: name the Classic pattern that was NOT applied, then scale anyway
    if kind == "affine":
        step = float(classic[1]) - float(classic[0])
        offset = float(c1) - step
        shape = f"{nice(step)} x rank {nice(offset):+}"
    else:
        shape = "non-linear"
    note = (f"Classic {c_str} is {shape}{extra}, which does not start at Forever's rank 1 "
            f"({nice(f1)}); Classic's pattern was NOT applied, ranks scaled proportionally "
            f"({nice(f1)} x rank)")
    return SlotPlan(vals, "proportional", note, rounding_hint(vals), low=True)


# ----------------------------------------------------------------------------
# Result
# ----------------------------------------------------------------------------

@dataclass
class RankResult:
    description: str
    ranks: list[list[Any]]
    ranks_source: str                 # observed | classic-prior | extrapolated | manual
    ranks_prior: dict | None = None
    ranks_note: str | None = None
    needs_manual: bool = False
    confidence: str = "high"          # high | medium | low
    match: Match | None = None
    rule: str | None = None           # copied | constant | proportional | none
    review: bool = False              # belongs in the review queue
    # Which ranks the footage actually showed. [1] for every rank-0 tooltip; a crop taken with
    # points already spent reports the rank it really shows (see `observed_rank` in `anticipate`).
    ranks_observed: list[int] = field(default_factory=lambda: [1])

    def to_fields(self) -> dict:
        """Canonical talent fields (DATA-SCHEMA.md section 4.4) plus pipeline extras."""
        out: dict[str, Any] = {
            "description": self.description,
            "ranks": self.ranks,
            "ranksObserved": list(self.ranks_observed),
            "ranksSource": self.ranks_source,
        }
        if self.ranks_prior is not None:
            out["ranksPrior"] = self.ranks_prior
        if self.ranks_note:
            out["ranksNote"] = self.ranks_note
        out["needsManual"] = self.needs_manual
        out["confidence"] = self.confidence
        out["review"] = self.review
        out["rule"] = self.rule
        if self.match is not None:
            out["match"] = {
                "classicTalentId": self.match.record.get("classicTalentId"),
                "name": self.match.record.get("name"),
                "class": self.match.record.get("class"),
                "tree": self.match.record.get("tree"),
                "maxRank": self.match.record.get("maxRank"),
                "match": self.match.match,
                "similarity": self.match.similarity,
            }
        return out

    def rendered(self) -> list[str]:
        return [r if isinstance(r, str) else render(self.description, r) for r in self.ranks]


def _prior_block(m: Match) -> dict:
    return {
        "classicTalentId": m.record.get("classicTalentId"),
        "classicSpellIds": list(m.record.get("spellIds") or []),
        "match": m.match,
        "similarity": m.similarity,
    }


def _all_number_slots(text: str, tokens: list[Token], nums: list[NumberInfo]) -> tuple[list[Slot], list[Any]]:
    slots: list[Slot] = []
    values: list[Any] = []
    for n in nums:
        if n.is_rank_ref:
            continue
        slots.append(Slot(len(slots), "num", n.token))
        values.append(n.value)
    return slots, values


def _finish(text: str, tokens: list[Token], num_slots: list[tuple[NumberInfo, list[Any]]], max_rank: int,
            heads: dict[int, Token | None]) -> tuple[str, list[list[Any]]]:
    """Given per-numeric-slot value lists, add plural slots where a value list crosses 1, build template and ranks."""
    slots: list[Slot] = []
    columns: list[list[Any]] = []
    for j, (info, vals) in enumerate(num_slots):
        slots.append(Slot(len(slots), "num", info.token, None))
        columns.append(vals)
        head = heads.get(j)
        if head is not None and any(v == 1 for v in vals) and any(v != 1 for v in vals):
            slots.append(Slot(len(slots), "plural", head, len(slots) - 1))
            columns.append([plural_value(v) for v in vals])
    # slots must appear in text order so that {n} counts up by first appearance
    order = sorted(range(len(slots)), key=lambda i: slots[i].token.pos)
    slots = [Slot(k, slots[i].kind, slots[i].token, slots[i].number_slot) for k, i in enumerate(order)]
    columns = [columns[i] for i in order]
    template = build_template(text, tokens, slots)
    ranks = [[col[k] for col in columns] for k in range(max_rank)]
    return template, ranks


# ----------------------------------------------------------------------------
# The decision table
# ----------------------------------------------------------------------------

def anticipate(name: str, description_rank1: str, max_rank: int, cls: str, prior: Prior | None,
               tree: str | None = None, observed_rank: int = 1) -> RankResult:
    text = clean_text(description_rank1 or "")
    tokens = tokenize(text)
    nums = number_infos(text, tokens)
    slot_nums = [n for n in nums if not n.is_rank_ref]
    max_rank = int(max_rank or 1)
    observed_rank = int(observed_rank or 1)

    # The tooltip was captured with points already spent, so its numbers are rank `observed_rank`,
    # not rank 1. Scaling them as if they were rank 1 is how mage/shatter's rank-3 "50%" became
    # 50/100/150, i.e. "150% critical strike chance". Never extrapolate from such a reading.
    if observed_rank > 1:
        res = _manual(text, tokens, nums, max_rank,
                      f"tooltip shows rank {observed_rank}/{max_rank}, so its numbers are not rank 1", None)
        res.ranks_observed = [observed_rank] if observed_rank <= max_rank else [1]
        return res

    # Row 1: nothing to anticipate
    if max_rank <= 1:
        slots, values = _all_number_slots(text, tokens, nums)
        return RankResult(build_template(text, tokens, slots), [values], "observed", confidence="high", rule="none")

    m = match_classic(name, text, max_rank, cls, prior) if prior is not None else None
    if m is not None:
        res = _from_classic(m, text, tokens, slot_nums, max_rank)
        if res is not None:
            return res

    # No usable Classic pattern: extrapolate or manual
    durations = [n for n in slot_nums if n.is_duration]
    reason = None
    if m is not None:
        reason = f"Classic match {m.label} has no alignable slots"
    if durations:
        reason = reason or f"duration slot ({durations[0].token.text} {tokens[durations[0].token.pos + 1].text}) is never extrapolated"
        return _manual(text, tokens, nums, max_rank, reason, m)
    if 1 <= len(slot_nums) <= 2:
        cols = [(n, [nice(n.value * k) for k in range(1, max_rank + 1)]) for n in slot_nums]
        heads = {j: n.head_word for j, n in enumerate(slot_nums)}
        template, ranks = _finish(text, tokens, cols, max_rank, heads)
        base = "No Classic counterpart" if m is None else reason
        note = f"{base}; proportional x2..x{max_rank} of rank 1 assumed."
        multi = len(cols) > 1
        roundings = [(f"{{{j}}} " if multi else "") + h
                     for j, (_, vals) in enumerate(cols) if (h := rounding_hint(vals))]
        if roundings:
            note += f" Rounding: {'; '.join(roundings)} (values above are the raw scaled numbers)."
        return RankResult(template, ranks, "extrapolated", None, note, False, "low", m, "proportional", review=True)
    reason = reason or (f"{len(slot_nums)} numeric slots" if slot_nums else "no numbers in rank-1 text")
    return _manual(text, tokens, nums, max_rank, reason, m)


def _manual(text: str, tokens: list[Token], nums: list[NumberInfo], max_rank: int, reason: str,
            m: Match | None) -> RankResult:
    slots, values = _all_number_slots(text, tokens, nums)
    template = build_template(text, tokens, slots)
    ranks = [list(values) for _ in range(max_rank)]
    span = "rank 2 is a copy" if max_rank == 2 else f"ranks 2..{max_rank} are copies"
    note = f"needs manual ranks: {reason}; {span} of rank 1."
    return RankResult(template, ranks, "manual", None, note, True, "low", m, "none", review=True)


def _from_classic(m: Match, text: str, tokens: list[Token], slot_nums: list[NumberInfo],
                  max_rank: int) -> RankResult | None:
    """Align Forever's numbers with the Classic talent's slots and apply its scaling."""
    rec = m.record
    rank_texts: list[str] = rec.get("ranks") or []
    classic_slots: list[list[Any]] | None = rec.get("slots")
    if not rank_texts or rec.get("maxRank", 0) < 2:
        return None  # 1-rank Classic talent: no pattern to apply
    c_text = rank_texts[0]
    c_tokens = tokenize(c_text)
    var = varying_positions(rank_texts) if classic_slots is not None else None
    if var is None:
        # Sentence shape changes between Classic ranks (Endurance: 45 sec -> 1.5 min). The per-rank
        # strings can only be reused verbatim, and only when Forever's rank 1 is Classic's rank 1.
        if len(rank_texts) == max_rank and clean_text(c_text) == text:
            note = f"Classic {m.label}: sentence shape changes per rank, per-rank texts copied as strings."
            return RankResult(text, list(rank_texts), "classic-prior", _prior_block(m), note, False, "medium", m,
                              "copied", review=True)
        return None
    var_set = set(var)
    c_num_positions = [t.pos for t in c_tokens if t.is_number]
    c_num_var = [p for p in c_num_positions if p in var_set]
    # per Classic varying numeric position -> column of per-rank values
    c_columns: dict[int, list[Any]] = {}
    c_plural_stem: dict[int, str] = {}  # numeric var position -> stem of the plural word governed by it
    var_index = {p: i for i, p in enumerate(var)}
    for p in c_num_var:
        c_columns[p] = [row[var_index[p]] for row in classic_slots]
    for p in var:
        if p not in c_columns:  # plural slot: attach to the nearest preceding numeric var slot
            prev = [q for q in c_num_var if q < p]
            if prev:
                c_plural_stem[prev[-1]] = _stem(c_tokens[p].text)

    f_nums = slot_nums
    aligned: list[tuple[NumberInfo, int | None]] = []   # (forever number, classic numeric position or None=literal)
    if skeleton(text) == skeleton(c_text):
        # identical wording: token-for-token
        f_all = [n for n in number_infos(text, tokens)]
        for n in f_all:
            aligned.append((n, n.token.pos if n.token.pos in c_columns else None))
    elif len(f_nums) == len(c_num_positions):
        for n, p in zip(f_nums, c_num_positions):
            aligned.append((n, p if p in c_columns else None))
    elif len(f_nums) == len(c_num_var):
        for n, p in zip(f_nums, c_num_var):
            aligned.append((n, p))
    else:
        return None

    plans: list[tuple[NumberInfo, SlotPlan]] = []
    heads: dict[int, Token | None] = {}
    literal_notes: list[str] = []
    for n, p in aligned:
        if p is None:
            continue  # a number Classic keeps constant: stays literal in the template
        column = c_columns[p]
        f_unit = duration_unit(tokens, n.token.pos, text) if n.is_duration else None
        c_unit = duration_unit(c_tokens, p, c_text)
        if f_unit != c_unit:
            # "1 min" against Classic "60 sec": normalise Classic into Forever's unit before scaling,
            # or hand over when the units are incompatible / do not convert whole
            converted = convert_duration(column, c_unit, f_unit) if f_unit and c_unit else None
            if converted is None:
                c_vals = "/".join(str(nice(v)) for v in column)
                reason = (f"Classic {m.label} has {c_vals} {c_unit or 'without unit'} where Forever rank 1 has "
                          f"{nice(n.value)} {f_unit or 'without unit'}; units differ")
                return _manual(text, tokens, number_infos(text, tokens), max_rank, reason, m)
            literal_notes.append(f"Classic {'/'.join(str(nice(v)) for v in column)} {c_unit} taken as "
                                 f"{'/'.join(str(v) for v in converted)} {f_unit}")
            column = converted
        # only an exact same-name Classic talent is evidence that Forever kept Classic's numbers;
        # a fuzzy or description match is a wording resemblance, so it scales like everything else
        plan = scale_slot(n.value, column, max_rank, copy_allowed=(m.match == "exact-name"))
        if plan is None:
            # the only unscalable base: a rank-1 value of 0 (or below), which has no ray through it
            c_vals = "/".join(str(nice(v)) for v in column)
            reason = (f"Forever rank 1 is {nice(n.value)}, which cannot be scaled proportionally "
                      f"(Classic {m.label} has {c_vals})")
            res = _manual(text, tokens, number_infos(text, tokens), max_rank, reason, m)
            return res
        # plural head: prefer the word Classic pluralises, else the heuristic head
        head = n.head_word
        stem = c_plural_stem.get(p)
        if stem:
            for t in tokens[n.token.pos + 1:n.token.pos + 4]:
                if not t.is_number and _stem(t.text) == stem:
                    head = t
                    break
        heads[len(plans)] = head
        plans.append((n, plan))

    if not plans:
        return None
    template, ranks = _finish(text, tokens, [(n, pl.values) for n, pl in plans], max_rank, heads)
    rules = {pl.rule for _, pl in plans}
    notes = [pl.note for _, pl in plans if pl.note] + literal_notes
    multi = sum(1 for _, pl in plans if pl.rounding) > 1 or len(plans) > 1
    roundings = [(f"{{{j}}} " if multi else "") + pl.rounding for j, (_, pl) in enumerate(plans) if pl.rounding]
    prefix = f"Classic {m.label}" + (" (cross-class)" if m.cross_class else "")
    if m.match == "description":
        prefix += f", matched on description ({m.similarity:.2f})"
    elif m.match == "fuzzy-name":
        prefix += f", matched on name ({m.similarity:.2f})"
    # only an exact same-class name with a verbatim copy skips review: a fuzzy name means the
    # name itself needs a reviewer, a cross-class or description match is structural guesswork
    high = (m.match == "exact-name" and not m.cross_class and rules <= {"copied", "constant"}
            and "non-proportional Classic progression copied verbatim" not in notes and not literal_notes)
    if high:
        note = f"{prefix}: ranks copied."
        return RankResult(template, ranks, "classic-prior", _prior_block(m), note, False, "high", m, "copied", review=False)
    detail = "; ".join(notes) if notes else "ranks copied"
    note = f"{prefix}: {detail}."
    if roundings:
        note += f" Rounding: {'; '.join(roundings)} (values above are the raw scaled numbers)."
    rule = "copied" if rules <= {"copied", "constant"} else "proportional"
    # a Classic pattern we deliberately did not apply is a standing doubt: one notch below proportional
    confidence = "low" if any(pl.low for _, pl in plans) else "medium"
    return RankResult(template, ranks, "classic-prior", _prior_block(m), note, False, confidence, m, rule, review=True)


def anticipate_record(rec: dict, prior: Prior | None) -> RankResult:
    """Convenience over a candidate record (pipeline brief section 1 shape)."""
    rank = rec.get("rank") or {}
    max_rank = rank.get("max") if isinstance(rank, dict) else rec.get("rank_max")
    observed = (rank.get("current") if isinstance(rank, dict) else None) or 0
    return anticipate(rec.get("name") or "", rec.get("description_rank1") or rec.get("description") or "",
                      max_rank or 1, rec.get("class") or "", prior, rec.get("tree"),
                      observed_rank=max(1, int(observed)))

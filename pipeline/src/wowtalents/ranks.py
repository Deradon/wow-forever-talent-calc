"""Rank anticipation (stage 6): derive ranks 2..N of a Forever talent from its
rank-1 tooltip text and the Classic Era prior.

Implements docs/briefs/data-prior-and-review.md section (b). Pure functions
over ``data/prior/classic-era/talents.json``; no I/O except ``Prior.load``.

Entry point::

    prior = Prior.load()
    res = anticipate("Toughness", "Increases your armor value from items by 2%.", 5, "paladin", prior)
    res.to_fields()   # description, ranks, ranksObserved, ranksSource, ranksPrior/ranksNote, needsManual

Decision table (``ranksSource`` / confidence):

    maxRank == 1                                            observed       high
    exact same-class name, slots constant/arithmetic, c1==f1 classic-prior  high   (copied)
    fuzzy / cross-class / description match, copied         classic-prior  medium (review queue)
    ("exact" is full-string key equality; the fuzzy tier uses token_sort_ratio, so a token subset
    such as "Divine Precision" vs "Precision" never scores 1.0 and never skips review)
    Classic match, arithmetic slot, base or ratio differs   classic-prior  medium (scaled, review queue)
    Classic match, rank count differs, arithmetic slot      classic-prior  medium (step extended, review queue)
    Classic shape-changing text, rank 1 identical           classic-prior  medium (per-rank strings copied)
    Classic match, non-linear slot, c1 == f1                classic-prior  medium (copied, review queue)
    Classic match, non-linear slot, c1 != f1                manual         -      (rank 1 copied, review queue)
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
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

PRIOR_PATH = Path(__file__).resolve().parents[3] / "data" / "prior" / "classic-era" / "talents.json"

# Same tokeniser as data/prior/classic-era/build.py so slot positions line up.
TOKEN_RE = re.compile(r"\d+(?:\.\d+)?|(?<!\d)\.\d+|[A-Za-z]+")
NUM_RE = re.compile(r"^(?:\d+(?:\.\d+)?|\.\d+)$")

DURATION_UNITS = {"sec", "secs", "second", "seconds", "min", "mins", "minute", "minutes", "hr", "hrs", "hour", "hours"}
DURATION_SECONDS = {"sec": 1, "secs": 1, "second": 1, "seconds": 1, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
                    "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600}
PLURAL_STOPWORDS = {"in", "of", "to", "for", "and", "or", "per", "from", "on", "by", "with", "while", "that", "when",
                    "the", "a", "an", "at", "is", "are", "if", "over", "up", "down", "than", "more", "less"}

NAME_THRESHOLD = 90.0        # rapidfuzz token_sort_ratio on names (brief (b), validator rule 15)
DESC_THRESHOLD = 85.0        # token_ratio on number-masked descriptions (brief (b) step 3)
MAXRANK_PENALTY = 10.0       # brief (b) step 2
CLEAN_RATIO_STEP = 0.25      # f1/c1 is "clean" when a multiple of this, and <= 4


# ----------------------------------------------------------------------------
# Text helpers (mirroring data/prior/classic-era/build.py)
# ----------------------------------------------------------------------------

def slug(name: str) -> str:
    """DATA-SCHEMA.md section 3 slug rule."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def clean_text(s: str) -> str:
    """Section 2 normalisation: nbsp/curly quotes to ASCII, collapse spaces, trim."""
    s = s.replace(" ", " ").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[ \t\r\n]+", " ", s)
    return s.strip()


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

def progression(values: list[int | float]) -> str:
    """constant | arithmetic | other over Classic per-rank values of one slot."""
    if len(values) < 2:
        return "constant"
    d = [round(float(b) - float(a), 6) for a, b in zip(values, values[1:])]
    if all(x == 0 for x in d):
        return "constant"
    return "arithmetic" if len(set(d)) == 1 else "other"


def _clean_ratio(f1: float, c1: float, classic: list[int | float]) -> float | None:
    if c1 == 0 or f1 == 0:
        return None
    r = f1 / c1
    if r <= 0 or r > 4 or round(r / CLEAN_RATIO_STEP, 6) != int(round(r / CLEAN_RATIO_STEP)):
        return None
    ints = all(isinstance(c, int) for c in classic)
    for c in classic:
        v = c * r
        if ints and abs(v - round(v)) > 1e-9:
            return None
    return r


@dataclass
class SlotPlan:
    values: list[int | float]
    rule: str            # copied | ratio | step | constant | extended
    note: str | None = None


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


def scale_slot(f1: int | float, classic: list[int | float], max_rank: int) -> SlotPlan | None:
    """Apply Classic's per-rank pattern to Forever's rank-1 value. None -> manual."""
    kind = progression(classic)
    c1 = classic[0]
    n = len(classic)
    if kind == "constant":
        return SlotPlan([nice(f1)] * max_rank, "constant")
    if kind == "arithmetic":
        d = float(classic[1]) - float(classic[0])
        if n == max_rank and c1 == f1:
            return SlotPlan([nice(v) for v in classic], "copied")
        if n != max_rank:
            vals = [nice(float(f1) + k * d) for k in range(max_rank)]
            return SlotPlan(vals, "extended", f"Classic has {n} ranks, step {nice(d):+} applied over {max_rank} ranks from {nice(f1)}")
        r = _clean_ratio(float(f1), float(c1), classic)
        if r is not None:
            return SlotPlan([nice(c * r) for c in classic], "ratio",
                            f"Classic {'/'.join(str(nice(c)) for c in classic)} scaled by {nice(r)}")
        vals = [nice(float(f1) + k * d) for k in range(max_rank)]
        return SlotPlan(vals, "step", f"Classic {'/'.join(str(nice(c)) for c in classic)}, Forever rank 1 is {nice(f1)}: applied {nice(d):+}/rank")
    # non-linear Classic progression: only a verbatim copy is defensible
    if n == max_rank and c1 == f1:
        return SlotPlan([nice(v) for v in classic], "copied", "non-linear Classic progression copied")
    return None


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
    rule: str | None = None           # copied | ratio | step | extended | linear | none
    review: bool = False              # belongs in the review queue

    def to_fields(self) -> dict:
        """Canonical talent fields (DATA-SCHEMA.md section 4.4) plus pipeline extras."""
        out: dict[str, Any] = {
            "description": self.description,
            "ranks": self.ranks,
            "ranksObserved": [1],
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
               tree: str | None = None) -> RankResult:
    text = clean_text(description_rank1 or "")
    tokens = tokenize(text)
    nums = number_infos(text, tokens)
    slot_nums = [n for n in nums if not n.is_rank_ref]
    max_rank = int(max_rank or 1)

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
        note = f"{base}; linear x2..x{max_rank} of rank 1 assumed."
        return RankResult(template, ranks, "extrapolated", None, note, False, "low", m, "linear", review=True)
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
        plan = scale_slot(n.value, column, max_rank)
        if plan is None:
            c_vals = "/".join(str(nice(v)) for v in column)
            reason = f"Classic {m.label} scales {c_vals} (non-linear) but Forever rank 1 is {nice(n.value)}"
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
    prefix = f"Classic {m.label}" + (" (cross-class)" if m.cross_class else "")
    if m.match == "description":
        prefix += f", matched on description ({m.similarity:.2f})"
    elif m.match == "fuzzy-name":
        prefix += f", matched on name ({m.similarity:.2f})"
    # only an exact same-class name with a verbatim copy skips review: a fuzzy name means the
    # name itself needs a reviewer, a cross-class or description match is structural guesswork
    high = (m.match == "exact-name" and not m.cross_class and rules <= {"copied", "constant"}
            and "non-linear Classic progression copied" not in notes and not literal_notes)
    if high:
        note = f"{prefix}: ranks copied."
        return RankResult(template, ranks, "classic-prior", _prior_block(m), note, False, "high", m, "copied", review=False)
    detail = "; ".join(notes) if notes else "ranks copied"
    note = f"{prefix}: {detail}."
    rule = "copied" if rules <= {"copied", "constant"} else ("ratio" if "ratio" in rules else ("step" if "step" in rules else "extended"))
    return RankResult(template, ranks, "classic-prior", _prior_block(m), note, False, "medium", m, rule, review=True)


def anticipate_record(rec: dict, prior: Prior | None) -> RankResult:
    """Convenience over a candidate record (pipeline brief section 1 shape)."""
    rank = rec.get("rank") or {}
    max_rank = rank.get("max") if isinstance(rank, dict) else rec.get("rank_max")
    return anticipate(rec.get("name") or "", rec.get("description_rank1") or rec.get("description") or "",
                      max_rank or 1, rec.get("class") or "", prior, rec.get("tree"))

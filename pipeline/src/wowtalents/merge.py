"""Shape-aware merge of the tooltip readers (data audit 2026-09-13, section 8.1).

The primary reader (Qwen 3x) wrote the export in 467 of 469 records, so the export
inherited its biases wholesale. The audit adjudicated all 72 stored disagreements
against the crops and found the split is *mechanical*, not random:

* **case** - a mid-sentence ``Increases``/``Instant``/``Immune`` that is lowercase in
  the footage (27 records). Codex was right ~100 % of the time.
* **punct** - a comma inside an enumeration read as a period (14 records). At 1080p
  ``,`` and ``.`` are near-identical 2 px blobs; codex was right ~100 % of the time.
* **percent** - a dropped ``%``, turning a percentage into a flat number that the rank
  scaler then multiplies (7 records). Codex was right in all seven.
* **word** - real wording differences (18). Here Qwen was right ~70 % of the time, so
  the per-shape winner is the *majority of all readings*, not codex.

So: the shape authority (codex) wins every case / punct / percent hunk; a word hunk is
decided by counting how many readings carry each variant, with the primary reader
winning a tie. Everything in this module is pure - no I/O, no network.

``repair_spell_names`` is the fourth shape (8 records: ``Immolates`` for ``Immolate``,
``Scorpion Sting`` for ``Scorpid Sting``, ``Tranquillity`` for ``Tranquility``): capitalised
phrases are snapped to the vocabulary of *this record's own* matched Classic talent - never a
global dictionary, which at two edits' distance turns ``Mangle`` into ``Mage``. A Forever spell
the Classic counterpart never mentions has no neighbour and survives untouched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable, Sequence

from rapidfuzz.distance import Levenshtein

from .text import clean_text

__all__ = ["Hunk", "MergeResult", "merge_readings", "classify_pair", "normalise_capital_i",
           "spell_vocabulary", "classic_vocabulary", "repair_spell_names", "CAPITAL_I_ALLOWED"]

CASE, PUNCT, PERCENT, WORD = "case", "punct", "percent", "word"

# Proper nouns that legitimately start with a capital I mid-sentence (audit 3.1: a scan of
# all 469 descriptions found 40 such occurrences against 27 wrong ones).
CAPITAL_I_ALLOWED = frozenset({
    "Intellect", "Imp", "Incubus", "Immolate", "Immolation", "Immolates", "Incinerate",
    "Intercept", "Insect", "Ice", "Inner", "Invisibility", "Interrupt", "Ignite", "Impact",
    "Improved", "Innervate", "Intimidation", "Initiative", "Illumination", "Iron",
})

_CAPITAL_I_RE = re.compile(r"(?<![.:;!?]\s)(?<!^)\b(I[a-z]{2,})\b")
_SENTENCE_START_RE = re.compile(r"(?:^|[.:;!?]\s+|\"\s*)$")
_WORD_RE = re.compile(r"\S+")
_CAP_RUN_RE = re.compile(r"\b[A-Z][A-Za-z']*(?:\s+(?:of|the|and)\s+[A-Z][A-Za-z']*|\s+[A-Z][A-Za-z']*)*")
_TRAILING = ".,;:!?)\"'"


@dataclass(frozen=True)
class Hunk:
    """One aligned difference between the primary reading and the shape authority."""
    kind: str               # case | punct | percent | word
    primary: str
    other: str
    chosen: str
    votes: tuple[int, int] = (0, 0)     # (readings carrying primary, readings carrying other)

    @property
    def changed(self) -> bool:
        return self.chosen != self.primary


@dataclass
class MergeResult:
    text: str
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return any(h.changed for h in self.hunks)

    def counts(self) -> dict[str, int]:
        """Applied changes per shape, for the before/after report."""
        out: dict[str, int] = {}
        for h in self.hunks:
            if h.changed:
                out[h.kind] = out.get(h.kind, 0) + 1
        return out

    @property
    def disputed_words(self) -> list[Hunk]:
        """Word hunks the vote could not settle: they stay in the review queue."""
        return [h for h in self.hunks if h.kind == WORD and h.votes[0] == h.votes[1]]


def _strip_edges(w: str) -> str:
    return w.strip(_TRAILING)


def classify_pair(a: str, b: str) -> str:
    """Shape of one aligned word pair (``a`` from the primary reader, ``b`` from the authority)."""
    if a == b:
        return ""
    if a.lower() == b.lower():
        return CASE
    # a dropped percent sign: the two words are equal once every '%' is removed
    if a.replace("%", "") == b.replace("%", "") and b.count("%") != a.count("%"):
        return PERCENT
    # comma read as period (or the other way): only ',' and '.' differ
    if a.translate(str.maketrans(",", ".")) == b.translate(str.maketrans(",", ".")):
        return PUNCT
    # both at once, e.g. "Bolt." -> "bolt," or "30." -> "30%,"
    norm_a = a.lower().replace("%", "").translate(str.maketrans(",", "."))
    norm_b = b.lower().replace("%", "").translate(str.maketrans(",", "."))
    if norm_a == norm_b:
        return PERCENT if a.count("%") != b.count("%") else (CASE if a.lower() != b.lower() else PUNCT)
    return WORD


def _vote(run_a: str, run_b: str, texts: Sequence[str]) -> tuple[int, int]:
    """How many readings carry each variant of a word hunk."""
    return (sum(1 for t in texts if run_a and run_a in t),
            sum(1 for t in texts if run_b and run_b in t))


def merge_readings(primary: str, authority: str, others: Iterable[str] = ()) -> MergeResult:
    """Merge two readings of one description; ``others`` are extra readings that only vote.

    ``authority`` (the second reader) wins every case, punctuation and percent hunk.
    A word hunk goes to whichever variant more readings carry, primary winning a tie -
    that is the audit's ~70 % for Qwen on wording, with the second Qwen pass breaking ties.
    """
    primary, authority = clean_text(primary or ""), clean_text(authority or "")
    if not authority or not primary:
        return MergeResult(primary or authority, [])
    all_texts = [primary, authority, *[clean_text(t or "") for t in others if t]]
    pa, pb = _WORD_RE.findall(primary), _WORD_RE.findall(authority)
    out: list[str] = []
    hunks: list[Hunk] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=pa, b=pb, autojunk=False).get_opcodes():
        if tag == "equal":
            out.extend(pa[i1:i2])
            continue
        run_a, run_b = " ".join(pa[i1:i2]), " ".join(pb[j1:j2])
        if tag == "replace" and (i2 - i1) == (j2 - j1):
            for a, b in zip(pa[i1:i2], pb[j1:j2]):
                kind = classify_pair(a, b)
                if not kind:
                    out.append(a)
                    continue
                if kind == WORD:
                    va, vb = _vote(a, b, all_texts)
                    chosen = b if vb > va else a
                    hunks.append(Hunk(WORD, a, b, chosen, (va, vb)))
                else:
                    chosen = b
                    hunks.append(Hunk(kind, a, b, chosen))
                out.append(chosen)
            continue
        # An inserted, deleted or re-shaped run: wording, so it is voted on as a whole. The vote
        # carries one word of context on each side, because a bare deletion has nothing to look
        # for otherwise (dropping "it" from "Plague it is active" leaves an empty variant).
        left = pa[i1 - 1] if i1 > 0 else ""
        right = pa[i2] if i2 < len(pa) else ""
        va, vb = _vote(" ".join(w for w in (left, run_a, right) if w),
                       " ".join(w for w in (left, run_b, right) if w), all_texts)
        chosen = run_b if vb > va else run_a
        hunks.append(Hunk(WORD, run_a, run_b, chosen, (va, vb)))
        if chosen:
            out.extend(chosen.split(" "))
    return MergeResult(" ".join(w for w in out if w), hunks)


def normalise_capital_i(text: str, allowed: Iterable[str] = CAPITAL_I_ALLOWED) -> tuple[str, list[str]]:
    """Lowercase a mid-sentence ``I<word>`` unless it is a game term (audit 8.1.2).

    Belt and braces behind the merge: it also catches records where *both* readers agreed
    on a wrong capital. Words after ``.``, ``:``, ``;``, ``!``, ``?`` or at a line start are
    sentence openers and are never touched.
    """
    allowed = set(allowed)
    fixed: list[str] = []

    def repl(m: re.Match) -> str:
        word = m.group(1)
        if word in allowed:
            return word
        before = text[:m.start()]
        if _SENTENCE_START_RE.search(before) or not before.strip():
            return word
        fixed.append(word)
        return word[0].lower() + word[1:]

    return _CAPITAL_I_RE.sub(repl, text), fixed


def spell_vocabulary(texts: Iterable[str]) -> set[str]:
    """Capitalised game terms appearing in ``texts`` - the dictionary ``repair_spell_names`` snaps to.

    Feed it *one Classic talent's* own text (name, description, per-rank strings), not the whole
    prior. A global vocabulary is actively dangerous: at two edits' distance ``Mangle`` reaches
    ``Mage`` and ``Bleeding`` reaches ``Blessing``, so a wide dictionary invents errors faster
    than it fixes them. The talent's own counterpart text mentions exactly the spells its
    description can legitimately name.
    """
    vocab: set[str] = set()
    for text in texts:
        text = clean_text(text or "")
        for m in _CAP_RUN_RE.finditer(text):
            phrase = _strip_edges(m.group()).strip()
            if phrase and len(phrase) > 2 and not (m.start() == 0 or _SENTENCE_START_RE.search(text[:m.start()])):
                vocab.add(phrase)
    return vocab


def classic_vocabulary(record: dict) -> set[str]:
    """Spell names a Classic prior record mentions, plus its own name."""
    texts = [record.get("name") or "", record.get("description") or "", *(record.get("ranks") or [])]
    vocab = spell_vocabulary(texts)
    name = clean_text(record.get("name") or "")
    if len(name) > 2:
        vocab.add(name)
    return vocab


def repair_spell_names(text: str, vocab: set[str], *, max_edits: int = 2,
                       min_length: int = 6) -> tuple[str, list[tuple[str, str]]]:
    """Snap a capitalised phrase to a near-identical prior term (``Immolates`` -> ``Immolate``).

    Conservative by construction, because Forever invents spells the Classic prior has never
    heard of and mangling one of those would be worse than the reader error this fixes:

    * a phrase already in the vocabulary is never touched;
    * the candidate must be within ``max_edits`` character edits (Levenshtein), share the
      first letter, and the phrase must be at least ``min_length`` characters;
    * the nearest candidate must be unique at that distance - an ambiguous snap is refused.

    A genuinely new Forever name has no neighbour that close and survives untouched.
    """
    if not vocab:
        return text, []
    fixed: list[tuple[str, str]] = []

    def repl(m: re.Match) -> str:
        raw = m.group()
        phrase = _strip_edges(raw).strip()
        tail = raw[len(phrase):]
        if (not phrase or phrase in vocab or len(phrase) < min_length or m.start() == 0
                or _SENTENCE_START_RE.search(text[:m.start()])):
            return raw
        scored = []
        for cand in vocab:
            if cand[0] != phrase[0] or abs(len(cand) - len(phrase)) > max_edits:
                continue
            d = Levenshtein.distance(cand, phrase, score_cutoff=max_edits)
            if 0 < d <= max_edits:
                scored.append((d, cand))
        if not scored:
            return raw
        best_d = min(d for d, _ in scored)
        winners = sorted(c for d, c in scored if d == best_d)
        if len(winners) != 1:
            return raw       # ambiguous: two prior terms are equally close, so repair nothing
        fixed.append((phrase, winners[0]))
        return winners[0] + tail

    return _CAP_RUN_RE.sub(repl, text), fixed

"""Stage 5b: adjudicate the stored tooltip readings shape by shape (data audit 2026-09-13, 8.1).

``05_read.py`` stores two Qwen passes and ``second_opinion.py`` adds a codex reading, but the
export simply took the primary Qwen text, biases and all: 27 spurious capital ``I``s, 14 commas
read as periods, 7 dropped ``%`` and 8 mangled spell names, all of them inside the review queue.
This rewrites ``description_rank1`` and ``name`` from ``wowtalents.merge``: the second reader
wins on case, punctuation and ``%``; wording goes to whichever reading the others back; then a
capital-``I`` normaliser and a spell-name repair against the Classic prior run over the result.

A record whose remaining disagreements were all settled leaves the review queue
(``source.confidence`` back to 1.0); one with a word the readers still split on stays at 0.7
with a note naming it. ``ranks_anticipated`` is dropped from every changed record so stage 6/8
re-derives the template and the ranks from the corrected text.

    uv run scripts/merge_readers.py all --dry-run       # report, write nothing
    uv run scripts/merge_readers.py all                 # rewrite every candidates file
    uv run scripts/merge_readers.py mage --reread       # re-read the queue crops at 4x first

``--reread`` asks llama-server for one more pass (4x) over the crops still in the review queue
and stores it as a third voting reading before merging. It needs the server:
``LLAMA_PORT=8089 pipeline/scripts/llama-server.sh 4b``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import typer

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parent
EXTRACTED = REPO / "data" / "extracted"
PRIOR = REPO / "data" / "prior" / "classic-era" / "talents.json"

sys.path.insert(0, str(PIPELINE / "src"))
from wowtalents import merge as MG  # noqa: E402
from wowtalents import ranks as R  # noqa: E402
from wowtalents.fsio import write_candidates_atomic  # noqa: E402

CLASSES = ["druid", "hunter", "mage", "paladin", "priest", "rogue", "shaman", "warlock", "warrior"]
QUEUE_BELOW = 0.8               # validator rule NEEDS-REVIEW
SETTLED_CONFIDENCE = 1.0
DISPUTED_CONFIDENCE = 0.7
REREAD_LABEL_SUFFIX = "/4x"
NARROW_FACTOR = 0.90            # crop width below this fraction of the class median
WEAK_EDGE_RATIO = 0.40          # weakest tooltip border below this fraction of the strongest
PRE_MERGE_LABEL = "pre-merge"
# The only fields this merge adjudicates. A record flagged because the readers disagreed about
# anything else (extra_lines, the Rank line, the Requires lines) keeps its flag: clearing a
# doubt nobody resolved would be worse than leaving it in the queue.
ADJUDICATED_FIELDS = {"description", "name"}
# Fields that are not talent data at all: the green "Click to learn" footer and the cut-off flag.
# Stage 5 records a disagreement about them without lowering its own confidence, and they must
# not put a record into the review queue either.
IGNORED_FIELDS = {"footer", "cut_off"}
_NOTE_FIELDS_RE = re.compile(r"second reader \(codex\) differs in ([^;]+)", re.I)

app = typer.Typer(add_completion=False)


# --------------------------------------------------------------------------- pure helpers

def split_readings(rec: dict, *, authority: str = "codex") -> tuple[dict | None, dict | None, list[dict]]:
    """(primary, authority, others) from ``source.readings``.

    The primary is the reading the record was built from (``source.reader`` plus the first
    pass label); the authority is the second, non-Qwen reader.
    """
    readings = [r for r in ((rec.get("source") or {}).get("readings") or []) if isinstance(r, dict)
                and str(r.get("reader")) != PRE_MERGE_LABEL]   # a superseded text must never vote again
    auth = next((r for r in readings if authority in str(r.get("reader") or "").lower()), None)
    rest = [r for r in readings if r is not auth]
    return (rest[0] if rest else None), auth, rest[1:]


def class_vocabulary(prior_doc: dict, cls: str) -> set[str]:
    """Spell names the Classic prior attests **for this class**: talent names plus every
    capitalised phrase their tooltips mention.

    Class scope matters. A prior-wide dictionary reaches ``Mangle`` -> ``Mage`` and
    ``Bleeding`` -> ``Blessing`` at two edits; the same talent's counterpart alone is too
    narrow, because Forever rewrote the sentences (warlock ``Aftermath`` no longer mentions
    Immolate in Classic's words). One class's vocabulary is the level that works.
    """
    entry = (prior_doc.get("classes") or {}).get(cls) or {}
    talents = [rec for tree in (entry.get("trees") or []) for rec in (tree.get("talents") or [])]
    vocab = MG.spell_vocabulary([t for rec in talents
                                 for t in [rec.get("name") or "", rec.get("description") or "", *(rec.get("ranks") or [])]])
    vocab |= {n for rec in talents if len(n := R.clean_text(rec.get("name") or "")) > 2}
    return vocab


def merged_fields(rec: dict, vocab: set[str]) -> dict[str, Any] | None:
    """The record's merged ``description_rank1`` plus what changed, or None if nothing did.

    The spell-name repair runs **only on records already in the review queue**. That is where
    the audit found every text error, and a census over all 469 records showed the dictionary
    is right 6 times out of 6 inside the queue and wrong 8 times out of 8 outside it (it
    "fixes" real plurals: ``Poisons``, ``Daggers``, ``Soul Shards``). Talent *names* are never
    repaired at all - Forever renames talents on purpose, so the prior has no authority there.
    """
    primary, auth, others = split_readings(rec)
    base_desc = str(rec.get("description_rank1") or "")
    base_name = str(rec.get("name") or "")
    shapes: dict[str, int] = {}
    disputed: list[str] = []

    desc = base_desc
    if auth is not None and primary is not None:
        res = MG.merge_readings(base_desc, str(auth.get("description") or ""),
                                [str(o.get("description") or "") for o in others])
        desc = res.text or base_desc
        for k, v in res.counts().items():
            shapes[k] = shapes.get(k, 0) + v
        disputed = [f"{h.primary!r} vs {h.other!r}" for h in res.disputed_words]

    desc, lowered = MG.normalise_capital_i(desc)
    if lowered:
        shapes["case"] = shapes.get("case", 0) + len(lowered)
    if float((rec.get("source") or {}).get("confidence") or 1.0) < QUEUE_BELOW:
        desc, renamed = MG.repair_spell_names(desc, vocab)
        if renamed:
            shapes["spell-name"] = shapes.get("spell-name", 0) + len(renamed)

    name = base_name
    auth_name = str(auth.get("name") or "") if auth is not None else ""
    if auth_name and auth_name.lower() == base_name.lower():
        name = auth_name                    # same name, different case: the authority wins
    elif auth_name and base_name and auth_name.lower() != base_name.lower():
        # A real name disagreement is never merged away - it is the shape that produced
        # `5 Rage` for `Feral Charge` - and it must keep the record in the review queue.
        disputed.append(f"name {base_name!r} vs {auth_name!r}")

    if desc == base_desc and name == base_name and not disputed:
        return None
    return {"description_rank1": desc, "name": name, "shapes": shapes, "disputed": disputed,
            "changed": desc != base_desc or name != base_name}


def apply_merge(rec: dict, vocab: set[str], *, at: str) -> dict[str, Any] | None:
    """Rewrite one candidate record in place. Returns the change report, or None if nothing changed.

    ``source.confidence`` and ``source.note`` are recomputed from the evidence every run rather
    than nudged, so running this twice says the same thing as running it once and a doubt that
    has since been settled does not linger in the note.
    """
    out = merged_fields(rec, vocab)
    src = rec.setdefault("source", {})
    left = unadjudicated_doubts(rec)
    if out is not None and out["changed"]:
        src.setdefault("readings", []).append({
            "reader": PRE_MERGE_LABEL, "name": rec.get("name"), "description": rec.get("description_rank1"),
            "maxRank": (rec.get("rank") or {}).get("max"), "confidence": src.get("confidence", 1.0)})
        rec["description_rank1"] = out["description_rank1"]
        rec["name"] = out["name"]
        rec.pop("ranks_anticipated", None)     # stage 6/8 re-derives the template from the new text
    disputed = out["disputed"] if out else []
    # shapes describe what the stored text owes to the merge, so a re-run that finds nothing left
    # to do keeps the previous run's tally rather than blanking it
    shapes = ((out or {}).get("shapes") or {}) if (out and out["changed"]) else ((src.get("merge") or {}).get("shapes") or {})
    src["merge"] = {"at": at, "shapes": shapes, "disputed": disputed, "unadjudicated": left}
    settle(rec)
    return out


def note_clauses(rec: dict, crop_warning: str | None = None) -> list[str]:
    """Every ``source.note`` clause this script owns, for the record as it now stands."""
    src = rec.get("source") or {}
    clauses: list[str] = []
    disputed = (src.get("merge") or {}).get("disputed") or []
    if disputed:
        clauses.append(f"readers still differ on {'; '.join(disputed[:3])}")
    if (left := unadjudicated_doubts(rec)):
        clauses.append(f"readers differ in {', '.join(left)}, which the reader merge does not adjudicate")
    if crop_warning:
        clauses.append(crop_warning)
    return clauses


def settle(rec: dict, crop_warning: str | None = None) -> None:
    """Set ``source.confidence`` and ``source.note`` from the evidence: in the queue iff something
    is still open (a disputed word or name, a field the merge cannot adjudicate, a cut-off crop)."""
    src = rec.setdefault("source", {})
    clauses = note_clauses(rec, crop_warning)
    src["confidence"] = DISPUTED_CONFIDENCE if clauses else SETTLED_CONFIDENCE
    set_note(src, *clauses)


# Clauses this script owns. They are stripped and rewritten on every run, so a note never
# accumulates three copies of the same sentence across re-runs, and a doubt that has since been
# settled does not linger. "second reader (codex) differs in ..." belongs to second_opinion.py
# and is superseded the moment the merge adjudicates the same fields.
MERGE_CLAUSE_MARKERS = (
    "second reader",
    "readers still differ",
    "readers differ in",
    "not adjudicated by the merge",     # an earlier spelling of the same clause
    "missing a tooltip border",
    "px wide",
    "cut off",
    "re-crop the cell",
)


def strip_merge_clauses(note: str | None) -> str:
    """Everything in ``source.note`` that this script did not write."""
    parts = [p.strip() for p in (note or "").split(";") if p.strip()]
    keep = [p for p in parts if not any(m in p.lower() for m in MERGE_CLAUSE_MARKERS)]
    return "; ".join(keep)


def set_note(src: dict, *clauses: str) -> None:
    """Rewrite ``source.note`` as (everything not ours) + (our clauses, in order)."""
    parts = [p for p in [strip_merge_clauses(src.get("note"))] if p]
    parts += [c for c in clauses if c]
    if parts:
        src["note"] = "; ".join(parts)
    else:
        src.pop("note", None)


def unadjudicated_doubts(rec: dict) -> list[str]:
    """Fields the record was flagged on that this merge cannot settle."""
    src = rec.get("source") or {}
    agreement = src.get("agreement") or {}
    fields: set[str] = set()
    # stage 5 lists differing fields even when it kept full confidence (a footer-only difference);
    # only a disagreement it actually flagged counts as a doubt
    if float(agreement.get("confidence") or 1.0) < 1.0:
        fields |= set(agreement.get("differs_in") or [])
    m = _NOTE_FIELDS_RE.search(str(src.get("note") or ""))
    if m:
        fields |= {f.strip() for f in m.group(1).split(",") if f.strip()}
    return sorted(f for f in fields if f not in ADJUDICATED_FIELDS and f not in IGNORED_FIELDS)


def queue_size(records: list[dict]) -> int:
    return sum(1 for r in records if float((r.get("source") or {}).get("confidence") or 1.0) < QUEUE_BELOW)


# --------------------------------------------------------------------------- crop geometry

def crop_geometry(path: Path) -> tuple[int, float] | None:
    """``(width, weakest edge brightness relative to the strongest)`` of a tooltip crop.

    A complete WoW tooltip is a box with a light border on all four sides. If one side's
    outermost pixels are much darker than the others, the crop cut through the tooltip
    instead of around it.
    """
    import cv2

    img = cv2.imread(str(path))
    if img is None or img.shape[0] < 8 or img.shape[1] < 8:
        return None
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(float)
    edges = (g[:3, :].mean(), g[-3:, :].mean(), g[:, :3].mean(), g[:, -3:].mean())
    ref = max(edges)
    return img.shape[1], (min(edges) / ref if ref else 1.0)


def suspect_crops(geometry: dict[str, tuple[int, float]], *, edge_ratio: float = WEAK_EDGE_RATIO,
                  width_factor: float = NARROW_FACTOR) -> set[str]:
    """Ids whose crop looks cut off: a missing border **and** a below-median width.

    Both halves are needed, and a census over all 469 crops is why. A missing border alone
    flags 6 crops, 5 of which simply sit on a dark background; a narrow crop alone flags 10,
    9 of which are genuinely short tooltips. Together they flag exactly one:
    ``mage/frost/piercing-ice``, 181 px against a class median of 221, whose first line ends
    mid-word at "Increases the damage done by yo". No reader flagged it - each just guessed a
    plausible ending - so geometry is the only thing that can catch this.
    """
    if len(geometry) < 5:
        return set()
    median = sorted(w for w, _ in geometry.values())[len(geometry) // 2]
    return {k for k, (w, ratio) in geometry.items() if ratio < edge_ratio and w < width_factor * median}


# --------------------------------------------------------------------------- re-read

# --------------------------------------------------------------------------- re-read

def reread_queue(records: list[dict], server: str, factor: float, label_suffix: str = REREAD_LABEL_SUFFIX) -> int:
    """One more VLM pass over the crops still in the review queue, stored as a voting reading."""
    import cv2

    from wowtalents import reader as RD

    rd = RD.Reader(server=server, cache_dir=PIPELINE / "work" / "read" / "cache")
    label = f"{rd.model_name()}+{RD.PROMPT_VERSION}{label_suffix}"
    n = 0
    todo = [r for r in records if float((r.get("source") or {}).get("confidence") or 1.0) < QUEUE_BELOW]
    for i, rec in enumerate(todo, 1):
        src = rec.setdefault("source", {})
        if any(str(r.get("reader")) == label for r in (src.get("readings") or [])):
            continue
        rel = src.get("crop_path")
        path = (PIPELINE / rel) if rel and not Path(rel).is_absolute() else Path(rel or "")
        if not path.is_file():
            typer.echo(f"  {rec.get('id')}: crop missing ({rel})")
            continue
        img = cv2.imread(str(path))
        if img is None:
            typer.echo(f"  {rec.get('id')}: crop unreadable ({rel})")
            continue
        r = RD.clean_reading(rd.read_tooltip(img, factor=factor))
        src.setdefault("readings", []).append({"reader": label, "name": r["name"], "description": r["description"],
                                               "maxRank": r["rank_max"], "confidence": 1.0})
        n += 1
        typer.echo(f"  [{i}/{len(todo)}] {rec.get('id')} {r['name']!r}")
    return n


# --------------------------------------------------------------------------- CLI

@app.command()
def main(
    cls: str = typer.Argument(..., help="class id, or 'all'"),
    dry_run: bool = typer.Option(False, "--dry-run", help="report only, write nothing"),
    reread: bool = typer.Option(False, "--reread", help="re-read the review-queue crops once more (needs llama-server)"),
    server: str = typer.Option("http://127.0.0.1:8089", "--server", help="llama-server base URL"),
    factor: float = typer.Option(4.0, "--factor", help="upscale factor of the re-read pass"),
    prior_path: Path = typer.Option(PRIOR, "--prior", help="Classic Era prior (spell-name dictionary)"),
    at: str = typer.Option("", "--at", help="RFC 3339 stamp for source.merge (default: now)"),
) -> None:
    prior_doc = json.loads(prior_path.read_text(encoding="utf-8")) if prior_path.is_file() else {}
    if not prior_doc:
        typer.echo(f"warning: no Classic prior at {prior_path}; spell-name repairs are disabled")
    stamp = at or __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total: dict[str, int] = {}
    q_before = q_after = n_changed = 0
    for c in (CLASSES if cls == "all" else [cls]):
        path = EXTRACTED / f"{c}.candidates.json"
        if not path.is_file():
            typer.echo(f"{c}: no candidates file, skipped", err=True)
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        records = doc["candidates"] if isinstance(doc, dict) else doc
        before = queue_size(records)
        if reread:
            typer.echo(f"{c}: re-reading {before} queue crops at {factor}x")
            reread_queue(records, server, factor)
        changed = 0
        shapes: dict[str, int] = {}
        vocab = class_vocabulary(prior_doc, c)
        for rec in records:
            rep = apply_merge(rec, vocab, at=stamp)
            if rep is None:
                continue
            if rep["changed"]:
                changed += 1
            for k, v in rep["shapes"].items():
                shapes[k] = shapes.get(k, 0) + v
                total[k] = total.get(k, 0) + v
        # geometry check: a truncated crop is unverifiable however well the readers agree
        geometry = {}
        for rec in records:
            rel = (rec.get("source") or {}).get("crop_path")
            geom = crop_geometry((PIPELINE / rel) if rel and not Path(rel).is_absolute() else Path(rel or ""))
            if geom:
                geometry[rec["id"]] = geom
        suspect = suspect_crops(geometry)
        for rec in records:
            warning = None
            if rec["id"] in suspect:
                warning = (f"crop is {geometry[rec['id']][0]} px wide and missing a tooltip border, so the tooltip "
                           f"is cut off and the reading cannot be verified from it - re-crop the cell")
            elif rec.get("cut_off"):
                warning = "the reader reported the tooltip text cut off at the crop edge"
            settle(rec, warning)
        if suspect:
            typer.echo(f"  {len(suspect)} crop(s) look cut off: {', '.join(sorted(suspect))}")

        after = queue_size(records)
        q_before += before
        q_after += after
        n_changed += changed
        typer.echo(f"{c}: {len(records)} records, {changed} rewritten "
                   f"({', '.join(f'{k} {v}' for k, v in sorted(shapes.items())) or 'no shape'}); "
                   f"review queue {before} -> {after}")
        if not dry_run:
            write_candidates_atomic(path, doc, before=len(records))
    typer.echo(f"total: {n_changed} records rewritten, shapes "
               f"{', '.join(f'{k} {v}' for k, v in sorted(total.items())) or '-'}; "
               f"review queue {q_before} -> {q_after}"
               + ("  (dry run, nothing written)" if dry_run else ""))


if __name__ == "__main__":
    app()

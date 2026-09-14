"""Stage 6: anticipate ranks 2..N for every candidate record.

Reads ``data/extracted/<class>.candidates.json`` (a JSON array of hover
records, brief section 1), matches each record against the Classic Era prior
and writes a ``ranks_anticipated`` block per record::

    "ranks_anticipated": {
      "description": "Increases your armor value from items by {0}%.",
      "ranks": [[2], [4], [6], [8], [10]],
      "ranksObserved": [1],
      "ranksSource": "classic-prior",                # observed | classic-prior | extrapolated | manual
      "ranksPrior": {"classicTalentId": 1423, "classicSpellIds": [...], "match": "exact-name", "similarity": 1.0},
      "ranksNote": "Classic paladin/protection/Toughness (talent 1423): ranks copied.",
      "needsManual": false, "confidence": "high", "review": false, "rule": "copied",
      "match": {"classicTalentId": 1423, "name": "Toughness", "class": "paladin", "tree": "protection", ...}
    }

The canonical keys are exactly what ``08_export`` copies onto the talent;
``needsManual``/``confidence``/``review``/``rule``/``match`` are pipeline-side.

Commands (from ``pipeline/``)::

    uv run stages/06_rankfill.py paladin                # rewrites data/extracted/paladin.candidates.json
    uv run stages/06_rankfill.py paladin --dry-run      # table only
    uv run stages/06_rankfill.py paladin --out /tmp/x.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import typer

from wowtalents import ranks as R  # noqa: E402
from wowtalents.fsio import write_candidates_atomic  # noqa: E402

PIPELINE_DIR = Path(__file__).resolve().parents[1]
REPO = PIPELINE_DIR.parent
EXTRACTED = REPO / "data" / "extracted"

app = typer.Typer(add_completion=False)


def load_candidates(path: Path) -> tuple[list[dict], dict | None]:
    """Accept a bare array or an object with a ``candidates``/``records`` list; return (records, wrapper)."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return doc, None
    for key in ("candidates", "records", "talents"):
        if isinstance(doc.get(key), list):
            return doc[key], doc
    raise typer.BadParameter(f"{path}: expected a JSON array or an object with a 'candidates' list")


def fill(records: list[dict], prior: R.Prior | None, force: bool = False) -> Counter:
    counts: Counter = Counter()
    for rec in records:
        if not force and isinstance(rec.get("ranks_anticipated"), dict) and rec["ranks_anticipated"].get("ranksSource"):
            counts["kept"] += 1
            continue
        res = R.anticipate_record(rec, prior)
        rec["ranks_anticipated"] = res.to_fields()
        counts[res.ranks_source] += 1
    return counts


def table(records: list[dict]) -> str:
    lines = []
    for rec in records:
        ra = rec.get("ranks_anticipated") or {}
        name = rec.get("name") or "?"
        tree = rec.get("tree") or "?"
        src = ra.get("ranksSource", "-")
        conf = ra.get("confidence", "-")
        ranks = ra.get("ranks", [])
        preview = " / ".join(("|".join(str(v) for v in r) if isinstance(r, list) else "str") for r in ranks)
        flag = "*" if ra.get("review") else " "
        lines.append(f"{flag} {tree:<14} {name:<32} {src:<13} {conf:<6} {preview}")
    return "\n".join(lines)


@app.command()
def main(
    cls: str = typer.Argument(..., help="class id, e.g. paladin"),
    candidates: Path | None = typer.Option(None, "--candidates", help="input file (default data/extracted/<class>.candidates.json)"),
    out: Path | None = typer.Option(None, "--out", help="output file (default: overwrite the input)"),
    prior_path: Path = typer.Option(R.PRIOR_PATH, "--prior", help="Classic Era prior JSON"),
    force: bool = typer.Option(False, "--force", help="recompute records that already have ranks_anticipated"),
    dry_run: bool = typer.Option(False, "--dry-run", help="print the table, write nothing"),
) -> None:
    src = candidates or (EXTRACTED / f"{cls}.candidates.json")
    if not src.is_file():
        typer.echo(f"no candidates file: {src}", err=True)
        raise typer.Exit(code=2)
    records, wrapper = load_candidates(src)
    n_before = len(records)
    prior = R.Prior.load(prior_path) if prior_path.is_file() else None
    if prior is None:
        typer.echo(f"warning: prior {prior_path} not found; only extrapolated/manual ranks will be produced")
    counts = fill(records, prior, force=force)
    typer.echo(table(records))
    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    review = sum(1 for r in records if (r.get("ranks_anticipated") or {}).get("review"))
    typer.echo(f"{len(records)} records: {summary}; {review} for the review queue (*)")
    if dry_run:
        return
    dest = out or src
    payload = wrapper if wrapper is not None else records
    write_candidates_atomic(dest, payload, before=n_before if dest == src else 0)
    typer.echo(f"wrote {dest}")


if __name__ == "__main__":
    app()

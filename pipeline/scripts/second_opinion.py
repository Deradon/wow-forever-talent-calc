"""Optional second reader: transcribe every crop of a candidates file with the local ``codex`` CLI
and lower ``source.confidence`` to 0.7 (with a note) where it disagrees with the Qwen reading.

Qwen (llama-server) stays the primary reader; this only routes disagreements into the review
queue (validator rule NEEDS-REVIEW fires below 0.8). Codex outputs are cached in
``work/read/codex/<sha1 of crop>.json`` so re-runs are free.

    uv run scripts/second_opinion.py paladin            # rewrites data/extracted/paladin.candidates.json
    uv run scripts/second_opinion.py paladin --dry-run  # report only
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import typer

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parent
CACHE = PIPELINE / "work" / "read" / "codex"
PROMPT = (
    'Transcribe this World of Warcraft talent tooltip exactly. Return only JSON with keys: name (string), '
    'rank_max (integer from the "Rank N/M" line), description (all gold paragraphs only, line breaks joined with '
    'single spaces; exclude the Passive line, Requires lines and the green "Click to learn" footer). '
    'Copy every character, including % and punctuation.'
)
SECOND_CONFIDENCE = 0.7

app = typer.Typer(add_completion=False)


def norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def codex_read(crop: Path, timeout: int = 180) -> dict | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(crop.read_bytes() + PROMPT.encode()).hexdigest()
    cp = CACHE / f"{key}.json"
    if cp.is_file():
        return json.loads(cp.read_text(encoding="utf-8"))
    out = CACHE / f"{key}.txt"
    subprocess.run(["codex", "exec", "--ephemeral", "--skip-git-repo-check", "-o", str(out), "-i", str(crop), "-"],
                   input=PROMPT, text=True, capture_output=True, timeout=timeout)
    if not out.is_file():
        return None
    body = "\n".join(l for l in out.read_text(encoding="utf-8").splitlines() if not re.match(r"^\s*tokens? used", l, re.I))
    m = re.search(r"\{.*\}", body, re.S)
    if not m:
        return None
    try:
        res = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    cp.write_text(json.dumps(res, ensure_ascii=False) + "\n", encoding="utf-8")
    out.unlink(missing_ok=True)
    return res


def compare(rec: dict, other: dict) -> list[str]:
    diffs = []
    if norm(other.get("name")).lower() != norm(rec.get("name")).lower():
        diffs.append("name")
    if other.get("rank_max") != (rec.get("rank") or {}).get("max"):
        diffs.append("rank_max")
    if norm(other.get("description")) != norm(rec.get("description_rank1")):
        diffs.append("description")
    return diffs


@app.command()
def main(
    cls: str = typer.Argument(..., help="class id"),
    candidates: Path | None = typer.Option(None, help="default data/extracted/<class>.candidates.json"),
    dry_run: bool = typer.Option(False, help="report only"),
) -> None:
    src = candidates or (REPO / "data" / "extracted" / f"{cls}.candidates.json")
    doc = json.loads(src.read_text(encoding="utf-8"))
    records = doc["candidates"] if isinstance(doc, dict) else doc
    n_diff = n_missing = 0
    for rec in records:
        crop = rec.get("source", {}).get("crop_path")
        path = (PIPELINE / crop) if crop and not Path(crop).is_absolute() else Path(crop or "")
        if not path.is_file():
            n_missing += 1
            continue
        other = codex_read(path)
        if other is None:
            n_missing += 1
            typer.echo(f"  {rec['id']}: no codex reading")
            continue
        diffs = compare(rec, other)
        s = rec["source"]
        s.setdefault("readings", []).append({"reader": "codex-cli", "name": other.get("name"),
                                             "description": norm(other.get("description")),
                                             "maxRank": other.get("rank_max"), "confidence": 1.0 if not diffs else 0.7})
        if diffs:
            n_diff += 1
            s["confidence"] = min(float(s.get("confidence") or 1.0), SECOND_CONFIDENCE)
            note = f"second reader (codex) differs in {', '.join(diffs)}"
            s["note"] = f"{s['note']}; {note}" if s.get("note") else note
            typer.echo(f"  {rec['id']} {rec.get('name')!r}: differs in {diffs}")
            for f in diffs:
                a = other.get("rank_max") if f == "rank_max" else other.get("name" if f == "name" else "description")
                b = (rec.get("rank") or {}).get("max") if f == "rank_max" else rec.get("name" if f == "name" else "description_rank1")
                typer.echo(f"      codex: {a}\n      qwen:  {b}")
    typer.echo(f"{len(records)} records: {n_diff} disagreements (confidence -> {SECOND_CONFIDENCE}), {n_missing} without a second reading")
    if not dry_run:
        src.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        typer.echo(f"wrote {src}")


if __name__ == "__main__":
    app()

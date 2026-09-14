"""What every stage driver needs and only stages 11 and 12 had two copies of.

Round one's finding E8 (duplicated logic) came back in round two as nine helpers copied
between ``stages/11_spellbook.py`` and ``stages/12_races.py``: ``hms``, ``now``,
``parse_window``, ``json_object``, ``codex_opinion``, ``source``, ``ensure``, ``apply_third``
and ``prune_crops`` (``docs/reviews/2026-09-14-data-code-perf.md`` K-7). Two copies of the
same confidence ladder drift; one of them already had.

Everything here is stage-agnostic: it takes the ids, keys and prompts of the dataset as
arguments rather than knowing about spells or races. The only I/O is the codex subprocess and
the crop deletion, both of which the caller asks for explicitly.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .fsio import write_json_atomic

__all__ = ["hms", "now", "parse_window", "json_object", "codex_opinion", "source", "ensure",
           "apply_third", "prune_crops", "CODEX_TIMEOUT",
           "BOTH_PASSES_AGREE_THIRD_DIFFERS", "TWO_OF_THREE_VERBATIM", "THIRD_ONLY"]

#: Seconds a single codex CLI call may take before it is abandoned.
CODEX_TIMEOUT = 420

#: The one confidence ladder for a third opinion, which stages 11 and 12 each had a copy of.
BOTH_PASSES_AGREE_THIRD_DIFFERS = 0.9
TWO_OF_THREE_VERBATIM = 0.85
THIRD_ONLY = 0.3


def hms(t: float) -> str:
    """Seconds of stream time as ``HH:MM:SS``."""
    s = int(t)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def now() -> str:
    """UTC stamp in the format every generated file in this repository carries."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_window(spec: str) -> tuple[int, int]:
    """``"03:59:00-04:02:00"`` or ``"14340-14520"`` -> ``(start, end)`` in seconds."""
    a, _, b = spec.partition("-")

    def p(x: str) -> int:
        x = x.strip()
        if ":" in x:
            parts = [int(v) for v in x.split(":")]
            while len(parts) < 3:
                parts.insert(0, 0)
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return int(x)

    return p(a), p(b)


def json_object(text: str, key: str | None = None) -> dict | None:
    """The first balanced JSON object in a free-form CLI answer, optionally holding ``key``.

    The codex CLI answers in prose around its JSON often enough that parsing the whole reply is
    not an option, and ``json.loads`` on a fenced block fails on the fence.
    """
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        doc = json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(doc, dict) and (key is None or key in doc):
                        return doc
                    break
        start = text.find("{", start + 1)
    return None


def codex_opinion(image: Path, out_dir: Path, prompt: str, key: str | None = None,
                  timeout: int = CODEX_TIMEOUT) -> dict | None:
    """An independent reading of one crop by the codex CLI (best effort, cached on disk).

    The cache is the point: a reading costs about ten seconds and several hundred of them make
    a run, so a re-run of the stage must not pay for them again. A crop whose answer could not
    be parsed returns ``None`` and is simply not cached.
    """
    out = out_dir / (image.stem + ".codex.json")
    if out.is_file():
        try:
            return json.loads(out.read_text())
        except json.JSONDecodeError:
            out.unlink()
    raw = out.with_suffix(".txt")
    try:
        subprocess.run(["codex", "exec", "--ephemeral", "--skip-git-repo-check",
                        "-o", str(raw), "-i", str(image), "-"],
                       input=prompt, text=True, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    doc = json_object(raw.read_text(), key) if raw.is_file() else None
    if doc is not None:
        write_json_atomic(out, doc)
    return doc


def source(video: str, t: float, frame: int, crop: str, conf: float, reader: str, panel: str,
           readings: list[dict] | None = None, note: str | None = None) -> dict:
    """The ``source`` block every published non-talent record carries, in schema key order."""
    src: dict = {"kind": "video", "video": video, "t": round(float(t), 3), "frame": int(frame),
                 "crop": crop, "panel": panel, "confidence": round(float(conf), 2), "reader": reader}
    if readings:
        src["readings"] = readings
    src["reviewed"] = False
    if note:
        src["note"] = note
    return src


def ensure(p: Path) -> Path:
    """``mkdir -p`` that returns the directory, so it can be used inline in a path expression."""
    p.mkdir(parents=True, exist_ok=True)
    return p


def apply_third(records: Sequence[dict], third: Sequence[dict], *, ident: Callable[[dict], str],
                agreement: Callable[[dict, dict], float]) -> list[dict]:
    """Fold a third reading into records that already carry two, on one confidence ladder.

    ``ident`` is the dataset's id of a reading (spell id, trait id); ``agreement`` scores two
    readings against each other. A third reading matching nobody becomes its own record at
    :data:`THIRD_ONLY`, which is below every publish threshold - it is a lead, not a fact.
    """
    by_id = {ident(c): c for c in third if ident(c)}
    out: list[dict] = []
    for rec in records:
        c = by_id.get(ident(rec))
        if c is None:
            out.append(rec)
            continue
        readings = list(rec.get("readings") or [])
        best = max((agreement(r, c) for r in readings), default=0.0)
        conf = float(rec.get("confidence") or 0.0)
        if conf >= 1.0 and best < 1.0:
            conf = BOTH_PASSES_AGREE_THIRD_DIFFERS     # both passes agree, the third reads it differently
        elif best >= 1.0:
            conf = max(conf, TWO_OF_THREE_VERBATIM)    # two of three agree verbatim
        elif best >= 0.7:
            conf = max(conf, 0.7)
        out.append({**rec, "confidence": conf, "readings": readings + [c], "codex": True})
    seen = {ident(r) for r in records}
    for tid, c in by_id.items():
        if tid not in seen:
            out.append({**c, "confidence": THIRD_ONLY, "readings": [c], "codex": True})
    return out


def prune_crops(review: Path, keep: Iterable[str], repo: Path, *, dry_run: bool = False) -> list[str]:
    """Delete review crops no published file names any more; returns what went (or would go).

    Files whose name starts with ``_`` are the page, panel and class-bar context crops the notes
    and docs point at, and are never pruned. ``dry_run`` lists without deleting, because this is
    the one pipeline operation that removes **committed** files (K-1).
    """
    keep = set(keep)
    gone: list[str] = []
    for png in sorted(review.rglob("*.png")):
        if png.name.startswith("_"):
            continue
        rel = str(png.relative_to(repo))
        if rel not in keep:
            if not dry_run:
                png.unlink()
            gone.append(rel)
    return gone

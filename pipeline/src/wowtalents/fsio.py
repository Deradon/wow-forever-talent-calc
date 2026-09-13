"""Crash-safe writes for the pipeline's expensive artefacts.

``data/extracted/<class>.candidates.json`` is hours of VLM reads. A plain
``Path.write_text`` truncates the target before it writes, so a Ctrl-C or an
exception in the middle leaves an empty or half-written JSON with no backup.
``export.write_validated`` already did this correctly (temp file + ``os.replace``);
these helpers are that pattern, reusable, for every other write site.

``os.replace`` is atomic within a filesystem, so the temp file is always created
next to the destination.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

__all__ = ["write_text_atomic", "write_json_atomic"]


def _umask() -> int:
    cur = os.umask(0)
    os.umask(cur)
    return cur


def write_text_atomic(path: str | Path, text: str, *, encoding: str = "utf-8") -> Path:
    """Write ``text`` to ``path`` via a temp file in the same directory and ``os.replace``.

    The destination either keeps its previous content or holds the complete new
    content; it is never observed truncated.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp creates 0600; keep the destination's own mode so an atomic rewrite does not
    # silently make a tracked file unreadable to anyone else
    mode = path.stat().st_mode & 0o777 if path.exists() else (0o666 & ~_umask())
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def write_json_atomic(path: str | Path, doc: Any, *, indent: int = 2, ensure_ascii: bool = False) -> Path:
    """``json.dumps`` + :func:`write_text_atomic`, with the pipeline's trailing newline."""
    return write_text_atomic(path, json.dumps(doc, indent=indent, ensure_ascii=ensure_ascii) + "\n")


def candidate_count(doc: Any) -> int:
    """Records in a candidates document, in either of its two shapes (wrapped dict or bare list)."""
    return len(doc.get("candidates") or [] if isinstance(doc, dict) else doc or [])


def write_candidates_atomic(path: str | Path, doc: Any, *, before: int) -> Path:
    """Atomic write of ``<class>.candidates.json``, refused if the run lost records.

    Stages 6, 7 and 9 rewrite the file wholesale and only stage 8 validated first, so a
    bug that dropped records overwrote hours of VLM reads with a shorter file. Losing a
    record is never a legitimate outcome of those stages; raising here keeps the old file.
    """
    now = candidate_count(doc)
    if now < before:
        raise ValueError(f"{Path(path).name}: record count would shrink {before} -> {now}; refusing to write")
    return write_json_atomic(path, doc)

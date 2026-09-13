"""Stage 8: export canonical class files (docs/DATA-SCHEMA.md sections 4-6).

Commands (from ``pipeline/``)::

    uv run stages/08_export.py extract warrior            # candidates -> data/extracted/warrior.json
    uv run stages/08_export.py promote warrior            # extracted + overrides (+ reviewed) -> data/talents/warrior.json
    uv run stages/08_export.py all warrior                # both

``extract`` reads ``data/extracted/<class>.candidates.json`` (stage 5/6
output), copies tooltip crops into ``data/review/<class>/<tree>/<id>.png``,
anticipates ranks where stage 6 has not run, and validates the result before
writing. ``promote`` applies ``data/overrides/<class>.json``, keeps every
``reviewed: true`` talent of the existing canonical file (``REVIEWED-DIFF``
warnings), strips ``source.readings`` and validates with ``--check``.

Validation rule 11 requires the class in the highest ``data/encoding/v<N>.json``;
``--update-encoding`` upserts the class entry there (only legal while that
version is unpublished; otherwise bump the version by hand, see
``data/encoding/README.md``). Every stage exits 1 on validation errors and
leaves the target file untouched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wowtalents import export as X  # noqa: E402
from wowtalents import ranks as R  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _print(log: X.Log, verbose: bool) -> None:
    for line in log.lines:
        if verbose or not line.startswith("INFO"):
            typer.echo(line)


def _load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _extract(cls: str, root: Path, candidates: Path | None, video: str, fps: int, tree_order: str | None,
             update_encoding: bool, no_files: bool, copy_crops: bool, dry_run: bool, verbose: bool) -> bool:
    src = candidates or (root / "data" / "extracted" / f"{cls}.candidates.json")
    if not src.is_file():
        typer.echo(f"no candidates file: {src}", err=True)
        raise typer.Exit(code=2)
    log = X.Log()
    prior = R.Prior.load(root / "data" / "prior" / "classic-era" / "talents.json") if (root / "data" / "prior" / "classic-era" / "talents.json").is_file() else None
    order = [t.strip() for t in tree_order.split(",")] if tree_order else None
    doc = X.build_extracted(cls, X.load_candidates(src), prior, root=root, video=video, fps=fps, tree_order=order,
                            copy_crops=copy_crops and not dry_run, log=log)
    if update_encoding and not dry_run:
        X.update_encoding(root, doc, log)
    dest = root / "data" / "extracted" / f"{cls}.json"
    if dry_run:
        _print(log, verbose)
        typer.echo(X.validate.canonical_dumps(doc))
        return True
    ok = X.write_validated(doc, dest, root, log, check=True, no_files=no_files)
    _print(log, verbose)
    n = sum(len(t["talents"]) for t in doc["trees"])
    typer.echo(f"{'wrote' if ok else 'NOT written'} {dest} ({n} talents in {len(doc['trees'])} trees)")
    return ok


def _prune(root: Path, verbose: bool, dry_run: bool) -> None:
    """Delete data/review PNGs no class file references any more (all nine files must exist)."""
    log = X.Log()
    paths = sorted((root / "data" / "talents").glob("*.json"))
    if len(paths) < 9:
        typer.echo(f"prune: only {len(paths)} class file(s) in data/talents; refusing to prune against a partial set",
                   err=True)
        raise typer.Exit(code=2)
    # data/examples/*.json keeps its own crops under data/review/<class>/ (the tinker sample the
    # schema, validator and web tests all point at); those are referenced, not orphaned
    paths += sorted((root / "data" / "examples").glob("*.json"))
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    gone = X.prune_review_crops(root, docs, log, dry_run=dry_run)
    _print(log, verbose)
    typer.echo(f"{'would remove' if dry_run else 'removed'} {len(gone)} orphaned crop(s) under data/review")


def _promote(cls: str, root: Path, update_encoding: bool, no_files: bool, verbose: bool) -> bool:
    extracted = root / "data" / "extracted" / f"{cls}.json"
    if not extracted.is_file():
        typer.echo(f"no extracted file: {extracted} (run extract first)", err=True)
        raise typer.Exit(code=2)
    log = X.Log()
    doc = X.build_talents(_load(extracted), _load(root / "data" / "overrides" / f"{cls}.json"),
                          _load(root / "data" / "talents" / f"{cls}.json"), log)
    if update_encoding:
        X.update_encoding(root, doc, log)
    dest = root / "data" / "talents" / f"{cls}.json"
    ok = X.write_validated(doc, dest, root, log, check=True, no_files=no_files)
    _print(log, verbose)
    reviewed = sum(1 for t in doc["trees"] for x in t["talents"] if x["source"].get("reviewed"))
    n = sum(len(t["talents"]) for t in doc["trees"])
    typer.echo(f"{'wrote' if ok else 'NOT written'} {dest} ({n} talents, {reviewed} reviewed)")
    return ok


ROOT_OPT = typer.Option(X.REPO_ROOT, "--root", help="repository root")
ENC_OPT = typer.Option(False, "--update-encoding", help="upsert the class into the highest data/encoding/v<N>.json")
NOFILES_OPT = typer.Option(False, "--no-files", help="skip crop existence checks (validator rule 9)")
VERBOSE_OPT = typer.Option(False, "--verbose", "-v", help="also print INFO lines (dedupe decisions, encoding)")


@app.command()
def extract(
    cls: str = typer.Argument(..., help="class id, e.g. warrior"),
    root: Path = ROOT_OPT,
    candidates: Path | None = typer.Option(None, "--candidates", help="input (default data/extracted/<class>.candidates.json)"),
    video: str = typer.Option(X.VIDEO_ID, "--video", help="YouTube id for records without one"),
    fps: int = typer.Option(X.FPS, "--fps", help="native frame rate, for frame = t * fps"),
    tree_order: str | None = typer.Option(None, "--tree-order", help="comma-separated tree names left to right (default: segments.json)"),
    update_encoding: bool = ENC_OPT,
    no_files: bool = NOFILES_OPT,
    no_copy: bool = typer.Option(False, "--no-copy", help="do not copy crops into data/review/"),
    dry_run: bool = typer.Option(False, "--dry-run", help="print the document, write nothing"),
    verbose: bool = VERBOSE_OPT,
) -> None:
    """candidates -> data/extracted/<class>.json"""
    if not _extract(cls, root, candidates, video, fps, tree_order, update_encoding, no_files, not no_copy, dry_run, verbose):
        raise typer.Exit(code=1)


@app.command()
def promote(
    cls: str = typer.Argument(..., help="class id"),
    root: Path = ROOT_OPT,
    update_encoding: bool = ENC_OPT,
    no_files: bool = NOFILES_OPT,
    verbose: bool = VERBOSE_OPT,
) -> None:
    """extracted + overrides + reviewed records -> data/talents/<class>.json"""
    if not _promote(cls, root, update_encoding, no_files, verbose):
        raise typer.Exit(code=1)


@app.command()
def prune(
    root: Path = ROOT_OPT,
    dry_run: bool = typer.Option(False, "--dry-run", help="list the orphans, delete nothing"),
    verbose: bool = VERBOSE_OPT,
) -> None:
    """delete data/review crops no data/talents or data/examples file references (run after promote)"""
    _prune(root, verbose, dry_run)


@app.command(name="all")
def all_(
    cls: str = typer.Argument(..., help="class id"),
    root: Path = ROOT_OPT,
    update_encoding: bool = ENC_OPT,
    no_files: bool = NOFILES_OPT,
    verbose: bool = VERBOSE_OPT,
) -> None:
    """extract, then promote"""
    if not _extract(cls, root, None, X.VIDEO_ID, X.FPS, None, update_encoding, no_files, True, False, verbose):
        raise typer.Exit(code=1)
    if not _promote(cls, root, update_encoding, no_files, verbose):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

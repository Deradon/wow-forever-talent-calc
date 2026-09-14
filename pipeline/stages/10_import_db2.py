"""Stage 10: datamined import from wago.tools DB2 CSV exports.

Commands (from ``pipeline/``)::

    uv run stages/10_import_db2.py fetch --build 1.15.9.69722
    uv run stages/10_import_db2.py build --build 1.15.9.69722 --out ../data/datamined/1.15.9.69722
    uv run stages/10_import_db2.py diff  --build 1.15.9.69722
    uv run stages/10_import_db2.py promote --from datamined/1.15.9.69722 --class warrior

``fetch`` downloads the ten tables the join needs into
``pipeline/work/db2/<build>/`` (sequential, ~1.5 s apart, cached, with
``manifest.json`` carrying row counts and sha256 per file). ``build`` joins them
into one class file per class in the canonical schema
(``source.kind: "datamined"``, ``ranksSource: "observed"``, ``iconSource:
"datamined"``, ``spellIds`` filled) and validates each file before writing.
``diff`` compares that output with ``data/talents/<class>.json`` by talent name
and writes a Markdown plus a JSON report. ``promote`` is the beta-day merge
(docs/DATA-SCHEMA.md section 9); it prints a plan and only writes with
``--apply``.

On beta day only ``--build`` changes. ``builds`` lists what wago.tools has.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wowtalents import db2 as D  # noqa: E402
from wowtalents import export as X  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)

ROOT_OPT = typer.Option(D.REPO_ROOT, "--root", help="repository root")
BUILD_OPT = typer.Option(..., "--build", help="client build, e.g. 1.15.9.69722")
CACHE_OPT = typer.Option(None, "--cache", help="DB2 CSV cache (default pipeline/work/db2/<build>)")
VERBOSE_OPT = typer.Option(False, "--verbose", "-v", help="also print INFO lines")


def _print(log: D.Log, verbose: bool) -> None:
    for line in log.lines:
        if verbose or not line.startswith("INFO"):
            typer.echo(line)


def _cache(build: str, cache: Path | None) -> Path:
    return cache or D.build_dir(build)


def _load_docs(out: Path) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(out.glob("*.json"))}


@app.command()
def builds(
    product: str = typer.Option("", "--product", help="filter, e.g. wow_classic_era"),
    limit: int = typer.Option(30, "--limit"),
) -> None:
    """list the builds wago.tools knows (find the Forever product code here)"""
    import requests

    resp = requests.get(D.BUILDS_URL, timeout=60, headers={"User-Agent": D.USER_AGENT})
    resp.raise_for_status()
    data = resp.json()
    rows: list[tuple[str, str, str]] = []
    for prod, entries in (data.items() if isinstance(data, dict) else []):
        if product and product not in prod:
            continue
        for e in entries if isinstance(entries, list) else []:
            rows.append((prod, str(e.get("version", e)), str(e.get("created_at", ""))))
    for prod, version, created in sorted(rows, key=lambda r: r[2], reverse=True)[:limit]:
        typer.echo(f"{prod:<28} {version:<20} {created}")
    typer.echo(f"({len(rows)} build(s); products: {', '.join(sorted({r[0] for r in rows}))})")


@app.command()
def fetch(
    build: str = BUILD_OPT,
    cache: Path | None = CACHE_OPT,
    force: bool = typer.Option(False, "--force", help="re-download tables that are already cached"),
    delay: float = typer.Option(1.5, "--delay", help="seconds between requests (be polite)"),
    verbose: bool = VERBOSE_OPT,
) -> None:
    """download the DB2 CSV exports for <build> and write manifest.json"""
    log = D.Log()
    out = _cache(build, cache)
    try:
        manifest = D.fetch(build, dest=out, force=force, delay=delay, log=log)
    except Exception as e:  # noqa: BLE001 - one failure must stop the run, with the reason
        _print(log, verbose)
        typer.echo(f"fetch failed: {e}", err=True)
        raise typer.Exit(code=1) from e
    _print(log, verbose)
    for e in manifest["tables"]:
        typer.echo(f"{e['table']:<24} {e['rows']:>8} rows  {e['bytes'] / 1e6:>7.2f} MB  {e['sha256'][:12]}")
    typer.echo(f"cached in {out}")


@app.command()
def check(build: str = BUILD_OPT, cache: Path | None = CACHE_OPT) -> None:
    """re-hash the cached CSVs against manifest.json"""
    log = D.Log()
    ok = D.verify(build, dest=_cache(build, cache), log=log)
    _print(log, True)
    typer.echo("manifest ok" if ok else "manifest MISMATCH")
    if not ok:
        raise typer.Exit(code=1)


@app.command()
def build(
    build: str = BUILD_OPT,
    out: Path | None = typer.Option(None, "--out", help="output directory (default data/datamined/<build>)"),
    root: Path = ROOT_OPT,
    cache: Path | None = CACHE_OPT,
    only: str = typer.Option("", "--class", help="comma-separated class ids; default all"),
    dry_run: bool = typer.Option(False, "--dry-run", help="validate and report, write nothing"),
    verbose: bool = VERBOSE_OPT,
) -> None:
    """join the cached CSVs into one canonical class file per class"""
    log = D.Log()
    dest = out or (root / "data" / "datamined" / build)
    db = D.load(build, dest=_cache(build, cache), log=log)
    docs, report = D.build_class_docs(db, root=root, log=log)
    wanted = {c.strip() for c in only.split(",") if c.strip()}
    if wanted:
        docs = {k: v for k, v in docs.items() if k in wanted}
    _print(log, verbose)

    failed = []
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)
    for cls, doc in docs.items():
        wlog = X.Log()
        if dry_run:
            result = X.run_validator_doc(doc, cls, dest, root)
            ok = result.count("ERROR") == 0
            for f in result.findings:
                if f.level == "ERROR":
                    typer.echo(f"ERROR {f.code} {f.path}: {f.message}")
        else:
            ok = X.write_validated(doc, dest / f"{cls}.json", root, wlog,
                                   check=True, no_files=True, no_encoding=True)
            for line in wlog.lines:
                if line.startswith("ERROR") or verbose:
                    typer.echo(line)
        n = sum(len(t["talents"]) for t in doc["trees"])
        typer.echo(f"{'ok   ' if ok else 'FAIL '} {cls:<9} {len(doc['trees'])} trees, {n} talents")
        if not ok:
            failed.append(cls)

    t = report["totals"]
    typer.echo(f"{t['classes']} classes, {t['trees']} trees, {t['talents']} talents")
    if not dry_run:
        rep = dest / "report"
        rep.mkdir(parents=True, exist_ok=True)
        (rep / "import.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (rep / "import.md").write_text(D.report_markdown(report), encoding="utf-8")
        typer.echo(f"wrote {dest} (+ report/import.md, report/import.json)")
    if failed:
        typer.echo(f"validation failed for: {', '.join(failed)}", err=True)
        raise typer.Exit(code=1)


@app.command()
def diff(
    build: str = BUILD_OPT,
    root: Path = ROOT_OPT,
    src: Path | None = typer.Option(None, "--src", help="datamined directory (default data/datamined/<build>)"),
    against: Path | None = typer.Option(None, "--against", help="canonical directory (default data/talents)"),
    out: Path | None = typer.Option(None, "--out", help="write the report here (default <src>/report/diff.{md,json})"),
    only: str = typer.Option("", "--class", help="comma-separated class ids; default all"),
    stdout: bool = typer.Option(False, "--stdout", help="print the Markdown instead of writing files"),
) -> None:
    """compare data/datamined/<build>/ with data/talents/ by talent name"""
    source = src or (root / "data" / "datamined" / build)
    canon = against or (root / "data" / "talents")
    if not source.is_dir():
        typer.echo(f"no datamined output at {source}; run `build --build {build}` first", err=True)
        raise typer.Exit(code=2)
    wanted = {c.strip() for c in only.split(",") if c.strip()}
    diffs = []
    for cls, doc in _load_docs(source).items():
        if wanted and cls not in wanted:
            continue
        old_path = canon / f"{cls}.json"
        if not old_path.is_file():
            typer.echo(f"{cls}: no {old_path.name} to compare against; skipped")
            continue
        diffs.append(D.diff_class(doc, json.loads(old_path.read_text(encoding="utf-8"))))
    if not diffs:
        typer.echo("nothing to compare", err=True)
        raise typer.Exit(code=2)
    md = D.diff_markdown(diffs)
    if stdout:
        typer.echo(md)
        return
    target = out or (source / "report")
    target.mkdir(parents=True, exist_ok=True)
    (target / "diff.md").write_text(md, encoding="utf-8")
    (target / "diff.json").write_text(json.dumps(diffs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for d in diffs:
        s = d["summary"]
        typer.echo(f"{d['class']:<9} new {s['new']:>3}  gone {s['gone']:>3}  pos {s['position']:>3}  "
                   f"maxRank {s['maxRank']:>3}  ranks {s['ranks']:>4}  requires {s['requires']:>3}  "
                   f"icons {s['icons']:>3}")
    typer.echo(f"wrote {target / 'diff.md'} and {target / 'diff.json'}")


@app.command(name="compare-prior")
def compare_prior(
    build: str = BUILD_OPT,
    root: Path = ROOT_OPT,
    src: Path | None = typer.Option(None, "--src", help="datamined directory (default data/datamined/<build>)"),
    out: Path | None = typer.Option(None, "--out", help="report directory (default <src>/report)"),
    stdout: bool = typer.Option(False, "--stdout", help="print the Markdown instead of writing files"),
) -> None:
    """check a Classic Era import against data/prior/classic-era/talents.json"""
    source = src or (root / "data" / "datamined" / build)
    prior_path = root / "data" / "prior" / "classic-era" / "talents.json"
    if not prior_path.is_file():
        typer.echo(f"no prior at {prior_path}", err=True)
        raise typer.Exit(code=2)
    res = D.compare_prior(_load_docs(source), json.loads(prior_path.read_text(encoding="utf-8")))
    md = D.compare_markdown(res)
    if stdout:
        typer.echo(md)
        return
    target = out or (source / "report")
    target.mkdir(parents=True, exist_ok=True)
    (target / "compare-prior.md").write_text(md, encoding="utf-8")
    (target / "compare-prior.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    r = res["rankTexts"]
    typer.echo(f"trees {res['datamined']['trees']}/{res['prior']['trees']}  "
               f"talents {res['datamined']['talents']}/{res['prior']['talents']}  "
               f"matched {res['matched']}  rank texts {r['equal']}/{r['equal'] + r['differing']} = {r['percent']} %")
    typer.echo(f"wrote {target / 'compare-prior.md'}")


@app.command()
def promote(
    from_: str = typer.Option(..., "--from", help="source under data/, e.g. datamined/1.15.9.69722"),
    cls: str = typer.Option("", "--class", help="comma-separated class ids; default every class in the source"),
    root: Path = ROOT_OPT,
    out: Path | None = typer.Option(None, "--out", help="target directory (default data/talents)"),
    apply: bool = typer.Option(False, "--apply", help="actually write; without it only the plan is printed"),
    verbose: bool = VERBOSE_OPT,
) -> None:
    """datamined build -> data/talents (merge policy: docs/DATA-SCHEMA.md section 9)"""
    source = root / "data" / from_
    dest = out or (root / "data" / "talents")
    if not source.is_dir():
        typer.echo(f"no such source: {source}", err=True)
        raise typer.Exit(code=2)
    wanted = {c.strip() for c in cls.split(",") if c.strip()}
    plans = []
    for name, doc in _load_docs(source).items():
        if wanted and name not in wanted:
            continue
        old_path = dest / f"{name}.json"
        old = json.loads(old_path.read_text(encoding="utf-8")) if old_path.is_file() else None
        log = X.Log()
        merged, plan = X.merge_datamined(doc, old, log)
        plans.append((name, merged, plan, log))
        typer.echo(f"{name:<9} {plan['talents']} talents; "
                   f"icon crops kept {plan['cropsKept']}, reviewed overrides dropped {plan['overridesDropped']}, "
                   f"new ids {len(plan['newIds'])}, gone ids {len(plan['goneIds'])}")
        for line in log.lines:
            if verbose or not line.startswith("INFO"):
                typer.echo(f"  {line}")
    if not apply:
        typer.echo("dry run: nothing written (pass --apply). "
                   "Remember the encoding step: new or renamed ids need data/encoding/v<N+1>.json "
                   "plus a migration (DATA-SCHEMA.md sections 8 and 9).")
        return
    for name, merged, _plan, log in plans:
        ok = X.write_validated(merged, dest / f"{name}.json", root, log, check=True)
        typer.echo(f"{'wrote' if ok else 'NOT written'} {dest / f'{name}.json'}")
        if not ok:
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

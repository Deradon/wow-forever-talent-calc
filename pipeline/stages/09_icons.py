"""Stage 9: replace 36 px screengrab icons by known icon names where one matches.

Commands (from ``pipeline/``)::

    uv run stages/09_icons.py refs                 # build the reference list + download 36 px icons (work/icons/)
    uv run stages/09_icons.py match all --sheet    # crops -> data/icons/matches.json (+ contact sheets)
    uv run stages/09_icons.py fetch                # 56 px icons for accepted matches -> web/public/icons/
    uv run stages/09_icons.py apply all            # icon/icon_source into data/extracted/<class>.candidates.json

``refs`` reads ``work/icons/lists/`` (Classic prior icons, Wowhead's TBC/Wrath/Cata/MoP talent data
files, the Classic Era client's ``ManifestInterfaceData`` from wago.tools; ``--fetch-lists`` downloads
the latter two) and fetches every listed icon once from Wowhead's CDN (``medium`` = 36 px), one
request at a time with a 0.3 s pause; a 403/429 stops the run. ``match`` compares every
``iconCrop`` of ``data/extracted/<class>.json`` (``--from talents`` for the canonical file) with the
reference set (see ``wowtalents.icons``) and writes one record per ``<tree>/<talent-id>`` into
``data/icons/matches.json``; hand verdicts in ``data/icons/verified.json`` (``{class: {"tree/talent":
true | false | "<icon name>"}}``) are merged: ``false`` retracts a match, ``true`` confirms it (or accepts
the best candidate of a rejected talent), an icon name forces that icon (``method: "manual"``). ``apply`` copies accepted matches into
the candidates file so ``08_export.py extract`` emits ``icon`` / ``iconSource: "classic"`` and drops
``iconCrop``; by default only ``confidence: "high"`` matches (and hand-verified ones) are applied and
fetched, ``--min-confidence medium`` takes all. Re-run ``08_export.py extract`` and ``promote`` afterwards.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import typer
from PIL import Image, ImageDraw

from wowtalents import icons as I  # noqa: E402
from wowtalents.fsio import write_candidates_atomic, write_text_atomic  # noqa: E402

PIPELINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PIPELINE_DIR.parent
WORK = PIPELINE_DIR / "work" / "icons"
CDN = "https://wow.zamimg.com/images/wow/icons/{size}/{name}.jpg"
USER_AGENT = "WoW4Ever-talents fan tool (icon reference fetch; contact via GitHub)"
PAUSE = 0.3
CLASSES = ["druid", "hunter", "mage", "paladin", "priest", "rogue", "shaman", "warlock", "warrior"]
LATER_GAMES = ["tbc", "wotlk", "cata", "mop-classic"]           # Wowhead game keys with talent data files
ERA_BUILD = "1.15.9.69722"                                      # Classic Era client listed by wago.tools

app = typer.Typer(add_completion=False, no_args_is_help=True)
ROOT_OPT = typer.Option(REPO_ROOT, "--root", help="repository root")


# ----------------------------------------------------------------------------- network

class Stop(Exception):
    pass


def _get(url: str, dest: Path, log: list[str]) -> bool:
    """One polite GET; False on 404/network error, raises Stop on 403/429."""
    import requests

    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    except requests.RequestException as e:
        log.append(f"ERR {url} {e}")
        return False
    finally:
        time.sleep(PAUSE)
    if r.status_code in (403, 429):
        raise Stop(f"{r.status_code} from {url}; stopping")
    if r.status_code != 200 or not r.content:
        log.append(f"{r.status_code} {url}")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return True


def _download_icons(names: list[str], size: str, dest_dir: Path, log: list[str]) -> tuple[int, int]:
    ok = miss = 0
    for i, name in enumerate(names):
        out = dest_dir / f"{name}.jpg"
        if out.is_file() and out.stat().st_size > 0:
            continue
        if _get(CDN.format(size=size, name=name), out, log):
            ok += 1
        else:
            miss += 1
        if i and i % 200 == 0:
            typer.echo(f"  {i}/{len(names)} ok={ok} miss={miss}")
    return ok, miss


# ----------------------------------------------------------------------------- reference list

def _era_icons(manifest_csv: Path) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    with manifest_csv.open(encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("FilePath") or "").lower().rstrip("\\") != "interface\\icons":
                continue
            n = re.sub(r"\.(blp|png|tga)$", "", (row.get("FileName") or "").lower())
            if n and n not in seen and I.ICON_RE.match(n):
                seen.add(n)
                names.append(n)
    return names


# Download order inside the client tier: talent icons are spells/abilities, then weapons, shields and
# miscellany used by weapon-specialisation talents; armour pieces, achievements and the rest come last.
_ERA_PRIORITY = [re.compile(r"^(spell|ability|classic|classicon|racial)_"),
                 re.compile(r"^inv_(sword|axe|mace|hammer|shield|weapon|staff|spear|throwingknife|throwingaxe|misc|jewelry|"
                            r"gizmo|potion|bandage|wand|gauntlets|glove|helmet|boots|belt|bracer)"),
                 re.compile(r"^inv_"), re.compile(r"^achievement_")]


def _era_rank(name: str) -> int:
    for i, rx in enumerate(_ERA_PRIORITY):
        if rx.match(name):
            return i
    return len(_ERA_PRIORITY)


def build_reference_list(root: Path, lists: Path) -> list[tuple[str, str]]:
    """Ordered (name, tier): Classic prior first, later-expansion talent icons, then the whole Era client."""
    prior = json.loads((root / "data" / "prior" / "classic-era" / "talents.json").read_text(encoding="utf-8"))
    tiers: list[tuple[str, list[str]]] = []
    tiers.append(("prior", sorted({t["icon"].lower() for c in prior["classes"].values() for tr in c["trees"] for t in tr["talents"]})))
    later: set[str] = set()
    for g in LATER_GAMES:
        p = lists / f"talents-{g}.js"
        if p.is_file():
            later |= {m.lower() for m in re.findall(r'"icon":"([^"]+)"', p.read_text(encoding="utf-8", errors="replace"))}
    tiers.append(("later-talents", sorted(later)))
    manifest = lists / f"mid-{ERA_BUILD}.csv"
    era = _era_icons(manifest) if manifest.is_file() else []
    tiers.append(("classic-era-client", sorted(era, key=lambda n: (_era_rank(n), n))))
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for tier, names in tiers:
        for n in names:
            if n not in seen and I.ICON_RE.match(n):
                seen.add(n)
                out.append((n, tier))
    return out


@app.command()
def refs(root: Path = ROOT_OPT,
         fetch_lists: bool = typer.Option(False, "--fetch-lists", help="download the Wowhead talent data files and the wago.tools manifest"),
         limit: int = typer.Option(0, "--limit", help="download at most N icons (0 = all)")) -> None:
    """Build work/icons/lists/reference.tsv and download the 36 px reference icons."""
    lists = WORK / "lists"
    lists.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    try:
        if fetch_lists:
            for g in LATER_GAMES:
                _get(f"https://nether.wowhead.com/{g}/data/talents-classic", lists / f"talents-{g}.js", log)
            _get(f"https://wago.tools/db2/ManifestInterfaceData/csv?build={ERA_BUILD}", lists / f"mid-{ERA_BUILD}.csv", log)
        ref_list = build_reference_list(root, lists)
        write_text_atomic(lists / "reference.tsv", "".join(f"{n}\t{t}\n" for n, t in ref_list))
        typer.echo(f"reference list: {len(ref_list)} icons ({', '.join(f'{t}={sum(1 for _, x in ref_list if x == t)}' for t in dict.fromkeys(x for _, x in ref_list))})")
        names = [n for n, _ in ref_list][: limit or None]
        ok, miss = _download_icons(names, "medium", WORK / "ref", log)
        typer.echo(f"downloaded {ok}, missing {miss}, present {sum(1 for _ in (WORK / 'ref').glob('*.jpg'))}")
    except Stop as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=3)
    finally:
        if log:
            with (lists / "fetch.log").open("a", encoding="utf-8") as f:
                f.write("\n".join(log) + "\n")


# ----------------------------------------------------------------------------- matching

def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _matches_path(root: Path) -> Path:
    return root / "data" / "icons" / "matches.json"


def _load_matches(root: Path) -> dict:
    p = _matches_path(root)
    return _load_json(p) if p.is_file() else {"classes": {}}


def _sheet(rows: list[tuple[Image.Image, Image.Image | None, str]], dest: Path) -> None:
    """Contact sheet: crop | matched icon | label, one talent per row, 4 talents per line."""
    z, per_line, lh = 2, 4, 36 * 2 + 24
    colw = 36 * z * 2 + 8 + 200
    lines = (len(rows) + per_line - 1) // per_line
    img = Image.new("RGB", (colw * per_line, max(1, lines) * lh), (32, 32, 32))
    d = ImageDraw.Draw(img)
    for i, (crop, icon, label) in enumerate(rows):
        x, y = (i % per_line) * colw, (i // per_line) * lh
        img.paste(crop.convert("RGB").resize((36 * z, 36 * z), Image.NEAREST), (x, y))
        if icon is not None:
            img.paste(icon.convert("RGB").resize((36 * z, 36 * z), Image.NEAREST), (x + 36 * z + 4, y))
        for j, part in enumerate(label.split("\n")[:5]):
            d.text((x + 36 * z * 2 + 12, y + 2 + j * 13), part, fill=(230, 230, 230))
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)


def _match_class(cls: str, root: Path, ref: I.Reference, prior_doc: dict, th: I.Thresholds, source: str,
                 verified: dict, sheet: bool) -> tuple[dict, dict]:
    doc = _load_json(root / "data" / source / f"{cls}.json")
    hints = I.prior_icons(prior_doc, cls)
    out: dict[str, dict] = {}
    stats = {"talents": 0, "matched": 0, "classic-prior": 0, "visual": 0, "unmatched": 0, "available": 0, "retracted": 0,
             "prior-disagrees": 0, "tiers": {}, "confidence": {}}
    rows: list[tuple[Image.Image, Image.Image | None, str]] = []
    for tree in doc["trees"]:
        for t in tree["talents"]:
            key = f"{tree['id']}/{t['id']}"
            crop_rel = t.get("iconCrop") or (t.get("source") or {}).get("crop")
            crop_path = root / crop_rel if crop_rel else None
            if not crop_path or not crop_path.is_file():
                out[key] = {"icon": None, "reason": "no crop", "candidate": {"tree": tree["name"], "row": t["row"], "col": t["col"]}}
                continue
            img = Image.open(crop_path)
            img.load()
            if img.size != (36, 36):
                out[key] = {"icon": None, "reason": f"crop is {img.size[0]}x{img.size[1]}, not an icon crop",
                            "candidate": {"tree": tree["name"], "row": t["row"], "col": t["col"]}}
                stats["talents"] += 1
                stats["unmatched"] += 1
                continue
            stats["talents"] += 1
            hint = hints.get(t["name"].strip().lower())
            m, sc = I.match_crop(img, ref, hint, th)
            top = [{"icon": ref.names[i], "score": round(float(sc.scores[i]), 3), "phash": sc.phash.get(i)} for i in sc.top(3)]
            rec: dict = {"icon": None, "candidate": {"tree": tree["name"], "row": t["row"], "col": t["col"]},
                         "iconCrop": crop_rel, "available": sc.available, "top": top}
            if hint:
                rec["priorIcon"] = hint
                if hint not in ref.names:
                    rec["priorNote"] = "prior icon not in reference set"
            if sc.available:
                stats["available"] += 1
            verdict = (verified.get(cls) or {}).get(key)
            if isinstance(verdict, str):
                # hand-picked icon name: overrides whatever the matcher says
                i = ref.index(verdict)
                m = {"icon": verdict, "score": round(float(sc.scores[i]), 3) if i is not None else None, "margin": None,
                     "phash": sc.phash.get(i) if i is not None else None, "rank": None, "method": "manual",
                     "confidence": "high", "tier": ref.tiers.get(verdict, "unknown")}
                verdict = True
            elif verdict is True and m is None and top:
                # human confirmed the best candidate of an otherwise rejected talent
                i = sc.top(1)[0]
                m = {"icon": ref.names[i], "score": top[0]["score"], "margin": None, "phash": top[0]["phash"], "rank": 0,
                     "method": "manual", "confidence": "high", "tier": ref.tiers.get(ref.names[i], "unknown")}
            if m is not None:
                if verdict is False:
                    rec["verified"] = False
                    rec["rejected"] = m
                    stats["retracted"] += 1
                else:
                    rec.update(m)
                    rec["verified"] = bool(verdict)
                    stats["matched"] += 1
                    stats[m["method"]] = stats.get(m["method"], 0) + 1
                    stats["confidence"][m["confidence"]] = stats["confidence"].get(m["confidence"], 0) + 1
                    stats["tiers"][m["tier"]] = stats["tiers"].get(m["tier"], 0) + 1
                    if hint and m["icon"] != hint:
                        stats["prior-disagrees"] += 1
                        rec["priorNote"] = "visual match differs from the Classic prior icon"
            if rec["icon"] is None:
                stats["unmatched"] += 1
            out[key] = rec
            if sheet:
                icon_img = Image.open(WORK / "ref" / f"{rec['icon']}.jpg") if rec["icon"] else None
                label = f"{key}\n{rec['icon'] or '-- keep crop --'}\n" + \
                        (f"{rec['method']} {rec['score']} m{rec['margin']} ph{rec['phash']}\n" if rec["icon"] else f"best {top[0]['icon']} {top[0]['score']}\n" if top else "") + \
                        (f"prior {hint}" if hint else "")
                rows.append((img, icon_img, label))
    if sheet and rows:
        _sheet(rows, WORK / "sheets" / f"{cls}.png")
    return out, stats


@app.command()
def match(cls: str = typer.Argument(..., help="class id or 'all'"), root: Path = ROOT_OPT,
          source: str = typer.Option("extracted", "--from", help="'extracted' (data/extracted/<class>.json) or 'talents'"),
          sheet: bool = typer.Option(False, "--sheet", help="write work/icons/sheets/<class>.png (crop | icon | scores)"),
          accept_score: float = typer.Option(I.Thresholds.accept_score, "--accept-score"),
          accept_margin: float = typer.Option(I.Thresholds.accept_margin, "--accept-margin"),
          prior_score: float = typer.Option(I.Thresholds.prior_score, "--prior-score"),
          phash_max: int = typer.Option(I.Thresholds.phash_max, "--phash-max"),
          dry_run: bool = typer.Option(False, "--dry-run", help="print statistics, write nothing")) -> None:
    """Match every icon crop against work/icons/ref and write data/icons/matches.json."""
    th = I.Thresholds(accept_score=accept_score, accept_margin=accept_margin, prior_score=prior_score, phash_max=phash_max)
    lists = WORK / "lists" / "reference.tsv"
    tiers = I.load_list(lists) if lists.is_file() else {}
    ref = I.load_reference(WORK / "ref", tiers)
    if len(ref) == 0:
        typer.echo(f"no reference icons under {WORK / 'ref'}; run `refs` first", err=True)
        raise typer.Exit(code=2)
    prior_doc = _load_json(root / "data" / "prior" / "classic-era" / "talents.json")
    vpath = root / "data" / "icons" / "verified.json"
    verified = _load_json(vpath) if vpath.is_file() else {}
    matches = _load_matches(root)
    matches.setdefault("classes", {})
    classes = CLASSES if cls == "all" else [cls]
    totals = {"talents": 0, "matched": 0, "unmatched": 0}
    for c in classes:
        if not (root / "data" / source / f"{c}.json").is_file():
            typer.echo(f"{c}: no data/{source}/{c}.json, skipped")
            continue
        out, stats = _match_class(c, root, ref, prior_doc, th, source, verified, sheet)
        matches["classes"][c] = out
        matches.setdefault("stats", {})[c] = stats
        for k in totals:
            totals[k] += stats[k]
        typer.echo(f"{c}: {stats['matched']}/{stats['talents']} matched (prior {stats['classic-prior']}, visual {stats['visual']}, "
                   f"available cells {stats['available']}, prior disagrees {stats['prior-disagrees']}, retracted {stats['retracted']}) "
                   f"confidence {stats['confidence']} tiers {stats['tiers']}")
    matches["generatedAt"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    matches["reference"] = {"icons": len(ref), "tiers": {t: sum(1 for n in ref.names if ref.tiers.get(n) == t) for t in sorted(set(ref.tiers.values()))},
                            "source": "Wowhead CDN medium (36 px); list: Classic prior + Wowhead TBC/Wrath/Cata/MoP talent data + Classic Era ManifestInterfaceData (wago.tools)"}
    matches["thresholds"] = th.__dict__
    matches["method"] = "NCC of normalised 24x24 luminance (crop inset 4/5, rank-digit corner masked), pHash re-rank, Classic-prior name hint"
    typer.echo(f"total: {totals['matched']}/{totals['talents']} matched, {totals['unmatched']} keep crop")
    if dry_run:
        return
    dest = _matches_path(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(dest, I.dumps(matches))
    typer.echo(f"wrote {dest}")


# ----------------------------------------------------------------------------- fetch + apply

CONFIDENCE_ORDER = {"medium": 0, "high": 1}


def _accepted(matches: dict, classes: list[str], min_confidence: str = "high") -> dict[str, dict[str, dict]]:
    floor = CONFIDENCE_ORDER.get(min_confidence, 0)
    return {c: {k: m for k, m in (matches.get("classes", {}).get(c) or {}).items()
                if m.get("icon") and (m.get("verified") is True or CONFIDENCE_ORDER.get(m.get("confidence", "medium"), 0) >= floor)}
            for c in classes}


MINCONF_OPT = typer.Option("high", "--min-confidence", help="'high' (default; verified matches always count) or 'medium' (every accepted match)")


@app.command()
def fetch(root: Path = ROOT_OPT,
          size: str = typer.Option("large", "--size", help="Wowhead size: large = 56 px, medium = 36 px"),
          min_confidence: str = MINCONF_OPT) -> None:
    """Download the icon of every accepted match into web/public/icons/<name>.jpg (skips existing files)."""
    names = sorted({m["icon"] for per in _accepted(_load_matches(root), CLASSES, min_confidence).values() for m in per.values()})
    dest = root / "web" / "public" / "icons"
    dest.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    try:
        ok, miss = _download_icons(names, size, dest, log)
    except Stop as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=3)
    for line in log:
        typer.echo(line)
    typer.echo(f"{len(names)} icons referenced, downloaded {ok}, missing {miss} -> {dest}")


@app.command()
def apply(cls: str = typer.Argument(..., help="class id or 'all'"), root: Path = ROOT_OPT,
          min_confidence: str = MINCONF_OPT,
          dry_run: bool = typer.Option(False, "--dry-run", help="report, write nothing")) -> None:
    """Write icon / icon_source / icon_match into data/extracted/<class>.candidates.json from matches.json."""
    matches = _load_matches(root)
    classes = CLASSES if cls == "all" else [cls]
    for c in classes:
        path = root / "data" / "extracted" / f"{c}.candidates.json"
        per = _accepted(matches, [c], min_confidence)[c]
        if not path.is_file():
            typer.echo(f"{c}: no candidates file, skipped")
            continue
        if c not in matches.get("classes", {}):
            typer.echo(f"{c}: not in matches.json, skipped")
            continue
        doc = _load_json(path)
        records = doc["candidates"] if isinstance(doc, dict) else doc
        n, missing = I.apply_matches(records, per)
        for k in missing:
            typer.echo(f"  {c}/{k}: no candidate record for cell {per[k]['candidate']}")
        typer.echo(f"{c}: {len(per)} icons, {n} records {'would change' if dry_run else 'changed'}")
        if not dry_run and n:
            write_candidates_atomic(path, doc, before=len(records))
    if not dry_run:
        typer.echo("now re-run: uv run stages/08_export.py extract <class> && uv run stages/08_export.py promote <class>")


if __name__ == "__main__":
    app()

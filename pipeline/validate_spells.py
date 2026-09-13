#!/usr/bin/env python3
"""Validate WoW Forever spellbook files against data/schema/spell.schema.json.

The third validator next to ``validate.py`` (talents) and ``validate_races.py``
(races), same shape as the latter: rules S1-S12 are errors, S13-S18 warnings
(``--strict`` makes warnings errors), and ``canonical_dumps`` is the one
serializer stage 11 writes through, so ``--check`` compares bytes.

    cd pipeline && uv run python validate_spells.py ../data/spells/*.json
    uv run python validate_spells.py --check ../data/spells/*.json      # CI
    uv run python validate_spells.py --report ../data/spells/*.json     # review queue

Exit code 1 on any error, 0 otherwise. Options mirror validate_races.py:
``--strict``, ``--json``, ``--report``, ``--check``, ``--no-files``, ``--root DIR``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import _dump  # noqa: E402  (the one serializer)

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    sys.stderr.write("validate_spells.py needs the 'jsonschema' package (uv run / uvx --with jsonschema)\n")
    raise

SCHEMA_VERSION = 1
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
REVIEW_THRESHOLD = 0.8
CLASSES = {"druid", "hunter", "mage", "paladin", "priest", "rogue", "shaman", "warlock", "warrior"}
#: The most entries one spellbook page can hold: three columns of seven rows.
PAGE_CAPACITY = 21

KEY_ORDER = {
    "top": ["$schema", "schemaVersion", "class", "className", "dataSource", "generatedAt",
            "observedLevel", "tabs", "spells", "coverage", "complete", "notes"],
    "tab": ["id", "name", "order", "tree"],
    "spell": ["id", "name", "kind", "tab", "ranksSeen", "icon", "iconSource", "iconCrop",
              "tooltips", "classic", "tags", "source"],
    "tooltip": ["rank", "cost", "range", "castTime", "cooldown", "tools", "requires",
                "description", "footer", "source"],
    "classic": ["status", "classicName", "classicText", "note"],
    "source": ["kind", "video", "t", "frame", "crop", "panel", "confidence", "reader", "readings",
               "build", "reviewed", "reviewedBy", "reviewedAt", "note"],
    "reading": ["reader", "name", "rank", "description", "confidence"],
    "coverage": ["pagesSeen", "tabsSeen", "tabsMissing", "states", "entriesRead", "tooltipsRead",
                 "tooltipsUnmatched", "showAllSpellRanks", "observedLevel", "windows"],
}


# ----------------------------------------------------------------------------
# Findings
# ----------------------------------------------------------------------------

@dataclass
class Finding:
    level: str
    code: str
    where: str
    message: str

    def line(self, path: str) -> str:
        return f"{self.level} {self.code} {path}:{self.where}: {self.message}"

    def to_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "where": self.where, "message": self.message}


@dataclass
class FileResult:
    path: Path
    findings: list[Finding] = field(default_factory=list)
    queue: list[dict] = field(default_factory=list)

    def count(self, level: str) -> int:
        return sum(1 for f in self.findings if f.level == level)

    def to_dict(self) -> dict:
        return {"file": str(self.path), "findings": [f.to_dict() for f in self.findings], "queue": self.queue}


@dataclass
class Ctx:
    result: FileResult
    root: Path | None
    strict: bool = False
    no_files: bool = False

    def err(self, code: str, where: str, msg: str) -> None:
        self.result.findings.append(Finding("ERROR", code, where, msg))

    def warn(self, code: str, where: str, msg: str) -> None:
        level = "ERROR" if self.strict else "WARN"
        self.result.findings.append(Finding(level, code, where, msg))


# ----------------------------------------------------------------------------
# Canonical serializer (rule S12)
# ----------------------------------------------------------------------------

def _order(obj: dict, keys: list[str]) -> dict:
    out = {k: obj[k] for k in keys if k in obj}
    for k in obj:
        if k not in out:
            out[k] = obj[k]
    return out


def order_spell_doc(doc: dict) -> dict:
    """Key order of the schema, spells sorted by (tab, id) and tabs by ``order``."""
    doc = _order(doc, KEY_ORDER["top"])
    if isinstance(doc.get("coverage"), dict):
        doc["coverage"] = _order(doc["coverage"], KEY_ORDER["coverage"])
    if isinstance(doc.get("tabs"), list):
        doc["tabs"] = sorted((_order(t, KEY_ORDER["tab"]) if isinstance(t, dict) else t
                              for t in doc["tabs"]),
                             key=lambda t: (t.get("order", 10 ** 6), t.get("id", "")))
    spells = []
    for s in doc.get("spells") or []:
        if not isinstance(s, dict):
            spells.append(s)
            continue
        s = _order(s, KEY_ORDER["spell"])
        if isinstance(s.get("classic"), dict):
            s["classic"] = _order(s["classic"], KEY_ORDER["classic"])
        if isinstance(s.get("source"), dict):
            s["source"] = _order_source(s["source"])
        tips = []
        for t in s.get("tooltips") or []:
            if isinstance(t, dict):
                t = _order(t, KEY_ORDER["tooltip"])
                if isinstance(t.get("source"), dict):
                    t["source"] = _order_source(t["source"])
            tips.append(t)
        if "tooltips" in s:
            s["tooltips"] = sorted(tips, key=lambda t: (t.get("rank") or 0, t.get("description", "")))
        spells.append(s)
    if "spells" in doc:
        try:
            spells = sorted(spells, key=lambda s: (s.get("tab") or "~", s.get("id", ""),
                                                   min(s.get("ranksSeen") or [0])))
        except TypeError:
            pass
        doc["spells"] = spells
    return doc


def _order_source(src: dict) -> dict:
    src = _order(src, KEY_ORDER["source"])
    if isinstance(src.get("readings"), list):
        src["readings"] = [_order(r, KEY_ORDER["reading"]) if isinstance(r, dict) else r
                           for r in src["readings"]]
    return src


def canonical_dumps(doc: dict) -> str:
    return _dump(order_spell_doc(doc), 0) + "\n"


# ----------------------------------------------------------------------------
# Rules
# ----------------------------------------------------------------------------

def rule_1_schema(ctx: Ctx, doc: Any, schema: dict) -> bool:
    if not isinstance(doc, dict):
        ctx.err("NOT-AN-OBJECT", "/", "top level is not a JSON object")
        return False
    ok = True
    for e in sorted(Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.absolute_path)):
        where = "/" + "/".join(str(p) for p in e.absolute_path)
        ctx.err("SCHEMA", where, e.message)
        ok = False
    if doc.get("schemaVersion") != SCHEMA_VERSION:
        ctx.err("SCHEMA-VERSION", "/schemaVersion", f"expected {SCHEMA_VERSION}, found {doc.get('schemaVersion')!r}")
        ok = False
    return ok


def rule_2_ids(ctx: Ctx, doc: dict, path: Path) -> None:
    if doc.get("class") != path.stem:
        ctx.err("CLASS-FILENAME", "/class", f"class {doc.get('class')!r} does not match the file name {path.stem!r}")
    for i, s in enumerate(doc.get("spells") or []):
        if not SLUG_RE.match(s.get("id") or ""):
            ctx.err("BAD-ID", f"/spells/{i}", f"{s.get('id')!r} is not a slug")


def rule_3_spells_unique(ctx: Ctx, doc: dict) -> None:
    """One record per (spell, rank): the same spell may appear once per rank, never twice per rank."""
    seen: dict[tuple, int] = {}
    for i, s in enumerate(doc.get("spells") or []):
        ranks = tuple(sorted(s.get("ranksSeen") or []))
        key = (s.get("id"), ranks)
        if key in seen:
            ctx.err("DUPLICATE-SPELL", f"/spells/{i}",
                    f"{s.get('id')!r} with ranks {list(ranks)} also appears at index {seen[key]}")
        seen[key] = i


def rule_4_tabs(ctx: Ctx, doc: dict) -> None:
    ids = {t.get("id") for t in doc.get("tabs") or []}
    orders = [t.get("order") for t in doc.get("tabs") or []]
    if sorted(orders) != list(range(len(orders))):
        ctx.err("TAB-ORDER", "/tabs", f"orders {orders} are not 0..{len(orders) - 1}")
    for i, s in enumerate(doc.get("spells") or []):
        tab = s.get("tab")
        if tab is not None and tab not in ids:
            ctx.err("UNKNOWN-TAB", f"/spells/{i}", f"tab {tab!r} is not one of {sorted(ids)}")
        if tab is None and not (s.get("source") or {}).get("note"):
            ctx.err("NO-TAB-NOTE", f"/spells/{i}",
                    "a spell without a tab was read from a search page; source.note must say so")


def rule_5_coverage(ctx: Ctx, doc: dict) -> None:
    cov = doc.get("coverage") or {}
    tabs = {t.get("id") for t in doc.get("tabs") or []}
    if set(cov.get("tabsSeen") or []) != tabs:
        ctx.err("COVERAGE-TABS", "/coverage/tabsSeen",
                f"tabsSeen {sorted(cov.get('tabsSeen') or [])} does not equal the tabs {sorted(tabs)}")
    if set(cov.get("tabsSeen") or []) & set(cov.get("tabsMissing") or []):
        ctx.err("COVERAGE-TABS", "/coverage/tabsMissing", "a tab is both seen and missing")
    if cov.get("entriesRead") != len(doc.get("spells") or []):
        ctx.err("COVERAGE-COUNT", "/coverage/entriesRead",
                f"entriesRead {cov.get('entriesRead')} != {len(doc.get('spells') or [])} spells")
    tips = sum(len(s.get("tooltips") or []) for s in doc.get("spells") or [])
    if cov.get("tooltipsRead") != tips:
        ctx.err("COVERAGE-COUNT", "/coverage/tooltipsRead",
                f"tooltipsRead {cov.get('tooltipsRead')} != {tips} tooltips")
    if cov.get("observedLevel") != doc.get("observedLevel"):
        ctx.err("COVERAGE-LEVEL", "/coverage/observedLevel", "differs from the top-level observedLevel")
    for key in ("tabsSeen", "tabsMissing"):
        v = cov.get(key) or []
        if sorted(v) != list(v):
            ctx.err("COVERAGE-UNSORTED", f"/coverage/{key}", "must be sorted")


def rule_6_ranks(ctx: Ctx, doc: dict) -> None:
    for i, s in enumerate(doc.get("spells") or []):
        ranks = s.get("ranksSeen")
        if ranks is None:
            continue
        if sorted(ranks) != list(ranks):
            ctx.err("RANKS-UNSORTED", f"/spells/{i}/ranksSeen", "must be sorted")
        if s.get("kind") in {"passive", "racial-passive"}:
            ctx.warn("RANK-ON-PASSIVE", f"/spells/{i}",
                     f"{s.get('id')!r} is {s['kind']} but carries a rank")
    on = (doc.get("coverage") or {}).get("showAllSpellRanks")
    multi = any(len(s.get("ranksSeen") or []) > 1 for s in doc.get("spells") or [])
    by_id: dict[str, int] = {}
    for s in doc.get("spells") or []:
        by_id[s.get("id")] = by_id.get(s.get("id"), 0) + 1
    multi = multi or any(n > 1 for n in by_id.values())
    if multi and on != "on":
        ctx.err("SHOW-ALL-RANKS", "/coverage/showAllSpellRanks",
                "a spell appears at two ranks, so the option was on")
    if not multi and on == "on":
        ctx.err("SHOW-ALL-RANKS", "/coverage/showAllSpellRanks",
                "no spell appears at two ranks, so 'on' is not supported by the data")


def rule_7_classic(ctx: Ctx, doc: dict) -> None:
    for i, s in enumerate(doc.get("spells") or []):
        c = s.get("classic") or {}
        st = c.get("status")
        if st == "new" and c.get("classicName"):
            ctx.err("CLASSIC-NEW", f"/spells/{i}", "status 'new' but a Classic counterpart is named")
        if st in {"same", "changed"} and not c.get("classicName"):
            ctx.err("CLASSIC-MATCH", f"/spells/{i}", f"status {st!r} needs classicName")
        if not c.get("note"):
            ctx.err("CLASSIC-NOTE", f"/spells/{i}",
                    "every classic block needs a note; the prior is unverified and must say so")
        tags = set(s.get("tags") or [])
        if st == "new" and "new" not in tags:
            ctx.warn("TAG-MISMATCH", f"/spells/{i}", f"status 'new' but tags {sorted(tags)} lack 'new'")


def _check_source(ctx: Ctx, src: dict, where: str) -> None:
    kind = src.get("kind")
    if kind == "video":
        for f in ("video", "t", "frame", "crop", "confidence", "reader"):
            if src.get(f) is None:
                ctx.err("SOURCE-FIELDS", where, f"kind 'video' needs {f}")
    if kind == "datamined" and not src.get("build"):
        ctx.err("SOURCE-FIELDS", where, "kind 'datamined' needs build")
    if kind == "manual" and not src.get("reviewed"):
        ctx.err("SOURCE-FIELDS", where, "a manual source must be reviewed")
    if src.get("reviewed") and not (src.get("reviewedBy") and src.get("reviewedAt")):
        ctx.err("SOURCE-FIELDS", where, "reviewed needs reviewedBy and reviewedAt")
    if not src.get("reviewed") and (src.get("reviewedBy") or src.get("reviewedAt")):
        ctx.err("SOURCE-FIELDS", where, "reviewedBy/reviewedAt without reviewed")


def rule_8_sources(ctx: Ctx, doc: dict) -> None:
    for i, s in enumerate(doc.get("spells") or []):
        _check_source(ctx, s.get("source") or {}, f"/spells/{i}/source")
        if (s.get("source") or {}).get("panel") not in (None, "spell-list"):
            ctx.err("SOURCE-PANEL", f"/spells/{i}/source", "a list entry must come from panel 'spell-list'")
        for j, t in enumerate(s.get("tooltips") or []):
            _check_source(ctx, t.get("source") or {}, f"/spells/{i}/tooltips/{j}/source")
            if (t.get("source") or {}).get("panel") != "tooltip":
                ctx.err("SOURCE-PANEL", f"/spells/{i}/tooltips/{j}/source",
                        "a tooltip must come from panel 'tooltip'")


def rule_9_files(ctx: Ctx, doc: dict) -> None:
    if ctx.no_files or ctx.root is None:
        return

    def check(rel: str, where: str) -> None:
        if rel and not (ctx.root / rel).is_file():
            ctx.err("MISSING-FILE", where, f"{rel} does not exist")

    for i, s in enumerate(doc.get("spells") or []):
        check((s.get("source") or {}).get("crop") or "", f"/spells/{i}/source/crop")
        for j, t in enumerate(s.get("tooltips") or []):
            check((t.get("source") or {}).get("crop") or "", f"/spells/{i}/tooltips/{j}/source/crop")
        if s.get("iconSource") == "crop":
            if not s.get("iconCrop"):
                ctx.err("ICON-CROP", f"/spells/{i}", "iconSource 'crop' needs iconCrop")
            else:
                check(s["iconCrop"], f"/spells/{i}/iconCrop")
        elif s.get("iconCrop"):
            ctx.err("ICON-CROP", f"/spells/{i}", "iconCrop without iconSource 'crop'")
        if s.get("icon") and s.get("iconSource") == "crop" and s["icon"] != f"crop-{s.get('id')}":
            ctx.warn("ICON-NAME", f"/spells/{i}", f"crop icons are named crop-<id>, found {s['icon']!r}")


def rule_10_complete(ctx: Ctx, doc: dict) -> None:
    cov = doc.get("coverage") or {}
    if doc.get("complete") and cov.get("tabsMissing"):
        ctx.err("COMPLETE-MISSING-TABS", "/complete",
                f"complete: true with tabs never seen: {cov['tabsMissing']}")
    if not doc.get("complete") and not doc.get("notes"):
        ctx.err("INCOMPLETE-UNEXPLAINED", "/notes", "complete: false needs a note saying what is missing")


def rule_11_tooltips(ctx: Ctx, doc: dict) -> None:
    for i, s in enumerate(doc.get("spells") or []):
        for j, t in enumerate(s.get("tooltips") or []):
            d = t.get("description") or ""
            if d != d.strip() or "  " in d:
                ctx.warn("TEXT-HYGIENE", f"/spells/{i}/tooltips/{j}",
                         "leading, trailing or double whitespace in the description")
            if re.search(r"[|\\~]", d):
                ctx.warn("TEXT-HYGIENE", f"/spells/{i}/tooltips/{j}", "OCR artefact character in the description")
            rank = t.get("rank")
            if rank is not None and s.get("ranksSeen") and rank not in s["ranksSeen"]:
                ctx.err("TOOLTIP-RANK", f"/spells/{i}/tooltips/{j}",
                        f"rank {rank} is not among ranksSeen {s['ranksSeen']}")


def rule_12_canonical(ctx: Ctx, doc: dict, raw: bytes, check: bool) -> None:
    canon = canonical_dumps(doc).encode("utf-8")
    if canon == raw:
        return
    msg = "file is not byte-identical to the canonical serializer output (re-run stage 11 build)"
    (ctx.err if check else ctx.warn)("NOT-CANONICAL", "/", msg)


def rule_13_confidence(ctx: Ctx, doc: dict) -> None:
    for i, s in enumerate(doc.get("spells") or []):
        src = s.get("source") or {}
        conf = src.get("confidence")
        if conf is not None and conf < REVIEW_THRESHOLD and not src.get("reviewed"):
            ctx.warn("NEEDS-REVIEW", f"/spells/{i}", f"confidence {conf} below {REVIEW_THRESHOLD}")
        if not src.get("reviewed"):
            ctx.result.queue.append({"spell": s.get("id"), "name": s.get("name"),
                                     "confidence": conf, "crop": src.get("crop"),
                                     "status": (s.get("classic") or {}).get("status")})


def rule_14_kind(ctx: Ctx, doc: dict) -> None:
    for i, s in enumerate(doc.get("spells") or []):
        if re.search(r"\brank\s*\d", (s.get("name") or ""), re.I):
            ctx.warn("RANK-IN-NAME", f"/spells/{i}", "the 'Rank N' subtitle belongs in ranksSeen, not in name")


def rule_15_counts(ctx: Ctx, doc: dict) -> None:
    """One page holds 21 entries; a tab with more of them was read across several pages."""
    per_tab: dict[str, int] = {}
    for s in doc.get("spells") or []:
        if s.get("tab"):
            per_tab[s["tab"]] = per_tab.get(s["tab"], 0) + 1
    for tab, n in sorted(per_tab.items()):
        if n > PAGE_CAPACITY:
            ctx.warn("TAB-OVER-CAPACITY", "/spells",
                     f"tab {tab!r} has {n} entries, more than the {PAGE_CAPACITY} one page holds; "
                     "check that the extra ones really came from a second page")


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------

def find_root(start: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).resolve()
    cur = start.resolve()
    for p in [cur, *cur.parents]:
        if (p / "data" / "schema" / "spell.schema.json").is_file():
            return p
    return None


def validate_path(path: Path, opts: argparse.Namespace, cache: dict[Path, dict]) -> FileResult:
    result = FileResult(path)
    root = find_root(path.parent, opts.root)
    ctx = Ctx(result, root, strict=opts.strict, no_files=opts.no_files)
    try:
        raw = path.read_bytes()
        doc = json.loads(raw)
    except FileNotFoundError:
        ctx.err("NO-FILE", "/", "file does not exist")
        return result
    except json.JSONDecodeError as e:
        ctx.err("BAD-JSON", "/", str(e))
        return result
    if root is None:
        ctx.err("NO-ROOT", "/", "cannot find the repository root (data/schema/spell.schema.json)")
        return result
    spath = root / "data" / "schema" / "spell.schema.json"
    if spath not in cache:
        cache[spath] = json.loads(spath.read_text(encoding="utf-8"))
    if not rule_1_schema(ctx, doc, cache[spath]):
        return result
    rule_2_ids(ctx, doc, path)
    rule_3_spells_unique(ctx, doc)
    rule_4_tabs(ctx, doc)
    rule_5_coverage(ctx, doc)
    rule_6_ranks(ctx, doc)
    rule_7_classic(ctx, doc)
    rule_8_sources(ctx, doc)
    rule_9_files(ctx, doc)
    rule_10_complete(ctx, doc)
    rule_11_tooltips(ctx, doc)
    rule_12_canonical(ctx, doc, raw, opts.check)
    rule_13_confidence(ctx, doc)
    rule_14_kind(ctx, doc)
    rule_15_counts(ctx, doc)
    return result


def print_text(results: list[FileResult], opts: argparse.Namespace) -> None:
    for r in results:
        rel = str(r.path)
        for f in r.findings:
            print(f.line(rel))
        if opts.report and r.queue:
            print(f"-- review queue {rel}: {len(r.queue)} unreviewed")
            for q in sorted(r.queue, key=lambda q: (q["confidence"] is None, q["confidence"])):
                print(f"   {q['confidence']}  {q['spell']:28} {q['status']:8} {q['crop']}")
    errors = sum(r.count("ERROR") for r in results)
    warns = sum(r.count("WARN") for r in results)
    print(f"{len(results)} file(s): {errors} error(s), {warns} warning(s)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="spell files (data/spells/*.json)")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--report", action="store_true", help="print the review queue")
    ap.add_argument("--check", action="store_true", help="fail unless the file is the canonical serializer output")
    ap.add_argument("--no-files", action="store_true", help="skip crop existence checks (rule S9)")
    ap.add_argument("--root", help="repository root (default: auto-detect)")
    opts = ap.parse_args(argv)

    cache: dict[Path, dict] = {}
    results = [validate_path(Path(f), opts, cache) for f in opts.files]
    errors = sum(r.count("ERROR") for r in results)
    if opts.json:
        print(json.dumps({"ok": errors == 0, "files": [r.to_dict() for r in results]}, indent=2, ensure_ascii=False))
    else:
        print_text(results, opts)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

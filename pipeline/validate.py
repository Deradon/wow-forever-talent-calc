#!/usr/bin/env python3
"""Validate WoW Forever talent class files against docs/DATA-SCHEMA.md.

Standalone: needs only the standard library plus ``jsonschema`` (``rapidfuzz``
is used for rule 15 when importable, otherwise a difflib fallback).

    cd pipeline && uv run python validate.py ../data/talents/*.json
    uvx --with jsonschema python pipeline/validate.py data/examples/tinker.json

Rules 1-19 follow section 10 of docs/DATA-SCHEMA.md: rules 1-12 are errors,
13-19 warnings (``--strict`` makes warnings errors). Exit code 1 on any
error, 0 otherwise.

Options:
    --strict      warnings count as errors
    --json        machine-readable output (used by the review UI)
    --report      also print the review queue (section 7 step 2)
    --overrides   the given files are data/overrides/<class>.json files
    --check       rule 12: file must equal the canonical serializer output
    --no-files    skip file-existence checks (rule 9)
    --root DIR    repo root (default: found by walking up from each file
                  until data/schema/class.schema.json exists)

This module also owns the canonical serializer (``canonical_dumps``) that
export.py and the review UI must use, so ``--check`` can compare bytes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover
    sys.stderr.write("validate.py needs the 'jsonschema' package (uv run / uvx --with jsonschema)\n")
    raise

try:  # optional, better rule-15 matching
    from rapidfuzz import fuzz as _rf_fuzz  # type: ignore
except Exception:  # pragma: no cover
    _rf_fuzz = None

SCHEMA_VERSION = 1
KNOWN_CLASSES = {"druid", "hunter", "mage", "paladin", "priest", "rogue", "shaman", "warlock", "warrior"}
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PLACEHOLDER_RE = re.compile(r"\{(\d+)\}")
RFC3339_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
REVIEW_THRESHOLD = 0.8
NAME_MATCH_THRESHOLD = 90

# Key order per docs/DATA-SCHEMA.md section 4 (canonical serializer).
KEY_ORDER = {
    "top": ["$schema", "schemaVersion", "class", "className", "dataVersion", "dataSource",
            "generatedAt", "rules", "pages", "trees", "notes"],
    "rules": ["pointsPerRow", "maxPoints", "firstPointLevel", "maxLevel", "pointsPerPage", "rulesSource"],
    "page": ["id", "name", "note"],
    "tree": ["id", "name", "page", "order", "icon", "background", "rows", "cols", "role",
             "datamined", "source", "talents"],
    "datamined": ["talentTabId", "build"],
    "talent": ["id", "name", "row", "col", "maxRank", "icon", "iconSource", "iconCrop", "description",
               "ranks", "ranksObserved", "ranksSource", "ranksPrior", "ranksNote", "requires",
               "capstone", "spellIds", "tags", "source"],
    "requirement": ["talent", "rank"],
    "ranksPrior": ["classicTalentId", "classicSpellIds", "match", "similarity"],
    "source": ["kind", "video", "t", "frame", "crop", "confidence", "reader", "readings", "build",
               "talentId", "reviewed", "reviewedBy", "reviewedAt", "note"],
    "reading": ["reader", "name", "description", "maxRank", "confidence"],
    "override": ["talent", "tree", "set", "unset", "rename", "delete", "add", "reason", "by", "at"],
    "overridesTop": ["$schema", "schemaVersion", "class", "overrides"],
}

# Fields an override may delete (DATA-SCHEMA.md section 6.2, "Deleting a field").
# Required fields are absent by construction: dropping one would make the record invalid.
UNSETTABLE = {"requires", "ranksNote", "ranksPrior", "capstone", "tags", "spellIds", "iconCrop",
              "source.note", "source.readings"}


# ----------------------------------------------------------------------------
# Findings
# ----------------------------------------------------------------------------

@dataclass
class Finding:
    level: str  # ERROR | WARNING | INFO
    code: str   # e.g. R05-CELL, NEEDS-REVIEW
    path: str   # class/tree/talent (as far as known)
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FileResult:
    file: str
    findings: list[Finding] = field(default_factory=list)
    review_queue: list[dict] = field(default_factory=list)

    def count(self, level: str) -> int:
        return sum(1 for f in self.findings if f.level == level)

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "errors": self.count("ERROR"),
            "warnings": self.count("WARNING"),
            "info": self.count("INFO"),
            "findings": [f.to_dict() for f in self.findings],
            "reviewQueue": self.review_queue,
        }


class Ctx:
    """Per-file validation context."""

    def __init__(self, path: Path, root: Path, opts: argparse.Namespace, schema: dict, prior: "Prior | None"):
        self.path = path
        self.root = root
        self.opts = opts
        self.schema = schema
        self.prior = prior
        self.result = FileResult(file=str(path))
        self.stem = path.stem

    def add(self, level: str, code: str, path: str, message: str) -> None:
        self.result.findings.append(Finding(level, code, path, message))

    def error(self, code: str, path: str, message: str) -> None:
        self.add("ERROR", code, path, message)

    def warn(self, code: str, path: str, message: str) -> None:
        self.add("WARNING", code, path, message)

    def info(self, code: str, path: str, message: str) -> None:
        self.add("INFO", code, path, message)


# ----------------------------------------------------------------------------
# Canonical serializer (section 2: one serializer for export.py and review UI)
# ----------------------------------------------------------------------------

def _order(obj: dict, keys: list[str]) -> dict:
    out = {k: obj[k] for k in keys if k in obj}
    for k in obj:  # unknown keys keep their position at the end (schema rejects them anyway)
        if k not in out:
            out[k] = obj[k]
    return out


def order_source(src: dict) -> dict:
    src = _order(src, KEY_ORDER["source"])
    if isinstance(src.get("readings"), list):
        src["readings"] = [_order(r, KEY_ORDER["reading"]) if isinstance(r, dict) else r for r in src["readings"]]
    return src


def order_talent(t: dict) -> dict:
    t = _order(t, KEY_ORDER["talent"])
    if isinstance(t.get("ranksPrior"), dict):
        t["ranksPrior"] = _order(t["ranksPrior"], KEY_ORDER["ranksPrior"])
    if isinstance(t.get("requires"), list):
        t["requires"] = [_order(r, KEY_ORDER["requirement"]) if isinstance(r, dict) else r for r in t["requires"]]
    if isinstance(t.get("source"), dict):
        t["source"] = order_source(t["source"])
    return t


def order_class_doc(doc: dict) -> dict:
    """Return a copy of a class document with keys in schema order and talents sorted by (row, col)."""
    doc = _order(doc, KEY_ORDER["top"])
    if isinstance(doc.get("rules"), dict):
        doc["rules"] = _order(doc["rules"], KEY_ORDER["rules"])
    if isinstance(doc.get("pages"), list):
        doc["pages"] = [_order(p, KEY_ORDER["page"]) if isinstance(p, dict) else p for p in doc["pages"]]
    trees = []
    for tree in doc.get("trees", []) or []:
        if not isinstance(tree, dict):
            trees.append(tree)
            continue
        tree = _order(tree, KEY_ORDER["tree"])
        if isinstance(tree.get("datamined"), dict):
            tree["datamined"] = _order(tree["datamined"], KEY_ORDER["datamined"])
        if isinstance(tree.get("source"), dict):
            tree["source"] = order_source(tree["source"])
        talents = tree.get("talents")
        if isinstance(talents, list) and all(isinstance(t, dict) for t in talents):
            talents = [order_talent(t) for t in talents]
            try:
                talents = sorted(talents, key=lambda t: (t.get("row", 0), t.get("col", 0)))
            except TypeError:
                pass
            tree["talents"] = talents
        trees.append(tree)
    if "trees" in doc:
        doc["trees"] = trees
    return doc


def order_overrides_doc(doc: dict) -> dict:
    doc = _order(doc, KEY_ORDER["overridesTop"])
    if isinstance(doc.get("overrides"), list):
        out = []
        for o in doc["overrides"]:
            if isinstance(o, dict):
                o = _order(o, KEY_ORDER["override"])
                if isinstance(o.get("set"), dict):
                    o["set"] = order_talent(o["set"])
                if isinstance(o.get("add"), dict):
                    o["add"] = order_talent(o["add"])
            out.append(o)
        doc["overrides"] = out
    return doc


_INLINE_MAX = 100


def _dump(v: Any, ind: int) -> str:
    pad = " " * ind
    if isinstance(v, dict):
        if not v:
            return "{}"
        items = [f'{pad}  {json.dumps(k, ensure_ascii=False)}: {_dump(x, ind + 2)}' for k, x in v.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(v, list):
        if not v:
            return "[]"
        if not any(isinstance(x, dict) for x in v):
            inline = "[" + ", ".join(_dump(x, ind) for x in v) + "]"
            if len(inline) <= _INLINE_MAX and "\n" not in inline:
                return inline
        items = [pad + "  " + _dump(x, ind + 2) for x in v]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    return json.dumps(v, ensure_ascii=False)


def canonical_dumps(doc: dict, kind: str = "class") -> str:
    """Serialize a class (or overrides) document exactly as export.py must write it."""
    ordered = order_overrides_doc(doc) if kind == "overrides" else order_class_doc(doc)
    return _dump(ordered, 0) + "\n"


# ----------------------------------------------------------------------------
# Classic Era prior (data/prior/classic-era/talents.json), optional
# ----------------------------------------------------------------------------

class Prior:
    def __init__(self, doc: dict):
        self.by_id: dict[int, dict] = {}
        self.by_class: dict[str, list[dict]] = {}
        for cls, cdoc in (doc.get("classes") or {}).items():
            lst = self.by_class.setdefault(cls, [])
            for tree in cdoc.get("trees", []):
                for t in tree.get("talents", []):
                    rec = dict(t)
                    rec["class"] = cls
                    rec["tree"] = tree.get("id")
                    lst.append(rec)
                    if isinstance(t.get("classicTalentId"), int):
                        self.by_id[t["classicTalentId"]] = rec

    @staticmethod
    def load(root: Path) -> "Prior | None":
        p = root / "data" / "prior" / "classic-era" / "talents.json"
        if not p.is_file():
            return None
        try:
            return Prior(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None


def token_ratio(a: str, b: str) -> float:
    """rapidfuzz.fuzz.token_ratio if available, else a difflib approximation (0..100)."""
    if _rf_fuzz is not None:
        return float(_rf_fuzz.token_ratio(a, b))
    import difflib

    def norm(s: str) -> list[str]:
        return sorted(re.findall(r"[a-z0-9]+", s.lower()))

    ta, tb = norm(a), norm(b)
    if not ta or not tb:
        return 0.0
    sort_ratio = difflib.SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
    common = sorted(set(ta) & set(tb))
    da = sorted(set(ta) - set(tb))
    db = sorted(set(tb) - set(ta))
    c = " ".join(common)
    s1 = (c + " " + " ".join(da)).strip()
    s2 = (c + " " + " ".join(db)).strip()
    set_ratio = max(
        difflib.SequenceMatcher(None, c, s1).ratio() if c else 0.0,
        difflib.SequenceMatcher(None, c, s2).ratio() if c else 0.0,
        difflib.SequenceMatcher(None, s1, s2).ratio(),
    )
    return 100.0 * max(sort_ratio, set_ratio)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def find_root(start: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).resolve()
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    for candidate in [cur, *cur.parents]:
        if (candidate / "data" / "schema" / "class.schema.json").is_file():
            return candidate
    return None


def file_kind(path: Path) -> str:
    """talents | extracted | overrides | examples | other, from the parent directory name."""
    name = path.parent.name
    return name if name in {"talents", "extracted", "overrides", "examples"} else "other"


def placeholders(description: str) -> list[int]:
    return sorted({int(n) for n in PLACEHOLDER_RE.findall(description)})


def json_path(parts: Iterable[Any]) -> str:
    return "/".join(str(p) for p in parts) or "(root)"


def is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ----------------------------------------------------------------------------
# Rules 1-12 (errors)
# ----------------------------------------------------------------------------

def rule_1_schema(ctx: Ctx, doc: Any) -> bool:
    """Returns False when validation must stop (not an object / wrong schemaVersion)."""
    if not isinstance(doc, dict):
        ctx.error("R01-SCHEMA", ctx.stem, "top level is not a JSON object")
        return False
    sv = doc.get("schemaVersion")
    if sv != SCHEMA_VERSION:
        ctx.error("R01-SCHEMA-VERSION", ctx.stem, f"schemaVersion is {sv!r}, this validator handles {SCHEMA_VERSION}")
        return False
    validator = Draft202012Validator(ctx.schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    for e in errors:
        # jsonschema reports each failing branch of oneOf/if-then; keep the most specific message.
        ctx.error("R01-SCHEMA", f"{ctx.stem}:{json_path(e.absolute_path)}", _schema_msg(e))
    return not errors


def _schema_msg(e) -> str:
    msg = e.message
    if e.validator == "additionalProperties":
        return msg
    if e.validator == "oneOf" and e.context:
        # show the shortest sub-error for readability
        best = min(e.context, key=lambda c: len(c.message))
        return f"{msg.split('is not valid')[0].strip()} is neither slot array nor rank string ({best.message})"
    if msg.startswith("False schema does not allow"):
        key = list(e.absolute_path)[-1] if e.absolute_path else "?"
        return f"'{key}' is not allowed here (conditional field, see DATA-SCHEMA.md section 4.4/4.5)"
    return msg if len(msg) <= 240 else msg[:237] + "..."


def rule_2_ids(ctx: Ctx, doc: dict) -> None:
    cls = doc.get("class")
    if cls != ctx.stem:
        ctx.error("R02-CLASS-STEM", ctx.stem, f"class {cls!r} does not equal file stem {ctx.stem!r}")
    if isinstance(cls, str) and cls not in KNOWN_CLASSES:
        ctx.warn("UNKNOWN-CLASS", ctx.stem, f"class {cls!r} is not one of the known classes ({', '.join(sorted(KNOWN_CLASSES))})")

    def check_slug(v: Any, where: str) -> None:
        if not (isinstance(v, str) and SLUG_RE.match(v) and len(v) <= 64):
            ctx.error("R02-SLUG", where, f"id {v!r} does not match ^[a-z0-9]+(-[a-z0-9]+)*$ (max 64 chars)")

    check_slug(cls, ctx.stem)
    for page in doc.get("pages", []):
        check_slug(page.get("id"), f"{cls}/pages")
    for tree in doc.get("trees", []):
        tid = tree.get("id")
        check_slug(tid, f"{cls}/{tid}")
        for t in tree.get("talents", []):
            check_slug(t.get("id"), f"{cls}/{tid}/{t.get('id')}")
            for req in t.get("requires", []) or []:
                check_slug(req.get("talent"), f"{cls}/{tid}/{t.get('id')}")


def rule_3_rules(ctx: Ctx, doc: dict) -> None:
    r = doc["rules"]
    cls = doc["class"]
    if r["firstPointLevel"] - 1 + r["maxPoints"] > r["maxLevel"]:
        ctx.error("R03-RULES", f"{cls}/rules",
                  f"firstPointLevel - 1 + maxPoints = {r['firstPointLevel'] - 1 + r['maxPoints']} exceeds maxLevel {r['maxLevel']}")
    page_ids = {p["id"] for p in doc["pages"]}
    for k in (r.get("pointsPerPage") or {}):
        if k not in page_ids:
            ctx.error("R03-POINTS-PER-PAGE", f"{cls}/rules", f"pointsPerPage key {k!r} is not a page id")


def rule_4_pages_trees(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    seen_pages: set[str] = set()
    for p in doc["pages"]:
        if p["id"] in seen_pages:
            ctx.error("R04-PAGE-DUP", f"{cls}/pages", f"duplicate page id {p['id']!r}")
        seen_pages.add(p["id"])
    seen_trees: set[str] = set()
    orders: dict[str, set[int]] = {}
    for tree in doc["trees"]:
        tid = tree["id"]
        if tid in seen_trees:
            ctx.error("R04-TREE-DUP", f"{cls}/{tid}", f"duplicate tree id {tid!r}")
        seen_trees.add(tid)
        if tree["page"] not in seen_pages:
            ctx.error("R04-TREE-PAGE", f"{cls}/{tid}", f"tree.page {tree['page']!r} is not a page id")
        o = orders.setdefault(tree["page"], set())
        if tree["order"] in o:
            ctx.error("R04-TREE-ORDER", f"{cls}/{tid}", f"tree.order {tree['order']} already used on page {tree['page']!r}")
        o.add(tree["order"])


def rule_5_talents(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    seen: dict[str, str] = {}
    for tree in doc["trees"]:
        tid = tree["id"]
        cells: dict[tuple[int, int], str] = {}
        for t in tree["talents"]:
            path = f"{cls}/{tid}/{t['id']}"
            if t["id"] in seen:
                ctx.error("R05-ID-DUP", path, f"talent id {t['id']!r} already used in tree {seen[t['id']]!r}")
            seen[t["id"]] = tid
            cell = (t["row"], t["col"])
            if cell in cells:
                ctx.error("R05-CELL-DUP", path, f"cell (row {cell[0]}, col {cell[1]}) already occupied by {cells[cell]!r}")
            cells[cell] = t["id"]
            if t["row"] >= tree["rows"]:
                ctx.error("R05-ROW", path, f"row {t['row']} >= tree.rows {tree['rows']}")
            if t["col"] >= tree["cols"]:
                ctx.error("R05-COL", path, f"col {t['col']} >= tree.cols {tree['cols']}")


def rule_6_ranks(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    for tree in doc["trees"]:
        for t in tree["talents"]:
            path = f"{cls}/{tree['id']}/{t['id']}"
            desc = t["description"]
            if re.search(r"[{}]", PLACEHOLDER_RE.sub("", desc)):
                ctx.error("R06-BRACES", path, "description contains braces that are not {n} placeholders")
            ph = placeholders(desc)
            k = len(ph)
            if ph != list(range(k)):
                ctx.error("R06-PLACEHOLDERS", path, f"placeholders {ph} are not {{0}}..{{{k - 1}}} without gaps")
            ranks = t["ranks"]
            if len(ranks) != t["maxRank"]:
                ctx.error("R06-RANKS-LEN", path, f"ranks has {len(ranks)} entries, maxRank is {t['maxRank']}")
            for i, r in enumerate(ranks):
                if isinstance(r, list):
                    if len(r) != k:
                        ctx.error("R06-SLOTS", path, f"ranks[{i}] has {len(r)} slot values, description has {k} placeholder(s)")
                elif isinstance(r, str):
                    if PLACEHOLDER_RE.search(r):
                        ctx.error("R06-STRING-RANK", path, f"string-form ranks[{i}] contains a {{n}} placeholder")
                else:
                    ctx.error("R06-RANK-TYPE", path, f"ranks[{i}] must be an array of slot values or a string")


def rule_7_rank_sources(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    for tree in doc["trees"]:
        for t in tree["talents"]:
            path = f"{cls}/{tree['id']}/{t['id']}"
            obs = t["ranksObserved"]
            if obs != sorted(set(obs)):
                ctx.error("R07-OBSERVED-ORDER", path, f"ranksObserved {obs} must be sorted and unique")
            bad = [r for r in obs if not (1 <= r <= t["maxRank"])]
            if bad:
                ctx.error("R07-OBSERVED-RANGE", path, f"ranksObserved entries {bad} outside 1..{t['maxRank']}")
            covers_all = set(obs) == set(range(1, t["maxRank"] + 1))
            src = t["ranksSource"]
            if src == "observed" and not covers_all:
                ctx.error("R07-OBSERVED-IFF", path, f"ranksSource is 'observed' but ranksObserved {obs} does not cover 1..{t['maxRank']}")
            if src != "observed" and covers_all:
                ctx.error("R07-OBSERVED-IFF", path, f"ranksObserved covers every rank, ranksSource must be 'observed' (is {src!r})")
            has_prior = "ranksPrior" in t
            if (src == "classic-prior") != has_prior:
                ctx.error("R07-PRIOR-IFF", path, "ranksPrior must be present iff ranksSource == 'classic-prior'")
            if src == "manual" and not t.get("ranksNote"):
                ctx.error("R07-MANUAL-NOTE", path, "ranksNote is required when ranksSource == 'manual'")
            if has_prior and ctx.prior is not None:
                cid = t["ranksPrior"].get("classicTalentId")
                rec = ctx.prior.by_id.get(cid)
                if rec is None:
                    ctx.warn("PRIOR-UNKNOWN", path, f"ranksPrior.classicTalentId {cid} not found in data/prior/classic-era/talents.json")
                elif rec.get("spellIds") and t["ranksPrior"].get("classicSpellIds") != rec["spellIds"]:
                    ctx.warn("PRIOR-SPELLS", path, f"ranksPrior.classicSpellIds differ from the prior's {rec['spellIds']} for Classic talent {cid} ({rec.get('name')})")


def rule_8_requires(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    all_ids = {t["id"]: tree["id"] for tree in doc["trees"] for t in tree["talents"]}
    for tree in doc["trees"]:
        by_id = {t["id"]: t for t in tree["talents"]}
        for t in tree["talents"]:
            path = f"{cls}/{tree['id']}/{t['id']}"
            reqs = t.get("requires")
            if reqs is None:
                continue
            if len(reqs) == 0:
                ctx.error("R08-EMPTY", path, "requires must be omitted instead of an empty array")
            if len(reqs) > 3:
                ctx.error("R08-COUNT", path, f"requires has {len(reqs)} entries, Talent.db2 allows at most 3")
            for req in reqs:
                target_id = req["talent"]
                if target_id == t["id"]:
                    ctx.error("R08-SELF", path, "talent requires itself")
                    continue
                target = by_id.get(target_id)
                if target is None:
                    where = f" (it is in tree {all_ids[target_id]!r})" if target_id in all_ids else ""
                    ctx.error("R08-TARGET", path, f"requires target {target_id!r} does not exist in tree {tree['id']!r}{where}")
                    continue
                if target["row"] > t["row"]:
                    ctx.error("R08-ROW", path, f"requires target {target_id!r} is in row {target['row']}, must be in row {t['row']} or above")
                elif target["row"] == t["row"] and target["col"] == t["col"]:
                    ctx.error("R08-CELL", path, f"requires target {target_id!r} occupies the same cell")
                if req["rank"] > target["maxRank"]:
                    ctx.error("R08-RANK", path, f"requires rank {req['rank']} exceeds {target_id!r} maxRank {target['maxRank']}")
        # cycles. Same-row prerequisites are legal (Forever has them, see
        # docs/handover/2026-09-13-cell-attribution-audit.md), so two talents in
        # one row can now require each other without breaking R08-ROW: this walk
        # is the only thing that catches it.
        WHITE, GREY, BLACK = 0, 1, 2
        colour = {tid: WHITE for tid in by_id}

        def visit(tid: str, stack: list[str]) -> None:
            colour[tid] = GREY
            for req in by_id[tid].get("requires") or []:
                nxt = req["talent"]
                if nxt not in by_id:
                    continue
                if colour[nxt] == GREY:
                    cyc = stack[stack.index(nxt):] + [nxt] if nxt in stack else [tid, nxt]
                    ctx.error("R08-CYCLE", f"{cls}/{tree['id']}/{tid}", "requires cycle: " + " -> ".join(cyc))
                elif colour[nxt] == WHITE:
                    visit(nxt, stack + [nxt])
            colour[tid] = BLACK

        for tid in by_id:
            if colour[tid] == WHITE:
                visit(tid, [tid])


def rule_9_files(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]

    def exists(rel: str) -> bool:
        return (ctx.root / rel).is_file()

    for tree in doc["trees"]:
        tsrc = tree.get("source") or {}
        if tsrc.get("kind") == "video" and "crop" in tsrc and not ctx.opts.no_files and not exists(tsrc["crop"]):
            ctx.error("R09-CROP-MISSING", f"{cls}/{tree['id']}", f"tree source.crop file not found: {tsrc['crop']}")
        for t in tree["talents"]:
            path = f"{cls}/{tree['id']}/{t['id']}"
            is_crop = t["iconSource"] == "crop"
            if is_crop != ("iconCrop" in t):
                ctx.error("R09-ICONCROP-IFF", path, "iconCrop must be present iff iconSource == 'crop'")
            if is_crop and t["icon"] != f"crop-{t['id']}":
                ctx.error("R09-ICON-SLUG", path, f"icon for iconSource 'crop' must be 'crop-{t['id']}', is {t['icon']!r}")
            if ctx.opts.no_files:
                continue
            if "iconCrop" in t and not exists(t["iconCrop"]):
                ctx.error("R09-ICONCROP-MISSING", path, f"iconCrop file not found: {t['iconCrop']}")
            src = t["source"]
            if src.get("kind") == "video" and "crop" in src and not exists(src["crop"]):
                ctx.error("R09-CROP-MISSING", path, f"source.crop file not found: {src['crop']}")


VIDEO_FIELDS = ("video", "t", "frame", "crop", "confidence", "reader")
DATAMINED_FIELDS = ("build", "talentId")


def check_source(ctx: Ctx, src: dict, path: str) -> None:
    kind = src.get("kind")
    present = set(src)
    if kind == "video":
        missing = [f for f in VIDEO_FIELDS if f not in present]
        if missing:
            ctx.error("R10-SOURCE-VIDEO", path, f"source.kind 'video' requires {missing}")
    else:
        extra = [f for f in VIDEO_FIELDS if f in present]
        if extra:
            ctx.error("R10-SOURCE-VIDEO", path, f"source fields {extra} are only allowed for kind 'video'")
    if kind == "datamined":
        missing = [f for f in DATAMINED_FIELDS if f not in present]
        if missing:
            ctx.error("R10-SOURCE-DATAMINED", path, f"source.kind 'datamined' requires {missing}")
    else:
        extra = [f for f in DATAMINED_FIELDS if f in present]
        if extra:
            ctx.error("R10-SOURCE-DATAMINED", path, f"source fields {extra} are only allowed for kind 'datamined'")
    reviewed = src.get("reviewed")
    has = [f for f in ("reviewedBy", "reviewedAt") if f in present]
    if reviewed is True and len(has) != 2:
        ctx.error("R10-REVIEWED", path, "reviewed: true requires reviewedBy and reviewedAt")
    if reviewed is not True and has:
        ctx.error("R10-REVIEWED", path, f"{has} only allowed when reviewed is true")
    if "reviewedAt" in src and not RFC3339_RE.match(str(src["reviewedAt"])):
        ctx.error("R10-REVIEWED-AT", path, f"reviewedAt {src['reviewedAt']!r} is not RFC 3339")
    if kind == "manual" and reviewed is not True:
        ctx.warn("MANUAL-UNREVIEWED", path, "manual source without reviewed: true (section 4.5 expects a reviewer)")


def rule_10_source(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    for tree in doc["trees"]:
        if isinstance(tree.get("source"), dict):
            check_source(ctx, tree["source"], f"{cls}/{tree['id']}")
        for t in tree["talents"]:
            path = f"{cls}/{tree['id']}/{t['id']}"
            check_source(ctx, t["source"], path)
            if "spellIds" in t and len(t["spellIds"]) != t["maxRank"]:
                ctx.error("R10-SPELLIDS", path, f"spellIds has {len(t['spellIds'])} entries, maxRank is {t['maxRank']}")


def _encoding_versions(root: Path) -> dict[int, Path]:
    enc = root / "data" / "encoding"
    out: dict[int, Path] = {}
    if enc.is_dir():
        for p in enc.glob("v*.json"):
            m = re.fullmatch(r"v(\d+)\.json", p.name)
            if m:
                out[int(m.group(1))] = p
    return out


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rule_11_encoding(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    dv = doc["dataVersion"]
    versions = _encoding_versions(ctx.root)
    if dv not in versions:
        ctx.error("R11-ENCODING-MISSING", cls, f"data/encoding/v{dv}.json does not exist")
        return
    if versions and dv != max(versions):
        ctx.error("R11-ENCODING-NOT-LATEST", cls, f"dataVersion {dv} is not the highest encoding version (v{max(versions)})")
    try:
        enc = _load_json(versions[dv])
    except ValueError as e:
        ctx.error("R11-ENCODING-PARSE", cls, f"data/encoding/v{dv}.json: {e}")
        return
    if enc.get("version") != dv:
        ctx.error("R11-ENCODING-VERSION", cls, f"v{dv}.json declares version {enc.get('version')!r}")
    centry = (enc.get("classes") or {}).get(cls)
    if centry is None:
        ctx.error("R11-ENCODING-CLASS", cls, f"class {cls!r} is not present in data/encoding/v{dv}.json")
        return
    # trees: pages flattened in pages[] order, trees by order within page
    page_rank = {p["id"]: i for i, p in enumerate(doc["pages"])}
    file_trees = [t["id"] for t in sorted(doc["trees"], key=lambda t: (page_rank.get(t["page"], 99), t["order"]))]
    enc_trees = centry.get("trees") or []
    if list(enc_trees) != file_trees:
        ctx.error("R11-ENCODING-TREES", cls, f"encoding trees {enc_trees} != file trees {file_trees} (pages flattened, by order)")
    order = centry.get("order") or {}
    enc_ids: list[str] = []
    for tid, ids in order.items():
        enc_ids.extend(ids)
    file_ids = [t["id"] for tree in doc["trees"] for t in tree["talents"]]
    if set(enc_ids) != set(file_ids):
        missing = sorted(set(file_ids) - set(enc_ids))
        extra = sorted(set(enc_ids) - set(file_ids))
        ctx.error("R11-ENCODING-IDS", cls,
                  f"talent id set differs from v{dv}.json order: missing in encoding {missing}, not in file {extra}")
    if len(enc_ids) != len(set(enc_ids)):
        ctx.error("R11-ENCODING-DUP", cls, f"v{dv}.json lists a talent id twice for class {cls!r}")
    for tree in doc["trees"]:
        want = [t["id"] for t in sorted(tree["talents"], key=lambda t: (t["row"], t["col"]))]
        got = order.get(tree["id"])
        if got is None:
            ctx.error("R11-ENCODING-TREE-ORDER", f"{cls}/{tree['id']}", f"v{dv}.json has no order for tree {tree['id']!r}")
        elif set(got) == set(want) and list(got) != want:
            ctx.warn("ENCODING-ORDER", f"{cls}/{tree['id']}",
                     "encoding order is not row-major for the current grid (allowed: the encoding is frozen, the grid moved)")
    # migration chain: v1 -> v2 -> ... -> dv, total for this class
    for a in range(1, dv):
        b = a + 1
        mpath = ctx.root / "data" / "encoding" / "migrations" / f"v{a}-v{b}.json"
        if a not in versions or b not in versions:
            ctx.error("R11-VERSION-GAP", cls, f"encoding version v{a if a not in versions else b}.json missing from the chain")
            continue
        if not mpath.is_file():
            ctx.error("R11-MIGRATION-MISSING", cls, f"migration file {mpath.relative_to(ctx.root)} missing")
            continue
        try:
            mig = _load_json(mpath)
            older = _load_json(versions[a])
            newer = _load_json(versions[b])
        except ValueError as e:
            ctx.error("R11-MIGRATION-PARSE", cls, f"{mpath.name}: {e}")
            continue
        if mig.get("from") != a or mig.get("to") != b:
            ctx.error("R11-MIGRATION-HEADER", cls, f"{mpath.name} declares from/to {mig.get('from')}/{mig.get('to')}")
        old_ids = {i for ids in ((older.get("classes") or {}).get(cls, {}).get("order") or {}).values() for i in ids}
        new_ids = {i for ids in ((newer.get("classes") or {}).get(cls, {}).get("order") or {}).values() for i in ids}
        mc = (mig.get("classes") or {}).get(cls) or {}
        renamed = mc.get("renamed") or {}
        removed = set(mc.get("removed") or [])
        moved = mc.get("moved") or {}
        for old in sorted(old_ids):
            if old in removed:
                continue
            target = renamed.get(old, old)
            if target not in new_ids:
                ctx.error("R11-MIGRATION-NOT-TOTAL", cls,
                          f"v{a}->v{b}: talent {old!r} is neither in v{b}.json (as {target!r}), renamed nor removed")
        for old, new in renamed.items():
            if old not in old_ids:
                ctx.error("R11-MIGRATION-RENAME", cls, f"v{a}->v{b}: renamed source {old!r} is not in v{a}.json")
            if new not in new_ids:
                ctx.error("R11-MIGRATION-RENAME", cls, f"v{a}->v{b}: renamed target {new!r} is not in v{b}.json")
        for tid in moved:
            if tid not in old_ids or tid not in new_ids:
                ctx.error("R11-MIGRATION-MOVE", cls, f"v{a}->v{b}: moved talent {tid!r} must exist in both versions")


def rule_12_canonical(ctx: Ctx, doc: dict, raw: bytes, kind: str) -> None:
    cls = doc["class"]
    if kind == "talents":
        for tree in doc["trees"]:
            for t in tree["talents"]:
                if "readings" in t["source"]:
                    ctx.error("R12-READINGS", f"{cls}/{tree['id']}/{t['id']}", "canonical files must not contain source.readings")
            if isinstance(tree.get("source"), dict) and "readings" in tree["source"]:
                ctx.error("R12-READINGS", f"{cls}/{tree['id']}", "canonical files must not contain source.readings")
        if "generatedAt" not in doc:
            ctx.error("R12-GENERATED-AT", cls, "generatedAt missing")
    if ctx.opts.check or kind == "talents":
        canon = canonical_dumps(doc).encode("utf-8")
        if raw != canon:
            code = "R12-NOT-CANONICAL"
            msg = "file is not byte-identical to the canonical serializer output (key order, talent sort, whitespace); rewrite via export.py"
            if ctx.opts.check:
                ctx.error(code, cls, msg)
            else:
                ctx.warn(code, cls, msg)


# ----------------------------------------------------------------------------
# Rules 13-19 (warnings)
# ----------------------------------------------------------------------------

def _tree_budget(doc: dict, tree: dict) -> int:
    r = doc["rules"]
    ppp = r.get("pointsPerPage") or {}
    return min(r["maxPoints"], ppp.get(tree["page"], r["maxPoints"]))


def rule_13_row_gating(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    ppr = doc["rules"]["pointsPerRow"]
    for tree in doc["trees"]:
        need = ppr * (tree["rows"] - 1)
        budget = _tree_budget(doc, tree)
        if need > budget:
            ctx.warn("R13-ROW-GATING", f"{cls}/{tree['id']}",
                     f"pointsPerRow * (rows - 1) = {need} exceeds the {budget}-point budget; the bottom row is unreachable")


def _progression(vals: list[float]) -> str:
    if len(vals) < 2:
        return "constant"
    d = [round(b - a, 6) for a, b in zip(vals, vals[1:])]
    if all(x == 0 for x in d):
        return "constant"
    if all(x > 0 for x in d) or all(x < 0 for x in d):
        return "arithmetic" if len(set(d)) == 1 else "monotonic"
    return "other"


def rule_14_progression(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    for tree in doc["trees"]:
        for t in tree["talents"]:
            ranks = t["ranks"]
            if t["maxRank"] < 2 or not all(isinstance(r, list) for r in ranks):
                continue
            path = f"{cls}/{tree['id']}/{t['id']}"
            k = len(placeholders(t["description"]))
            prior_slots = None
            if ctx.prior is not None and "ranksPrior" in t:
                rec = ctx.prior.by_id.get(t["ranksPrior"].get("classicTalentId"))
                if rec:
                    prior_slots = rec.get("slots")
            for i in range(k):
                col = [r[i] for r in ranks if i < len(r)]
                if len(col) != len(ranks) or not all(is_number(v) for v in col):
                    continue
                kind = _progression([float(v) for v in col])
                if kind in ("constant", "arithmetic"):
                    continue
                if prior_slots and _matches_prior_pattern([float(v) for v in col], prior_slots):
                    continue
                ctx.warn("NONLINEAR-RANKS", path, f"slot {{{i}}} progression {col} is neither constant nor arithmetic")


def _matches_prior_pattern(vals: list[float], prior_slots: list[list[float]]) -> bool:
    """True when some Classic slot has the same difference pattern (up to a scale factor)."""
    n = len(vals)
    d = [b - a for a, b in zip(vals, vals[1:])]
    for pv in prior_slots:
        if len(pv) != n:
            continue
        pd = [b - a for a, b in zip(pv, pv[1:])]
        if pd == d:
            return True
        nz = [(x, y) for x, y in zip(d, pd) if y != 0]
        if nz and all(y != 0 for y in pd):
            ratios = {round(x / y, 6) for x, y in nz}
            if len(ratios) == 1:
                return True
    return False


def rule_15_names(ctx: Ctx, doc: dict) -> None:
    if ctx.prior is None:
        return
    cls = doc["class"]
    candidates = ctx.prior.by_class.get(cls) or []
    if not candidates:
        return
    for tree in doc["trees"]:
        for t in tree["talents"]:
            path = f"{cls}/{tree['id']}/{t['id']}"
            best, best_score = None, 0.0
            for c in candidates:
                s = token_ratio(t["name"], c.get("name", ""))
                if s > best_score:
                    best, best_score = c, s
            if best is None or best_score < NAME_MATCH_THRESHOLD:
                ctx.info("NEW-TALENT", path, f"no Classic talent of class {cls!r} matches name {t['name']!r} (best {best_score:.0f})")
                continue
            if best.get("maxRank") != t["maxRank"]:
                ctx.warn("MAXRANK-DIFFERS-FROM-CLASSIC", path,
                         f"maxRank {t['maxRank']} but Classic {best['name']!r} (talent {best.get('classicTalentId')}) has {best.get('maxRank')}")


def rule_16_needs_review(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    for tree in doc["trees"]:
        for t in tree["talents"]:
            src = t["source"]
            if src.get("kind") == "video" and src.get("confidence", 1.0) < REVIEW_THRESHOLD and not src.get("reviewed"):
                ctx.warn("NEEDS-REVIEW", f"{cls}/{tree['id']}/{t['id']}",
                         f"confidence {src['confidence']:.2f} < {REVIEW_THRESHOLD} and not reviewed")


OCR_ARTEFACT_RE = re.compile(r"[|\\~]")
LONE_L_RE = re.compile(r"(?<![A-Za-z])[lI](?=\d|%|\s(?:sec|min|yd|yards|seconds|minutes)\b)|(?<=\d)[lI](?![A-Za-z])")


def _text_hygiene(ctx: Ctx, text: str, path: str, what: str) -> None:
    if text != text.strip():
        ctx.warn("R17-WHITESPACE", path, f"{what} has leading/trailing whitespace")
    if "  " in text:
        ctx.warn("R17-DOUBLE-SPACE", path, f"{what} contains a double space")
    s = text.strip()
    if s and not (s.endswith(".") or s.endswith("%")):
        ctx.warn("R17-TERMINATOR", path, f"{what} does not end with '.' or '%' (ends with {s[-1]!r})")
    m = OCR_ARTEFACT_RE.search(text)
    if m:
        ctx.warn("R17-OCR-ARTEFACT", path, f"{what} contains OCR artefact {m.group(0)!r}")
    m = LONE_L_RE.search(text)
    if m:
        ctx.warn("R17-OCR-ARTEFACT", path, f"{what} has a lone {m.group(0)!r} where a digit is expected")


def rule_17_hygiene(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    for tree in doc["trees"]:
        for t in tree["talents"]:
            path = f"{cls}/{tree['id']}/{t['id']}"
            _text_hygiene(ctx, t["description"], path, "description")
            for i, r in enumerate(t["ranks"]):
                if isinstance(r, str):
                    _text_hygiene(ctx, r, path, f"ranks[{i}]")
            if t["name"] != t["name"].strip() or "  " in t["name"]:
                ctx.warn("R17-NAME", path, "name has stray whitespace")


def rule_18_tree_totals(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    for tree in doc["trees"]:
        total = sum(t["maxRank"] for t in tree["talents"])
        budget = _tree_budget(doc, tree)
        if total < budget:
            ctx.warn("R18-TREE-TOO-SMALL", f"{cls}/{tree['id']}", f"sum(maxRank) = {total} < {budget} points; tree cannot absorb all points")
        if total > 3 * doc["rules"]["maxPoints"]:
            ctx.warn("R18-TREE-TOO-LARGE", f"{cls}/{tree['id']}", f"sum(maxRank) = {total} > 3 * maxPoints")


# Rule 20: anticipated ranks that cannot be real numbers (data audit 2026-09-13, work package B6).
# Only ranks 2+ are ever flagged: rank 1 was read off a tooltip, the rest is arithmetic.
PERCENT_SLOT_RE = r"\{{{i}}}\s*%"
# A threshold is a condition, not a magnitude: "below 35% health" does not become "below 70%"
# at rank 2. Classic never scales these, and the extrapolator has no way to know.
THRESHOLD_RE = re.compile(
    r"(?:below|under|less than|beneath|at or below|above|over|more than|greater than|at least)\s+"
    r"(?:\w+\s+){0,2}?\{(\d+)\}\s*%", re.I)
# The same shape with a distance instead of a percentage: "jumping to a nearby enemy within 5 yards"
# is a search condition, not the talent's magnitude, so it does not double at rank 2 either.
# Only distance units qualify - "within {0} sec" is often a real window that a talent may extend.
DISTANCE_THRESHOLD_RE = re.compile(
    r"(?:within|inside|closer than|no more than)\s+(?:\w+\s+){0,2}?\{(\d+)\}\s*(?:yards?|yds?|meters?|metres?)",
    re.I)
CLASSIC_HEADROOM = 1.6          # Forever rank N above this multiple of Classic's max is worth a look


def _percent_slot(description: str, i: int) -> bool:
    return re.search(PERCENT_SLOT_RE.format(i=i), description) is not None


def rule_20_rank_sanity(ctx: Ctx, doc: dict) -> None:
    """Flag anticipated rank values that cannot be right: impossible percentages, scaled
    thresholds, and values far above the Classic talent they were derived from."""
    cls = doc["class"]
    for tree in doc["trees"]:
        for t in tree["talents"]:
            ranks = t["ranks"]
            desc = t["description"]
            path = f"{cls}/{tree['id']}/{t['id']}"
            if t["maxRank"] < 2 or not all(isinstance(r, list) for r in ranks):
                continue
            observed = set(t.get("ranksObserved") or [1])
            thresholds = {int(m.group(1)) for m in THRESHOLD_RE.finditer(desc)}
            thresholds |= {int(m.group(1)) for m in DISTANCE_THRESHOLD_RE.finditer(desc)}
            for i in placeholders(desc):
                col = [(n, r[i]) for n, r in enumerate(ranks, 1) if i < len(r) and is_number(r[i])]
                if len(col) != len(ranks):
                    continue
                vals = [v for _, v in col]
                if i in thresholds and len(set(vals)) > 1:
                    ctx.warn("R20-THRESHOLD-SCALED", path,
                             f"slot {{{i}}} reads as a threshold in the text but changes per rank {vals}; "
                             f"a condition like 'below {vals[0]}% health' or 'within {vals[0]} yards' does not scale")
                if _percent_slot(desc, i):
                    over = [(n, v) for n, v in col if v > 100 and n not in observed]
                    if over and vals[0] <= 100:
                        ctx.warn("R20-PERCENT-OVER-100", path,
                                 f"slot {{{i}}} is a percentage and the anticipated value exceeds 100 % at rank(s) "
                                 f"{[n for n, _ in over]} ({vals}); rank 1 was read, the rest is arithmetic")
                prior = t.get("ranksPrior") or {}
                rec = ctx.prior.by_id.get(prior.get("classicTalentId")) if ctx.prior is not None else None
                # the prior's slots are indexed [rank][placeholder]; take this placeholder's column
                slots = (rec or {}).get("slots") or []
                classic_col = [row[i] for row in slots if isinstance(row, list) and i < len(row) and is_number(row[i])]
                if classic_col:
                    classic_max = max(float(x) for x in classic_col)
                    if classic_max > 0 and max(vals) > CLASSIC_HEADROOM * classic_max:
                        ctx.warn("R20-ABOVE-CLASSIC", path,
                                 f"slot {{{i}}} reaches {max(vals)} against the Classic talent's {classic_max:g} "
                                 f"({max(vals) / classic_max:.1f}x); the match or the scaling may be wrong")


def rule_19_row_occupancy(ctx: Ctx, doc: dict) -> None:
    cls = doc["class"]
    for tree in doc["trees"]:
        used = {t["row"] for t in tree["talents"]}
        empty = [r for r in range(tree["rows"]) if r not in used]
        if empty:
            ctx.warn("R19-EMPTY-ROWS", f"{cls}/{tree['id']}", f"rows {empty} have no talent")


# ----------------------------------------------------------------------------
# Review queue (section 7 step 2)
# ----------------------------------------------------------------------------

def build_review_queue(ctx: Ctx, doc: dict) -> list[dict]:
    cls = doc["class"]
    by_path: dict[str, list[str]] = {}
    for f in ctx.result.findings:
        if f.level == "WARNING":
            by_path.setdefault(f.path, []).append(f.code)
    queue = []
    for tree in doc["trees"]:
        for t in tree["talents"]:
            path = f"{cls}/{tree['id']}/{t['id']}"
            reasons: list[str] = []
            src = t["source"]
            conf = src.get("confidence")
            if src.get("kind") == "video" and conf is not None and conf < REVIEW_THRESHOLD:
                reasons.append(f"confidence {conf:.2f}")
            if t["ranksSource"] == "manual":
                reasons.append("ranksSource manual")
            if t["iconSource"] == "crop":
                reasons.append("iconSource crop")
            reasons.extend(c for c in by_path.get(path, []) if c not in ("NEEDS-REVIEW",))
            if reasons and not src.get("reviewed"):
                queue.append({"tree": tree["id"], "talent": t["id"], "name": t["name"],
                              "confidence": conf, "reasons": reasons})
    queue.sort(key=lambda q: (q["confidence"] if q["confidence"] is not None else 1.0, q["tree"], q["talent"]))
    return queue


# ----------------------------------------------------------------------------
# Overrides files (--overrides)
# ----------------------------------------------------------------------------

def _without_required(node: Any) -> Any:
    """Same schema with every ``required`` list dropped (recursively through $ref-free branches)."""
    if isinstance(node, dict):
        return {k: _without_required(v) for k, v in node.items() if k != "required"}
    if isinstance(node, list):
        return [_without_required(v) for v in node]
    return node


def overrides_schema(class_schema: dict) -> dict:
    """Schema for data/overrides/<class>.json (section 6.2), reusing the class schema's $defs."""
    defs = json.loads(json.dumps(class_schema["$defs"]))
    talent = defs["talent"]
    # `set` is a shallow merge, and section 6.2 says source sub-fields merge shallowly too, so a
    # `set.source` that names only the field being corrected must validate. Strip the required
    # lists from the source variants used inside `set` (the merged result is validated in full
    # when the class file itself is validated).
    # the talent's `source` is a $ref; point `set.source` at a required-less copy of that $def
    defs["sourcePartial"] = _without_required(defs["source"])
    props = json.loads(json.dumps(talent["properties"]))
    props["source"] = {"$ref": "#/$defs/sourcePartial"}
    partial = {"type": "object", "additionalProperties": False, "properties": props,
               "allOf": talent.get("allOf", [])}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["schemaVersion", "class", "overrides"],
        "properties": {
            "$schema": {"type": "string"},
            "schemaVersion": {"type": "integer", "const": SCHEMA_VERSION},
            "class": {"$ref": "#/$defs/classId"},
            "overrides": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["talent", "tree", "reason", "by", "at"],
                    "properties": {
                        "talent": {"$ref": "#/$defs/talentId"},
                        "tree": {"$ref": "#/$defs/treeId"},
                        "set": partial,
                        "unset": {"type": "array", "minItems": 1, "uniqueItems": True,
                                  "items": {"type": "string", "enum": sorted(UNSETTABLE)}},
                        "rename": {"$ref": "#/$defs/talentId"},
                        "delete": {"const": True},
                        "add": {"$ref": "#/$defs/talent"},
                        "reason": {"type": "string", "minLength": 1},
                        "by": {"type": "string", "minLength": 1},
                        "at": {"$ref": "#/$defs/rfc3339"},
                    },
                    "anyOf": [
                        {"required": ["set"]},
                        {"required": ["unset"]},
                        {"required": ["rename"]},
                        {"required": ["delete"]},
                        {"required": ["add"]},
                    ],
                    # delete and add own the whole record; nothing else may ride along
                    "allOf": [
                        {"if": {"required": ["delete"]},
                         "then": {"not": {"anyOf": [{"required": ["set"]}, {"required": ["unset"]},
                                                    {"required": ["rename"]}, {"required": ["add"]}]}}},
                        {"if": {"required": ["add"]},
                         "then": {"not": {"anyOf": [{"required": ["set"]}, {"required": ["unset"]},
                                                    {"required": ["rename"]}, {"required": ["delete"]}]}}},
                    ],
                },
            },
        },
        "$defs": defs,
    }


def validate_overrides(ctx: Ctx, doc: Any, raw: bytes) -> None:
    if not isinstance(doc, dict):
        ctx.error("R01-SCHEMA", ctx.stem, "top level is not a JSON object")
        return
    if doc.get("schemaVersion") != SCHEMA_VERSION:
        ctx.error("R01-SCHEMA-VERSION", ctx.stem, f"schemaVersion is {doc.get('schemaVersion')!r}")
        return
    validator = Draft202012Validator(overrides_schema(ctx.schema), format_checker=FormatChecker())
    ok = True
    for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path)):
        ok = False
        ctx.error("R01-SCHEMA", f"{ctx.stem}:{json_path(e.absolute_path)}", _schema_msg(e))
    if doc.get("class") != ctx.stem:
        ctx.error("R02-CLASS-STEM", ctx.stem, f"class {doc.get('class')!r} does not equal file stem {ctx.stem!r}")
    if not ok:
        return
    cls = doc["class"]
    # cross-check against the sibling extracted file when present
    extracted = ctx.root / "data" / "extracted" / f"{cls}.json"
    ex_index: dict[str, str] | None = None
    if extracted.is_file():
        try:
            exdoc = _load_json(extracted)
            ex_index = {t["id"]: tree["id"] for tree in exdoc.get("trees", []) for t in tree.get("talents", [])}
        except (ValueError, KeyError, TypeError):
            ex_index = None
    for i, o in enumerate(doc["overrides"]):
        path = f"{cls}/{o['tree']}/{o['talent']}"
        if "add" in o:
            add = o["add"]
            if add.get("id") != o["talent"]:
                ctx.error("OVR-ADD-ID", path, f"overrides[{i}]: add.id {add.get('id')!r} must equal talent {o['talent']!r}")
            check_source(ctx, add.get("source", {}), path)
            if ex_index is not None and o["talent"] in ex_index:
                ctx.error("OVR-ADD-EXISTS", path, f"overrides[{i}]: add for a talent that extraction already has")
        elif ex_index is not None:
            if o["talent"] not in ex_index:
                ctx.warn("OVR-TARGET", path, f"overrides[{i}]: talent not found in data/extracted/{cls}.json")
            elif ex_index[o["talent"]] != o["tree"]:
                ctx.warn("OVR-TREE", path, f"overrides[{i}]: extracted has this talent in tree {ex_index[o['talent']]!r}")
        if "set" in o and "source" in o["set"]:
            s = o["set"]["source"]
            if "kind" in s and s["kind"] == "video" and not all(f in s for f in VIDEO_FIELDS):
                pass  # partial merge is allowed for set.source (shallow merge, section 6.2)
    if ctx.opts.check:
        canon = canonical_dumps(doc, kind="overrides").encode("utf-8")
        if raw != canon:
            ctx.error("R12-NOT-CANONICAL", cls, "overrides file is not byte-identical to the canonical serializer output")


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------

def validate_path(path: Path, opts: argparse.Namespace, schema_cache: dict[Path, dict], prior_cache: dict[Path, Any]) -> FileResult:
    root = find_root(path, opts.root)
    if root is None:
        r = FileResult(file=str(path))
        r.findings.append(Finding("ERROR", "R00-ROOT", path.stem, "repo root not found (no data/schema/class.schema.json above the file); pass --root"))
        return r
    schema_path = root / "data" / "schema" / "class.schema.json"
    if schema_path not in schema_cache:
        schema = _load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        schema_cache[schema_path] = schema
    if root not in prior_cache:
        prior_cache[root] = Prior.load(root)
        if prior_cache[root] is None and not opts.json:
            sys.stderr.write(f"note: {root / 'data/prior/classic-era/talents.json'} not found; rules 14 (prior pattern) and 15 skipped\n")
    ctx = Ctx(path, root, opts, schema_cache[schema_path], prior_cache[root])
    try:
        raw = path.read_bytes()
    except OSError as e:
        ctx.error("R01-IO", path.stem, str(e))
        return ctx.result
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        ctx.error("R01-PARSE", path.stem, f"invalid JSON: {e}")
        return ctx.result

    kind = file_kind(path)
    if opts.overrides or kind == "overrides":
        validate_overrides(ctx, doc, raw)
        return ctx.result

    if not rule_1_schema(ctx, doc):
        return ctx.result  # structural checks below assume a schema-valid document
    rule_2_ids(ctx, doc)
    rule_3_rules(ctx, doc)
    rule_4_pages_trees(ctx, doc)
    rule_5_talents(ctx, doc)
    rule_6_ranks(ctx, doc)
    rule_7_rank_sources(ctx, doc)
    rule_8_requires(ctx, doc)
    rule_9_files(ctx, doc)
    rule_10_source(ctx, doc)
    rule_11_encoding(ctx, doc)
    rule_12_canonical(ctx, doc, raw, kind)
    rule_13_row_gating(ctx, doc)
    rule_14_progression(ctx, doc)
    rule_15_names(ctx, doc)
    rule_16_needs_review(ctx, doc)
    rule_17_hygiene(ctx, doc)
    rule_18_tree_totals(ctx, doc)
    rule_19_row_occupancy(ctx, doc)
    rule_20_rank_sanity(ctx, doc)
    if opts.strict:
        for f in ctx.result.findings:
            if f.level == "WARNING":
                f.level = "ERROR"
    ctx.result.review_queue = build_review_queue(ctx, doc)
    return ctx.result


LEVEL_ORDER = {"ERROR": 0, "WARNING": 1, "INFO": 2}


def print_text(results: list[FileResult], opts: argparse.Namespace) -> None:
    for r in results:
        name = os.path.basename(r.file)
        for f in sorted(r.findings, key=lambda f: (LEVEL_ORDER.get(f.level, 9), f.path, f.code)):
            print(f"{f.level:<7} {f.code:<28} {name}:{f.path}: {f.message}")
        print(f"{name}: {r.count('ERROR')} error(s), {r.count('WARNING')} warning(s), {r.count('INFO')} info")
        if opts.report and r.review_queue:
            print(f"{name}: review queue ({len(r.review_queue)}):")
            for q in r.review_queue:
                conf = f"{q['confidence']:.2f}" if q["confidence"] is not None else "  - "
                print(f"  {conf}  {q['tree']}/{q['talent']:<32} {', '.join(q['reasons'])}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="class files (data/talents, data/extracted, data/examples) or, with --overrides, override files")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--json", action="store_true", help="JSON output for the review UI")
    ap.add_argument("--report", action="store_true", help="print the review queue")
    ap.add_argument("--overrides", action="store_true", help="files are data/overrides files")
    ap.add_argument("--check", action="store_true", help="fail unless the file is byte-identical to the canonical serializer output")
    ap.add_argument("--no-files", action="store_true", help="skip crop file existence checks (rule 9)")
    ap.add_argument("--root", help="repository root (default: auto-detect)")
    opts = ap.parse_args(argv)

    results: list[FileResult] = []
    schema_cache: dict[Path, dict] = {}
    prior_cache: dict[Path, Any] = {}
    for f in opts.files:
        results.append(validate_path(Path(f), opts, schema_cache, prior_cache))

    errors = sum(r.count("ERROR") for r in results)
    if opts.json:
        print(json.dumps({"ok": errors == 0, "files": [r.to_dict() for r in results]}, indent=2, ensure_ascii=False))
    else:
        print_text(results, opts)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

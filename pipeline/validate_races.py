#!/usr/bin/env python3
"""Validate WoW Forever race files against docs/DATA-SCHEMA-RACES.md.

The companion of ``validate.py`` for ``data/races/``. Separate file rather than a
mode of the class validator because the two share only the serializer and the
``source`` conventions, and ``validate.py`` is already 1200 lines.

    cd pipeline && uv run python validate_races.py ../data/races/*.json
    uv run python validate_races.py --check ../data/races/*.json      # CI
    uv run python validate_races.py --report ../data/races/*.json     # review queue

Rules R1-R12 are errors, R13-R18 warnings (``--strict`` makes warnings errors).
Exit code 1 on any error, 0 otherwise. The matrix file (``matrix.json``) is
recognised by its shape and checked by rules M1-M4 instead.

Options mirror validate.py: ``--strict``, ``--json``, ``--report``, ``--check``,
``--no-files``, ``--root DIR``.
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
    sys.stderr.write("validate_races.py needs the 'jsonschema' package (uv run / uvx --with jsonschema)\n")
    raise

SCHEMA_VERSION = 1
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
REVIEW_THRESHOLD = 0.8
CLASSES = {"druid", "hunter", "mage", "paladin", "priest", "rogue", "shaman", "warlock", "warrior"}
#: The nine races the character-creation screen offers. A file outside this set is
#: not an error (Forever may add one), only a warning, exactly as UNKNOWN-CLASS is.
KNOWN_RACES = {"human", "dwarf", "night-elf", "gnome", "skyborne", "orc", "undead", "tauren", "troll"}

KEY_ORDER = {
    "top": ["$schema", "schemaVersion", "race", "raceName", "faction", "dataSource", "generatedAt",
            "variants", "classes", "classesSource", "lore", "loreComplete", "loreSource",
            "traits", "complete", "notes"],
    "variant": ["id", "name", "faction", "classes", "lore", "loreComplete"],
    "trait": ["id", "name", "kind", "order", "variants", "description", "icon", "iconSource",
              "iconCrop", "classic", "tags", "source"],
    "classic": ["status", "classicName", "classicText", "note"],
    "source": ["kind", "video", "t", "frame", "crop", "panel", "confidence", "reader", "readings",
               "build", "reviewed", "reviewedBy", "reviewedAt", "note"],
    "reading": ["reader", "name", "description", "confidence"],
    "matrixTop": ["$schema", "schemaVersion", "dataSource", "generatedAt", "classes", "races", "notes"],
    "matrixRow": ["race", "raceName", "faction", "classes", "byVariant", "observed",
                  "reportedElsewhere", "agreement", "disagreement"],
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

    def info(self, code: str, where: str, msg: str) -> None:
        self.result.findings.append(Finding("INFO", code, where, msg))


# ----------------------------------------------------------------------------
# Canonical serializer (rule R12 / M4)
# ----------------------------------------------------------------------------

def _order(obj: dict, keys: list[str]) -> dict:
    out = {k: obj[k] for k in keys if k in obj}
    for k in obj:
        if k not in out:
            out[k] = obj[k]
    return out


def order_race_doc(doc: dict) -> dict:
    """Key order of docs/DATA-SCHEMA-RACES.md, traits sorted by ``order``."""
    if is_matrix(doc):
        doc = _order(doc, KEY_ORDER["matrixTop"])
        if isinstance(doc.get("races"), list):
            doc["races"] = [_order(r, KEY_ORDER["matrixRow"]) if isinstance(r, dict) else r
                            for r in doc["races"]]
        return doc
    doc = _order(doc, KEY_ORDER["top"])
    if isinstance(doc.get("variants"), list):
        doc["variants"] = [_order(v, KEY_ORDER["variant"]) if isinstance(v, dict) else v
                           for v in doc["variants"]]
    for key in ("classesSource", "loreSource"):
        if isinstance(doc.get(key), dict):
            doc[key] = _order(doc[key], KEY_ORDER["source"])
    traits = []
    for t in doc.get("traits") or []:
        if not isinstance(t, dict):
            traits.append(t)
            continue
        t = _order(t, KEY_ORDER["trait"])
        if isinstance(t.get("classic"), dict):
            t["classic"] = _order(t["classic"], KEY_ORDER["classic"])
        if isinstance(t.get("source"), dict):
            t["source"] = _order(t["source"], KEY_ORDER["source"])
            if isinstance(t["source"].get("readings"), list):
                t["source"]["readings"] = [_order(r, KEY_ORDER["reading"]) if isinstance(r, dict) else r
                                           for r in t["source"]["readings"]]
        traits.append(t)
    if "traits" in doc:
        try:
            traits = sorted(traits, key=lambda t: (t.get("order", 10 ** 6), t.get("id", "")))
        except TypeError:
            pass
        doc["traits"] = traits
    return doc


def canonical_dumps(doc: dict) -> str:
    return _dump(order_race_doc(doc), 0) + "\n"


def is_matrix(doc: Any) -> bool:
    return isinstance(doc, dict) and "races" in doc and "race" not in doc


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
    if doc.get("race") != path.stem:
        ctx.err("RACE-FILENAME", "/race", f"race {doc.get('race')!r} does not match the file name {path.stem!r}")
    if doc.get("race") not in KNOWN_RACES:
        ctx.warn("UNKNOWN-RACE", "/race", f"{doc.get('race')!r} is not one of the nine races seen in the picker")
    for i, t in enumerate(doc.get("traits") or []):
        if not SLUG_RE.match(t.get("id") or ""):
            ctx.err("BAD-ID", f"/traits/{i}", f"{t.get('id')!r} is not a slug")
    for i, v in enumerate(doc.get("variants") or []):
        if not SLUG_RE.match(v.get("id") or ""):
            ctx.err("BAD-ID", f"/variants/{i}", f"{v.get('id')!r} is not a slug")


def rule_3_traits_unique(ctx: Ctx, doc: dict) -> None:
    seen: dict[str, int] = {}
    orders: dict[int, str] = {}
    for i, t in enumerate(doc.get("traits") or []):
        tid = t.get("id")
        if tid in seen:
            ctx.err("DUPLICATE-TRAIT", f"/traits/{i}", f"{tid!r} also appears at index {seen[tid]}")
        seen[tid] = i
        o = t.get("order")
        if isinstance(o, int):
            if o in orders:
                ctx.err("DUPLICATE-ORDER", f"/traits/{i}", f"order {o} also used by {orders[o]!r}")
            orders[o] = tid
    if orders and sorted(orders) != list(range(len(orders))):
        ctx.warn("ORDER-GAPS", "/traits", f"orders {sorted(orders)} are not 0..{len(orders) - 1}")


def rule_4_variants(ctx: Ctx, doc: dict) -> None:
    variants = doc.get("variants") or []
    ids = {v.get("id") for v in variants}
    if variants:
        factions = [v.get("faction") for v in variants]
        if len(set(factions)) != len(factions):
            ctx.err("VARIANT-FACTIONS", "/variants", "two variants claim the same faction")
        if doc.get("faction") != "neutral":
            ctx.warn("VARIANT-FACTION-TOP", "/faction",
                     "a race with variants in both factions should be 'neutral' at the top level")
    for i, t in enumerate(doc.get("traits") or []):
        tv = t.get("variants")
        if variants and not tv:
            ctx.err("TRAIT-VARIANTS", f"/traits/{i}", "a race with variants needs variants[] on every trait")
        if tv and not variants:
            ctx.err("TRAIT-VARIANTS", f"/traits/{i}", "variants[] on a trait of a race without variants")
        for v in tv or []:
            if v not in ids:
                ctx.err("UNKNOWN-VARIANT", f"/traits/{i}", f"{v!r} is not one of {sorted(ids)}")


def rule_5_classes(ctx: Ctx, doc: dict) -> None:
    classes = doc.get("classes") or []
    if sorted(classes) != list(classes):
        ctx.err("CLASSES-UNSORTED", "/classes", "class ids must be sorted")
    bad = [c for c in classes if c not in CLASSES]
    if bad:
        ctx.err("UNKNOWN-CLASS", "/classes", f"not class ids: {bad}")
    union: set[str] = set()
    for v in doc.get("variants") or []:
        union |= set(v.get("classes") or [])
    if doc.get("variants") and union != set(classes):
        ctx.err("CLASSES-UNION", "/classes",
                f"classes must be the union over the variants: {sorted(union)} != {sorted(classes)}")
    if not classes:
        ctx.warn("NO-CLASSES", "/classes", "empty class list: the class bar was never read for this race")


def rule_6_descriptions(ctx: Ctx, doc: dict) -> None:
    for i, t in enumerate(doc.get("traits") or []):
        d = t.get("description")
        if d is None:
            ctx.warn("NO-DESCRIPTION", f"/traits/{i}",
                     f"{t.get('id')!r} has a name but no description; source.note must say why")
            if not (t.get("source") or {}).get("note"):
                ctx.err("NO-DESCRIPTION-NOTE", f"/traits/{i}", "a trait without a description needs source.note")
            continue
        if d != d.strip() or "  " in d:
            ctx.warn("TEXT-HYGIENE", f"/traits/{i}", "leading, trailing or double whitespace in the description")
        if re.search(r"[|\\~]", d):
            ctx.warn("TEXT-HYGIENE", f"/traits/{i}", "OCR artefact character in the description")


def rule_7_classic(ctx: Ctx, doc: dict) -> None:
    for i, t in enumerate(doc.get("traits") or []):
        c = t.get("classic") or {}
        st = c.get("status")
        if st == "new" and c.get("classicName"):
            ctx.err("CLASSIC-NEW", f"/traits/{i}", "status 'new' but a Classic counterpart is named")
        if st in {"same", "changed"} and not c.get("classicName"):
            ctx.err("CLASSIC-MATCH", f"/traits/{i}", f"status {st!r} needs classicName and classicText")
        tags = set(t.get("tags") or [])
        want = {"new": "new", "changed": "reworked", "same": "classic-unchanged"}.get(st)
        if want and want not in tags:
            ctx.warn("TAG-MISMATCH", f"/traits/{i}", f"status {st!r} but tags {sorted(tags)} lack {want!r}")


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
    for key in ("classesSource", "loreSource"):
        if isinstance(doc.get(key), dict):
            _check_source(ctx, doc[key], f"/{key}")
    for i, t in enumerate(doc.get("traits") or []):
        src = t.get("source") or {}
        _check_source(ctx, src, f"/traits/{i}/source")
        if src.get("panel") == "spellbook-general" and t.get("description"):
            ctx.warn("PANEL-DESCRIPTION", f"/traits/{i}",
                     "the spellbook General page shows no description, yet one is recorded")


def rule_9_files(ctx: Ctx, doc: dict) -> None:
    if ctx.no_files or ctx.root is None:
        return
    def check(rel: str, where: str) -> None:
        if rel and not (ctx.root / rel).is_file():
            ctx.err("MISSING-FILE", where, f"{rel} does not exist")
    for key in ("classesSource", "loreSource"):
        if isinstance(doc.get(key), dict):
            check(doc[key].get("crop") or "", f"/{key}/crop")
    for i, t in enumerate(doc.get("traits") or []):
        check((t.get("source") or {}).get("crop") or "", f"/traits/{i}/source/crop")
        if t.get("iconSource") == "crop":
            if not t.get("iconCrop"):
                ctx.err("ICON-CROP", f"/traits/{i}", "iconSource 'crop' needs iconCrop")
            else:
                check(t["iconCrop"], f"/traits/{i}/iconCrop")
        elif t.get("iconCrop"):
            ctx.err("ICON-CROP", f"/traits/{i}", "iconCrop without iconSource 'crop'")
        if t.get("icon") and t.get("iconSource") == "crop" and t["icon"] != f"crop-{t.get('id')}":
            ctx.warn("ICON-NAME", f"/traits/{i}", f"crop icons are named crop-<id>, found {t['icon']!r}")


def rule_10_complete(ctx: Ctx, doc: dict) -> None:
    if doc.get("complete") and not doc.get("traits"):
        ctx.err("COMPLETE-EMPTY", "/complete", "complete: true with no traits")
    if not doc.get("complete") and not any("scroll" in n or "not" in n for n in doc.get("notes") or []):
        ctx.warn("INCOMPLETE-UNEXPLAINED", "/notes", "complete: false but no note says what is missing")


def rule_11_lore(ctx: Ctx, doc: dict) -> None:
    if doc.get("lore") and doc.get("loreComplete") is None:
        ctx.err("LORE-COMPLETE", "/lore", "lore without loreComplete")
    if doc.get("lore") and not doc.get("loreSource"):
        ctx.err("LORE-SOURCE", "/lore", "lore without loreSource")
    for i, v in enumerate(doc.get("variants") or []):
        if v.get("lore") and v.get("loreComplete") is None:
            ctx.err("LORE-COMPLETE", f"/variants/{i}", "variant lore without loreComplete")


def rule_12_canonical(ctx: Ctx, doc: dict, raw: bytes, check: bool) -> None:
    canon = canonical_dumps(doc).encode("utf-8")
    if canon == raw:
        return
    msg = "file is not byte-identical to the canonical serializer output (re-run stage 12 build)"
    (ctx.err if check else ctx.warn)("NOT-CANONICAL", "/", msg)


def rule_13_confidence(ctx: Ctx, doc: dict) -> None:
    for i, t in enumerate(doc.get("traits") or []):
        src = t.get("source") or {}
        conf = src.get("confidence")
        if conf is not None and conf < REVIEW_THRESHOLD and not src.get("reviewed"):
            ctx.warn("NEEDS-REVIEW", f"/traits/{i}", f"confidence {conf} below {REVIEW_THRESHOLD}")
        if not src.get("reviewed"):
            ctx.result.queue.append({"trait": t.get("id"), "name": t.get("name"),
                                     "confidence": conf, "crop": src.get("crop"),
                                     "status": (t.get("classic") or {}).get("status")})


def rule_14_kind(ctx: Ctx, doc: dict) -> None:
    for i, t in enumerate(doc.get("traits") or []):
        if "(passive" in (t.get("name") or "").lower():
            ctx.warn("KIND-IN-NAME", f"/traits/{i}", "the '(Passive)' suffix belongs in kind, not in name")


def rule_15_counts(ctx: Ctx, doc: dict) -> None:
    n = len(doc.get("traits") or [])
    if doc.get("complete") and not 3 <= n <= 8:
        ctx.warn("TRAIT-COUNT", "/traits", f"{n} traits is outside the 3..8 every race showed on stream")


# ----------------------------------------------------------------------------
# Matrix rules
# ----------------------------------------------------------------------------

def matrix_rules(ctx: Ctx, doc: dict, root: Path | None) -> None:
    seen = set()
    for i, row in enumerate(doc.get("races") or []):
        race = row.get("race")
        if race in seen:
            ctx.err("DUPLICATE-RACE", f"/races/{i}", f"{race!r} twice")
        seen.add(race)
        if sorted(row.get("classes") or []) != list(row.get("classes") or []):
            ctx.err("CLASSES-UNSORTED", f"/races/{i}", "class ids must be sorted")
        if row.get("observed") != bool(row.get("classes")):
            ctx.err("OBSERVED", f"/races/{i}", "observed must be true exactly when classes is non-empty")
        by = row.get("byVariant") or {}
        if by:
            union = sorted({c for v in by.values() for c in v})
            if union != list(row.get("classes") or []):
                ctx.err("CLASSES-UNION", f"/races/{i}", "classes must be the union over byVariant")
        if root is None:
            continue
        f = root / "data" / "races" / f"{race}.json"
        if not f.is_file():
            ctx.err("MISSING-RACE-FILE", f"/races/{i}", f"data/races/{race}.json does not exist")
            continue
        rdoc = json.loads(f.read_text(encoding="utf-8"))
        if list(rdoc.get("classes") or []) != list(row.get("classes") or []):
            ctx.err("MATRIX-MISMATCH", f"/races/{i}",
                    f"matrix says {row.get('classes')}, {race}.json says {rdoc.get('classes')}")
        if rdoc.get("faction") != row.get("faction"):
            ctx.err("MATRIX-MISMATCH", f"/races/{i}", "faction differs from the race file")
    if root is not None:
        on_disk = {p.stem for p in (root / "data" / "races").glob("*.json")} - {"matrix"}
        missing = sorted(on_disk - seen)
        if missing:
            ctx.err("MATRIX-INCOMPLETE", "/races", f"race files not in the matrix: {missing}")


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------

def find_root(start: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).resolve()
    cur = start.resolve()
    for p in [cur, *cur.parents]:
        if (p / "data" / "schema" / "race.schema.json").is_file():
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
        ctx.err("NO-ROOT", "/", "cannot find the repository root (data/schema/race.schema.json)")
        return result
    name = "race-matrix.schema.json" if is_matrix(doc) else "race.schema.json"
    spath = root / "data" / "schema" / name
    if spath not in cache:
        cache[spath] = json.loads(spath.read_text(encoding="utf-8"))
    if not rule_1_schema(ctx, doc, cache[spath]):
        return result
    if is_matrix(doc):
        matrix_rules(ctx, doc, root)
        rule_12_canonical(ctx, doc, raw, opts.check)
        return result
    rule_2_ids(ctx, doc, path)
    rule_3_traits_unique(ctx, doc)
    rule_4_variants(ctx, doc)
    rule_5_classes(ctx, doc)
    rule_6_descriptions(ctx, doc)
    rule_7_classic(ctx, doc)
    rule_8_sources(ctx, doc)
    rule_9_files(ctx, doc)
    rule_10_complete(ctx, doc)
    rule_11_lore(ctx, doc)
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
                print(f"   {q['confidence']}  {q['trait']:28} {q['status']:8} {q['crop']}")
    errors = sum(r.count("ERROR") for r in results)
    warns = sum(r.count("WARN") for r in results)
    print(f"{len(results)} file(s): {errors} error(s), {warns} warning(s)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="race files (data/races/*.json, matrix.json included)")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--report", action="store_true", help="print the review queue")
    ap.add_argument("--check", action="store_true", help="fail unless the file is the canonical serializer output")
    ap.add_argument("--no-files", action="store_true", help="skip crop existence checks (rule R9)")
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

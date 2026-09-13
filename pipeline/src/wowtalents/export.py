"""Stage 8: candidates + overrides -> canonical class files (docs/DATA-SCHEMA.md sections 4-6).

Two steps, mirroring the schema doc:

* ``build_extracted``: ``data/extracted/<class>.candidates.json`` (one record per
  hover, brief section 1) -> ``data/extracted/<class>.json``. Pure pipeline
  output: slugs, trees, pages, provisional rules, prerequisites parsed from
  the tooltip strings, crop icons, video provenance, anticipated ranks
  (``wowtalents.ranks`` is run inline when a record has no
  ``ranks_anticipated`` block). No override is applied here, because
  ``overrides[].talent`` addresses the pre-rename id as it appears in
  ``extracted/`` (section 6.2).
* ``build_talents``: extracted + ``data/overrides/<class>.json`` + the existing
  ``data/talents/<class>.json`` -> canonical file (section 6.3): overrides in
  file order, reviewed records never overwritten (``REVIEWED-DIFF`` logged),
  ``source.readings`` stripped.

``write_validated`` serialises through ``validate.canonical_dumps``, runs the
validator on a temp file and only then renames it into place.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import shutil
import sys
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from rapidfuzz import fuzz

from . import fsio
from . import ranks as R

PIPELINE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = PIPELINE_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))
import validate  # noqa: E402  (pipeline/validate.py owns canonical_dumps and the rules)

SCHEMA_VERSION = 1
VIDEO_ID = "DxtVEhjyROU"
FPS = 60
DEFAULT_ROWS = 7
DEFAULT_COLS = 4
RULES_ASSUMED = {"pointsPerRow": 5, "maxPoints": 51, "firstPointLevel": 10, "maxLevel": 60, "rulesSource": "assumed"}
PAGE_NOTES = {"secondary": "Secondary tab was locked in all footage; meaning unconfirmed."}
REQ_NAME_THRESHOLD = 90.0

REQ_POINTS_RE = re.compile(r"^\s*Requires\s+(\d+)\s+points?\s+in\s+(.+?)\s*\.?\s*$", re.I)
REQ_RANK_RE = re.compile(r"^\s*Requires\s+(.+?)\s*\(\s*Rank\s+(\d+)\s*\)\s*\.?\s*$", re.I)


@dataclass
class Log:
    lines: list[str] = field(default_factory=list)

    def __call__(self, level: str, msg: str) -> None:
        self.lines.append(f"{level} {msg}")

    def warn(self, msg: str) -> None:
        self("WARNING", msg)

    def info(self, msg: str) -> None:
        self("INFO", msg)

    def errors(self) -> list[str]:
        return [l for l in self.lines if l.startswith("ERROR")]


def now_rfc3339() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def class_name(cls: str) -> str:
    return " ".join(w.capitalize() for w in cls.split("-"))


# ----------------------------------------------------------------------------
# candidates -> extracted
# ----------------------------------------------------------------------------

def load_candidates(path: Path) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return doc
    for key in ("candidates", "records", "talents"):
        if isinstance(doc.get(key), list):
            return doc[key]
    raise ValueError(f"{path}: expected a JSON array or an object with a 'candidates' list")


def default_tree_order(root: Path, cls: str) -> list[str]:
    """Tree names left-to-right from data/extracted/segments.json (probe stage), if present."""
    seg = root / "data" / "extracted" / "segments.json"
    if not seg.is_file():
        return []
    try:
        for s in json.loads(seg.read_text(encoding="utf-8")):
            if s.get("class") == cls and s.get("trees_visible"):
                return list(s["trees_visible"])
    except (ValueError, TypeError, AttributeError):
        pass
    return []


def dedupe(records: list[dict], log: Log) -> list[dict]:
    """One record per (page, tree, row, col): prefer not cut off, rank 0, higher confidence, earlier time."""
    best: dict[tuple, dict] = {}
    for rec in records:
        key = (str(rec.get("page") or "Primary"), str(rec.get("tree") or ""), int(rec.get("row", -1)), int(rec.get("col", -1)))
        src = rec.get("source") or {}
        rank = rec.get("rank") or {}
        score = (
            0 if rec.get("cut_off") else 1,
            0 if (rank.get("current") or 0) > 0 else 1,
            float(src.get("confidence") or 0.0),
            -float(src.get("t") or 0.0),
        )
        cur = best.get(key)
        if cur is None or score > cur[0]:
            if cur is not None:
                log.info(f"dedupe {key}: kept t={src.get('t')} over t={(cur[1].get('source') or {}).get('t')}")
            best[key] = (score, rec)
        else:
            log.info(f"dedupe {key}: dropped t={src.get('t')}")
    return [v[1] for v in best.values()]


def parse_requires(strings: list[str]) -> list[dict]:
    """'Requires 5 points in X' / 'Requires X (Rank 5)' -> [{name, points, tier: bool}]."""
    out = []
    for s in strings or []:
        s = R.clean_text(str(s))
        m = REQ_RANK_RE.match(s)
        if m:
            out.append({"name": m.group(1).strip(), "points": int(m.group(2)), "tier": False, "text": s})
            continue
        m = REQ_POINTS_RE.match(s)
        if m:
            target = m.group(2).strip()
            tier = bool(re.search(r"\bTalents$", target, re.I))
            if tier:
                target = re.sub(r"\s+Talents$", "", target, flags=re.I)
            out.append({"name": target, "points": int(m.group(1)), "tier": tier, "text": s})
            continue
        out.append({"name": None, "points": None, "tier": False, "text": s})
    return out


def _talent_id(name: str, row: int, col: int) -> str:
    s = R.slug(R.clean_text(name or ""))
    return s or f"crop-r{row}c{col}"


def _lookup(name: str, by_name: dict[str, str], names: list[tuple[str, str]]) -> str | None:
    key = R.slug(name)
    if key in by_name:
        return by_name[key]
    best, score = None, 0.0
    for n, tid in names:
        s = float(fuzz.token_ratio(name, n))
        if s > score:
            best, score = tid, s
    return best if score >= REQ_NAME_THRESHOLD else None


def build_extracted(cls: str, records: list[dict], prior: R.Prior | None, *, root: Path = REPO_ROOT,
                    video: str = VIDEO_ID, fps: int = FPS, tree_order: list[str] | None = None,
                    generated_at: str | None = None, copy_crops: bool = True, data_version: int | None = None,
                    log: Log | None = None) -> dict:
    log = log if log is not None else Log()
    records = dedupe([r for r in records if r.get("class", cls) == cls], log)
    if not records:
        raise ValueError(f"no candidate records for class {cls!r}")

    # ranks (stage 6 inline when missing)
    for rec in records:
        ra = rec.get("ranks_anticipated")
        if not (isinstance(ra, dict) and ra.get("ranksSource")):
            rec["ranks_anticipated"] = R.anticipate_record(rec, prior).to_fields()

    # pages and trees
    order_names = tree_order if tree_order is not None else default_tree_order(root, cls)
    page_ids: "OrderedDict[str, str]" = OrderedDict()
    trees: "OrderedDict[str, dict]" = OrderedDict()
    for rec in records:
        page_name = R.clean_text(str(rec.get("page") or "Primary"))
        pid = R.slug(page_name)
        page_ids.setdefault(pid, page_name)
        tree_name = R.clean_text(str(rec.get("tree") or ""))
        if not tree_name:
            log.warn(f"record {rec.get('name')!r} at r{rec.get('row')}c{rec.get('col')} has no tree; skipped")
            continue
        tid = R.slug(tree_name)
        tree = trees.setdefault(tid, {"id": tid, "name": tree_name, "page": pid, "records": []})
        tree["records"].append(rec)

    def tree_sort_key(t: dict) -> tuple:
        try:
            return (0, [R.slug(n) for n in order_names].index(t["id"]))
        except ValueError:
            return (1, list(trees).index(t["id"]))

    per_page: Counter = Counter()
    ordered_trees = sorted(trees.values(), key=tree_sort_key)
    for t in ordered_trees:
        t["order"] = per_page[t["page"]]
        per_page[t["page"]] += 1

    # talent ids with the section-3 collision rule
    ids_by_tree: dict[str, list[str]] = {}
    for t in ordered_trees:
        ids_by_tree[t["id"]] = [_talent_id(r.get("name") or "", int(r.get("row", 0)), int(r.get("col", 0))) for r in t["records"]]
    tree_of: dict[str, set[str]] = {}
    for tid, ids in ids_by_tree.items():
        for i in ids:
            tree_of.setdefault(i, set()).add(tid)
    seen: set[str] = set()
    for t in ordered_trees:
        final = []
        for i in ids_by_tree[t["id"]]:
            fid = f"{i}-{t['id']}" if len(tree_of[i]) > 1 else i
            if fid in seen:
                rec = t["records"][len(final)]
                alt = f"{fid}-r{rec.get('row')}c{rec.get('col')}"
                log.warn(f"{cls}/{t['id']}: duplicate talent id {fid!r} inside one tree; using {alt!r}")
                fid = alt
            seen.add(fid)
            final.append(fid)
        ids_by_tree[t["id"]] = final

    # talents
    out_trees = []
    for t in ordered_trees:
        ids = ids_by_tree[t["id"]]
        by_name = {R.slug(R.clean_text(r.get("name") or "")): i for r, i in zip(t["records"], ids) if r.get("name")}
        names = [(R.clean_text(r.get("name") or ""), i) for r, i in zip(t["records"], ids) if r.get("name")]
        rows_of = {i: int(r.get("row", 0)) for r, i in zip(t["records"], ids)}
        id_at = {(int(r.get("row", 0)), int(r.get("col", 0))): i for r, i in zip(t["records"], ids)}
        talents = []
        for rec, tid in zip(t["records"], ids):
            talents.append(_talent(cls, t, rec, tid, by_name, names, rows_of, root, video, fps, copy_crops, log, id_at))
        talents.sort(key=lambda x: (x["row"], x["col"]))
        rows = max(DEFAULT_ROWS, max(x["row"] for x in talents) + 1)
        cols = max(DEFAULT_COLS, max(x["col"] for x in talents) + 1)
        tree_doc = {"id": t["id"], "name": t["name"], "page": t["page"], "order": t["order"],
                    "icon": f"crop-{t['id']}", "rows": rows, "cols": cols}
        header = root / "data" / "review" / cls / t["id"] / "_header.png"
        hdr_src = next((r.get("tree_source") for r in t["records"] if isinstance(r.get("tree_source"), dict)), None)
        if hdr_src and header.is_file():
            tree_doc["source"] = _video_source(hdr_src, f"data/review/{cls}/{t['id']}/_header.png", video, fps)
        tree_doc["talents"] = talents
        out_trees.append(tree_doc)

    pages = []
    for pid, pname in page_ids.items():
        page = {"id": pid, "name": pname}
        if pid in PAGE_NOTES:
            page["note"] = PAGE_NOTES[pid]
        pages.append(page)

    doc = {
        "$schema": "../schema/class.schema.json",
        "schemaVersion": SCHEMA_VERSION,
        "class": cls,
        "className": class_name(cls),
        "dataVersion": data_version if data_version is not None else highest_encoding_version(root),
        "dataSource": "video",
        "generatedAt": generated_at or now_rfc3339(),
        "rules": dict(RULES_ASSUMED),
        "pages": pages,
        "trees": out_trees,
        "notes": ["Extracted from BlizzCon 2026 stream footage (rank-0 tooltips only); ranks 2+ are anticipated, "
                  "point rules assumed from Classic."],
    }
    return validate.order_class_doc(doc)


def _video_source(src: dict, crop_rel: str, video: str, fps: int) -> dict:
    t = float(src.get("t") or 0.0)
    frame = src.get("frame_index", src.get("frame"))
    out: dict[str, Any] = {
        "kind": "video",
        "video": src.get("video") or video,
        "t": round(t, 3),
        "frame": int(frame) if isinstance(frame, (int, float)) else int(round(t * fps)),
        "crop": crop_rel,
        "confidence": float(src.get("confidence") if src.get("confidence") is not None else 0.0),
        "reader": str(src.get("reader") or "unknown"),
    }
    readings = [r for r in (src.get("readings") or []) if isinstance(r, dict)]
    if readings:
        # schema: reading.maxRank is an integer when present; a reading without a Rank line omits it
        out["readings"] = [{k: r[k] for k in ("reader", "name", "description", "maxRank", "confidence")
                            if k in r and r[k] is not None} for r in readings]
    out["reviewed"] = False
    if src.get("note"):
        out["note"] = str(src["note"])
    return out


def _place_crop(src_path: str | None, dest_rel: str, root: Path, copy_crops: bool, log: Log, what: str) -> bool:
    dest = root / dest_rel
    if dest.is_file():
        return True
    if not copy_crops or not src_path:
        log.warn(f"{what}: crop {dest_rel} missing and no source path to copy from")
        return False
    src = Path(src_path)
    if not src.is_absolute():
        src = PIPELINE_DIR / src
    if not src.is_file():
        log.warn(f"{what}: crop source {src_path} not found; {dest_rel} not written")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return True


ARROW_NOTE = "prerequisite from tree arrow (stage 7): {name} at rank {rank} = its max rank (Classic rule; rank-0 tooltips do not list talent prerequisites)"


def merge_arrow_requires(rec: dict, path: str, requires: list[dict], rows_of: dict, id_at: dict[tuple[int, int], str],
                         notes: list[str], log: Log) -> None:
    """Add the arrow-derived prerequisites of ``rec`` (``requires_arrows`` from stage 7) to ``requires``.

    A tooltip-derived requirement is never overwritten: when the tooltip names the same
    target with another rank the tooltip's rank stays, and when the tooltip names other
    targets only, the arrow is dropped; both are logged as ``ARROW-CONFLICT`` and noted.
    Same-row (horizontal) arrows are real in Forever and are stored like any other
    (schema rule 8: the target must be in the same row or above, and in another cell).
    An arrow from a *later* row, or one whose target cell has no record, goes to
    ``source.note`` only.
    """
    tooltip_targets = {r["talent"] for r in requires}
    for arrow in rec.get("requires_arrows") or []:
        row, col = int(arrow.get("row", -1)), int(arrow.get("col", -1))
        name = str(arrow.get("name") or f"r{row}c{col}")
        rank = int(arrow.get("rank") or 1)
        target = id_at.get((row, col))
        if target is None:
            log.warn(f"{path}: arrow from cell r{row}c{col} has no talent record; kept as a note")
            notes.append(f"unresolved prerequisite arrow from r{row}c{col} ({name})")
            continue
        if rows_of.get(target, 0) > int(rec.get("row", 0)):
            log.warn(f"{path}: arrow from {target!r} points up from a later row; kept as a note")
            notes.append(f"prerequisite arrow from {name} (rank {rank}) in a later row; not representable")
            continue
        if tooltip_targets and target not in tooltip_targets:
            log.warn(f"{path}: ARROW-CONFLICT arrow from {target!r} but the tooltip requires {sorted(tooltip_targets)}; tooltip kept")
            notes.append(f"arrow conflict: tree arrow from {name} (rank {rank}), tooltip names another talent; tooltip kept")
            continue
        if target in tooltip_targets:
            cur = next(r for r in requires if r["talent"] == target)
            if cur["rank"] != rank:
                log.warn(f"{path}: ARROW-CONFLICT arrow says {target!r} rank {rank}, tooltip says rank {cur['rank']}; tooltip kept")
                notes.append(f"arrow conflict: tree arrow implies {name} rank {rank}, tooltip says rank {cur['rank']}; tooltip kept")
            else:
                log.info(f"{path}: arrow from {target!r} confirms the tooltip requirement")
            continue
        requires.append({"talent": target, "rank": rank})
        notes.append(ARROW_NOTE.format(name=name, rank=rank))
        if float(arrow.get("confidence") or 0.0) < 0.8:
            notes.append(f"arrow confidence {float(arrow.get('confidence') or 0.0):.2f}")


def _talent(cls: str, tree: dict, rec: dict, tid: str, by_name: dict, names: list, rows_of: dict, root: Path,
            video: str, fps: int, copy_crops: bool, log: Log, id_at: dict[tuple[int, int], str] | None = None) -> dict:
    path = f"{cls}/{tree['id']}/{tid}"
    name = R.clean_text(rec.get("name") or "") or f"Unread r{rec.get('row')}c{rec.get('col')}"
    rank = rec.get("rank") or {}
    max_rank = int(rank.get("max") or rec.get("rank_max") or 1)
    if (rank.get("current") or 0) > 0:
        log.warn(f"{path}: hover shows rank {rank.get('current')}/{max_rank}; text may not be rank 1")
    ra = rec["ranks_anticipated"]
    src = rec.get("source") or {}
    notes: list[str] = []
    if src.get("note"):
        notes.append(str(src["note"]))

    crop_rel = f"data/review/{cls}/{tree['id']}/{tid}.png"
    _place_crop(src.get("crop_path"), crop_rel, root, copy_crops, log, path)
    # stage 9 (icon matching) writes icon / icon_source into the candidate record; once it has,
    # the record keeps no iconCrop, so copying the icon crop here would only create an orphan
    # under data/review/ (405 such files were being globbed into the web bundle and deployed)
    matched_icon = bool(rec.get("icon")) and rec.get("icon_source") in ("classic", "datamined", "manual")
    icon_rel = f"data/review/{cls}/{tree['id']}/{tid}.icon.png"
    if matched_icon:
        icon_rel = None
    elif not _place_crop(src.get("icon_crop_path"), icon_rel, root, copy_crops, Log(), path):
        icon_rel = crop_rel  # no icon crop yet: the tooltip crop stands in (both are provisional)

    requires = []
    for req in parse_requires(rec.get("requires") or []):
        if req["name"] is None:
            log.warn(f"{path}: unparsed requirement {req['text']!r}")
            notes.append(f"unparsed requirement: {req['text']}")
            continue
        if req["tier"]:
            if R.slug(req["name"]) != tree["id"]:
                log.warn(f"{path}: tier requirement names tree {req['name']!r}, talent sits in {tree['name']!r}")
            expected_row = req["points"] // RULES_ASSUMED["pointsPerRow"]
            if expected_row != int(rec.get("row", 0)):
                log.warn(f"{path}: '{req['text']}' implies row {expected_row}, detected row {rec.get('row')}")
            continue
        target = _lookup(req["name"], by_name, names)
        if target is None or target == tid:
            log.warn(f"{path}: requirement target {req['name']!r} not found in tree {tree['id']!r}")
            notes.append(f"unresolved requirement: {req['text']}")
            continue
        if rows_of.get(target, 0) >= int(rec.get("row", 0)):
            log.warn(f"{path}: requirement target {target!r} is not in an earlier row")
        requires.append({"talent": target, "rank": int(req["points"])})
    merge_arrow_requires(rec, path, requires, rows_of, id_at or {}, notes, log)

    t: dict[str, Any] = {
        "id": tid,
        "name": name,
        "row": int(rec.get("row", 0)),
        "col": int(rec.get("col", 0)),
        "maxRank": max_rank,
        "icon": f"crop-{tid}",
        "iconSource": "crop",
        "description": ra["description"],
        "ranks": ra["ranks"],
        # normally [1] (only rank-0 tooltips exist), but a crop taken with points already spent
        # reports the rank it actually shows - see ranks.anticipate's observed_rank guard
        "ranksObserved": list(ra.get("ranksObserved") or [1]),
        "ranksSource": ra["ranksSource"],
    }
    if matched_icon:
        t["icon"] = str(rec["icon"]).lower()
        t["iconSource"] = str(rec["icon_source"])   # schema: iconCrop iff iconSource == "crop"
    else:
        t["iconCrop"] = icon_rel
    if "ranksPrior" in ra:
        t["ranksPrior"] = ra["ranksPrior"]
    if ra.get("ranksNote"):
        t["ranksNote"] = ra["ranksNote"]
    if requires:
        t["requires"] = requires[:3]
        if len(requires) > 3:
            log.warn(f"{path}: {len(requires)} requirements, keeping 3")
    if rec.get("cut_off"):
        notes.append("tooltip text cut off at the crop edge")
    source = _video_source(src, crop_rel, video, fps)
    if notes:
        source["note"] = "; ".join(notes)
    t["source"] = source
    return t


# ----------------------------------------------------------------------------
# overrides and promotion (section 6.2 / 6.3)
# ----------------------------------------------------------------------------

def _index(doc: dict) -> dict[tuple[str, str], dict]:
    return {(tree["id"], t["id"]): t for tree in doc["trees"] for t in tree["talents"]}


def _reading_of(t: dict) -> dict:
    src = t.get("source") or {}
    return {"reader": str(src.get("reader") or src.get("kind") or "pipeline"), "name": t.get("name"),
            "description": t.get("description"), "maxRank": t.get("maxRank"), "confidence": src.get("confidence", 0.0)}


def apply_overrides(doc: dict, overrides: dict | None, log: Log) -> set[str]:
    """Apply data/overrides/<class>.json in file order. Returns the set of talent ids touched (post-rename)."""
    doc_trees = {tree["id"]: tree for tree in doc["trees"]}
    touched: set[str] = set()
    if not overrides:
        return touched
    for i, o in enumerate(overrides.get("overrides") or []):
        tree = doc_trees.get(o.get("tree"))
        label = f"overrides[{i}] {o.get('tree')}/{o.get('talent')}"
        if tree is None:
            log.warn(f"{label}: tree not in extracted file; skipped")
            continue
        talents = tree["talents"]
        target = next((t for t in talents if t["id"] == o.get("talent")), None)
        if "add" in o:
            if target is not None:
                log.warn(f"{label}: add for an existing talent; replaced")
                talents.remove(target)
            new = copy.deepcopy(o["add"])
            new.setdefault("id", o["talent"])
            _mark_reviewed(new, o)
            talents.append(new)
            touched.add(new["id"])
            continue
        if target is None:
            log.warn(f"{label}: talent not in extracted file; skipped")
            continue
        if o.get("delete") is True:
            talents.remove(target)
            touched.add(target["id"])
            continue
        before = _reading_of(target)
        for field_name in o.get("unset") or []:
            # section 6.2 "Deleting a field": unset runs before set, so set wins on a field in both.
            # A shallow merge can only add or replace, so this is the only way to drop a wrong
            # `requires` arrow or a stale ranksNote. Unsetting an absent field is a no-op.
            if field_name not in validate.UNSETTABLE:
                log.warn(f"{label}: unset {field_name!r} is not an optional field; ignored")
                continue
            if field_name.startswith("source."):
                (target.get("source") or {}).pop(field_name.split(".", 1)[1], None)
            else:
                target.pop(field_name, None)
        if "set" in o:
            for k, v in o["set"].items():
                if k == "source" and isinstance(v, dict):
                    target.setdefault("source", {}).update(copy.deepcopy(v))
                else:
                    target[k] = copy.deepcopy(v)
            # a rank-source switch must keep the iff-fields consistent
            if target.get("ranksSource") != "classic-prior":
                target.pop("ranksPrior", None)
        if "rename" in o:
            new_id = o["rename"]
            old_id = target["id"]
            target["id"] = new_id
            if target.get("iconSource") == "crop":
                target["icon"] = f"crop-{new_id}"
            for t in talents:
                for req in t.get("requires") or []:
                    if req["talent"] == old_id:
                        req["talent"] = new_id
        src = target.setdefault("source", {})
        readings = src.setdefault("readings", [])
        if before not in readings and (before["name"] != target.get("name") or before["description"] != target.get("description")
                                       or before["maxRank"] != target.get("maxRank")):
            readings.append(before)
        if not readings:
            src.pop("readings", None)
        _mark_reviewed(target, o)
        touched.add(target["id"])
    for tree in doc["trees"]:
        tree["talents"].sort(key=lambda t: (t["row"], t["col"]))
    return touched


def _mark_reviewed(t: dict, o: dict) -> None:
    src = t.setdefault("source", {})
    src["reviewed"] = True
    src["reviewedBy"] = o.get("by") or "unknown"
    src["reviewedAt"] = o.get("at") or now_rfc3339()


def strip_readings(doc: dict) -> None:
    for tree in doc["trees"]:
        if isinstance(tree.get("source"), dict):
            tree["source"].pop("readings", None)
        for t in tree["talents"]:
            t.get("source", {}).pop("readings", None)


def _diff(a: dict, b: dict) -> list[str]:
    keys = sorted(set(a) | set(b))
    return [k for k in keys if k != "source" and a.get(k) != b.get(k)]


def build_talents(extracted: dict, overrides: dict | None, existing: dict | None, log: Log,
                  generated_at: str | None = None) -> dict:
    """Section 6.3: apply overrides, keep reviewed records of the existing canonical file, strip readings."""
    doc = copy.deepcopy(extracted)
    touched = apply_overrides(doc, overrides, log)
    if existing:
        old = _index(existing)
        new = _index(doc)
        doc_trees = {tree["id"]: tree for tree in doc["trees"]}
        for (tree_id, tid), old_t in old.items():
            if not (old_t.get("source") or {}).get("reviewed"):
                continue
            if tid in touched:
                # the override re-applies over the new extraction (section 6.3 step 2); say so when
                # that changes an already reviewed record, e.g. an empty "accepted as read" set
                cur = new.get((tree_id, tid))
                changed = _diff(old_t, cur) if cur else ["(deleted)"]
                if changed:
                    log.warn(f"REVIEWED-DIFF {tree_id}/{tid}: override re-applied over a new reading; differs in {changed}")
                continue
            tree = doc_trees.get(tree_id)
            if tree is None:
                log.warn(f"REVIEWED-DIFF {tree_id}/{tid}: reviewed talent's tree is gone from the extracted file; kept anyway")
                tree = {"id": tree_id, "name": tree_id, "page": doc["pages"][0]["id"], "order": len(doc["trees"]),
                        "icon": f"crop-{tree_id}", "rows": DEFAULT_ROWS, "cols": DEFAULT_COLS, "talents": []}
                doc["trees"].append(tree)
                doc_trees[tree_id] = tree
            cur = new.get((tree_id, tid))
            if cur is None:
                log.warn(f"REVIEWED-DIFF {tree_id}/{tid}: no longer extracted; reviewed record kept")
                tree["talents"].append(copy.deepcopy(old_t))
            else:
                changed = _diff(old_t, cur)
                if changed:
                    log.warn(f"REVIEWED-DIFF {tree_id}/{tid}: pipeline now differs in {changed}; reviewed record kept")
                tree["talents"][tree["talents"].index(cur)] = copy.deepcopy(old_t)
        for tree in doc["trees"]:
            tree["talents"].sort(key=lambda t: (t["row"], t["col"]))
    strip_readings(doc)
    doc["generatedAt"] = generated_at or now_rfc3339()
    return validate.order_class_doc(doc)


# ----------------------------------------------------------------------------
# encoding helpers, validation, writing
# ----------------------------------------------------------------------------

def highest_encoding_version(root: Path) -> int:
    versions = validate._encoding_versions(root)
    return max(versions) if versions else 1


def class_encoding_entry(doc: dict) -> dict:
    """This class's ``{trees, order}`` block: pages flattened, talents row-major (schema section 8)."""
    page_rank = {p["id"]: i for i, p in enumerate(doc["pages"])}
    trees = sorted(doc["trees"], key=lambda t: (page_rank.get(t["page"], 99), t["order"]))
    return {
        "trees": [t["id"] for t in trees],
        "order": {t["id"]: [x["id"] for x in sorted(t["talents"], key=lambda x: (x["row"], x["col"]))] for t in trees},
    }


def _fork_frozen(root: Path, path: Path, enc: dict, log: Log) -> tuple[Path, dict]:
    """A frozen v<N> is published: copy it to v<N+1> and leave every minted digit alone.

    This is the guard for the failure the version mechanism exists to prevent: v1 was
    rewritten in place four times, and inserting a recovered talent into ``order`` shifted
    every digit after it, so shared ``?v=1&t=...`` links silently decoded to other talents.
    """
    n = int(enc.get("version") or 1)
    new_path = path.with_name(f"v{n + 1}.json")
    if new_path.exists():
        raise FileExistsError(f"{path.name} is frozen and {new_path.name} already exists; "
                              f"set dataVersion to {n + 1} and re-run, or unfreeze deliberately")
    new_enc = copy.deepcopy(enc)
    new_enc["version"] = n + 1
    new_enc["createdAt"] = now_rfc3339()
    new_enc["frozen"] = False
    new_enc["note"] = (f"Forked from v{n}.json by 08_export --update-encoding because v{n} is frozen. "
                       f"Fill in migrations/v{n}-v{n + 1}.json and set dataVersion to {n + 1} in every class file.")
    mig = root / "data" / "encoding" / "migrations" / f"v{n}-v{n + 1}.json"
    if not mig.is_file():
        mig.parent.mkdir(parents=True, exist_ok=True)
        fsio.write_json_atomic(mig, {"from": n, "to": n + 1, "classes": {}})
        log.warn(f"encoding: wrote an empty migration {mig.name}; fill in renamed/removed/moved before publishing")
    log.warn(f"encoding: v{n}.json is frozen; created {new_path.name} instead. Every data/talents/*.json and "
             f"data/examples/*.json must move to dataVersion {n + 1} before the validator passes again.")
    return new_path, new_enc


def update_encoding(root: Path, doc: dict, log: Log) -> Path:
    """Upsert this class into the highest ``data/encoding/v<N>.json``.

    A version file carrying ``"frozen": true`` is published and immutable
    (``data/encoding/README.md`` rule 1): this refuses to touch it and forks v<N+1>.
    """
    versions = validate._encoding_versions(root)
    if not versions:
        enc_dir = root / "data" / "encoding"
        enc_dir.mkdir(parents=True, exist_ok=True)
        path = enc_dir / "v1.json"
        enc = {"version": 1, "createdAt": now_rfc3339(), "note": "created by 08_export", "frozen": False, "classes": {}}
    else:
        path = versions[max(versions)]
        enc = json.loads(path.read_text(encoding="utf-8"))
    entry = class_encoding_entry(doc)
    if enc.get("frozen"):
        if (enc.get("classes") or {}).get(doc["class"]) == entry:
            log.info(f"encoding {path.name}: frozen, class {doc['class']} entry already identical; nothing to do")
            doc["dataVersion"] = enc["version"]
            return path
        path, enc = _fork_frozen(root, path, enc, log)
    enc.setdefault("classes", {})[doc["class"]] = entry
    fsio.write_json_atomic(path, enc)
    log.info(f"encoding {path.name}: class {doc['class']} entry updated")
    doc["dataVersion"] = enc["version"]
    return path


def referenced_crops(doc: dict) -> set[str]:
    """Every ``data/review/`` path one class document points at: tooltip crops, icon crops, tree headers."""
    out: set[str] = set()
    for tree in doc.get("trees") or []:
        src = tree.get("source") or {}
        if src.get("crop"):
            out.add(str(src["crop"]))
        for t in tree.get("talents") or []:
            if t.get("iconCrop"):
                out.add(str(t["iconCrop"]))
            if (t.get("source") or {}).get("crop"):
                out.add(str(t["source"]["crop"]))
    return out


#: Subtrees of ``data/review/`` that belong to another pipeline and are therefore not
#: this one's to prune. ``races/`` is stage 12's, validated by ``validate_races.py``
#: (rule R9), which checks those crops against ``data/races/*.json`` instead.
FOREIGN_REVIEW_DIRS = ("races", "spells")


def orphan_crops(root: Path, docs: Iterable[dict]) -> list[Path]:
    """PNGs under ``data/review/`` that no class document references any more.

    Stage 9 switches a talent to ``iconSource: "classic"`` and drops its ``iconCrop``; the
    file stays behind. 405 such files (1.0 MB) were still being globbed into the web bundle
    and deployed. Tooltip crops named in ``source.crop`` are provenance and are never orphans.
    Subtrees in :data:`FOREIGN_REVIEW_DIRS` are skipped entirely.
    """
    review = root / "data" / "review"
    if not review.is_dir():
        return []
    keep: set[str] = set()
    for doc in docs:
        keep |= referenced_crops(doc)
    return sorted(p for p in review.rglob("*.png")
                  if p.relative_to(review).parts[0] not in FOREIGN_REVIEW_DIRS
                  and str(p.relative_to(root)) not in keep)


def prune_review_crops(root: Path, docs: Iterable[dict], log: Log, *, dry_run: bool = False) -> list[Path]:
    """Delete the orphans; returns what was (or would be) removed."""
    gone = orphan_crops(root, docs)
    for p in gone:
        log.info(f"{'would remove' if dry_run else 'removed'} orphan crop {p.relative_to(root)}")
        if not dry_run:
            p.unlink(missing_ok=True)
    if gone:
        kb = sum(1 for _ in gone)
        log.warn(f"data/review: {kb} orphaned crop(s) {'would be' if dry_run else ''} removed")
    return gone


def run_validator(path: Path, root: Path, *, check: bool = False, no_files: bool = False, strict: bool = False):
    opts = validate.argparse.Namespace(files=[str(path)], strict=strict, json=False, report=False, overrides=False,
                                       check=check, no_files=no_files, root=str(root))
    return validate.validate_path(path, opts, {}, {})


def write_validated(doc: dict, dest: Path, root: Path, log: Log, *, check: bool = True, no_files: bool = False,
                    strict: bool = False) -> bool:
    """Serialize canonically, validate a temp copy, rename into place. False (nothing written) on errors.

    The validator takes the file kind from the parent directory name and the class from the stem,
    so the temp copy lives at ``<dest dir>/.export-tmp/<kind>/<class>.json``.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_root = dest.parent / ".export-tmp"
    probe = tmp_root / dest.parent.name / dest.name
    probe.parent.mkdir(parents=True, exist_ok=True)
    try:
        probe.write_text(validate.canonical_dumps(doc), encoding="utf-8")
        result = run_validator(probe, root, check=check, no_files=no_files, strict=strict)
        for f in sorted(result.findings, key=lambda f: (validate.LEVEL_ORDER.get(f.level, 9), f.path, f.code)):
            log(f.level, f"{f.code} {f.path}: {f.message}")
        if result.count("ERROR"):
            log("ERROR", f"{dest.name}: {result.count('ERROR')} validation error(s); file not written")
            return False
        os.replace(probe, dest)
        return True
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

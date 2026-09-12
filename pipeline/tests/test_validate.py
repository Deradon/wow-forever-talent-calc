"""Tests for pipeline/validate.py (run: cd pipeline && uv run pytest)."""

from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parent
sys.path.insert(0, str(PIPELINE))

import validate  # noqa: E402

EXAMPLE = REPO / "data" / "examples" / "tinker.json"
SCHEMA = REPO / "data" / "schema" / "class.schema.json"
ENCODING_V1 = REPO / "data" / "encoding" / "v1.json"


@pytest.fixture
def example() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def make_repo(tmp_path: Path, doc: dict, *, encoding: dict | None = None, subdir: str = "extracted") -> Path:
    """Build a throw-away repo root with schema, encoding, crops and one class file."""
    root = tmp_path / "repo"
    (root / "data" / "schema").mkdir(parents=True)
    shutil.copy(SCHEMA, root / "data" / "schema" / "class.schema.json")
    (root / "data" / "encoding" / "migrations").mkdir(parents=True)
    enc = encoding if encoding is not None else json.loads(ENCODING_V1.read_text(encoding="utf-8"))
    (root / "data" / "encoding" / "v1.json").write_text(json.dumps(enc, indent=2) + "\n")
    for tree in doc["trees"]:
        crops = [tree["source"]["crop"]] if tree.get("source", {}).get("crop") else []
        for t in tree["talents"]:
            if t["source"].get("crop"):
                crops.append(t["source"]["crop"])
            if "iconCrop" in t:
                crops.append(t["iconCrop"])
        for c in crops:
            p = root / c
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"\x89PNG placeholder")
    target = root / "data" / subdir / f"{doc['class']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(validate.canonical_dumps(doc), encoding="utf-8")
    return target


def run(path: Path, *args: str) -> tuple[int, list[validate.Finding]]:
    opts = validate.main.__globals__["argparse"].Namespace(
        files=[str(path)], strict="--strict" in args, json=False, report=False,
        overrides="--overrides" in args, check="--check" in args, no_files="--no-files" in args, root=None,
    )
    result = validate.validate_path(path, opts, {}, {})
    errors = [f for f in result.findings if f.level == "ERROR"]
    return (1 if errors else 0), result.findings


def codes(findings: list[validate.Finding], level: str | None = None) -> set[str]:
    return {f.code for f in findings if level is None or f.level == level}


def test_repo_example_is_valid():
    """The committed example must validate in place (crops, encoding v1)."""
    code = validate.main([str(EXAMPLE), "--check"])
    assert code == 0


def test_valid_example_in_tmp_repo(tmp_path, example):
    path = make_repo(tmp_path, example)
    code, findings = run(path, "--check")
    assert code == 0, codes(findings, "ERROR")
    assert not codes(findings, "ERROR")
    # content warnings of the minimal example are expected but no errors
    assert "NEEDS-REVIEW" in codes(findings, "WARNING")


def test_duplicate_cell(tmp_path, example):
    doc = copy.deepcopy(example)
    gadgetry = doc["trees"][0]["talents"]
    gadgetry[1]["row"], gadgetry[1]["col"] = gadgetry[0]["row"], gadgetry[0]["col"]
    code, findings = run(make_repo(tmp_path, doc))
    assert code == 1
    assert "R05-CELL-DUP" in codes(findings, "ERROR")


def test_prerequisite_in_later_row(tmp_path, example):
    doc = copy.deepcopy(example)
    talents = {t["id"]: t for t in doc["trees"][0]["talents"]}
    # rocket-boots (row 2) requires improved-wrench (row 0); move the target below it
    talents["improved-wrench"]["row"] = 5
    code, findings = run(make_repo(tmp_path, doc))
    assert code == 1
    assert "R08-ROW" in codes(findings, "ERROR")


def test_prerequisite_unknown_and_rank_too_high(tmp_path, example):
    doc = copy.deepcopy(example)
    talents = {t["id"]: t for t in doc["trees"][0]["talents"]}
    talents["rocket-boots"]["requires"] = [{"talent": "volatile-mixture", "rank": 1}, {"talent": "steady-hands", "rank": 9}]
    _, findings = run(make_repo(tmp_path, doc))
    assert {"R08-TARGET", "R08-RANK"} <= codes(findings, "ERROR")


def test_missing_class_in_encoding_file(tmp_path, example):
    enc = json.loads(ENCODING_V1.read_text(encoding="utf-8"))
    enc["classes"] = {}
    code, findings = run(make_repo(tmp_path, example, encoding=enc))
    assert code == 1
    assert "R11-ENCODING-CLASS" in codes(findings, "ERROR")


def test_encoding_id_set_mismatch(tmp_path, example):
    enc = json.loads(ENCODING_V1.read_text(encoding="utf-8"))
    enc["classes"]["tinker"]["order"]["gadgetry"].append("ghost-talent")
    _, findings = run(make_repo(tmp_path, example, encoding=enc))
    assert "R11-ENCODING-IDS" in codes(findings, "ERROR")


def test_schema_rejects_conditional_fields(tmp_path, example):
    doc = copy.deepcopy(example)
    t = doc["trees"][0]["talents"][0]  # improved-wrench, iconSource classic
    t["iconCrop"] = "data/review/tinker/gadgetry/x.png"
    t["source"]["build"] = "1.60.1.69704"  # only for datamined
    code, findings = run(make_repo(tmp_path, doc), "--no-files")
    assert code == 1
    assert "R01-SCHEMA" in codes(findings, "ERROR")


def test_ranks_length_and_placeholders(tmp_path, example):
    doc = copy.deepcopy(example)
    t = doc["trees"][0]["talents"][1]  # steady-hands, maxRank 5, one placeholder
    t["ranks"] = [[1], [2, 3], [3], [4]]
    t["description"] = "Increases your chance to hit with Gadgets by {1}%."
    _, findings = run(make_repo(tmp_path, doc))
    assert {"R06-RANKS-LEN", "R06-SLOTS", "R06-PLACEHOLDERS"} <= codes(findings, "ERROR")


def test_observed_iff_all_ranks(tmp_path, example):
    doc = copy.deepcopy(example)
    t = doc["trees"][0]["talents"][1]  # steady-hands, classic-prior, observed [1]
    t["ranksObserved"] = [1, 2, 3, 4, 5]
    _, findings = run(make_repo(tmp_path, doc))
    assert "R07-OBSERVED-IFF" in codes(findings, "ERROR")


def test_strict_turns_warnings_into_errors(tmp_path, example):
    code, findings = run(make_repo(tmp_path, example), "--strict")
    assert code == 1
    assert not codes(findings, "WARNING")


def test_canonical_serializer_is_idempotent(example):
    once = validate.canonical_dumps(example)
    twice = validate.canonical_dumps(json.loads(once))
    assert once == twice
    assert once.endswith("\n")
    # talents sorted by (row, col) and key order per schema doc
    doc = json.loads(once)
    for tree in doc["trees"]:
        cells = [(t["row"], t["col"]) for t in tree["talents"]]
        assert cells == sorted(cells)
        for t in tree["talents"]:
            keys = [k for k in validate.KEY_ORDER["talent"] if k in t]
            assert list(t) == keys


def test_canonical_file_rejects_readings(tmp_path, example):
    """The example is an extracted-style record (steady-hands keeps readings); talents/ must not."""
    path = make_repo(tmp_path, example, subdir="talents")
    code, findings = run(path)
    assert code == 1
    assert codes(findings, "ERROR") == {"R12-READINGS"}


def test_non_canonical_talents_file_fails_check(tmp_path, example):
    path = make_repo(tmp_path, example)
    path.write_text(json.dumps(example, indent=4), encoding="utf-8")
    code, findings = run(path, "--check")
    assert code == 1
    assert "R12-NOT-CANONICAL" in codes(findings, "ERROR")


def _overrides_file(root: Path, overrides: list[dict]) -> Path:
    ovr = {"schemaVersion": 1, "class": "tinker", "overrides": overrides}
    p = root / "data" / "overrides" / "tinker.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(validate.canonical_dumps(ovr, kind="overrides"), encoding="utf-8")
    return p


def test_overrides_file_valid(tmp_path, example):
    root = make_repo(tmp_path, example).parents[2]
    p = _overrides_file(root, [
        {"talent": "steady-hands", "tree": "gadgetry", "set": {"name": "Steady Hands"},
         "reason": "accepted as read", "by": "deradon", "at": "2026-09-14T20:11:00Z"},
        {"talent": "steady-hands", "tree": "gadgetry", "set": {},
         "reason": "accepted as read", "by": "deradon", "at": "2026-09-14T20:11:30Z"},
        {"talent": "ghost", "tree": "gadgetry", "delete": True,
         "reason": "duplicate", "by": "deradon", "at": "2026-09-14T20:12:00Z"},
    ])
    code, findings = run(p, "--overrides", "--check")
    assert code == 0, codes(findings, "ERROR")
    assert "OVR-TARGET" in codes(findings, "WARNING")  # 'ghost' not in extracted


def test_overrides_file_invalid(tmp_path, example):
    root = make_repo(tmp_path, example).parents[2]
    p = _overrides_file(root, [
        {"talent": "bad", "tree": "gadgetry", "set": {}, "rename": "worse",
         "reason": "two actions at once", "by": "deradon", "at": "2026-09-14T20:13:00Z"},
        {"talent": "no-reason", "tree": "gadgetry", "delete": True,
         "reason": "", "by": "deradon", "at": "2026-09-14T20:13:00Z"},
    ])
    code, findings = run(p, "--overrides")
    assert code == 1
    assert codes(findings, "ERROR") == {"R01-SCHEMA"}


def test_json_output(tmp_path, example, capsys):
    path = make_repo(tmp_path, example)
    code = validate.main([str(path), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"] is True
    assert out["files"][0]["errors"] == 0
    assert any(q["talent"] == "steady-hands" for q in out["files"][0]["reviewQueue"])

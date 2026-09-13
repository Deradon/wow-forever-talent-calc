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


# ----------------------------------------------------------------------------
# Rule 20: rank anticipation sanity (data audit 2026-09-13, work package B6)
# ----------------------------------------------------------------------------

def _first_multirank(doc: dict) -> dict:
    return next(t for tree in doc["trees"] for t in tree["talents"] if t["maxRank"] >= 3)


def test_r20_flags_an_anticipated_percentage_above_100(tmp_path, example):
    """warrior/enrage reads 30/60/90/120/150 %: rank 1 was read off a tooltip, the rest is
    arithmetic, and 150 % damage is not a number the game prints."""
    doc = copy.deepcopy(example)
    t = _first_multirank(doc)
    t["maxRank"] = 3
    t["description"] = "Increases your damage by {0}%."
    t["ranks"] = [[50], [100], [150]]
    t["ranksObserved"] = [1]
    t["ranksSource"] = "extrapolated"
    t.pop("ranksPrior", None)
    _, findings = run(make_repo(tmp_path, doc))
    assert "R20-PERCENT-OVER-100" in codes(findings, "WARNING")


def test_r20_does_not_flag_a_percentage_that_was_actually_observed(tmp_path, example):
    doc = copy.deepcopy(example)
    t = _first_multirank(doc)
    t["maxRank"] = 3
    t["description"] = "Increases your damage by {0}%."
    t["ranks"] = [[50], [100], [150]]
    t["ranksObserved"] = [1, 2, 3]
    t["ranksSource"] = "observed"
    t.pop("ranksPrior", None)
    _, findings = run(make_repo(tmp_path, doc))
    assert "R20-PERCENT-OVER-100" not in codes(findings, "WARNING")


def test_r20_does_not_flag_a_value_that_is_not_a_percentage(tmp_path, example):
    doc = copy.deepcopy(example)
    t = _first_multirank(doc)
    t["maxRank"] = 3
    t["description"] = "Deals {0} additional damage."
    t["ranks"] = [[50], [100], [150]]
    t["ranksObserved"] = [1]
    t["ranksSource"] = "extrapolated"
    t.pop("ranksPrior", None)
    _, findings = run(make_repo(tmp_path, doc))
    assert "R20-PERCENT-OVER-100" not in codes(findings, "WARNING")


@pytest.mark.parametrize("text", [
    "Your attacks deal double damage against targets below {0}% health.",
    "Usable only on enemies with less than {0}% health.",
    "Triggers when the target is at or below {0}% health.",
])
def test_r20_flags_a_threshold_that_was_scaled(tmp_path, example, text):
    """rogue/quietus: 'below 35% health' became 'below 175% health' at rank 5. A condition is
    not a magnitude and the extrapolator cannot tell the difference from the numbers alone."""
    doc = copy.deepcopy(example)
    t = _first_multirank(doc)
    t["maxRank"] = 3
    t["description"] = text
    t["ranks"] = [[35], [70], [105]]
    t["ranksObserved"] = [1]
    t["ranksSource"] = "extrapolated"
    t.pop("ranksPrior", None)
    _, findings = run(make_repo(tmp_path, doc))
    assert "R20-THRESHOLD-SCALED" in codes(findings, "WARNING")


def test_r20_leaves_a_constant_threshold_alone(tmp_path, example):
    doc = copy.deepcopy(example)
    t = _first_multirank(doc)
    t["maxRank"] = 3
    t["description"] = "Deals double damage against targets below {0}% health, for {1} sec."
    t["ranks"] = [[35, 5], [35, 10], [35, 15]]
    t["ranksObserved"] = [1]
    t["ranksSource"] = "extrapolated"
    t.pop("ranksPrior", None)
    _, findings = run(make_repo(tmp_path, doc))
    assert "R20-THRESHOLD-SCALED" not in codes(findings, "WARNING")


def test_r20_is_silent_on_a_single_rank_talent(tmp_path, example):
    doc = copy.deepcopy(example)
    for tree in doc["trees"]:
        for t in tree["talents"]:
            t["maxRank"] = 1
            t["ranks"] = t["ranks"][:1]
            t["ranksObserved"] = [1]
            t["ranksSource"] = "observed"
            t.pop("ranksPrior", None)
            t.pop("ranksNote", None)
    _, findings = run(make_repo(tmp_path, doc))
    assert not {c for c in codes(findings, "WARNING") if c.startswith("R20-")}


def test_the_repo_data_has_no_rank_sanity_errors():
    """R20 findings are warnings by design - they are review prompts, not gate failures."""
    for cls in ("mage", "warrior"):
        p = REPO / "data" / "talents" / f"{cls}.json"
        assert validate.main([str(p), "--check", "--root", str(REPO)]) == 0


def _overrides_in_repo(tmp_path: Path, example: dict, doc: dict) -> Path:
    root = make_repo(tmp_path, example).parents[2]
    p = root / "data" / "overrides" / f"{doc['class']}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(validate.canonical_dumps(doc, kind="overrides"), encoding="utf-8")
    return p


def test_overrides_set_source_may_be_partial(tmp_path, example):
    """Section 6.2: `set` is a shallow merge and source sub-fields merge shallowly too, so an
    override that corrects only `source.note` must validate."""
    doc = {"schemaVersion": 1, "class": "tinker", "overrides": [{
        "talent": "improved-wrench", "tree": "gadgetry",
        "set": {"requires": [{"talent": "steady-hands", "rank": 2}],
                "source": {"note": "prerequisite added by hand from the tree arrow"}},
        "reason": "arrow the detector missed", "by": "reviewer", "at": "2026-09-13T00:00:00Z"}]}
    p = _overrides_in_repo(tmp_path, example, doc)
    code, findings = run(p, "--overrides", "--check")
    assert code == 0, codes(findings, "ERROR")


def test_overrides_set_source_still_rejects_an_unknown_field(tmp_path, example):
    doc = {"schemaVersion": 1, "class": "tinker", "overrides": [{
        "talent": "improved-wrench", "tree": "gadgetry",
        "set": {"source": {"nonsense": 1}},
        "reason": "r", "by": "reviewer", "at": "2026-09-13T00:00:00Z"}]}
    p = _overrides_in_repo(tmp_path, example, doc)
    code, findings = run(p, "--overrides")
    assert code == 1 and "R01-SCHEMA" in codes(findings, "ERROR")


def test_the_repo_override_files_validate():
    for p in sorted((REPO / "data" / "overrides").glob("*.json")):
        assert validate.main([str(p), "--overrides", "--check", "--root", str(REPO)]) == 0, p.name

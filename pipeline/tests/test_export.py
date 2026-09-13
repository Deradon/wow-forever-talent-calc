"""End-to-end tests for wowtalents.export / stages/08_export.py.

A throw-away repo root (schema, prior, encoding, crops) is built under tmp_path;
the synthetic candidates come from tests/fixtures/warrior.candidates.json.
Run: cd pipeline && uv run pytest -q
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parent
sys.path.insert(0, str(PIPELINE / "src"))
sys.path.insert(0, str(PIPELINE))

from wowtalents import export as X  # noqa: E402
from wowtalents import ranks as R  # noqa: E402
import validate  # noqa: E402

FIXTURE = PIPELINE / "tests" / "fixtures" / "warrior.candidates.json"
SCHEMA = REPO / "data" / "schema" / "class.schema.json"
PRIOR = REPO / "data" / "prior" / "classic-era" / "talents.json"
STAGE = PIPELINE / "stages" / "08_export.py"

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8ffff3f0300"
                    "05fe02fea7a5b6e70000000049454e44ae426082")


@pytest.fixture(scope="module")
def prior() -> R.Prior:
    return R.Prior.load(PRIOR)


def make_repo(tmp_path: Path) -> tuple[Path, list[dict]]:
    """Repo root with schema, an empty encoding v1, fake crops under pipeline-relative work/ paths."""
    root = tmp_path / "repo"
    (root / "data" / "schema").mkdir(parents=True)
    shutil.copy(SCHEMA, root / "data" / "schema" / "class.schema.json")
    (root / "data" / "prior" / "classic-era").mkdir(parents=True)
    shutil.copy(PRIOR, root / "data" / "prior" / "classic-era" / "talents.json")
    (root / "data" / "encoding" / "migrations").mkdir(parents=True)
    (root / "data" / "encoding" / "v1.json").write_text(json.dumps(
        {"version": 1, "createdAt": "2026-09-13T01:00:00Z", "note": "test", "classes": {}}, indent=2) + "\n")
    (root / "data" / "extracted").mkdir()
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    crops = tmp_path / "crops"
    crops.mkdir()
    for rec in records:
        p = crops / f"{rec['source']['t']}.png"
        p.write_bytes(PNG)
        rec["source"]["crop_path"] = str(p)
    (root / "data" / "extracted" / "warrior.candidates.json").write_text(json.dumps(records, indent=2) + "\n")
    return root, records


def talents_of(doc: dict) -> dict[str, dict]:
    return {t["id"]: t for tree in doc["trees"] for t in tree["talents"]}


# ----------------------------------------------------------------------------
# requires parsing
# ----------------------------------------------------------------------------

def test_parse_requires_forms():
    out = X.parse_requires(["Requires 5 points in Arms Talents", "Requires 5 points in Tactical Mastery",
                            "Requires Tactical Mastery (Rank 5)", "Requires 1 point in Nature's Grasp.", "gibberish"])
    assert out[0] == {"name": "Arms", "points": 5, "tier": True, "text": "Requires 5 points in Arms Talents"}
    assert (out[1]["name"], out[1]["points"], out[1]["tier"]) == ("Tactical Mastery", 5, False)
    assert (out[2]["name"], out[2]["points"], out[2]["tier"]) == ("Tactical Mastery", 5, False)
    assert (out[3]["name"], out[3]["points"]) == ("Nature's Grasp", 1)
    assert out[4]["name"] is None


# ----------------------------------------------------------------------------
# build_extracted
# ----------------------------------------------------------------------------

def test_build_extracted_shape(tmp_path, prior):
    root, records = make_repo(tmp_path)
    log = X.Log()
    doc = X.build_extracted("warrior", copy.deepcopy(records), prior, root=root, generated_at="2026-09-13T12:00:00Z", log=log)
    assert doc["class"] == "warrior" and doc["className"] == "Warrior" and doc["dataSource"] == "video"
    assert doc["rules"] == {"pointsPerRow": 5, "maxPoints": 51, "firstPointLevel": 10, "maxLevel": 60, "rulesSource": "assumed"}
    assert doc["pages"] == [{"id": "primary", "name": "Primary"}]
    assert [t["id"] for t in doc["trees"]] == ["arms"]
    arms = doc["trees"][0]
    assert (arms["name"], arms["page"], arms["order"], arms["rows"], arms["cols"]) == ("Arms", "primary", 0, 7, 4)
    ids = [t["id"] for t in arms["talents"]]
    assert ids == ["improved-heroic-strike", "tactical-mastery", "anger-management"]  # dedupe dropped the cut-off duplicate

    t = talents_of(doc)
    ihs = t["improved-heroic-strike"]
    assert ihs["icon"] == "crop-improved-heroic-strike" and ihs["iconSource"] == "crop"
    assert ihs["iconCrop"] == "data/review/warrior/arms/improved-heroic-strike.png"
    assert ihs["description"] == "Reduces the cost of your Heroic Strike ability by {0} rage point{1}."
    assert ihs["ranks"] == [[1, ""], [2, "s"], [3, "s"]] and ihs["ranksSource"] == "classic-prior"
    assert ihs["ranksPrior"]["classicTalentId"] == 124 and ihs["ranksObserved"] == [1]
    assert ihs["source"] == {
        "kind": "video", "video": "DxtVEhjyROU", "t": 17832.25, "frame": 1069935,
        "crop": "data/review/warrior/arms/improved-heroic-strike.png", "confidence": 0.93,
        "reader": "qwen3-vl-4b-instruct-q4_k_m", "reviewed": False,
    }
    assert (root / "data" / "review" / "warrior" / "arms" / "improved-heroic-strike.png").read_bytes() == PNG

    tm = t["tactical-mastery"]
    assert "requires" not in tm  # tier requirement is row gating, not a prerequisite
    assert tm["source"]["readings"][0]["reader"].endswith("pass2")
    am = t["anger-management"]
    assert am["requires"] == [{"talent": "tactical-mastery", "rank": 5}]
    assert am["maxRank"] == 1 and am["ranksSource"] == "observed" and am["ranks"] == [[30]]
    assert not log.errors()
    assert any("dedupe" in l for l in log.lines)


def test_tier_requirement_row_mismatch_is_logged(tmp_path, prior):
    root, records = make_repo(tmp_path)
    records[1]["requires"] = ["Requires 10 points in Arms Talents"]  # implies row 2, detected row 1
    log = X.Log()
    X.build_extracted("warrior", records, prior, root=root, log=log)
    assert any("implies row 2" in l for l in log.lines)


def test_unresolved_requirement_goes_to_source_note(tmp_path, prior):
    root, records = make_repo(tmp_path)
    records[2]["requires"] = ["Requires 5 points in Deep Wounds"]
    doc = X.build_extracted("warrior", records, prior, root=root)
    am = talents_of(doc)["anger-management"]
    assert "requires" not in am and "unresolved requirement" in am["source"]["note"]


def test_arrow_requires_merge_and_conflicts(tmp_path, prior):
    root, records = make_repo(tmp_path)
    arrow = {"tree": "Arms", "row": 1, "col": 1, "name": "Tactical Mastery", "rank": 5, "shape": "straight",
             "confidence": 0.95, "medians": 2}
    # 1. no tooltip requirement: the arrow becomes the prerequisite, with the max-rank note
    records[2]["requires"] = []
    records[2]["requires_arrows"] = [dict(arrow)]
    doc = X.build_extracted("warrior", copy.deepcopy(records), prior, root=root)
    am = talents_of(doc)["anger-management"]
    assert am["requires"] == [{"talent": "tactical-mastery", "rank": 5}]
    assert "prerequisite from tree arrow (stage 7): Tactical Mastery at rank 5 = its max rank" in am["source"]["note"]
    # 2. tooltip says rank 3, arrow says 5: the tooltip wins, the conflict is logged and noted
    records[2]["requires"] = ["Requires Tactical Mastery (Rank 3)"]
    log = X.Log()
    doc = X.build_extracted("warrior", copy.deepcopy(records), prior, root=root, log=log)
    am = talents_of(doc)["anger-management"]
    assert am["requires"] == [{"talent": "tactical-mastery", "rank": 3}]
    assert any("ARROW-CONFLICT" in l for l in log.lines) and "arrow conflict" in am["source"]["note"]
    # 3. tooltip names another talent: the arrow is dropped, tooltip kept
    records[2]["requires"] = ["Requires Improved Heroic Strike (Rank 3)"]
    log = X.Log()
    doc = X.build_extracted("warrior", copy.deepcopy(records), prior, root=root, log=log)
    am = talents_of(doc)["anger-management"]
    assert am["requires"] == [{"talent": "improved-heroic-strike", "rank": 3}]
    assert any("ARROW-CONFLICT" in l for l in log.lines)
    # 4. same-row arrow: note only, no requires entry (schema rule 8)
    records[2]["requires"] = []
    records[1]["requires_arrows"] = [{"tree": "Arms", "row": 2, "col": 1, "name": "Anger Management", "rank": 1,
                                      "shape": "row", "confidence": 1.0, "medians": 2}]
    records[2]["requires_arrows"] = []
    doc = X.build_extracted("warrior", copy.deepcopy(records), prior, root=root)
    tm = talents_of(doc)["tactical-mastery"]
    assert "requires" not in tm and "same-row prerequisite arrow from Anger Management" in tm["source"]["note"]


def test_id_collision_across_trees_gets_tree_suffix(tmp_path, prior):
    root, records = make_repo(tmp_path)
    clone = copy.deepcopy(records[0])
    clone.update({"tree": "Fury", "row": 0, "col": 0})
    clone["source"]["t"] = 17999.0
    records.append(clone)
    doc = X.build_extracted("warrior", records, prior, root=root, tree_order=["Arms", "Fury", "Protection"])
    ids = sorted(talents_of(doc))
    assert "improved-heroic-strike-arms" in ids and "improved-heroic-strike-fury" in ids
    assert [t["id"] for t in doc["trees"]] == ["arms", "fury"] and doc["trees"][1]["order"] == 1


def test_unread_name_gets_positional_id(tmp_path, prior):
    root, records = make_repo(tmp_path)
    records[0]["name"] = ""
    doc = X.build_extracted("warrior", records, prior, root=root)
    t = talents_of(doc)["crop-r0c0"]
    assert t["name"] == "Unread r0c0" and t["icon"] == "crop-crop-r0c0"


# ----------------------------------------------------------------------------
# write + validate, overrides, promotion
# ----------------------------------------------------------------------------

def test_write_validated_refuses_invalid_doc(tmp_path, prior):
    root, records = make_repo(tmp_path)
    doc = X.build_extracted("warrior", records, prior, root=root)
    log = X.Log()
    dest = root / "data" / "extracted" / "warrior.json"
    # class not in the encoding file yet: rule 11 error, nothing written
    assert X.write_validated(doc, dest, root, log) is False
    assert not dest.exists() and any("R11-ENCODING-CLASS" in l for l in log.errors())
    X.update_encoding(root, doc, log)
    assert X.write_validated(doc, dest, root, log) is True
    assert dest.read_text(encoding="utf-8") == validate.canonical_dumps(doc)
    assert not (root / "data" / "extracted" / ".export-tmp").exists()
    assert validate.main([str(dest), "--check", "--root", str(root)]) == 0


def overrides_doc(*entries: dict) -> dict:
    return {"schemaVersion": 1, "class": "warrior", "overrides": list(entries)}


def test_override_set_rename_delete_add(tmp_path, prior):
    root, records = make_repo(tmp_path)
    doc = X.build_extracted("warrior", records, prior, root=root)
    ov = overrides_doc(
        {"talent": "tactical-mastery", "tree": "arms",
         "set": {"ranks": [[5], [10], [15], [20], [25]], "ranksSource": "manual", "ranksNote": "confirmed by hand"},
         "reason": "reader confidence 0.71", "by": "reviewer", "at": "2026-09-14T20:11:00Z"},
        {"talent": "anger-management", "tree": "arms", "rename": "anger-mgmt",
         "reason": "test rename", "by": "reviewer", "at": "2026-09-14T20:12:00Z"},
        {"talent": "improved-heroic-strike", "tree": "arms", "delete": True,
         "reason": "test delete", "by": "reviewer", "at": "2026-09-14T20:13:00Z"},
        {"talent": "deep-wounds", "tree": "arms",
         "add": {"id": "deep-wounds", "name": "Deep Wounds", "row": 0, "col": 2, "maxRank": 3, "icon": "ability_backstab",
                 "iconSource": "manual", "description": "Your critical strikes cause the opponent to bleed for {0}% of your melee weapon's average damage over 12 sec.",
                 "ranks": [[20], [40], [60]], "ranksObserved": [1], "ranksSource": "manual", "ranksNote": "typed from frame",
                 "source": {"kind": "manual", "reviewed": True, "reviewedBy": "reviewer", "reviewedAt": "2026-09-14T20:14:00Z"}},
         "reason": "missed by segmentation", "by": "reviewer", "at": "2026-09-14T20:14:00Z"},
    )
    log = X.Log()
    out = X.build_talents(doc, ov, None, log, generated_at="2026-09-14T21:00:00Z")
    t = talents_of(out)
    assert set(t) == {"tactical-mastery", "anger-mgmt", "deep-wounds"}
    tm = t["tactical-mastery"]
    assert tm["ranksSource"] == "manual" and "ranksPrior" not in tm and tm["ranks"][4] == [25]
    assert tm["source"]["reviewed"] is True and tm["source"]["reviewedBy"] == "reviewer"
    assert "readings" not in tm["source"]  # stripped for talents/
    am = t["anger-mgmt"]
    assert am["icon"] == "crop-anger-mgmt" and am["requires"] == [{"talent": "tactical-mastery", "rank": 5}]
    assert out["generatedAt"] == "2026-09-14T21:00:00Z"
    # the override result validates (files skipped: manual add has no crop)
    X.update_encoding(root, out, log)
    dest = root / "data" / "talents" / "warrior.json"
    assert X.write_validated(out, dest, root, log, no_files=True), log.errors()


def test_reviewed_override_survives_reexport(tmp_path, prior):
    root, records = make_repo(tmp_path)
    doc = X.build_extracted("warrior", copy.deepcopy(records), prior, root=root)
    ov = overrides_doc({"talent": "improved-heroic-strike", "tree": "arms", "set": {},
                        "reason": "accepted as read", "by": "reviewer", "at": "2026-09-14T20:11:00Z"})
    log = X.Log()
    first = X.build_talents(doc, ov, None, log)
    assert talents_of(first)["improved-heroic-strike"]["source"]["reviewed"] is True
    # the pipeline re-runs with a different reading of that talent and of an unreviewed one
    changed = copy.deepcopy(records)
    changed[0]["description_rank1"] = "Reduces the cost of your Heroic Strike ability by 2 rage points."
    changed[0]["source"]["confidence"] = 0.5
    changed[2]["description_rank1"] = "Increases the time required for your rage to decay while out of combat by 40%."
    doc2 = X.build_extracted("warrior", changed, prior, root=root)
    assert talents_of(doc2)["improved-heroic-strike"]["source"]["reviewed"] is False  # extracted/ is raw
    second = X.build_talents(doc2, ov, first, log)
    t = talents_of(second)
    ihs = t["improved-heroic-strike"]
    assert ihs["source"]["reviewed"] is True and ihs["source"]["reviewedBy"] == "reviewer"
    # section 6.3 step 2: a talent targeted by an override this run gets the override re-applied over the
    # NEW extraction, so an empty "accepted as read" set follows the new reading (and is logged)
    assert ihs["ranks"] == [[2], [4], [6]] and ihs["source"]["confidence"] == 0.5
    assert any(l.startswith("WARNING REVIEWED-DIFF arms/improved-heroic-strike") for l in log.lines)
    assert t["anger-management"]["ranks"] == [[40]]        # unreviewed talents follow the pipeline
    # a reviewed talent no longer targeted by an override is kept verbatim with a REVIEWED-DIFF warning
    prev = copy.deepcopy(first)
    talents_of(prev)["anger-management"]["source"].update({"reviewed": True, "reviewedBy": "reviewer", "reviewedAt": "2026-09-14T20:20:00Z"})
    log2 = X.Log()
    third = X.build_talents(doc2, ov, prev, log2)
    assert talents_of(third)["anger-management"]["ranks"] == [[30]]
    assert any(l.startswith("WARNING REVIEWED-DIFF arms/anger-management") for l in log2.lines)


def test_stage_cli_extract_and_promote(tmp_path):
    root, _ = make_repo(tmp_path)
    (root / "data" / "overrides").mkdir()
    (root / "data" / "overrides" / "warrior.json").write_text(validate.canonical_dumps(overrides_doc(
        {"talent": "tactical-mastery", "tree": "arms", "set": {}, "reason": "accepted as read",
         "by": "reviewer", "at": "2026-09-14T20:11:00Z"}), kind="overrides"))
    cmd = [sys.executable, str(STAGE), "all", "warrior", "--root", str(root), "--update-encoding"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PIPELINE))
    assert res.returncode == 0, res.stdout + res.stderr
    extracted = json.loads((root / "data" / "extracted" / "warrior.json").read_text())
    talents = json.loads((root / "data" / "talents" / "warrior.json").read_text())
    assert talents_of(extracted)["tactical-mastery"]["source"]["reviewed"] is False
    assert talents_of(talents)["tactical-mastery"]["source"]["reviewed"] is True
    enc = json.loads((root / "data" / "encoding" / "v1.json").read_text())
    assert enc["classes"]["warrior"]["order"]["arms"] == ["improved-heroic-strike", "tactical-mastery", "anger-management"]
    assert validate.main([str(root / "data" / "talents" / "warrior.json"), "--check", "--root", str(root)]) == 0
    # a second run must be idempotent and keep the reviewed flag
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PIPELINE))
    assert res.returncode == 0, res.stdout + res.stderr
    again = json.loads((root / "data" / "talents" / "warrior.json").read_text())
    assert talents_of(again)["tactical-mastery"]["source"]["reviewed"] is True


def test_stage_cli_fails_loudly_without_encoding(tmp_path):
    root, _ = make_repo(tmp_path)
    res = subprocess.run([sys.executable, str(STAGE), "extract", "warrior", "--root", str(root)],
                         capture_output=True, text=True, cwd=str(PIPELINE))
    assert res.returncode == 1
    assert "R11-ENCODING-CLASS" in res.stdout and "NOT written" in res.stdout
    assert not (root / "data" / "extracted" / "warrior.json").exists()


def test_video_source_omits_null_reading_maxrank():
    from wowtalents import export as E
    src = {"t": 20800.0, "frame_index": 1248000, "confidence": 0.3, "reader": "q",
           "readings": [{"reader": "q/3x", "name": "5 Rage", "description": "x", "maxRank": None, "confidence": 0.3},
                        {"reader": "codex-cli", "name": "Feral Charge", "description": "x", "maxRank": 1, "confidence": 0.3}]}
    out = E._video_source(src, "data/review/druid/feral-combat/x.png", "vid", 60)
    assert "maxRank" not in out["readings"][0] and out["readings"][1]["maxRank"] == 1


# ----------------------------------------------------------------------------
# stage 9 icon fields on the candidate record
# ----------------------------------------------------------------------------
def test_candidate_icon_fields_replace_the_crop(tmp_path, prior):
    root, records = make_repo(tmp_path)
    records = copy.deepcopy(records)
    records[0]["icon"] = "Ability_Warrior_SavageBlow"
    records[0]["icon_source"] = "classic"
    records[1]["icon"] = "inv_sword_27"           # no icon_source: ignored, stays a crop
    records[2]["icon"] = "inv_axe_01"
    records[2]["icon_source"] = "crop"           # not a known-icon source: ignored
    doc = X.build_extracted("warrior", records, prior, root=root)
    by_t = {(t["row"], t["col"], tree["name"]): t for tree in doc["trees"] for t in tree["talents"]}
    matched = by_t[(records[0]["row"], records[0]["col"], records[0]["tree"])]
    assert matched["icon"] == "ability_warrior_savageblow" and matched["iconSource"] == "classic"
    assert "iconCrop" not in matched and matched["source"]["crop"].endswith(".png")
    for rec in records[1:3]:
        t = by_t[(rec["row"], rec["col"], rec["tree"])]
        assert t["iconSource"] == "crop" and t["icon"] == f"crop-{t['id']}" and "iconCrop" in t
    log = X.Log()
    X.update_encoding(root, doc, log)
    assert X.write_validated(doc, root / "data" / "extracted" / "warrior.json", root, log) is True

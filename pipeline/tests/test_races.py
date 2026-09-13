"""Pure helpers of ``wowtalents.races``, ``stages/12_races.py`` and ``validate_races.py``.

No video, no ffmpeg, no llama-server: the pixel functions get synthetic frames,
everything else gets the strings the reader really produced on 2026-09-13.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from wowtalents import mkv  # noqa: E402
from wowtalents import races as RC  # noqa: E402

import validate_races as VR  # noqa: E402

_spec = importlib.util.spec_from_file_location("stage12", ROOT / "stages" / "12_races.py")
st12 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(st12)


# --------------------------------------------------------------------------- trait text

@pytest.mark.parametrize("line,name,kind,desc", [
    ("Perception: Detect Stealthed enemies for 20 sec", "Perception", "active",
     "Detect Stealthed enemies for 20 sec"),
    ("Sword Specialization (Passive): Swords increase spell and ability critical chance by 2%",
     "Sword Specialization", "passive", "Swords increase spell and ability critical chance by 2%"),
    ("Elune's Light: Increases critical chance by 10% for 15 sec", "Elune's Light", "active",
     "Increases critical chance by 10% for 15 sec"),
    ("Eureka!: Reduced cost and 10% increased damage", "Eureka!", "active",
     "Reduced cost and 10% increased damage"),
])
def test_parse_trait_line(line, name, kind, desc):
    got = RC.parse_trait_line(line)
    assert got == {"name": name, "kind": kind, "description": desc}


@pytest.mark.parametrize("line", [
    "Humans are a young race, and thus highly versatile",   # lore sentence, no colon
    "Racial Traits",                                        # the heading
    ": nothing before the colon",
])
def test_parse_trait_line_rejects_non_traits(line):
    assert RC.parse_trait_line(line) is None


def test_trait_id_drops_the_passive_suffix_and_punctuation():
    assert RC.trait_id("Sword Specialization (Passive)") == "sword-specialization"
    assert RC.trait_id("Elune's Light") == "elunes-light"
    assert RC.trait_id("Eureka!") == "eureka"


def test_normalise_trait_splits_a_whole_line_filed_as_the_name():
    """The reader sometimes puts the whole row in ``name`` and leaves ``description`` empty."""
    out = RC.normalise_trait({"name": "Hardiness (Passive): Stun durations decreased by 20%",
                              "description": "", "kind": None, "cut_off": False})
    assert out == {"name": "Hardiness", "kind": "passive",
                   "description": "Stun durations decreased by 20%", "cut_off": False}


def test_normalise_trait_keeps_a_clean_pair():
    out = RC.normalise_trait({"name": "War Stomp", "kind": None,
                              "description": "Stuns nearby enemies for 2 sec", "cut_off": True})
    assert out["name"] == "War Stomp" and out["kind"] == "active" and out["cut_off"] is True


def test_clean_race_panel_drops_headings_and_duplicates():
    doc = RC.clean_race_panel({
        "race_name": "  Undead ",
        "traits": [{"name": "Racial Traits", "kind": None, "description": "", "cut_off": False},
                   {"name": "Cannibalize", "kind": None, "description": "Consume corpses", "cut_off": False},
                   {"name": "Cannibalize", "kind": None, "description": "Consume corpses", "cut_off": False}],
        "lore": "Free of the Lich King's grasp", "lore_cut_off": True})
    assert doc["race_name"] == "Undead"
    assert [t["name"] for t in doc["traits"]] == ["Cannibalize"]
    assert doc["lore_cut_off"] is True


# --------------------------------------------------------------------------- fragments and order

def test_drop_fragments_removes_a_scrolled_off_name():
    """troll-11740: the box cut 'Beast Slaying (Passive):' off, leaving its tail as a 'trait'."""
    recs = [{"name": "Damage to Beasts", "description": "increased by 5%"},
            {"name": "Beast Slaying", "description": "Damage to Beasts increased by 5%"},
            {"name": "Regeneration", "description": "10% of Health regeneration continues during combat"}]
    kept, dropped = RC.drop_fragments(recs)
    assert [r["name"] for r in kept] == ["Beast Slaying", "Regeneration"]
    assert [r["name"] for r in dropped] == ["Damage to Beasts"]


def test_drop_fragments_removes_a_wrapped_description_read_as_a_name():
    """tauren-11730: 'Plainsrunning (Passive): Gain' scrolled off, the wrap became a name."""
    recs = [{"name": "increased movement speed the longer you stay moving",
             "description": "increased movement speed the longer you stay moving"},
            {"name": "Plainsrunning", "description": "Gain increased movement speed the longer you stay moving"}]
    kept, _ = RC.drop_fragments(recs)
    assert [r["name"] for r in kept] == ["Plainsrunning"]


def test_drop_fragments_keeps_two_genuinely_different_traits():
    recs = [{"name": "Regeneration", "description": "10% of Health regeneration continues during combat"},
            {"name": "Rapid Regeneration", "description": "Regenerate 50% of maximum Health over time"}]
    kept, dropped = RC.drop_fragments(recs)
    assert len(kept) == 2 and dropped == []


def test_stitch_order_recovers_the_panel_order_from_overlapping_windows():
    seqs = [["will-to-survive", "perception", "sword-specialization"],
            ["perception", "sword-specialization", "the-human-spirit"],
            ["sword-specialization", "the-human-spirit"]]
    assert RC.stitch_order(seqs) == ["will-to-survive", "perception", "sword-specialization",
                                     "the-human-spirit"]


def test_stitch_order_survives_a_contradiction():
    out = RC.stitch_order([["a", "b"], ["b", "a"]])
    assert sorted(out) == ["a", "b"] and len(out) == 2


# --------------------------------------------------------------------------- band alignment

def test_align_bands_one_to_one():
    traits = [{"cut_off": False}, {"cut_off": False}]
    assert RC.align_bands([(10, 40), (60, 90)], traits) == [(0, (10, 40)), (1, (60, 90))]


def test_align_bands_peels_a_clipped_row_off_the_top():
    traits = [{"cut_off": True}, {"cut_off": False}, {"cut_off": False}]
    assert RC.align_bands([(60, 90), (110, 140)], traits) == [(1, (60, 90)), (2, (110, 140))]


def test_align_bands_refuses_an_ambiguous_case():
    traits = [{"cut_off": False}, {"cut_off": False}, {"cut_off": False}]
    assert RC.align_bands([(60, 90)], traits) == []
    assert RC.align_bands([(10, 40), (60, 90), (110, 140), (160, 190)], traits) == []


def test_trait_blocks_run_from_one_icon_to_the_next():
    _, top, _, bottom = RC.PANEL
    blocks = RC.trait_blocks([(top + 20, top + 54), (top + 80, top + 114)])
    assert blocks[0] == (top + 14, top + 74)
    assert blocks[1][1] == bottom


# --------------------------------------------------------------------------- agreement

def test_confidence_matches_stage_5s_three_values():
    a = {"name": "Stoneform", "kind": "active", "description": "Immunity to Bleeds"}
    assert RC.confidence(a, dict(a)) == 1.0
    assert RC.confidence(a, dict(a, description="Immunity to bleeds and poisons")) == 0.7
    assert RC.confidence(a, {"name": "Find Treasure", "kind": "active", "description": "x"}) == 0.3
    assert RC.confidence(a, None) == 0.0


def test_merge_traits_keeps_the_complete_reading_and_the_panel_order():
    recs = [
        {"name": "Beast Slaying", "kind": "passive", "description": "Damage to Beasts increased by",
         "cut_off": True, "variants": [], "source": {"confidence": 1.0, "sharpness": 90.0}},
        {"name": "Beast Slaying", "kind": "passive", "description": "Damage to Beasts increased by 5%",
         "cut_off": False, "variants": [], "source": {"confidence": 0.7, "sharpness": 10.0}},
        {"name": "Berserking", "kind": "active", "description": "Increases casting speed",
         "cut_off": False, "variants": [], "source": {"confidence": 1.0, "sharpness": 50.0}},
    ]
    out = RC.merge_traits(recs, order=["berserking", "beast-slaying"])
    assert [r["name"] for r in out] == ["Berserking", "Beast Slaying"]
    assert out[1]["description"] == "Damage to Beasts increased by 5%"
    assert len(out[1]["alternates"]) == 1


def test_merge_traits_unions_the_variants_of_a_shared_trait():
    recs = [{"name": "Walk on Air", "kind": "active", "description": "Glide", "cut_off": False,
             "variants": ["high-order"], "source": {"confidence": 1.0, "sharpness": 1.0}},
            {"name": "Walk on Air", "kind": "active", "description": "Glide", "cut_off": False,
             "variants": ["windshaper"], "source": {"confidence": 1.0, "sharpness": 2.0}}]
    out = RC.merge_traits(recs)
    assert len(out) == 1 and out[0]["variants"] == ["high-order", "windshaper"]


# --------------------------------------------------------------------------- geometry

def test_race_slots_cover_the_ten_portraits_and_only_skyborne_has_variants():
    assert [RC.race_of_slot("alliance", k) for k in range(5)] == [
        ("human", None), ("dwarf", None), ("night-elf", None), ("gnome", None), ("skyborne", "high-order")]
    assert RC.race_of_slot("horde", 4) == ("skyborne", "windshaper")
    assert RC.race_of_slot("horde", 1) == ("undead", None)


def test_selection_key_names_the_unit_a_panel_belongs_to():
    assert RC.Selection("horde", 4, "skyborne", "windshaper", 120.0, 60.0).key == "skyborne/windshaper"
    assert RC.Selection("horde", 0, "orc", None, 120.0, 60.0).key == "orc"


def test_class_boxes_are_nine_non_overlapping_squares_inside_the_frame():
    boxes = [RC.class_box(k) for k in range(len(RC.CLASS_ORDER))]
    assert len(boxes) == 9
    for (x0, y0, x1, y1), (nx0, *_rest) in zip(boxes, boxes[1:]):
        assert x1 < nx0
    assert boxes[-1][2] < RC.FRAME_W and boxes[-1][3] < RC.FRAME_H


def _frame(fill: int = 0) -> np.ndarray:
    return np.full((RC.FRAME_H, RC.FRAME_W, 3), fill, np.uint8)


def test_is_character_creation_needs_both_banners():
    f = _frame()
    assert not RC.is_character_creation(f)
    x0, y0, x1, y1 = RC.BANNER_ALLIANCE
    f[y0:y1, x0:x1] = (200, 60, 20)         # BGR blue
    assert not RC.is_character_creation(f)
    x0, y0, x1, y1 = RC.BANNER_HORDE
    f[y0:y1, x0:x1] = (20, 20, 200)         # BGR red
    assert RC.is_character_creation(f)


def test_selected_race_picks_the_framed_portrait():
    f = _frame(30)
    assert RC.selected_race(f) is None
    x0, y0, x1, y1 = RC.portrait_box("horde", 2)
    f[y0:y1, x0:x1] = 200
    sel = RC.selected_race(f)
    assert sel is not None and sel.race == "tauren" and sel.margin > 50


def test_class_availability_reads_colour_not_position():
    f = _frame(10)
    for k in (0, 3):
        x0, y0, x1, y1 = RC.class_box(k)
        f[y0:y1, x0:x1] = (20, 200, 240)    # saturated
    lit, margin = RC.class_availability(f)
    assert lit == ["rogue", "warrior"] and margin > 5


def test_trait_icon_bands_finds_discs_and_ignores_text_strokes():
    px0, py0, px1, py1 = RC.PANEL
    panel = np.zeros((py1 - py0, px1 - px0, 3), np.uint8)
    ix0 = RC.ICON_COLUMN[0] - px0
    import cv2
    cv2.circle(panel, (ix0 + 18, 40), 17, (200, 200, 200), -1)
    cv2.circle(panel, (ix0 + 18, 110), 17, (200, 200, 200), -1)
    for y in (160, 175, 190):               # lore text: thin strokes at the box's left edge
        cv2.line(panel, (ix0 - 4, y), (ix0 + 30, y), (180, 180, 180), 2)
    bands = RC.trait_icon_bands(panel)
    assert len(bands) == 2
    assert bands[0][0] - py0 == pytest.approx(23, abs=3)


# --------------------------------------------------------------------------- stage 12 helpers

@pytest.mark.parametrize("spec,expected", [
    ("03:11:00-03:16:40", (11460, 11800)),
    ("11460-11800", (11460, 11800)),
    ("5:30-5:40", (330, 340)),
])
def test_parse_window(spec, expected):
    assert st12.parse_window(spec) == expected


def test_json_object_finds_the_answer_in_a_chatty_cli_reply():
    text = 'Here you go:\n```json\n{"traits": [{"name": "Stoneform"}]}\n```\nDone.'
    assert st12._json_object(text) == {"traits": [{"name": "Stoneform"}]}
    assert st12._json_object("no json here") is None
    assert st12._json_object('{"other": 1}') is None


def test_classic_status_is_new_only_when_the_name_is_absent():
    prior = ({"orc": {"traits": [{"name": "Hardiness", "kind": "passive", "description": "25% stun"}]}},
             {"orc": {"hardiness": {"status": "changed", "note": "25% -> 20%"}}})
    changed = st12._classic_for(prior, "orc", {"name": "Hardiness", "kind": "passive"})
    assert changed["status"] == "changed" and changed["classicName"] == "Hardiness"
    assert "25% -> 20%" in changed["note"] and st12.UNVERIFIED in changed["note"]
    new = st12._classic_for(prior, "orc", {"name": "Shatter Curse", "kind": "active"})
    assert new["status"] == "new" and "classicName" not in new


def test_classic_status_is_unknown_without_a_hand_verdict():
    prior = ({"orc": {"traits": [{"name": "Command", "kind": "passive", "description": "pets"}]}}, {})
    out = st12._classic_for(prior, "orc", {"name": "Command", "kind": "passive"})
    assert out["status"] == "unknown"


def test_the_shipped_classic_prior_and_diff_agree_on_trait_ids():
    races, diff = st12._prior()
    assert races, "data/prior/classic-era/racials.json is missing"
    for race, entries in diff.items():
        known = {RC.trait_id(t["name"]) for t in (races.get(race) or {}).get("traits") or []}
        assert set(entries) <= known, f"{race}: verdicts for traits the prior does not list"


# --------------------------------------------------------------------------- serializer and validator

def test_canonical_dumps_orders_keys_and_sorts_traits_by_order():
    doc = {"traits": [{"source": {"reviewed": False, "kind": "video"}, "id": "b", "order": 1,
                       "name": "B", "kind": "passive", "classic": {"note": "x", "status": "new"}},
                      {"source": {"reviewed": False, "kind": "video"}, "id": "a", "order": 0,
                       "name": "A", "kind": "active", "classic": {"note": "x", "status": "new"}}],
           "race": "orc", "schemaVersion": 1}
    out = VR.canonical_dumps(doc)
    assert out.index('"schemaVersion"') < out.index('"race"') < out.index('"traits"')
    assert out.index('"a"') < out.index('"b"')
    assert out.index('"status"') < out.index('"note"')
    assert out.endswith("\n")


def test_every_shipped_race_file_is_canonical_and_valid():
    repo = ROOT.parent
    files = sorted((repo / "data" / "races").glob("*.json"))
    assert files, "no race files to validate"
    opts = type("O", (), {"strict": True, "check": True, "no_files": False, "root": str(repo),
                          "report": False, "json": False})()
    cache: dict = {}
    for f in files:
        res = VR.validate_path(f, opts, cache)
        assert res.count("ERROR") == 0, [x.line(str(f)) for x in res.findings]


def test_validator_catches_a_broken_race_file(tmp_path):
    repo = ROOT.parent
    doc = json.loads((repo / "data" / "races" / "orc.json").read_text())
    doc["traits"][0]["classic"] = {"status": "new", "classicName": "Hardiness"}
    doc["classes"] = ["warrior", "hunter"]              # unsorted
    bad = tmp_path / "orc.json"
    bad.write_text(json.dumps(doc))
    opts = type("O", (), {"strict": False, "check": False, "no_files": True, "root": str(repo),
                          "report": False, "json": False})()
    codes = {f.code for f in VR.validate_path(bad, opts, {}).findings}
    assert {"CLASSIC-NEW", "CLASSES-UNSORTED"} <= codes


def test_matrix_matches_the_race_files():
    repo = ROOT.parent
    opts = type("O", (), {"strict": True, "check": True, "no_files": False, "root": str(repo),
                          "report": False, "json": False})()
    res = VR.validate_path(repo / "data" / "races" / "matrix.json", opts, {})
    assert res.count("ERROR") == 0, [f.line("matrix.json") for f in res.findings]


def test_race_crops_are_not_orphans_of_the_class_pipeline():
    """``08_export.py promote`` prunes data/review; it must leave stage 12's crops alone."""
    from wowtalents import export as X

    repo = ROOT.parent
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((repo / "data" / "talents").glob("*.json"))]
    orphans = X.orphan_crops(repo, docs)
    assert not [p for p in orphans if "review/races/" in str(p)]


# --------------------------------------------------------------------------- mkv frame picking

def test_decode_cmd_every_selects_frames_by_index():
    cmd = mkv.decode_cmd(Path("x.mkv"), 10.0, 2.0, every=30)
    assert r"select=not(mod(n\,30))" in cmd
    assert "-vsync" in cmd and cmd[cmd.index("-vsync") + 1] == "0"
    assert not any(c.startswith("fps=") for c in cmd)


def test_decode_cmd_without_every_still_resamples():
    cmd = mkv.decode_cmd(Path("x.mkv"), 10.0, 2.0, fps=2)
    assert "fps=2" in cmd and "-vsync" not in cmd

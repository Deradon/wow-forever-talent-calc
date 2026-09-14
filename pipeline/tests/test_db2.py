"""Tests for wowtalents.db2: the $-formatter renderer, the CSV join, template/slots, diff.

The join runs against a hand-written five-talent fixture written into tmp_path, not
against the real 1.15.9 download, so the test suite stays offline and fast.
Run: cd pipeline && uv run pytest -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parent
sys.path.insert(0, str(PIPELINE / "src"))
sys.path.insert(0, str(PIPELINE))

from wowtalents import db2 as D  # noqa: E402
from wowtalents import export as X  # noqa: E402


# ----------------------------------------------------------------------------
# Renderer
# ----------------------------------------------------------------------------

def spell(sid: int, text: str, *, effects=(), duration=0, proc=0, charges=0, stacks=0, name="") -> D.Spell:
    sp = D.Spell(id=sid, name=name or f"Spell {sid}", description=text, duration_ms=duration,
                 proc_chance=proc, proc_charges=charges, cumulative_aura=stacks)
    for e in effects:
        sp.effects[e.index] = e
    return sp


def eff(index=0, base=0, die=0, period=0, radius=0.0, chain=0, misc=0) -> D.Effect:
    return D.Effect(index=index, base_points=base, die_sides=die, aura_period=period,
                    radius=radius, chain_targets=chain, misc_value_0=misc)


@pytest.fixture
def renderer() -> D.Renderer:
    spells = {
        # Improved Heroic Strike rank 1: -11 + DieSides 1 = -10, "$/10;s1" -> 1
        100: spell(100, "Reduces the cost of your Heroic Strike ability by $/10;s1 rage $lpoint:points;.",
                   effects=[eff(0, base=-11, die=1)]),
        101: spell(101, "Reduces the cost of your Heroic Strike ability by $/10;s1 rage $lpoint:points;.",
                   effects=[eff(0, base=-21, die=1)]),
        200: spell(200, "Deals $s1 damage and $s2% more over $d.",
                   effects=[eff(0, base=9, die=1), eff(1, base=4, die=1)], duration=12000),
        201: spell(201, "Rolls for $s1 damage.", effects=[eff(0, base=224, die=11)]),
        202: spell(202, "Ticks for $o1 over $d, every $t1 seconds, within $a1 yards.",
                   effects=[eff(0, base=29, die=1, period=3000, radius=10.0)], duration=15000),
        203: spell(203, "Gives a $h% chance, $n charges, $u stacks, hits $x1 targets.",
                   effects=[eff(0, base=0, die=0, chain=3)], proc=20, charges=5, stacks=7),
        204: spell(204, "Borrows $100s1 and $200d from elsewhere.", effects=[eff(0, base=0, die=1)]),
        205: spell(205, "Lasts ${$d-1} sec.", effects=[eff(0, base=0, die=1)], duration=13000),
        206: spell(206, "A $ghe:she; strikes.$bNew line.", effects=[eff(0, base=0, die=1)]),
        207: spell(207, "Increases power by $s1%$?s999[ and more][] for $d.",
                   effects=[eff(0, base=4, die=1)], duration=10000),
        208: spell(208, "Grows by $c1 and $PCT and ${$PL*3}.", effects=[eff(0, base=1, die=1)]),
        209: spell(209, "Min $m1 max $M1.", effects=[eff(0, base=10, die=5)]),
        210: spell(210, "Lasts $d.", effects=[eff(0, base=1, die=1)], duration=120000),
    }
    return D.Renderer(spells)


def test_effect_value_is_base_plus_die_sides():
    assert D.Effect(index=0, base_points=-11, die_sides=1).value == -10


@pytest.mark.parametrize("sid,expected", [
    (100, "Reduces the cost of your Heroic Strike ability by 1 rage point."),
    (101, "Reduces the cost of your Heroic Strike ability by 2 rage points."),
    (200, "Deals 10 damage and 5% more over 12 sec."),
    (201, "Rolls for 225 to 235 damage."),                     # DieSides > 1 -> "min to max"
    (202, "Ticks for 150 over 15 sec, every 3 seconds, within 10 yards."),
    (203, "Gives a 20% chance, 5 charges, 7 stacks, hits 3 targets."),
    (204, "Borrows 10 and 12 sec from elsewhere."),            # cross-spell $<id>s1 / $<id>d
    (205, "Lasts 12 sec."),                                    # ${$d-1}
    (207, "Increases power by 5% for 10 sec."),                # $?cond[a][b] -> else branch
    (209, "Min 11 max 15."),
    (210, "Lasts 2 min."),
])
def test_render_supported_formatters(renderer, sid, expected):
    assert renderer.render(sid).text == expected


def test_gender_renders_male_and_dollar_b_is_a_line_break(renderer):
    # clean_text collapses the line break to a single space
    assert renderer.render(206).text == "A he strikes. New line."


def test_unsupported_tokens_are_left_verbatim_and_reported(renderer):
    res = renderer.render(208)
    assert "$c1" in res.text and "$PCT" in res.text and "${$PL*3}" in res.text
    assert "$c1" in res.unsupported and "$PCT" in res.unsupported
    assert any(u.startswith("${") for u in res.unsupported)


def test_conditionals_are_reported_even_though_they_render(renderer):
    res = renderer.render(207)
    assert res.conditionals == ["$?s999[ and more][]"]
    assert res.unsupported == []


def test_plural_uses_the_last_number_printed(renderer):
    assert renderer.render(100).text.endswith("1 rage point.")
    assert renderer.render(101).text.endswith("2 rage points.")


def test_missing_duration_keeps_the_token(renderer):
    renderer.spells[300] = spell(300, "Lasts $d.", effects=[eff(0)])
    res = renderer.render(300)
    assert res.text == "Lasts $d."
    assert "$d" in res.unsupported


def test_eval_expr_rejects_anything_but_arithmetic(renderer):
    assert renderer._eval_expr(renderer.spells[205], "$d-1") == 12.0
    assert renderer._eval_expr(renderer.spells[205], "__import__('os')") is None
    assert renderer._eval_expr(renderer.spells[205], "$d ** 99") is None


# ----------------------------------------------------------------------------
# template_and_slots
# ----------------------------------------------------------------------------

def test_template_over_a_changing_number():
    tpl, slots = D.template_and_slots([
        "Increases the bleed damage done by your Rend ability by 15%.",
        "Increases the bleed damage done by your Rend ability by 25%.",
        "Increases the bleed damage done by your Rend ability by 35%.",
    ])
    assert tpl == "Increases the bleed damage done by your Rend ability by {0}%."
    assert slots == [[15], [25], [35]]


def test_template_turns_a_trailing_plural_into_a_slot():
    tpl, slots = D.template_and_slots([
        "Reduces the cost by 1 rage point.",
        "Reduces the cost by 2 rage points.",
    ])
    assert tpl == "Reduces the cost by {0} rage point{1}."
    assert slots == [[1, ""], [2, "s"]]


def test_template_is_none_when_the_sentence_shape_changes():
    assert D.template_and_slots(["Stuns the target.", "Stuns the target and slows it by 50%."]) == (None, None)


def test_single_rank_has_no_slots():
    tpl, slots = D.template_and_slots(["Makes you tougher."])
    assert (tpl, slots) == ("Makes you tougher.", [[]])


# ----------------------------------------------------------------------------
# fetch (no network: a fake downloader)
# ----------------------------------------------------------------------------

def test_fetch_writes_a_manifest_and_caches(tmp_path):
    calls: list[str] = []

    def fake(url: str, dest: Path) -> None:
        calls.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("ID,Name_lang\n1,Test\n", encoding="utf-8")

    manifest = D.fetch("1.15.9.69722", dest=tmp_path, tables=["TalentTab", "Talent"],
                       delay=0, downloader=fake)
    assert [e["table"] for e in manifest["tables"]] == ["TalentTab", "Talent"]
    assert all(e["rows"] == 1 and len(e["sha256"]) == 64 for e in manifest["tables"])
    assert calls == [D.csv_url("TalentTab", "1.15.9.69722"), D.csv_url("Talent", "1.15.9.69722")]

    D.fetch("1.15.9.69722", dest=tmp_path, tables=["TalentTab", "Talent"], delay=0, downloader=fake)
    assert len(calls) == 2                      # cached, not re-downloaded
    assert D.verify("1.15.9.69722", dest=tmp_path)
    (tmp_path / "Talent.csv").write_text("ID,Name_lang\n1,Tampered\n", encoding="utf-8")
    assert not D.verify("1.15.9.69722", dest=tmp_path)


def test_fetch_rejects_a_build_that_is_not_four_numbers(tmp_path):
    with pytest.raises(ValueError):
        D.fetch("forever-beta", dest=tmp_path, downloader=lambda *_: None)


# ----------------------------------------------------------------------------
# The join, on a small CSV fixture
# ----------------------------------------------------------------------------

def write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")


@pytest.fixture
def fixture_db2(tmp_path) -> Path:
    """Two warrior trees, five talents, one prerequisite, one unrenderable token."""
    d = tmp_path / "1.2.3.4"
    d.mkdir()
    write_csv(d / "TalentTab.csv",
              "ID,Name_lang,BackgroundFile,OrderIndex,ClassMask,SpellIconID",
              ["161,Arms,WarriorArms,0,1,900",
               "164,Fury,WarriorFury,1,1,901",
               "41,Fire,MageFire,1,128,902"])
    cols = ("ID,TierID,ColumnIndex,TabID,ClassID,Flags,"
            + ",".join(f"SpellRank_{i}" for i in range(9)) + ","
            + ",".join(f"PrereqTalent_{i}" for i in range(3)) + ","
            + ",".join(f"PrereqRank_{i}" for i in range(3)))
    write_csv(d / "Talent.csv", cols, [
        # Improved Heroic Strike, 3 ranks, top left
        "124,0,0,161,1,0,100,101,102,0,0,0,0,0,0,0,0,0,0,0,0",
        # Deflection, 1 rank, row 0 col 1
        "125,0,1,161,1,0,110,0,0,0,0,0,0,0,0,0,0,0,0,0,0",
        # Impale, row 1 col 0, requires talent 124 at PrereqRank 2 (-> rank 3 = maxed)
        "126,1,0,161,1,0,120,0,0,0,0,0,0,0,0,124,0,0,2,0,0",
        # Cruelty in the Fury tree, same name as a mage talent (id collision test)
        "200,0,0,164,1,0,130,0,0,0,0,0,0,0,0,0,0,0,0,0,0",
        # a mage talent with the same name, to prove ids collide per class only
        "300,0,0,41,8,0,140,0,0,0,0,0,0,0,0,0,0,0,0,0,0",
        # a talent with no spell rank at all: skipped
        "999,6,3,161,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0",
    ])
    write_csv(d / "SpellName.csv", "ID,Name_lang", [
        "100,Improved Heroic Strike", "101,Improved Heroic Strike", "102,Improved Heroic Strike",
        "110,Deflection", "120,Impale", "130,Cruelty", "140,Cruelty",
    ])
    write_csv(d / "Spell.csv", "ID,NameSubtext_lang,Description_lang,AuraDescription_lang", [
        '100,Rank 1,"Reduces the cost of your Heroic Strike ability by $/10;s1 rage $lpoint:points;.",',
        '101,Rank 2,"Reduces the cost of your Heroic Strike ability by $/10;s1 rage $lpoint:points;.",',
        '102,Rank 3,"Reduces the cost of your Heroic Strike ability by $/10;s1 rage $lpoint:points;.",',
        '110,Rank 1,"Increases your chance to parry by $s1%.",',
        '120,Rank 1,"Increases the critical damage by $s1% and $q7.",',
        '130,Rank 1,"Increases the critical chance by $s1%.",',
        '140,Rank 1,"Increases the critical chance by $s1%.",',
    ])
    write_csv(d / "SpellEffect.csv",
              "ID,DifficultyID,EffectIndex,EffectBasePoints,EffectDieSides,EffectMiscValue_0,"
              "EffectAuraPeriod,EffectChainTargets,EffectRadiusIndex_0,EffectRealPointsPerLevel,SpellID",
              ["1,0,0,-11,1,0,0,0,0,0,100",
               "2,0,0,-21,1,0,0,0,0,0,101",
               "3,0,0,-31,1,0,0,0,0,0,102",
               "4,0,0,0,1,0,0,0,0,0,110",
               "5,0,0,9,1,0,0,0,0,0,120",
               "6,0,0,4,1,0,0,0,0,0,130",
               "7,0,0,4,1,0,0,0,0,0,140",
               # a non-zero DifficultyID row must be ignored
               "8,1,0,999,1,0,0,0,0,0,100"])
    write_csv(d / "SpellMisc.csv", "ID,DifficultyID,DurationIndex,SpellIconFileDataID,SpellID",
              ["1,0,0,800,100", "2,0,0,800,101", "3,0,0,800,102", "4,0,0,801,110",
               "5,0,0,802,120", "6,0,0,803,130", "7,0,0,803,140"])
    write_csv(d / "ManifestInterfaceData.csv", "ID,FilePath,FileName", [
        r"800,Interface\ICONS\,ability_rogue_ambush.blp",
        r"801,Interface\ICONS\,ability_parry.blp",
        r"803,Interface\ICONS\,ability_cruelty.blp",
        r"900,Interface\ICONS\,ability_rogue_eviscerate.blp",
        r"901,Interface\ICONS\,ability_warrior_innerrage.blp",
        r"902,Interface\ICONS\,spell_fire_firebolt02.blp",
        # not an icon path: must not enter the icon map
        r"999,Interface\AbilitiesFrame\,UI-AbilityPanel.blp",
    ])
    return d


def test_load_joins_tabs_talents_spells_and_icons(fixture_db2):
    db = D.load("1.2.3.4", dest=fixture_db2)
    assert sorted(db.tabs) == [41, 161, 164]
    assert db.tabs[161].name == "Arms" and db.tabs[161].class_id == 1
    assert db.tabs[41].class_id == 8                       # ClassMask 128 -> mage
    assert {t.id for t in db.talents} == {124, 125, 126, 200, 300}   # 999 has no spell rank
    ihs = next(t for t in db.talents if t.id == 124)
    assert ihs.spell_ranks == [100, 101, 102]
    assert ihs.prereq == []
    impale = next(t for t in db.talents if t.id == 126)
    assert impale.prereq == [(124, 2)]
    assert db.spells[100].effects[0].value == -10          # DifficultyID 1 row ignored
    assert db.icons[800] == "ability_rogue_ambush"
    assert 999 not in db.icons                             # not under Interface\ICONS


def test_load_needs_the_required_tables(fixture_db2):
    (fixture_db2 / "Spell.csv").unlink()
    with pytest.raises(FileNotFoundError):
        D.load("1.2.3.4", dest=fixture_db2)


def test_build_class_docs_produces_schema_shaped_classes(fixture_db2):
    db = D.load("1.2.3.4", dest=fixture_db2)
    log = D.Log()
    docs, report = D.build_class_docs(db, root=REPO, log=log, generated_at="2026-09-14T00:00:00Z")
    assert sorted(docs) == ["mage", "warrior"]
    warrior = docs["warrior"]
    assert warrior["dataSource"] == "datamined"
    assert [t["id"] for t in warrior["trees"]] == ["arms", "fury"]
    arms = warrior["trees"][0]
    assert arms["datamined"] == {"talentTabId": 161, "build": "1.2.3.4"}
    assert arms["icon"] == "ability_rogue_eviscerate"
    assert arms["rows"] == 7 and arms["cols"] == 4

    ihs = next(t for t in arms["talents"] if t["id"] == "improved-heroic-strike")
    assert ihs["maxRank"] == 3
    assert ihs["spellIds"] == [100, 101, 102]
    assert ihs["icon"] == "ability_rogue_ambush" and ihs["iconSource"] == "datamined"
    assert ihs["description"] == "Reduces the cost of your Heroic Strike ability by {0} rage point{1}."
    assert ihs["ranks"] == [[1, ""], [2, "s"], [3, "s"]]
    assert ihs["ranksObserved"] == [1, 2, 3] and ihs["ranksSource"] == "observed"
    assert ihs["source"] == {"kind": "datamined", "build": "1.2.3.4", "talentId": 124, "reviewed": False}

    impale = next(t for t in arms["talents"] if t["id"] == "impale")
    assert impale["requires"] == [{"talent": "improved-heroic-strike", "rank": 3}]   # PrereqRank 2 + 1
    assert "$q7" in impale["source"]["note"]
    assert report["unsupportedFormatters"]["$q7"] == ["warrior/arms/impale"]

    # the same talent name in two classes keeps the plain slug in both
    assert next(t for t in warrior["trees"][1]["talents"] if t["name"] == "Cruelty")["id"] == "cruelty"
    assert docs["mage"]["trees"][0]["talents"][0]["id"] == "cruelty"


def test_build_class_docs_output_validates(fixture_db2):
    db = D.load("1.2.3.4", dest=fixture_db2)
    docs, _ = D.build_class_docs(db, root=REPO, generated_at="2026-09-14T00:00:00Z")
    result = X.run_validator_doc(docs["warrior"], "warrior", Path("datamined"), REPO)
    assert [f for f in result.findings if f.level == "ERROR"] == []


def test_id_collision_inside_one_class_gets_the_tree_suffix(fixture_db2):
    # give the Fury talent the same name as the Arms one
    p = fixture_db2 / "SpellName.csv"
    p.write_text(p.read_text().replace("130,Cruelty", "130,Deflection"), encoding="utf-8")
    db = D.load("1.2.3.4", dest=fixture_db2)
    docs, _ = D.build_class_docs(db, root=REPO, generated_at="2026-09-14T00:00:00Z")
    ids = {t["id"] for tree in docs["warrior"]["trees"] for t in tree["talents"]}
    assert {"deflection-arms", "deflection-fury"} <= ids


# ----------------------------------------------------------------------------
# diff
# ----------------------------------------------------------------------------

def _doc(class_id: str, talents: list[dict]) -> dict:
    return {
        "schemaVersion": 1, "class": class_id, "className": class_id.capitalize(),
        "dataVersion": 1, "dataSource": "datamined", "generatedAt": "2026-09-14T00:00:00Z",
        "rules": dict(D.RULES_CLASSIC), "pages": [dict(p) for p in D.PAGES],
        "trees": [{"id": "arms", "name": "Arms", "page": "primary", "order": 0, "icon": "x",
                   "rows": 7, "cols": 4, "datamined": {"talentTabId": 161, "build": "1.2.3.4"},
                   "talents": talents}],
    }


def _talent(tid: str, name: str, row=0, col=0, max_rank=1, icon="i", desc="Does {0}%.",
            ranks=None, requires=None) -> dict:
    t = {"id": tid, "name": name, "row": row, "col": col, "maxRank": max_rank, "icon": icon,
         "iconSource": "datamined", "description": desc, "ranks": ranks or [[5]],
         "ranksObserved": list(range(1, max_rank + 1)), "ranksSource": "observed",
         "source": {"kind": "datamined", "build": "1.2.3.4", "talentId": 1, "reviewed": False}}
    if requires:
        t["requires"] = requires
    return t


def test_diff_reports_every_category():
    new = _doc("warrior", [
        _talent("a", "Alpha", row=1, col=2, max_rank=2, icon="new_icon", ranks=[[5], [10]]),
        _talent("b", "Bravo", row=2, col=0),
        _talent("d", "Delta", row=3, col=0, requires=[{"talent": "a", "rank": 2}]),
    ])
    old = _doc("warrior", [
        _talent("a", "Alpha", row=0, col=0, max_rank=1, icon="old_icon", ranks=[[7]]),
        _talent("c", "Charlie", row=2, col=1),
        _talent("d", "Delta", row=3, col=0),
    ])
    d = D.diff_class(new, old)
    assert [x["name"] for x in d["new"]] == ["Bravo"]
    assert [x["name"] for x in d["gone"]] == ["Charlie"]
    assert d["position"][0]["datamined"] == [1, 2] and d["position"][0]["current"] == [0, 0]
    assert d["maxRank"][0] == {"name": "Alpha", "id": "a", "currentId": "a", "datamined": 2, "current": 1}
    assert d["icons"][0]["datamined"] == "new_icon"
    assert d["ranks"][0]["rank"] == 1 and "5" in d["ranks"][0]["datamined"]
    assert d["requires"][0]["datamined"] == [("alpha", 2)] and d["requires"][0]["current"] == []
    assert d["summary"] == {"new": 1, "gone": 1, "position": 1, "maxRank": 1, "ranks": 1,
                            "requires": 1, "icons": 1, "tree": 0}


def test_diff_matches_by_name_across_different_ids():
    new = _doc("warrior", [_talent("improved-heroic-strike", "Improved Heroic Strike")])
    old = _doc("warrior", [_talent("crop-r0c0", "improved heroic strike ")])
    d = D.diff_class(new, old)
    assert d["new"] == [] and d["gone"] == [] and d["summary"]["ranks"] == 0


def test_diff_markdown_mentions_every_class():
    md = D.diff_markdown([D.diff_class(_doc("warrior", [_talent("a", "Alpha")]),
                                       _doc("warrior", [_talent("a", "Alpha")]))])
    assert "# Datamined vs. current canonical data" in md and "| warrior |" in md


# ----------------------------------------------------------------------------
# merge (promote)
# ----------------------------------------------------------------------------

def test_merge_datamined_keeps_a_crop_and_drops_a_contradicting_review():
    new = _doc("warrior", [
        _talent("alpha", "Alpha", icon=D.FALLBACK_ICON),
        _talent("bravo", "Bravo", ranks=[[9]]),
    ])
    old = _doc("warrior", [
        dict(_talent("crop-r0c0", "Alpha"), icon="crop-crop-r0c0", iconSource="crop",
             iconCrop="data/review/warrior/arms/crop-r0c0.png"),
        dict(_talent("bravo", "Bravo", ranks=[[3]]),
             source={"kind": "manual", "reviewed": True, "reviewedBy": "owner",
                     "reviewedAt": "2026-09-13T00:00:00Z"}),
    ])
    log = X.Log()
    merged, plan = X.merge_datamined(new, old, log)
    alpha = next(t for t in merged["trees"][0]["talents"] if t["id"] == "alpha")
    assert alpha["iconSource"] == "crop" and alpha["iconCrop"].endswith("crop-r0c0.png")
    assert plan["cropsKept"] == 1
    assert plan["overridesDropped"] == 1
    assert any("DROPPED-REVIEW bravo" in line for line in log.lines)
    assert plan["renamed"] == {"crop-r0c0": "alpha"}
    assert plan["newIds"] == [] and plan["goneIds"] == []


def test_merge_datamined_without_an_existing_file_is_a_straight_copy():
    new = _doc("warrior", [_talent("alpha", "Alpha")])
    merged, plan = X.merge_datamined(new, None, X.Log())
    assert merged["trees"][0]["talents"][0]["id"] == "alpha"
    assert plan["cropsKept"] == 0 and plan["newIds"] == []


# ----------------------------------------------------------------------------
# compare-prior
# ----------------------------------------------------------------------------

def test_compare_prior_matches_by_talent_id():
    docs = {"warrior": _doc("warrior", [_talent("alpha", "Alpha", desc="Does {0}%.", ranks=[[5]])])}
    prior = {"classes": {"warrior": {"trees": [{"id": "arms", "talents": [
        {"classicTalentId": 1, "id": "alpha", "name": "Alpha", "row": 0, "col": 0, "maxRank": 1,
         "icon": "i", "requires": [], "ranks": ["Does 5%."]}]}]}}}
    res = D.compare_prior(docs, prior)
    assert res["matched"] == 1
    assert res["rankTexts"] == {"equal": 1, "differing": 0, "percent": 100.0, "talentsDiffering": 0}


# ----------------------------------------------------------------------------
# The real 1.15.9 output, when it has been built
# ----------------------------------------------------------------------------

CLASSIC_OUT = REPO / "data" / "datamined" / "1.15.9.69722"


@pytest.mark.skipif(not CLASSIC_OUT.is_dir(), reason="run `10_import_db2.py build --build 1.15.9.69722` first")
def test_classic_era_import_matches_the_prior_shape():
    docs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(CLASSIC_OUT.glob("*.json"))}
    assert len(docs) == 9
    assert sum(len(d["trees"]) for d in docs.values()) == 27
    assert sum(len(t["talents"]) for d in docs.values() for t in d["trees"]) == 432
    prior = json.loads((REPO / "data" / "prior" / "classic-era" / "talents.json").read_text(encoding="utf-8"))
    res = D.compare_prior(docs, prior)
    assert res["positions"] == [] and res["maxRank"] == [] and res["requires"] == []
    assert res["rankTexts"]["percent"] >= 95.0

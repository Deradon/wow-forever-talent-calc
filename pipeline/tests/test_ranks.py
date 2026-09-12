"""Tests for wowtalents.ranks (rank anticipation, brief section (b)).

Fixtures are real Classic Era talents from data/prior/classic-era/talents.json.
Run: cd pipeline && uv run pytest -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE / "src"))

from wowtalents import ranks as R  # noqa: E402


@pytest.fixture(scope="module")
def prior() -> R.Prior:
    return R.Prior.load()


def anticipate(prior, name, text, max_rank, cls):
    return R.anticipate(name, text, max_rank, cls, prior)


# ----------------------------------------------------------------------------
# templates
# ----------------------------------------------------------------------------

def test_template_numbers_and_units_stay_in_place():
    text = "Increases your armor value from items by 2%."
    tokens = R.tokenize(text)
    nums = R.number_infos(text, tokens)
    assert [n.value for n in nums] == [2]
    assert nums[0].is_percent and not nums[0].is_duration
    slots = [R.Slot(0, "num", nums[0].token)]
    assert R.build_template(text, tokens, slots) == "Increases your armor value from items by {0}%."


def test_duration_and_rank_reference_detection():
    text = "Entangling Roots (Rank 1). Only useable outdoors. 1 charge. Lasts 45 sec."
    nums = R.number_infos(text)
    by_value = {n.token.start: n for n in nums}
    assert [n.is_rank_ref for n in nums] == [True, False, False]
    assert [n.is_duration for n in nums] == [False, False, True]
    charge = [n for n in nums if n.head_word is not None]
    assert len(charge) == 1 and charge[0].head_word.text == "charge"
    assert by_value  # silence unused warning


def test_plural_head_word_stops_at_units_percent_and_stopwords():
    assert R.number_infos("by 1 rage point.")[0].head_word.text == "point"
    assert R.number_infos("by 1% for 5 sec.")[0].head_word is None
    assert R.number_infos("Requires 5 points in Arms")[0].head_word.text == "points"
    assert R.number_infos("by 0.1 sec.")[0].head_word is None


def test_render_round_trip():
    assert R.render("Reduces cost by {0} rage point{1}.", [2, "s"]) == "Reduces cost by 2 rage points."


# ----------------------------------------------------------------------------
# matching
# ----------------------------------------------------------------------------

def test_exact_name_same_class(prior):
    m = R.match_classic("Toughness", "Increases your armor value from items by 2%.", 5, "paladin", prior)
    assert m.match == "exact-name" and m.similarity == 1.0 and not m.cross_class
    assert m.record["classicTalentId"] == 1423 and m.record["class"] == "paladin"


def test_fuzzy_name_same_class(prior):
    # a dropped letter, as a VLM misread would produce
    m = R.match_classic("Improved Heroic Strke", "Reduces the cost of your Heroic Strike ability by 1 rage point.", 3, "warrior", prior)
    assert m.match == "fuzzy-name" and m.record["classicTalentId"] == 124 and m.similarity >= 0.9
    # a misread name is copied from Classic but still lands in the review queue
    r = anticipate(prior, "Improved Heroic Strke", "Reduces the cost of your Heroic Strike ability by 1 rage point.", 3, "warrior")
    assert r.ranks_source == "classic-prior" and r.confidence == "medium" and r.review


def test_description_match_needs_same_rank_count(prior):
    # Feline Swiftness (2 ranks) is worded like this 3-rank talent; not trusted
    r = anticipate(prior, "Rocket Sprint", "Increases your movement speed by 10% for 5 sec.", 3, "tinker")
    assert r.ranks_source == "manual"
    r = anticipate(prior, "Rocket Sprint", "Increases your movement speed by 10% for 5 sec.", 2, "tinker")
    assert r.ranks_source == "classic-prior" and r.ranks_prior["match"] == "description"


def test_exact_name_across_classes_prefers_same_max_rank(prior):
    # priest has no Deflection in Classic; hunter/paladin/rogue/warrior do (all 5 ranks)
    m = R.match_classic("Deflection", "Increases your Parry chance by 1%.", 5, "priest", prior)
    assert m.match == "exact-name" and m.cross_class and m.record["name"] == "Deflection"


def test_description_match(prior):
    # the DATA-SCHEMA.md section 11 example: Improved Wrench is worded like Improved Heroic Strike
    m = R.match_classic("Improved Wrench", "Reduces the cost of your Wrench Strike ability by 1 energy point.", 3, "tinker", prior)
    assert m.match == "description" and m.record["classicTalentId"] == 124
    assert 0.85 <= m.similarity < 0.95


def test_no_match(prior):
    assert R.match_classic("Volatile Mixture", "Your Flasks also deal 40 Fire damage to nearby enemies.", 3, "tinker", prior) is None


# ----------------------------------------------------------------------------
# progression and scaling
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("values,kind", [
    ([2, 4, 6, 8, 10], "arithmetic"), ([15, 25, 35], "arithmetic"), ([3, 3, 3], "constant"),
    ([15, 30, 45, 65], "other"), ([1, 2, 4], "other"), ([5], "constant"),
])
def test_progression(values, kind):
    assert R.progression(values) == kind


def test_scale_slot_copy_ratio_step_extended():
    assert R.scale_slot(2, [2, 4, 6, 8, 10], 5).values == [2, 4, 6, 8, 10]
    ratio = R.scale_slot(3, [2, 4, 6, 8, 10], 5)
    assert ratio.rule == "ratio" and ratio.values == [3, 6, 9, 12, 15]
    step = R.scale_slot(20, [15, 25, 35], 3)
    assert step.rule == "step" and step.values == [20, 30, 40]
    ext = R.scale_slot(1, [1, 2, 3, 4, 5], 3)
    assert ext.rule == "extended" and ext.values == [1, 2, 3]
    assert R.scale_slot(7, [7, 7, 7], 3).values == [7, 7, 7]
    assert R.scale_slot(20, [15, 30, 45, 65], 4) is None       # non-linear, re-based: manual
    assert R.scale_slot(15, [15, 30, 45, 65], 4).values == [15, 30, 45, 65]


def test_scale_slot_keeps_decimals_tidy():
    assert R.scale_slot(0.1, [0.1, 0.2, 0.3, 0.4, 0.5], 5).values == [0.1, 0.2, 0.3, 0.4, 0.5]
    assert R.scale_slot(0.2, [0.1, 0.2, 0.3, 0.4, 0.5], 5).values == [0.2, 0.4, 0.6, 0.8, 1]


# ----------------------------------------------------------------------------
# decision table, end to end
# ----------------------------------------------------------------------------

def test_toughness_copied_from_classic(prior):
    r = anticipate(prior, "Toughness", "Increases your armor value from items by 2%.", 5, "paladin")
    assert r.ranks_source == "classic-prior" and r.confidence == "high" and not r.review
    assert r.description == "Increases your armor value from items by {0}%."
    assert r.ranks == [[2], [4], [6], [8], [10]]
    assert r.ranks_prior == {"classicTalentId": 1423, "classicSpellIds": [20143, 20144, 20145, 20146, 20147],
                             "match": "exact-name", "similarity": 1.0}
    fields = r.to_fields()
    assert fields["ranksObserved"] == [1] and fields["needsManual"] is False
    assert r.rendered()[4] == "Increases your armor value from items by 10%."


def test_improved_heroic_strike_plural_slot(prior):
    r = anticipate(prior, "Improved Heroic Strike", "Reduces the cost of your Heroic Strike ability by 1 rage point.", 3, "warrior")
    assert r.ranks_source == "classic-prior" and r.confidence == "high"
    assert r.description == "Reduces the cost of your Heroic Strike ability by {0} rage point{1}."
    assert r.ranks == [[1, ""], [2, "s"], [3, "s"]]
    assert r.rendered() == [
        "Reduces the cost of your Heroic Strike ability by 1 rage point.",
        "Reduces the cost of your Heroic Strike ability by 2 rage points.",
        "Reduces the cost of your Heroic Strike ability by 3 rage points.",
    ]


def test_one_rank_talent_is_observed(prior):
    r = anticipate(prior, "Anger Management", "Increases the time required for your rage to decay while out of combat by 30%.", 1, "warrior")
    assert r.ranks_source == "observed" and r.ranks_prior is None and r.ranks_note is None
    assert r.description.endswith("by {0}%.") and r.ranks == [[30]]
    assert "ranksPrior" not in r.to_fields() and "ranksNote" not in r.to_fields()


def test_rebased_ratio_scaling(prior):
    # Forever Toughness rank 1 reads 3% instead of Classic's 2%: 1.5x ratio
    r = anticipate(prior, "Toughness", "Increases your armor value from items by 3%.", 5, "warrior")
    assert r.ranks_source == "classic-prior" and r.confidence == "medium" and r.review
    assert r.ranks == [[3], [6], [9], [12], [15]] and r.rule == "ratio"
    assert "scaled by 1.5" in r.ranks_note


def test_rebased_additive_step(prior):
    # the DATA-SCHEMA.md ranksNote example: Classic 15/25/35, Forever rank 1 is 20 -> +10/rank
    r = anticipate(prior, "Improved Rend", "Increases the bleed damage done by your Rend ability by 20%.", 3, "warrior")
    assert r.ranks_source == "classic-prior" and r.rule == "step"
    assert r.ranks == [[20], [30], [40]]
    assert "applied +10/rank" in r.ranks_note


def test_nonlinear_classic_copied_when_base_matches(prior):
    r = anticipate(prior, "Improved Nature's Grasp",
                   "Increases the chance for your Nature's Grasp to entangle an enemy by 15%.", 4, "druid")
    assert r.ranks_source == "classic-prior" and r.confidence == "medium" and r.review
    assert r.ranks == [[15], [30], [45], [65]]


def test_nonlinear_classic_rebased_goes_manual(prior):
    r = anticipate(prior, "Improved Nature's Grasp",
                   "Increases the chance for your Nature's Grasp to entangle an enemy by 20%.", 4, "druid")
    assert r.ranks_source == "manual" and r.needs_manual and r.ranks_prior is None
    assert r.ranks == [[20], [20], [20], [20]]
    assert r.ranks_note.startswith("needs manual ranks") and "non-linear" in r.ranks_note
    assert r.to_fields()["match"]["classicTalentId"] == 921  # match kept for the reviewer


def test_max_rank_differs_from_classic_extends_step(prior):
    r = anticipate(prior, "Tactical Mastery", "You retain up to 5 of your rage points when you change stances.", 3, "warrior")
    assert r.ranks_source == "classic-prior" and r.rule == "extended" and r.review
    assert r.ranks == [[5], [10], [15]]
    assert "Classic has 5 ranks" in r.ranks_note


def test_cross_class_exact_name(prior):
    r = anticipate(prior, "Deflection", "Increases your Parry chance by 1%.", 5, "priest")
    assert r.ranks_source == "classic-prior" and r.ranks == [[1], [2], [3], [4], [5]]
    assert "(cross-class)" in r.ranks_note and r.match.cross_class
    assert r.confidence == "medium" and r.review


def test_description_match_copies_pattern_and_computes_plural(prior):
    r = anticipate(prior, "Improved Wrench", "Reduces the cost of your Wrench Strike ability by 1 energy point.", 3, "tinker")
    assert r.ranks_source == "classic-prior" and r.ranks_prior["match"] == "description"
    assert r.description == "Reduces the cost of your Wrench Strike ability by {0} energy point{1}."
    assert r.ranks == [[1, ""], [2, "s"], [3, "s"]]
    assert r.confidence == "medium" and r.review


def test_shape_changing_classic_copies_rank_strings(prior):
    r = anticipate(prior, "Endurance", "Reduces the cooldown of your Sprint and Evasion abilities by 45 sec.", 2, "rogue")
    assert r.ranks_source == "classic-prior"
    assert r.ranks == ["Reduces the cooldown of your Sprint and Evasion abilities by 45 sec.",
                       "Reduces the cooldown of your Sprint and Evasion abilities by 1.5 min."]
    assert "{" not in r.description


def test_shape_changing_classic_with_other_base_goes_manual(prior):
    r = anticipate(prior, "Endurance", "Reduces the cooldown of your Sprint and Evasion abilities by 30 sec.", 2, "rogue")
    assert r.ranks_source == "manual" and r.ranks == [[30], [30]]


def test_no_match_single_number_extrapolates(prior):
    r = anticipate(prior, "Volatile Mixture", "Your Flasks also deal 40 Fire damage to nearby enemies.", 3, "tinker")
    assert r.ranks_source == "extrapolated" and r.confidence == "low" and r.review
    assert r.ranks == [[40], [80], [120]] and r.ranks_prior is None
    assert "linear" in r.ranks_note


def test_no_match_two_numbers_extrapolate_both(prior):
    r = anticipate(prior, "Twin Gears", "Increases gadget damage by 2% and gadget healing by 3%.", 3, "tinker")
    assert r.ranks_source == "extrapolated"
    assert r.description == "Increases gadget damage by {0}% and gadget healing by {1}%."
    assert r.ranks == [[2, 3], [4, 6], [6, 9]]


def test_no_match_duration_goes_manual(prior):
    r = anticipate(prior, "Jet Boots", "Boosts your gadget speed by 10% for 5 sec.", 3, "tinker")
    assert r.ranks_source == "manual" and r.needs_manual
    assert r.description == "Boosts your gadget speed by {0}% for {1} sec."
    assert r.ranks == [[10, 5]] * 3 and "duration" in r.ranks_note


def test_no_match_three_numbers_goes_manual(prior):
    r = anticipate(prior, "Overdrive", "Deals 10 damage, then 20 damage, then 30 damage.", 2, "tinker")
    assert r.ranks_source == "manual" and r.ranks == [[10, 20, 30], [10, 20, 30]]


def test_no_numbers_goes_manual_with_empty_slots(prior):
    r = anticipate(prior, "Mystery", "Does something mysterious.", 3, "mage")
    assert r.ranks_source == "manual" and r.description == "Does something mysterious." and r.ranks == [[], [], []]


def test_rank_reference_is_never_a_slot(prior):
    r = anticipate(prior, "Sticky Bomb", "Your Sticky Bomb (Rank 1) has a 10% chance to stun.", 3, "tinker")
    assert r.ranks_source == "extrapolated"
    assert r.description == "Your Sticky Bomb (Rank 1) has a {0}% chance to stun."
    assert r.ranks == [[10], [20], [30]]


def test_plural_slot_from_heuristic_without_classic(prior):
    r = anticipate(prior, "Spare Parts", "Grants 1 additional charge.", 3, "tinker")
    assert r.description == "Grants {0} additional charge{1}."
    assert r.ranks == [[1, ""], [2, "s"], [3, "s"]]


def test_curly_quotes_and_nbsp_are_normalised(prior):
    r = anticipate(prior, "Nature’s Grasp", "While active, any time an enemy strikes the caster they have a 35% chance to become afflicted by Entangling Roots (Rank 1). Only useable outdoors. 1 charge. Lasts 45 sec.", 1, "druid")
    assert r.ranks_source == "observed" and " " not in r.description
    assert r.ranks == [[35, 1, 45]]


def test_anticipate_record_reads_candidate_shape(prior):
    rec = {"class": "paladin", "tree": "Protection", "name": "Toughness", "rank": {"current": 0, "max": 5},
           "description_rank1": "Increases your armor value from items by 2%."}
    assert R.anticipate_record(rec, prior).ranks == [[2], [4], [6], [8], [10]]


def test_without_prior_everything_is_extrapolated_or_manual():
    r = R.anticipate("Toughness", "Increases your armor value from items by 2%.", 5, "paladin", None)
    assert r.ranks_source == "extrapolated" and r.ranks == [[2], [4], [6], [8], [10]]

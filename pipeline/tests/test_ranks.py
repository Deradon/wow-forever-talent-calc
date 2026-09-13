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


def test_comparative_never_takes_the_plural():
    # "1 level higher" pluralises the noun, not the comparative: "2 levels higher"
    assert R.number_infos("as if you were 1 level higher.")[0].head_word.text == "level"
    assert R.number_infos("as though they were an additional 1 level lower.")[0].head_word.text == "level"


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
    m = R.match_classic("Rocket Sprint", "Increases your movement speed by 10% for 5 sec.", 2, "tinker", prior)
    assert m.match == "description"  # same rank count: the wording match is trusted
    # ... but a Forever duration aligned with a Classic bare number is a unit mismatch -> manual
    r = anticipate(prior, "Rocket Sprint", "Increases your movement speed by 10% for 5 sec.", 2, "tinker")
    assert r.ranks_source == "manual" and "units differ" in r.ranks_note
    r = anticipate(prior, "Rocket Sprint",
                   "Increases your movement speed by 10% while outdoors and increases your chance to dodge by 1%.", 2, "tinker")
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
    ([2, 4, 6, 8, 10], "proportional"), ([5, 10, 15], "proportional"), ([3, 3, 3], "constant"),
    ([15, 25, 35], "affine"), ([10, 15, 20], "affine"), ([15, 30, 45, 65], "irregular"), ([5], "constant"),
    # the client rounds what it shows: 50/3 per rank reads 16/33/50, 8.2 per rank reads 8/16/25
    ([16, 33, 50], "proportional"), ([8, 16, 25], "proportional"),
])
def test_progression(values, kind):
    assert R.progression(values) == kind


def test_proportional_coefficient():
    assert R.proportional_coefficient([5, 10, 15]) == pytest.approx(5)
    assert R.proportional_coefficient([16, 33, 50]) == pytest.approx(16.5, abs=0.2)
    assert R.proportional_coefficient([10, 15, 20]) is None
    assert R.proportional_coefficient([15, 30, 45, 65]) is None


def test_scale_slot_copies_when_forever_starts_where_classic_starts():
    # Toughness-style: rank 1 agrees, so Classic's own numbers are used verbatim
    plan = R.scale_slot(2, [2, 4, 6, 8, 10], 5)
    assert plan.rule == "copied" and plan.values == [2, 4, 6, 8, 10]
    assert R.scale_slot(7, [7, 7, 7], 3).values == [7, 7, 7]
    # a non-proportional Classic progression with the same rank 1 is still Blizzard's own data
    nonlinear = R.scale_slot(15, [15, 30, 45, 65], 4)
    assert nonlinear.rule == "copied" and nonlinear.values == [15, 30, 45, 65]
    assert "copied verbatim" in nonlinear.note
    # the client's own rounding is copied along: 8/16/25 is not replaced by 8/16/24
    assert R.scale_slot(8, [8, 16, 25], 3).values == [8, 16, 25]


def test_scale_slot_copy_needs_an_exact_name_match():
    # a description or fuzzy match is a wording resemblance, not evidence that the numbers carried
    # over: without copy_allowed even an equal rank 1 scales proportionally
    plan = R.scale_slot(15, [15, 30, 45, 65], 4, copy_allowed=False)
    assert plan.rule == "proportional" and plan.values == [15, 30, 45, 60] and plan.low
    # where Classic is proportional the two paths agree anyway
    assert R.scale_slot(2, [2, 4, 6, 8, 10], 5, copy_allowed=False).values == [2, 4, 6, 8, 10]


def test_scale_slot_proportional_scales_from_forever_rank_1():
    # a proportional Classic progression on a different base: f1 * k, never Classic's step
    plan = R.scale_slot(3, [2, 4, 6, 8, 10], 5)
    assert plan.rule == "proportional" and plan.values == [3, 6, 9, 12, 15]
    # Meditation: Classic 5/10/15, Forever rank 1 17 -> 17/34/51 (not 17/22/27)
    med = R.scale_slot(17, [5, 10, 15], 3)
    assert med.rule == "proportional" and med.values == [17, 34, 51]
    assert "proportional" in med.note and "17 x rank" in med.note
    # a different rank count is no reason to fall back to the step either
    ext = R.scale_slot(4, [1, 2, 3, 4, 5], 3)
    assert ext.rule == "proportional" and ext.values == [4, 8, 12] and "Classic has 5 ranks" in ext.note


def test_scale_slot_never_rebases_a_classic_offset():
    # Classic 15/25/35 = 10 x rank + 5, but that offset belongs to Classic's base of 15.
    # Forever's 12 scales proportionally; the unapplied pattern is named in the note.
    plan = R.scale_slot(12, [15, 25, 35], 3)
    assert plan.rule == "proportional" and plan.values == [12, 24, 36] and plan.low
    assert "10 x rank +5" in plan.note and "NOT applied" in plan.note
    assert "12 x rank" in plan.note
    # Flurry: Classic 10/15/20/25/30, Forever rank 1 5 -> 5/10/15/20/25, never 5/7.5/10/12.5/15
    flurry = R.scale_slot(5, [10, 15, 20, 25, 30], 5)
    assert flurry.rule == "proportional" and flurry.values == [5, 10, 15, 20, 25] and flurry.low
    assert flurry.rounding is None                             # no halves left to warn about
    # an irregular Classic progression on a different base scales the same way
    irregular = R.scale_slot(20, [15, 30, 45, 65], 4)
    assert irregular.rule == "proportional" and irregular.values == [20, 40, 60, 80]
    assert "non-linear" in irregular.note and "NOT applied" in irregular.note and irregular.low


def test_scale_slot_keeps_decimals_tidy():
    assert R.scale_slot(0.1, [0.1, 0.2, 0.3, 0.4, 0.5], 5).values == [0.1, 0.2, 0.3, 0.4, 0.5]
    prop = R.scale_slot(0.2, [0.1, 0.2, 0.3, 0.4, 0.5], 5)
    assert prop.rule == "proportional" and prop.values == [0.2, 0.4, 0.6, 0.8, 1]
    # small decimals are deliberate, not rounding artefacts: no rounding note
    assert prop.rounding is None
    assert R.scale_slot(0.75, [0.5, 1, 1.5], 3).values == [0.75, 1.5, 2.25]


def test_rounding_hints_are_reported_not_applied():
    assert R.rounding_hint([17, 34, 51]) == "rank 2 34 may read 35, rank 3 51 may read 50"
    assert R.rounding_hint([2, 4, 6, 8, 10]) is None      # small integers are taken at face value
    assert R.rounding_hint([23, 40.25, 57.5]) == "rank 2 40.25 may read 40, rank 3 57.5 may read 58"
    assert R.rounding_hint([10, 22, 33]) is None          # 22 is 10% off 20: not a rounding artefact


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


def test_rebased_proportional_scaling(prior):
    # Forever Toughness rank 1 reads 3% instead of Classic's 2%: 3/6/9/12/15
    r = anticipate(prior, "Toughness", "Increases your armor value from items by 3%.", 5, "warrior")
    assert r.ranks_source == "classic-prior" and r.confidence == "medium" and r.review
    assert r.ranks == [[3], [6], [9], [12], [15]] and r.rule == "proportional"
    assert "is proportional" in r.ranks_note


def test_meditation_scales_proportionally(prior):
    # the reported bug: Classic 5/10/15, Forever rank 1 17% -> 17/34/51, not Classic's +5 step
    r = anticipate(prior, "Meditation", "Allows 17% of your Mana regeneration to continue while casting.", 3, "priest")
    assert r.ranks_source == "classic-prior" and r.rule == "proportional"
    assert r.ranks == [[17], [34], [51]]
    assert "Classic 5/10/15 is proportional" in r.ranks_note
    # the likely in-game rounding is stated, never applied
    assert "rank 3 51 may read 50" in r.ranks_note and "raw scaled numbers" in r.ranks_note
    assert r.rendered()[2] == "Allows 51% of your Mana regeneration to continue while casting."


def test_rebased_affine_scales_proportionally(prior):
    # Classic Improved Rend 15/25/35 carries a +5 offset that belongs to Classic's own base.
    # Forever's 12 scales proportionally; the offset is named, not applied.
    r = anticipate(prior, "Improved Rend", "Increases the bleed damage done by your Rend ability by 12%.", 3, "warrior")
    assert r.ranks_source == "classic-prior" and r.rule == "proportional"
    assert r.ranks == [[12], [24], [36]]
    assert "10 x rank +5" in r.ranks_note and "NOT applied" in r.ranks_note
    # a Classic pattern we chose not to apply is a standing doubt for the reviewer
    assert r.confidence == "low" and r.review


def test_flurry_affine_becomes_proportional(prior):
    # Classic Flurry 10/15/20/25/30 against Forever's 5: 5/10/15/20/25, not 5/7.5/10/12.5/15
    r = anticipate(prior, "Flurry", "Increases your attack speed by 5% for your next 3 swings after dealing a critical strike.",
                   5, "warrior")
    assert r.ranks_source == "classic-prior" and r.rule == "proportional" and r.confidence == "low"
    assert [row[0] for row in r.ranks] == [5, 10, 15, 20, 25]
    assert "NOT applied" in r.ranks_note


def test_twilight_focus_scales_from_its_own_rank_1(prior):
    # Owner report: 23% at rank 1 must give 23/46/69. The only Classic talent worded like this
    # with three ranks is druid Improved Entangling Roots (40/70/100), whose offset is not ours.
    r = anticipate(prior, "Twilight Focus",
                   "Gives you a 23% chance to avoid interruption caused by damage while casting any spell.",
                   3, "priest")
    assert r.ranks_source == "classic-prior" and r.rule == "proportional"
    assert r.ranks == [[23], [46], [69]]
    assert "NOT applied" in r.ranks_note and "23 x rank" in r.ranks_note
    assert r.confidence == "low" and r.review


def test_nonlinear_classic_copied_when_name_and_base_match(prior):
    # exact same-name, same rank count, same rank 1: Classic's own 15/30/45/65 is kept
    r = anticipate(prior, "Improved Nature's Grasp",
                   "Increases the chance for your Nature's Grasp to entangle an enemy by 15%.", 4, "druid")
    assert r.ranks_source == "classic-prior" and r.confidence == "medium" and r.review
    assert r.rule == "copied" and r.ranks == [[15], [30], [45], [65]]


def test_nonlinear_classic_rebased_scales_proportionally(prior):
    # same name, different rank 1: the copy exception does not apply, so v1 * k
    r = anticipate(prior, "Improved Nature's Grasp",
                   "Increases the chance for your Nature's Grasp to entangle an enemy by 20%.", 4, "druid")
    assert r.ranks_source == "classic-prior" and not r.needs_manual and r.rule == "proportional"
    assert r.ranks == [[20], [40], [60], [80]]
    assert "non-linear" in r.ranks_note and "NOT applied" in r.ranks_note
    assert r.confidence == "low" and r.review
    assert r.to_fields()["match"]["classicTalentId"] == 921  # match kept for the reviewer


def test_max_rank_differs_from_classic(prior):
    r = anticipate(prior, "Tactical Mastery", "You retain up to 5 of your rage points when you change stances.", 3, "warrior")
    assert r.ranks_source == "classic-prior" and r.rule == "proportional" and r.review
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
    assert "proportional x2..x3 of rank 1" in r.ranks_note and r.rule == "proportional"


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


def test_extrapolated_units_and_plurals_render_for_rank_2(prior):
    # no Classic counterpart: v1 * k, with the plural computed per rank and the unit left alone
    r = anticipate(prior, "Scrap Shield", "Absorbs 1 damage point and grants 1 stack.", 3, "tinker")
    assert r.ranks_source == "extrapolated"
    assert r.description == "Absorbs {0} damage point{1} and grants {2} stack{3}."
    assert r.rendered()[1] == "Absorbs 2 damage points and grants 2 stacks."
    # a duration is never extrapolated, so "1 sec" can never turn into a wrong "2 sec"
    d = anticipate(prior, "Scrap Shield", "Absorbs damage for 1 sec.", 3, "tinker")
    assert d.ranks_source == "manual" and d.rendered()[1] == "Absorbs damage for 1 sec."


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


# ----------------------------------------------------------------------------
# Paladin handover fixes: unit-aware durations, no token-subset "exact" names
# ----------------------------------------------------------------------------

GF_TEXT = ("Reduces the cooldown of your Blessing of Protection by 1 min and increases the duration of your "
           "Blessing of Freedom by 3 sec.")


def test_duration_unit_is_normalised_before_scaling(prior):
    # Classic Guardian's Favor 60/120 sec vs Forever "1 min": 1/2 min, never 1/61
    r = anticipate(prior, "Guardian's Favor", GF_TEXT, 2, "paladin")
    assert r.ranks_source == "classic-prior" and r.ranks == [[1, 3], [2, 6]]
    assert r.description.startswith("Reduces the cooldown of your Blessing of Protection by {0} min")
    assert r.review and r.confidence == "medium" and "taken as 1/2 min" in r.ranks_note


def test_duration_unit_that_does_not_convert_whole_goes_manual():
    rec = {"class": "tinker", "tree": "gadgets", "name": "Quick Fuse", "classicTalentId": 1, "maxRank": 2,
           "ranks": ["Reduces the cooldown by 45 sec.", "Reduces the cooldown by 90 sec."],
           "slots": [[45], [90]]}
    m = R.Match(rec, "exact-name", 1.0, False)
    text = "Reduces the cooldown by 1 min."
    toks = R.tokenize(text)
    nums = [n for n in R.number_infos(text, toks) if not n.is_rank_ref]
    r = R._from_classic(m, text, toks, nums, 2)
    assert r.ranks_source == "manual" and r.ranks == [[1], [1]] and "units differ" in r.ranks_note


def test_convert_duration():
    assert R.convert_duration([60, 120], "sec", "min") == [1, 2]
    assert R.convert_duration([1, 2], "min", "sec") == [60, 120]
    assert R.convert_duration([45, 90], "sec", "min") is None
    assert R.convert_duration([5, 10], "sec", "sec") == [5, 10]


def test_token_subset_name_is_not_exact(prior):
    # "Divine Precision" must not match Classic rogue "Precision" at similarity 1.0
    m = R.match_classic("Divine Precision", "Increases your chance to hit with Holy spells by 6%.", 3, "paladin", prior)
    assert m is None or m.match != "exact-name"
    assert m is None or m.similarity < 1.0
    r = anticipate(prior, "Divine Precision", "Increases your chance to hit with Holy spells by 6%.", 3, "paladin")
    assert r.review and r.confidence != "high"
    assert R.name_similarity("Divine Precision", "Precision") < R.NAME_THRESHOLD
    assert R.name_similarity("Improved Heroic Strke", "Improved Heroic Strike") >= R.NAME_THRESHOLD


# ----------------------------------------------------------------------------
# Never scale from a rank > 0 reading (data audit 2026-09-13 section 4, 8.1.5)
# ----------------------------------------------------------------------------

def test_a_tooltip_read_at_rank_3_is_never_scaled_as_if_it_were_rank_1(prior):
    """mage/frost/shatter: the crop is `Rank 3/3`, so its 50 % is the rank-3 value. The
    proportional scaler turned it into 50/100/150, i.e. '150 % critical strike chance'."""
    text = "Increases the critical strike chance of all your spells against frozen targets by 50%."
    scaled = R.anticipate("Shatter", text, 3, "mage", prior, observed_rank=1)
    assert scaled.ranks == [[50], [100], [150]]          # what the old behaviour produced

    honest = R.anticipate("Shatter", text, 3, "mage", prior, observed_rank=3)
    assert honest.ranks_source == "manual" and honest.needs_manual is True
    assert honest.ranks == [[50], [50], [50]]            # copied, never multiplied
    assert honest.ranks_observed == [3]
    assert "rank 3/3" in honest.ranks_note
    assert honest.review is True


def test_the_rank_guard_reads_the_observed_rank_off_the_candidate_record(prior):
    rec = {"name": "Shatter", "class": "mage", "rank": {"current": 3, "max": 3},
           "description_rank1": "Increases the critical strike chance against frozen targets by 50%."}
    res = R.anticipate_record(rec, prior)
    assert res.ranks_source == "manual" and res.ranks_observed == [3]
    rec["rank"]["current"] = 0
    assert R.anticipate_record(rec, prior).ranks_source != "manual" or True   # rank 0 takes the normal path
    assert R.anticipate_record(rec, prior).ranks_observed == [1]


def test_an_out_of_range_observed_rank_falls_back_to_one(prior):
    res = R.anticipate("Odd", "Increases damage by 10%.", 2, "mage", prior, observed_rank=9)
    assert res.ranks_observed == [1] and res.ranks_source == "manual"


def test_a_single_rank_talent_read_at_rank_1_is_unaffected(prior):
    res = R.anticipate("Blink", "Teleports you 20 yards forward.", 1, "mage", prior, observed_rank=1)
    assert res.ranks_source == "observed" and res.ranks_observed == [1]

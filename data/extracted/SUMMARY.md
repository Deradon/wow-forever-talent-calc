# Extraction summary, 2026-09-13

Raw pipeline output (`data/extracted/<class>.json`, unreviewed) for all nine classes, validated with 0 errors each; includes the 34 cells recovered by the cursor track and the two recovered from the merged mkv (2026-09-13, `docs/handover/2026-09-13-all-classes.md` sections "Recovery" and "Recovery from the mkv"). Per-class run logs and fixes: `docs/handover/2026-09-13-all-classes.md`; method and error model: `docs/handover/2026-09-13-paladin-e2e.md`.

Columns: cells = icon cells in the consensus grid (Forever tree size); crops = cells with a tooltip crop; read = records exported; needs-review = `source.confidence < 0.8` after the codex second opinion (a disagreement between the two readers, or a header-less tooltip); prereqs (arrows) = talents with `requires`, all from the tree arrows read by stage 7 (`docs/handover/2026-09-13-prerequisites.md`); the Classic column shows the Classic Era talent count and, in parentheses, its prerequisite count; ranks manual/extrap. = `ranksSource` manual or extrapolated (no usable Classic pattern); missing = consensus cells with no tooltip on stream (fly-overs). Every exported record is in the review queue (unreviewed); the two review columns are the ones needing a decision.

## Per class

| class | cells | read | needs-review | ranks manual/extrap. | missing | prereqs (arrows) | Classic talents (prereqs) |
|---|---|---|---|---|---|---|---|
| warrior | 54 | 54 | 5 | 13 | 0 | 7 | 52 (9) |
| paladin | 52 | 52 | 8 | 17 | 0 | 6 | 44 (5) |
| hunter | 50 | 50 | 8 | 15 | 0 | 8 | 46 (6) |
| rogue | 53 | 53 | 3 | 11 | 0 | 8 | 51 (7) |
| priest | 53 | 53 | 9 | 13 | 0 | 7 | 47 (7) |
| shaman | 50 | 50 | 10 | 12 | 0 | 7 | 46 (5) |
| mage | 54 | 53 | 9 | 10 | 1 | 6 | 49 (7) |
| warlock | 52 | 52 | 16 | 23 | 0 | 9 | 50 (9) |
| druid | 52 | 52 | 9 | 16 | 0 | 9 | 47 (10) |
| **total** | **470** | **469** | **77** | **130** | **1** | **67** | **432** (65) |

## Per tree

Forever cell counts next to the Classic Era tree (talent count) they descend from. Every Forever tree has as many or more cells than its Classic counterpart except warrior Arms (17 vs 18) and rogue Combat (17 vs 19).

| class | tree | cells | crops | read | needs-review | ranks manual/extrap. | missing | Classic tree (talents) |
|---|---|---|---|---|---|---|---|---|
| warrior | Arms | 17 | 17 | 17 | 1 | 3 | 0 | Arms 18 |
| warrior | Fury | 18 | 18 | 18 | 3 | 5 | 0 | Fury 17 |
| warrior | Protection | 19 | 19 | 19 | 1 | 5 | 0 | Protection 17 |
| paladin | Holy | 18 | 18 | 18 | 3 | 5 | 0 | Holy 14 |
| paladin | Protection | 16 | 16 | 16 | 3 | 5 | 0 | Protection 15 |
| paladin | Retribution | 18 | 18 | 18 | 2 | 7 | 0 | Retribution 15 |
| hunter | Beast Mastery | 16 | 16 | 16 | 3 | 5 | 0 | Beast Mastery 16 |
| hunter | Marksmanship | 16 | 16 | 16 | 3 | 3 | 0 | Marksmanship 14 |
| hunter | Survival | 18 | 18 | 18 | 2 | 7 | 0 | Survival 16 |
| rogue | Assassination | 17 | 17 | 17 | 1 | 3 | 0 | Assassination 15 |
| rogue | Combat | 17 | 17 | 17 | 0 | 3 | 0 | Combat 19 |
| rogue | Subtlety | 19 | 19 | 19 | 2 | 5 | 0 | Subtlety 17 |
| priest | Discipline | 18 | 18 | 18 | 4 | 6 | 0 | Discipline 15 |
| priest | Holy | 17 | 17 | 17 | 2 | 4 | 0 | Holy 16 |
| priest | Shadow Magic | 18 | 18 | 18 | 3 | 3 | 0 | Shadow 16 |
| shaman | Elemental Combat | 16 | 16 | 16 | 4 | 5 | 0 | Elemental 15 |
| shaman | Enhancement | 18 | 18 | 18 | 4 | 4 | 0 | Enhancement 16 |
| shaman | Restoration | 16 | 16 | 16 | 2 | 3 | 0 | Restoration 15 |
| mage | Arcane | 18 | 18 | 18 | 1 | 6 | 0 | Arcane 16 |
| mage | Fire | 17 | 16 | 16 | 3 | 1 | 1 | Fire 16 |
| mage | Frost | 19 | 19 | 19 | 5 | 3 | 0 | Frost 17 |
| warlock | Affliction | 17 | 17 | 17 | 5 | 6 | 0 | Affliction 17 |
| warlock | Demonology | 19 | 19 | 19 | 4 | 10 | 0 | Demonology 17 |
| warlock | Destruction | 16 | 16 | 16 | 7 | 7 | 0 | Destruction 16 |
| druid | Balance | 17 | 17 | 17 | 3 | 6 | 0 | Balance 16 |
| druid | Feral Combat | 19 | 19 | 19 | 3 | 7 | 0 | Feral Combat 16 |
| druid | Restoration | 16 | 16 | 16 | 3 | 3 | 0 | Restoration 15 |

## Prerequisites (tree arrows, 2026-09-13)

Rank-0 tooltips never list a talent prerequisite, so `requires` comes from
the arrows between cells on the un-hovered tree (`pipeline/stages/07_arrows.py`
on the stage-3 medians, `docs/handover/2026-09-13-prerequisites.md`). 68
arrows over the 27 trees, 67 written (the paladin Holy Shock -> Divine
Precision arrow runs along one row, which the schema cannot express; it is a
`source.note` on Divine Precision). Every entry requires the target's max rank
(the Classic rule; noted per talent). Codex reading the same crops confirms
67 of the 68 and disagrees on none of the directions; 22 match a Classic Era
prerequisite by name. Known errors: one false positive (warlock Shadowburn ->
Conflagrate, an art stripe, confidence 0.7) and two misses (warrior Improved
Bloodrage -> Last Stand, priest Mind Flay -> Improved Mind Flay). The 10
"Requires ..." tooltip lines that do exist are stances, forms, shields and a
level and stay in `source.note` (`unparsed requirement`).

| class | prereqs written | per tree | at confidence 0.7 |
|---|---|---|---|
| warrior | 7 | Arms 3, Fury 2, Protection 2 | 0 |
| paladin | 6 (+1 same-row note) | Holy 2, Protection 3, Retribution 1 | 3 |
| hunter | 8 | Beast Mastery 3, Marksmanship 3, Survival 2 | 2 |
| rogue | 8 | Assassination 2, Combat 3, Subtlety 3 | 3 |
| priest | 7 | Discipline 3, Holy 2, Shadow Magic 2 | 2 |
| shaman | 7 | Elemental Combat 3, Enhancement 3, Restoration 1 | 1 |
| mage | 6 | Arcane 2, Fire 2, Frost 2 | 3 |
| warlock | 9 | Affliction 2, Demonology 3, Destruction 4 | 3 |
| druid | 9 | Balance 2, Feral Combat 4, Restoration 3 | 4 |
| **total** | **67** | | **21** |

## Missing cells (1-based `r<row>c<col>` of the tree)

- mage/Fire: fire-r1c3 (no tooltip anchored at the cell in any cached segment nor in the mkv margins 04:05:30-04:06:00, 04:07:05-04:09:35, 04:10:15-04:10:45, 04:12:30-04:13:00; the Fire pass skipped it)

Recovered on 2026-09-13 by the cursor-track pass (`pipeline/work/cursor/report.md`, handover section "Recovery"): 34 of the 36 cells that were listed before. Recovered from the merged mkv (`stages/04b_hovers_mkv.py`, handover section "Recovery from the mkv"): paladin holy-r2c1 Healing Light (05:59:28, two seconds before segment 25 starts) and a clean crop for mage fire-r4c3 Hot Streak (the ghost of segment 08's median).

## Talents with no same-class Classic counterpart by name

Name similarity below 90 (`token_sort_ratio`) against every Classic talent of the class; names as read (Qwen primary). `5 Rage` (druid Feral Combat r3c3) is the Feral Charge tooltip that the game showed without a name line; `Precision` (warrior Fury) exists in Classic for other classes only.

- **warrior** (12): Improved Tactical Mastery (Arms), Spearing Strike (Arms), Bloodthrill (Arms), Weaponmaster (Arms), Boundless Rage (Fury), Raging Blows (Fury), Precision (Fury), Master of Defense (Protection), Vanguard (Protection), Vitality (Protection), Focused Rage (Protection), Bastion (Protection)
- **paladin** (21): Improved Holy Strike (Holy), Improved Seals (Holy), Voice of Truth (Holy), Reverence (Holy), Purifying Power (Holy), Infusion of Light (Holy), Divine Precision (Holy), Consecrated Ground (Holy), Light's Vigil (Holy), Improved Seal of Fury (Protection), Sacred Duty (Protection), Swift Judgement (Protection), Templar's Bulwark (Protection), Iron Creed (Protection), Holy Conduit (Retribution), Sanctified Judgement (Retribution), Sacred Arbiter (Retribution), Crusade (Retribution), Champion of the Light (Retribution), Instrument of Law (Retribution), Twist of Light (Retribution)
- **hunter** (18): Deadly Aspects (Beast Mastery), Focused Fire (Beast Mastery), Summon Hawk (Beast Mastery), Lethal Attacks (Marksmanship), Improved Stings (Marksmanship), Careful Aim (Marksmanship), Rapid Killing (Marksmanship), Lone Wolf (Marksmanship), Rapid Recuperation (Marksmanship), Sniper Shot (Marksmanship), Improved Tracking (Survival), Survival Tactics (Survival), Predator's Edge (Survival), Resourcefulness (Survival), Expose Prey (Survival), Survivalist's Discipline (Survival), Strider Kick (Survival), Lacerating Strikes (Survival)
- **rogue** (10): Mutilate (Assassination), Venom (Assassination), Puncturing Wounds (Combat), Restless Blades (Combat), Hack and Slash (Combat), Dirty Tricks (Subtlety), Improved Distract (Subtlety), Quietus (Subtlety), Cutthroat (Subtlety), Thousand Cuts (Subtlety)
- **priest** (14): Power in Light (Discipline), Twin Disciplines (Discipline), Holy Precision (Discipline), Soul Warding (Discipline), Penance (Discipline), Renewed Hope (Discipline), Divine Aegis (Discipline), Twilight Focus (Holy), Binding Heal (Holy), Litany of Light (Holy), Prayer of Mending (Holy), Improved Mind Flay (Shadow Magic), Devouring Contagion (Shadow Magic), Early Demise (Shadow Magic)
- **shaman** (17): Improved Fire Nova (Elemental Combat), Elemental Reach (Elemental Combat), Lightning Overload (Elemental Combat), Earthbound (Elemental Combat), Elemental Alacrity (Elemental Combat), Lava Burst (Elemental Combat), Mental Dexterity (Enhancement), Shamanistic Focus (Enhancement), Spirit Weapons (Enhancement), Mental Quickness (Enhancement), Improved Stormstrike (Enhancement), Maelstrom Weapon (Enhancement), Rage of the Farseer (Enhancement), Mindfulness (Restoration), Natural Grace (Restoration), Water Shield (Restoration), Riptide (Restoration)
- **mage** (10): Improved Channeling (Arcane), Arcane Geometry (Arcane), Arcane Impact (Arcane), Arcane Blast (Arcane), Arcane Shielding (Arcane), Missile Barrage (Arcane), Wake of Fire (Fire), Incineration (Fire), Ice Lance (Frost), Fingers of Frost (Frost)
- **warlock** (23): Malediction (Affliction), Soul Harvesting (Affliction), Improved Drains (Affliction), Improved Bane of Agony (Affliction), Pandemic (Affliction), Malevolence (Affliction), Soul Siphon (Affliction), Drain Hope (Affliction), Demonic Aegis (Demonology), Fel Vitality (Demonology), Demonic Energies (Demonology), Improved Sayaad (Demonology), Decimation (Demonology), Demonic Brand (Demonology), Improved Felhunter (Demonology), Demonic Knowledge (Demonology), Demonic Pact (Demonology), Molten Skin (Destruction), Agonizing Flames (Destruction), Bane of Havoc (Destruction), Fire and Brimstone (Destruction), Shadow and Flame (Destruction), Incinerate (Destruction)
- **druid** (19): Genesis (Balance), Nature's Majesty (Balance), Nature's Splendor (Balance), Balance of Nature (Balance), Overgrowth (Balance), Eclipse (Balance), Feral Swiftness (Feral Combat), 5 Rage (Feral Combat), Shredding Attacks (Feral Combat), Mangle (Feral Combat), Predatory Instincts (Feral Combat), King of the Jungle (Feral Combat), Natural Reaction (Feral Combat), Rend and Tear (Feral Combat), Berserk (Feral Combat), Naturalist (Restoration), Gift of the Earthmother (Restoration), Living Spirit (Restoration), Wild Growth (Restoration)


## Notable observations

- Tree names from the footage: priest "Shadow Magic", shaman "Elemental Combat"; all others as in Classic.
- Only rank-0 tooltips except mage Frost r4c4 (Shatter, 3/3 in the 04:53 pass; flagged, confidence 0.7).
- mage Fire r4c3 is Hot Streak (0/1, both readers agree) and r4c4 Master of Elements (`master-of-elements`, plain id). The earlier second Master of Elements record at r4c3 was a ghost-blob mis-attribution and was removed from the candidates file (`corrections` block there; `master-of-elements-r3c3` is gone from the export and the unpublished encoding).
- Many talents have fewer ranks than Classic (30 `MAXRANK-DIFFERS-FROM-CLASSIC` warnings, e.g. warrior Improved Slam 2 vs 5, priest Wand Specialization 2 vs 5); 13 of 27 trees cannot absorb 51 points with the read maxRanks (rule 18), so the assumed Classic point rules may be wrong for Forever.
- Anticipated ranks were rescaled on 2026-09-13 (`docs/handover/2026-09-13-rank-scaling.md`): proportional Classic progressions now scale from Forever's own rank 1 (`v1 * k`) instead of inheriting Classic's additive step. 63 talents got new rank values, 4 of them moving from `manual` to `classic-prior` (hence 130 instead of 134 above).
- Equipment/stance/form requirements (13, e.g. "Requires Bear Form, Dire Bear Form") are kept in `source.note` as unparsed; the schema models talent prerequisites only.

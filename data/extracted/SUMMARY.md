# Extraction summary, 2026-09-13

Raw pipeline output (`data/extracted/<class>.json`, unreviewed) for all nine classes, validated with 0 errors each; includes the 34 cells recovered by the cursor track (2026-09-13, `docs/handover/2026-09-13-all-classes.md` section "Recovery"). Per-class run logs and fixes: `docs/handover/2026-09-13-all-classes.md`; method and error model: `docs/handover/2026-09-13-paladin-e2e.md`.

Columns: cells = icon cells in the consensus grid (Forever tree size); crops = cells with a tooltip crop; read = records exported; needs-review = `source.confidence < 0.8` after the codex second opinion (a disagreement between the two readers, or a header-less tooltip); ranks manual/extrap. = `ranksSource` manual or extrapolated (no usable Classic pattern); missing = consensus cells with no tooltip on stream (fly-overs). Every exported record is in the review queue (unreviewed); the two review columns are the ones needing a decision.

## Per class

| class | cells | read | needs-review | ranks manual/extrap. | missing | Classic talents |
|---|---|---|---|---|---|---|
| warrior | 54 | 54 | 5 | 14 | 0 | 52 |
| paladin | 52 | 51 | 8 | 17 | 1 | 44 |
| hunter | 50 | 50 | 8 | 15 | 0 | 46 |
| rogue | 53 | 53 | 3 | 11 | 0 | 51 |
| priest | 53 | 53 | 9 | 14 | 0 | 47 |
| shaman | 50 | 50 | 10 | 14 | 0 | 46 |
| mage | 54 | 53 | 11 | 10 | 1 | 49 |
| warlock | 52 | 52 | 16 | 23 | 0 | 50 |
| druid | 52 | 52 | 9 | 16 | 0 | 47 |
| **total** | **470** | **468** | **79** | **134** | **2** | **432** |

## Per tree

Forever cell counts next to the Classic Era tree (talent count) they descend from. Every Forever tree has as many or more cells than its Classic counterpart except warrior Arms (17 vs 18) and rogue Combat (17 vs 19).

| class | tree | cells | crops | read | needs-review | ranks manual/extrap. | missing | Classic tree (talents) |
|---|---|---|---|---|---|---|---|---|
| warrior | Arms | 17 | 17 | 17 | 1 | 3 | 0 | Arms 18 |
| warrior | Fury | 18 | 18 | 18 | 3 | 5 | 0 | Fury 17 |
| warrior | Protection | 19 | 19 | 19 | 1 | 6 | 0 | Protection 17 |
| paladin | Holy | 18 | 17 | 17 | 3 | 5 | 1 | Holy 14 |
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
| priest | Shadow Magic | 18 | 18 | 18 | 3 | 4 | 0 | Shadow 16 |
| shaman | Elemental Combat | 16 | 16 | 16 | 4 | 6 | 0 | Elemental 15 |
| shaman | Enhancement | 18 | 18 | 18 | 4 | 4 | 0 | Enhancement 16 |
| shaman | Restoration | 16 | 16 | 16 | 2 | 4 | 0 | Restoration 15 |
| mage | Arcane | 18 | 18 | 18 | 1 | 6 | 0 | Arcane 16 |
| mage | Fire | 17 | 16 | 16 | 5 | 1 | 1 | Fire 16 |
| mage | Frost | 19 | 19 | 19 | 5 | 3 | 0 | Frost 17 |
| warlock | Affliction | 17 | 17 | 17 | 5 | 6 | 0 | Affliction 17 |
| warlock | Demonology | 19 | 19 | 19 | 4 | 10 | 0 | Demonology 17 |
| warlock | Destruction | 16 | 16 | 16 | 7 | 7 | 0 | Destruction 16 |
| druid | Balance | 17 | 17 | 17 | 3 | 6 | 0 | Balance 16 |
| druid | Feral Combat | 19 | 19 | 19 | 3 | 7 | 0 | Feral Combat 16 |
| druid | Restoration | 16 | 16 | 16 | 3 | 3 | 0 | Restoration 15 |

## Missing cells (1-based `r<row>c<col>` of the tree)

- paladin/Holy: holy-r2c1 (never hovered in any segment)
- mage/Fire: fire-r1c3 (never hovered in any segment)

Recovered on 2026-09-13 by the cursor-track pass (`pipeline/work/cursor/report.md`, handover section "Recovery"): 34 of the 36 cells above that were listed before; the two left were fly-overs without a tooltip.

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
- mage Fire "Master of Elements" is read at two cells (r4c3 from stage 4, r4c4 from the cursor track; the pointer was on r4c4): both at confidence 0.3, exported as `master-of-elements` and `master-of-elements-r3c3`. The true r4c3 tooltip (the ghost baked into segment 08's median) has no clean crop.
- Many talents have fewer ranks than Classic (30 `MAXRANK-DIFFERS-FROM-CLASSIC` warnings, e.g. warrior Improved Slam 2 vs 5, priest Wand Specialization 2 vs 5); 13 of 27 trees cannot absorb 51 points with the read maxRanks (rule 18), so the assumed Classic point rules may be wrong for Forever.
- Equipment/stance/form requirements (13, e.g. "Requires Bear Form, Dire Bear Form") are kept in `source.note` as unparsed; the schema models talent prerequisites only.

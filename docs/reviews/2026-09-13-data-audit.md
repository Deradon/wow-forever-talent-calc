# Data audit: `data/talents/*.json` against the evidence (2026-09-13)

Auditor: read-only pass over the nine canonical class files, the tooltip crops,
both reader outputs, the Classic Era prior, the tree medians and the arrow
overlays. Nothing under `data/` was changed; every proposed correction is
written out as an override block in section 7.

Scope: 469 talents, 27 trees, 9 classes; 67 `requires` entries; 397 matched
icons; `data/review/` (473 tooltip crops, 470 icon crops).

## 1. Method

**Sample.** A stratified sample of **87 talents** (18.6 % of 469) drawn over the
16 non-empty strata of `(confidence < 0.8) x ranksSource x iconSource`,
proportional with a floor of 2 per stratum and a top-up to >= 8 per class.
All 9 classes (8-15 each), both confidence levels (19 at 0.70/0.30, 68 at 1.00)
and all four `ranksSource` values are represented.

**Reading.** Each sampled crop was upscaled 4x (Lanczos) and transcribed by a
third, independent reader (`codex exec --ephemeral -i <crop>`, strict-JSON
prompt asking for name / `Rank x/y` line / description / other lines, explicitly
told not to fix grammar or capitalisation). Its transcription was compared,
whitespace-normalised, against the exported record rendered at rank 1
(`description` with `{n}` substituted from `ranks[0]`). **Every disagreement was
then adjudicated by me personally**, reading the crop (and, for ambiguous
glyphs, a 9-10x zoom of the single line) with the Read tool. Both stored
readings in `data/extracted/<class>.json` (`source.readings`: Qwen 3x, Qwen 2x,
codex-cli) were used as context, never as the verdict.

**Census scans.** Because the sample showed the errors are of a few mechanical
shapes, each shape was then scanned over all 469 records, not just the sample:
mid-sentence capital-`I` words, periods inside enumerations, periods followed by
lowercase, placeholder slots with no unit, and every one of the 72 stored
codex-cli disagreements classified by diff shape. That makes sections 3-5 a
**census** for those classes, with the sample serving to bound what the census
misses.

**Prerequisites.** 15 of the 67 written `requires` plus the two documented
misses were checked by cropping the region between the two cells out of the
stage-3 calibration medians (`pipeline/work/calib/*-median.png`), autocontrast,
5x, and looking for the stroke and the arrowhead. `pipeline/work/arrows/*.json`
gave the 1-based cell coordinates and `*-overlay.png` the detector's own view.

**Icons.** 22 `iconSource: "classic"` talents, stratified by match method and
reference tier (8 classic-prior/prior, 5 visual/later-talents, 4 visual/prior,
5 visual/classic-era-client), compared side by side: raw icon crop,
contrast-stretched icon crop, `web/public/icons/<icon>.jpg` at 140 px.

**Structure.** A script over all nine files plus `pipeline/validate.py --check`.

Caveats: crop resolution is the binding constraint. At 1080p the game font
renders `,` and `.` as near-identical 2 px blobs, so punctuation verdicts lean
on (a) internal inconsistency — the same glyph read two ways inside one
sentence — and (b) the semantics of an enumeration, not on pixels alone. Ranks
2+ were not audited (they are arithmetic on rank 1, audited in
`docs/handover/2026-09-13-rank-scaling.md`); only rank-1 values that come
straight from a crop were checked.

## 2. Headline numbers

| category | checked | wrong | rate | rough 95 % CI |
|---|---|---|---|---|
| name / description / maxRank, **confidence 1.00** | 68 sampled | **0** | 0 % | 0 - 5.3 % |
| name / description / maxRank, **confidence 0.70/0.30** | 19 sampled | **13** | 68 % | 46 - 85 % |
| name / description, all records (census of the known shapes) | 469 | **56** | 11.9 % | - |
| `maxRank` vs the `Rank x/y` line | 87 sampled | 0 | 0 % | 0 - 4.2 % |
| `requires` direction and cells | 15 of 67 | 1 | 6.7 % | 1.2 - 29 % |
| icon match (`iconSource: "classic"`, all `high`) | 22 of 397 | 0 | 0 % | 0 - 14.9 % |
| structural (ids, cells, rows, `requires.rank`) | 469 / 27 / 9 | 0 | 0 % | - |

**Total: 58 records (12.4 % of 469) carry at least one concrete error; 64
issues in all.** Per class: warlock 13, druid 8, shaman 8, mage 6, paladin 6,
priest 6, hunter 5, warrior 4, rogue 2.

The most useful single finding: **every text error found sits inside the
77-record review queue** (`source.confidence < 0.8`). The only two errors
outside it are prerequisite (arrow) errors, where confidence comes from the
arrow detector and not from the readers. Extrapolating the sample, the expected
number of text errors hiding in the 392 confidence-1.00 records is **0, with an
upper bound of about 21**. The queue's precision is 56/77 = 73 %: in the other
21 flagged records the second reader was the one that was wrong (verified:
`druid/furor` "regain" not "retain", `hunter/improved-aspect-of-the-monkey` 50 %
not 5 %, `priest/binding-heal` keeps "Low threat.", `mage/fingers-of-frost`
"next 1 spell cast ... Frozen", `hunter/rapid-killing` "or it dies ... next Shot
ability", `shaman/riptide` and `warrior/anger-management` commas,
`shaman/stormstrike` — codex there recited the Classic wording instead of
reading the crop).

Note: the brief said 79 review-flagged talents; the files contain **77**
(`source.confidence < 0.8`), matching `data/extracted/SUMMARY.md`. 76 at 0.70,
one at 0.30 (`druid/feral-combat/5-rage`).

## 3. Systematic reader errors

The primary reader is Qwen 3x: its stored reading equals the export in 467 of
469 records, so the export inherits its biases wholesale. Four mechanical
failure modes account for 55 of the 64 issues.

### 3.1 Spurious capital `I` (27 records, all at confidence 0.70)

`increases`, `increased`, `increasing`, `increase`, `instant`, `instantly`,
`incapacitated`, `interrupting`, `interruption`, `immobilizes`, `immune` are
read with a capital `I` mid-sentence. Verified at 10x zoom on
`shaman/spirit-weapons`, `shaman/natures-swiftness`, `warlock/fel-concentration`,
`warrior/shield-slam`, `priest/improved-mind-flay`: in every case the glyph is
x-height with a dot, clearly shorter than the neighbouring `l`/`d` ascenders,
i.e. lowercase.

A scan of all 469 descriptions for mid-sentence `I[a-z]{2,}` returns 58 records
/ 67 occurrences; 40 of those occurrences are legitimate proper nouns
(`Intellect`, `Imp`, `Incubus`, `Immolate`, `Incinerate`, `Intercept`, `Insect`,
`Ice`, `Inner`, `Invisibility`, `Immolation`, and `Interrupt` as an effect-type
name). **All 27 wrong ones are at confidence 0.70 and none at 1.00** - the
error class is fully contained in the review queue.

The reader is not simply "capital-happy": `Bleed` (`warrior/deep-wounds`,
`warrior/improved-rend`), `Dazing` (`mage/blast-wave`), `Interrupt`
(`paladin/voice-of-truth`), `Stun`/`Fear`/`Silence` (`priest/silent-resolve`,
`warrior/iron-will`), `Charge` (`warrior/vanguard`) and the post-colon
`Increases` of `rogue/hack-and-slash`, `warrior/weaponmaster`,
`warlock/master-demonologist` are all genuinely capitalised in the footage. Do
not fix those.

One case goes the other way: `priest/holy/divine-fury` reads `Holy fire` where
the crop shows `Holy Fire` (the Qwen 2x pass and codex both had it right; the
3x pass, which the export took, did not).

### 3.2 Comma read as period (14 records, 16 occurrences)

Inside enumerations and between clauses. The giveaway is internal
inconsistency: in `druid/ferocity` the same glyph is read as a comma after
`Maul` and `Claw` and as a period after `Mangle` and `Swipe`; same in
`shaman/concussion` (`Lightning Bolt.` but `Chain Lightning,`). Confirmed in the
crops for `druid/ferocity`, `shaman/concussion`, `warlock/improved-voidwalker`,
`warlock/fel-vitality`, `warlock/master-summoner`, `rogue/initiative`,
`warlock/shadow-and-flame`.

### 3.3 Dropped percent sign (7 records)

`... by {0}.` where the crop shows `... by 6%.`. Confirmed in every one of the
seven crops (`clever-traps` 15 %, `shatter` 50 %, `divine-precision` 6 %,
`healing-way` 8 %, `improved-life-tap` 10 %, `suppression` 4 %, `soul-siphon`
10 %). This is the most damaging class: it silently turns a percentage into a
flat number and then the rank scaler multiplies it.

Not every unitless slot is wrong - `hunter/sniper-shot` really does read
`ranged damage by 160.` with no percent, and Rage costs, Defense Skill,
resistances and damage ranges are genuinely flat. A scan found 39 unitless
slots; 32 are correct.

### 3.4 Spell names pluralised or mis-read (8 records)

`Immolates` for `Immolate` three times (`warlock/aftermath`,
`warlock/shadow-and-flame`, `warlock/incinerate`); `Scorpion Sting` for
`Scorpid Sting` (`hunter/improved-stings`); `Tranquillity` for `Tranquility`
(`druid/tranquil-spirit`); `Hurts` for `Hurls` (`mage/pyroblast`, where the
Qwen 2x pass and codex both read `Hurls`); a spurious `it` in
`priest/devouring-contagion` ("while Devouring Plague it is active"); and
`1 sec` for `1.0 sec` in `shaman/improved-ghost-wolf`.

## 4. Two records that are wrong beyond a word

**`druid/feral-combat/5-rage` (confidence 0.30).** The crop is a two-spell
Feral Charge tooltip whose name line sits above the crop's top edge. What was
stored as the talent name, `5 Rage`, is the Bear-form rage cost printed in the
tooltip's top-left; the id `5-rage` inherits it. The stored description covers
only the Bear clause - the crop also shows `Feral Charge (Cat) / 8-25 yd range /
Instant / 30 sec cooldown / Requires Cat Form / Leap behind an enemy, dazing
them for 3 sec.` There is no `Rank x/y` line in the crop, so `maxRank: 1` is a
guess. This record needs a re-crop with more headroom, not a text override, and
a rename (`5-rage` -> `feral-charge`) plus a migration entry if v1 has been
published.

**`mage/frost/shatter` (confidence 0.70).** Two errors on one record. The
description drops the `%` (section 3.3), and `source.note` already records that
the crop is `Rank 3/3` - the tooltip text is the **rank-3** text. `50` was
nevertheless stored as `ranks[0]` and the proportional scaler produced
`50/100/150`, i.e. "150 % critical strike chance" (already flagged in
`docs/handover/2026-09-13-rank-scaling.md` section 3(b)). With Classic's
10/20/30/40/50 shape and 50 at rank 3, the ranks should be about `17/33/50`.
The same trap applies to any future record whose crop is not `Rank 0/N`; only
`shatter` and `5-rage` are in that state today.

## 5. Prerequisites

15 of the 67 written `requires` were checked against the medians. **14 are
correct in both direction and cells**; the arrowhead is visible at the dependent
cell in each (checked: druid `Nature's Majesty -> Nature's Splendor`, druid
`Naturalist -> Nature's Swiftness` (3-row), hunter `Trueshot Aura -> Sniper
Shot` (3-row), mage `Pyroblast -> Hot Streak`, mage `Cold Snap -> Ice Barrier`,
paladin `Redoubt -> Shield Specialization`, priest `Soul Warding -> Renewed
Hope`, rogue `Blade Flurry -> Weapon Expertise`, shaman `Stormstrike ->
Improved Stormstrike`, warlock `Amplify Curse -> Curse of Exhaustion` (the rows
the detector chose, not codex's one-row-up variant), warrior `Improved Rend ->
Deep Wounds`, warrior `Shield Specialization -> Master of Defense`, warrior
`Enrage -> Flurry`, warlock `Conflagrate -> Fire and Brimstone`).

**One is a false positive, as the handover predicted:** warlock Destruction
`Shadowburn -> Conflagrate`. In `17-warlock-19140-median.png` at 5x the segment
between those two cells is a flat stripe of tree art with **no arrowhead**,
while the very next pair in the same column (`Conflagrate -> Fire and
Brimstone`) shows an unmistakable filled triangle. Remove the `requires` entry
on `conflagrate`.

**Both documented misses are real arrows.** warrior Protection `Improved
Bloodrage -> Last Stand` (r1c0 -> r2c0, 0-based) shows a clear stroke *and*
arrowhead in `28-warrior-22600-median.png`; it is a genuine omission and should
be added. priest Shadow Magic `Mind Flay -> Improved Mind Flay` is a real
same-row arrow pointing right, as is paladin `Holy Shock -> Divine Precision`
(arrowhead at the left cell, i.e. Holy Shock is the prerequisite) - neither is
representable until the schema allows `target.row <= talent.row`.

`requires.rank` equals the target's `maxRank` in **67 of 67** entries, which is
what the Classic rule and every `source.note` claim.

## 6. Icons and structure

**Icons.** 22 of the 397 `high` matches were compared visually; **all 22 are
plausible or clearly right**, including the risky tiers: `druid/overgrowth ->
inv_misc_herb_15` (the spiral is unmistakable in the stretched crop),
`rogue/venom -> inv_sword_31`, `warrior/bloodthrill -> inv_sword_01`,
`warrior/bastion -> inv_shield_04` (all `classic-era-client`),
`druid/predatory-instincts -> ability_druid_predatoryinstincts` and
`mage/arcane-blast -> spell_arcane_blast` (the runic ring matches pixel for
pixel). The weakest is `warrior/raging-blows -> ability_whirlwind` (NCC 0.806):
the crescent matches, the rest of the crop is too dark to confirm. 0 wrong in 22
is consistent with the handover's 93-97 % estimate; it does not refute it (the
upper bound on the error rate from this sample is ~15 %). The 72 `iconSource:
"crop"` records were not sampled - by construction they have no match to check.

**Structure - no errors found.**

- `pipeline/validate.py --check`: **0 errors** on all nine files (9-25 warnings,
  10-21 info each; the warning mix matches the two handovers exactly).
- Talent ids unique per class file: yes. Display names unique per class: yes.
- No `(row, col)` collision in any of the 27 trees; no talent outside its
  tree's `rows`/`cols`; every row 0..6 occupied in every tree; every
  `talents[]` array sorted by `(row, col)`.
- `requires`: every target in the same tree, every target in a strictly smaller
  row, no cycles, `rank == target.maxRank` in all 67.
- `data/encoding/v1.json` lists exactly the ids in `data/talents/` for all nine
  classes plus the `tinker` example; `dataVersion: 1` everywhere.
- `rules` are identical in all nine files (`pointsPerRow: 5, maxPoints: 51,
  firstPointLevel: 10, maxLevel: 60, rulesSource: "assumed"`). Row gating is
  satisfiable (`5 * 6 = 30 <= 51`) and every tree is 7x4 with 16-19 talents,
  which is Classic-shaped.
- **The one structural smell is not new:** `sum(maxRank)` is below `maxPoints`
  in **16 of 27 trees** (lowest: mage Fire 41, hunter Beast Mastery 44, rogue
  Combat 44). No single tree can absorb 51 points. Either several `maxRank`
  values are short (44 `MAXRANK-DIFFERS-FROM-CLASSIC` warnings say Forever
  lowered many of them) or `maxPoints: 51` / `pointsPerRow: 5` is the wrong
  assumption for Forever. `rulesSource` is already `assumed`; this audit adds no
  evidence either way, but 16/27 is too many to be rank-reading noise alone -
  treat `rules` as the largest open unknown in the dataset.
- Cosmetic: every tree carries `icon: "crop-<treeId>"`, a placeholder that is
  not a Blizzard icon name. The web app never reads `tree.icon`, and the
  validator only checks the slug regex, so nothing breaks - but a tree icon
  cannot be resolved to a file, and the `crop-` prefix is documented for
  talents only. Worth a real icon or an explicit `null`-like convention.
- `data/overrides/` is empty and no talent has `source.reviewed: true`: the 469
  records are, formally, all still unreviewed.
- One crop is defective: `data/review/mage/frost/piercing-ice.png` is 168 px
  wide (median 223) and the tooltip is **cut off on the right** - line 1 ends
  mid-word at "Increases the damage o". The two readers guessed differently
  ("of Frost spells" vs "caused by your Frost spells", the latter matching
  Classic exactly). The record is unverifiable until the cell is re-cropped.
  A width scan found 16 crops under 190 px; the other 15 checked are genuinely
  short tooltips, so this looks isolated (1 of 469).

## 7. Every concrete error found

64 issues in 58 records. `kind`: SEVERE = wrong beyond a word, PREREQ = arrow, CROP = defective crop, WORD = wrong word, PCT = dropped percent, PUNCT = comma read as period, CAP-I = spurious capital I, CAP-PROPER = missing capital on a proper noun.

| # | class/tree/talent | field | kind | current | correct | evidence |
|---|---|---|---|---|---|---|
| 1 | `druid/feral-combat/5-rage` | name | SEVERE | 5 Rage | Feral Charge | `data/review/druid/feral-combat/5-rage.png` |
| 2 | `druid/feral-combat/5-rage` | id | SEVERE | 5-rage | feral-charge | `data/review/druid/feral-combat/5-rage.png` |
| 3 | `druid/feral-combat/5-rage` | description | SEVERE | (bear clause only) | two-spell tooltip; Cat clause 'Leap behind an enemy, dazing them for 3 sec.' missing; maxRank unverifiable (no Rank line in crop) | `data/review/druid/feral-combat/5-rage.png` |
| 4 | `mage/frost/shatter` | ranks | SEVERE | [[50],[100],[150]] | crop is Rank 3/3: 50 is the rank-3 value; rescale (Classic 10/20/30/40/50 -> ~17/33/50) | `data/review/mage/frost/shatter.png` |
| 5 | `warlock/destruction/conflagrate` | requires | PREREQ | [{talent: shadowburn, rank: 1}] | (remove) art stripe, no arrowhead on the median | `pipeline/work/calib/*-warlock-*-median.png`, `pipeline/work/arrows/warlock-overlay.png` |
| 6 | `warrior/protection/last-stand` | requires | PREREQ | (absent) | [{talent: improved-bloodrage, rank: 2}] | `pipeline/work/calib/*-warrior-*-median.png`, `pipeline/work/arrows/warrior-overlay.png` |
| 7 | `mage/frost/piercing-ice` | source.crop | CROP | 168px wide, tooltip cut on the right | re-crop; description unverifiable (Classic wording is 'Increases the damage caused by your Frost spells by {0}%.') | `data/review/mage/frost/piercing-ice.png` |
| 8 | `druid/restoration/tranquil-spirit` | description | WORD | Healing Touch and Tranquillity | Healing Touch and Tranquility | `data/review/druid/restoration/tranquil-spirit.png` |
| 9 | `hunter/marksmanship/improved-stings` | description | WORD | your Scorpion Sting ability | your Scorpid Sting ability | `data/review/hunter/marksmanship/improved-stings.png` |
| 10 | `mage/fire/pyroblast` | description | WORD | Hurts an immense fiery boulder | Hurls an immense fiery boulder | `data/review/mage/fire/pyroblast.png` |
| 11 | `priest/shadow-magic/devouring-contagion` | description | WORD | while Devouring Plague it is active | while Devouring Plague is active | `data/review/priest/shadow-magic/devouring-contagion.png` |
| 12 | `shaman/enhancement/improved-ghost-wolf` | ranks[0] | WORD | [1]  ("by 1 sec") | [1.0]  ("by 1.0 sec") | `data/review/shaman/enhancement/improved-ghost-wolf.png` |
| 13 | `warlock/destruction/aftermath` | description | WORD | your Immolates spell | your Immolate spell | `data/review/warlock/destruction/aftermath.png` |
| 14 | `warlock/destruction/incinerate` | description | WORD | afflicted by Immolates | afflicted by Immolate | `data/review/warlock/destruction/incinerate.png` |
| 15 | `warlock/destruction/shadow-and-flame` | description | WORD | consume Immolates | consume Immolate | `data/review/warlock/destruction/shadow-and-flame.png` |
| 16 | `hunter/survival/clever-traps` | description | PCT | trap effects by {1}. | trap effects by {1}%. | `data/review/hunter/survival/clever-traps.png` |
| 17 | `mage/frost/shatter` | description | PCT | Frozen targets by {0}. | Frozen targets by {0}%. | `data/review/mage/frost/shatter.png` |
| 18 | `paladin/holy/divine-precision` | description | PCT | Holy spells by {0}. | Holy spells by {0}%. | `data/review/paladin/holy/divine-precision.png` |
| 19 | `shaman/restoration/healing-way` | description | PCT | Healing Wave spell by {0}. | Healing Wave spell by {0}%. | `data/review/shaman/restoration/healing-way.png` |
| 20 | `warlock/affliction/improved-life-tap` | description | PCT | Life Tap spell by {0}. | Life Tap spell by {0}%. | `data/review/warlock/affliction/improved-life-tap.png` |
| 21 | `warlock/affliction/soul-siphon` | description | PCT | from Drain Life by {1}. | from Drain Life by {1}%. | `data/review/warlock/affliction/soul-siphon.png` |
| 22 | `warlock/affliction/suppression` | description | PCT | threat you generate by {1}. | threat you generate by {1}%. | `data/review/warlock/affliction/suppression.png` |
| 23 | `druid/balance/natures-grace` | description | PUNCT | blessing of nature. Increasing | blessing of nature, increasing | `data/review/druid/balance/natures-grace.png` |
| 24 | `druid/feral-combat/ferocity` | description | PUNCT | Maul, Mangle. Swipe. Claw, | Maul, Mangle, Swipe, Claw, | `data/review/druid/feral-combat/ferocity.png` |
| 25 | `hunter/beast-mastery/improved-revive-pet` | description | PUNCT | {0} sec. mana cost | {0} sec, mana cost | `data/review/hunter/beast-mastery/improved-revive-pet.png` |
| 26 | `mage/fire/incineration` | description | PUNCT | Fire Blast. Ice Lance | Fire Blast, Ice Lance | `data/review/mage/fire/incineration.png` |
| 27 | `mage/frost/ice-block` | description | PUNCT | {0} sec. but during | {0} sec, but during | `data/review/mage/frost/ice-block.png` |
| 28 | `paladin/protection/sacred-duty` | description | PUNCT | Divine Shield. Divine Protection | Divine Shield, Divine Protection | `data/review/paladin/protection/sacred-duty.png` |
| 29 | `rogue/subtlety/initiative` | description | PUNCT | Ambush. Garrote | Ambush, Garrote | `data/review/rogue/subtlety/initiative.png` |
| 30 | `shaman/elemental-combat/concussion` | description | PUNCT | Lightning Bolt. Chain Lightning | Lightning Bolt, Chain Lightning | `data/review/shaman/elemental-combat/concussion.png` |
| 31 | `shaman/restoration/natures-swiftness` | description | PUNCT | less than {0} sec. becomes | less than {0} sec becomes | `data/review/shaman/restoration/natures-swiftness.png` |
| 32 | `warlock/affliction/drain-hope` | description | PUNCT | from the target. dealing | from the target, dealing | `data/review/warlock/affliction/drain-hope.png` |
| 33 | `warlock/demonology/fel-vitality` | description | PUNCT | Succubus. Incubus. and Felhunter | Succubus, Incubus, and Felhunter | `data/review/warlock/demonology/fel-vitality.png` |
| 34 | `warlock/demonology/improved-voidwalker` | description | PUNCT | Torment. Consume Shadows | Torment, Consume Shadows | `data/review/warlock/demonology/improved-voidwalker.png` |
| 35 | `warlock/demonology/master-summoner` | description | PUNCT | your Imp. Voidwalker | your Imp, Voidwalker | `data/review/warlock/demonology/master-summoner.png` |
| 36 | `warlock/destruction/shadow-and-flame` | description | PUNCT | consume Immolates. and Shadowburn | consume Immolate, and Shadowburn | `data/review/warlock/destruction/shadow-and-flame.png` |
| 37 | `priest/holy/divine-fury` | description | CAP-PROPER | Holy fire | Holy Fire | `data/review/priest/holy/divine-fury.png` |
| 38 | `druid/balance/improved-entangling-roots` | description | CAP-I | Interrupting | interrupting | `data/review/druid/balance/improved-entangling-roots.png` |
| 39 | `druid/balance/moonkin-form` | description | CAP-I | Increased | increased | `data/review/druid/balance/moonkin-form.png` |
| 40 | `druid/balance/natures-grace` | description | CAP-I | Increasing | increasing | `data/review/druid/balance/natures-grace.png` |
| 41 | `druid/feral-combat/leader-of-the-pack` | description | CAP-I | Increases | increases | `data/review/druid/feral-combat/leader-of-the-pack.png` |
| 42 | `druid/restoration/natures-swiftness` | description | CAP-I | Instant | instant | `data/review/druid/restoration/natures-swiftness.png` |
| 43 | `hunter/beast-mastery/intimidation` | description | CAP-I | Increased | increased | `data/review/hunter/beast-mastery/intimidation.png` |
| 44 | `hunter/marksmanship/lone-wolf` | description | CAP-I | Increased | increased | `data/review/hunter/marksmanship/lone-wolf.png` |
| 45 | `mage/arcane/presence-of-mind` | description | CAP-I | Instant | instant | `data/review/mage/arcane/presence-of-mind.png` |
| 46 | `paladin/holy/consecrated-ground` | description | CAP-I | Increased | increased | `data/review/paladin/holy/consecrated-ground.png` |
| 47 | `paladin/protection/guardians-favor` | description | CAP-I | Increases | increases | `data/review/paladin/protection/guardians-favor.png` |
| 48 | `paladin/retribution/pursuit-of-justice` | description | CAP-I | Increasing | increasing | `data/review/paladin/retribution/pursuit-of-justice.png` |
| 49 | `paladin/retribution/seal-of-command` | description | CAP-I | Incapacitated | incapacitated | `data/review/paladin/retribution/seal-of-command.png` |
| 50 | `priest/discipline/mental-agility` | description | CAP-I | Instant | instant | `data/review/priest/discipline/mental-agility.png` |
| 51 | `priest/discipline/penance` | description | CAP-I | Instantly | instantly | `data/review/priest/discipline/penance.png` |
| 52 | `priest/discipline/renewed-hope` | description | CAP-I | Increased | increased | `data/review/priest/discipline/renewed-hope.png` |
| 53 | `priest/shadow-magic/improved-mind-flay` | description | CAP-I | Increased | increased | `data/review/priest/shadow-magic/improved-mind-flay.png` |
| 54 | `rogue/assassination/remorseless-attacks` | description | CAP-I | Increased | increased | `data/review/rogue/assassination/remorseless-attacks.png` |
| 55 | `shaman/elemental-combat/earthbound` | description | CAP-I | Immobilizes | immobilizes | `data/review/shaman/elemental-combat/earthbound.png` |
| 56 | `shaman/elemental-combat/elemental-devastation` | description | CAP-I | Increase | increase | `data/review/shaman/elemental-combat/elemental-devastation.png` |
| 57 | `shaman/elemental-combat/lava-burst` | description | CAP-I | Increased | increased | `data/review/shaman/elemental-combat/lava-burst.png` |
| 58 | `shaman/enhancement/spirit-weapons` | description | CAP-I | Increases | increases | `data/review/shaman/enhancement/spirit-weapons.png` |
| 59 | `shaman/restoration/natures-swiftness` | description | CAP-I | Instant | instant | `data/review/shaman/restoration/natures-swiftness.png` |
| 60 | `warlock/affliction/fel-concentration` | description | CAP-I | Interruption | interruption | `data/review/warlock/affliction/fel-concentration.png` |
| 61 | `warlock/destruction/intensity` | description | CAP-I | Interruption | interruption | `data/review/warlock/destruction/intensity.png` |
| 62 | `warrior/fury/death-wish` | description | CAP-I | Immune | immune | `data/review/warrior/fury/death-wish.png` |
| 63 | `warrior/fury/enrage` | description | CAP-I | Increased | increased | `data/review/warrior/fury/enrage.png` |
| 64 | `warrior/protection/shield-slam` | description | CAP-I | Increased | increased | `data/review/warrior/protection/shield-slam.png` |

### 7.1 Prepared override blocks (53 records)

Paste per class into `data/overrides/<class>.json`. Generated by applying the section-7 corrections to the current `data/talents/<class>.json` description; placeholder sets verified unchanged.

```json
{
 "druid": {
  "schemaVersion": 1,
  "class": "druid",
  "overrides": [
   {
    "talent": "improved-entangling-roots",
    "tree": "balance",
    "set": {
     "description": "Increases the damage done by your Entangling Roots spell by {0}%, and its victims can take up to {1}% more damage without interrupting the effect."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/druid/balance/improved-entangling-roots.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "moonkin-form",
    "tree": "balance",
    "set": {
     "description": "Transforms the Druid into Moonkin Form. While in this form, the armor contribution from items is increased by {0}% and all party members within {1} yards have their critical chance increased by {2}%, exclusive with Leader of the Pack. The Moonkin cannot cast healing spells while shapeshifted. The act of shapeshifting frees the caster of Polymorph and Movement Impairing effects."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/druid/balance/moonkin-form.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "natures-grace",
    "tree": "balance",
    "set": {
     "description": "All non-periodic spell criticals grace you with a blessing of nature, increasing your spellcasting speed and reducing your global cooldown by {0}% for {1} sec."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I+PUNCT); corrected against data/review/druid/balance/natures-grace.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "ferocity",
    "tree": "feral-combat",
    "set": {
     "description": "Reduces the cost of your Maul, Mangle, Swipe, Claw, and Rake abilities by {0} Rage or Energy."
    },
    "reason": "audit 2026-09-13: reader error (PUNCT); corrected against data/review/druid/feral-combat/ferocity.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "leader-of-the-pack",
    "tree": "feral-combat",
    "set": {
     "description": "While in Cat Form, Bear Form, or Dire Bear Form, the Leader of the Pack increases the critical strike chance of all party members within {0} yards by {1}%, exclusive with Moonkin Aura."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/druid/feral-combat/leader-of-the-pack.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "natures-swiftness",
    "tree": "restoration",
    "set": {
     "description": "When activated, your next Nature spell becomes an instant cast spell."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/druid/restoration/natures-swiftness.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "tranquil-spirit",
    "tree": "restoration",
    "set": {
     "description": "Reduces the mana cost of your Healing Touch and Tranquility spells by {0}%."
    },
    "reason": "audit 2026-09-13: reader error (WORD); corrected against data/review/druid/restoration/tranquil-spirit.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   }
  ]
 },
 "hunter": {
  "schemaVersion": 1,
  "class": "hunter",
  "overrides": [
   {
    "talent": "improved-revive-pet",
    "tree": "beast-mastery",
    "set": {
     "description": "Revive Pet's casting time is reduced by {0} sec, mana cost is reduced by {1}%, and increases the health your pet returns with by an additional {2}%."
    },
    "reason": "audit 2026-09-13: reader error (PUNCT); corrected against data/review/hunter/beast-mastery/improved-revive-pet.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "intimidation",
    "tree": "beast-mastery",
    "set": {
     "description": "Command your pet to Stun the target for {0} sec on its next successful attack, which also gains {1}% increased critical strike chance. Generates high threat."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/hunter/beast-mastery/intimidation.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "improved-stings",
    "tree": "marksmanship",
    "set": {
     "description": "Increased the damage of your Serpent Sting ability by {0}%, reduces the cooldown of your Viper Sting ability by {1} sec, and increases the duration of your Scorpid Sting ability by {2} sec."
    },
    "reason": "audit 2026-09-13: reader error (WORD); corrected against data/review/hunter/marksmanship/improved-stings.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "lone-wolf",
    "tree": "marksmanship",
    "set": {
     "description": "You deal {0}% increased damage with all attacks while you do not have an active pet."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/hunter/marksmanship/lone-wolf.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "clever-traps",
    "tree": "survival",
    "set": {
     "description": "Increases the duration of Freezing and Frost trap effects by {0}% and the damage of Immolation and Explosive trap effects by {1}%."
    },
    "reason": "audit 2026-09-13: reader error (PCT); corrected against data/review/hunter/survival/clever-traps.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   }
  ]
 },
 "mage": {
  "schemaVersion": 1,
  "class": "mage",
  "overrides": [
   {
    "talent": "presence-of-mind",
    "tree": "arcane",
    "set": {
     "description": "When activated, your next Mage spell with a casting time less than {0} sec becomes an instant cast spell."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/mage/arcane/presence-of-mind.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "incineration",
    "tree": "fire",
    "set": {
     "description": "Increases the critical strike chance of your Fire Blast, Ice Lance, Arcane Blast, and Scorch spells by {0}%."
    },
    "reason": "audit 2026-09-13: reader error (PUNCT); corrected against data/review/mage/fire/incineration.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "pyroblast",
    "tree": "fire",
    "set": {
     "description": "Hurls an immense fiery boulder that causes {0} to {1} Fire damage and an additional {2} Fire damage over {3} sec."
    },
    "reason": "audit 2026-09-13: reader error (WORD); corrected against data/review/mage/fire/pyroblast.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "ice-block",
    "tree": "frost",
    "set": {
     "description": "You become encased in a block of ice, protecting you from all physical attacks and spells for {0} sec, but during that time you cannot attack, move, or cast spells."
    },
    "reason": "audit 2026-09-13: reader error (PUNCT); corrected against data/review/mage/frost/ice-block.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "shatter",
    "tree": "frost",
    "set": {
     "description": "Increases the critical strike chance of all your spells against Frozen targets by {0}%."
    },
    "reason": "audit 2026-09-13: reader error (PCT); corrected against data/review/mage/frost/shatter.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   }
  ]
 },
 "paladin": {
  "schemaVersion": 1,
  "class": "paladin",
  "overrides": [
   {
    "talent": "consecrated-ground",
    "tree": "holy",
    "set": {
     "description": "Gives your Holy spells {0}% increased damage against the first {1} enemies that enter your Consecration."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/paladin/holy/consecrated-ground.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "divine-precision",
    "tree": "holy",
    "set": {
     "description": "Increases your chance to hit with Holy spells by {0}%."
    },
    "reason": "audit 2026-09-13: reader error (PCT); corrected against data/review/paladin/holy/divine-precision.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "guardians-favor",
    "tree": "protection",
    "set": {
     "description": "Reduces the cooldown of your Blessing of Protection by {0} min and increases the duration of your Blessing of Freedom by {1} sec."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/paladin/protection/guardians-favor.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "sacred-duty",
    "tree": "protection",
    "set": {
     "description": "Increases your total Stamina by {0}% and reduces the cooldown of your Divine Shield, Divine Protection, and Templar's Bulwark spells by {1} sec."
    },
    "reason": "audit 2026-09-13: reader error (PUNCT); corrected against data/review/paladin/protection/sacred-duty.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "pursuit-of-justice",
    "tree": "retribution",
    "set": {
     "description": "Increases movement speed and mounted movement speed by {0}%. This does not stack with other movement speed increasing effects."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/paladin/retribution/pursuit-of-justice.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "seal-of-command",
    "tree": "retribution",
    "set": {
     "description": "Gives the Paladin a chance to deal additional Holy damage equal to {0}% of normal weapon damage. Only one Seal can be active on the Paladin at any one time. Lasts {1} sec. Unleashing this Seal's energy will judge an enemy, instantly causing {2} to {3} Holy damage, {4} to {5} if the target is stunned or incapacitated."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/paladin/retribution/seal-of-command.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   }
  ]
 },
 "priest": {
  "schemaVersion": 1,
  "class": "priest",
  "overrides": [
   {
    "talent": "mental-agility",
    "tree": "discipline",
    "set": {
     "description": "Reduces the mana cost of your Smite, Holy Fire, and instant cast spells by {0}%."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/priest/discipline/mental-agility.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "penance",
    "tree": "discipline",
    "set": {
     "description": "Launches a volley of holy light at the target, causing {0} Holy damage to an enemy, or {1} healing to an ally, instantly and every {2} sec for {3} sec."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/priest/discipline/penance.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "renewed-hope",
    "tree": "discipline",
    "set": {
     "description": "Your heals from Flash Heal, Binding Heal, Lesser Heal, Heal, Greater Heal, and Penance gain {0}% increased critical strike chance when cast on targets with Weakened Soul, and reduce the remaining duration of Weakened Soul on their target by {1} sec."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/priest/discipline/renewed-hope.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "divine-fury",
    "tree": "holy",
    "set": {
     "description": "Reduces the casting time of your Smite, Holy Fire, Heal, and Greater Heal spells by {0} sec."
    },
    "reason": "audit 2026-09-13: reader error (CAP-PROPER); corrected against data/review/priest/holy/divine-fury.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "devouring-contagion",
    "tree": "shadow-magic",
    "set": {
     "description": "Reduces the mana cost of your Devouring Plague by {0}%. Targets that die while Devouring Plague is active spreads it, jumping to a nearby enemy within {1} yards for the remaining duration."
    },
    "reason": "audit 2026-09-13: reader error (WORD); corrected against data/review/priest/shadow-magic/devouring-contagion.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "improved-mind-flay",
    "tree": "shadow-magic",
    "set": {
     "description": "Your Mind Flay now deals {0}% more damage, gains {1} yards increased range, but slows the target's movement speed by {2}%."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/priest/shadow-magic/improved-mind-flay.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   }
  ]
 },
 "rogue": {
  "schemaVersion": 1,
  "class": "rogue",
  "overrides": [
   {
    "talent": "remorseless-attacks",
    "tree": "assassination",
    "set": {
     "description": "After killing a non-trivial enemy, gives you a {0}% increased critical strike chance on your next Sinister Strike, Backstab, Ambush, Mutilate, or Ghostly Strike. Lasts 20 sec."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/rogue/assassination/remorseless-attacks.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "initiative",
    "tree": "subtlety",
    "set": {
     "description": "Gives you a {0}% chance to add an additional combo point to your target when using your Ambush, Garrote, or Cheap Shot ability."
    },
    "reason": "audit 2026-09-13: reader error (PUNCT); corrected against data/review/rogue/subtlety/initiative.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   }
  ]
 },
 "shaman": {
  "schemaVersion": 1,
  "class": "shaman",
  "overrides": [
   {
    "talent": "concussion",
    "tree": "elemental-combat",
    "set": {
     "description": "Increases the damage done by your Lightning Bolt, Chain Lightning, and Earth Shock spells by {0}%."
    },
    "reason": "audit 2026-09-13: reader error (PUNCT); corrected against data/review/shaman/elemental-combat/concussion.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "earthbound",
    "tree": "elemental-combat",
    "set": {
     "description": "Your Earthbind Totem immobilizes nearby targets for {0} sec when cast."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/shaman/elemental-combat/earthbound.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "elemental-devastation",
    "tree": "elemental-combat",
    "set": {
     "description": "Your offensive spell critical strikes will increase your chance to get a critical strike with melee attacks by {0}% for 10 sec."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/shaman/elemental-combat/elemental-devastation.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "lava-burst",
    "tree": "elemental-combat",
    "set": {
     "description": "You hurl molten lava at the target, dealing {0} to {1} Fire damage. If your Flame Shock is on the target, Lava Burst deals {2}% increased damage."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/shaman/elemental-combat/lava-burst.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "spirit-weapons",
    "tree": "enhancement",
    "set": {
     "description": "Gives a chance to parry enemy melee attacks, reduces all threat generated by your attacks by {0}% while Rockbiter Weapon is not active, and increases all threat generated by {1}% while Rockbiter Weapon is active."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/shaman/enhancement/spirit-weapons.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "healing-way",
    "tree": "restoration",
    "set": {
     "description": "Increases the amount healed by your Healing Wave spell by {0}%."
    },
    "reason": "audit 2026-09-13: reader error (PCT); corrected against data/review/shaman/restoration/healing-way.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "natures-swiftness",
    "tree": "restoration",
    "set": {
     "description": "When activated, your next Nature spell with a casting time less than {0} sec becomes an instant cast spell."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I+PUNCT); corrected against data/review/shaman/restoration/natures-swiftness.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   }
  ]
 },
 "warlock": {
  "schemaVersion": 1,
  "class": "warlock",
  "overrides": [
   {
    "talent": "drain-hope",
    "tree": "affliction",
    "set": {
     "description": "Drains all hope from the target, dealing {0} Shadow damage every {1} sec and increasing all other Shadow damage over time you deal to that target by {2}%. Lasts {3} sec."
    },
    "reason": "audit 2026-09-13: reader error (PUNCT); corrected against data/review/warlock/affliction/drain-hope.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "fel-concentration",
    "tree": "affliction",
    "set": {
     "description": "Gives you a {0}% chance to avoid interruption caused by damage while channeling or casting your Drain Life, Drain Mana, or Drain Soul spells."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/warlock/affliction/fel-concentration.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "improved-life-tap",
    "tree": "affliction",
    "set": {
     "description": "Increases the amount of Mana awarded by your Life Tap spell by {0}%."
    },
    "reason": "audit 2026-09-13: reader error (PCT); corrected against data/review/warlock/affliction/improved-life-tap.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "soul-siphon",
    "tree": "affliction",
    "set": {
     "description": "Increases the rate at which your Drain Life and Drain Soul deal damage by {0}%, but reduces your healing from Drain Life by {1}%."
    },
    "reason": "audit 2026-09-13: reader error (PCT); corrected against data/review/warlock/affliction/soul-siphon.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "suppression",
    "tree": "affliction",
    "set": {
     "description": "Increases your chance to hit with all spells and attacks by {0}% and reduces all threat you generate by {1}%."
    },
    "reason": "audit 2026-09-13: reader error (PCT); corrected against data/review/warlock/affliction/suppression.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "fel-vitality",
    "tree": "demonology",
    "set": {
     "description": "Increases the maximum health and Mana of your Imp, Voidwalker, Succubus, Incubus, and Felhunter by {0}%, and increases your maximum Mana by {1}%."
    },
    "reason": "audit 2026-09-13: reader error (PUNCT); corrected against data/review/warlock/demonology/fel-vitality.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "improved-voidwalker",
    "tree": "demonology",
    "set": {
     "description": "Increases the effectiveness of your Voidwalker's Torment, Consume Shadows, Sacrifice, and Suffering spells by {0}%."
    },
    "reason": "audit 2026-09-13: reader error (PUNCT); corrected against data/review/warlock/demonology/improved-voidwalker.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "master-summoner",
    "tree": "demonology",
    "set": {
     "description": "Reduces the casting time of your Imp, Voidwalker, Succubus, Incubus, and Felhunter Summoning spells by {0} sec and the Mana cost by {1}%."
    },
    "reason": "audit 2026-09-13: reader error (PUNCT); corrected against data/review/warlock/demonology/master-summoner.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "aftermath",
    "tree": "destruction",
    "set": {
     "description": "Increases the initial damage of your Immolate spell by {0}% and your Conflagrate spell has a {1}% chance to Daze the target, reducing the target's movement speed by {2}% for {3} sec."
    },
    "reason": "audit 2026-09-13: reader error (WORD); corrected against data/review/warlock/destruction/aftermath.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "incinerate",
    "tree": "destruction",
    "set": {
     "description": "Deals {0} to {1} Fire damage to your target and an additional {2}% damage if the target is afflicted by Immolate."
    },
    "reason": "audit 2026-09-13: reader error (WORD); corrected against data/review/warlock/destruction/incinerate.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "intensity",
    "tree": "destruction",
    "set": {
     "description": "Gives you a {0}% chance to resist interruption caused by damage while casting or channeling any Destruction spell."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/warlock/destruction/intensity.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "shadow-and-flame",
    "tree": "destruction",
    "set": {
     "description": "Hitting an enemy with Conflagrate increases all Shadow damage you deal by {0}% for {1} sec. and hitting an enemy with Shadowburn increases all Fire damage you deal by {2}% for {3} sec. In addition, Conflagrate has a {4}% chance not to consume Immolate, and Shadowburn has a {5}% chance to instantly refund a Soul Shard."
    },
    "reason": "audit 2026-09-13: reader error (PUNCT+WORD); corrected against data/review/warlock/destruction/shadow-and-flame.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   }
  ]
 },
 "warrior": {
  "schemaVersion": 1,
  "class": "warrior",
  "overrides": [
   {
    "talent": "death-wish",
    "tree": "fury",
    "set": {
     "description": "When activated, increases your Physical damage done by {0}% and makes you immune to Fear effects, but increases all damage you take by {1}%. Lasts {2} sec."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/warrior/fury/death-wish.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "enrage",
    "tree": "fury",
    "set": {
     "description": "Gives you a {0}% chance to deal 2% increased Physical damage for 12 sec after being the victim of any damaging attack."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/warrior/fury/enrage.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   },
   {
    "talent": "shield-slam",
    "tree": "protection",
    "set": {
     "description": "Slam the target with your shield, causing {0} to {1} damage, increased by your Block Value, and has a {2}% chance of dispelling {3} magic effect on the target. Causes a very high amount of threat."
    },
    "reason": "audit 2026-09-13: reader error (CAP-I); corrected against data/review/warrior/protection/shield-slam.png",
    "by": "data-audit",
    "at": "2026-09-13T00:00:00Z"
   }
  ]
 }
}
```

## 8. Recommended fixes

### 8.1 Fix in the pipeline and re-export (systematic)

These are reader-level defects. Correcting 55 records by hand leaves the next
`05_read.py` run to reintroduce them, so the fix belongs upstream.

1. **Resolve reader disagreements in favour of the non-Qwen reader for
   capitalisation, punctuation and `%`, and in favour of Qwen for content.**
   This audit is the evidence: across the 72 stored codex-cli disagreements the
   split is 33 case + 16 punctuation + 7 missing-`%` + 18 word-level, and the
   adjudication came out ~100 % for codex on the first three shapes and ~70 %
   for Qwen on the fourth. A shape-aware merge in
   `pipeline/src/wowtalents/` (classify each diff hunk as case / `.`-vs-`,` /
   `%`-insertion / other, then apply the per-shape winner) fixes 48 of the 64
   issues mechanically and keeps the confidence flag for the rest.
2. **Post-reading normaliser** (belt and braces, and it also catches records
   where *both* readers agree on a wrong capital): lowercase a mid-sentence
   `I[a-z]+` unless it is in an allow-list of game terms
   (`Intellect Imp Incubus Immolate Immolation Incinerate Intercept Insect Ice
   Inner Invisibility Interrupt`), preceded by `. `, `: `, `- ` or a line start.
   Today the allow-list would fire on 40 occurrences and the lowercasing on 27,
   with no false positives in a full-file scan.
3. **Percent-sign guard**: warn (`R17`-style) when a numeric slot in a sentence
   containing `chance|critical|damage|healed|threat|duration|amount|increases|
   reduces` is followed directly by `.` or `,` with no unit **and** the matched
   Classic slot is a percentage. All 7 cases would have been caught; none of the
   32 legitimate unitless slots has a percentage Classic counterpart.
4. **Enumeration-punctuation guard**: warn when a description contains
   `<Word>. <Word>...` followed later in the same clause by `, and ` / `, or `.
   All 11 real cases are caught; the 4 false positives (`druid/wild-growth`,
   `hunter/counterattack`, `shaman/water-shield`, `warlock/bane-of-havoc`) are
   real sentence boundaries and are cheap to dismiss in the review UI.
5. **Refuse to derive `ranks[0]` from a non-rank-0 tooltip.** `shatter` and
   `5-rage` already carry the "points already spent" `source.note`; that note
   should force `ranksSource: "manual"` and `ranks` beyond copy-of-rank-1 should
   not be computed from the observed value at all. As it stands a rank-3 value
   was scaled as if it were rank 1 and produced 150 % crit.
6. **Crop with more headroom / a width floor.** The `5-rage` name line and the
   right half of `piercing-ice` are outside their crops. A sanity check in the
   crop stage (tooltip border visible on all four sides, else widen and retry)
   would have caught both.
7. **Stage 7 arrowhead gate.** The two known detector errors both reproduce:
   `Shadowburn -> Conflagrate` (head energy 10.2, just over the 9.5 gate, on an
   art stripe) and the missed `Improved Bloodrage -> Last Stand` (strong head,
   coverage 0.08 because the stroke lies on a hard art edge). Weighting the
   arrowhead higher relative to ridge coverage would fix both at once; until
   then they are the two per-record fixes below.

### 8.2 Per-record overrides (prepared)

**53 ready-to-apply description overrides** are in section 7, one per record,
each carrying the crop path as its reason. They are the mechanical text fixes
(27 capitalisation, 14 punctuation, 7 percent, 8 word-level, minus the records
where one edit subsumes another). They need no human decision beyond accepting
this audit; applying them also sets `source.reviewed: true` on those 53 records
(schema section 6.2), which is desirable - they have been looked at.

**5 more need a human decision or a re-run and are deliberately not written as
`set` blocks:**

| # | record | what is needed |
|---|---|---|
| 1 | `druid/feral-combat/5-rage` | re-crop with headroom, then `rename` to `feral-charge` + full `set` (name, description with both clauses, `maxRank`); needs a migration entry if `v1` is published |
| 2 | `mage/frost/shatter` | `ranks` must be re-derived (crop is rank 3/3); the `%` half is already in the 53 |
| 3 | `shaman/enhancement/improved-ghost-wolf` | `ranks[0]` `1` -> `1.0` and `description` `1 sec` -> `1.0 sec`; trivial but touches `ranks`, so it is a separate decision |
| 4 | `warlock/destruction/conflagrate` | drop `requires`. The override format cannot delete a field (`set: {}` is a no-op); either extend it with a `unset: ["requires"]` verb or re-`set` every other field. **The format gap is worth closing** - it will recur |
| 5 | `warrior/protection/last-stand` | add `requires: [{talent: "improved-bloodrage", rank: 2}]` with the same `source.note` wording the other 67 use |

And one that is neither: `mage/frost/piercing-ice` is unverifiable from its
crop. Do not override it from the Classic wording; re-crop the cell first.

### 8.3 Not a data fix

`rules` (`pointsPerRow: 5`, `maxPoints: 51`) is `assumed` and 16 of 27 trees
cannot absorb 51 points. That is a modelling question for the next footage or
datamining pass, not an override.

## 9. What this audit did not cover

- Ranks 2+ of the 300 anticipated records (audited separately in
  `docs/handover/2026-09-13-rank-scaling.md`; its section 3 doubt list stands,
  and `shatter` is now confirmed as a bad input to that arithmetic rather than
  bad arithmetic).
- The 52 `requires` entries not sampled and the 375 icon matches not sampled.
- The 72 `iconSource: "crop"` records (nothing to compare them against yet).
- Tree headers (`_header.png`), tree names, and the `Secondary` page question.

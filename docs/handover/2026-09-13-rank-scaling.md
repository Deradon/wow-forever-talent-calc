# Handover: proportional rank scaling, 2026-09-13

Reported by the owner: anticipated ranks scaled wrongly. Priest **Meditation**
reads 17% at rank 1 in the footage; Classic Meditation is 5/10/15, and the
export produced **17/22/27** — Classic's additive step `+5` applied to a base
it does not belong to. Classic progressions are almost always proportional, so
the expected answer is **17/34/51** (possibly shown as 50 at rank 3).

Changed: `pipeline/src/wowtalents/ranks.py`, `pipeline/tests/test_ranks.py`,
all nine `data/extracted/<class>.candidates.json`, `data/extracted/<class>.json`
and `data/talents/<class>.json`, `docs/DATA-SCHEMA.md` section 5,
`pipeline/README.md` stage 6, `data/extracted/SUMMARY.md`. No encoding change
(no ids moved), nothing touched under `data/icons/` or `pipeline/stages/09_*`.

## 1. The rule

A Classic slot's per-rank values are classified as

| class | test | example | applied to Forever rank 1 `v1` |
|---|---|---|---|
| constant | all values equal | 3/3/3 | `v1` repeated |
| proportional | some `a` with `c_k = a * k` within the half unit the client rounds by | 5/10/15, 2/4/6/8/10, 16/33/50 (= 50/3 per rank), 8/16/25 (= 8.2 per rank) | `v_k = v1 * k` |
| affine | arithmetic with a non-zero offset | 10/15/20 = 5k + 5, 15/25/35 = 10k + 5 | `v_k = (v1 / c1) * (step * k + offset)`, confidence one notch lower |
| irregular | neither | 15/30/45/65 | copy only when `c1 == v1`, else `manual` |

When Forever's rank 1 equals Classic's rank 1 and the rank counts agree,
Classic's own numbers are still copied verbatim (they are Blizzard's, not ours)
— that is the unchanged `copied` rule and the only one that can be `high`
confidence. Everything else keeps `ranksSource: "classic-prior"`, stays in the
review queue, and states the rule in `ranksNote`.

The half-unit tolerance in the proportional test is what makes 16/33/50 and
8/16/25 proportional: the client displays `round(a * k)`, so a Classic sequence
that is one unit off the exact ray is still a proportional effect. It also
turned four previously unusable (`manual`) records into usable ones.

Rounding is **reported, never applied**. A scaled value that looks like
something Blizzard would round (an integer within 5% of a multiple of five, or
a fraction >= 5) adds a clause to `ranksNote`:
`Rounding: rank 2 34 may read 35, rank 3 51 may read 50 (values above are the
raw scaled numbers)`. `ranks` keeps the raw value so a reviewer can see what the
rule produced; 33 records carry such a clause.

Two smaller fixes came out of the same review:

- The plural slot no longer lands on a comparative: `"1 level higher"` now
  templates as `"{0} level{1} higher"` (rank 2: "2 levels higher"), not
  `"level higher{1}"` ("2 level highers"). 4 descriptions fixed.
- `rule` values in the stage-6 block are now `copied | constant | proportional |
  affine | none`; `ratio`, `step`, `extended` and `linear` are gone.

## 2. Audit

All 300 anticipated records (`ranksSource` `classic-prior` or `extrapolated`)
across `data/talents/*.json` were recomputed from their rank-1 text and matched
the files exactly before the change, so the table below is the complete picture.
257 Classic slots feed them: **252 proportional, 5 affine, 0 irregular** (the
irregular branch survives for `15/30/45/65`-style data and is covered by tests
only). The 70 `extrapolated` records were already `v1 * k` and are unchanged in
value; their note wording and, where applicable, the plural/unit slots changed.

| class | anticipated | copied | proportional | affine | extrapolated | new values | note-only |
|---|---|---|---|---|---|---|---|
| warrior | 36 | 16 | 11 | 2 | 7 | 10 | 10 |
| paladin | 32 | 12 | 11 | 0 | 9 | 6 | 14 |
| hunter | 30 | 12 | 11 | 0 | 7 | 6 | 12 |
| rogue | 36 | 17 | 12 | 0 | 7 | 7 | 12 |
| priest | 36 | 14 | 13 | 1 | 8 | 10 | 13 |
| shaman | 33 | 18 | 7 | 1 | 7 | 6 | 11 |
| mage | 36 | 22 | 8 | 1 | 5 | 8 | 7 |
| warlock | 29 | 8 | 9 | 0 | 12 | 5 | 16 |
| druid | 32 | 14 | 10 | 0 | 8 | 5 | 13 |
| **total** | **300** | **133** | **92** | **5** | **70** | **63** | **108** |

171 talents differ from the previous export: **63 with new rank values**, 108
with a new `ranksNote` only (and 4 of those also with the plural fix). By old
`ranksSource`: `observed` 109 unchanged, `manual` 60 unchanged and 4 promoted to
`classic-prior`, `classic-prior` 129 unchanged and 97 changed. No `observed` or
`manual` record lost data.

### 2.1 Every value change

| class | talent | ranks | Classic slot(s) | before | after |
|---|---|---|---|---|---|
| druid | `improved-moonfire` | 2 | 2/4/6/8/10 (proportional) | 5/7 | 5/10 |
| druid | `sharpened-claws` | 2 | 2/4/6 (proportional) | 3/5 | 3/6 |
| druid | `subtlety` | 3 | 4/8/12/16/20 (proportional) | 10/14/18 | 10/20/30 |
| druid | `reflection` | 3 | 5/10/15 (proportional) | 17/22/27 | 17/34/51 |
| druid | `living-spirit` | 3 | 25/50/75 (proportional) | 5/30/55 | 5/10/15 |
| hunter | `ferocity` | 5 | 3/6/9/12/15 (proportional) | 2/5/8/11/14 | 2/4/6/8/10 |
| hunter | `careful-aim` | 5 | 2/4/6/8/10 (proportional) | 20/22/24/26/28 | 20/40/60/80/100 |
| hunter | `barrage` | 3 | 5/10/15 (proportional) | 3/8/13 | 3/6/9 |
| hunter | `savage-strikes` | 2 | 10/20 (proportional) | 2/12 | 2/4 |
| hunter | `improved-wing-clip` | 3 | 4/8/12/16/20 (proportional) | 7/11/15 | 7/14/21 |
| hunter | `lightning-reflexes` | 5 | 3/6/9/12/15 (proportional) | 2/5/8/11/14 | 2/4/6/8/10 |
| mage | `arcane-subtlety` | 2 | 5/10 (proportional); 20/40 (proportional) | 8/15 &middot; 13/30 | 8/15 &middot; 16/30 |
| mage | `magic-absorption` | 2 | 2/4/6/8/10 (proportional); 1/2/3/4/5 (proportional) | 5/1 &middot; 7/2 | 5/1 &middot; 10/2 |
| mage | `arcane-meditation` | 3 | 5/10/15 (proportional) | 17/22/27 | 17/34/51 |
| mage | `impact` | 3 | 2/4/6/8/10 (proportional) | 3/5/7 | 3/6/9 |
| mage | `burning-soul` | 3 | 35/70 (proportional); 15/30 (proportional) | 23/10 &middot; 58/25 &middot; 93/40 | 23/10 &middot; 46/20 &middot; 69/30 |
| mage | `elemental-precision` | 5 | 2/4/6 (proportional) | 1/3/5/7/9 | 1/2/3/4/5 |
| mage | `shatter` | 3 | 10/20/30/40/50 (proportional) | 50/60/70 | 50/100/150 |
| mage | `improved-cone-of-cold` | 3 | 15/25/35 (affine) | 12/22/32 | 12/20/28 |
| paladin | `spiritual-focus` | 2 | 14/28/42/56/70 (proportional) | 35/49 | 35/70 |
| paladin | `divine-precision` | 3 | 1/2/3 (proportional) | 6/7/8 | 6/12/18 |
| paladin | `improved-righteous-fury` | 3 | 16/33/50 (proportional) | 2/19/36 | 2/4/6 |
| paladin | `one-handed-weapon-specialization` | 3 | 2/4/6/8/10 (proportional) | 3/5/7 | 3/6/9 |
| paladin | `benediction` | 5 | 3/6/9/12/15 (proportional) | 2/5/8/11/14 | 2/4/6/8/10 |
| paladin | `eye-for-an-eye` | 2 | 15/30 (proportional) | 5/20 | 5/10 |
| priest | `wand-specialization` | 2 | 5/10/15/20/25 (proportional) | 13/18 | 13/26 |
| priest | `holy-precision` | 3 | 1/2/3 (proportional) | 6/7/8 | 6/12/18 |
| priest | `improved-power-word-shield` | 3 | 5/10/15 (proportional) | 7/12/17 | 7/14/21 |
| priest | `mental-agility` | 3 | 2/4/6/8/10 (proportional) | 3/5/7 | 3/6/9 |
| priest | `meditation` | 3 | 5/10/15 (proportional) | 17/22/27 | 17/34/51 |
| priest | `twilight-focus` | 3 | 40/70/100 (affine) | 23/53/83 | 23/40.25/57.5 |
| priest | `spiritual-healing` | 3 | 2/4/6/8/10 (proportional) | 3/5/7 | 3/6/9 |
| priest | `shadow-affinity` | 3 | 8/16/25 (proportional) | 10/10/10 | 10/20/30 |
| priest | `shadow-reach` | 2 | 6/13/20 (proportional) | 10/17 | 10/20 |
| priest | `shadow-weaving` | 3 | 20/40/60/80/100 (proportional) | 33/53/73 | 33/66/99 |
| rogue | `improved-kidney-shot` | 2 | 3/6/9 (proportional) | 5/8 | 5/10 |
| rogue | `improved-eviscerate` | 3 | 5/10/15 (proportional) | 7/12/17 | 7/14/21 |
| rogue | `deflection` | 3 | 1/2/3/4/5 (proportional) | 2/3/4 | 2/4/6 |
| rogue | `weapon-expertise` | 2 | 3/5 (proportional) | 1/3 | 1/2 |
| rogue | `opportunity` | 2 | 4/8/12/16/20 (proportional) | 5/9 | 5/10 |
| rogue | `setup` | 3 | 15/30/45 (proportional) | 33/48/63 | 33/66/99 |
| rogue | `initiative` | 3 | 25/50/75 (proportional) | 33/58/83 | 33/66/99 |
| shaman | `eye-of-the-storm` | 3 | 33/66/100 (proportional) | 23/23/23 | 23/46/69 |
| shaman | `anticipation` | 3 | 1/2/3/4/5 (proportional) | 2/3/4 | 2/4/6 |
| shaman | `flurry` | 5 | 10/15/20/25/30 (affine) | 5/10/15/20/25 | 5/7.5/10/12.5/15 |
| shaman | `mindfulness` | 3 | 5/10/15 (proportional) | 17/22/27 | 17/34/51 |
| shaman | `healing-focus` | 3 | 14/28/42/56/70 (proportional) | 23/37/51 | 23/46/69 |
| shaman | `healing-way` | 3 | 33/66/100 (proportional) | 8/8/8 | 8/16/24 |
| warlock | `fel-concentration` | 3 | 14/28/42/56/70 (proportional) | 23/37/51 | 23/46/69 |
| warlock | `pandemic` | 3 | 2/4/6 (proportional) | 33/35/37 | 33/66/99 |
| warlock | `master-demonologist` | 5 | 4/8/12/16/20 (proportional); 2/4/6/8/10 (proportional); 2/4/6/8/10 (proportional); 0.2/0.4/0.6/0.8/1 (proportional) | 2/2/2/2 &middot; 4/4/4/2.2 &middot; 6/6/6/2.4 &middot; 8/8/8/2.6 &middot; 10/10/10/2.8 | 2/2/2/2 &middot; 4/4/4/4 &middot; 6/6/6/6 &middot; 8/8/8/8 &middot; 10/10/10/10 |
| warlock | `cataclysm` | 3 | 1/2/3/4/5 (proportional) | 3/4/5 | 3/6/9 |
| warlock | `intensity` | 3 | 35/70 (proportional) | 23/58/93 | 23/46/69 |
| warrior | `improved-rend` | 3 | 15/25/35 (affine) | 12/22/32 | 12/20/28 |
| warrior | `improved-slam` | 2 | 0.1/0.2/0.3/0.4/0.5 (proportional) | 0.25/0.35 | 0.25/0.5 |
| warrior | `improved-cleave` | 3 | 40/80/120 (proportional) | 1/41/81 | 1/2/3 |
| warrior | `enrage` | 5 | 5/10/15/20/25 (proportional) | 30/35/40/45/50 | 30/60/90/120/150 |
| warrior | `flurry` | 5 | 10/15/20/25/30 (affine) | 5/10/15/20/25 | 5/7.5/10/12.5/15 |
| warrior | `improved-bloodrage` | 2 | 2/5 (proportional) | 25/28 | 25/50 |
| warrior | `improved-thunder-clap` | 3 | 1/2/4 (proportional) | 2/2/2 | 2/4/6 |
| warrior | `improved-revenge` | 3 | 15/30/45 (proportional) | 20/35/50 | 20/40/60 |
| warrior | `defiance` | 3 | 3/6/9/12/15 (proportional) | 5/8/11 | 5/10/15 |
| warrior | `improved-disarm` | 3 | 1/2/3 (proportional) | 7/8/9 | 7/14/21 |
## 3. Doubtful cases for review

The rule is mechanical; these are the records where it produces something a
human should look at. All of them are in the review queue already.

**(a) Affine offsets that scale into halves (5 records, confidence `low`).**
The brief's rule scales step and offset by `v1 / c1`, which is only clean when
the ratio is. `shaman/flurry` and `warrior/flurry` (Classic 10/15/20/25/30,
Forever rank 1 5) now read **5/7.5/10/12.5/15**; `priest/twilight-focus`
(Classic 40/70/100, rank 1 23) reads **23/40.25/57.5**. The old additive result
(5/10/15/20/25) looked tidier but assumed Forever kept Classic's +5 step from a
halved base. If Forever's Flurry is really 5/10/15/20/25, that is a data fact we
do not have; the rounding clause flags 7.5 -> 8 and 12.5 -> 13.
`mage/improved-cone-of-cold` and `warrior/improved-rend` are the well-behaved
affine cases (12/20/28 from Classic 15/25/35).

**(b) Ratios so far from 1 that the Classic match itself is suspect.** The
scaling is only as good as the matched talent. Worst offenders, all `>= 3x` or
`<= 1/3` off Classic's rank 1:

| talent | Classic | rank 1 | now | doubt |
|---|---|---|---|---|
| `mage/shatter` | 10/20/30/40/50 | 50 | 50/100/150 | 150% crit chance is not a real number |
| `warrior/enrage` | 5/10/15/20/25 | 30 | 30/60/90/120/150 | same; 30 may be a different effect (Classic Enrage is a 25% damage buff) |
| `warlock/pandemic` | 2/4/6 | 33 | 33/66/99 | matched talent is almost certainly the wrong effect (16.5x) |
| `warrior/improved-bloodrage` | 2/5 | 25 | 25/50 | Classic is rage, Forever's 25 is probably a percentage |
| `hunter/careful-aim` | 2/4/6/8/10 | 20 | 20/40/60/80/100 | 10x; 100% of a stat at rank 5 |
| `warlock/master-demonologist` | 0.2/.../1.0 (4th slot) | 2 | 2/4/6/8/10 | 10x on one slot only; the other three slots match Classic exactly |
| `warrior/improved-cleave` | 40/80/120 | 1 | 1/2/3 | 1 is a target count, Classic is a damage percentage; result is plausible, the match is not |
| `paladin/improved-righteous-fury` | 16/33/50 | 2 | 2/4/6 | 0.125x, but 2/4/6 is far more plausible than the old 2/19/36 |
| `druid/living-spirit`, `hunter/savage-strikes`, `paladin/eye-for-an-eye`, `shaman/healing-way`, `rogue/weapon-expertise` | see 2.1 | | | 0.2x-0.33x; all now read as small proportional series |

**(c) Two-rank Classic sequences classified proportional by the half-unit
tolerance.** `2/5` (`warrior/improved-bloodrage`, and 3/5 for
`rogue/weapon-expertise`) and `1/2/4` (`warrior/improved-thunder-clap`) pass the
proportional test only because rounding leaves room; they could equally be
irregular. Thunder Clap was `manual` before and is now `classic-prior` 2/4/6.

**(d) The four records promoted from `manual` to `classic-prior`:**
`priest/shadow-affinity` 10/20/30 (Classic 8/16/25), `shaman/eye-of-the-storm`
23/46/69 (Classic 33/66/100), `shaman/healing-way` 8/16/24 (same), and
`warrior/improved-thunder-clap` 2/4/6 (Classic 1/2/4). They used to be three
copies of rank 1, which is not better data, only quieter data. Reject any of
them with an override if the tooltip suggests otherwise.

**(e) The 33/66/99 family.** `rogue/setup`, `rogue/initiative`,
`priest/shadow-weaving` and `warlock/pandemic` all read 33% at rank 1 and scale
to 33/66/99. Blizzard almost certainly means thirds, i.e. 33/67/100. The
rounding clause only proposes multiples of five here ("66 may read 65"), which
is the weakest hint the heuristic produces — do not take it literally.

**(f) `warrior/improved-slam` 0.25 -> 0.25/0.5 sec.** The only decimal duration
in the set. Classic Improved Slam is 0.1 per rank (proportional), so 0.5 sec at
rank 2 follows the rule, but a cast-time reduction doubling in one rank deserves
a look.

## 4. Validation and tests

- `cd pipeline && uv run pytest -q`: **170 passed**. `tests/test_ranks.py` now
  has 46 test functions (39 before, 54 cases with parametrisation): Meditation
  17/34/51, Toughness-style copy, proportional re-base, affine offset, decimals,
  rounding hints, the comparative plural, and rank-2 rendering of extrapolated
  unit/plural slots.
- Stage 6 re-run with `--force` on all nine classes, then
  `08_export.py all <class> --update-encoding`: `data/talents/*.json`
  **0 errors** each (`validate.py --check`), warning mix byte-identical to
  before the change (77 NEEDS-REVIEW, 44 MAXRANK-DIFFERS-FROM-CLASSIC,
  16 R18-TREE-TOO-SMALL, 5 NONLINEAR-RANKS, 1 R17-TERMINATOR).
- `cd web && npx vitest run`: 81 passed (7 files). `npm run build`: clean.

## 5. Follow-ups

1. The rounding hints are a heuristic (multiples of five, or a fraction >= 5).
   Thirds (33/67/100) and sixths are not modelled; if the review UI shows the
   hint, show it as a suggestion, not a correction.
2. `ranksNote` is now long enough to matter in the UI. Consider splitting the
   `Rounding:` clause into its own field when the schema is next bumped.
3. Section (b) of `docs/briefs/data-prior-and-review.md` still describes the old
   "clean ratio else +step" rule. It is superseded by section 1 above; the brief
   was left as the historical record of the first implementation.
4. A ratio guard (reject a Classic match whose rank-1 ratio is beyond, say,
   4x/0.25x) would catch most of the list in 3(b) automatically, at the price of
   sending records back to `manual`. Not implemented: 2/4/6 for Improved
   Righteous Fury (0.125x) is better data than three copies of 2.

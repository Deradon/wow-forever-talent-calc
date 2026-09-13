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

---

# Addendum: proportional is now the default, 2026-09-13 (second round)

Reported by the owner: priest Holy **Twilight Focus** reads 23 % at rank 1 and
was exported as **23 / 40.25 / 57.5**. The expectation is **23 / 46 / 69** —
a Forever talent scales from its own rank 1, and scaling a Classic *offset*
produces values nobody would design. Section 1 above (the affine branch) is
superseded by section 6; the rest of this document stands as the record of the
first round.

## 6. The rule, second revision

**Anticipated ranks are `v1 * k`.** Whatever shape the matched Classic talent
has, the Forever talent scales proportionally from its own rank 1.

The single exception is a **verbatim copy**, and it needs all three of:

1. the Classic match is an **exact same-name** talent (full-string key
   equality, the `exact-name` tier — not fuzzy, not description),
2. the **rank counts agree**, and
3. **Forever's rank 1 equals Classic's rank 1**.

Then Classic's own per-rank numbers are used, whatever their progression:
they are Blizzard's numbers and not our arithmetic. This is deliberately wider
than the letter of the owner's rule, which names only the non-proportional
case. For a strictly proportional Classic series copy and `v1 * k` agree
anyway; where they do not, it is because the client's own rounding puts
Classic's displayed series slightly off the ray (`8/16/25`, `13/25`,
`33/66/100`, `16/33/50`). In exactly those cases Blizzard's displayed number is
better evidence than our multiplication, so the copy wins. Seven records live
there and are listed in 6.3.

Everything else — affine (`10/15/20 = 5k + 5`), irregular (`15/30/45/65`), or
proportional on a different base — is `v1 * k`. When the Classic slot was
*not* proportional, `ranksNote` names the pattern that was **not** applied and
the record drops to **`low`** confidence and stays in the review queue:

> Classic 40/70/100 is 30 x rank +10, which does not start at Forever's rank 1
> (23); Classic's pattern was NOT applied, ranks scaled proportionally
> (23 x rank).

Consequences of the change in code (`pipeline/src/wowtalents/ranks.py`):

- `scale_slot` gained a `copy_allowed` flag; `_from_classic` passes
  `m.match == "exact-name"`. A description or fuzzy match is a wording
  resemblance, not evidence that Forever kept Classic's numbers, so it no
  longer copies — it scales, with the same values whenever Classic is
  proportional.
- The `affine` **rule** value is gone. `rule` is now
  `copied | constant | proportional | none`; the low-confidence signal moved to
  `SlotPlan.low`.
- The irregular branch no longer returns `None`, so a non-linear Classic slot
  on a different base is no longer `manual`. `scale_slot` now returns `None`
  only for a rank-1 value of 0 or below, which has no ray through it.
- The `observed_rank` guard is untouched: a tooltip captured at rank > 1 still
  goes straight to `manual` with `ranksObserved: [<rank>]` (mage Shatter stays
  50/50/50). Validator rule 20 is untouched except for the addition in 6.5.
- The shape-changing branch (Classic's sentence differs per rank, e.g. rogue
  Elusiveness `45 sec` -> `1.5 min`) still copies the per-rank strings; it
  already requires Forever's whole rank-1 text to equal Classic's, which is a
  stronger form of condition 3.

### 6.1 Audit before the change

All 300 anticipated records (`classic-prior` or `extrapolated`) were checked
for values that are not `v1 * k`. **Twelve**, all `classic-prior`:

| class | talent | values | Classic slot(s) | match | verdict |
|---|---|---|---|---|---|
| mage | `improved-cone-of-cold` | 12/20/28 | 15/25/35 affine | exact-name | **changed** to 12/24/36 |
| priest | `twilight-focus` | 23/40.25/57.5 | 40/70/100 affine | description, cross-class | **changed** to 23/46/69 |
| shaman | `flurry` | 5/7.5/10/12.5/15 | 10/15/20/25/30 affine | exact-name | **changed** to 5/10/15/20/25 |
| warrior | `improved-rend` | 12/20/28 | 15/25/35 affine | exact-name | **changed** to 12/24/36 |
| warrior | `flurry` | 5/7.5/10/12.5/15 | 10/15/20/25/30 affine | exact-name | **changed** to 5/10/15/20/25 |
| mage | `wand-specialization` | 13/25 | 13/25 | exact-name | kept (verbatim copy) |
| mage | `improved-scorch` | 33/66/100 | 33/66/100 | exact-name | kept (verbatim copy) |
| priest | `inspiration` | 8/16/25 | 8/16/25 | exact-name | kept (verbatim copy) |
| rogue | `improved-sinister-strike` | 3/5 | 3/5 | exact-name | kept (verbatim copy) |
| rogue | `elusiveness` | per-rank strings | shape changes per rank | exact-name | kept (strings copied) |
| shaman | `elemental-weapons` | 7/13/5 .. 20/40/15 | same | exact-name | kept (verbatim copy) |
| shaman | `ancestral-healing` | 8/16/25 | 8/16/25 | exact-name | kept (verbatim copy) |

**Twilight Focus specifically: the Classic match is the wrong talent.** The
crop (`data/review/priest/holy/twilight-focus.png`) reads, verbatim and with
full reader agreement, "Rank 0/3 — Passive — Gives you a 23% chance to avoid
interruption caused by damage while casting **any spell**." The matcher had no
same-name candidate and fell through to a description match, which requires the
same rank count; the only three-rank Classic talent worded like this is druid
Balance **Improved Entangling Roots** (40/70/100), a talent scoped to a single
spell and designed to reach a guaranteed 100 %. Its `+10` offset is the sole
reason 23 became 40.25. The real Classic family for "avoid interruption caused
by damage" is **14/28/42/56/70** — shaman Healing Focus, druid Nature's Focus,
warlock Fel Concentration, all five ranks, all proportional — plus priest Holy's
own two-rank **Healing Focus** 35/70. Every one of them is proportional, so the
owner's 23/46/69 is what the right match would have produced anyway. The match
is kept in `ranksPrior` for the reviewer, and the note now says plainly that
Classic's pattern was not applied.

### 6.2 Records that changed

Six records changed value; twelve changed only their `ranksNote`. Nothing with
`ranksSource: observed`, nothing `reviewed: true`, and no `manual` record lost
data (one gained data, see the last row).

| class | talent | before | after | Classic slot | why |
|---|---|---|---|---|---|
| priest | `holy/twilight-focus` | 23/40.25/57.5 | **23/46/69** | 40/70/100 (`+10` offset) | offset not re-based |
| shaman | `enhancement/flurry` | 5/7.5/10/12.5/15 | **5/10/15/20/25** | 10/15/20/25/30 (`+5`) | offset not re-based |
| warrior | `fury/flurry` | 5/7.5/10/12.5/15 | **5/10/15/20/25** | 10/15/20/25/30 (`+5`) | offset not re-based |
| mage | `frost/improved-cone-of-cold` | 12/20/28 | **12/24/36** | 15/25/35 (`+5`) | offset not re-based |
| warrior | `arms/improved-rend` | 12/20/28 | **12/24/36** | 15/25/35 (`+5`) | offset not re-based |
| mage | `frost/improved-blizzard` | 15/15/15, `manual` | **15/30/45**, `classic-prior` | 30/50/65 irregular | irregular is no longer `manual` |

`mage/frost/improved-blizzard` also lost a template slot: as a `manual` record
every number became a slot (`[[15, 1.5], ...]`), while the Classic match shows
that only the 15 % varies, so "for 1.5 sec" is now literal text.

Note-only changes (same values, `rule` `copied` -> `proportional`, note now
states the scaling instead of claiming a copy — all twelve are description
matches, which no longer qualify for the copy exception):
`druid/natures-majesty`, `druid/feral-swiftness`, `druid/predatory-instincts`,
`hunter/lethal-attacks`, `mage/arcane-geometry`, `mage/arcane-impact`,
`mage/incineration`, `paladin/improved-holy-strike`, `paladin/improved-seals`,
`shaman/natural-grace`, `warlock/malevolence`, `warlock/improved-sayaad`.

### 6.3 Remaining doubtful cases

Sections 3(b), 3(c), 3(e) and 3(f) above are unchanged — they are about
suspect *matches*, not about the scaling rule, and the worst of them
(`warlock/pandemic` 16.5x, `hunter/careful-aim` 10x, `warrior/enrage`,
`mage/shatter`) still stand. New or revised doubts:

**(g) The five ex-affine records now assert a step Forever may not have.**
`5/10/15/20/25` for both Flurries is a clean series, but Classic's Flurry
really is `10/15/20/25/30`; if Forever kept Classic's shape from a halved base
the answer would be 5/7.5/10/12.5/15 after all. Same for Improved Rend and
Improved Cone of Cold (12/24/36 against Classic's 15/25/35, whose rank 3 is
35). All five are `low` confidence and name the unapplied pattern in the note.
Only footage of rank 2 settles them.

**(h) `priest/twilight-focus` is matched to the wrong Classic talent.**
23/46/69 is right for the wrong reason (see 6.1). The prior has no same-name
candidate; a reviewer should either accept 23/46/69 or pin it by override. Do
not "fix" the match to Improved Entangling Roots.

**(i) `mage/frost/improved-blizzard` was promoted out of `manual`.**
15/30/45 is now asserted where three copies of 15 used to sit. Classic is
30/50/65, i.e. Forever's 15 is half of Classic's rank 1 and Classic's own rank
3 is 65 — proportional would put Forever's rank 3 at 45 against a Classic-shape
32.5. The record is `low` confidence and in the review queue.

**(j) The copy exception is wider than the owner's wording.** Seven records
keep Classic's numbers where `v1 * k` would have produced something else
(6.1, "kept" rows) — 13/25, 33/66/100, 8/16/25 twice, 3/5, Elemental Weapons'
three slots and Elusiveness' strings. Each is an exact same-name Classic talent
with the same rank count and the same rank 1. Reject the reading if the owner
wants `v1 * k` there too; that would make mage Improved Scorch 33/66/99 and
priest Inspiration 8/16/24.

### 6.4 Over-100 % and scaled thresholds (rule 20)

A full scan of `data/talents/*.json` for anticipated values above 100 % and for
scaled conditions, re-run after the change:

- **Over 100 %, 5 records, all flagged `R20-PERCENT-OVER-100`, unchanged by
  this round:** `druid/predatory-strikes` 50/100/150,
  `hunter/improved-aspect-of-the-monkey` 50/100/150, `paladin/illumination`
  50/100/150/200/250, `rogue/quietus` 35/70/105/140/175, `warrior/enrage`
  30/60/90/120/150. None is capped: rule 20 flags, the data keeps the raw
  arithmetic, and rank 1 is the only read value. None of the six records this
  round changed comes near 100 %.
- **Scaled thresholds:** `rogue/quietus` ("targets below {1}% health",
  35 -> 175) and `priest/early-demise` ("at or below {0}% health", 20 -> 40)
  were already flagged `R20-THRESHOLD-SCALED`.
- **One gap found and closed:** `priest/shadow-magic/devouring-contagion`
  scales a *distance* condition — "jumping to a nearby enemy within {1} yards",
  5 -> 10 — which rule 20's threshold regex missed because it only looked for
  `{n}%`. `validate.py` gained `DISTANCE_THRESHOLD_RE`
  (`within|inside|closer than|no more than` + `{n}` + `yards|yds|meters`), so
  the record is now flagged. Deliberately restricted to distance units: "within
  {0} sec" is often a real window a talent may extend, and flagging those would
  fire on four `manual` records that do not scale anyway.
- Every other "within {n} yards" / "within {n} sec" record in the data is
  `observed` or `manual` with identical per-rank copies, so nothing else scales
  a condition. "Increases the range of your Fire spells by {0} yards" (3/6) and
  friends are magnitudes, not conditions, and are correctly scaled.

### 6.5 Validation and tests

- `cd pipeline && uv run pytest -q`: **313 passed** (311 after the ranks
  changes, plus 2 new validator tests). `tests/test_ranks.py` covers: Twilight
  Focus 23/46/69, Flurry 5/10/15/20/25, Improved Rend 12/24/36, an exact-name
  non-proportional case with an equal rank 1 keeping Classic's 15/30/45/65, the
  same case with a different rank 1 falling back to `v1 * k`, and
  `copy_allowed=False` refusing the copy for a fuzzy/description match.
  `test_validate.py` covers the distance threshold and the untouched time
  window.
- Stage 6 re-run with `--force` on all nine classes, then
  `08_export.py all <class> --update-encoding`: `validate.py --check` reports
  **0 errors** on all nine files. Diff against the previous export: **6 value
  changes, 12 note-only changes, 0 other field changes** across 469 records;
  the only other difference is `generatedAt`. No id moved, so
  `data/encoding/v1.json` keeps its order and stays `frozen: false`.
- Warning mix unchanged except the one new finding: 6 NEEDS-REVIEW,
  44 MAXRANK-DIFFERS-FROM-CLASSIC, 16 R18-TREE-TOO-SMALL, 5 NONLINEAR-RANKS,
  1 R17-TERMINATOR, 27 R20-ABOVE-CLASSIC, 5 R20-PERCENT-OVER-100,
  **3** R20-THRESHOLD-SCALED (was 2).
- `cd web && npx vitest run`: 237 passed (18 files). `npm run build`: clean.

Also updated: `docs/DATA-SCHEMA.md` section 5, `pipeline/README.md` stage 6,
`data/extracted/SUMMARY.md`. Not touched: `web/`, `data/icons/`,
`data/overrides/`, `data/encoding/`.

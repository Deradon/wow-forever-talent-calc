# Cell-attribution audit, and what "moved" is allowed to mean

Date: 2026-09-13. Owner report: priest Shadow Magic **Blackout** says *"Moved
from row 1"* although it sits in row 1 in both games. Hypothesis: stage 4
attributed two neighbouring tooltips to each other's cells (Forever has
Blackout at row 0 col 1 and Spirit Tap at col 2; Classic has them the other way
round).

**Verdict: the attribution is right and the game really swapped them.** The bug
is the change line, which said "row" for a change that was only a column. The
owner's call, taken during this session: a column-only change inside the same
row is not worth reporting at all.

Paths are relative to the repo root.

## 1. What was checked, and how

115 of the 123 `moved` talents are same-tree moves: 42 column-only, 35 row-only,
38 both. Three independent lines of evidence, none of which uses the tooltip
text that stage 5 read.

**(a) The icon in the median at the recorded cell.** Stage 4 crops the cell's
icon straight out of the calibration median
(`04_hovers.py`: `icon = bg[c.y:c.y + c.h, c.x:c.x + c.w]`), so it is evidence
about the *cell*, independent of which tooltip was filed there. 106 of the 115
match the Classic icon of the talent recorded at that cell exactly; two differ
for reasons that are not positional (shaman Stormstrike, whose Forever icon is
`ability_shaman_stormstrike` where the Classic Era prior has
`spell_holy_sealofmight`; shaman Healing Way, where the prior names the
`classic_`-prefixed file of the same art). Six are `keep crop` — the crop is too
dark for any reference to explain, the documented failure mode from
`2026-09-13-icons.md`, and their best candidates are gems, dust and coins rather
than a neighbour's icon. One (druid Feral Charge) is missing from
`data/icons/matches.json`, which predates the current ids.

**(b) A swap test over every tree.** For all 324 cells that have both an icon
crop and a Classic talent of the same name, the cell's icon was scored against
the Classic icon of *every* talent of that Forever tree. 318 rank their own
first. The six that do not are listed below; none of them is adjacent to the
talent that outscores it, so none is a swap.

**(c) The geometry, and the frames themselves.** Across all 28 segments, every
one of the 646 accepted hovers was resolved by the corner rule (`method` is
`corner` for 646 of 646, mean distance 4.77 px, 99th percentile 6.7 px, one
35.2 px outlier in the points-spent segment 09). Neighbouring cells' top-right
corners are 52-56 px apart in both axes, `nearest_cell` gives up at 40 px and
stage 4's `CORNER_STRICT` asks the cursor above 8 px. A one-cell error is not
reachable from a 6.7 px residual. Six frames were decoded from
`work/video/xaryu-blizzcon-day1.mkv` at the recorded timestamps with the grid
drawn on them; in every one the tooltip's bottom-left corner sits on the
recorded cell's top-right corner and the cursor is on that cell.

The `cursor_cell` disagreements (137 cells) are the stale-icon artefact already
described in `2026-09-13-missing-cells-forensics.md`: in segment 08 for example
`[2, 4, 3]` is reported on nearly every hover, which is the Hot Streak ghost,
not a pointer.

## 2. Per-talent verdicts

Every pair that looked like an adjacent swap — A now sits where B was and B
where A was — with the icon score of the cell against its own Classic icon and
against the best alternative in the same tree:

| class | tree | pair | own | best other | verdict |
|---|---|---|---|---:|---:|---|
| priest | Shadow Magic | Blackout r0c1 (was c2) | 0.810 | 0.427 Shadow Affinity | real move |
| priest | Shadow Magic | Spirit Tap r0c2 (was c1) | 0.821 | 0.478 Improved Fade | real move |
| priest | Shadow Magic | Improved Mind Blast r2c0 (was c1) | 0.923 | 0.217 | real move |
| priest | Shadow Magic | Improved Psychic Scream r2c1 (was c0) | 0.970 | 0.381 | real move |
| mage | Arcane | Arcane Subtlety r1c0 (was r0c0) | 0.955 | 0.557 | real move |
| mage | Arcane | Wand Specialization r0c0 (was r1c0) | 0.875 | 0.537 | real move |
| mage | Frost | Frostbite r1c3 (was c1) | 0.851 | 0.533 | real move |
| mage | Frost | Permafrost r1c1 (was c3) | 0.985 | 0.779 | real move |
| warlock | Destruction | Bane r0c2 (was r1c1) | 0.525 | 0.020 | real move |
| warlock | Destruction | Cataclysm r1c1 (was r0c2) | 0.967 | 0.429 | real move |

Blackout and Spirit Tap head to head: the icon at r0c1 scores 0.810 against
Blackout's Classic icon and **0.053** against Spirit Tap's; the icon at r0c2
scores 0.821 against Spirit Tap's and **0.132** against Blackout's. The two
frames (19630.0 s and 19633.1 s stream time) show the Blackout tooltip anchored
on r1c2 and the Spirit Tap tooltip on r1c3, cursor on the same cell each time.
Improved Mind Blast / Improved Psychic Scream, Bane / Cataclysm, Wand
Specialization / Arcane Subtlety and Frostbite / Permafrost were confirmed the
same way (four more frames decoded).

The six cells whose own Classic icon does not win, all non-adjacent and all
explained without moving anything:

| cell | own | best other | why |
|---|---:|---:|---|
| mage Fire r3c0 Improved Scorch | -0.095 | 0.421 Combustion (r6c1) | crop recovered from a merged blob, uncorrelated |
| shaman Enhancement r3c2 Stormstrike | 0.037 | 0.466 Ancestral Knowledge (r0c2) | Forever uses a different icon for it |
| shaman Elemental Combat r0c2 Concussion | 0.184 | 0.356 Elemental Focus (r2c1) | icon changed; already noted in the icons handover |
| mage Frost r3c3 Shatter | 0.552 | 0.681 Ice Block (r3c1) | known degraded crop, `keep crop` |
| shaman Restoration r4c1 Healing Way | 0.385 | 0.495 Restorative Totems (r3c1) | prior names the `classic_`-prefixed file |
| shaman Restoration r0c1 Improved Healing Wave | 0.835 | 0.864 Healing Focus (r2c1) | the two healing-wave icons are near-identical |

## 3. Root cause

There is no attribution bug. `cell_for_tooltip` and the anchor-corner rule are
unchanged; `tests/test_ui.py` gained
`test_corner_rule_cannot_reach_a_neighbouring_cell`, which pins the geometric
argument (neighbour spacing > `max_dist`, and a correct match stays inside
`CORNER_STRICT`) so this question does not have to be re-opened from scratch.

The reported defect was in the **wording**. `changeLine` said
`Moved from row ${prior.row + 1}.` for any move, and the generator called a
talent moved when tree, row **or column** differed. Blackout changed column
only, so a player looking straight at row 1 was told it had moved from row 1.

## 4. The rule now

A move is a change of **tree or row**. Columns are ordering; rows gate points
(five per tier), and Forever reshuffled the order in most trees.

- `gen-data-index.mjs`: `moved` iff the mapped tree or the row differs.
  `prior.movedRow` and `prior.movedCol` record which; a column-only move keeps
  its real status (`same`, `text-changed`, ...) and is still written to the file
  so the review route can show the Classic cell. `entry.row` carries the Forever
  row for a row move.
- `tooltipText.ts` `movedLine`: `Moved from row 3 to row 5.`,
  `Moved from Arms.` when the tree changed but the row did not,
  `Moved from Arms, row 3 to row 5.` when both did, and the old vague
  `Moved from row 3.` only when no current row is available. Nothing is said for
  a column-only change.

### Counts, before and after

| | new | moved | rank-changed | text-changed | values-changed | same | gone |
|---|---:|---:|---:|---:|---:|---:|---:|
| before | 145 | 123 | 18 | 111 | 16 | 56 | 108 |
| after | 145 | **81** | **26** | **127** | **22** | **68** | 108 |

The 42 column-only moves land as 16 `text-changed`, 8 `rank-changed`, 6
`values-changed` and 12 `same`. Per class, `moved` goes druid 20→12, hunter
11→7, mage 14→7, paladin 12→11, priest 14→5, rogue 13→9, shaman 19→13,
warlock 15→13, warrior 5→4. The eight cross-tree moves are untouched.

`changeLine` reads the new row from `change.row` when the caller does not pass
one, so `Tooltip.tsx` needed no change. Whoever owns it may pass
`row: talent.row` at `Tooltip.tsx:140` and add `row?: number` to `Change` in
`classicDiff.ts`; the behaviour is identical either way.

## 5. Same-row prerequisites

Forever draws horizontal prerequisite arrows, which the schema previously
forbade. Rule 8 is now `target.row <= talent.row` in the same tree and a
different cell (`validate.py`, `docs/DATA-SCHEMA.md` sections 4.4 and 8;
`data/schema/class.schema.json` never encoded the row constraint, so it needed
no change). Same-row targets make a two-talent cycle expressible for the first
time, so the existing cycle walk is now load-bearing and has a test.

`export.merge_arrow_requires` no longer files a same-row arrow as a note; only
an arrow pointing up from a *later* row does.

Stage 7 had to be taught to see them. Two changes in `arrows.py`:

- `HEAD_MIN_ROW = 7.5` instead of `HEAD_MIN = 9.5` for the `row` shape. A
  horizontal head is a small round stub, not the tall triangle a vertical arrow
  gets: the two real ones measure 8.3 and 15.9.
- `stroke_cover`, a new gate on the `row` shape: the gap must hold a *dark*
  stroke connecting the two cells. `ridge_masks` accepts bright ridges too
  (a satisfied arrow would be gold, and none is, since every hover is at rank
  0), which is how a bright diagonal highlight in paladin Retribution scored
  9.1 at the head and nearly became an arrow. Over the twelve same-row
  candidates that clear `LEG_MIN_COVER` in the nine classes: 1.00 and 0.78 for
  the two real arrows, 0.06 or less for every piece of art above the head floor.

Result: **two horizontal prerequisites**, both of them the ones the
prerequisites handover predicted.

| class | dependent | requires | confidence |
|---|---|---|---:|
| paladin | Holy / Divine Precision (r4c0) | Holy Shock (r4c1) rank 1 | 1.00 |
| priest | Shadow Magic / Improved Mind Flay (r2c3) | Mind Flay (r2c2) rank 1 | 0.50 |

The priest one is flagged `ambiguous`: on an 18 px gap the head and tail windows
both sit on the arrowhead, so the direction cannot be read from edge energy. The
direction it picked is the right one (checked against the frame), and the
confidence is honest. The 67 vertical arrows are byte-identical to before.

All nine classes were re-exported (`08_export.py all <class> --update-encoding`).
The only data changes are those two `requires` blocks and their `source.note`;
no talent id, cell or encoding position moved, so there are no encoding
implications. `validate.py --check` over all nine: 0 errors.

## 6. Commands run

```sh
cd pipeline
uv run stages/07_arrows.py detect all && uv run stages/07_arrows.py merge all
for c in druid hunter mage paladin priest rogue shaman warlock warrior; do
  uv run stages/08_export.py all $c --update-encoding
done
uv run python validate.py --check ../data/talents/*.json   # 0 errors
uv run pytest -q                                            # 319 passed
cd ../web && node scripts/gen-data-index.mjs
npx vitest run                                              # 329 passed
npm run build
npx playwright test                                         # 53 passed
```

## 7. Next

- `data/icons/matches.json` predates the current talent ids (druid Feral Charge
  has no record). Re-run `09_icons.py match all` before anyone reads it as
  evidence again.
- The six `keep crop` talents in section 2 are the same review queue the icons
  handover already lists; nothing here changes their status.
- `stroke_cover` is calibrated on twelve samples from one stream. If a second
  capture ever arrives, re-measure `STROKE_MIN` before trusting it on new
  footage.
- Only two same-row arrows exist in the nine classes. If the owner knows of a
  third, it is a detector miss, not a rule problem — start at
  `work/arrows/<class>.json` and the `row` candidates in section 5.

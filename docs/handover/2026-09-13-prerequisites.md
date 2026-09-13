# Handover: talent prerequisites from tree arrows (2026-09-13)

Before this session no class file had a single `requires` entry: the only
source was "Requires ..." tooltip lines, and rank-0 tooltips never name a
talent prerequisite (0 of the 1155 cached Qwen readings; the 10 lines that
exist are `Requires Bear Form, Dire Bear Form` x4 (+ Cat Form x2), `Requires
Shields` x2, `Requires Battle Stance`, `Requires Defensive Stance`, `Requires
Level 40`, all kept as `source.note: unparsed requirement`). Classic Era has
65 prerequisites (`data/prior/classic-era/talents.json`), every one at the
target's max rank. The arrows between cells on the un-hovered tree are the
only footage signal, and this session reads them.

## What was done

- `pipeline/src/wowtalents/arrows.py` (new): ridge masks for thin dark or
  bright lines, path templates between cell pairs (`straight`, `row`,
  `L-top`, `L-bottom`; only paths crossing no cell), per-leg ridge coverage,
  Laplacian edge energy at the head end as the arrowhead test, a vote over
  the class's calibration medians, L-vs-straight overlap pruning, overlay
  drawing. Constants and the measurements behind them are in the module and
  in `pipeline/README.md` ("Stage 7").
- `pipeline/stages/07_arrows.py` (new): `detect` -> `work/arrows/<class>.json`
  + `<class>-overlay.png`; `merge` -> `requires_arrows` on the dependent
  candidate record (target cell, name, `rank` = target max rank, shape,
  confidence, medians) and an `arrows` stats block on the candidates file.
  `all all` does every class. `scripts/run_class.sh` runs it between 06 and 08.
- `pipeline/src/wowtalents/export.py`: `merge_arrow_requires` turns
  `requires_arrows` into `requires` after the tooltip lines. Rules: a
  tooltip-derived requirement is never overwritten (`ARROW-CONFLICT` logged
  and noted when the tooltip names another talent or rank; the tooltip
  stays); a same-row arrow or an arrow from a cell without a record stays a
  `source.note` (schema rule 8 needs an earlier row); every arrow-derived
  entry gets the note `prerequisite from tree arrow (stage 7): <name> at
  rank N = its max rank (Classic rule; rank-0 tooltips do not list talent
  prerequisites)` plus `arrow confidence 0.70` when the detector was unsure.
  No schema change: `requires` stays `[{talent, rank}]`, the provenance is
  the note (DATA-SCHEMA.md allows no extra fields).
- Tests: `tests/test_arrows.py` (synthetic tree: straight, long straight,
  leftward same-row arrow, an art line without arrowhead, a ghost median,
  the vote) and `test_arrow_requires_merge_and_conflicts` in
  `tests/test_export.py`. `uv run pytest`: 160 passed.
- Re-exported all nine classes (`08_export.py all <class>
  --update-encoding`), validator 0 errors each (rule 8 included).
- Web: `npx vitest run` 81 passed, `npm run build` ok, `npx playwright
  test` 8 passed after fixing a stale expectation in `tests/paladin.spec.ts`
  (45 -> 52 paladin talents; the count changed with the cursor-track
  recovery, unrelated to arrows). `web/src/ui/Arrows.tsx` reads `requires`
  and draws one polyline per entry; the warrior page shows the 7 arrows
  (screenshot checked: Arms 3, Fury 2, Protection 2, grey until the
  prerequisite is at rank N).
- `data/extracted/SUMMARY.md`: prerequisite column and section.

## Results

68 arrows detected over 27 trees, 67 written as `requires` (the 68th, paladin
Holy Shock -> Divine Precision, runs along row 5 and is a note on Divine
Precision). Per class: warrior 7, paladin 6 (+1 note), hunter 8, rogue 8,
priest 7, shaman 7, mage 6, warlock 9, druid 9. 46 at confidence >= 0.8, 21
capped at 0.7 (weak arrowhead: energy below 11 or under 1.3 x the stroke).
Every arrow in the footage is straight down a column except that one row
arrow; no L-shape survived (the two L candidates were the vertical leg of a
straight arrow plus art). All 67 targets have a smaller row, no cycles.

Cross-checks:

- Codex (`codex exec -i <tree crop>`, "list arrows as tail -> head"): of
  our 68, codex lists 67 with the same direction; it does not list
  Shadowburn -> Conflagrate. Codex names 11 more arrows; 9 of them have zero
  ridge coverage on the medians (hallucinated or shifted by one row: it puts
  Amplify Curse -> Curse of Exhaustion one row up), 2 are real misses (below).
- Classic Era prior by name: 22 of the 67 are Classic prerequisites
  (warrior 6, rogue 5, warlock 3, hunter 3, priest 2, druid 2, mage 1,
  paladin 1, shaman 0). The other 43 of the 65 Classic prerequisites involve
  talents that moved, were renamed or no longer exist; every Forever tree now
  has a capstone arrow r5c2 -> r7c2 (1-based), which Classic had in 15 trees.
- Tooltip lines: no talent-prerequisite tooltip line exists, so there were
  no conflicts to log (`ARROW-CONFLICT` count 0 in every class).
- Eyeballed at 2.5-6x: all paladin trees, warrior Arms/Fury/Protection,
  druid Restoration/Feral, rogue Subtlety, warlock Destruction, plus zooms
  on every disputed pair.

Known errors (leave for the review queue; do not hand-edit `data/`):

- False positive: warlock Destruction Shadowburn -> Conflagrate (r2c2 ->
  r3c2, 0-based). A vertical stripe of the tree art runs through both cells;
  head energy 10.2 is just above the 9.5 gate, confidence capped at 0.7.
  Codex does not see it. An override (`data/overrides/warlock.json`,
  `set: {}` cannot drop a field; use `set` with the talent's other fields
  and no `requires`, or extend the override format) removes it once a human
  confirms.
- Miss: warrior Protection Improved Bloodrage -> Last Stand (r1c0 -> r2c0):
  a real arrow (also in Classic, and codex sees it) whose stroke lies on a
  hard art edge (castle shadow), so neither the dark nor the bright ridge
  test fires (coverage 0.08) although the arrowhead is strong (energy 12-13).
- Miss: priest Shadow Magic Mind Flay -> Improved Mind Flay (r2c2 -> r2c3,
  same row, points right): coverage 0.92 but head energy 8.3 < 9.5. It would
  only become a note anyway (same row).
- The paladin Divine Precision note says `same-row prerequisite arrow from
  Holy Shock (rank 1)`; the web cannot draw or enforce it until the schema
  allows same-row targets (Classic had three such arrows).

## Rank assumption

An arrow means "prerequisite at max rank" in Classic (65/65 in the prior).
Nothing in the footage confirms it for Forever: no tooltip shows "Requires
<talent> (Rank N)", and no arrow was ever seen lit (all hovers at rank 0).
`rank` is therefore the target's `maxRank` as read from its tooltip, stated
in every affected talent's `source.note`. If a datamined Talent.db2 arrives
(`PrereqTalent`/`PrereqRank`), it replaces these values wholesale.

## Detector notes (for whoever tunes it)

- The arrow texture on the 1080p stream: a ~2 px stroke about half as bright
  as the art 4-7 px beside it, with a 1 px lighter core (on dark art the
  core is what you see: 30 vs 20), and a filled triangle ~9 px wide at the
  dependent cell. Its edge energy (mean |Laplacian|, 9 px band, 8 px before
  the cell, border skipped) measured 9.6-22 on arrowheads, 8-12 along the
  stroke, 2-8.4 on art between cells. Pixel-width profiles (counting dark
  pixels across the line) did not separate heads from art; the Laplacian
  did. A "ridge continues past the cells = art stripe" heuristic was tried
  and dropped: it rejected two real arrows (art stripes behind paladin
  Protection and hunter Marksmanship) and missed the Shadowburn one.
- Medians: paladin 7, mage 5, shaman 3, others 2, priest and druid 1 (no
  vote possible there; ghosts in the single median would hide an arrow).
  Borrowed `m*` calibrations and the Secondary-page ones are skipped.
- Cost: about 2 s per class on CPU; no VLM involved.

## Next

1. Review queue: the 21 confidence-0.7 arrows (all real on inspection except
   Shadowburn -> Conflagrate) and the two misses above; an override per
   correction, then `08_export.py promote`.
2. Decide whether the schema should allow same-row prerequisites
   (`target.row <= talent.row`, no self, no cycle) so paladin Divine
   Precision <- Holy Shock and Mind Flay -> Improved Mind Flay can be stored
   and drawn; `web/src/ui/Arrows.tsx` needs a horizontal case.
3. Stage 5 rewrites the candidates file: after any `05_read.py run`, run
   `07_arrows.py all <class>` again before stage 8 (`run_class.sh` does).

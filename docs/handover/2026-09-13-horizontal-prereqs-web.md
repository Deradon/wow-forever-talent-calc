# Horizontal prerequisites (web side)

Forever has same-row prerequisites: priest Improved Mind Flay (Shadow Magic,
row 2 col 3) requires Mind Flay right next to it. The data contract is being
relaxed from "the prerequisite sits in an earlier row" to "same tree, same row
or earlier, different cell". This is the web half of that change.

## 1. What was done

Zod mirror (`web/src/data/schema.zod.ts`)

- `TreeSchema` gained a `superRefine` for the one rule the object shapes cannot
  express (`DATA-SCHEMA.md` section 10.8, relaxed): the prerequisite must exist
  in the same tree, sit in the same row or an earlier one, use a different cell
  and name a rank within its own `maxRank`. A **later** row, the talent's own
  cell, an unknown id and a `requires` **cycle** stay errors - rows alone no
  longer rule cycles out once two talents in one row may point at each other.
- `web/src/data/validateData.test.ts` now asserts `target.row <= talent.row`
  plus a different cell instead of `target.row < talent.row`.
- New cases in `web/src/data/schema.test.ts` cover accept-same-row and the four
  rejections.

Rules engine (`web/src/rules/*`) - no production change needed

`canAdd`, `canRemove`, `validate` and `sanitize` never looked at rows for
`requires`, so the horizontal case already behaved. It is now pinned by
table-driven tests in `rules.test.ts` against a second fixture,
`makeHorizontalClass()` in `fixture.ts` (kept apart from `makeClass` so the
codec fixtures and their digit strings stay untouched): `mid` (3 ranks) in row 1
col 1 with `early` left of it, `near` right of it and `far` two cells right.
Covered: adding a dependent needs the prerequisite at rank; the prerequisite's
own points do **not** pay for the row it shares with the dependent (row gating
still asks the rows above), but they do unlock the row below; removing the
prerequisite below the required rank is blocked from either side (`prereq`, or
`would-orphan` when the row below loses its support); `sanitize` drops the
dependent and keeps the prerequisite, whichever side it sits on; plus a
property run of random clicks.

Arrows (`web/src/ui/arrows.ts`, `Arrows.tsx`)

- The same-row shape existed since round 1b (usability finding 18). The
  geometry moved out of the component into `arrows.ts` as the pure
  `arrowLines(tree, build)`, which returns one `ArrowLine` per requirement with
  a `kind` of `vertical | horizontal | elbow`, and the polyline now carries
  `data-arrow-kind` next to `data-arrow` and `data-satisfied`.
- Horizontal arrows run along the row's centre line in both directions,
  adjacent or not, leaving the prerequisite 2px outside its border and stopping
  `CLEARANCE` (5px) short of the dependent's leading edge - inside the 12px
  gutter, never on the icon, backed up by the SVG being painted under the cells.
  Smallest x is 49, so the tier gutter left of the grid is never reached; the
  line stays inside the row's own 44px band, so it cannot share a pixel with the
  vertical leg of an L crossing the row gap.
- Guards added: a requirement pointing at its own cell or at an unknown id draws
  nothing, and a prerequisite below the dependent (invalid data) now aims at the
  bottom edge instead of drawing across the icon.

Tests and fixture

- `web/src/ui/arrows.test.ts` (unit, 17 cases) owns the exact numbers.
- `web/tests/arrows.spec.ts` (Playwright) checks the same shapes against the
  real layout: direction, the head landing between the cells, clearance from the
  tier gutter, the vertical arrow living in the row gap the horizontal ones
  avoid, and gold/grey switching with the build.
- `web/tests/fixtures/fixture-arrows.json` is a new fixture class (`sideways`
  tree: `echo` - `flay` - `improved-flay` - `distant-flay` in row 1, `deep-flay`
  below), loaded only with `VITE_INCLUDE_EXAMPLES=1`. It mirrors the priest
  layout, so nothing here needs a real class file. `classes-index.json` picks it
  up automatically (vite regenerates it); fixture classes have no Classic prior,
  so `classic-diff.json` is unchanged.

## 2. State

`cd web && npx vitest run && npm run build && npx playwright test`: everything
in this work package is green. Six vitest cases (`src/data/classicDiff.test.ts`,
`src/ui/tooltipText.test.ts`) and one Playwright case (`tests/changes.spec.ts`,
"Moved from row 2.") fail **before** these changes too - `tooltipText.ts`
already prints the new `Moved from row 2 to row 1.` wording and its tests have
not caught up. That belongs to the data/wording agent, untouched here.

Screenshot taken on the fixture at 1400px (dev preview, `VITE_INCLUDE_EXAMPLES`):
both horizontal arrows gold, heads in the gutter beside `echo` and
`improved-flay`, the two-cell arrow to `distant-flay` disappearing behind the
cell it passes under and reappearing with its head in the next gutter.

## 3. Next

1. When the data agent's export lands `requires: [{ talent: "mind-flay", rank:
   5 }]` on priest `improved-mind-flay`, no web change is needed: it is the
   adjacent left-to-right case the fixture already covers. Check it on
   `#/priest` and, if you want a real-data regression, add it to
   `tests/arrows.spec.ts`.
2. `docs/DATA-SCHEMA.md` section 10.8 still says `target.row < talent.row`; the
   data owner has that file.

## 4. Decisions on the way

- A cycle check went into the Zod mirror rather than being left to the pipeline:
  with horizontal edges allowed, `a requires b` / `b requires a` in one row is
  now expressible, and it would render two cells nothing can ever unlock.
- A two-cells-apart horizontal arrow passes behind the cell between the two,
  like the vertical leg of every long L. Routing it through the gap above the
  row was rejected: it would read as an arrow from the row above.
- The fixture is a new class file rather than an extension of the tinker example
  (owned by the data agent) or of the rules `makeClass` fixture (whose talent
  set is frozen into the codec test vectors).

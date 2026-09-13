# Handover: A1 tooltip content and player-facing text (2026-09-13)

Work package A1 from `docs/reviews/2026-09-13-consolidated.md`, items 1-5.
Detail specs: `docs/reviews/2026-09-13-text-quality.md` (style guide at the
end) and the review-route findings 12-14 in
`docs/reviews/2026-09-13-usability.md`.

Presentation only: no file under `data/` was touched, and no pipeline code.
Files owned by work package A2 (`TalentCell.tsx`, `ClassPage.tsx`,
`Header.tsx`, `Arrows.tsx`, `App.tsx` routing, `talents.css`, build config)
were not edited; what A1 needs from them is listed under "Requests for A2".

## What changed

New `web/src/ui/tooltipText.ts` - every player-facing string rule as a pure
function, unit tested in `web/src/ui/tooltipText.test.ts` (34 tests, the last
four run over all 469 talents in `data/talents/`):

- `trustKind` / `trustLine` / `fitTrustLine`: the single amber sentence.
  Priority is doubt first: `Uncertain reading, check.` (unreviewed below 0.8
  confidence) beats `Only rank 1 is known.` (`ranksSource: manual`) beats
  `Ranks 2-5 estimated.` / `Rank 2 estimated.`. Never two amber lines, never
  `2+`, never the raw `ranksSource` enum. A reviewed record gets no line.
- `metaLength` / `fitsBudget` / `fitTrustLine`: the budget. Meta is the trust
  line plus the `Details` label, and it must stay shorter than the rendered
  description; when it does not, the short variant is used
  (`Estimated ranks.`, `Rank 1 only.`, `Check this reading.`).
- `requirementLine`: red line for a blocked click, always a full sentence,
  never an internal id. `Requires 10 points in Balance Talents.`,
  `Requires 2 points in Improved Moonfire.`,
  `No points left on this tab (51 of 51 spent).` (was
  `... (51 points on page primary)`), plus the two cases that were silent
  before: `No talent points left (51 of 51 spent).` and
  `Already at maximum rank.`
- `gameRequirement`: the `unparsed requirement: Requires ...` clause hidden in
  `source.note` is rendered as a requirement line under the talent name -
  `Requires Bear Form, Dire Bear Form.`, `Requires Battle Stance.`,
  `Requires Shields.`, `Requires Level 40.` (10 talents; druid forms, warrior
  stances, paladin/warrior shields, `paladin/twist-of-light` level 40).
- `detailLines`: what the disclosure holds, in order - derivation in plain
  words (`Rank 1 was read from the stream. Ranks 2-3 are rank 1 multiplied by
  the rank, the way the matching Classic Era talent scales.`), the reworded
  rounding caveat (`Rank 2 may read 35 in game; the value shown is the
  unrounded 34.`), the reading line (`Read from the stream at 5:48:12.`, with
  `, 70% confidence` only when it is not 100%), and `source.note` clauses
  reworded for players. `rankScaling` reads proportional/copied/table off the
  numbers, not off the note, so the sentence stays true if the note changes.
- `internalId`: the guard. Classic talent ids, similarity scores, reader model
  names, `{0}` slot labels, `needs manual ranks`, crop paths, page ids and the
  `ranksSource` enum are rejected; the corpus test asserts that nothing the
  tooltip can render trips it. That is what keeps pipeline prose on
  `#/review/<class>` from leaking back in with the next data export.

`web/src/ui/Tooltip.tsx` - renders name, `Rank x/y`, `Capstone`, the game
requirement line, the description, `Next rank:` (`Not known yet.` instead of
`Higher ranks unknown (only rank 1 was read).`), the red requirement line,
then one amber trust line with a `Details` disclosure (native `<details>`) on
the same row. The old second caveat (`Rank 5 values unknown; showing the rank
1 text.`) and the always-on provenance line (`..., confidence 100%,
unreviewed`) are gone. The root now carries `id="tooltip-<talent id>"` so a
cell can point `aria-describedby` at it; `ReviewPage` passes its own ids.

`web/src/ui/tooltip.css` (new, imported by `Tooltip.tsx`) - disclosure,
requirement-line and review-chip styles. `talents.css` was not touched.

`web/src/ui/review.ts` - added `filterRows` (flag `all|queue|unreviewed|manual
|crops`, tree, free text) and `diffWords` (word-level LCS), both pure and unit
tested in `review.test.ts`.

`web/src/ui/ReviewPage.tsx` - sticky toolbar with filter chips and counts, a
tree filter, a search box, a "Jump to" select that scrolls to a row (a
`#fragment` would land in the hash route, so it scrolls with JS and
`scroll-margin-top` keeps the row clear of the toolbar), a compact-rows
toggle, links to the other classes' review pages, the matched icon image next
to the frame crop (was an empty dashed box for every non-crop icon), a
`Classic` row with talent id, match kind and similarity, and a word diff for
`source.readings`.

`web/src/ui/ClassPicker.tsx` - the 90-word paragraph is now two sentences,
with the repo link on its own line. This is the one place the global caveat is
stated.

## Before and after

Meta text (caveat + provenance, then trust line + `Details`) against the
rendered rank-1 description, all 469 talents:

| | median meta/description | over budget | median meta | longest meta |
|---|---|---|---|---|
| before | 1.80 | 331 of 469 (70%) | 167 chars | 458 chars |
| after | 0.26 | 0 | 27 chars | 32 chars |

Sample rows (description chars, meta before -> after):

- `mage/burning-soul` 139: 458 -> 27 (`Ranks 2-3 estimated.` + `Details`)
- `druid/reflection` 63: 333 -> 27
- `druid/improved-wrath` 78: 207 -> 28 (`Only rank 1 is known.`)
- `druid/natural-reaction` 97: 144 -> 28, and it now shows
  `Requires Bear Form, Dire Bear Form.`
- `druid/mangle` 49: 56 -> 7 (`Details` only)

Checked visually against the preview build (`npm run build && npm run
preview`) with Playwright: hover tooltips for `druid/reflection`
(classic-prior), `druid/natural-reaction` (manual with a form requirement),
`druid/improved-entangling-roots` and `druid/5-rage` (both low confidence),
the same tooltips with the disclosure open, and `#/review/druid` with and
without a filter. Screenshots are in the session scratchpad, not committed.

The screenshots caught one bug that the tests had missed: `trustLine` read
`confidence` off the talent instead of off `talent.source`, and because every
field involved is optional a whole `Talent` was still structurally assignable.
`ReadFacts` now nests `source`, and a corpus test asserts that each of the 77
unreviewed sub-0.8 records gets the `Uncertain reading` line.

## Decision taken on the way

The style guide lists the trust line priority as estimated ranks first,
uncertain reading last. That would silence the warning on 49 of the 77
low-confidence records, because they also carry estimated ranks - and section
3 of the same review asks for `Uncertain reading - check` on
`warrior/enrage`, which is exactly such a record. Doubt about the text a
player is reading now wins; the estimated-rank story is one click away in the
disclosure. Wording is the consolidated review's `Uncertain reading, check.`

## Requests for the A2 owner

1. `talents.css` sets `pointer-events: none` on `.tooltip-layer` and
   `.tooltip`, and `useHover` in `TalentCell.tsx` has no `safePolygon`, so the
   `Details` disclosure cannot be reached with the mouse on a class page (it
   works on `#/review/<class>`, where `.review-tips .tooltip` re-enables
   pointer events). Please keep the tooltip open while the pointer is over it
   (`safePolygon` from `@floating-ui/react`, or `handleClose`) and let the
   floating layer take pointer events. `tooltip.css` already sets
   `pointer-events: auto` on the disclosure itself.
2. `aria-describedby`: the tooltip root renders `id="tooltip-<talent id>"`;
   add `aria-describedby={`tooltip-${talent.id}`}` to the cell button while
   the tooltip is open.
3. The caveat is now stated once on the picker. Please drop the duplicate in
   `ClassPage.tsx` (`Data was read from stream footage (video); talent rules
   are assumed. Hover a talent for its provenance.`), keep
   `Left click adds a point, right click removes one.` and the class note, and
   shorten the `App.tsx` nav subtitle to
   `Classic+ talent calculator - unofficial, unreviewed data`.
4. Touch and keyboard: the disclosure is a real button in the tooltip, so the
   tap-to-open tooltip from A2 item 5 gets it for free; please make sure the
   tooltip is reachable (and dismissible) without a mouse.
5. The `?` badge legend (A2 item 6) should read the same as the trust line:
   `? = uncertain reading, check it`.

## Not done here, for later

- `source.readings` is empty on all 469 records, so the review route's word
  diff has nothing to show yet. Package B has to emit both readings for
  `second reader ... differs in ...` to be reviewable (usability finding 14).
- Article and unit normalisation at render time (`a`/`an` before a number,
  `sec` everywhere) - text-quality section 4. It is safe only for the article
  case; the unit fixes belong in the data (package B item 1), and the three
  reviewed decisions there (`5-rage`, `shatter`, `quietus`) change the numbers
  the tooltip shows.
- `j`/`k` row jumping on the review route; the "Jump to" select covers the
  need for now.

## Commands

```
cd web && npx vitest run && npm run build   # 131 tests, build clean
cd web && npm run preview                   # then #/druid and #/review/druid
```

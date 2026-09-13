# Handover: nested, sticky tooltips (2026-09-13)

Crusader Kings style tooltips for the class pages, desktop first. Closes the
one request work package A1 made of A2 that could not be met at the time
(`docs/handover/2026-09-13-fix-a1-tooltip.md`, request 1;
`docs/handover/2026-09-13-fix-a2-interaction.md`, "A1's requests", item 1):
the derivation is now mouse-reachable, and the grid stays clickable.

Web only. Nothing under `data/` or `pipeline/` was touched.

Verified green: `npx vitest run` (153 tests, 14 files), `npm run build`
(type-check included), `npx playwright test` (27 tests, 9 of them new).

## The problem A2 measured, and the rule that solves it

A tooltip is 300 px wide and the grid gap is 12 px, so an interactive tooltip
always covers a neighbouring cell. A2 made the layer interactive, the
neighbour became unclickable, and two Playwright suites failed on intercepted
clicks. The layer went back to `pointer-events: none` and the disclosure
stayed unreachable.

The fix is not a placement trick - it is that the layer takes the pointer only
when the player has shown intent **twice** (`web/src/ui/stickyTooltip.ts`):

1. **Dwell.** The pointer rested on the cell for `CELL_DWELL_MS` (250 ms).
   A brisk click along a row never dwells.
2. **Approach.** After leaving the cell, two consecutive pointer samples land
   inside the tooltip box, each a step a hand could have made
   (`0 < step <= 40 px`). A cursor that *teleports* onto the tooltip in one
   jump - which is what a script does, and the shortest jump on this grid is
   56 px - never counts, so the cell underneath keeps the click.

Both predicates are pure and unit tested (`stickyTooltip.test.ts`). The layer
carries `data-sticky="true"` once it is live, which is what the new Playwright
cases assert in both directions: the sticky path must work, and the brisk path
must never trigger it.

Two supporting pieces:

- **`safePolygon` cannot see a transparent layer.** While the layer is
  `pointer-events: none`, floating-ui hit-tests the cell *underneath* it, so
  the polygon closes the tooltip the moment the cursor arrives - the exact
  failure A2 described. `TalentCell`'s `onOpenChange` therefore vetoes a
  `safePolygon` close while the cursor is inside the (still transparent)
  layer and the cell was dwelled on. Holding it open costs nothing: the layer
  is still transparent, so every click still reaches the grid.
- **One tooltip at a time.** `claimTooltip` in the same module closes whichever
  tooltip was open when another cell opens one, so hovering another cell beats
  a sticky tooltip that is still hanging around.

Closing: leaving the tooltip (safePolygon's grace), Escape, hovering another
cell, or pressing the tooltip's own background - the last one because *cells
win in every ambiguous case*, so a press that was meant for the grid gets the
tooltip out of the way instead of being eaten twice. The neighbour is clickable
again immediately, because the layer is unmounted with the tooltip.

## Placement

`web/src/ui/tooltipPlacement.ts`, pure and unit tested:

- last column -> `left`, everything else `right`;
- the bottom two rows -> `-end` (the tooltip grows upwards), but only once at
  least `HEADER_CLEARANCE_ROWS` (3) rows sit above the cell, so it can never
  reach the tree title;
- fallbacks mirror the **side** first (`right-start` -> `left-start` ->
  `right-end` -> ...), so a flip at the viewport edge does not silently move
  the tooltip onto a different row. `top`/`bottom` are last resorts.

The leftmost tree still flips to the right for its last column, because there
is no room on the left of the page - that is `flip` doing its job, and the
Playwright case checks the rule on the rightmost tree instead.

## What replaced the `<details>` disclosure

`TooltipContent` renders **terms**: underline-dotted, `cursor: help`, each a
real `<button>`. Hovering one (same dwell, same `safePolygon`) opens a nested
tooltip; at most one per card, one level deep.

| Term | Nested content |
|---|---|
| the amber trust line, or `Details` when there is none | `detailLines()` - the derivation in plain words |
| `Rank x/y` | `rankDerivationLines()`: `Values by rank: 5/10/15.`, `Classic Era: 2/4/6/8/10.` when the record carries a `ranksPrior`, the derivation sentence, the rounding caveat |
| a prerequisite name inside the red requirement line | that talent's own card - `TooltipContent` at `depth={1}`, so it carries no terms of its own |
| the `?` marker | `readerViews()`: every reading side by side with its confidence, plus the **source crop** - the stream frame the reader looked at |

New pure helpers in `tooltipText.ts`, all unit tested and all behind the
existing `internalId()` guard: `foreverSeries`, `classicSeries`, `ranksCopied`,
`rankDerivationLines`, `readerViews`, `splitOnNames`. The Classic numbers come
out of `ranksNote` by regex - only the digit series, never the sentence around
it, which carries the Classic talent id and the similarity score. `readerViews`
labels readings `The reading in use` / `A second reading`; a reader model name
never reaches a player, and a corpus test asserts that over all 469 records.

`splitOnNames` cuts the rendered requirement line at the prerequisite names it
contains, so the wording stays exactly the tested string from `requirementLine`
and the name inside it still becomes a term.

**Keeping it reachable without a mouse**

- `d` while a tooltip is showing toggles the derivation open **in place**
  (`data-testid="derivation-<id>"`). It works from keyboard focus, where there
  is no pointer at all.
- A tap opens any nested tooltip: the terms use `useClick` as well as
  `useHover({ mouseOnly: true })`. Without `mouseOnly`, the synthesized
  `mouseleave` after a tap closed the card again.
- While the derivation is collapsed, the same lines sit in the tooltip as
  `sr-only` text, so `aria-describedby` still resolves them - A1's request 4,
  now true whether or not anything is expanded.

**Nested positioning.** A term usually starts at the card's left edge, so
anchoring on the term alone dropped the nested card on top of the text it
explains. The terms therefore set a *position reference* that takes `left`/
`right` from the parent card and `top`/`bottom` from the term: the nested card
lands beside the whole card, aligned with its term, with a 10 px connector rule
(`.tooltip-nest::before`, drawn on whichever side floating-ui chose).

Nested layers are rendered **inside** the parent tooltip's DOM, not in a
portal. That is load-bearing: `safePolygon` keeps the parent open while the
pointer is over a descendant of the floating element, so DOM nesting is what
makes a two-level chain survivable with a mouse.

## Files

Added: `web/src/ui/stickyTooltip.ts` + `.test.ts`,
`web/src/ui/tooltipPlacement.ts` + `.test.ts`, `web/tests/tooltip.spec.ts`.

Changed: `web/src/ui/Tooltip.tsx` (terms, nested tooltips, readings, in-place
derivation), `TalentCell.tsx` (dwell/approach, placement, `d`, the pointer-down
escape hatch), `TreePanel.tsx` (passes `rankOf` down for the nested
prerequisite card), `tooltipText.ts` + `.test.ts`, `tooltip.css`, `talents.css`
(the layer decides pointer-events; `.tooltip` inherits), `web/tests/touch.spec.ts`.

## Bundle

| | before (A2) | after |
|---|---:|---:|
| main chunk gzip | 103,650 B | 107,600 B |
| CSS gzip | 5,073 B | 5,435 B |
| `ReviewPage-*.js` gzip | 19,059 B | 2,738 B |
| `crops-*.js` gzip (new, on demand) | - | 10,971 B |

The main chunk grows by ~3.9 kB gzip for the nesting machinery. The crop
registry (971 paths) is now its own chunk shared by the review route and by the
`?` marker's nested tooltip, which imports it with a dynamic `import()` only
when a player actually opens one - so the class route still fetches one class
chunk and no review code (`tests/landing.spec.ts` still passes unchanged).

## New Playwright cases (`web/tests/tooltip.spec.ts`, plus one in `touch.spec.ts`)

- a tooltip goes sticky when the pointer walks into it, and the derivation is
  readable; Escape closes the chain
- the rank term shows the Classic values, and only one nested tooltip is open
  at a time
- the neighbour under a sticky tooltip is clickable again as soon as it closes
  (it asserts the tooltip really does cover the cell first)
- a brisk click sequence across a row never makes a tooltip sticky
- a prerequisite name opens that talent's own card (10 points into Protection
  without touching Redoubt, so what blocks Shield Specialization is the
  prerequisite and not the row)
- the uncertain marker shows both readings and the captured crop, and names no
  reader
- `d` opens the derivation in place, from keyboard focus only
- tooltips prefer the placements that cover fewer cells (last row opens
  upwards; last column opens left)
- touch: a tap opens the nested tooltips that replaced the disclosure, and the
  tap never reaches the cell

Checked visually against the preview build at 1280x800: the Tinker
`improved-wrench` card with the derivation open, and Paladin
`infusion-of-light` with the readings and its stream crop. Screenshots are in
the session scratchpad, not committed. The crop shot caught one bug: the image
was `width: 100%`, so the Tinker example's 1x1 placeholder crop stretched into
a 236 px black wall. Crops now render at natural size, capped at 200 px.

## Notes for whoever comes next

- The example class `tinker` is the only record in the repo with a populated
  `source.readings`, so it is the only place the two-reader comparison has
  anything to show. The real classes render "Only one reading was recorded."
  plus the crop until package B emits both readings (A1's "Not done here").
- The approach heuristic is deliberately hostile to synthetic pointers. A test
  that wants a sticky tooltip has to walk into it (`page.mouse.move(..., {
  steps: 30 })`); `hover()` alone will never make one sticky, which is exactly
  what keeps the other suites safe.
- Still open from the earlier reviews and untouched here: usability 8-11,
  16/17 (mobile layout), 18, 20-22, 24/25; P-4 to P-8; A-8, A-10, A-12.

## Commands

```
cd web && npx vitest run && npm run build && npx playwright test
cd web && npm run preview   # then #/tinker and #/paladin
```

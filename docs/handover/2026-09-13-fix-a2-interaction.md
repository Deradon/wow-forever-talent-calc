# Handover: A2 - interaction, accessibility, performance, 2026-09-13

Work package A2 from `docs/reviews/2026-09-13-consolidated.md`, items 1-9.
Details in `docs/reviews/2026-09-13-usability.md` (findings 1-7, 19, 23) and
`docs/reviews/2026-09-13-performance-a11y.md` (A-1 to A-9, P-1 to P-3, S-1,
S-3). Nothing committed. Work package A1 (Tooltip, ReviewPage, copy) ran in
parallel; what it asked of A2 is answered under "A1's requests".

Verified green: `npx vitest run` (131 tests, 10 files), `npm run build`
(type-check included), `npx playwright test` (18 tests). The Playwright suite
had two pre-existing failures in `tests/paladin.spec.ts` before this work
started - stale expectations from when Paladin had more crop icons; both are
fixed below.

## Bundle and request budget

Same data, same nine classes, `npm run build` with no `VITE_BASE`.

| | before | after | delta |
|---|---:|---:|---:|
| main chunk `index-*.js` raw | 493,984 B | 324,208 B | **-169,776 B (-34 %)** |
| main chunk gzip | 138,850 B | 103,650 B | **-35,200 B (-25 %)** |
| CSS gzip | 4,014 B | 5,073 B | +1,059 B |
| `ReviewPage-*.js` (new, review route only) | - | 104,676 B / 19,059 B gzip | - |
| class chunks (9, unchanged) | 344,644 B / ~63,700 B gzip | same | - |
| **first load, landing `#/`** | 11 text subresources | **2** (entry JS + CSS) | -9 requests, -58 kB gzip |
| **first load, class `#/paladin`** | 3 text + 51 images | 3 text + 52 images | -35.2 kB gzip of JS |
| `dist/` total | 1291 files, 18.84 MiB | 1294 files, 18.87 MiB | +robots, +sitemap, +1 chunk |

Where the 35.2 kB gzip came from:

- **zod off the production path** (~25 kB gzip, P-3). `src/data/schema.ts` is
  now hand-written types plus `renderDescription`, no zod. The zod mirror moved
  to `src/data/schema.zod.ts` and `load.ts` reaches it through
  `if (import.meta.env.DEV) await import('./schema.zod')`, which folds to dead
  code in production. Dev, `vitest` and `validate-data` still validate every
  class file, and `schema.zod.ts` carries a compile-time assertion that
  `z.infer<typeof ClassSchema> extends ClassData`, so the two cannot drift -
  `tsc -b` fails if they do.
- **the crop registry code-split** (~16 kB gzip, P-2). `src/data/crops.ts`
  (eager glob over all 971 crops) is now imported only by `ReviewPage`, which
  `App.tsx` loads with `React.lazy`. The calculator uses the generated
  `src/data/iconCrops.ts` instead: exactly the 73 `iconSource: "crop"` icons.
  Verified in the built output: 73 `data/review/` occurrences in the main
  chunk, 971 in the review chunk.
- The landing page no longer imports class chunks (P-1); that is nine fewer
  requests rather than main-chunk bytes.

`tests/landing.spec.ts` asserts all three as a budget: the landing page fetches
exactly one script, no class chunk and no `ReviewPage` chunk; the class route
fetches exactly one class chunk and still no review chunk.

## Build-time data indexes

`web/scripts/gen-data-index.mjs` generates two files into `src/data/` from
`data/talents/*.json`, `data/examples/*.json` and `web/tests/fixtures/*.json`
(the same precedence `load.ts` uses):

- `classes-index.json` - id, origin, class name, data source, maxPoints,
  talent/reviewed/needs-review counts, tree names and sizes. 4.8 kB. It is the
  landing page's whole data source now.
- `iconCrops.ts` - one static `?url` import per crop icon, 73 entries.

A small plugin in `vite.config.ts` runs the generator in `config()` and
`buildStart()`, so every dev server, build and vitest run refreshes them. Both
files are **committed** because `tsc -b` runs before `vite build`;
`src/data/generated.test.ts` fails when a commit forgets to refresh them, and
also cross-checks the index against the class files it claims to describe.

Regenerate by hand with `node scripts/gen-data-index.mjs` from `web/`.

## Interaction and accessibility

**Keyboard (A-1, usability 23).** `TalentCell` now passes `onClick`,
`onContextMenu` and `onKeyDown` *through* `getReferenceProps({...})`, so
floating-ui's `useDismiss` handler no longer overwrites the component's.
Backspace / Delete / `-` refund again.

**Grid pattern (A-7).** `TreePanel` renders `role="grid"` with one
`role="row"` per talent row. The row elements are `display: contents`, so the
CSS grid still positions the cells itself and the layout is byte-identical.
Cells are `<button role="gridcell">` with a roving `tabindex`: one tab stop per
tree, arrows/Home/End move inside it. The tab stop defaults to the first spent
talent, else the first cell. This is a deliberate deviation from the letter of
the WAI pattern (a gridcell normally *contains* the widget); putting the role
on the button keeps the accessible name and native Enter/Space activation and
costs no wrapper per cell.

**Touch (A-2, A-3).** `useCoarsePointer()` in `ClassPage` watches
`(hover: none), (pointer: coarse)`. On a coarse pointer the cell's click no
longer spends a point: a tap opens the tooltip via `useClick`, and the floating
layer renders explicit `+` / `-` buttons (44 px targets) plus the rank and the
points left underneath `TooltipContent`. `pointer-events` is re-enabled for
that mode only. Kept deliberately minimal per the owner's note - no responsive
layout work; usability 16/17 (`--cell` sizing, sticky header, tree tabs) are
untouched and still open.

**Blocked actions (usability 4).** `ClassPage` now asks `canAdd` / `canRemove`
itself and, on a refusal, shows a `role="alert"` line under the header for 4 s
plus a red flash on the cell (a remounted `<span key={blockedAt}>`, so a repeat
refusal replays it; `prefers-reduced-motion` gets a static ring instead). The
wording lives in `src/ui/interaction.ts` (`blockedMessage`), unit-tested in
`interaction.test.ts`.

**Rules change.** `canRemove` in `src/rules/mutate.ts` now puts the blocked
talent's **name** in `verdict.detail` instead of its slug, so the message reads
"Refunding Devotion Aura would orphan Consecration". This is the only rules
change; `rules.test.ts` was already `toMatchObject` on reason only, and
`interaction.test.ts` covers the new detail.

**Zero points (usability 2).** No new cell state was needed: a rank-0 available
cell already carries `data-addable="false"` when the pool is empty. It is now
styled dim (border `#4f7d46`, desaturated icon), the header shows "all spent"
in gold, the accessible name says "no talent points left", and the floating
layer adds a "No talent points left (51/51 spent)" note.

**Search (usability 1).** Input in the header, `/` focuses it from anywhere,
Escape clears. Matching cells get `data-match="true"` (gold outline),
non-matching `data-match="false"` (25 % opacity). A result list under the header
shows up to 8 talent **names** with tree and row - the first place talent names
are visible in the DOM without hovering - and clicking one switches page if
needed, scrolls to the cell and focuses it. `matchesTalent` matches name and
description; unit-tested.

**Landmarks and live region (A-6, A-7).** `App.tsx` wraps the body in
`<main id="main" tabIndex={-1}>` with a skip link as the first focusable
element (it `preventDefault`s, because the app routes on the hash and `#main`
must not land there). `ClassPage` renders a visually hidden
`aria-live="polite"` region with per-tree points, points left and required
level.

**Tooltip for screen readers (A-4).** The cell sets `aria-describedby` to
A1's tooltip root id while the tooltip is open, and passes that id down through
`TooltipContent`'s `id` prop. See "A1's requests" for why floating-ui's
`useRole` is not used.

**Cell state in text (A-5).** `aria-label` is now
`"<name>, rank X of Y, locked: requires 5 points in Holy"` / `", maxed"` /
`", no talent points left"` / `", low-confidence reading, may be misread"`, and
locked or unaffordable cells carry `aria-disabled="true"` while staying
focusable. Note for test authors: Playwright treats `aria-disabled` as *not
enabled*, so a test that deliberately clicks such a cell needs
`click({ force: true })`.

## Visual fixes

**Crop icons (usability 6).** The `<img>` moved into a `.icon-clip` wrapper and
crop icons render at 120 % with a -10 % margin, i.e. the 36 px source inset by
3 px per edge - that removes the in-game green border, so cells no longer show
two nested borders.

The in-game **rank box cannot be removed by an inset**: measured across all 73
crops it starts at exactly `(18, 18)` of 36, i.e. the whole bottom-right
quadrant, and cropping it away would eat more than half the icon. Our own badge
now covers it instead: it moved inside the cell and is 22x22, which is exactly
where the game's counter lands after the 3 px inset. Verified by screenshot -
no doubled border, no doubled number. The cost is a slightly larger badge on
the 402 non-crop cells too; making it large for crop cells only would be
inconsistent across a grid, so it is uniform. A pipeline re-crop (package B)
could shrink it back.

**Badge overlap (usability 7).** Both the rank badge (was `right/bottom: -7px`)
and the review `?` flag (was `left: -7px; top: -8px`, and a `::after`, so it had
no text equivalent) are now elements inside the cell. A legend beside the search
box explains the `?` and the counter.

**Contrast (A-9).** Locked border `#555` (2.60:1) -> `#787878` (4.39:1). The
out-of-points border is `#4f7d46` (4.02:1). The locked icon filter went from
`grayscale(1) brightness(0.5)` to `grayscale(0.7) brightness(0.75)` (usability
19), so deep talents are identifiable again.

## SEO (S-1, S-3)

`web/index.html` gained a longer title, a real description, canonical,
`og:type/site_name/title/description/url/locale`, `twitter:card=summary` and
`theme-color`. `web/public/robots.txt` and `web/public/sitemap.xml` are new.

Two caveats: no `og:image` (a 1200x630 PNG is on the review's "Not doing now"
list), and on GitHub Pages `robots.txt` is served under
`/wow-forever-talent-calc/robots.txt`, not the domain root, so crawlers will not
honour it as a robots file - it becomes effective if the site moves to a custom
domain. The sitemap lists one URL because hash routing gives one crawlable URL
(S-2, per-class prerender, is out of scope).

## A1's requests, and one that could not be met

From `docs/handover/2026-09-13-fix-a1-tooltip.md`, "Requests for the A2 owner":

2. **Done.** `TooltipContent` already takes an `id` prop, so the cell sets
   `aria-describedby={`tooltip-${talent.id}`}` while the tooltip is open and
   passes the same id down. `useRole` was deliberately *not* used: it would put
   a second `role="tooltip"` on the floating wrapper around A1's root.
   `tests/interaction.spec.ts` asserts the id resolves to a `role="tooltip"`
   element and that exactly one exists.
3. **Done.** The duplicate caveat is gone from `ClassPage.tsx` (the help line is
   now the interaction hint plus `cls.notes`), and the `App.tsx` nav subtitle
   reads `Classic+ talent calculator - unofficial, unreviewed data`.
4. **Done for touch.** A tap opens the tooltip, the layer takes taps there, and
   Escape / a tap outside dismisses it (`useDismiss`). Not done for the
   keyboard: the tooltip lives in a `FloatingPortal` at the end of `<body>`, so
   Tab from a cell goes to the next cell, not into the tooltip. Making the
   disclosure keyboard-reachable needs a focus decision that belongs with the
   tooltip owner (a focus manager on the portal, or a key that moves focus into
   it). The *content* is still announced, because `aria-describedby` resolves
   the whole tooltip subtree including the open details.
5. **Done.** The legend reads `? = uncertain reading, check it`, and the cell's
   `aria-label` uses the same words.

1. **Could not be met, and should be redesigned.** Making the Details
   disclosure mouse-reachable needs the floating layer to take pointer events,
   and `safePolygon` alone is not enough - with `pointer-events: none` the
   polygon closes as soon as the cursor reaches the tooltip, because
   floating-ui hit-tests the floating element. Both were implemented and
   measured:

   - layer interactive + `safePolygon`: the disclosure works (verified - it
     opens, and the cell's rank does not change), **but the tooltip is anchored
     8 px right of a cell and is far wider than the 12 px grid gap, so it
     always covers the neighbouring cell**. With pointer events on, that cell
     became unclickable: two Playwright cases that walk the grid clicking
     addable cells started failing on an intercepted click.
   - So the layer is back to `pointer-events: none` on hover, and interactive
     only when the tooltip was opened by tap (`[data-touch="true"]`).

   A hover tooltip that covers its neighbours cannot also be traversable by
   mouse. Options for A1, in the order I would try them: put the derivation on
   `#/review/<class>` and behind `?debug=1` only (the consolidated review's own
   first suggestion for finding 5); or move Details out of the hover tooltip
   into a panel that opens on an explicit action; or keep it and accept that it
   is a touch and screen-reader affordance. Whatever the choice, the cells must
   stay clickable.

## Still open from the reviews (not in A2 items 1-9)

- Usability 8 (class switcher in the header), 9 (Back = undo), 10 (Reset
  confirmation), 11 (notice wall), 16/17 (mobile layout, sticky header - owner
  deferred), 18 (arrowheads drawn over the target; `Arrows.tsx` untouched), 20
  (landing page order and class colours), 21 (review link on public cards), 22
  ("Required level: 1" at 0 points), 24/25 (build summary, empty right column).
- P-4 to P-8 (WebP crops, icon sprite, modulepreload, immutable caching,
  `React.memo` on the cell). P-8 is now slightly more relevant: `TreePanel`
  calls `canRemove` per cell as well as `canAdd`, and `canRemove` runs
  `validate()` twice. Measured click cost is still well inside budget on this
  machine, but that is the first thing to memoise if a class ever grows past
  ~80 talents.
- A-8 (incomplete tab roles in `PageTabs`), A-10 (focus on route change), A-12
  (intrinsic dimensions on review frames). A-11 is now genuinely exercised: the
  blocked-action flash is the app's first animation and honours
  `prefers-reduced-motion`.

## Files

Added: `web/scripts/gen-data-index.mjs`, `web/scripts/gen-data-index.d.mts`,
`web/src/data/schema.zod.ts`, `web/src/data/iconCrop.ts`,
`web/src/data/iconCrops.ts` (generated), `web/src/data/classes-index.json`
(generated), `web/src/data/generated.test.ts`, `web/src/ui/interaction.ts`,
`web/src/ui/interaction.test.ts`, `web/tests/interaction.spec.ts`,
`web/tests/touch.spec.ts`, `web/tests/landing.spec.ts`,
`web/public/robots.txt`, `web/public/sitemap.xml`.

Changed: `web/vite.config.ts`, `web/tsconfig.node.json`, `web/index.html`,
`web/src/App.tsx`, `web/src/data/schema.ts` (zod removed), `crops.ts`,
`load.ts`, `web/src/rules/mutate.ts`, `fixture.ts`, `web/src/ui/TalentCell.tsx`,
`TreePanel.tsx`, `ClassPage.tsx`, `Header.tsx`, `ClassPicker.tsx` (data source
only - the copy is A1's), `talents.css`, and the test imports that followed the
schema split (`crops.test.ts`, `schema.test.ts`, `validateData.test.ts`,
`codec.test.ts`).

Not touched: `Tooltip.tsx`, `ReviewPage.tsx`, `review.ts`, `Arrows.tsx`,
`Notice.tsx`, `PageTabs.tsx`, `main.tsx`, and the URL codec itself
(`src/url/codec.ts`, `route.ts`).

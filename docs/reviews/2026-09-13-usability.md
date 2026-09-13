# Usability review, 2026-09-13

Live site (`https://deradon.github.io/wow-forever-talent-calc/`) driven with
Playwright at 1280x900 and at 400px mobile width. Reviewed as a WoW player who
wants to plan a build fast, plus one pass over `#/review/<class>` as a data
reviewer. Screenshots referenced by filename live in the session scratchpad
(not committed).

25 findings, ordered by severity.

## High

### 1. A talent can only be identified by hovering it, one at a time

Severity: **high**. Evidence: `03-priest-1280-fold.png`; the page's full text
content contains no talent names at all, only `0/5`-style counters. 48 of 53
Priest cells use real icon files, 5 use frame crops, and none carry a label.
There is no search box anywhere on the site.

Planning a build means "where is Improved Power Word: Shield" — currently the
only answer is to hover cells until one matches. Wowhead's calculator solves
this with a search field that dims non-matching talents.

Suggestion: add a search input in the class header that filters/highlights
cells by talent name and description (match -> full opacity + outline,
non-match -> 30% opacity), plus `aria-label` is already there, so also allow
`/` to focus it.

### 2. With 0 points left the whole tree still looks clickable

Severity: **high**. Evidence: `23-full-51.png`, `24-nopoints-tooltip.png`.
After spending all 51 points in Discipline, 35 cells in Holy and Shadow Magic
still render with green borders and green badges and full-colour icons.
Clicking them does nothing, and their tooltip shows no explanation.
`cellState.ts` does this deliberately (`return 'available' // out of points:
keep the colour, just not addable`), and `requirementLine()` in `Tooltip.tsx`
returns `undefined` for `reason === 'no-points'`.

Suggestion: add a fifth cell state (`data-addable="false"` on a rank-0
available cell) rendered with a dim/desaturated border, and add a tooltip line
"No talent points left (51/51 spent)". The header "Points left: 0" should also
get a warning colour.

### 3. On mobile the tooltip never appears and points cannot be refunded

Severity: **high**. Evidence: `19-mobile-tap.png`; tapping
`talent-power-in-light` at 400px raised the rank to 1 and produced zero
`[role="tooltip"]` nodes. The tooltip is bound to `useHover`/`useFocus` only,
and refunding is bound to `onContextMenu`.

On a phone the app is therefore unreadable (no talent text at all) and
one-way (the only undo is Reset, which wipes everything).

Suggestion: on coarse pointers, make the first tap open the tooltip with an
explicit "+" / "-" control pair inside it (or long-press to refund), and show
the per-talent name in that tooltip. Keep click-to-add for mouse users.

### 4. Every blocked interaction fails silently

Severity: **high**. Evidence: `09-click-locked.png` (clicking the locked
`Inner Focus` left "Points left: 51" and produced no visible change);
`15-refund-blocked-tooltip.png` (right-clicking a 5/5 `Power in Light` that
gates a spent `Martyrdom` left the rank at 5 and the tooltip said nothing
about why). Clicking a maxed talent a sixth time is equally silent.

The rules layer computes a `Verdict` with a reason for adding, but nothing is
computed or shown for a refused *removal*, and nothing at all animates.

Suggestion: a short shake/flash on the cell plus a transient one-line message
under the header ("Martyrdom needs 5 points in Discipline"), and a
`canRemove()` verdict whose reason feeds both.

### 5. Tooltips are up to half pipeline meta-information, in the loudest colour

Severity: **high**. Evidence: `08-tooltip-zoom.png` (Martyrdom: 6 lines of
game text, then 4 lines of orange caveat and 2 of provenance);
`24-nopoints-tooltip.png` (Twilight Focus, a *Priest* talent, whose caveat
reads "Classic druid/balance/Improved Entangling Roots (talent 787)
(cross-class), matched on description (0.93): Classic 40/70/100 = 30 x rank
+10; Forever rank 1 is 23 = 0.575x Classic's 40, step and offset scaled by
0.575. Rounding: rank 2 40.25 may read 40 ...").

The caveat (`#e2a640`, 12px) is visually louder than the actual spell text
(`#ffd`, 13px), and leaks internal vocabulary: `classic-prior`, `talent 321`,
`cross-class`, match scores, reader model names, "confidence 100%".

Suggestion: keep one short player-facing line ("Ranks 2-5 estimated, not read
from the stream") and move the derivation to the review route (or behind a
"why?" affordance / `?debug=1`). Drop `confidence NN%` from the player
tooltip; keep only "unreviewed".

### 6. Frame-crop icons contain the in-game border and rank counter

Severity: **high**. Evidence: `26-crop-icon-zoom.png` (8x zoom of
`Power in Light`). The crop includes the game's own green border and its own
`0` rank box, so the cell shows two nested green borders and two rank numbers,
one of which is ours (`0/5`) sitting right next to the baked-in one. 5 of 53
Priest talents use crops, and they are all in row 1 - the most visible row on
the page.

Suggestion: crop tighter (inset the source rect by the in-game frame width) or
render crop icons at a smaller inset with our own frame drawn on top; failing
that, prefer the `initials` fallback over a crop that contains a second
counter.

## Medium

### 7. The orange "?" badge is never explained

Severity: **medium**. Evidence: `03-priest-1280-fold.png` - 7 orange `?`
circles float over the Discipline/Holy/Shadow grids, overlapping the top-left
corner of their cell and sometimes the cell above. Nothing on the page says
what they mean (they are `source.confidence < 0.8 && !reviewed`). The
hover tooltip's provenance line turns orange, but you have to hover to learn
that.

Suggestion: a one-line legend under the trees ("? = low-confidence reading,
may be misread") and move the badge inside the cell's top-left corner so it
stops colliding with neighbours.

### 8. No way to switch class from a class page

Severity: **medium**. Evidence: the only links on `#/priest` are the site
title (`#/`) and the GitHub footer link. Comparing Priest with Shaman means
going back to the picker every time.

Suggestion: a class strip or `<select>` in the header, next to the class name.

### 9. Browser Back after editing leaves the calculator and loses the build

Severity: **medium**. Evidence: spending 5 points moved the hash to
`#/priest?v=1&t=5` via `replaceState`; one Back press landed on the empty hash
(the class picker) and the build was gone from the header. Forward restores
it, but nobody expects Back to be "leave the page" after 30 clicks of build
editing.

Suggestion: either push a history entry per edit (Back = undo, which is what
players will try) or leave a single entry for the whole editing session.

### 10. Reset has no confirmation and no visible undo

Severity: **medium**. Evidence: `23-full-51.png` - "Reset" sits directly next
to "Copy link" in the header; one click wiped a 51-point build. (Back happens
to restore it, but only because the arrival URL was a different history
entry - undiscoverable.)

Suggestion: an inline "Reset - undo?" confirmation for a few seconds after the
click, or require a second click.

### 11. Notices for a stale link are a wall of internal jargon

Severity: **medium**. Evidence: `25-notice-adjusted.png`. Opening
`#/priest?v=1&t=999999999999999999-55555` produced two banners that together
fill the screen above the trees, listing every clamped talent by name and then
`holy/divine-fury: no-points (72 > maxPoints 51)` eight times followed by "and
13 more".

Suggestion: collapse to one sentence ("This link did not fit the rules; 21
points were dropped and some ranks clamped.") with a "details" disclosure, and
deduplicate violations per talent.

### 12. Review route has no filters and no navigation on an 18,700px page

Severity: **medium**. Evidence: `#/review/priest` renders 53 rows,
`scrollHeight` 18710px, with no anchor list, no per-tree filter, and no
"queue only" toggle - even though the header itself says which 9 talents are
below 80% confidence (`21-review-fold.png`).

Suggestion: filter chips (queue / unreviewed / all, and per tree), a sticky
count, and `j`/`k` to jump between rows.

### 13. Review route never shows the matched icon it asks you to verify

Severity: **medium**. Evidence: `22-review-row.png` - next to "icon: classic
(spell_nature_tranquility)" there is an empty dashed placeholder. In
`ReviewPage.tsx` the icon image is only built for `iconSource === 'crop'`;
for matched icons it renders `review-missing`. The header meanwhile reports
"5 unmatched icons", implying icon matching is something to review.

Suggestion: render `icons/<talent.icon>.jpg` next to the frame crop so the
reviewer can compare the matched icon against the crop side by side.

### 14. Review route says a second reader disagrees but never shows what it read

Severity: **medium**. Evidence: `22-review-row.png` - "Note: second reader
(codex) differs in description", with no diff. The `Readings` block exists in
`ReviewPage.tsx` but `source.readings` is empty for 0 of 53 Priest talents
(i.e. never populated), so it never renders.

Suggestion: populate `source.readings` in the pipeline for disagreements and
show the two descriptions with the differing words highlighted; that is the
single most useful thing on the page for a reviewer.

### 15. Review rows repeat the same caveat three times and squeeze the meta column

Severity: **medium**. Evidence: `22-review-row.png` - the rank note "Classic
priest/discipline/Martyrdom (talent 321): ..." appears in the `Ranks` field
and again in both rendered tooltips; the provenance line appears twice. The
grid is `300px / minmax(220px, 1fr) / auto`, so the two 300px tooltips push
the meta column to ~250px of ragged wrapping while the left column sits on a
large empty area below the crop.

Suggestion: drop the caveat and provenance from the two rendered tooltips on
this page (they are already in the meta list), and give the meta column the
`1fr`.

### 16. Mobile wastes ~45% of the width and scrolls 1800px

Severity: **medium**. Evidence: `17-mobile-priest.png`, `18-mobile-priest-full.png`;
at 400px the tree panel is ~340px wide inside a 400px viewport but the grid
itself is ~250px, cells stay pinned at `--cell: 44px` (`talents.css`), and the
three trees stack to `scrollHeight` 1805px.

Suggestion: make `--cell` responsive (e.g. `min(56px, (100vw - 80px) / cols)`)
so the tree fills the width, and offer a tree tab switcher instead of stacking
on narrow screens.

### 17. The header is not sticky

Severity: **medium**. Evidence: `18-mobile-priest-full.png` - by the time you
are spending points in Shadow Magic, "Points left" has scrolled off. Same at
1280px on shorter laptop viewports once notices are shown.

Suggestion: `position: sticky; top: 0` on the class header panel.

### 18. Arrowheads are drawn on top of the talent they point at

Severity: **medium**. Evidence: `04-tree-discipline-zoom.png` - the grey
arrows in Discipline end in a head roughly 21px wide (`markerWidth 7` scaled
by `strokeWidth 3` in `Arrows.tsx`) while the gap between rows is only 12px,
so the head lands on the target icon. Unsatisfied arrows are `#777` on a dark
grid, close to the locked-cell border colour.

Suggestion: shrink the marker (`markerWidth 4`), stop the line 4px short of
the cell, and make the unsatisfied state clearly dimmer/dashed and the
satisfied one gold (the gold state already reads well - `23-full-51.png`).

### 19. Locked talents are doubly darkened and become unreadable

Severity: **medium**. Evidence: `03-priest-1280-fold.png` versus
`23-full-51.png` - `filter: grayscale(1) brightness(0.5)` on locked cells
turns the whole lower two thirds of every tree into identical grey squares.
Combined with finding 1 (no names), a first-time visitor cannot tell what any
deep talent is without hovering each one.

Suggestion: `grayscale(0.7) brightness(0.75)`, and rely on the border colour
for the state distinction.

### 20. The landing page leads with a disclaimer, not with the classes

Severity: **medium**. Evidence: `01-landing-1280.png`, `16-mobile-landing.png`.
Five lines of "read by a local vision model and is unreviewed ..." occupy the
top of the page; on mobile the first class card starts below the first
screenful. The nine cards are visually identical gold-on-dark blocks with no
class colours and no class icons, and each repeats "read from video 0
reviewed".

Suggestion: class grid first with the standard class colours on the name (and
a class icon if one can be cropped), disclaimer condensed to one line with a
"details" link; drop the per-card "0 reviewed".

### 21. The reviewer-facing "review queue (N)" link is on the public landing page

Severity: **medium**. Evidence: `01-landing-1280.png` - every class card
carries a "review queue (9)" link. For a player this is an unexplained
internal route; the review page then talks about
`data/overrides/priest.json`.

Suggestion: keep the route, but link it from a small "data quality" footer
line (or gate it behind `?review=1`) rather than from every class card.

## Low

### 22. "Required level: 1" is shown for an empty build

Severity: **low**. Evidence: `03-priest-1280-fold.png` header at 0 points.
`requiredLevel()` returns 1 for `total <= 0`, but talents start at level 10,
so "1" reads like a wrong rule rather than "no points spent".

Suggestion: show "-" (or "10") at 0 points.

### 23. Keyboard refund is implemented but undocumented

Severity: **low**. Evidence: `TalentCell.tsx` handles `Backspace`, `Delete`
and `-` for removal, and Tab-focus works (`29-keyboard-focus.png`, focus
landed on "Improved Charge, rank 0 of 2" with a white ring), but the help line
under the trees only says "Left click adds a point, right click removes one."

Suggestion: extend that line ("... or Backspace when a talent is focused"),
which also gives touch/trackpad users a documented way to refund.

### 24. No export other than the URL, and no build summary

Severity: **low**. Evidence: `14-copied.png` - "Copy link" works well
(clipboard contained the full URL, button flips to "Copied!" for 2s, and
there is a fallback input when the clipboard is blocked). But there is no
compact talent string to paste into Discord, and nothing lists the talents
actually chosen.

Suggestion: reuse the existing `t=` string as a copyable "build code", and put
a "spent talents" list (name + rank per tree) in the empty right-hand third of
the 1280px layout (finding 25).

### 25. ~390px of the 1280px layout is empty

Severity: **low**. Evidence: `03-priest-1280-fold.png` - the three trees end
at roughly x=840 inside a `max-w-[1200px]` container, leaving a wide empty
column while the trees themselves stay at 44px cells.

Suggestion: use that column for the build summary from finding 24, or the
search results from finding 1; alternatively let `--cell` grow on wide
viewports.

## What works well

Worth keeping as-is: the share-link flow (short `t=` codes, `replaceState` so
the URL is always current, clipboard fallback input), the document title
tracking the split (`Priest 51/0/0 - ...`), "Next rank:" in the tooltip once a
talent has a rank, gold arrows once a prerequisite is satisfied, the accessible
`aria-label` on every cell, and the review row layout (source frame crop beside
the rendered rank-1 and max-rank tooltips) - that last one is genuinely the
right idea and only needs the fixes in findings 12-15.

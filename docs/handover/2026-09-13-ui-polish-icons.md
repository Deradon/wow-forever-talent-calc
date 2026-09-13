# Handover: class icons and the round-one polish pass

Owner feedback on rounds 1a and 1b, three items: class icons for the switcher
chips and the landing cards, a polish pass on what the round-one reviews
flagged (tiny "New in Forever" stars, a dead summary column, small text), and a
consistency pass on the class-level control row. Web only. `pipeline/` and
`data/` belong to another agent and were read, never written - including
`data/icons/SOURCES.md`. Desktop first. Nothing committed.

## 1. The nine class icons

Fetched by hand into `web/public/icons/`:
`https://wow.zamimg.com/images/wow/icons/large/classicon_<class>.jpg` for the
nine Classic classes, one request at a time with a 1 s pause and a descriptive
User-Agent, stopping on 403/429. All nine returned HTTP 200 and 56x56 baseline
JPEG (1.7-2.3 kB each, ~17 kB total, nine distinct checksums; the druid file is
the bear paw, spot-checked).

**`data/icons/SOURCES.md` is the pipeline's file and was not touched.** The
note lives at **`web/public/icons/CLASS-ICONS.md`** instead: what the nine files
are, where they came from, that they are *not* stage 9 output, and a pointer to
the licensing section of `data/icons/SOURCES.md` rather than a second copy of
it.

> For whoever owns stage 9: `09_icons.py match/fetch/apply` must stay free to
> rewrite every talent icon in `web/public/icons/`, and must not delete these
> nine. They have no talent, no crop and no match score, so nothing in
> `matches.json` should ever mention them.

`src/ui/classIcon.ts` is the read side, shared by both call sites: the class
colours (moved out of `ClassSwitcher.tsx`) and `classIconUrl` (`BASE_URL`
prefixed, because Pages serves from `/<repo>/`). `src/ui/ClassIcon.tsx` is the
component next to it - two files only because oxlint's fast-refresh rule wants a
component file to export nothing else - and its `onError` falls back to the
class-coloured two-letter initials the chips used before. So the escape hatch
`data/icons/SOURCES.md` promises still holds: delete `web/public/icons/` and
both places degrade instead of breaking. The example
tinker class has no icon and takes the same path, visibly, in every dev and e2e
build.

**Chips**: 24px crest plus the class name in the class colour, current class
ringed in it as before. The name is hidden below **1320px** - the same step at
which the summary column drops under the trees - because nine names are ~700px
of strip and would push the header to three lines on a laptop; the `title` and
an `sr-only` name carry the class either way, so nothing is lost when the text
goes. **Cards**: a 40px crest left of the name; name, trees and counts as they
were.

One colour decision: Blizzard's shaman blue `#0070de` is **1.8:1** on the chip
background and unreadable as text. `CLASS_TEXT` overrides that one class with
`#3f9bff` (6.0:1) for the label only - the crest ring and the border keep the
real colour. The other eight clear 4.5:1 unchanged. The landing card keeps its
gold class name; class-coloured names there would have put the same problem on
a bigger surface.

## 2. Polish

**The star.** 14px with a 10px glyph read as a blue smudge. It is **18px with a
14px glyph** now, which is the most the cell can give: the padding box of a 44px
cell is 40px and the rank badge owns the bottom 22px of the right-hand edge, so
18 is exactly flush with the badge. The bounding-box case in
`tests/changes.spec.ts` still passes, and it now also asserts a 16px floor, so
the next person to shrink it has to argue with a test. Across the top edge the
star sits beside the 16px `?`: 16 + 18 of 40. The fill stays `#4ea3ff`, the same
blue as the highlight ring and the tooltip's change line - a brighter fill was
tried at 18px and shouted.

**The summary column.** It is `align-self: stretch`, so on an empty build it was
~700px of nothing next to the trees, and it is also the one place a player is
already looking. The empty state now carries the shortcuts: shift-click to max,
ctrl-click to empty and right click for one point, `/` for search and `Esc` to
clear it, `d` for a tooltip's derivation, Ctrl+Z / Ctrl+Shift+Z including for a
Reset, and What's new. `<kbd>` styling in `talents.css`. It is replaced by the
talent list on the first click, so it costs a returning player nothing, and the
lead sentence still starts "No points spent yet." - `ui-round1a.spec.ts` asserts
that string.

**Small text.** Nothing player-facing is below 12px any more. Bumped 11 -> 12px:
the rank badge on every cell, the tier gutter numbers, the tooltip provenance
line, the tooltip derivation body, the two-readings labels. The `?` marker and
its tooltip chip went 15 -> 16px square with a 12px glyph (still clear of the
star: 16 + 18 of 40). Tailwind's `text-xs` is 12px, so the many `text-xs`
utilities were already at the floor and were left alone. The only sub-12px
number left in the sheets is inside `.new-flag`, which is a marker glyph sized
by its box, not text.

## 3. The control row

Search, What's new and Reset all act on the whole class, so they are now one
left-aligned row in exactly that order (`.class-controls` in `talents.css`),
one height (28px) and one style, with the `?` legend holding the right edge.
Before: Reset and What's new sat top-right, Search sat on a line of its own
below, and the toggle was a smaller chip in a third style left over from the
tree panel header it started in.

`HighlightNewToggle` is a `.btn` now; `.new-toggle` in `tiers.css` is down to a
modifier that adds the star and the pressed state, in the marker blue. The
header is a `flex-col` of three rows - identity and counts, the class strip,
the controls - instead of one wrapping row with two `ml-auto` islands.

## 4. Files

Added: `web/src/ui/classIcon.ts`, `web/src/ui/ClassIcon.tsx`,
`web/public/icons/classicon_*.jpg` (9), `web/public/icons/CLASS-ICONS.md`.

Changed: `web/src/ui/Header.tsx` (the control row, the three-row header),
`ClassSwitcher.tsx` (crest plus name), `ClassPicker.tsx` (crest on the card),
`HighlightNewToggle.tsx` (`.btn`), `BuildSummary.tsx` (the empty state),
`talents.css`, `cells.css`, `tiers.css`, `tooltip.css`,
`tests/changes.spec.ts` (the 16px floor).

Not touched: anything under `data/` or `pipeline/`, `rules/`, `url/`,
`TalentCell.tsx`, `TreePanel.tsx`, `Arrows.tsx`, `Tooltip.tsx`.

## 5. Verification

`cd web && npx vitest run && npm run build && npx playwright test` - green:
**237 unit tests in 18 files**, **49 Playwright tests**. Main chunk 392.7 kB raw
/ 120.9 kB gzip; the nine icons are ~17 kB of static files, fetched only for the
chips actually on screen.

Checked at 1500px (`#/` and `#/paladin`, empty and with two points) and at 1200
and 900px for the icon-only chips. Screenshots are in the session scratchpad,
not committed.

One trap worth recording: running `npm run build:e2e` **while** `vite preview`
is already serving `dist/` flipped the hashed asset names under a page the
browser had just loaded, and one e2e case failed on a 404'd chunk. It passed
alone and the whole suite passed on the next run. If a single unrelated case
ever fails right after a rebuild, re-run before believing it.

## 6. Next

- The empty state answers the *empty* column; a two-point build still leaves
  ~350px of it blank. If that matters, the honest fixes are
  `align-self: start` on `.summary-panel` (losing the level bottom edge) or
  idea 11's pinned inspector card, which is meant to live in that gap anyway.
- `.class-chip-name` appears at 1320px. If the header ever grows a fourth
  element, that is the first thing that should go back to icon-only.
- Unchanged from round 1: `Arrows.tsx` should read `--cell` / `--gap`, then the
  `--arrow-scale` rule goes; `#/changes` (idea 13); usability 11, 16/17
  (mobile), 20-22; P-4 to P-8; A-8, A-10, A-12.

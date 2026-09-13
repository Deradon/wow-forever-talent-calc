# Brief: UI and UX improvements (web app)

Status: proposal, 2026-09-13. Written after using the live site
(`https://deradon.github.io/wow-forever-talent-calc/`) as a player at 1440x900
and 390x844, reading `web/src/ui/*`, and comparing against the Classic
calculators listed in section 7. Owner decision 2026-09-13: **desktop first**,
mobile work is deferred (table row 21).

**Scope boundary.** The fixes already scheduled in
`docs/reviews/2026-09-13-consolidated.md` (A1 tooltip text, A2 interaction /
a11y / performance, B data, C CI) are assumed done and are **not** repeated
here. Everything below is additive and is ordered to land *after* or
*alongside* those, with the conflicts called out in section 6.

## 1. What five minutes as a player actually feels like

Confirming and extending the usability review, with fresh screenshots:

- The page uses about half of a 1440px viewport. The three trees end at
  x ~ 935 inside a 1200px container; ~360-400px of the container and the
  entire lower half of the viewport are empty, while the trees stay at 44px
  cells. The floating tooltip then opens *on top of* the neighbouring tree
  because there is nowhere else to go.
- Rows 2-6 of every tree are near-black squares with no names. A newcomer
  cannot read a tree at all without hovering 50 cells one at a time.
- Nothing tells a player what is **new**. This is a Classic+ calculator and
  the single most interesting question ("what changed?") is unanswered, even
  though the data to answer it is already committed (section 5, idea 3).
- Once a build exists there is no artefact to take away except the URL: no
  talent list, no text block for Discord, no way to get a build *in*.
- There is no way to leave a class page except the back link, and no memory
  of what you were building when you return.

A second opinion on the desktop screenshot (Codex) independently flagged the
dead space, the unreadable locked rows, the crude arrows, and the missing
class/build identity in the header as the top quality problems.

## 2. Prioritised table

Effort = hours for a session already inside this codebase, including tests.
"Data/pipeline" says what has to exist outside `web/src` before it can ship.

| # | Idea | Player impact | Effort | Data / pipeline dependency | A1/A2 relation | Round |
|---|------|---------------|--------|----------------------------|----------------|-------|
| 1 | Build summary panel + "Copy as text" + build code | High - the build becomes something you can take away | 4 h | none | Shares the right column with A2.1 search results: agree the layout contract once | 1 |
| 2 | Class switcher in the class header (icon strip + `<select>` fallback) | High - removes the only navigation dead end | 2 h (+1 h for 9 class icons) | Optional: fetch 9 `classicon_*` files via the CDN already used by `09_icons.py` | Independent; reuse in A2.8's build-time class index | 1 |
| 3 | "New in Forever" / changed-vs-Classic markers on cells and in the tooltip | Very high - the reason this site exists rather than Wowhead | 3 h web + 2 h index | Build-time diff of `data/talents/*` against `data/prior/classic-era/talents.json` (already committed) | **Conflicts**: competes with A2.6's `?` badge for a cell corner and with A1's tooltip line budget | 2 |
| 4 | Shift-click = max, Ctrl/Alt-click = clear talent, hold to repeat | High - halves the clicks for a 51-point build | 2 h | none | **Depends** on A2.3 (blocked-action feedback) and A2.4 (handler rewrite): same file, do not edit in parallel | 1 |
| 5 | Wide-desktop layout: bigger cells, equal-height panels, trees + summary as one grid | High - the trees stop looking like a prototype pinned to the upper left | 2.5 h | none | Must be agreed with idea 1 (they share the horizontal budget) | 1 |
| 6 | Tier gutter ("5 / 10 / 15 points"), arrow fix, readable locked cells | Medium-high - the tree becomes legible as a structure | 3 h | none | Arrows and the tier gutter are unclaimed; locked contrast overlaps A2.6 | 1 |
| 7 | Undo / redo (Ctrl+Z), Reset with inline undo, sane Back behaviour | Medium-high - removes the fear of one misclick | 3 h | none | Touches `ClassPage.commit()`; pairs naturally with A2.3's message channel | 1 |
| 8 | Remember the last class and build in `localStorage`, "Continue" card on the landing page | Medium - returning players land where they left | 1.5 h | none | Landing page is edited by A2.8; do after | 1 |
| 9 | Import: paste a link, a build code, or a Wowhead Classic string | High - imports the entire existing Classic build corpus | 5 h | Build-time Classic name index (8 KB from the prior); verify Wowhead's digit order against 2-3 known builds | Independent of A1/A2; does not touch the `t=` codec | 2 |
| 10 | Level slider / "points at level X" | Medium-high for levellers, low for 60 planners | 3 h | `rules.firstPointLevel`, `rules.maxLevel` already in the data | Independent | 2 |
| 11 | Desktop inspector panel (pinned talent card in the right column) | Medium-high - tooltips stop covering the trees | 3 h | none | **Depends** on A1: it renders the same `TooltipContent` | 2 |
| 12 | Per-talent permalink `&sel=<talentId>` | Medium - link a friend to one talent | 1.5 h | none | Needs 11 | 2 |
| 13 | `#/changes` page (talents-only diff, filters, counts) | High news value; durable after datamining | 4 h | Same index as 3; subset of `13_changes` in `docs/briefs/beyond-talents.md` | Independent of A1/A2 | 2 |
| 14 | Keyboard shortcut overlay (`?`) | Medium - makes A2.4's work discoverable | 1.5 h | none | **Depends** on A2.4 | 2 |
| 15 | Print / screenshot view (`?view=print`) | Medium - forum and guide authors | 2.5 h | none | Needs 1 | 2 |
| 16 | Embed mode `#/embed/<class>?v&t` | Low-medium - forums, Discord, the repo README | 2 h | none | Independent | 2 |
| 17 | Class colours and icons on the landing cards | Medium - the landing page stops looking like a table | 1.5 h | Shares the icon fetch with 2 | Edits the same file as A2.8 | 1 |
| 18 | Named local build library ("save this build as Prot 1") | Low-medium | 3 h | none | Needs 8 | later |
| 19 | Compare two builds side by side (`?b=<other>`) | Low | 4 h | none | - | later |
| 20 | Light theme toggle | Low - a Classic skin has one right answer | 3 h | none | Prefer a *compact* toggle instead | not now |
| 21 | Mobile: tree tabs instead of stacking, responsive `--cell`, sticky compact header | High on phones, but **deferred by owner decision 2026-09-13**: desktop players first | 4 h | none | Would depend on A2.5 (tap-to-tooltip); same components | deferred |

Mobile is explicitly out of scope for these two rounds (row 21). The only
mobile-adjacent rule kept in round 1 is negative: nothing below should make
the narrow layout *worse* than it is today, so every new panel stays inside
one `flex-wrap` container and no fixed pixel width above 320px is introduced.

## 3. Top ten, with interaction specs

### 1. Build summary panel with text export

A right-hand column (>= 1100px viewport; below the trees under that) showing
the spent talents grouped by tree, in row order: `Improved Charge 2/2`, each
row hoverable (highlights the cell) and clickable (scrolls to it and pins it
in the inspector, idea 11). Header of the column: `Warrior 31/0/20 - level 60`.
Three buttons: **Copy link** (moves here from the header), **Copy build code**
(the bare `t=` string, e.g. `30250-005-32`, which the import box in idea 9
accepts), and **Copy as text**, which produces a Discord-ready block:

```
Warrior 31/0/20 (level 60) - WoW Forever
Arms (31): Improved Charge 2/2, Deflection 5/5, ...
Protection (20): ...
https://deradon.github.io/wow-forever-talent-calc/#/warrior?v=1&t=30250-005-32
```

Empty state: "No points spent yet. Click a talent to start." No URL or data
implications; pure rendering of the live `Build`. This also finally uses the
dead 360-400px column and is the natural host for A2.1's search results, so
the two should agree on one column layout before either is built.

### 2. Class switcher in the class header

A strip of nine class chips (36px icon or class-coloured initial, class name
on hover) in the class-page header, left of the point counters, with the
current class highlighted; a `<select>` replaces the strip below 700px.
Clicking a class navigates to `#/<class>` - **empty build**, because talent
ids are per class and carrying points across is meaningless. Guard: if the
current build is non-empty, the chip click shows a one-line confirm
("Switch to Shaman? Your Warrior build stays in this link.") with a Copy-link
shortcut, or simply pushes a history entry so Back restores the build; the
second is cheaper and, with idea 7's history policy, sufficient. URL scheme
unchanged (`#/<class>?v=<N>&t=<build>`). Assets: nine `classicon_*.jpg`
files fetched with the same CDN helper as `pipeline/stages/09_icons.py`, into
`web/public/classicons/`; until then, class-coloured initials. The same
assets upgrade the landing cards (idea 17) and any future OG image.

### 3. "New in Forever" and changed-vs-Classic markers

The strongest differentiator, and the data is already in the repo. A
build-time script diffs each `data/talents/<class>.json` against
`data/prior/classic-era/talents.json` by talent name within the class, and
emits `data/changes/talents.json`: per class, per talent, one of
`new | moved | rank-changed | text-changed | same`, plus the Classic
tree/row/col and the Classic rank-1 text where a counterpart exists, plus a
`removed[]` list of Classic talents with no counterpart. Today that yields
**146 new, 131 moved, 18 with a different max rank, 174 unchanged slots and
109 Classic talents gone** across the nine classes (e.g. Warrior gains
Bloodthrill, Weaponmaster, Focused Rage and loses the four weapon
specialisations). In the UI: a small blue star in the cell's **top-right**
corner for `new` (the `?` review badge keeps the top-left - this must be
agreed with A2.6, which is redesigning badge placement), a header toggle
"Highlight what's new" that dims everything else, and exactly one tooltip
line - `New in Forever.` or `Classic: 2/4/6/8/10% -> 1/2/3/4/5%` - which has
to be inside A1's tooltip line budget, not appended after it. The index is
regenerated in CI whenever `data/talents/` changes, and it is a talents-only
down payment on `13_changes` from `docs/briefs/beyond-talents.md`.

### 4. Modifier clicks: shift to max, ctrl to clear

Shift+click adds points until `canAdd` fails, so a 5/5 talent is one click
instead of five; Ctrl+click (and Alt+click, for browsers that hijack Ctrl)
removes points until `canRemove` fails; press-and-hold on a cell repeats the
add every 120ms after a 400ms delay, which is what touch users will try
anyway. All of it must go through the existing verdicts - never a special
case - and the first refusal reuses A2.3's transient message ("Martyrdom
needs 5 points in Discipline") instead of failing silently. Because A2.4
rewrites the same `TalentCell` handler set (`getReferenceProps` pass-through,
Backspace/Delete refund, WAI grid navigation), this must be sequenced after
it, not developed in parallel. Keyboard equivalents: Shift+Enter maxes,
Shift+Backspace clears.

### 5. A wide-desktop layout that fills the page

At 1440x900 the calculator occupies roughly the upper-left half of the
window: three 250-290px panels, 44px cells, ~400px of empty container beside
them and the lower half of the viewport unused. Proposal: one CSS grid on the
class page, `trees | summary`, with the summary column fixed at 320px from
1180px upward and the trees taking the rest; inside the trees, `--cell` grows
with the viewport,
`clamp(44px, (100% - (var(--cols) - 1) * var(--gap)) / var(--cols), 56px)`,
and `--gap` from 12px to 14px above 1400px, so a 4-column tree renders at
56px cells - close to the in-game frame and a far easier click target. The
three tree panels get `align-items: stretch` so they share one height instead
of ending at three different y positions, and the tree headline becomes
`Arms 31` with the count in gold, large enough to read from the header. No
data or URL implications; it is the cheapest change with the largest effect
on perceived quality, and it has to be designed together with idea 1 because
the two divide the same horizontal budget.

### 6. Tier gutter, honest arrows, readable locked cells

Three small skin changes that make a tree readable at a glance. (a) A 28px
gutter left of each grid with the row requirement (`5`, `10`, `15`, ...),
dim until the row is unlocked, gold on the first locked row - the player sees
*why* the bottom of the tree is dark. (b) Arrows: `markerWidth` 4 instead of
7, the line stopping 5px short of the target cell, unsatisfied arrows dashed
`#5a5f70`, satisfied solid gold, and the SVG kept under the cells
(`z-index`) so an arrowhead never lands on an icon. (c) Locked cells go from
`grayscale(1) brightness(.5)` to `grayscale(.75) brightness(.72)`, letting
the border carry the state; combined with A2.1's visible names on hover this
turns the lower two thirds of every tree back into content.

### 7. Undo, redo, and a Back button that behaves

Every edit currently uses `replaceState`, so Back leaves the calculator and
Reset silently destroys a 51-point build. Proposal: keep `replaceState` for
the hash (links stay live), and hold an in-memory undo stack of `Build`
snapshots (cap 50). `Ctrl+Z` / `Ctrl+Shift+Z` (and small Undo/Redo buttons in
the summary column) walk it; Reset pushes one entry and shows "Build reset -
Undo" for 8 seconds where the Reset button was. Additionally, on first edit
of a session push one history entry so a single Back leaves the page *once*,
predictably, rather than from wherever the 30th click left the hash. No URL
scheme change.

### 8. Remember the last build

On every commit, write `wft.last = {classId, v, t, savedAt}` to
`localStorage` (best-effort, wrapped in try/catch). The URL stays the source
of truth: storage is only read when the hash is bare `#/`, where the landing
page then shows a "Continue: Warrior 31/0/20" card above the class grid, with
a small "forget" link. Never redirect automatically - a shared link or a
bookmark must always win. Two-line diff in `ClassPage` plus a card in the
picker; do it after A2.8 rebuilds that page.

### 9. Import a build

A small "Import" button next to Copy link opens a textarea that accepts, in
this order: (a) a full URL of this site (parse the hash, navigate), (b) a
bare build code `30250-005-32` with the current class assumed and a class
picker if ambiguous, (c) a Wowhead-style Classic string
(`.../classic/talent-calc/warrior/30350100...`), which is decoded against the
Classic prior's per-tab, row-major talent order, mapped Classic talent ->
Forever talent **by name within the class** (204 of 469 talents match
exactly), then sanitized. The result panel is the interesting part: "37 of 41
points placed. Dropped: Sword Specialization (not in Forever), Improved
Battle Shout (not in Forever). 4 points left to spend." That single flow
converts every existing Classic build link on the internet into a Forever
build and is the best possible showcase for idea 3. Data: the 8 KB per-class
name index derived from the prior at build time. Risk: Wowhead's digit order
must be confirmed against two or three known builds before shipping; if it
does not match, keep (a) and (b) and drop (c). Nothing here touches our own
encoding, so it is unaffected by the encoding-freeze decision.

### 10. Inspector panel and per-talent permalinks

At >= 1100px, hovering a cell fills a pinned card at the top of the summary
column instead of floating over a neighbouring tree (the floating tooltip
stays for narrow viewports and for touch). Clicking the cell's name in the
summary, or arriving with `&sel=<talentId>` in the hash, *pins* that card
until dismissed and outlines the cell; the parameter is written on pin and
removed on dismiss, is independent of `t=`, and is ignored by the codec, so
`#/warrior?v=1&t=30250-005-32&sel=focused-rage` is a link to "this build, look
at this talent". The card is the same `TooltipContent` A1 rewrites - so build
it after A1 lands, and keep exactly one renderer of talent text, used by the
tooltip, the inspector, the print view and the review page.

## 4. Two implementation rounds

**Round 1 - "a calculator you can use and leave with" (~2 days).** Order
matters because of the file overlaps in section 6:

1. Idea 4 (modifier clicks) - immediately after A2.3/A2.4 land, same files.
2. Idea 6 (tier gutter, arrows, locked contrast) - pure skin, parallelisable.
3. Idea 1 (summary column + exports) - defines the right-column layout that
   A2.1's search results then slot into.
4. Idea 2 + 17 (class switcher, class colours/icons, one icon fetch).
5. Idea 7 (undo/redo, Reset safety, history policy).
6. Idea 5 (wide-desktop grid and cell sizing) - last, so it absorbs the
   final widths of the summary column and the tier gutter.
7. Idea 8 (localStorage continue) - after A2.8's landing rebuild.

Mobile (row 21) is deferred by owner decision and is not part of either
round.

**Round 2 - "the Classic+ angle" (~2.5 days).**

1. The changes index (build-time diff + CI regeneration).
2. Idea 3 (markers, filter, one tooltip line) - coordinate the badge slot
   with A2.6 *before* A2.6 ships.
3. Idea 13 (`#/changes` page) on the same index.
4. Idea 9 (import, including the Wowhead path).
5. Ideas 11 + 12 (inspector panel, `&sel=` permalinks) - after A1.
6. Idea 10 (level slider), then 14, 15, 16 (shortcut overlay, print view,
   embed mode) as time allows.

## 5. URL scheme summary after both rounds

```
#/                                  class picker (+ "continue" card)
#/<class>?v=<N>&t=<build>           unchanged, canonical
      &sel=<talentId>               pinned talent, ignored by the codec
      &lvl=<10..60>                 only written when below rules.maxLevel
#/embed/<class>?v=<N>&t=<build>     chromeless, fixed 960px, link back
#/changes  #/changes/<class>        Classic diff
#/review/<class>                    unchanged
```

All additions are optional query parameters or new routes; `t=` and its
version semantics are untouched, so none of this interacts with the
"encoding v1 stays mutable until launch, then freeze" decision.

## 6. Conflicts and dependencies with the A1/A2 work in flight

- **A1 (tooltip text)**: ideas 3 and 11 both render talent text. The
  "New in Forever" line must be part of A1's line budget from the start, and
  the inspector must reuse `TooltipContent` rather than fork it.
- **A2.1 (search)**: idea 1 occupies the same right-hand column. Build the
  column once, with a slot for search results.
- **A2.3 / A2.4 (feedback, keyboard)**: idea 4 extends exactly the handlers
  A2.4 rewrites and needs A2.3's message channel for refusals. Strictly
  sequential.
- **A2.5 (touch)**: unaffected while mobile is deferred; if row 21 is ever
  picked up, its tab layout and A2.5's tap-to-tooltip work touch the same
  components and belong in one session.
- **A2.6 (badges, legend, contrast)**: idea 3 adds a second badge. Agree
  "review `?` top-left, new-star top-right, one shared legend" before A2.6
  is implemented, or the badge work gets done twice.
- **A2.7 (crop icon inset)**: no conflict; it silently improves every idea
  here, especially the class strip and the summary list.
- **A2.8 (build-time class index)**: ideas 2, 8 and 17 extend the same
  generated index (class colour, icon, "N new talents"). One generator.
- **`docs/briefs/beyond-talents.md`**: ideas 3 and 13 are a talents-only
  subset of stage `13_changes` and `#/changes`. Build the index with the same
  entry shape so the spell and racial data can be merged in later without a
  second UI.

## 7. What the reference calculators do (checked 2026-09-13)

Wowhead Classic (`wowhead.com/classic/talent-calc/<class>`) and wowtbc.gg
both give a class dropdown, per-tree "0/X" rank counters, per-tree totals, a
global points-remaining counter, a global Reset and a per-tree Reset, and a
Share button that writes the build into the URL. Shift-click-to-max and
right-click-to-remove are longstanding Wowhead conventions (not verifiable by
fetch, both are JS-rendered SPAs). Wowhead's retail calculator added explicit
**Import and Export** of loadout strings, so a build round-trips between game
and browser - the pattern idea 9 copies. `wowisclassic.com` was the one page
that rendered fully: it switches class with a **strip of nine class icons**,
shows `Warrior 0/0/0`, `Remaining points: 51` and `Level required: -` (note:
a dash at zero points, which is also usability finding 22), has Copy link
plus social sharing, and offers a library of rated builds. A Turtle WoW
community planner (west-games.com) goes further with a level input, a points
budget display, capstone validators and a **Print** button. Nobody in this
set has a "what changed versus Classic" view - which is exactly the gap idea
3 fills, and the one thing a Classic+ audience cannot get anywhere else.

## 8. Deliberately not doing

- Light theme (a Classic skin has one right answer; offer a compact density
  toggle instead if the trees feel cramped).
- Build comparison view and a shared build library (server-side or
  login-gated; out of scope for a static site).
- Real in-game tree background art cropped from the footage: licensing risk
  and pipeline cost out of proportion to a stylised backdrop plus the tier
  gutter from idea 6.
- Simulation, gear or DPS scoring of any kind.

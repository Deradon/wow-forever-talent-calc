# Handover: the Classic Era diff, round 2 - moves, rewrites and value changes

Round 1 shipped in `docs/handover/2026-09-13-ui-round1b.md`. The owner reported
that priest **Shadowform** said *"Moved from Shadow, row 7"* although it has
always sat in row 7 of the Shadow tree, and that the same false claim appeared
all over the priest and shaman trees. What actually changed about Shadowform is
the description.

Web only. Nothing under `data/` or `pipeline/` was touched; `data/` was read.

Verified green: `cd web && npx vitest run` (281 tests, 18 files), `npm run build`
(type-check included), `npx playwright test` (51 tests). Nothing committed.

## 1. Why the false moves happened

Three suspects were checked; only one was guilty.

- **Renamed trees - guilty.** Forever renamed two of the twenty-seven trees:
  priest `shadow` "Shadow" -> `shadow-magic` "Shadow Magic", and shaman
  `elemental` "Elemental" -> `elemental-combat` "Elemental Combat". Round 1
  compared the raw tree ids, so all 33 talents of those two trees differed in
  `tree` and were classified `moved`. Nine of them had not moved at all; the
  other 24 had really shifted row or column, but their line named the wrong
  reason ("Moved from Shadow, ...") instead of the row.
- **Row base - innocent.** Both sides are 0-based (`min(row) == 0` for every
  tree on both sides). Guarded anyway: `cellBase` rebases each side on its own
  origin so a future 1-based prior cannot invent 470 moves. Only an exact
  minimum of 1 counts as a 1-based origin - a minimum of 2 is a sparse tree, not
  a convention.
- **Wider Forever trees - innocent.** Both sides use columns 0-3 (some Forever
  trees only reach column 2, which is a narrower tree, not a shifted one).

**The fix.** `matchTrees` in `web/scripts/gen-data-index.mjs` maps Classic trees
onto Forever trees before any cell is compared: same id, else same name after
`normalizeName`, else the majority of talents matching by name (greedy on the
strongest overlap, so a tree that traded one talent with its neighbour cannot
steal the neighbour's identity). Talent matching uses the mapping too, so the
"same tree first" pass now actually finds the priest Shadow counterparts.

A talent is `moved` only when the mapped tree differs or `(row, col)` differs.
`prior.movedTree` is set **only** for a genuine change of tree, and that is what
`changeLine` asks before naming the old tree. `prior.tree` stays the Classic id
(`"shadow"`), which is not a Forever tree id - never compare the two.

There are exactly **eight** genuine cross-tree moves in the game, pinned by name
in the tests: druid Insect Swarm and Natural Shapeshifter, rogue Improved Gouge
and Improved Eviscerate, shaman Earth's Grasp, warrior Improved Slam, Iron Will
and Improved Thunder Clap. Round 1 reported 41.

## 2. The two new categories

Both descriptions are rendered at **rank 1** - Classic from the prior's
`ranks[0]`, Forever from the `{n}` template filled with `ranks[0]` - and compared
through `normalizeText`: lower case, one spelling per unit (`sec`/`seconds`,
`min`, `yd`, `percent` -> `%`), no punctuation that is not part of a number,
single spaces. What survives that is a real change:

- **`values-changed`** when the sentences mask to the same shape
  (`maskNumbers`: every `15%`/`1.5`/`30` becomes `#`) - only the numbers moved.
  The entry lists `[was, now]` per slot, in order, for the slots that differ.
- **`text-changed`** otherwise - a rewrite.

Precedence, worst news first: `new > moved > rank-changed > text-changed >
values-changed > same`. The entry still carries everything the losing categories
would have said, so the card can be richer than the line.

The word diff is `compactDiff`, `[op, text]` runs with `=` keep, `-` Classic
only, `+` Forever only, computed on the **raw** sentences so a player reads real
words - the normaliser decides, it does not render.

### Counts, before and after

| | new | moved | rank-changed | text-changed | values-changed | same | gone |
|---|---:|---:|---:|---:|---:|---:|---:|
| round 1 | 145 | 132 | 18 | - | - | 174 | 108 |
| round 2 | 145 | **123** | 18 | **111** | **16** | **56** | 108 |

Nine false moves are gone; the 174 "unchanged" turn out to be 127 talents whose
text Forever changed and 56 that are genuinely identical. Per class the counts
are in `src/data/classic-diff.json` under `classes.<id>.counts`; warrior leads
the rewrites with 25, shaman has no pure value change at all.

## 3. Two files, because the text is bulky

`generate()` now writes four files. The diff became two:

| | raw | gzip | when |
|---|---:|---:|---|
| `src/data/classic-diff.json` | 112.3 kB | 8.9 kB | class route (was 72 kB / 6.6 kB) |
| `src/data/classic-text.json` | 82.4 kB | 17.0 kB | on demand |

`classic-text.json` holds the Classic sentence, its per-rank values and the word
diff for the 238 talents that have one. It is fetched with a dynamic `import()`
the first time a player opens a card - the same deal the 971-entry crop registry
gets - so it is its own chunk and the class route pays nothing for it. The main
chunk went 120.8 -> 123.6 kB gzip, which is the richer diff plus the card.

What stays in the light file is what the **line** needs: the status, the Classic
cell, and the value pairs (a single pair is always spelled out on the line, so
the card deliberately does not repeat it).

## 4. The tooltip

The one change line is precise now: `New in Forever.` / `Moved from row 5.` /
`Moved from Arms, row 3.` (only for a real cross-tree move) / `Now 3 ranks,
was 5.` / `Reworked.` / `Values changed: 15% -> 20%.`

It is still exactly one line and still inside the card's budget:
`CHANGE_MAX = 60` mirrors `TRUST_MAX`, and a talent whose every number moved
(mage Pyroblast changed three) collapses to `Values changed: 148 -> 155 and 2
more.` rather than wrapping. The meta budget rule (`fitsBudget`) is untouched.

When the Classic sentence differs at all - whatever the headline status is - the
line becomes a **term** and opens a nested card with the same mechanics as the
others (dwell, `safePolygon`, tap, one nest per card, rendered inside the parent
tooltip's DOM). The card shows `IN CLASSIC ERA`, the Classic rank-1 sentence with
the diff drawn into it (dropped words struck in red, added words marked green on
a faint plate - the plate is there because colour alone is not a difference every
player sees), then `Classic values by rank: 8/16/25.` and, for two or more value
pairs, the full list.

Files: `web/src/ui/Tooltip.tsx` (the term and `ClassicTip`),
`web/src/ui/tooltipText.ts` (`changeLine`, `valuesChangedLine`,
`changeCardTitle`, `classicSeriesLine`, `changeCardLines`),
`web/src/ui/classicDiff.ts` (the read side plus the lazy loader), and a new
`web/src/ui/diff.css`, imported from `Tooltip.tsx`.

### One request to the owner of `cells.css` / `TalentCell.tsx`

`diff.css` temporarily carries four lines that belong next to their siblings in
`cells.css` - the highlight ring for the two new statuses. The selectors match
the ones there exactly, so it is a cut and paste:

```css
.cell[data-highlight='true'][data-change='text-changed'],
.cell[data-highlight='true'][data-change='values-changed'] {
  box-shadow: 0 0 0 2px rgba(78, 163, 255, 0.3);
}
```

**No marker variant was added to `TalentCell`.** `data-change` already carries
`text-changed` and `values-changed` with no change needed there. If a "reworked"
marker is wanted later, the proposal is: reuse the top-right slot the star owns,
same 18px box, the glyph `~` instead of `★`, and the muted blue `#2f6ca8`
instead of `#4ea3ff` - a talent that is *new* must stay the louder of the two.
That needs one line in `TalentCell.tsx` (`isNew` becomes a small
`markerFor(change)`) and one rule in `cells.css`; nothing in the diff data.

## 5. `diffWords` is deliberately duplicated

The build script needs the same word diff the review route uses, but it is plain
ESM run by node and cannot import TypeScript. The obvious fix - one copy in
`web/scripts/diffWords.mjs`, re-exported from `src/ui/review.ts` - was built,
measured and **reverted**: importing a `.mjs` from app code makes rolldown split
its CommonJS-interop helpers into a separate `rolldown-runtime` chunk that
`index.html` then modulepreloads, which breaks `tests/landing.spec.ts` ("the
entry chunk only") and costs every first load a request. `src/ui/review.ts` is
therefore back to HEAD, untouched, and `src/data/classicDiff.test.ts` asserts
that the two implementations agree run for run.

## 6. Tests

`src/data/classicDiff.test.ts` (56 cases, was 22). New: `normalizeText` /
`maskNumbers` / `compareDescriptions`, `matchTrees` (id, name, majority, and the
neighbour that must not be stolen), `cellBase`, `rankSeries`, the renamed-tree
case in both `classifyTalent` and `diffClass`, a true move beside it, a
values-changed case, the eight cross-tree moves pinned by name, the freshness of
both generated files, the drift guard against `src/ui/review.ts`, and the
invariant that every stored diff still rebuilds the sentence it describes.

`src/ui/tooltipText.test.ts`: the six change lines, the collapse at `CHANGE_MAX`,
and the card's lines.

`tests/changes.spec.ts`: two new cases - Shadowform is `text-changed`, carries no
star, says `Reworked.`, and its card shows the struck and marked Classic wording
including the Holy-spell clause Forever dropped; and priest Shadow Affinity says
`Values changed: 8% -> 10%.` with `Classic values by rank: 8/16/25.` in the card.
One existing assertion changed: the highlight switch probed a `same` talent in
paladin Retribution, and Retribution no longer has one, so it probes a
`text-changed` cell instead.

Screenshots at 1280x800 in the session scratchpad
(`test-results/classic-diff-card.png`, `...-values.png`), not committed.

## 7. Next

- `#/changes` page (brief idea 13): `removed[]` is still unread, and the text
  index now gives that page the "what it used to say" column for free.
- The four CSS lines and the optional "reworked" marker, above.
- The normaliser is deliberately conservative. If a class file ever renders a
  rank as a whole sentence rather than a `{n}` template, `rankSeries` returns
  nothing and the card simply omits the Classic series line - it never guesses.
- Still open from the earlier reviews: usability 11, 16/17 (mobile, deferred),
  20-22; P-4 to P-8; A-8, A-10, A-12.

# Handover: `#/spells` (Phase 2d web half)

Date 2026-09-13. Owner of this session: `web/` only. Nothing under `data/` or
`pipeline/` was touched; `data/spells/` and `data/review/spells/` were read,
never written. The spec is section 5 of
`docs/handover/2026-09-13-spells-data.md`, the scope is its section 6
recommendation ("build it, but scope it as spells seen on stream"), and where
this page had to choose, those decided.

Verified green: `cd web && npx vitest run` (523 tests, 25 files), `npm run build`
(type-check included), `npx playwright test` (76 tests, 6 of them new). Nothing
committed.

## 1. The two routes

`#/spells` and `#/spells/<class>`, one lazily loaded component
(`web/src/ui/SpellsPage.tsx`) with its own chunk (14.6 kB raw / 4.6 kB gzip)
and its own stylesheet (`spells.css`) - the arrangement `#/races` has.

- **`#/spells`** is the coverage overview: one card per class that has a
  spellbook file, with the entries seen, how many of them have full text, a
  `N new` chip, the tabs that were opened and - in amber - the tab pages nobody
  opened. It runs off the generated `spells-index.json` alone, so it fetches no
  spell file and no crop. Under the cards, one line: *"Priest never appeared in
  the footage, so there is no priest page."*
- **`#/spells/<class>`** is one class's book: the class crest, the level chip, a
  link into that class's calculator, then the coverage sentence, the trust line,
  the caveats, then the entries grouped by tab exactly as the spellbook groups
  them. A row is icon crop, name, the ranks that were on screen, the kind when
  it is not a plain active spell, a `New` chip, and - only when the spell was
  hovered - a native `<details>` disclosure holding the verbatim tooltip.

The coverage sentence is the header, not a footnote, because the data handover's
rule 1 is the whole reason this page is allowed to exist:

> Spells seen on stream: 41 entries across Balance, Feral Combat, Restoration;
> 27 with full text. The General page was not shown.

A single-tab class reads *"10 entries on the General page; none with full
text. The Affliction, Demonology and Destruction pages were not shown."* That
is the warlock, and it is the case the page was designed around: 10 rows
presented as a spell list would be a lie about the game.

Linked from the site header (`Changes · Races · Spells`) and from the landing
page in one line under the races line.

## 2. The rules from section 5, and where each one lives

All of them are in `web/src/ui/spellsModel.ts`, pure and unit tested
(`spellsModel.test.ts`, 23 cases run against the **real** files rather than a
fixture - the page's job is to describe a coverage record honestly, and a
fixture would let the honest wording drift away from the data):

1. **Coverage record, not a spell list.** `coverageLine` names the tabs that
   were read and the pages that were not; `levelLine` states the level bound;
   the overview repeats both shapes per card (`cardCountLine`, `cardGapLine`).
2. **Every entry is unreviewed.** `spellTrustLines` states it once for the page
   ("Read from BlizzCon 2026 footage; not yet reviewed. 1 of 45 entries is
   uncertain and marked below."), and the 10 rows below the review threshold
   carry the talent tooltip's own short amber line through `trustLine` in
   `trust.ts` - so a shaky spell and a shaky talent say the same words.
3. **`ranksSeen` is what was on screen.** `rankLabel` prints `Rank 4` or
   `Ranks 1, 2, 3, 4` and never a range; a corpus test asserts no label ever
   matches `\d-\d`. `ranksLine` says which of the two cases the page is in,
   from `coverage.showAllSpellRanks`.
4. **A tooltip without a rank says so**: "One rank; which one was not on
   screen." 89 of 112 are in that state.
5. Entries render in file order inside a tab, which is the page's own
   alphabetical order; groups render in `tabs[].order`.
6. Icons are crops, rendered directly, with the shared `initials` fallback
   (`web/src/ui/initials.ts`, now used by the talent grid's neighbours, the
   racial cards and the spell rows).
7. **`classic.status` is name-level only.** The `New` chip therefore carries
   exactly one caveat, at the top of the page: *"New means the name is missing
   from our Classic Era list, which was written from memory and never checked.
   It is a hint, not a finding."* Never a repeat per row.
8. A spell with no `tab` goes into a final group named **Seen only in a
   search** (14 entries, mostly the paladin's Blessings), never into an
   invented tab.

Two deliberate departures, both wording:

- **`notes[]` is filtered, not printed.** The races page prints every note; the
  spellbook's are written for the data owner and name repo paths, field names
  and the reader. `playerNotes` keeps only what a player can use - today
  exactly one note per class, the build date - and the caveats the dropped ones
  carried are stated by the page in its own words. A unit test asserts nothing
  that survives the filter carries pipeline vocabulary, and a Playwright case
  asserts the same over the rendered page for `vlm`, `reader`, `confidence`,
  `codex`, `stage `, `pipeline`, `.json` and `.py`.
- **The tooltip `footer` is not rendered.** It is always "You haven't added this
  to your action bars", which is a fact about the streamer's action bars, not
  about the spell.

A row with no tooltip shows nothing extra - no disclosure, no "no text". 215 of
327 rows are in that state, and a placeholder on each would be the loudest thing
on the page.

## 3. The 14 MB problem, and what was done about it

`data/review/spells/` is 765 files and 14 MB - more than everything else under
`data/review/` put together. Two things had to be true: the spell crops must
reach no chunk but the spells route, and the spells route itself must not carry
all eight classes' worth.

- **`crops.ts` no longer globs them.** Its pattern was
  `data/review/*/*/*.png`, which matches `data/review/spells/<class>/*.png` -
  so the review route was already shipping 765 spell crop URLs it never renders.
  The glob is now `['../../../data/review/*/*/*.png', '!../../../data/review/spells/**']`
  and the review chunk went from **141.4 kB to 63.0 kB** (29.9 -> 14.5 kB gzip).
- **One generated crop module per class.** `scripts/gen-data-index.mjs` writes
  `src/data/spellCrops/spells-<class>.ts`, and `src/data/spellCrop.ts` reaches
  them through a **lazy** `import.meta.glob`, so each is its own chunk
  (0.9-9.2 kB) and `#/spells/mage` downloads the mage's crop URLs and nobody
  else's. The overview downloads none.
- **Only the crops the page uses.** `collectSpellCrops` takes the icon crop of
  every entry and the frame behind every tooltip - 434 of the 765. The row crops
  are not collected, because a row without a tooltip has no disclosure and
  therefore nothing linking them. `dist/` fell from 38 MB to 30 MB as a result.

`tests/landing.spec.ts` now also fails on a `SpellsPage` or `spells-` chunk on
the landing path, and `tests/spells.spec.ts` asserts that `#/spells` loads zero
crop chunks and `#/spells/mage` exactly one, named `spells-mage-*`. The landing
budget of four scripts is unchanged: the fifth lazy route added no shared chunk.

## 4. Generated files and the loader

`scripts/gen-data-index.mjs` gained a spells half, regenerated on every dev
server, build and vitest run, asserted fresh by `generated.test.ts`:

- **`src/data/spells-index.json`** (~4 kB): per class the counts (entries, rows
  with full text, tooltips, new names, search-only rows), the tabs with their
  entry counts, `tabsMissing`, the level and the rank-option state - plus
  **`absent`**, the classes with no spellbook file at all. That list is how the
  overview knows about priest; the page never guesses it.
- **`src/data/spellCrops/spells-<class>.ts`**: 434 `?url` imports over eight
  modules. `generate()` also deletes an orphaned module, because the lazy glob
  would otherwise keep serving a class whose data file is gone.

`src/data/spells.ts` is the loader (lazy `import.meta.glob` over
`data/spells/*.json`, zod behind `import.meta.env.DEV` as `load.ts` and
`races.ts` do). `hasSpells('priest')` is false, and the class page answers with
*"Priest's spellbook was never on screen, so there is nothing to show."* plus a
link back - not an unknown-route panel.

## 5. Tests

- `src/data/validateSpells.test.ts` (58): the Zod mirror
  (`spells.zod.ts`, mirroring `data/schema/spell.schema.json`) over all eight
  files, plus the rules a JSON Schema cannot state - unique slug ids, tab orders
  without gaps, every `tab` known, a tab-less row explaining itself,
  `coverage.entriesRead`/`tooltipsRead` agreeing with the arrays they describe,
  a tab never both seen and missing, `complete: false`, several ranks on a row
  only with the option on, a Classic note on every entry, `new` implying the
  tag, and every crop the page renders or links being shipped. An independent
  second implementation of `pipeline/validate_spells.py`'s contract, on purpose.
  One finding worth keeping: `source.confidence` **0.0 is a real value** (only
  one reading pass saw the row); four entries have it.
- `src/ui/spellsModel.test.ts` (23): the overview cards and their three lines,
  the priest line in both the one-class and many-class shape, the three
  coverage-sentence shapes, the level and rank sentences, grouping by tab and
  the search group last, the empty-tab case, rank labels including the
  no-range corpus check, the 16 new names, the kind labels, `hasText` over the
  corpus, the tooltip facts and the two rank lines, the reading line without a
  reader name or "100%", the three trust sentences, the 10 shaky rows, and the
  note filter over all eight files.
- `src/data/generated.test.ts`: both generated artefacts fresh, the index
  agreeing with every spellbook file (counts, tabs, gaps, level), one crop
  module per class holding only that class's crops, and - the load-bearing one -
  `cropUrl()` returning `undefined` for a spell crop, which is the review
  registry proving it dropped them.
- `src/url/route.test.ts`: `#/spells`, `#/spells/<class>`, the rejected
  non-slug and two-segment forms, and the round trip.
- `tests/spells.spec.ts` (6): the overview counts, gaps, the priest line and the
  card link; the coverage sentence and the tab groups on a class page plus the
  link into the calculator; the disclosure opening to the verbatim tooltip with
  its cost line and the unanchored-rank sentence, the New chip with its single
  caveat, and a hovered-never row carrying no disclosure at all; the priest
  answer; the chunk budget and the no-pipeline-words sweep; the header and
  landing entry points.

Screenshots at 1440x900 in the session scratchpad (overview, mage, mage with a
tooltip open, warlock), not committed.

## 6. Next

- **Review.** All 327 entries and 112 tooltips are unreviewed and there is still
  no overrides mechanism for spells (data handover section 7.1). The page says
  so once per class; it will keep saying so until `source.reviewed` moves.
- **The Classic prior.** Replacing `spells-baseline.json` with a sourced list
  *with text* turns 311 `unknown` verdicts into real ones and would let the New
  caveat shrink to one clause. Nothing in `web/` changes; the index regenerates
  and `priorVerified` flips.
- **Cross-links.** `data/spells/*.json` now gives the web app 327 spell names.
  The talent-tooltip cross-link (`spellLinks.ts` in the data handover section 5)
  is still worth building, and still should wait for the review round.
- **Spell icons.** 325 rows render a 40 px crop. Pointing stage 9's icon matcher
  at them would replace most with clean Classic icon files and cut the crop
  modules to the genuinely new ones.
- **A nit:** the class list is a CSS grid, so opening a long tooltip stretches
  its whole grid row and leaves whitespace beside it. Acceptable on desktop;
  a multi-column layout would fix it at the cost of reflowing on every toggle.
- **Mobile** is untuned here as it is for `#/races`: the rows drop to one column
  below 900 px and nothing else was done.

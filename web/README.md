# web/ - WoW Forever talent calculator

Static Vite + React + TypeScript app that renders `data/talents/<class>.json`
with Classic-style talent trees, point rules and shareable build links. Brief:
`docs/briefs/web-app.md`; data contract: `docs/DATA-SCHEMA.md`.

## Commands (run inside `web/`)

| Command | What |
|---|---|
| `npm install` | Install (Node 22+). |
| `npm run dev` | Dev server on http://localhost:5173 with the example classes included (`.env.development`). |
| `npm run build` | Type-check and build to `dist/`. Set `VITE_BASE=/<repo>/` for GitHub Pages, `VITE_INCLUDE_EXAMPLES=1` to ship `data/examples/`. |
| `npm run build:e2e` | Production build that includes the example classes (`.env.e2e`). |
| `npm run preview` | Serve `dist/` on http://localhost:4173. |
| `npm test` | Vitest: rules engine table (points and levels), codec, routing, Zod-vs-JSON-Schema, `validate-data`, crop registry, review ordering, the Classic diff, the `#/changes` model, the race files against a Zod mirror and the `#/races` model, the spellbook files against their own Zod mirror and the `#/spells` model. |
| `npm run e2e` | Playwright: `tests/smoke.spec.ts` (example class) and `tests/paladin.spec.ts` (real data: crop icons, titles, manual ranks, review route). Builds with `build:e2e`, then `preview`. First time: `npx playwright install chromium`. |
| `npm run lint` | oxlint. |

CI (`.github/workflows/deploy.yml`, job `check`) runs `npm ci`, `npx vitest
run`, `npx playwright install --with-deps chromium` and `npm run e2e`
alongside the pipeline tests and the data validator; the deploy job waits on
it. The Playwright step is `continue-on-error` until the suite has proven
stable on CI runners.

## Layout

- `src/data/` - `schema.ts` (Zod mirror of the JSON Schema; unknown keys pass through), `load.ts` (class files via `import.meta.glob`; `data/talents/` always, `data/examples/` and `tests/fixtures/` when `VITE_INCLUDE_EXAMPLES=1`), `encoding.ts` (encoding versions and migrations). Races are the same arrangement one folder over: `schema.races.ts` and `races.zod.ts` mirror `docs/DATA-SCHEMA-RACES.md`, `races.ts` loads `data/races/<race>.json` lazily, `raceCrop.ts` resolves the racial icon and row crops. Spellbooks are the same arrangement again: `schema.spells.ts` and `spells.zod.ts` mirror `data/schema/spell.schema.json`, `spells.ts` loads `data/spells/<class>.json` lazily, and `spellCrop.ts` reaches the generated per-class crop modules in `spellCrops/` - one lazy chunk each, because the spellbook crops are 14 MB and no other route may carry them.
- `src/rules/` - pure rules engine (`points`, `level`, `validate`, `mutate`); no DOM.
- `src/url/` - `codec.ts` (Wowhead-style tree strings) and `route.ts` (hash routing).
- `src/ui/` - React components and `talents.css` (the skin), plus `print.css` (the print view), `changes.css` (the `#/changes` page), `races.css` (the `#/races` pages) and `spells.css` (the `#/spells` pages). `changesModel.ts` is the pure model behind `#/changes`, `racesModel.ts` the one behind `#/races`, `spellsModel.ts` the one behind `#/spells`, `classicDiff.ts` the read side of the generated Classic diff, `trust.ts` the trust line and the internal-id guard every one of them shares.
- `tests/` - Playwright smoke test and JSON fixtures.

## Routes

- `#/` class picker
- `#/<class>?v=<dataVersion>&t=<tree strings>` calculator; `#/<class>` is an empty build
- `#/changes` what changed against Classic Era: per-class counts; `#/changes/<class>` lists them in six sections (new, moved, rank count changed, reworked with the word diff, values changed, gone from Classic) with a filter box
- `#/races` the race/class matrix: one row per playable identity (the two Skyborne variants are separate rows), one column per class, the combinations Classic Era did not allow ringed in gold; `#/races/<race>` its racial traits as cards with the icon crop, the kind, the vs-Classic verdict and the frame behind Details. `?variant=<id>` picks the Skyborne variant.
- `#/spells` what each class's spellbook showed on stream: one card per class with the entries seen, how many have full text, and the tab pages nobody opened (priest was never on screen and is named as absent); `#/spells/<class>` the entries grouped by tab, each row with its icon crop, the ranks that were on screen and a New chip when the Classic Era name list has no such name, and a disclosure with the verbatim tooltip for the spells that were hovered
- `#/about` what the site is, how the data was made and what to distrust, in three paragraphs; linked from the footer of every page
- `#/review/<class>` review queue: every talent, worst reading first (unreviewed below 80% confidence, then other unreviewed, then reviewed), with the frame crop, icon crop, provenance and the rendered tooltip at rank 1 and max rank. It writes nothing: "Copy override" and "Copy all flagged" put a `data/overrides/<class>.json` entry on the clipboard (`overrideEntry.ts`, canonical key order and formatting mirrored from `pipeline/validate.py`), and "Report on GitHub" opens the wrong-reading issue form with the class and the record prefilled.

Two optional parameters ride along on the class route. Both are view state: the
build codec ignores them, so they never change what `t=` means.

- `&sel=<talentId>` opens that talent's tooltip pinned (interactive, its nested
  cards reachable) and focuses the cell, switching page first if the talent is
  on another page of the class. Dismissing the card - Escape, a press on its own
  background, hovering another cell - drops the parameter from the hash again.
  Every row of `#/changes/<class>` is such a link.
- `&embed=1` is embed mode, below.

## Embed mode

`#/<class>?v=<N>&t=<build>&embed=1` renders the calculator without any site
chrome: no site header, no class header, no summary column, no footer, no
shortcut overlay. What is left is a one-line header (`Paladin 31/0/20`, the
points and the required level, and an "Open the full calculator" link that
leaves the iframe), the page tabs and the trees, which take the full width.

It is still the whole calculator: points can be spent, and `embed=1` survives
every edit, so the iframe keeps working as one. The link out is the only route
to the caveats and the data provenance, which is why it is always there.

```html
<iframe
  src="https://deradon.github.io/wow-forever-talent-calc/#/paladin?v=1&t=...&embed=1"
  width="960" height="760" style="border:0" title="Paladin talent build"></iframe>
```

`height` has to hold the deepest tree: about 700 px at the default 44 px cells,
more if the class has page tabs. The page never scrolls the iframe horizontally
above 960 px.

## Printing

`@media print` in `src/ui/print.css` is the whole print view - there is no
`?view=print` route. It drops every control, the navigation and the tooltips,
puts the trees on white at 34 px cells, sets the summary list in three columns
and prints the build URL under the title. The **Print** button in the summary
column calls `window.print()`; Ctrl+P from anywhere does the same.

## Icons and crops

Talents with `iconSource: "crop"` render their `iconCrop` PNG from `data/review/<class>/<tree>/`; all other talents try `public/icons/<icon>.jpg` (fetched by the pipeline, M2+) and fall back to initials. `src/data/crops.ts` globs `data/review/*/*/*.png` eagerly as URLs (the PNGs are copied to `dist/assets/`, never base64-inlined; see `vite.config.ts`). `src/data/crops.test.ts` fails when a class file points at a crop that is not shipped.

Left click adds a point, right click (or Backspace) removes one. The full set
of keys and modifier clicks is in the app itself: press `?`, or the `?` button
in the site header (`src/ui/ShortcutsOverlay.tsx`).

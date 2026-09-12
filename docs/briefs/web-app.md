# Brief: web app (`web/`) — WoW Forever talent calculator

Implementation brief for a fresh session. Read `CLAUDE.md`,
`docs/research/2026-09-13-web-architecture.md` and
`docs/research/2026-09-13-talent-system.md` first. Versions and config were
verified on 2026-09-13 against the linked docs unless marked *unverified*.

## 1. Objective and milestones

Static Classic-style talent calculator rendering `data/talents/<class>.json`
with point rules and shareable Wowhead-compatible links, on GitHub Pages at
`https://<user>.github.io/<repo>/`. MIT.

**M1 — one class, deployed.** Accept when: `npm run build` emits `web/dist/`;
the first extracted class renders all its trees; clicking spends/refunds
points under the rules in §4; header shows points left, required level,
per-tree counts; "Copy link" yields a URL that reloads to the same build;
`vitest` engine tests and the `validate-data` test pass; one Playwright smoke
test passes on `vite preview`; the Actions workflow deploys on push to `main`.

**M2 — all classes.** Class picker; every JSON in `data/talents/` loads
through Zod; hover tooltip shows current rank text and "Next rank:"; icons
served from `web/public/icons/` (no zamimg hotlinks); `#/review/<class>`
route lists talents by ascending confidence with frame crop beside tooltip.

**M3 — polish.** Skin finished (§6), keyboard/touch, "Export for addon"
(the tree string), per-class `<title>`/OG tags via prerendered per-class
`index.html` copies, non-affiliation footer.

## 2. Scaffold (run from repo root)

```bash
npm create vite@latest web -- --template react-ts   # Vite 8, React 19, TS ~6.0
cd web && npm install
npm install tailwindcss @tailwindcss/vite            # Tailwind 4.3
npm install zod @floating-ui/react                   # zod 4.6, floating-ui 0.27
npm install -D vitest fast-check @playwright/test    # vitest 5.0, fast-check 4, playwright 1.63
npx playwright install --with-deps chromium
```

Sources: <https://vite.dev/guide/> (command; Node 20.19+/22.12+),
<https://tailwindcss.com/docs/installation/using-vite>,
<https://vitest.dev/guide/> (needs Vite ≥ 6.4, Node ≥ 22.12),
<https://playwright.dev/docs/intro>. Keep the template's `typescript: ~6.0`
(npm `latest` is 7.x, the Go compiler; do not upgrade in M1). Skip
`npm init playwright` (interactive); write `playwright.config.ts` by hand with
`webServer: { command: 'npm run preview', url: 'http://localhost:4173' }`.
Add scripts `"test": "vitest run"` and `"e2e": "playwright test"`.

`web/vite.config.ts`:

```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({
  base: process.env.VITE_BASE ?? '/',        // CI sets '/<repo>/'; custom domain later: '/'
  plugins: [react(), tailwindcss()],
  server: { fs: { allow: ['..'] } },          // data/ lives outside web/
  test: { include: ['src/**/*.test.ts'] },
})
```

`base` per <https://vite.dev/guide/static-deploy> ("project repository" case);
`server.fs.allow` per <https://vite.dev/config/server-options>. Use
`import.meta.env.BASE_URL` for any hand-built asset URL.

**Routing: hash routing** (`#/warrior?v=3&t=30502-05-3`). One `index.html`;
no 404-copy trick (HTTP 404 status, redirect flicker, breaks when a custom
domain changes the base) and no reliance on Pages' trailing-slash redirects
keeping query strings. Cost: no per-route OG tags, which static hosting cannot
do per build anyway. No router library: `parseHash()` plus a `hashchange`
listener.

`.github/workflows/deploy.yml` — action majors verified via GitHub releases
(checkout v7, setup-node v7, configure-pages v6, upload-pages-artifact v5,
deploy-pages v5; Vite's guide pins the same majors by SHA):

```yaml
name: Deploy to Pages
on: { push: { branches: [main] }, workflow_dispatch: }
permissions: { contents: read, pages: write, id-token: write }
concurrency: { group: pages, cancel-in-progress: true }
jobs:
  deploy:
    environment: { name: github-pages, url: ${{ steps.deployment.outputs.page_url }} }
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with: { node-version: 22, cache: npm, cache-dependency-path: web/package-lock.json }
      - run: npm ci
        working-directory: web
      - run: npx vitest run && npm run build
        working-directory: web
        env: { VITE_BASE: /${{ github.event.repository.name }}/ }
      - uses: actions/configure-pages@v6
      - uses: actions/upload-pages-artifact@v5
        with: { path: web/dist }
      - id: deployment
        uses: actions/deploy-pages@v5
```

Repo setting: Pages → Source "GitHub Actions". Playwright runs in a
separate, non-blocking job later.

## 3. Folder structure and module boundaries

```
web/
  public/icons/<icon>.jpg        fetched by pipeline/fetch_icons.py (M2)
  src/
    main.tsx, App.tsx            hash route -> ClassPage | ReviewPage | ClassPicker
    data/
      schema.ts                  Zod schema + TS types (mirror of data/schema/class.schema.json)
      load.ts                    import.meta.glob('../../../data/talents/*.json') lazy per class
      encoding.ts                loads data/encoding/v{N}.json (+ migrations)
    rules/                       PURE. No DOM, no React. 100% unit tested.
      types.ts  points.ts  validate.ts  mutate.ts  level.ts
    url/
      codec.ts                   encode/decode tree strings
      route.ts                   parseHash/buildHash
    ui/
      ClassPage.tsx  PageTabs.tsx  TreePanel.tsx  TalentCell.tsx  Arrows.tsx
      Tooltip.tsx  Header.tsx  ClassPicker.tsx  ReviewPage.tsx  Notice.tsx
      talents.css                the skin (grid, borders, tooltip)
  tests/smoke.spec.ts            Playwright
```

**Zod types.** `z.fromJSONSchema()` is experimental in zod 4
(<https://zod.dev/json-schema>), so hand-write `schema.ts` and add a Vitest
asserting `z.toJSONSchema(ClassSchema)` matches `data/schema/class.schema.json`
on required keys and enums. Types: `ClassData`, `Tree`, `Talent`, `Rules`.
`description` is a template with `{n}` slots filled from `ranks[r]` (which may
be a full string). Unknown keys pass through so the data lead can add fields
freely.

**Rules API** (`Build = Record<treeId, Record<talentId, number>>`):

```ts
pointsInTree(b, treeId): number
pointsInRowsAbove(tree, b, row): number      // rows < row
totalPoints(b): number
requiredLevel(total, rules): number          // total===0 ? 1 : firstPointLevel-1+total
canAdd(cls, b, treeId, talentId): Verdict    // {ok:true} | {ok:false, reason: Reason}
canRemove(cls, b, treeId, talentId): Verdict
add / remove(cls, b, treeId, talentId): Build   // no-op copy when verdict fails
validate(cls, b): Violation[]                // {treeId, talentId, reason}
sanitize(cls, b): { build: Build; dropped: Violation[] }
resetTree(b, treeId): Build;  resetAll(): Build
```

## 4. Rules engine

All thresholds come from `cls.rules`, never constants. Add when rank <
maxRank, `totalPoints < maxPoints`, `pointsInRowsAbove >= pointsPerRow * row`,
and each entry of the `requires` array (see `docs/DATA-SCHEMA.md`) is met. Remove when rank > 0 and
`validate(remove(...))` is empty — simulate, do not special-case. `capstone`
is display-only until the data lead says otherwise. Points count across all
trees and pages. `sanitize` walks trees in encoding order, rows top-down,
dropping ranks until `validate` is empty; the UI shows a "build adjusted"
notice.

| # | Case | Expect |
|---|------|--------|
| 1 | Empty build, row-0 talent | canAdd ok; level 1 → 10 after first point |
| 2 | 4 points in row 0, row-1 talent | reject `row-locked`; 5th point unlocks |
| 3 | Points only in tree A, row-1 of tree B | reject (rows count per tree) |
| 4 | rank == maxRank | reject `maxed` |
| 5 | totalPoints == maxPoints | reject `no-points` everywhere |
| 6 | requires 5/5 prereq at 4/5 | reject `prereq`; ok at 5/5 |
| 7 | Chain A→B→C, remove from A | canRemove false while B > 0 |
| 8 | Remove point from row 0 leaving row 1 with fewer than 5 above | reject `would-orphan` |
| 9 | Remove point where rows above still ≥ threshold | ok |
| 10 | Two paths to same row total, remove one | ok if threshold still met |
| 11 | Capstone with 0 points above | reject `row-locked` |
| 12 | sanitize: row 2 points without row 0/1 | drops row 2, reports violation |
| 13 | decode: digit > maxRank | clamp to maxRank, report |
| 14 | decode: more digits than talents | ignore extras, report `unknown-talent` |
| 15 | decode: unknown data version | empty build, notice `unknown-version` |
| 16 | decode: older version with renamed id in migrations | mapped, no notice |
| 17 | encode(decode(s)) == s for valid s | property test (fast-check) |
| 18 | random click sequences never violate | property test |

## 5. URL codec and review route

Format: one decimal digit per talent (so `maxRank ≤ 9`, asserted by the
schema test) in the order given by `data/encoding/v{N}.json`; trailing zeros
trimmed per tree; trees joined by `-`; trailing empty trees omitted.

```
#/warrior?v=3&t=30502-05-3    tree1 "30502", tree2 "05", tree3 "3"
#/warrior?v=3&t=--3           only tree3 has points
#/warrior                     empty build, current version
```

`data/encoding/v3.json`: `{ "version": 3, "classes": { "warrior": { "arms":
["improved-heroic-strike", …], "fury": […] } } }`; tree order = key order.
Migrations live under `data/encoding/migrations/` as specified in
`docs/DATA-SCHEMA.md` section 8 (authoritative; the shape there wins).
Decode: order for `v` → digits to ids → migrations up to current version →
`sanitize` → notice if anything dropped. Encode always writes the current
`dataVersion`. Wowhead-compatible while the first three trees match Wowhead's
order (still Classic placeholder data; revisit after beta).

**Review route** `#/review/<class>`: rows sorted by `source.confidence`
ascending, `confidence < 0.8 && !reviewed` first. Each row shows the crop
`data/review/<class>/<tree>/<talentId>.png` (via `import.meta.glob('../../../data/
review/*/*/*.png', { query: '?url', import: 'default' })`, lazy) beside the
rendered `Tooltip` at rank 1 and max rank, plus id, row/col, frame. Crops ship
in the production build (~10 MB for 432 talents; gate behind `VITE_REVIEW` if
that grows).

## 6. Styling

Tailwind for layout; `talents.css` for the skin. Each tree is a CSS grid
(columns = max `col`+1, rows = max `row`+1, `--cell: 44px`, gap 12px) over a
darkened `tree.background` image. Arrows: one absolutely positioned `<svg>`
per tree; `Arrows.tsx` draws a polyline from prerequisite cell to dependent
cell (straight or L-shaped as in Classic), gold when satisfied, grey
otherwise.

Cell states (border + icon filter + rank badge):

- **available** — green border, full-colour icon, badge `0/3` green text
- **partial** — green border, full colour, badge `1/3`
- **maxed** — gold border, full colour, badge `3/3` gold
- **locked** — grey border, `filter: grayscale(1) brightness(.5)`, badge grey;
  tooltip adds a red "Requires N points in Row/Talent" line

Tooltip: dark navy panel, 1px gold-brown border, white name, "Rank x/y",
yellow-white description, "Next rank:" block, red requirement line;
positioned with `@floating-ui/react` (`flip`, `shift`). Pages: a tab strip
(`Primary | Secondary`) appears only when a class has more than one page;
trees within a page sit side by side and wrap under 900px.

## 7. Risks and open questions (data lead)

1. **Total points / points per row / first-point level** — unknown (51/5/10
   assumed). App reads `cls.rules`; never hard-code.
2. **Tab semantics** — is "Secondary" a second page of trees, a second
   point pool, or a second spec? Needs a `trees[].page` field (or a `pages[]`
   array) in the schema. Until answered, all trees are one page and one pool.
3. **Capstone rule** — display only, or a "must have N in tree" gate? Add
   `rules.capstoneGate` when known.
4. **Global vs per-class `dataVersion`** — answered in `docs/DATA-SCHEMA.md`
   section 8: encoding files are global and immutable once merged; the
   validator enforces that every class is present in its version's file.
5. **`maxRank > 9`** would break one-digit encoding; schema should cap it.
6. **Icon licensing** — icons and crops are Blizzard property; keep the
   non-affiliation footer and be ready to pull `data/review` from the build.
7. Beta datamining (2026-09-17) may replace OCR data wholesale; the app only
   depends on the JSON contract, so this is a data-only change.

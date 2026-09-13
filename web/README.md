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
| `npm test` | Vitest: rules engine table, codec, routing, Zod-vs-JSON-Schema, `validate-data`, crop registry, review ordering. |
| `npm run e2e` | Playwright: `tests/smoke.spec.ts` (example class) and `tests/paladin.spec.ts` (real data: crop icons, titles, manual ranks, review route). Builds with `build:e2e`, then `preview`. First time: `npx playwright install chromium`. |
| `npm run lint` | oxlint. |

## Layout

- `src/data/` - `schema.ts` (Zod mirror of the JSON Schema; unknown keys pass through), `load.ts` (class files via `import.meta.glob`; `data/talents/` always, `data/examples/` and `tests/fixtures/` when `VITE_INCLUDE_EXAMPLES=1`), `encoding.ts` (encoding versions and migrations).
- `src/rules/` - pure rules engine (`points`, `level`, `validate`, `mutate`); no DOM.
- `src/url/` - `codec.ts` (Wowhead-style tree strings) and `route.ts` (hash routing).
- `src/ui/` - React components and `talents.css` (the skin).
- `tests/` - Playwright smoke test and JSON fixtures.

## Routes

- `#/` class picker
- `#/<class>?v=<dataVersion>&t=<tree strings>` calculator; `#/<class>` is an empty build
- `#/review/<class>` review queue: every talent, worst reading first (unreviewed below 80% confidence, then other unreviewed, then reviewed), with the frame crop, icon crop, provenance and the rendered tooltip at rank 1 and max rank. Read-only.

## Icons and crops

Talents with `iconSource: "crop"` render their `iconCrop` PNG from `data/review/<class>/<tree>/`; all other talents try `public/icons/<icon>.jpg` (fetched by the pipeline, M2+) and fall back to initials. `src/data/crops.ts` globs `data/review/*/*/*.png` eagerly as URLs (the PNGs are copied to `dist/assets/`, never base64-inlined; see `vite.config.ts`). `src/data/crops.test.ts` fails when a class file points at a crop that is not shipped.

Left click adds a point, right click (or Backspace) removes one.

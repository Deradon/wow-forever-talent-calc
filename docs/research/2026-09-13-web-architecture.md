# Research: talent calculator web architecture (2026-09-13)

Role: senior frontend architect (sub-agent). Decisions taken afterwards:
Vite + React + TypeScript, **GitHub Pages** (not Cloudflare), MIT.

## Recommendations (TL;DR)

- Stack: Vite + React 19 + TypeScript, Tailwind v4, Zod-validated JSON data,
  Vitest for the rules engine, one Playwright smoke test. No router library;
  class in the path (or hash) and build in a query param.
- Layout: monorepo `pipeline/` (Python, uv), `data/` (canonical JSON + JSON
  Schema + versioned encoding orders), `web/` (Vite app), `docs/`. `data/` is
  the contract between the halves.
- Sharing: Wowhead-compatible one-digit-per-talent tree strings
  (`30502...-...-...`) plus a data-version segment; talent order per version is
  frozen in `data/encoding/v{N}.json`, with migration maps so old links keep
  working after OCR corrections.
- Timing: beta opens 2026-09-17. OCR data is a stopgap; design the pipeline
  so a beta-client dump (addon export or wago.tools DB2 export) replaces it.

## 1. Tech stack

Vite + React + TS over Svelte or plain TS: AI assistants produce the most
reliable React code (the maintenance model here); SvelteKit/Next add a
server-side mental model that a static site does not need; plain TS gets
tedious for tooltips, arrows and derived state. Keep React thin: all game
logic in `web/src/engine/` as pure functions; one `useReducer` per class page.
No Zustand/Redux. Tailwind for layout plus one small `talents.css` for the
tree skin. Tests: Vitest on the engine, a `validate-data` test that loads every
class JSON through the schema, one Playwright test (open a class, spend 51
points, assert the URL round-trips).

## 2. Data model

JSON Schema (`data/schema/class.schema.json`), language neutral so Python
(`jsonschema`) and the web (`zod`) validate the same file. One file per class.
IDs are stable slugs, never grid positions.

```json
{
  "class": "warrior", "dataVersion": 3,
  "rules": { "pointsPerRow": 5, "maxPoints": 51, "firstPointLevel": 10 },
  "trees": [{
    "id": "arms", "name": "Arms", "background": "arms",
    "talents": [
      { "id": "improved-heroic-strike", "name": "Improved Heroic Strike",
        "row": 0, "col": 0, "maxRank": 3, "icon": "ability_rogue_ambush",
        "description": "Reduces the cost of your Heroic Strike ability by {0} rage point(s).",
        "ranks": [[1],[2],[3]],
        "source": { "video": "DxtVEhjyROU", "frame": 18420, "t": "03:41:12", "confidence": 0.91, "reviewed": true } },
      { "id": "mortal-strike", "name": "Mortal Strike", "row": 6, "col": 1, "maxRank": 1,
        "icon": "ability_warrior_savageblow", "capstone": true,
        "requires": { "talent": "tactical-mastery", "points": 5 },
        "description": "A vicious strike that deals weapon damage plus {0} and wounds the target...",
        "ranks": [[85]], "source": { "frame": 19110, "confidence": 0.88, "reviewed": true } }
    ]
  }]
}
```

`description` is a template with `{n}` slots and `ranks[r]` supplies per-rank
values; if a talent's text changes shape per rank, `ranks[r]` may be a full
string. Row gating is a class-level rule. `requires` is an object (allow a
future array). `source` is optional so hand-entered talents are legal;
`confidence < 0.8 && !reviewed` is what the review UI queues.

## 3. Rules engine (pure functions)

State: `Build = Record<treeId, Record<talentId, rank>>`.
- `pointsInTree`, `pointsInRowsAbove`, `totalPoints`.
- `requiredLevel(total) = total === 0 ? 1 : firstPointLevel - 1 + total`.
- `canAdd`: rank < maxRank, total < maxPoints, `pointsInRowsAbove >=
  pointsPerRow * row`, prerequisite rank >= `requires.points`.
- `canRemove`: rank > 0 and `validateTree(remove(build, id))` is empty.
  Simulate-and-revalidate beats special-casing.
- `validateTree` returns `Violation[]`; also sanitises decoded URLs (drop
  points top-down on violation and show a "build adjusted" notice).
Tests: table-driven Vitest cases plus a property test (fast-check).

## 4. Build sharing

Wowhead format: one decimal digit per talent, fixed order per tree, trailing
zeros trimmed, trees joined by `-`. Freeze the order in
`data/encoding/v3.json`; URL `/warrior?v=3&t=30502-05-3`. Decoder loads the
order for `v`, maps digits to IDs, re-validates against current data.
Migrations only for renamed IDs.

## 5. UI

- Each tree is a CSS grid, 4 columns x 7 rows, `--cell: 44px`. Arrows are one
  absolutely positioned SVG per tree computed from `(row, col)` of both ends.
- Tooltip: `@floating-ui/react` or a positioned div; name, rank x/y, current
  rank text, "Next rank:" text, red requirement line while gated.
- Header: points remaining, required level, per-tree counts (also in the page
  title), Reset tree / Reset all, Copy link, "Export for addon" (Wowhead
  string; TalentPlanner addon imports that).
- Icons: `https://wow.zamimg.com/images/wow/icons/{small|medium|large}/{icon}.jpg`
  is the de facto source. Do not hotlink in production: a fetch script
  downloads referenced icons into `web/public/icons/`. New Forever talents get
  64x64 crops from the source frame with `iconSource: "crop"`.

## 6. Repo layout and review workflow

```
pipeline/   uv project: stage scripts, validate.py, fetch_icons.py
data/       classes/*.json, schema/, encoding/v*.json, migrations/, review/ (frame crops)
web/        Vite app; src/engine, src/data (generated types), src/ui, public/icons
docs/       plans, briefs, decisions, research
.github/    ci.yml: validate data -> vitest -> build -> deploy
```
The pipeline writes candidate JSON once and never overwrites a talent with
`reviewed: true`; corrections are manual edits. The review UI is a hidden
route in the app (`/review/warrior`) listing talents by ascending confidence
with the frame crop beside the rendered tooltip.

## 7. Deployment

GitHub Pages (chosen): deploy with Actions; deep links need hash routing or
the `404.html` copy trick; soft bandwidth limit 100 GB/month. Avoid
"worldofwarcraft" or "blizzard" in any domain; footer non-affiliation line.

## 8. Projects worth reading (mostly unlicensed: borrow ideas, not code)

- https://github.com/maladr0it/classic-talent-calculator (TS, CSS grid, URL state)
- https://github.com/melv-n/wow-talent-calculator (React + TS)
- https://github.com/ddfilipov/vanilla-wow-talent-calculator (Next.js)
- https://github.com/iamadagostino/wow-classic-talent-calculator (Vue)
- https://github.com/mikeacjones/TalentPlanner (Lua addon, MIT, imports Wowhead strings)
- https://github.com/Znuff/wow_icons (icon extraction scripts)
- Wowhead Classic calc URL shape: https://www.wowhead.com/classic/talent-calc

# WoW Forever Talent Calculator

Talent calculator for **World of Warcraft: Forever** (Classic+, announced at
BlizzCon 2026-09-12). Two halves: a data-extraction pipeline that turns
gameplay video into talent JSON, and a static web app that renders it.
Live: https://deradon.github.io/wow-forever-talent-calc/

## State (2026-09-13)

All nine classes published, 469 of 470 talents (mage Fire r1c3 was never
hovered on stream). Everything is **unreviewed**: 0 talents have
`source.reviewed: true`, 77 sit below the 0.8 confidence threshold, plus 21
low-confidence prerequisite arrows. A full review round landed in
`docs/reviews/` on 2026-09-13; `docs/reviews/2026-09-13-consolidated.md`
ranks the findings and assigns the work packages. Next: owner review via
`#/review/<class>`, then Phase 2b (races). History: `docs/PLAN.md`.

## Layout

- `pipeline/` – Python (uv). Stages `00, 03, 04, 04b, 05..09, 11, 12` in
  `pipeline/stages/` (the numbering has gaps; there is no stage 1, 2, 10 or 13;
  11 is the spellbook and 12 the races, both independent of 3-9), shared code
  in `pipeline/src/wowtalents/`, one-off scripts in `pipeline/scripts/`, the
  standalone validators `validate.py`, `validate_races.py` and
  `validate_spells.py`, tests in `pipeline/tests/`. Large artefacts stay under
  `pipeline/work/` (git-ignored).
- `data/` – `talents/<class>.json` canonical, `extracted/` raw pipeline
  output, `overrides/` hand corrections, `review/` tooltip and icon crops,
  `encoding/` build-link orders, `prior/classic-era/` the Classic prior,
  `schema/` (`class`, `race`, `race-matrix`, `spell`), `examples/` the
  fictional tinker class, plus the non-talent datasets `races/` and `spells/`.
- `web/` – Static calculator, no backend. `src/rules/` pure rules,
  `src/url/` build-link codec and hash routing, `src/data/` schema, loading
  and encoding registry, `src/ui/` React, `tests/` Playwright.
- `docs/` – `PLAN.md` (read first), `DATA-SCHEMA.md` (normative for `data/`),
  `briefs/`, `decisions/`, `reviews/`, `handover/` (indexed in
  `docs/handover/README.md`).
- There is no `tools/` directory. The review UI is the `#/review/<class>`
  route in the web app; icon matching is `pipeline/stages/09_icons.py`.

## Data contract

- Source of truth is `data/talents/*.json`. `docs/DATA-SCHEMA.md` is
  normative; `data/schema/class.schema.json` and `web/src/data/schema.ts`
  mirror it. Where a brief disagrees, the schema wins.
- Run the validator before committing any data change, from `pipeline/`:
  `uv run python validate.py --check ../data/talents/*.json`
  (about a second, must exit 0). CI runs the same command, plus
  `validate_races.py --check ../data/races/*.json` and
  `validate_spells.py --check ../data/spells/*.json` for the two non-talent
  datasets.
- Every talent record keeps `source` (video id, timestamp, frame path,
  confidence). Data corrected by hand keeps `source.reviewed: true`.
- The pipeline owns `data/extracted/`, `data/review/`, `data/icons/` and
  `web/public/icons/`. It writes `data/talents/` only through
  `08_export.py promote`, which never overwrites a `reviewed: true` record.
  Never hand-edit `data/extracted/`.
- Pure rules (point allocation, row gating, prerequisites) live in
  `web/src/rules/`, the build-link codec and hash routing in `web/src/url/`.
  No DOM access in either.
- The web app must stay deployable as static files (GitHub/Cloudflare Pages).

## Encoding freeze

`data/encoding/v<N>.json` fixes the digit position of every talent in a
build link. Each file carries a `frozen` flag:

- `frozen: false` (v1 today, pre-launch): the order may still be regenerated
  in place. Shared links can shift; that is the accepted cost until launch.
- `frozen: true`: the file is immutable. Any change to the set or order of
  talent ids then needs a new `v<N+1>.json` covering every class, a
  `migrations/v<N>-v<N+1>.json`, and `dataVersion` bumped in every class
  file. `08_export.py --update-encoding` refuses to touch a frozen file and
  creates the next version instead.

Freeze v1 when launch is declared. A published version that is silently
rewritten breaks every shared build link — it has happened once already
(`docs/reviews/2026-09-13-code-and-docs.md`, finding A1).

## Commands

```bash
# web (in web/)
npm test          # vitest
npm run build     # tsc -b && vite build
npm run e2e       # playwright; once: npx playwright install chromium

# pipeline (in pipeline/)
uv run pytest
uv run python validate.py --check ../data/talents/*.json
uv run stages/08_export.py --help

# from the repo root, prefix with --directory (globs must then be absolute):
uv run --directory pipeline pytest
```

Stage by stage: `pipeline/README.md`. Web details: `web/README.md`.

## Decisions (see docs/decisions/)

- Local Qwen3-VL via llama.cpp reads tooltip text; no cloud APIs. OpenCV
  owns all positional work.
- Vite + React + TypeScript, Tailwind, Vitest. GitHub Pages hosting, so the
  app needs a base path and hash/query routing. MIT license.
- Source window in the stream: 03:00:00 to 06:20:00. Only rank-0 tooltips
  exist; higher ranks are anticipated from Classic Era scaling and marked via
  `ranksSource`.

## Commits and privacy

- Public repository. No real names, e-mail addresses, home paths, hostnames
  or hardware readouts in tracked files. Commit author identity is the
  owner's normal git identity and is fine.
- Commit messages: a `Co-Authored-By` line for Claude is fine; never add a
  `Claude-Session:` line or any claude.ai session URL. A local commit-msg
  hook rejects them.
- Docs in English. Keep the status log in `docs/PLAN.md` current when a phase
  finishes; write a handover to `docs/handover/` and add its line to
  `docs/handover/README.md`.

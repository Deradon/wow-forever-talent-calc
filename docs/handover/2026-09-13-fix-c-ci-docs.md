# Handover: review package C — CI, CLAUDE.md, docs (2026-09-13)

Work package C of `docs/reviews/2026-09-13-consolidated.md`, items 1-5.
Scope: `.github/workflows/`, `CLAUDE.md`, `README.md`, `docs/PLAN.md`,
`docs/DATA-SCHEMA.md`, `docs/handover/README.md`, `pipeline/README.md`,
`web/README.md` (README prose only). No code and no data was touched;
packages A1, A2 and B were being worked in parallel by other sessions.
Nothing committed.

## What changed

| File | Change |
|---|---|
| `.github/workflows/deploy.yml` | New `check` job: `uv sync --frozen`, `uv run pytest`, `validate.py --check ../data/talents/*.json`, `npm ci`, `npx vitest run`, `npx playwright install --with-deps chromium`, `npm run e2e`. `deploy` now has `needs: check` and is otherwise unchanged apart from the dangling `VITE_INCLUDE_EXAMPLES` comment (C5), which the web M2 handover had already flagged. Action majors pinned as before (`checkout@v7`, `setup-node@v7`, `configure-pages@v6`, `upload-pages-artifact@v5`, `deploy-pages@v5`) plus `astral-sh/setup-uv@v5`. |
| `CLAUDE.md` | Rewritten, 56 -> 114 lines: state, real layout, data contract, encoding freeze, commands, decisions, privacy. Removes the three false statements (a `tools/` directory, URL encoding in `web/src/rules/`, "the pipeline never writes outside `data/extracted/`") and the dead pointer to a command list the root README did not have. |
| `docs/DATA-SCHEMA.md` | The five D3 contradictions fixed; `iconSource` value table; `requires.rank` semantics spelled out; `unset` documented (6.2); `frozen` documented (8, rule 11); section 9 marked planned; section 7 now describes the read-only review route and the manual override step. |
| `docs/PLAN.md` | New "Immediate next actions" (review packages, owner review of the queue, freeze the encoding at launch, phase 2b-2d, DB2 importer) and new "Open questions". Status log untouched; the "fast path while the download runs" section marked historical. |
| `docs/handover/README.md` | Index of all 14 handovers, chronological (commit order), one line each; the template rules above it stay. |
| `README.md` | "bootstrapping" -> live/unreviewed status, real command block, links to the two sub-READMEs, the schema and `CLAUDE.md`. |
| `pipeline/README.md` | `uv run --directory pipeline ...` note at the top; tests section now also documents `validate.py` and the CI job; `data/overrides/<class>.json`, `data/icons/verified.json` and `work/icons/` marked optional or git-ignored. |
| `web/README.md` | One paragraph on what the CI `check` job runs. |

## Verification (commands run at the end, read-only)

| Command | Result |
|---|---|
| `uv run --directory pipeline pytest -q` | 171 passed, 4.6 s |
| `cd pipeline && uv run python validate.py --check ../data/talents/*.json` | exit 0, 0 errors across all nine classes (warnings and NEW-TALENT infos only) |
| `cd pipeline && uv run stages/08_export.py --help` | exit 0, lists `extract` / `promote` / `all` as documented |
| `cd web && npx vitest run` | 8 files, 85 tests passed, 2.3 s |
| `cd web && npm run lint` | 4 React warnings, no errors |
| `cd web && npm run build` | **fails** on `tsc -b`, see below |

`npm run build` fails with nine TypeScript errors in files the A2 session was
editing while this ran (`scripts/gen-data-index.mjs` has no declaration,
`src/data/schema.zod` does not export `ClassData`/`Talent`, `TreePanel` is
called without seven of its new props, implicit `any` in three tests). These
are in-progress web changes, not a docs or CI defect, and were left alone by
design. Re-run `npm run build` once that session lands; the `check` job and
the deploy job both depend on it passing.

Playwright was not run here (it needs a browser download and a preview
server). Its step is `continue-on-error: true` in the `check` job on the
review's own advice (B2): the suite has never run on a CI runner, and
`paladin.spec.ts:23` asserts no talent falls back to initials, which now
depends on 312 JPEGs decoding under `vite preview`. Remove the flag after a
few green runs.

## Documented ahead of the code

Two things are described as agreed, not as shipped. Both were the owner's
decision in the consolidated review; the B session owns the implementation.

- **`unset` in overrides** (`DATA-SCHEMA.md` 6.2): `"unset": ["requires"]`,
  optional fields only, dotted names for `source` sub-fields, applied before
  `set`. As of this writing `pipeline/src/wowtalents/export.py` still handles
  only `set`/`rename`/`delete`/`add`. If the implementation picks a different
  spelling, the schema section is the thing to correct.
- **`frozen` in encoding files** (`DATA-SCHEMA.md` 8, `CLAUDE.md`): not yet a
  field in `data/encoding/v1.json`, and `validate.py` does not check it. The
  rule as written: at most one version file (the newest) may be unfrozen, v1
  stays unfrozen until launch is declared, `--update-encoding` refuses a
  frozen file and creates `v<N+1>` instead.

`data/encoding/README.md` still has the stale "Current state" paragraph from
finding D4 (it claims v1 holds only the tinker example; it holds all nine
real classes). It sits under `data/`, which another session owned, so it was
left untouched — it is a two-line fix for whoever takes `data/` next, plus
the same correction in `v1.json`'s own `note` field.

## Next

1. Re-run `npm run build` and then the whole `check` job once the web and
   pipeline sessions land; that is the first real test of the workflow.
2. Land `unset` and `frozen`, then re-read the two sections above.
3. Freeze `v1` when launch is declared (`docs/PLAN.md`, next action 3).

# Handover: rank anticipation and export (data side), 2026-09-13

Scope: stage 6 (`ranks`) and stage 8 (`export`) of `docs/briefs/pipeline.md`,
implementing brief `data-prior-and-review.md` section (b) and
`docs/DATA-SCHEMA.md` sections 4-6. Nothing committed; `pipeline/work/`,
stages 03/04 and `pyproject.toml` untouched. Once stage 5 writes
`data/extracted/<class>.candidates.json`, a class file is produced by
`uv run stages/08_export.py all <class> --update-encoding`.

## What exists

| Path | What |
|---|---|
| `pipeline/src/wowtalents/ranks.py` | `Prior` (loads `data/prior/classic-era/talents.json`), `match_classic` (exact name in class -> `token_ratio >= 90` in class -> exact/fuzzy across classes -> masked-description `token_ratio >= 85` with equal rank count), `scale_slot` (constant / arithmetic copy, clean ratio, `+step`, extended to a different rank count / non-linear copy or manual), `anticipate(name, text, maxRank, class, prior)` -> `RankResult` with `to_fields()` in schema shape. Templates per section 5: `{n}` numeric slots, `%`/`sec`/`min` literal, plural slots computed (`point{1}` -> `""`/`"s"`), `(Rank 1)` never a slot. |
| `pipeline/stages/06_rankfill.py` | Typer CLI: fills `ranks_anticipated` per candidate record (canonical keys `description, ranks, ranksObserved, ranksSource, ranksPrior, ranksNote` plus `needsManual, confidence, review, rule, match`). `--dry-run` prints a table, `--force` recomputes. |
| `pipeline/src/wowtalents/export.py` | `build_extracted` (dedupe per cell, slugs with the section-3 collision rule, trees/pages/order from `segments.json` or `--tree-order`, provisional rules 51/5/10/60 `assumed`, `requires` parsed from "Requires N points in X" / "Requires X (Rank N)" with tier strings treated as row gating and cross-checked against the detected row, `crop-<id>` icons, video provenance, inline stage 6 when missing), `apply_overrides` (set/rename/delete/add, reviewed stamps, previous reading pushed to `source.readings`), `build_talents` (section 6.3: overrides, reviewed-keep with `REVIEWED-DIFF`, readings stripped), `update_encoding`, `write_validated` (temp copy -> `validate.py` -> rename; errors leave the target untouched). |
| `pipeline/stages/08_export.py` | `extract`, `promote`, `all`; `--root`, `--update-encoding`, `--no-files`, `--tree-order`, `--dry-run`, `-v`. Exit 1 on validation errors. |
| `pipeline/tests/test_ranks.py` | 40 tests over real Classic talents: Toughness 2/4/6/8/10 (copied) and 3% (ratio 1.5), Improved Heroic Strike (plural slot), Anger Management (1 rank), Improved Rend 20% (+10 step, the schema's `ranksNote` example), Improved Nature's Grasp 15/30/45/65 (non-linear copied vs re-based -> manual), Tactical Mastery with 3 ranks (extended), Deflection cross-class, Improved Wrench (description match, the section-11 example), Endurance (shape-changing strings), durations -> manual, three numbers -> manual, no numbers -> manual, `(Rank 1)` literal, no prior -> extrapolated. |
| `pipeline/tests/test_export.py` | 11 tests over `tests/fixtures/warrior.candidates.json` (3 Arms talents + a cut-off duplicate; one tier requirement, one talent prerequisite): document shape, crop copy, requires resolution and warnings, id collisions, unread names, validation refusal (rule 11) and acceptance, all four override kinds, reviewed survival across a re-export (both an override re-applied and an untouched reviewed record kept with `REVIEWED-DIFF`), the stage CLI end to end and idempotent, loud failure without an encoding entry. |
| `pipeline/README.md` | Appended section "Stage 6 and 8". |

`cd pipeline && uv run pytest -q`: 81 passed at the time of writing (51 from this session, the rest from the validator and the stage 00/03/04 work).

## Decision-table coverage (ranks.py)

| Condition | `ranksSource` | confidence / review | tested by |
|---|---|---|---|
| maxRank 1 | `observed` | high / no | Anger Management, Nature's Grasp |
| exact same-class name, constant/arithmetic, `c1 == f1` | `classic-prior` | high / no | Toughness 2%, Improved Heroic Strike, Improved Wrath |
| fuzzy name, cross-class or description match, copied | `classic-prior` | medium / yes | Improved Heroic Strke, Deflection (priest), Improved Wrench |
| arithmetic, clean ratio | `classic-prior` (`ratio`) | medium / yes | Toughness 3% |
| arithmetic, other base | `classic-prior` (`step`) | medium / yes | Improved Rend 20% |
| arithmetic, Classic rank count differs | `classic-prior` (`extended`) | medium / yes | Tactical Mastery 3 ranks |
| non-linear, `c1 == f1` | `classic-prior` | medium / yes | Improved Nature's Grasp 15% |
| non-linear, `c1 != f1` | `manual` | low / yes | Improved Nature's Grasp 20% |
| Classic shape-changing text, rank 1 identical | `classic-prior` (string ranks) | medium / yes | Endurance 45 sec |
| no match, 1-2 numbers, no duration | `extrapolated` | low / yes | Volatile Mixture, Twin Gears |
| no match, duration / 0 / 3+ numbers | `manual` | low / yes | Jet Boots, Mystery, Overdrive |

Deviations from the brief: description matches use threshold 85 (brief) and
additionally require the same rank count (Feline Swiftness otherwise matched
a 3-rank fixture at 0.86); "high" is reserved for exact same-class names (a
fuzzy name means the name itself needs review); a Classic match whose slots
cannot be aligned with the Forever numbers falls through to the no-match rows
with the match kept in `ranks_anticipated.match` for the reviewer.

## Deviations from the task text

- `08_export.py extract` writes `data/extracted/<class>.json` **without**
  overrides; `promote` applies them into `data/talents/<class>.json`. Section
  6.2 defines `overrides[].talent` as the id "as it appears in `extracted/`
  (pre-rename)" and `validate.py --overrides` cross-checks against
  `extracted/`, so baking overrides into `extracted/` would break both.
- Requirement refs use the schema's `{talent, rank}` (the task said
  `points`).
- `iconCrop` is `data/review/<class>/<tree>/<id>.icon.png` when the candidate
  carries `source.icon_crop_path`, else the tooltip crop `<id>.png` (rule 9
  needs an existing file either way).

## Open questions for the schema

1. **Empty-set "accept" overrides do not pin content.** Section 6.3 step 2
   re-applies overrides over the new extraction, so `"set": {}` marks whatever
   the pipeline reads next as reviewed. Export now logs `REVIEWED-DIFF` for
   that case; the review UI should probably write the accepted `name`,
   `description`, `ranks`, `maxRank` into `set`, or the doc should say that
   targeted-and-reviewed records are also kept verbatim.
2. **Rule 11 blocks every first export.** `extracted/` must list the class
   in the highest encoding version, which by section 8 is immutable once
   merged. `--update-encoding` upserts while unpublished; a cleaner rule
   would exempt `extracted/` from rule 11 or let export propose `v<N+1>.json`
   plus the migration.
3. **Tree icons.** `tree.icon` is required with no `iconSource`; export writes
   the provisional `crop-<treeId>`. Either add `tree.iconSource`/`iconCrop`
   or document the provisional slug for trees.
4. **Cross-class prior matches.** `ranksPrior.match` has no value for
   "cross-class"; it is recorded in `ranksNote` only. Consider adding the
   class to `ranksPrior` (`classicClass`) so the UI can say where the pattern
   came from.
5. **Unread names.** Export uses `crop-r<row>c<col>` ids (the doc's own
   example) with name `Unread r<row>c<col>`, which yields the icon slug
   `crop-crop-r3c2`. A reserved `unread-` prefix would read better.
6. **`validate.py` rule 15** (`token_ratio`) scores a name that is a token
   subset of a Classic name as 100 ("Improved Roots" vs "Improved Entangling
   Roots"); `ranks.py` inherits this for fuzzy names, hence the review flag.

## Next steps

1. Stage 5 must emit `source.crop_path` (and ideally `icon_crop_path`,
   `frame_index`, `readings`) per record so export can populate provenance
   without guessing; the fixture shows the expected keys.
2. Run `06_rankfill.py <class> --dry-run` on the first real class and eyeball
   the `*` rows; tune `PLURAL_STOPWORDS` / `DURATION_UNITS` if the heuristic
   misfires on Forever wording.
3. Review UI (`tools/review/`) should consume `ranks_anticipated.match` for
   its "pick Classic prior" box and write full `set` blocks (question 1).
4. First real class: `extract --update-encoding` on v1 is fine before the
   first publish; afterwards follow `data/encoding/README.md`.

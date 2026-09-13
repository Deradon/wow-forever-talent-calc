# Encoding versions

Build links (`/#/paladin?v=3&t=05320-0-3102`) encode one decimal digit per
talent. The digit order is frozen per data version in `v<N>.json`; the
normative description is `docs/DATA-SCHEMA.md` section 8.

## Files

- `v<N>.json`: `{ version, createdAt, frozen, note, classes: { <class>: { trees, order } } }`.
  `trees` lists tree ids in string-segment order (pages flattened: primary
  trees by `order`, then secondary trees). `order[<tree>]` lists talent ids
  row-major, i.e. the tree's talents sorted by `(row, col)` at the time the
  version was created.
- `migrations/v<A>-v<B>.json`: `{ from, to, classes: { <class>: { renamed,
  removed, moved } } }`. Migrations are total: every id in `v<A>` maps to an id
  in `v<B>` or appears in `removed`; `pipeline/validate.py` rule 11 checks
  the whole chain up to the class file's `dataVersion`.

## Rules

1. A version file is immutable once it is published, and `frozen: true` is what
   says so. `pipeline/stages/08_export.py --update-encoding` refuses to rewrite a
   frozen file: it copies it to `v<N+1>.json` (unfrozen), writes an empty
   `migrations/v<N>-v<N+1>.json` and tells you to fill both in. A missing
   `frozen` key is read as `false`.
2. Any change to the *set or order* of talent ids of any class (add, remove,
   rename, move between trees) requires `v<N+1>.json` covering all classes
   plus `migrations/v<N>-v<N+1>.json`. Text-only fixes (name spelling,
   description, ranks, icons) do not bump the version.
3. `dataVersion` in every `data/talents/<class>.json` and
   `data/extracted/<class>.json` must equal the highest version present here,
   and every class present in `data/talents/` must be present in that version.
4. A talent moved to another grid cell keeps its digit position; `validate.py`
   only warns (`ENCODING-ORDER`) when the encoding order is no longer
   row-major. The next version bump re-sorts.

## Current state

- `v1.json` (2026-09-13): the `tinker` example class plus all nine real classes,
  `frozen: false`. Owner decision of 2026-09-13: v1 stays mutable until launch
  is declared, because the data is still being corrected and no link is
  promised yet. It was in fact rewritten in place four times before the flag
  existed (see `docs/reviews/2026-09-13-code-and-docs.md` A1), which is exactly
  what `frozen` now prevents. **At launch: set `frozen: true`.** From then on
  any id or order change forks `v2.json`.

## How to bump

1. Copy `v<N>.json` to `v<N+1>.json`, set `version`, `createdAt`, `note` and
   `frozen: false` (`--update-encoding` does this for you when `v<N>` is frozen).
2. For every class, regenerate `trees` and `order` from the class file
   (row-major per tree). Keep a talent's id stable unless the rename changed
   its meaning.
3. Write `migrations/v<N>-v<N+1>.json` with every rename/removal/move.
4. Set `dataVersion: N+1` in every class file, run
   `cd pipeline && uv run python validate.py ../data/talents/*.json`.

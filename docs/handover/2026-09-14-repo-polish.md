# Handover: public repo polish, review write-back, About page (2026-09-14)

Frontend and docs session. Nothing under `pipeline/` or `data/` was touched
(other agents were working there at the same time), and
`.github/workflows/deploy.yml` was left alone.

## What changed

**Public README** (`README.md`, 107 lines) rewritten for a visitor rather than
a maintainer: what the site is, four screenshots, the feature list, three
sentences on how the data was made, the caveats ranked by how much they should
worry a reader (numbers first, 57 of 469 reviewed, the one missing mage Fire
talent, assumed rules, unverified Classic prior), how to run each half, how to
report a wrong reading, licence and non-affiliation. Screenshots are in
`docs/images/*.webp`, taken from the live site at 1440 px with
`npx playwright screenshot` and converted with `ffmpeg -c:v libwebp -quality 82`
(45-137 kB each, all four under the 300 kB budget). The class shot uses
`#/druid?sel=improved-moonfire`, which pins a tooltip from the URL - that is
how a sticky tooltip is scripted without a driver.

**`CONTRIBUTING.md`** (new): the override workflow as five steps (find the
record on `#/review/<class>`, Copy override, paste and edit, `promote` plus the
two validator runs, one class per pull request), one paragraph of coding
conventions, and the privacy rule spelled out for outside contributors -
including that `by` in an override is a public attribution.

**`.github/ISSUE_TEMPLATE/`** (new): `wrong-reading.yml` (where, which record,
what the site shows, what the crop or the game shows, link, plus a privacy
checkbox), `bug.yml`, and `config.yml` with blank issues off and three contact
links - Discussions, `CONTRIBUTING.md`, `#/about`. No e-mail address anywhere.

**Review write-back** on `#/review/<class>`, which stays read-only in the sense
that matters (it writes nothing to the repository):

- `web/src/ui/overrideEntry.ts` - pure. `buildOverrideEntry` turns a
  `ReviewRow` into an override entry prefilled with the id, the tree and the
  current name and description; `canonicalDump` is a TypeScript port of
  `_dump` in `pipeline/validate.py`, so the copied text is byte-identical to
  what the canonical serializer would write (verified against
  `canonical_dumps`). `overrideEntryText` indents an entry to its place inside
  the file; `overrideEntriesText` joins several as array *elements*.
  `wrongReadingUrl` builds the prefilled issue-form URL.
- `web/src/ui/ReviewPage.tsx` - a "Copy override" button and a "Report on
  GitHub" link per row, "Copy all flagged (n)" in the toolbar, a select-me
  textarea when the clipboard refuses, and a hint that names the file, the two
  `TODO`s and the two commands.
- `web/src/ui/copy.ts` (the `useCopy` hook, extracted so `ReviewPage` does not
  duplicate `BuildSummary`'s copy), `web/src/ui/review.css`.
- Tests: `overrideEntry.test.ts` (18 cases) checks the emitted shape against
  `data/schema/class.schema.json` (entry keys, `set` keys, `set.source` keys,
  the `talentId` / `treeId` / `rfc3339` patterns) and the key order against
  `KEY_ORDER` read out of `pipeline/validate.py`, and pastes an entry into the
  real `data/overrides/warrior.json` to check it still parses.
  `tests/review-writeback.spec.ts` covers the two buttons through the real
  clipboard (`playwright.config.ts` already grants the permission), the issue
  link and the About page.

**About page** `#/about` (`web/src/ui/AboutPage.tsx`, lazy): three paragraphs -
what it is, how the text was read, what to distrust - plus links to the changes
page, the issue form and the repository, linked from the footer on every page.
The Playwright case asserts the page carries no pipeline vocabulary.

Supporting edits: `#/about` in `src/url/route.ts` (before the class branch, or
`about` parses as a class id), `aboutHash()`, route tests, the lazy import and
the footer link in `App.tsx`, `REPO_URL` moved into the new
`web/src/ui/site.ts` alongside `SITE_URL`, `ISSUES_URL` and `DISCUSSIONS_URL`
(`ClassPicker` re-exports it, so no other call site changed), and the two new
routes documented in `web/README.md`.

## Decisions taken on the way

**`by` is `TODO`, not empty.** The brief asked for `by` left blank, but
`pipeline/validate.py`'s overrides schema has `required: [... by ...]` with
`minLength: 1`, so an empty string does not validate. It is emitted as `TODO`,
like `reason`, so both fields a human must write are one `grep TODO` away.

**`reviewed: true` sits in `set.source`, not at the top of the entry.** The
override entry schema is `additionalProperties: false` and has no `reviewed`
key, so a top-level one would fail. `set.source.reviewed` is a legal partial
source merge (the `$def` allows it, and the required-stripped `allOf` branches
do not fire without `kind`), and it states out loud what promoting the entry
does - `_mark_reviewed` sets `source.reviewed`, `reviewedBy` and `reviewedAt`
from `by`/`at` anyway. Verified end to end: an entry of this shape pasted into
`data/overrides/warrior.json` gives `0 errors, 0 warnings` from
`validate.py --overrides`.

**"Copy all flagged" emits array elements, not a bracketed array.** All nine
classes already have a `data/overrides/<class>.json` with an `overrides` array,
so a second pair of brackets would be a syntax error at the paste site. The
unit test parses `[${text}]` to prove it is still an array.

**"Flagged" means "what the filter shows".** The button count follows the flag
chips, the tree chips and the search box, so a reviewer narrows to `queue` (or
one tree) and takes that set in one go.

GitHub issue-form prefill syntax was verified against GitHub's form-schema
docs: the query parameter key is the element's `id` ("the id is the canonical
identifier for the field in URL query parameter prefills"), alongside the
reserved `template` and `labels`. `overrideEntry.test.ts` reads the ids back
out of `wrong-reading.yml`, so renaming a field there fails the test rather
than silently dropping the prefill.

## State

Green as of this session: `cd web && npx vitest run` 542 unit tests,
`npm run build` clean, `npx playwright test` 80 browser tests.
`npm run lint` shows only the pre-existing warnings.

**One thing seen in passing:** for a few minutes around 08:55 local,
`pipeline/validate.py` carried a duplicated
`ap.add_argument("--no-encoding", ...)` and crashed with
`argparse.ArgumentError` on every invocation, including the `--check` the CI
`check` job runs. That was another agent's in-flight edit, not this session's,
and it was gone again by 08:58 (`validate.py --check ../data/talents/druid.json`
exits 0). Worth a glance before pushing, since a duplicate argparse flag takes
the whole validator down, not just one mode.

## Next

1. Take the review route for a real round: `#/review/mage` (the 6 remaining
   sub-0.8 records), Copy override, paste, `promote`. That flow has never been
   walked by a human end to end.
2. Races and spells have no override mechanism, so a wrong racial trait can
   only be reported, not fixed. `data/overrides/races/` and the equivalent in
   `12_races.py` / `11_spellbook.py` are the missing half.
3. A `by` other than `TODO` per reviewer would be worth a one-field toolbar
   input on the review route (stored in `localStorage`, never committed by the
   page itself).
4. `BuildSummary.tsx` still carries its own copy of `useCopy`; point it at
   `web/src/ui/copy.ts` the next time it is touched.

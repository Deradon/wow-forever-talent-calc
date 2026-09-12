# Data schema

`data/` is the contract between the Python pipeline (writes candidates to
`data/extracted/`) and the static web app (reads `data/talents/<class>.json`).
This document is the normative description of that contract. The machine
schema `data/schema/class.schema.json` (JSON Schema draft 2020-12) is derived
from it; when they disagree, fix the schema.

Status: schema version 1, written 2026-09-13 before any real Forever data
exists. Unknowns of the Forever talent system (Primary/Secondary tabs, tree
count, points per row, cap) are modelled as data, not as code assumptions.

Related: `docs/briefs/data-prior-and-review.md` (implementation brief),
`docs/research/2026-09-13-*.md` (background).

## 1. Directory layout

```
data/
  schema/class.schema.json      JSON Schema for every class file below
  talents/<class>.json          canonical, reviewed data; the web app reads only this
  extracted/<class>.json        pipeline output, same schema, never edited by hand
  overrides/<class>.json        hand corrections applied on top of extracted/
  prior/classic-era/            Classic Era reference data used for rank anticipation
  encoding/v<N>.json            frozen talent order per data version (build-link strings)
  encoding/migrations/v<A>-v<B>.json   id renames/removals between versions
  review/<class>/<tree>/<talent-id>.png   tooltip crops referenced by source.crop
```

Everything under `data/` is committed, crops included (a 64x64 icon crop is
~5 KB, a tooltip crop ~40 KB; 500 talents ~20 MB, acceptable). Video and full
frames stay under `pipeline/work/`.

Flow: `pipeline` -> `data/extracted/` -> (`data/overrides/`, review UI) ->
`export` -> `data/talents/` -> `validate` -> web app. See section 7.

## 2. Conventions

- JSON, UTF-8, 2-space indent, keys in the order given in this document,
  arrays of talents sorted by `(row, col)`. `export.py` and the review UI
  write files through one serializer so diffs stay small: `canonical_dumps`
  in `pipeline/validate.py` (objects and arrays of objects expanded, arrays
  of scalars or of scalar arrays inline when they fit in 100 characters).
- Field names camelCase. Unknown fields are rejected (`additionalProperties:
  false` everywhere) so typos fail validation instead of being ignored.
- Text is stored as shown in the English client. Curly quotes, non-breaking
  spaces and double spaces are normalised to ASCII / single space by the
  pipeline before writing.
- All IDs are slugs (section 3). Grid positions are never part of an ID.
- Every talent carries `source` (provenance). Hand-entered talents use
  `source.kind: "manual"`; there is no talent without provenance.

## 3. ID conventions

| Kind | Rule | Example |
|---|---|---|
| class id | slug of the class name. The schema accepts any slug; `validate.py` warns (`UNKNOWN-CLASS`) when it is not one of `druid hunter mage paladin priest rogue shaman warlock warrior`, so the fictional example class still validates (extend the list if Forever adds a class) | `paladin` |
| page id | `primary` or `secondary` (extend if the UI shows more tabs) | `primary` |
| tree id | slug of the tree name as shown in the client; unique per class file | `protection` |
| talent id | slug of the talent name; unique per class file (not per tree); on collision across trees append `-<treeId>` | `improved-heroic-strike`, `improved-blessing-of-might-holy` |
| icon | Blizzard icon file name, lower-case, no extension | `ability_warrior_savageblow` |

Slug rule: NFKD-normalise, drop diacritics, lower-case, remove apostrophes
(`Nature's Grasp` -> `natures-grasp`), replace every other non-`[a-z0-9]` run
with `-`, trim `-`. Regex for validation: `^[a-z0-9]+(-[a-z0-9]+)*$`, max 64
chars.

IDs are stable once an encoding version (section 8) has been published. A
talent that is renamed by Blizzard keeps its id unless the rename changes the
meaning; renames go through a migration file, never through a silent edit.

## 4. Class file, field by field

Top level of `data/talents/<class>.json` (identical for `data/extracted/`).

| Field | Type | Req | Description |
|---|---|---|---|
| `$schema` | string | no | `"../schema/class.schema.json"`, for editor support only |
| `schemaVersion` | integer | yes | Version of this document's schema. Currently `1`. Bumped on breaking shape changes; `validate.py` refuses other values. |
| `class` | string (class id) | yes | Must equal the file name stem. |
| `className` | string | yes | Display name, e.g. `"Paladin"`. |
| `dataVersion` | integer >= 1 | yes | Encoding version this file conforms to; `data/encoding/v<dataVersion>.json` must exist and list exactly this file's talent ids (section 8). |
| `dataSource` | enum `video`, `datamined`, `mixed`, `manual` | yes | Dominant provenance of the file; informational (per-talent truth is `source.kind`). The UI shows a global caveat unless `datamined`. |
| `generatedAt` | string, RFC 3339 | yes | When `export.py` wrote the file. |
| `rules` | object | yes | Point rules for this class (section 4.1). |
| `pages` | array of Page | yes, >= 1 | Tabs shown above the trees (section 4.2). |
| `trees` | array of Tree | yes, >= 1 | Talent trees (section 4.3). No upper bound; vanilla has 3, Forever may have more. |
| `notes` | array of string | no | Free-form caveats shown in the UI footer ("Secondary tab meaning unconfirmed"). |

### 4.1 `rules`

| Field | Type | Req | Description |
|---|---|---|---|
| `pointsPerRow` | integer >= 0 | yes | Points needed in a tree per row of depth; vanilla 5. `0` disables row gating. |
| `maxPoints` | integer >= 1 | yes | Total spendable points; vanilla 51. |
| `firstPointLevel` | integer >= 1 | yes | Level at which the first point is earned; vanilla 10. `requiredLevel(n) = n === 0 ? 1 : firstPointLevel - 1 + n`. |
| `maxLevel` | integer | yes | 60. Validation: `firstPointLevel - 1 + maxPoints <= maxLevel`. |
| `pointsPerPage` | object `{ <pageId>: integer }` | no | Per-page budget if Primary/Secondary turn out to have separate pools. Absent = one shared pool of `maxPoints`. |
| `rulesSource` | enum `observed`, `classic-prior`, `assumed` | yes | Where these numbers come from. Start with `assumed` (51/5/10 from Classic) until confirmed on screen or in DB2. |

### 4.2 Page

| Field | Type | Req | Description |
|---|---|---|---|
| `id` | page id | yes | |
| `name` | string | yes | Tab label as shown, e.g. `"Primary"`. |
| `note` | string | no | What we believe the tab means; shown as a caveat. |

### 4.3 Tree

| Field | Type | Req | Description |
|---|---|---|---|
| `id` | tree id | yes | |
| `name` | string | yes | As shown in the client. |
| `page` | page id | yes | Which tab the tree lives on. Must reference `pages[].id`. |
| `order` | integer >= 0 | yes | Left-to-right position within its page. Unique per page. |
| `icon` | icon | yes | Tree icon (next to the point counter). |
| `background` | string | no | Key into `web/public/backgrounds/`; omitted until we have art. |
| `rows` | integer >= 1 | yes | Grid rows; vanilla 7. |
| `cols` | integer >= 1 | yes | Grid columns; vanilla 4. |
| `role` | enum `tank`, `healer`, `dps`, `hybrid` | no | Informational. |
| `datamined` | object | no | `{ "talentTabId": 383, "build": "1.60.1.69704" }` once imported (section 9). |
| `source` | Source | no | Provenance of the tree header reading (segment frame). |
| `talents` | array of Talent | yes, >= 1 | Sorted by `(row, col)`. |

### 4.4 Talent

| Field | Type | Req | Description |
|---|---|---|---|
| `id` | talent id | yes | Unique per class file. |
| `name` | string, 1..80 | yes | Exactly as shown in the tooltip header. |
| `row` | integer, `0 <= row < tree.rows` | yes | 0 = top. |
| `col` | integer, `0 <= col < tree.cols` | yes | 0 = left. `(row, col)` unique per tree. |
| `maxRank` | integer 1..9 | yes | From the tooltip's `Rank 0/N`. Upper bound 9 = Talent.db2 `SpellRank_0..8` width. |
| `icon` | icon | yes | Canonical icon name. For `iconSource: "crop"` this is a provisional slug `crop-<talent-id>`, resolved when datamined. |
| `iconSource` | enum `classic`, `crop`, `datamined`, `manual` | yes | `classic` = pHash-matched against the Classic icon set; `crop` = no match, the UI shows `iconCrop`. |
| `iconCrop` | string (repo-relative path) | iff `iconSource == "crop"` | 64x64 PNG under `data/review/`. |
| `description` | string | yes | Rank-independent template. Placeholders `{0}`, `{1}`, ... are filled from `ranks[r]`. Braces that are not placeholders are not allowed. |
| `ranks` | array, length == `maxRank` | yes | `ranks[r]` is either an array of slot values (number or string) whose length equals the number of distinct placeholders in `description`, or a full string when the sentence changes shape at that rank. Index 0 = rank 1. |
| `ranksObserved` | array of integer (1-based) | yes | Which ranks were actually read from footage/DB2. Video data: `[1]`. Datamined: all. |
| `ranksSource` | enum `observed`, `classic-prior`, `extrapolated`, `manual` | yes | How ranks beyond `ranksObserved` were derived. `observed` only when `ranksObserved` covers every rank. The UI shows a caveat for everything else. |
| `ranksPrior` | object | iff `ranksSource == "classic-prior"` | `{ "classicTalentId": 124, "classicSpellIds": [12282, 12663, 12664], "match": "exact-name" \| "fuzzy-name" \| "description", "similarity": 0.97 }`. Points into `data/prior/classic-era/`. |
| `ranksNote` | string | no | Human note, e.g. `"Classic scales 15/25/35, Forever rank 1 is 20: applied +10/rank"`. Required when `ranksSource == "manual"`. |
| `requires` | array of Requirement | no | Prerequisite talents (arrow). Array from day one: Talent.db2 has three `PrereqTalent` slots and Wowhead's data uses an array. Empty array is not allowed; omit instead. |
| `capstone` | boolean | no | Informational; the app derives "bottom row" itself. Only for a talent that is explicitly called out as the tree's capstone in footage. |
| `spellIds` | array of integer, length == `maxRank` | no | Per-rank spell ids once datamined. Absent for video data. |
| `tags` | array of string | no | Free-form (`"new"`, `"reworked"`, `"classic-unchanged"`); the UI may filter on them. |
| `source` | Source | yes | Provenance (section 4.5). |

Requirement:

| Field | Type | Req | Description |
|---|---|---|---|
| `talent` | talent id | yes | Must exist in the same tree and in a strictly smaller `row`. |
| `rank` | integer >= 1 | yes | Points required in that talent; usually its `maxRank`. |

### 4.5 Source (provenance)

| Field | Type | Req | Description |
|---|---|---|---|
| `kind` | enum `video`, `datamined`, `manual` | yes | |
| `video` | string | iff `kind == "video"` | YouTube video id, e.g. `"DxtVEhjyROU"`. |
| `t` | number >= 0 | iff `video` | Seconds into the video of the chosen frame (3 decimals). |
| `frame` | integer >= 0 | iff `video` | Frame index at the source's native frame rate (`t * fps`). |
| `crop` | string | iff `video` | Repo-relative path of the tooltip crop, e.g. `data/review/warrior/arms/improved-heroic-strike.png`. |
| `confidence` | number 0..1 | iff `kind == "video"` | Reader confidence for the whole record (min over fields). Review queue threshold: `< 0.8`. |
| `reader` | string | iff `kind == "video"` | Model or engine incl. quantisation, e.g. `"qwen3-vl-8b-instruct-q4_k_m"`, `"rapidocr-1.4"`. |
| `readings` | array of object | no | Alternative readings kept for the review UI: `{ "reader": "...", "name": "...", "description": "...", "maxRank": 3, "confidence": 0.7 }`. Dropped by `export.py`. |
| `build` | string | iff `kind == "datamined"` | Client build, e.g. `"1.60.1.69704"`. |
| `talentId` | integer | iff `kind == "datamined"` | Talent.db2 `ID`. |
| `reviewed` | boolean | yes | `true` = a human confirmed every field of this talent. The pipeline never overwrites a talent whose canonical record has `reviewed: true`. |
| `reviewedBy` | string | iff `reviewed` | Handle or email of the reviewer. |
| `reviewedAt` | string, RFC 3339 | iff `reviewed` | |
| `note` | string | no | Free text ("tooltip partly covered by cursor, description completed from Classic"). |

A `manual` source needs only `kind`, `reviewed: true`, `reviewedBy`,
`reviewedAt` and ideally `note` saying where the information came from.

## 5. Description templates and ranks

- `description` is the rank-1 text with every number that changes per rank
  replaced by `{n}`, `n` counted from 0 in order of first appearance. Numbers
  that do not change stay literal.
- Units stay in the template: `"by {0}%"`, `"for {0} sec"`. Pluralisation
  goes into a slot: `"{0} rage point{1}."` with `ranks: [[1, ""], [2, "s"],
  [3, "s"]]`.
- Rendering: `render(talent, r) = ranks[r] is string ? ranks[r] :
  description.replace(/\{(\d+)\}/g, (_, i) => String(ranks[r][i]))`.
- The web app shows `ranks[current-1]` and `ranks[current]` ("Next rank"); at
  rank 0 it shows `ranks[0]`.
- `ranksSource` and `ranksObserved` drive the caveat. Rule for the UI:
  `ranksSource != "observed"` -> show "ranks 2+ anticipated (<ranksSource>)"
  on the tooltip and dim the next-rank text.

## 6. Extracted, overrides and canonical files

### 6.1 `data/extracted/<class>.json`

Same schema. Written by `pipeline/10_export` from the reader output. Every
talent has `source.kind: "video"`, `source.reviewed: false`,
`ranksObserved: [1]` and a `ranksSource` of `classic-prior`, `extrapolated`
or `manual` (in which case `ranks` beyond rank 1 are `null`-free copies of
rank 1 and `ranksNote` says "needs manual ranks"). `source.readings` may be
present. Re-running the pipeline rewrites this file completely; it is never
edited by hand.

### 6.2 `data/overrides/<class>.json`

Hand corrections, produced by the review UI or by editing. Structure:

```json
{
  "schemaVersion": 1,
  "class": "warrior",
  "overrides": [
    {
      "talent": "improved-rend",
      "tree": "arms",
      "set": { "name": "Improved Rend", "ranks": [[15], [25], [35]], "ranksSource": "classic-prior" },
      "reason": "reader dropped the 'd' in Rend; ranks from Classic talent 126",
      "by": "deradon", "at": "2026-09-14T20:11:00Z"
    },
    {
      "talent": "crop-r3c2", "tree": "fury",
      "rename": "blood-frenzy",
      "reason": "reader failed on the name; read manually from frame 20311",
      "by": "deradon", "at": "2026-09-14T20:15:00Z"
    },
    {
      "talent": "ghost-talent", "tree": "fury",
      "delete": true,
      "reason": "duplicate hover of enrage detected as a separate cell",
      "by": "deradon", "at": "2026-09-14T20:20:00Z"
    },
    {
      "talent": "new-talent-id", "tree": "protection",
      "add": { "...full Talent record with source.kind manual..." : "" },
      "reason": "missed by segmentation; hovered at 04:02:11",
      "by": "deradon", "at": "2026-09-14T20:25:00Z"
    }
  ]
}
```

| Field | Type | Req | Description |
|---|---|---|---|
| `talent` | talent id | yes | Target as it appears in `extracted/` (pre-rename). |
| `tree` | tree id | yes | Disambiguates and catches the pipeline moving a talent between trees. |
| `set` | partial Talent | one of `set`/`rename`/`delete`/`add` | Shallow merge over the extracted talent; `source` sub-fields merge shallowly too. |
| `rename` | talent id | | New id. Requires a migration entry if an encoding version already contains the old id. |
| `delete` | `true` | | Drop the talent. |
| `add` | full Talent | | Insert a talent that extraction missed. |
| `reason` | string | yes | Why. Non-empty. |
| `by`, `at` | string, RFC 3339 | yes | Who and when. |

Overrides are applied in file order; a later override on the same talent
wins field-by-field. Applying an override sets `source.reviewed: true`,
`reviewedBy: by`, `reviewedAt: at` on the resulting talent, and pushes the
pre-override reading into `source.readings` if it is not already there.

### 6.3 `data/talents/<class>.json` (canonical)

Written by `export.py`:

1. Load `extracted/<class>.json`, apply `overrides/<class>.json`.
2. Load the existing `talents/<class>.json` if any. For every talent id in
   it with `source.reviewed: true` that is not targeted by an override in
   this run, keep the existing record verbatim (even if the pipeline now
   reads it differently; the pipeline logs a `REVIEWED-DIFF` warning with the
   diff so the reviewer can decide). This is the "never overwritten" rule.
3. Strip `source.readings`, sort, serialize, set `generatedAt`, write.
4. Run `validate.py`; a failing file is not written (write to a temp path,
   validate, rename).

Direct manual edits to `data/talents/` are allowed as a last resort but
must set `source.reviewed: true` and `reviewedBy`; CI runs `validate.py`
and rejects a canonical file that does not round-trip through `export.py`
(`export.py --check` compares).

## 7. Review workflow

1. Pipeline run produces `data/extracted/<class>.json` + crops.
2. `validate.py data/extracted/<class>.json --report` prints the review
   queue: every talent with `source.confidence < 0.8`, any structural
   warning, any `ranksSource: "manual"`, and any `iconSource: "crop"`.
3. Reviewer opens the review UI (`tools/review/`, or the hidden
   `/review/<class>` route in the web app) which lists the queue by
   ascending confidence, shows the crop next to the rendered tooltip, and
   writes accepted/edited records into `data/overrides/<class>.json`.
4. `export.py <class>` merges and writes `data/talents/<class>.json`.
5. `validate.py data/talents/<class>.json` must pass; commit extracted,
   overrides, talents and crops together.

Accepting a record unchanged still writes an override with an empty `set`
(`"set": {}`) so `reviewed: true` gets provenance; there is no other way to
mark a talent reviewed.

## 8. Encoding versions and migrations

Build links use Wowhead's format: one decimal digit per talent, trees joined
by `-`, trailing zeros trimmed, plus a data version segment:
`/#/paladin?v=3&t=05320-0-3102`. The digit order is frozen per version in
`data/encoding/v<N>.json`:

```json
{
  "version": 3,
  "createdAt": "2026-09-15T10:00:00Z",
  "note": "after rogue/warrior review",
  "classes": {
    "paladin": {
      "trees": ["holy", "protection", "retribution", "secondary-holy"],
      "order": {
        "holy": ["divine-strength", "divine-intellect", "spiritual-focus", "..."],
        "protection": ["..."]
      }
    }
  }
}
```

- `trees` lists tree ids in string-segment order (pages flattened: primary
  trees in `order`, then secondary trees). `order[tree]` lists talent ids
  row-major. Every class present in `data/talents/` must be present here.
- Rules: an encoding file is immutable once merged to `main`. Any change to
  the set or order of talent ids in any class (add, remove, rename, move)
  requires a new version `v<N+1>.json` covering all classes, plus a
  migration file. Text-only corrections (name spelling, description, ranks,
  icons) do not need a new version.
- `dataVersion` in each class file must equal the highest version in
  `data/encoding/`; validation checks that the class's talent ids equal the
  version's `order` sets.
- `data/encoding/migrations/v3-v4.json`:

```json
{
  "from": 3, "to": 4,
  "classes": {
    "paladin": {
      "renamed": { "crop-r3c2": "sanctified-light" },
      "removed": ["duplicate-holy-shock"],
      "moved": { "toughness": { "from": "holy", "to": "protection" } }
    }
  }
}
```

Decoder in `web/src/rules/encoding.ts`: read `v`, load `v<N>.json` (all
versions are shipped, they are small), map digits to ids, apply migrations
`v -> v+1 -> ... -> current` (renamed: keep points; removed: drop points;
moved: keep points), re-encode in the current order, then run
`validateTree` and drop violating points top-down with a "build adjusted"
notice. Migrations are total: every id in `v<N>` maps to an id in `v<N+1>` or
appears in `removed`; `validate.py` checks this chain.

## 9. Datamined import path (drop-in replacement, after 2026-09-17)

`pipeline/import_db2.py --build <build> --class <class>` reads the wago.tools
CSV exports and writes `data/extracted/<class>.json` in this same schema
with `source.kind: "datamined"`, `ranksObserved` = all, `ranksSource:
"observed"`, `spellIds` filled, `iconSource: "datamined"`. Then the usual
`export.py` run applies. Reviewed video records are still kept by rule 6.3/2
until the reviewer accepts the datamined version (bulk accept: `export.py
--prefer datamined` writes overrides with reason "datamined <build>"). Field
mapping and verified table names are in the brief, section (e).

Talent ids stay slugs of the datamined `SpellName.Name_lang`; the importer
uses the migration mechanism for any id that differs from the video-era id
(it proposes `renamed` entries by matching `(tree, row, col)`).

## 10. Validation rules (`pipeline/validate.py`)

Exit code 1 on any error; warnings are printed and do not fail unless
`--strict`. Applies to `extracted/`, `talents/` and (with `--overrides`)
`overrides/` files.

Schema (errors):

1. File parses; validates against `data/schema/class.schema.json`;
   `schemaVersion == 1`; no additional properties anywhere.
2. `class` equals the file stem; all ids match the slug regex.
3. `rules`: `firstPointLevel - 1 + maxPoints <= maxLevel`; every key of
   `pointsPerPage` is a page id.
4. `pages[].id` unique; every `tree.page` exists; `tree.order` unique per
   page; `tree.id` unique.
5. Talent ids unique across the whole file; `(row, col)` unique per tree;
   `row < tree.rows`, `col < tree.cols`.
6. `ranks.length == maxRank`; every array-form `ranks[r]` has exactly as
   many entries as there are distinct `{n}` placeholders in `description`
   and the placeholders are `{0}..{k-1}` without gaps; string-form
   `ranks[r]` contains no `{n}`.
7. `ranksObserved` is sorted, unique, each `1..maxRank`; `ranksSource ==
   "observed"` iff `ranksObserved` covers all ranks; `ranksPrior` present iff
   `ranksSource == "classic-prior"`; `ranksNote` present if `manual`.
8. `requires[]`: target exists in the same tree, `target.row < talent.row`,
   `rank <= target.maxRank`, no self-reference, no cycles, at most 3 entries
   (Talent.db2 width).
9. `iconCrop` present iff `iconSource == "crop"` and the file exists;
   `source.crop` file exists (both checked relative to repo root).
10. `source` conditional fields per section 4.5; `reviewedBy`/`reviewedAt`
    iff `reviewed`. `spellIds.length == maxRank` when present.
11. `dataVersion` encoding file exists; the class's talent id set equals the
    union of `order[*]` for that class; tree list equals the file's tree ids;
    migration chain from every older version is total (section 8).
12. For `talents/`: no `source.readings`; `generatedAt` present; file equals
    the canonical serializer output byte-for-byte (`--check`; a warning
    without the flag).

Content (warnings, `--strict` makes them errors):

13. Row gating sanity: `pointsPerRow * (tree.rows - 1) <= maxPoints` (a
    capstone must be reachable).
14. Numeric progression: for array-form ranks, each numeric slot is
    monotonic and either constant, arithmetic, or matches the Classic
    prior's pattern; otherwise warn `NONLINEAR-RANKS`.
15. Name dictionary: `rapidfuzz.fuzz.token_ratio(name, classicName) >= 90`
    for some Classic talent of the same class, else `NEW-TALENT` (info, not a
    problem, but listed for review). If a match exists and `maxRank`
    differs, warn `MAXRANK-DIFFERS-FROM-CLASSIC`.
16. `source.confidence < 0.8 && !reviewed` -> `NEEDS-REVIEW`.
17. Description hygiene: no double spaces, no leading/trailing space, ends
    with `.` or `%`-terminated clause, no OCR artefacts (`|`, `\`, `~`,
    lone `l`/`I` where a digit is expected).
18. Tree total ranks: `sum(maxRank)` per tree >= `maxPoints` (you cannot
    have a tree that cannot absorb all points) and <= 3 * `maxPoints`.
19. Per-tree row occupancy: every row 0..rows-1 has at least one talent.

Output: human-readable list `LEVEL CODE file:class/tree/talent: message`
and `--json` for the review UI. `--no-files` skips the file-existence part of
rule 9, `--root <dir>` sets the repo root (default: found by walking up from
the file to `data/schema/class.schema.json`). Rules 14 (prior pattern) and 15
need `data/prior/classic-era/talents.json` and are skipped without it.

## 11. Complete example: fictional two-tree class

Every field appears at least once. Class `tinker` with a primary tree
`gadgetry` and a secondary tree `chemistry`. `rocket-boots` has `requires`;
`volatile-mixture` has `ranksSource: "extrapolated"`.

```json
{
  "$schema": "../schema/class.schema.json",
  "schemaVersion": 1,
  "class": "tinker",
  "className": "Tinker",
  "dataVersion": 1,
  "dataSource": "video",
  "generatedAt": "2026-09-15T18:42:07Z",
  "rules": {
    "pointsPerRow": 5,
    "maxPoints": 51,
    "firstPointLevel": 10,
    "maxLevel": 60,
    "pointsPerPage": { "primary": 51, "secondary": 10 },
    "rulesSource": "assumed"
  },
  "pages": [
    { "id": "primary", "name": "Primary" },
    { "id": "secondary", "name": "Secondary", "note": "Meaning of the Secondary tab unconfirmed; modelled as a separate 10-point pool." }
  ],
  "trees": [
    {
      "id": "gadgetry",
      "name": "Gadgetry",
      "page": "primary",
      "order": 0,
      "icon": "inv_misc_enggizmos_27",
      "background": "tinker-gadgetry",
      "rows": 7,
      "cols": 4,
      "role": "dps",
      "source": { "kind": "video", "video": "DxtVEhjyROU", "t": 13102.500, "frame": 786150, "crop": "data/review/tinker/gadgetry/_header.png", "confidence": 0.99, "reader": "qwen3-vl-8b-instruct-q4_k_m", "reviewed": false },
      "talents": [
        {
          "id": "improved-wrench",
          "name": "Improved Wrench",
          "row": 0, "col": 1,
          "maxRank": 3,
          "icon": "inv_misc_wrench_01",
          "iconSource": "classic",
          "description": "Reduces the cost of your Wrench Strike ability by {0} energy point{1}.",
          "ranks": [[1, ""], [2, "s"], [3, "s"]],
          "ranksObserved": [1],
          "ranksSource": "classic-prior",
          "ranksPrior": { "classicTalentId": 124, "classicSpellIds": [12282, 12663, 12664], "match": "description", "similarity": 0.93 },
          "ranksNote": "Same wording as Improved Heroic Strike; Classic scales 1/2/3.",
          "tags": ["classic-unchanged"],
          "source": {
            "kind": "video", "video": "DxtVEhjyROU", "t": 13110.250, "frame": 786615,
            "crop": "data/review/tinker/gadgetry/improved-wrench.png",
            "confidence": 0.94, "reader": "qwen3-vl-8b-instruct-q4_k_m",
            "reviewed": true, "reviewedBy": "deradon", "reviewedAt": "2026-09-15T17:30:00Z"
          }
        },
        {
          "id": "steady-hands",
          "name": "Steady Hands",
          "row": 0, "col": 2,
          "maxRank": 5,
          "icon": "crop-steady-hands",
          "iconSource": "crop",
          "iconCrop": "data/review/tinker/gadgetry/steady-hands.icon.png",
          "description": "Increases your chance to hit with Gadgets by {0}%.",
          "ranks": [[1], [2], [3], [4], [5]],
          "ranksObserved": [1],
          "ranksSource": "classic-prior",
          "ranksPrior": { "classicTalentId": 1341, "classicSpellIds": [19407, 19412, 19413, 19414, 19415], "match": "fuzzy-name", "similarity": 0.91 },
          "source": {
            "kind": "video", "video": "DxtVEhjyROU", "t": 13114.000, "frame": 786840,
            "crop": "data/review/tinker/gadgetry/steady-hands.png",
            "confidence": 0.71, "reader": "qwen3-vl-8b-instruct-q4_k_m",
            "readings": [ { "reader": "rapidocr-1.4", "name": "Steady Hand", "description": "Increases your chance to hit with Gadgets by 1%.", "maxRank": 5, "confidence": 0.62 } ],
            "reviewed": false,
            "note": "cursor overlaps the icon; icon unmatched"
          }
        },
        {
          "id": "rocket-boots",
          "name": "Rocket Boots",
          "row": 2, "col": 1,
          "maxRank": 1,
          "icon": "inv_boots_02",
          "iconSource": "classic",
          "description": "Propels you forward, increasing movement speed by {0}% for {1} sec. {2} min cooldown.",
          "ranks": [[70, 3, 2]],
          "ranksObserved": [1],
          "ranksSource": "observed",
          "requires": [ { "talent": "improved-wrench", "rank": 3 } ],
          "tags": ["new"],
          "source": {
            "kind": "video", "video": "DxtVEhjyROU", "t": 13131.750, "frame": 787905,
            "crop": "data/review/tinker/gadgetry/rocket-boots.png",
            "confidence": 0.97, "reader": "qwen3-vl-8b-instruct-q4_k_m",
            "reviewed": true, "reviewedBy": "deradon", "reviewedAt": "2026-09-15T17:31:00Z"
          }
        },
        {
          "id": "overclock",
          "name": "Overclock",
          "row": 6, "col": 1,
          "maxRank": 1,
          "icon": "spell_nature_lightning",
          "iconSource": "classic",
          "description": "Overclocks your gadgets, increasing all damage dealt by {0}% for {1} sec.",
          "ranks": [[20, 15]],
          "ranksObserved": [1],
          "ranksSource": "observed",
          "capstone": true,
          "spellIds": [990001],
          "source": {
            "kind": "manual",
            "reviewed": true, "reviewedBy": "deradon", "reviewedAt": "2026-09-15T17:40:00Z",
            "note": "Not hovered in the stream; text taken from the Output Lag panel screenshot."
          }
        }
      ]
    },
    {
      "id": "chemistry",
      "name": "Chemistry",
      "page": "secondary",
      "order": 0,
      "icon": "inv_potion_24",
      "rows": 3,
      "cols": 4,
      "role": "hybrid",
      "datamined": { "talentTabId": 999, "build": "1.60.1.69704" },
      "talents": [
        {
          "id": "volatile-mixture",
          "name": "Volatile Mixture",
          "row": 0, "col": 0,
          "maxRank": 3,
          "icon": "inv_potion_23",
          "iconSource": "classic",
          "description": "Your Flasks also deal {0} Fire damage to nearby enemies.",
          "ranks": [[40], [80], [120]],
          "ranksObserved": [1],
          "ranksSource": "extrapolated",
          "ranksNote": "No Classic counterpart; linear x2, x3 of rank 1 assumed.",
          "tags": ["new"],
          "source": {
            "kind": "video", "video": "DxtVEhjyROU", "t": 13240.000, "frame": 794400,
            "crop": "data/review/tinker/chemistry/volatile-mixture.png",
            "confidence": 0.88, "reader": "qwen3-vl-8b-instruct-q4_k_m",
            "reviewed": false
          }
        },
        {
          "id": "field-medic",
          "name": "Field Medic",
          "row": 1, "col": 1,
          "maxRank": 2,
          "icon": "inv_misc_bandage_12",
          "iconSource": "datamined",
          "description": "Your bandages heal {0}% more and can be used while moving.",
          "ranks": ["Your bandages heal 10% more.", "Your bandages heal 20% more and can be used while moving."],
          "ranksObserved": [1, 2],
          "ranksSource": "observed",
          "spellIds": [990010, 990011],
          "source": {
            "kind": "datamined", "build": "1.60.1.69704", "talentId": 2101,
            "reviewed": false
          }
        }
      ]
    }
  ],
  "notes": ["Fictional example class used to document the schema; not game data."]
}
```

Notes on the example:

- `field-medic` shows string-form ranks: rank 2 changes the sentence shape,
  so both ranks are full strings and the template is only documentation.
- `overclock` shows a `manual` source and an informational `capstone`.
- `steady-hands` is what a review-queue record looks like: low confidence,
  a second reading, an unmatched icon with `iconCrop`. Its `ranksPrior`
  points at a real Classic talent (1341, Improved Concussive Shot) so the
  cross-check against `data/prior/classic-era/talents.json` passes.
- The example is committed as `data/examples/tinker.json` (written through
  the canonical serializer) with placeholder 1x1 PNGs under
  `data/review/tinker/` so it passes `validate.py --check` unchanged; it is
  the class file the web app starts from. `data/encoding/v1.json` lists it.
- The `secondary` page is given its own 10-point pool via
  `rules.pointsPerPage` purely to show the field; delete `pointsPerPage`
  for a shared pool.

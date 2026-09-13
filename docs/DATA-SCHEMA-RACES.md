# Data schema: races

Normative description of `data/races/`, the second contract between the Python
pipeline and the static web app. `docs/DATA-SCHEMA.md` owns `data/talents/` and
everything the two have in common (conventions, slugs, the `source` idea); this
document owns what is different. Where they disagree about races, this file
wins. The machine schemas `data/schema/race.schema.json` and
`data/schema/race-matrix.schema.json` are derived from it; when they disagree,
fix the schema.

Status: schema version 1, written 2026-09-13 from the first full extraction
(37 traits over 9 races, `docs/handover/2026-09-13-races-data.md`).

## 1. Directory layout

```
data/
  schema/race.schema.json          JSON Schema for every data/races/<race>.json
  schema/race-matrix.schema.json   JSON Schema for data/races/matrix.json
  races/<race>.json                canonical race file; the web app reads only this
  races/matrix.json                derived race/class matrix (generated, never hand-edited)
  extracted/races.json             stage 12 candidates, every reading of every state
  extracted/races.md               human inventory: counts, confidence, the matrix
  review/races/<race>/<trait>.png       trait row crop referenced by source.crop
  review/races/<race>/<trait>.icon.png  36 px icon crop referenced by iconCrop
  review/races/<race>/_panel.png        the whole box, fallback evidence
  review/races/<race>/_classbar.png     the class bar the class list was read from
  review/races/<race>/_general.png      spellbook General page (Undead cross-check only)
  prior/classic-era/racials.json        Classic Era racials, written from memory
  prior/classic-era/racial-diff.json    hand same/changed verdicts, unverified
```

Flow: `pipeline/stages/12_races.py scan` -> `read` -> `build` ->
`data/races/` -> `pipeline/validate_races.py` -> web app. There is no
`extracted -> overrides -> talents` promote step for races yet: stage 12 writes
`data/races/` directly, because nothing there is reviewed and no encoding
version depends on race ids. When the first review round happens, add
`data/overrides/races/<race>.json` with the mechanism of `DATA-SCHEMA.md`
section 6.2 and make `build` refuse to overwrite a `reviewed: true` trait, the
same rule as `08_export.py promote`.

## 2. Conventions

Section 2 of `docs/DATA-SCHEMA.md` applies unchanged: UTF-8, 2-space indent,
camelCase, `additionalProperties: false` everywhere, ASCII-normalised text,
every record carries `source`. Two additions:

- The canonical serializer for race files is `canonical_dumps` in
  `pipeline/validate_races.py` (it reuses `_dump` from `validate.py`, so the
  two formats are identical). `validate_races.py --check` compares bytes;
  stage 12 writes through the same function.
- `traits` are sorted by `order`, not alphabetically. `order` is the row's
  position in the race box, which is the order a player sees.

## 3. ID conventions

| Kind | Rule | Example |
|---|---|---|
| race id | slug of the race name; equals the file stem. The nine seen on stream are `human dwarf night-elf gnome skyborne orc undead tauren troll`; another id only warns (`UNKNOWN-RACE`) | `night-elf` |
| variant id | slug of the variant's distinguishing words, without the race name | `high-order`, `windshaper` |
| trait id | slug of the trait name with the `(Passive)` suffix removed; unique per race file | `elunes-light`, `sword-specialization` |
| class id | as in `DATA-SCHEMA.md` | `paladin` |
| icon | `crop-<trait id>` while the icon is only a crop | `crop-walk-on-air` |

Slug rule and regex are `DATA-SCHEMA.md` section 3 (one implementation,
`wowtalents.text.slug`).

## 4. Race file, field by field

| Field | Type | Req | Description |
|---|---|---|---|
| `$schema` | string | no | `"../schema/race.schema.json"`, editor support only |
| `schemaVersion` | integer | yes | `1`. |
| `race` | race id | yes | Must equal the file name stem. |
| `raceName` | string | yes | Display name, e.g. `"Night Elf"`. |
| `faction` | enum `alliance`, `horde`, `neutral` | yes | `neutral` only for a race the picker shows in both columns (Skyborne). |
| `dataSource` | enum `video`, `datamined`, `mixed`, `manual` | yes | Dominant provenance; per-trait truth is `source.kind`. |
| `generatedAt` | string, RFC 3339 | yes | When stage 12 wrote the file. |
| `variants` | array of Variant | no | Present iff the race has faction variants. At least 2, one per faction. |
| `classes` | array of class id, sorted | yes | Union over the variants. **Empty means the class bar was never read**, not "no classes". |
| `classesSource` | Source | no | `panel: "class-bar"`, `reader: "opencv-classbar"`. |
| `lore` | string | no | The lore paragraph as shown. Only for a race without variants; variants carry their own. |
| `loreComplete` | boolean | iff `lore` | `false` when the paragraph ran past the box edge. |
| `loreSource` | Source | iff `lore` | |
| `traits` | array of Trait | yes | Sorted by `order`. |
| `complete` | boolean | yes | See section 4.3. |
| `notes` | array of string | no | Caveats shown in the UI footer. |

### 4.1 Variant

| Field | Type | Req | Description |
|---|---|---|---|
| `id` | variant id | yes | |
| `name` | string | yes | As shown at the top of the box, e.g. `"Windshaper Skyborne"`. |
| `faction` | enum `alliance`, `horde` | yes | Unique across the variants. |
| `classes` | array of class id, sorted | yes | The variant's own class bar. The two Skyborne variants differ: High Order has Mage, Windshaper has Shaman. |
| `lore` | string | no | |
| `loreComplete` | boolean | iff `lore` | |

### 4.2 Trait

| Field | Type | Req | Description |
|---|---|---|---|
| `id` | trait id | yes | Unique per file. |
| `name` | string, 1..60 | yes | Exactly as shown, without `(Passive)`. |
| `kind` | enum `active`, `passive` | yes | `passive` iff the name carried `(Passive)`. |
| `order` | integer >= 0 | yes | 0-based row position in the box, stitched from the overlapping scroll positions (section 6). Unique per file, no gaps. |
| `variants` | array of variant id | iff the file has `variants` | Which variants show this trait. Shared traits list both. |
| `description` | string, 1..400 | no | The gold text after the colon, as shown. **Absent** when the trait is known only by name; `source.note` must then say why. There are no rank templates: a racial has one rank and no `{n}` placeholders. |
| `icon` | string | no | `crop-<id>` while `iconSource` is `crop`. |
| `iconSource` | enum `classic`, `crop`, `datamined`, `manual` | no | Stage 12 only writes `crop`; racial icons were never matched against the Classic icon set (stage 9 runs on talents). |
| `iconCrop` | repo-relative path | iff `iconSource == "crop"` | 36x36 PNG under `data/review/races/`. |
| `classic` | object | yes | Section 4.4. |
| `tags` | array of string | no | `new`, `reworked`, `classic-unchanged`, mirroring `classic.status`. |
| `source` | Source | yes | Section 4.5. |

### 4.3 `complete`

`true` only when, for **every** variant of the race, some frame showed the box
scrolled to the top (the race name above the first trait) **and** some frame
showed the lore paragraph (below the last trait). Those two anchors are what
proves no row was missed in the middle: the scroll positions overlap, so the
stitched list is the whole list. `false` means a row may be missing and the UI
must say so.

### 4.4 `classic`

| Field | Type | Req | Description |
|---|---|---|---|
| `status` | enum `new`, `changed`, `same`, `unknown` | yes | |
| `classicName` | string | iff `status` is `changed` or `same` | The Classic Era racial this one corresponds to. |
| `classicText` | string | with `classicName` | The Classic effect, **paraphrased from memory**. Never quote it as game text. |
| `note` | string | no | Why the verdict, then always the unverified warning. |

`new` is the only verdict the data supports on its own: the name does not occur
in the Classic racial list for that race. `same` and `changed` are hand
verdicts from `data/prior/classic-era/racial-diff.json`, because the Classic
side is a paraphrase and a text diff of a paraphrase says "changed" every time.
A matched name with no hand verdict is `unknown`, never a guess.

Both prior files carry `"verified": false`. Replace them the moment a sourced
Classic racial list or a DB2 dump exists; the trait records need no change,
only a rebuild.

### 4.5 Source

As `DATA-SCHEMA.md` section 4.5, minus the talent-only fields (`talentId`) and
plus one:

| Field | Type | Req | Description |
|---|---|---|---|
| `kind` | enum `video`, `datamined`, `manual` | yes | |
| `video`, `t`, `frame`, `crop` | | iff `kind == "video"` | As for talents. `crop` points at the trait row crop, or at `_panel.png` when no single row could be cut. |
| `panel` | enum `race-panel`, `class-bar`, `spellbook-general` | no | **Which piece of UI the reading comes from.** `spellbook-general` means the racial was read from the spellbook's General page, which shows a name and a "Racial"/"Racial Passive" subtitle but no description. |
| `confidence` | number 0..1 | iff `kind == "video"` | Section 6. |
| `reader` | string | iff `kind == "video"` | Model label, or `opencv-classbar` for the class list. |
| `readings` | array | no | The individual passes, for the review UI. |
| `reviewed`, `reviewedBy`, `reviewedAt`, `note`, `build` | | | As for talents. |

## 5. `data/races/matrix.json`

Derived from the race files by `12_races.py build`; never hand-edited. Shape in
`data/schema/race-matrix.schema.json`.

| Field | Type | Description |
|---|---|---|
| `classes` | array of class id | Class-bar order, left to right: warrior, hunter, mage, rogue, priest, warlock, paladin, druid, shaman. |
| `races[].classes` | array of class id | Must equal the race file's `classes`. |
| `races[].byVariant` | object | Per-variant lists where they differ. Their union must equal `classes`. |
| `races[].observed` | boolean | `true` exactly when `classes` is non-empty. |
| `races[].reportedElsewhere` | array of class id | Combinations a third party reported (`docs/research/2026-09-13-talent-system.md`). |
| `races[].agreement` / `disagreement` | string | The cross-check result. A disagreement is recorded, never silently resolved. |

## 6. How a trait record is produced

1. **Frame classification.** Both faction banners on screen means the race
   picker (`races.is_character_creation`). Checked against all 541 stage-0 probe
   minutes: it fires on exactly the character-creation minutes and nothing else.
2. **Which race.** The selected portrait's border ring is gold (~125 mean grey
   against ~58 for the others), and the two columns of five portraits are in a
   fixed order, so the race and the variant come from pixel positions, not from
   a reading.
3. **Panel states.** Frames are decoded at 2 fps by frame index (not by the
   `fps` filter, which hands back a frame up to a quarter second off and can
   attribute a box to the wrong race) and grouped into runs of one scroll
   position by dHash; the sharpest frame of each run is kept, then identical
   scroll positions are deduplicated across windows.
4. **Reading.** Each state's box goes to llama-server twice, at 3x and 2x
   upscale, with a JSON schema that returns an array of rows. Agreement of the
   two passes is the confidence: 1.0 identical, 0.7 same name and kind, 0.3
   otherwise, 0.0 if only one pass saw the row. One state per race also goes to
   the codex CLI; a third reading that agrees lifts a disagreeing pair to 0.85,
   one that disagrees with an agreeing pair caps the trait at 0.9.
5. **Fragments.** A row whose name has scrolled above the edge still shows an
   icon, so the reader files its tail as a trait ("Damage to Beasts: increased
   by 5%"). Such a record is contained in the row it came from, which is how
   `races.drop_fragments` recognises and removes it.
6. **Order.** Each state gives a window onto the list; the windows overlap, so
   a topological sort over the "directly above" pairs recovers the full order
   (`races.stitch_order`).
7. **Crops.** Trait icons are round discs in a fixed column; morphological
   opening separates them from the lore text that starts at the same x. Bands
   are aligned to rows only when the counts reconcile after peeling clipped
   rows off the ends, never by guessing.

## 7. Validation rules (`pipeline/validate_races.py`)

Exit code 1 on any error; warnings print and only fail with `--strict`.

Errors:

1. R1 File parses, validates against the schema, `schemaVersion == 1`.
2. R2 `race` equals the file stem; all ids are slugs.
3. R3 Trait ids unique; `order` unique.
4. R4 Variants have distinct factions; every trait of a race with variants
   names at least one existing variant, and no trait of a race without
   variants has `variants`.
5. R5 `classes` sorted, all known, and equal to the union over the variants.
6. R6 A trait without a `description` needs a `source.note`.
7. R7 `status: "new"` may not name a Classic counterpart; `same`/`changed` must.
8. R8 `source` conditional fields; `reviewed` implies `reviewedBy`/`reviewedAt`.
9. R9 Every `source.crop` and `iconCrop` exists; `iconCrop` iff `iconSource == "crop"`.
10. R10 `complete: true` needs traits.
11. R11 `lore` needs `loreComplete` and `loreSource`.
12. R12 The file equals the canonical serializer output (`--check`; a warning without it).
13. M1-M4 for `matrix.json`: no duplicate race, sorted classes, `observed`
    consistent, `byVariant` union equals `classes`, and every row matches the
    race file it names — plus every race file appears in the matrix.

Warnings:

14. R13 `confidence < 0.8` and not reviewed -> `NEEDS-REVIEW` (and the record
    joins the `--report` queue, as every unreviewed record does).
15. R14 `(Passive)` left in a name.
16. R15 A `complete` race with fewer than 3 or more than 8 traits.
17. `UNKNOWN-RACE`, `NO-CLASSES`, `ORDER-GAPS`, `TEXT-HYGIENE`,
    `INCOMPLETE-UNEXPLAINED`, `TAG-MISMATCH`, `PANEL-DESCRIPTION`, `ICON-NAME`.

CI equivalent of the talent command:

```bash
cd pipeline && uv run python validate_races.py --check ../data/races/*.json
```

## 8. What the web app reads

`data/races/<race>.json` and `data/races/matrix.json` are static JSON, loaded
the way `web/src/data/load.ts` loads class files. The app must:

- treat `classes: []` as "unknown", not "none", and use `observed` in the
  matrix for the same reason;
- show the `complete: false` caveat and every `notes[]` entry;
- show a trust line for any trait whose `source.reviewed` is `false` (all of
  them today), as the talent tooltip does;
- label `classic.classicText` as an unverified paraphrase wherever it shows it;
- render `iconCrop` PNGs directly (there is no icon file to fall back on) and
  fall back to the trait's initials when the crop is missing;
- key Skyborne's trait list on the selected variant, and show the class list of
  that variant rather than the union.

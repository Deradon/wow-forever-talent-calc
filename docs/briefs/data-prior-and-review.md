# Brief: Classic prior, rank anticipation, validation, review, DB2 import

For a fresh Claude Code session. Read `CLAUDE.md` and `docs/DATA-SCHEMA.md`
(normative) first. Facts below were verified on 2026-09-13 unless marked
*unverified*.

## (a) Classic Era prior dataset

Goal: for every Classic Era talent, name, tree, position, max rank, icon,
prerequisites and **rendered per-rank tooltip text**, in
`data/prior/classic-era/`.

Verified sources:

1. `https://nether.wowhead.com/classic/data/talents-classic` (HTTP 200,
   1.27 MB, `text/javascript`). Not bare JSON: the body is
   `WH.setPageData("wow.talentCalcClassic.classic.data", {...})` followed by
   more calls; parse with `json.JSONDecoder.raw_decode` after the first
   prefix. `talents[treeId][talentId] = {id,row,col,icon,ranks:[spellId per
   rank],requires:[{id,qty}]}`; `trees[treeId] = {id, description
   ("PaladinProtection"), role}`. 27 trees, 432 talents, 1357 rank spell ids,
   65 with prerequisites. **No names, no text.**
2. `https://nether.wowhead.com/classic/tooltip/spell/<spellId>` (HTTP 200,
   `application/json`): `{name, icon, tooltip (HTML), ...}`; the rank text is
   the `<div class="q">` inside `tooltip`. Checked 12282/12663 (Improved
   Heroic Strike r1/r2: "...by 1 rage point." / "...by 2 rage points."). One
   request per rank spell = 1357 requests.
3. wago.tools CSV export, `https://wago.tools/db2/<Table>/csv?build=1.15.9.69722`
   (latest `wow_classic_era` build per `https://wago.tools/api/builds`).
   Tables in (e). Structurally the same data, but `Spell.Description_lang`
   is a `$s1` template; rendering `$/10;s1`, `$5530d`, `$h` is a rabbit
   hole. Use it for numbers, not text.
4. `melv-n/wow-talent-calculator` `src/data/spells.json` (285 KB):
   `{name, icon, rank, description}` for exactly the 1357 rank spells,
   scraped from source 2 in 2023 (coverage checked: 1357/1357). No repo
   license; text is Blizzard's either way. `maladr0it/classic-talent-calculator`
   has per-class `data.ts` with tagged-template descriptions
   (`${[15,25,35]}`), also unlicensed, harder to parse.

Caveats: Wowhead's ToS page returns 403 to non-browser clients, so its
scraping clause is *unverified*; the nether endpoints answered plain `curl`.
Treat as tolerated, not permitted: 2 req/s, descriptive User-Agent, cache
forever, no hotlinking. wago.tools terms *unverified* (`/about` is 404).

Decision: `pipeline/fetch_prior.py` fetches sources 1 and 2 into
`data/prior/classic-era/`: `talents-classic.json` (parsed), `spells/<id>.json`
(raw tooltips) and derived `classic-talents.json`, per talent
`{classicTalentId, class, tree, name, row, col, maxRank, icon, spellIds,
requires, rankTexts, slots:[[numbers per rank]]}`. Source 4 is only a diff
check. Commit all of it (~1 MB); it is the reproducible input of every
`classic-prior` rank.

## (b) Rank anticipation

Input: a Forever talent with rank-1 text `T1`, `maxRank`, class. Output:
`ranks`, `ranksSource`, `ranksPrior`/`ranksNote`.

1. Extract numbers from `T1` in order: integers, decimals, `%` and
   `sec/min` units stay in the template; produce `description` with `{n}`
   slots and `slots1 = [numbers]`.
2. Candidates: Classic talents of the same class; score = max of rapidfuzz
   `token_ratio` on names and on number-masked templates; `maxRank`
   mismatch costs 10.
3. Take the best candidate `C` if score >= 85. Compute Classic's per-slot
   progression from `C.slots`: for each slot, differences `d_k = v_{k+1}
   - v_k`. Classify: `constant` (all d = 0), `arithmetic` (all d equal),
   `other`.
4. Apply per slot to Forever's rank-1 value `f1`:
   - `constant` -> repeat `f1`.
   - `arithmetic` with Classic rank 1 == `f1` -> copy Classic values.
   - `arithmetic` with Classic rank 1 != `f1` -> if `f1 / c1` is a clean
     ratio (0.5, 1.5, 2) scale Classic values by it; else `f1 + k*d` (same
     step, new base).
   - `other` -> copy Classic values only if `c1 == f1`; else manual.
5. Pluralisation slots ("point"/"points") are computed from the number,
   not copied.

Decision table (`ranksSource`, confidence written to `ranksNote`):

| Condition | ranksSource | Notes |
|---|---|---|
| `maxRank == 1` | `observed` | nothing to anticipate |
| match >= 95, `c1 == f1`, all slots constant/arithmetic | `classic-prior` | copy; high |
| match >= 85, slots arithmetic, base or ratio differs | `classic-prior` | scaled; `ranksNote` states the rule; medium; review-queue |
| match >= 85 but Classic slot is `other` and `c1 != f1` | `manual` | copy rank 1 into all ranks, note "needs manual ranks"; review-queue |
| no match, `T1` has exactly one numeric slot | `extrapolated` | `f1 * (k+1)`; low; review-queue |
| no match, 0 or >= 2 numeric slots | `manual` | review-queue |

Never extrapolate durations/cooldowns (slot followed by `sec`/`min`); those
go `manual`.
`pipeline/ranks.py`: pure function plus table tests with Improved Heroic
Strike (1/2/3), Improved Rend (15/25/35), Deflection (1..5).

## (c) `validate.py`

Implement `pipeline/validate.py` exactly per `docs/DATA-SCHEMA.md` section
10 (rules 1-19, error/warning split, `--strict`, `--json`, `--report`,
`--overrides`, `--check`). `jsonschema` (draft 2020-12) for rules 1-2,
hand-written checks for the rest; each rule returns `Finding(level, code,
path, message)` so the review UI and CI share output. Generate
`data/schema/class.schema.json` from a Pydantic model in `pipeline/model.py`,
commit it, diff in CI. Mirror it in `web/src/data/schema.ts` (Zod) with a
test that both accept the example class in schema doc section 11.

## (d) Human review workflow and UI

Flow: schema doc section 7. Build `tools/review/`: one static HTML page,
vanilla JS, plus `review_server.py` with `GET /class/<c>` (extracted +
overrides + findings) and `POST /override/<c>` (append). No build step.

Per record, ordered by ascending confidence, grouped by tree:

- Left: tooltip crop at 2x, icon crop, a `https://youtu.be/<video>?t=<t>`
  link, and the grid position on a small schematic.
- Middle: the tooltip rendered as the app will show it (name, `Rank 0/N`,
  rank-1 and next-rank text, prerequisites) plus this talent's validator
  findings.
- Right: an edit form with exactly the editable fields: `name`, `maxRank`,
  `description`, `ranks` (grid, one row per rank; toggle array/string
  form), `ranksSource`/`ranksNote`, `requires`, `icon`, `iconSource`,
  `row`/`col`, `tags`, `source.note`. Alternative readings from
  `source.readings` are one-click fills. A "pick Classic prior" search
  box lists the class's Classic talents and fills `ranks` via (b).
- Buttons: Accept (empty `set`), Save, Delete, Add missing talent, Skip.

Persistence: every action appends one override with `reason` (required;
Accept defaults to "accepted as read"), `by` (`REVIEWER` env var) and `at`
(server time). The server never touches `extracted/` or `talents/`; the
reviewer runs `export.py` afterwards. The UI shows unreviewed / needs-review
/ reviewed counts per class.

## (e) Datamined import (after 2026-09-17)

Source: `https://wago.tools/db2/<Table>/csv?build=<build>` once a Forever
build appears in `https://wago.tools/api/builds` (product code unknown;
`wow_classic_titan` is Titan Reforged/China, not Forever). Column headers
verified on Classic Era 1.15.9.69722; field docs at
`https://wowdev.wiki/DB/Talent` and `/DB/TalentTab`:

| Table | Columns used | Maps to |
|---|---|---|
| `TalentTab` | `ID, Name_lang, BackgroundFile, OrderIndex, ClassMask, SpellIconID` | tree `id` (slug of name), `name`, `order`, `datamined.talentTabId`; `ClassMask` bit -> class (2 = paladin); `SpellIconID` is a FileDataID |
| `Talent` | `ID, TierID, ColumnIndex, TabID, ClassID, SpellRank_0..8, PrereqTalent_0..2, PrereqRank_0..2, Flags` | `row`, `col`, tree, `spellIds` (non-zero ranks; count = `maxRank`), `requires[]`, `source.talentId` |
| `SpellName` | `ID, Name_lang` | `name` from `SpellRank_0` |
| `Spell` | `ID, NameSubtext_lang ("Rank 1"), Description_lang, AuraDescription_lang` | per-rank text template, e.g. `"...by $/10;s1 rage point."` |
| `SpellEffect` | `SpellID, EffectIndex, EffectBasePoints, EffectDieSides, EffectMiscValue_0` | slot numbers: value = `EffectBasePoints + EffectDieSides` (12282/12663/12664 give -11/-21/-31 with DieSides 1 -> -10/-20/-30, then `$/10;` -> 1/2/3) |
| `SpellMisc` | `SpellID, SpellIconFileDataID` | icon FileDataID |
| `ManifestInterfaceData` | `ID, FilePath, FileName` | FileDataID -> `Interface\ICONS\ability_rogue_ambush.blp` -> `icon` slug |

`pipeline/import_db2.py`: download the seven CSVs into
`pipeline/work/db2/<build>/`, join as above, render `$`-templates with a
small formatter (`$s1..$s3`, `$/N;sX`, `$*N;sX`, `$d`, `$h`, `$o1`; anything
else left unrendered and flagged), emit the class file in the standard
schema (`source.kind: "datamined"`, all ranks observed). TalentTab has no
page concept; if Forever adds a Secondary tab expect a new column or table
and map it by hand. Unrendered templates fall back to
`https://nether.wowhead.com/forever/tooltip/spell/<id>?dataEnv=Forever`
(Classic placeholder data today).

Deliverable order: fetch_prior -> ranks.py -> validate.py + schema ->
review UI -> import_db2 (stub with the Classic Era build as test input).

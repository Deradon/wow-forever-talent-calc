# Handover 2026-09-14: datamined importer (stage 10)

`pipeline/stages/10_import_db2.py` turns wago.tools DB2 CSV exports into class
files in our canonical schema. It was built and proven against Classic Era
`1.15.9.69722` as a stand-in for the Forever beta build expected 2026-09-17.
**On beta day only the build number changes.**

## 1. What works

| Command | Result on 1.15.9.69722 |
|---|---|
| `fetch --build <build>` | 10 CSVs, 12 MB, into `pipeline/work/db2/<build>/` + `manifest.json` (rows, bytes, sha256 per table) |
| `check --build <build>` | re-hashes the cache against the manifest |
| `build --build <build>` | 9 classes, 27 trees, **432 talents**, every file validated before it is written; 0 errors |
| `compare-prior --build <build>` | 432/432 matched, **1302/1357 = 95.95 %** of per-rank texts identical to the Classic prior |
| `diff --build <build>` | Markdown + JSON report against `data/talents/` |
| `promote --from datamined/<build>` | merge plan per class; writes only with `--apply` |
| `builds` | the wago.tools product/build list |

Everything reusable is in `pipeline/src/wowtalents/db2.py` (fetch, CSV loaders,
the join, the `$`-formatter renderer, template/slots, diff, compare-prior);
`pipeline/src/wowtalents/export.py` gained `merge_datamined` and
`run_validator_doc`. Tests: `pipeline/tests/test_db2.py` (36 tests — renderer,
join on a five-talent CSV fixture, fetch with a fake downloader, diff, merge).
`cd pipeline && uv run pytest -q` is green: **497 passed**.

Output of the proof run is committed at `data/datamined/1.15.9.69722/` with
`report/import.md`, `report/compare-prior.md` and `report/diff.md`.

Commands actually run (in `pipeline/`):

```bash
uv run stages/10_import_db2.py fetch  --build 1.15.9.69722
uv run stages/10_import_db2.py build  --build 1.15.9.69722
uv run stages/10_import_db2.py compare-prior --build 1.15.9.69722
uv run stages/10_import_db2.py diff   --build 1.15.9.69722
uv run python validate.py --check --no-files --no-encoding ../data/datamined/1.15.9.69722/*.json   # 0 errors
```

### Validation

`data/datamined/<build>/` is staging that no `data/encoding/v<N>.json` covers, so
`validate.py` grew a `--no-encoding` flag that skips rule 11 (and nothing else).
Everything else is checked in full, `--check` included, so the files are
byte-identical to `canonical_dumps`. 0 errors over all nine classes; the
warnings are real Classic quirks (`NONLINEAR-RANKS` on 8/16/25 and 1/2/3/4/6
progressions, `R18-TREE-TOO-SMALL` because a Classic tree holds 46-49 points and
the cap is 51, two `NEW-TALENT` infos for the renamed warlock talents).

### The join

Verified against the prior, per talent: **positions 0 differences, `maxRank` 0,
prerequisites 0, tree names and order 27/27.**

* `TalentTab.ClassMask` bit -> class; `OrderIndex` -> `tree.order`; `Name_lang`
  is the in-game tree name (the four names Wowhead spells differently are right
  in DB2).
* `Talent.TierID`/`ColumnIndex` -> `row`/`col`; non-zero `SpellRank_0..8` ->
  `spellIds`, their count -> `maxRank`.
* `PrereqTalent_0..2` -> `requires[]`. **`PrereqRank` is 0-based**: `rank =
  PrereqRank + 1`. For all 65 Classic Era edges that equals the target's
  `maxRank`, i.e. a Classic arrow always means "maxed" — which is what the
  video-era extractor assumed. Forever may use a partial rank; the importer
  stores whatever the column says, so nothing needs changing.
* Icon: `SpellMisc.SpellIconFileDataID` -> `ManifestInterfaceData` (rows under
  `Interface\ICONS\` only) -> lower-case file stem. 432/432 resolved. Where one
  does not, the record gets `inv_misc_questionmark` and a warning, and `promote`
  swaps in the video crop (section 9.2 of the schema).
* Talent id = slug of `SpellName.Name_lang`, unique **per class**, `-<treeId>`
  appended on a collision inside one class.

## 2. Formatter coverage

`db2.Renderer` renders `Spell.Description_lang` into the text the client shows.
"Uses" counts occurrences in the rendered text of the 1357 Classic Era rank
texts; `-` means supported but never exercised by Classic Era, so untested
against real tooltips.

| Token | Meaning | Source | Uses |
|---|---|---|---:|
| `$s1..$s9`, `$S1` | effect value `EffectBasePoints + EffectDieSides`, absolute | SpellEffect | 1247 |
| `$d`, `$<id>d` | duration, "30 sec" / "2 min" | SpellMisc.DurationIndex -> SpellDuration | 202 |
| `$/N;`, `$*N;` | divide / multiply the value that follows, chainable | - | 187 |
| `$<id>s1` | `$sN` resolved against another spell | SpellEffect | 164 |
| `$h` | proc chance | SpellAuraOptions.ProcChance | 124 |
| `$n`, `$u` | proc charges / cumulative aura | SpellAuraOptions | 27 |
| `$o1`, `$o2` | periodic total = value x ticks | SpellEffect + duration | 9 |
| `$a1` | radius | SpellEffect.EffectRadiusIndex_0 -> SpellRadius | 7 |
| `$t1` | aura period in seconds | SpellEffect.EffectAuraPeriod | 6 |
| `$lone:many;` | plural, chosen by the last number printed | - | 5 |
| `${expr}` | arithmetic over `+ - * / ( )` and the tokens above | - | 1 |
| `$?<cond>[a][b]` | conditional; rendered as the **else** branch | - | 26 talents |
| `$m1`, `$M1` | min / max roll of the effect | SpellEffect | - |
| `$x1`, `$i` | chain targets, `EffectMiscValue_0` | SpellEffect | - |
| `$b` | line break (collapsed to a space by `clean_text`) | - | - |
| `$ghe:she;` | gender; always rendered **male** | - | - |

(`$m1`/`$M1`, `$x1`, `$i`, `$b` and `$g` do occur in Classic Era, but only
inside the *then* branch of a rune conditional, which we drop; they are covered
by unit tests instead.)

Two extra behaviours worth knowing:

* **`$sN` prints a range when `EffectDieSides > 1`**: Shield Slam effect 2 is
  `BasePoints 224, DieSides 11` and renders "225 to 235 damage", exactly as the
  client does. Without this the single number would be wrong on every
  damage talent.
* **`$?<cond>[a][b]` takes the else branch.** In Classic Era every condition is a
  Season of Discovery rune ("does the player know spell 446374"), and the else
  branch is the plain Classic wording, which is what a talent calculator wants.
  This is a guess about the *player*, not about the data, so all 26 affected
  talents are listed in `report/import.md` and get a `source.note`.

### Not supported

`${expr}` shapes that are not plain arithmetic; `$?cond` with a condition
that is not `[aAsS]<id>`; any `$` letter outside the table (`$c`, `$e`, `$p`,
`$w`, `$PCT`, `$b1`); a `$<id>` reference to a spell that has no row in this
build. Such a token is **left verbatim**, listed in `RenderResult.unsupported`,
written into the talent's `source.note`, and tabulated in
`report/import.md`. Classic Era 1.15.9 leaves exactly **two** of 432 talents
with an unrendered token:

* `rogue/assassination/relentless-strikes` — `$b1` (a token we have no source
  for; Wowhead shows 20 %).
* `rogue/combat/riposte` — `$19718d`, a duration on spell 19718, which has no row
  in any of the ten tables for this build.

Also not modelled: `EffectRealPointsPerLevel` scaling (see below) and
`SpellLevels`. Both would be the first thing to add if beta tooltips disagree.

## 3. The 55 rank texts that differ from the Classic prior (4.05 %)

All 55 are explained; none is a join error. The list is in
`data/datamined/1.15.9.69722/report/compare-prior.md`.

| Count | Talents | Cause |
|---:|---:|---|
| 39 | 13 | **The client text changed after the prior's snapshot.** The prior came from Wowhead + a spell dump taken before Classic renamed Succubus -> Sayaad, Enslave Demon -> Subjugate Demon and added Incubus to every demon list, and before the SoD-era rewording of Vindication and Wyvern Sting's duration. DB2 is right, the prior is stale. |
| 7 | 7 | **Level scaling.** Wowhead applies `EffectRealPointsPerLevel` (and probably a spell-level term); we print the raw DB2 base values. Pyroblast "141 to 187" vs "148 to 195", Ice Barrier 438 vs 455, also Blast Wave, Holy Nova, Shadowburn, Conflagrate, Seal of Command. |
| 3 | 1 | **Decimal formatting.** Improved Blizzard: we print `1.5 sec`, the prior `1.50 sec`. |
| 3 | 2 | **Plural.** We honour `$lsec:secs;` / `$lpoint:points;` (Permafrost "2 secs", Hemorrhage "1 combo point"); the prior always prints the singular resp. plural form. Ours follows the format string. |
| 2 | 2 | **Unrendered formatter** — the two talents above. |
| 1 | 1 | **Whitespace.** The prior joins `\r\n\r\n` with nothing ("shapeshifted.The act"); we insert a space. |

Non-text differences: 5 icons where the prior's Wowhead name carries a
`classic_` prefix that the real file name does not have, and the 2 renamed
warlock talents.

## 4. Beta-day runbook

### Step 0 — find the Forever build id

```bash
cd pipeline
uv run stages/10_import_db2.py builds --limit 40
uv run stages/10_import_db2.py builds --product classic      # narrow it down
```

This reads `https://wago.tools/api/builds`. As of 2026-09-14 the products are
`wow`, `wow_anniversary`, `wow_beta`, `wow_classic`, `wow_classic_beta`,
`wow_classic_era`, `wow_classic_era_ptr`, `wow_classic_ptr`,
`wow_classic_titan`, `wowlivetest`, `wowt`, `wowxptr`, `wowz` —
**no Forever product yet.** Expect it to appear as a new code, or under
`wow_classic_beta`, when the beta client ships on 2026-09-17. `wow_classic_titan`
is Titan Reforged / China, not Forever. The build string looks like
`1.15.9.69722`; the version is what `--build` takes, not the product code.

Cross-check against the Wowhead Forever calculator
(`https://www.wowhead.com/forever/talent-calc`) — while its data is still a
Classic placeholder, our datamined build will differ from it wholesale, which is
the signal that we have real data and Wowhead does not.

### Step 1-4 — import, verify, look, merge

```bash
cd pipeline
B=<the build>

uv run stages/10_import_db2.py fetch --build $B                      # ~12 MB, sequential, ~1.5 s apart
uv run stages/10_import_db2.py build --build $B                      # -> data/datamined/$B/
uv run python validate.py --check --no-files --no-encoding ../data/datamined/$B/*.json
less ../data/datamined/$B/report/import.md                           # formatter coverage FIRST

uv run stages/10_import_db2.py diff --build $B                       # vs data/talents/
less ../data/datamined/$B/report/diff.md

uv run stages/10_import_db2.py promote --from datamined/$B           # plan only
# read every DROPPED-REVIEW line, then:
uv run stages/10_import_db2.py promote --from datamined/$B --apply
uv run python validate.py --check ../data/talents/*.json
```

Between `promote` (plan) and `promote --apply`, do the encoding step if the plan
reports new, gone or renamed ids and v1 is frozen: new
`data/encoding/v2.json` covering every class plus
`data/encoding/migrations/v1-v2.json` (its `renamed` map is exactly what the
plan printed), and `dataVersion: 2` in every class file. While v1 is unfrozen,
`08_export.py --update-encoding` regenerates it in place instead. Schema
sections 8 and 9.2.

### What to check first when the numbers look wrong

1. `report/import.md`, "Unrendered formatters": a Forever-only `$` token shows up
   here as a table row, not as a silent wrong number. Add it to
   `Renderer._token_value` / `SUPPORTED_LETTERS`.
2. `report/import.md`, "Conditional text": if Forever uses `$?cond[a][b]` for
   something other than runes, the else-branch choice may be wrong for these
   talents — check one against an in-game screenshot before trusting the batch.
3. Column names: the loaders read **by name** and raise a `KeyError` naming the
   missing column, so a renamed DB2 column fails loudly at `load`, not silently.
4. `rules` is still `classic-prior` 51/5/10/60. If Forever's cap is not 51, edit
   `db2.RULES_CLASSIC` — no DB2 table carries it.
5. Pages: `TalentTab` has no page concept. If Forever ships a Secondary tab,
   expect a new column or table; today every tree lands on `primary`.

## 5. Decisions taken on the way

* **Staging directory, not `data/extracted/`.** The brief's sketch wrote
  `data/extracted/<class>.json`. That directory is the video pipeline's output
  and hand-editing it is forbidden; overwriting it would also destroy the record
  of what the video said, which is exactly what `diff` needs. `build` writes
  `data/datamined/<build>/` instead and `promote` does the merge.
* **`--no-encoding` rather than putting staging files into `data/encoding`.**
  Rule 11 requires the encoding version to list exactly a file's talent ids; a
  staging import cannot satisfy that and must not rewrite the frozen order to try.
* **Whole spell tables are loaded, not filtered.** Descriptions reference spells
  that are not talent ranks (`$14893s1`), so pre-filtering to the rank ids breaks
  cross-references. Classic Era costs ~100 MB of RAM for 31k spells; check this
  if Forever's `Spell.db2` is retail-sized.
* **The Classic prior is the test oracle.** It was built independently (Wowhead
  structure + a community spell dump), so agreeing with it on 432 talents and
  95.95 % of rank texts tests the join and the renderer, not our own arithmetic
  against itself. `compare-prior` stays as a regression check.

## 6. Next

1. Freeze `data/encoding/v1.json` (or consciously decide not to) **before** beta
   day: after `promote` the id set will move, and an unfrozen v1 silently
   invalidates every shared link.
2. If the first Forever build lands while reviews are still open, expect
   `promote` to drop them; the plan output is the re-review queue.
3. Optional accuracy work, in order of payoff: `EffectRealPointsPerLevel` +
   `SpellLevels` scaling (7 Classic talents), then whatever `report/import.md`
   lists for the real build.

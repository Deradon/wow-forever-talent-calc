# Round two review: data, code, performance (2026-09-14)

Reviewer: read-only combined pass (data auditor, code reviewer, performance
reviewer). Nothing under `data/`, `pipeline/` or `web/src/` was changed; the
only file written is this one. `web/dist/` was rebuilt (git-ignored).

Scope: everything that landed after round one's review commit `038080e`, i.e.
the handovers `fix-b-pipeline-data`, `rank-scaling`, `cell-attribution-audit`,
`races-data`, `spells-data`, `classic-diff-v2`, `races-web`, `spells-web`,
`ui-round2`. Baselines are `docs/reviews/2026-09-13-consolidated.md`,
`2026-09-13-data-audit.md`, `2026-09-13-code-and-docs.md` and
`2026-09-13-performance-a11y.md`.

Severity: **P1** = wrong data or broken behaviour reaching a player, fix before
sharing the link wider; **P2** = next pass; **P3** = nice to have.

## 1. Method

**Data.** 44 records were transcribed from their crops by an independent third
reader (`codex exec --ephemeral --skip-git-repo-check -i <crop>`, strict
"transcribe verbatim, do not correct spelling" prompt) and compared field by
field against the exported JSON: 11 racial traits over all 9 races, 18
spellbook list rows (all 10 review-queue rows plus 8 of the "new in Forever"
names), 15 spell tooltips (all 4 low-confidence ones plus 12 at confidence 1.0
- 11 of them chosen blind or by defect signature, 2 as controls).
Every disagreement was then read out of the crop by hand. Coverage records were
diffed against `data/extracted/spells.md` programmatically. The Classic diff was
sampled at 20 `text-changed` talents and additionally re-run over all 195 under
a deliberately aggressive normaliser. Review queues were recomputed from the
files rather than taken from the validators.

**Performance.** `npm run build` + `npm run preview` + Chromium via Playwright
with CDP throttling and per-request `responseBodySize` logging, mirroring
`2026-09-13-performance-a11y.md` §1 exactly so the two rounds compare. Byte
counts are exact; wall times are indicative (round one's hardware is not
recorded).

## 2. Headline

1. **Confidence 1.0 does not mean "correct" for spell tooltips.** 10 of the 12
   sampled `confidence: 1.0` tooltips carry at least one text error, all of
   them the *same* systematic reader defects round one catalogued for talents
   (comma read as full stop, spurious capital I). Round one's equivalent
   figure for talents was 0 errors in 68 confidence-1.0 records. Work package
   B1's shape-aware reader merge was never applied to stage 11.
2. **Four fabricated spell records are published as "new in Forever".** All
   four sit at confidence 0.0, all four are tagged `new`, and
   `web/src/data/spells-index.json` counts them, so the site's headline is 16
   new spell names where the evidence supports 12.
3. **The racial dataset is clean.** 11 of 11 sampled traits match their crops
   exactly on name, description and kind; 0 traits below 0.8; matrix and race
   files agree on every row.
4. **The review queues are exactly what the handovers claim** - 6 talents and
   10 spell rows - but 4 low-confidence spell *tooltips* are in no queue at
   all, because `validate_spells.py` never looks inside `tooltips[]`.
5. **The Classic diff holds up.** 16 of 20 sampled `text-changed` verdicts are
   real rewrites; 5 of all 195 are normalisation misses (plural, hyphen,
   article), one of which hides a genuine value change behind "Reworked."
6. **`12_races.py build` can publish an empty race file and then delete that
   race's committed crops, with exit code 0** - and the emptied file passes the
   schema, the validator and CI (K-1).
7. **The test that is supposed to catch stale generated files cannot fail**:
   the vite plugin regenerates them from `config()`, and vitest loads the same
   config (K-2). A `STALE-MARKER` injected into `classes-index.json` passed
   11/11 and was silently rewritten.
8. **Round one's three big bundle findings are fixed** - zod gone, crop
   registry -92 %, landing no longer pulls nine class chunks. First load is
   24.5 % smaller and time-to-interactive improved 15-49 % on every condition
   round one measured. But `dist/` grew 44 %, the entry stylesheet's gzip
   doubled, `classic-diff.json` still inlines all nine classes into the entry
   chunk (K-17), and the review crop registry is now pulled onto the player
   route by the tooltip (K-18).

Also: round one's E7 and E8 **regressed** (`sys.path.insert` 22 -> 36; nine
helpers duplicated between the two new stages), A2 and the `codec.ts` findings
are untouched and now reachable by paste as well as by link (K-3), `npm run e2e`
exits 1 on an all-green suite (K-28), and `CLAUDE.md` §State plus
`docs/PLAN.md` §"Immediate next actions" both still say 0 talents reviewed and
77 in the queue against a real 57 and 6 (C-1, C-2).

## 3. Measurements

### 3.1 Build output

| Group | Round 1 | Round 2 | Delta |
|---|---:|---:|---:|
| `dist/` files | 1291 | 1471 | +180 (+13.9 %) |
| `dist/` raw bytes | 19,756,339 | 28,428,192 | **+8,671,853 (+43.9 %)** |
| Crop PNGs (files / bytes) | 966 / 18,320,951 | 1096 / 26,225,134 | +130 / +7,904,183 (+43.1 %) |
| Icons `icons/*.jpg` | 312 / 582,566 | 320 / 598,203 | +8 / +15,637 |
| Main chunk `index-*.js` raw | 493,984 | 411,674 | **-82,310 (-16.7 %)** |
| Main chunk gzip | 137,308 | 119,948 | **-17,360 (-12.6 %)** |
| Class talent chunks (9) raw / gzip | 344,644 / 63,741 | 346,624 / 64,058 | +1,980 / +317 |
| CSS raw / gzip (all) | 13,207 / 4,010 | 45,344 / 11,501 | **+32,137 / +7,491 (+187 %)** |
| - entry CSS gzip | 4,010 | 7,865 | +3,855 (+96 %) |
| HTML + favicon | 987 | 2,524 | +1,537 |
| `robots.txt` + `sitemap.xml` | absent (404) | 719 B | new |
| Crop registry inside main chunk, raw | 92,392 (18.7 %) | **7,557 (1.8 %)** | **-84,835 (-91.8 %)** |
| Same, gzip contribution | ~16,600 | **2,409** | **-14,191 (-85.5 %)** |
| zod in the client | ~100 kB min / ~25 kB gzip | **absent** | removed |
| `npm run build` wall | 2.8 s | 3.83 s | +1.03 s (indicative) |
| JS chunks in `dist/assets` | ~11 | 46 | +35 |

### 3.2 First load over the network (cold cache, Chromium)

| Route | Req R1 | Req R2 | Bytes R1 | Bytes R2 | Delta |
|---|---:|---:|---:|---:|---:|
| `#/` (landing) | 11 subres | 13 subres | 202,000 | **152,439** | **-49,561 (-24.5 %)** |
| `#/paladin` | 55 | 66 | 248,000 | 264,001 | +16,001 (+6.5 %) |
| `#/review/paladin` (first viewport) | 19 | 29 | 558,000 | **462,083** | **-95,917 (-17.2 %)** |
| `#/review/paladin` (full scroll) | - | 112 | 2,044,723 | 2,123,053 | +78,330 (+3.8 %) |

Routes that did not exist in round one:

| Route | Requests | Bytes | Of which text | Of which images |
|---|---:|---:|---:|---:|
| `#/races` | 18 | 163,021 | 145,438 | 17,583 (9 jpg) |
| `#/races/human` | 21 | 173,102 | 146,805 | 26,297 (7 jpg, 4 png) |
| `#/spells` | 16 | 157,221 | 141,533 | 15,688 (8 jpg) |
| `#/spells/paladin` | 59 | **339,369** | 147,320 | 192,049 (48 png, 1 jpg) |
| `#/changes` | 16 | 157,243 | 139,660 | 17,583 (9 jpg) |
| `#/changes/paladin` | 18 | 182,487 | 164,904 (incl. `classic-text` 17,993) | 17,583 |
| `#/paladin?embed=1` | 57 | 246,418 | 142,921 | 103,497 |

### 3.3 Time to interactive

| Condition | load R1 | load R2 | FCP R1 | FCP R2 | Interactive R1 | Interactive R2 |
|---|---:|---:|---:|---:|---:|---:|
| No throttle, `#/` | 67 | **42** | 96 | **92** | 138 | **50** |
| Fast 3G, `#/` | 1192 | **1002** | 1312 | **1028** | 1331 | **1010** |
| Fast 3G, `#/paladin` | 1189 | **1001** | 1272 | **1032** | 1708 | **1243** |
| 4G, `#/paladin` | 442 | **286** | 536 | **336** | 847 | **431** |
| Fast 3G + 4x CPU, `#/paladin` | - | 1072 | - | 1160 | - | 1480 |

### 3.4 Data and test suites

| Measurement | Round 1 | Round 2 |
|---|---:|---:|
| Talents / reviewed / below 0.8 | 469 / 0 / 77 | 469 / **57** / **6** |
| Racial traits / below 0.8 | - | 37 / **0** |
| Spell rows / below 0.8 | - | 327 / **10** |
| Spell tooltips / below 0.8 | - | 112 / **4 (in no queue)** |
| Orphaned PNGs under `data/review` | 430 | **12** (11 are `_page`/`_panel`/`_general` context crops + the tinker fixture) |
| `validate.py` errors / warnings | - | 0 / 97 |
| `validate_races.py` | - | 0 / 0 |
| `validate_spells.py` | - | 0 / 12 |
| `uv run pytest` | - | 461 passed, **5.8 s** |
| `npx vitest run` | 281 tests | **542 tests, 26 files, 2.1 s** |

### 3.5 Performance regressions

| # | Sev | Regression | Numbers | Cause |
|---|---|---|---|---|
| R-1 | P2 | `dist/` grew 43.9 % | 19.76 -> 28.43 MB; crop PNGs 966 -> 1096 files | Race and spell review crops, plus a new class of decorative PNGs that did not exist in round one (`_header` 28 files, `_panel` 9, `_classbar` 9, `_general` 1 = 2,663,904 B, ~31 % of the growth). Frame-crop average 34.4 -> 37.2 kB, max 92 -> 167 kB. Round one's **P-4 (emit WebP/AVIF)** is still open and is now worth ~20 MB. |
| R-2 | **P2** | Entry CSS gzip nearly doubled, on the critical path | 4,010 -> 7,865 B gzip (+96 %); all CSS 4,010 -> 11,501 | `tailwindcss` + `@tailwindcss/vite` were added since round one and the entry sheet is not split (32,782 B raw). Route CSS (`RacesPage` 6,489, `SpellsPage` 3,491, `ChangesPage` 2,582) **is** correctly split. The +3,855 B eats 22 % of the 17,360 B gzip won back by dropping zod. Fix: make sure Tailwind's content globs cover only `src/`, and check whether the preflight/reset is needed at all next to the hand-written `index.css`. |
| R-3 | P3 | `#/paladin` heavier | 55 -> 66 requests, 248 -> 264 kB | 9 extra icon JPGs (17,583 B) from the new class-navigation bar; `?embed=1` drops exactly those 9 and lands at 57 / 246 kB. Round one's **P-5 (icon sprite or WebP)** is still open and a class page now makes 48 icon requests. |
| R-4 | P3 | Build wall +37 % | 2.8 -> 3.83 s | `vite build` is only 654 ms of it; the rest is `tsc -b` over a larger project plus `gen-data-index.mjs` running in **both** `config()` and `buildStart()`, i.e. twice per build. Indicative - different machine. |
| R-5 | P3 | Fully scrolled review page | 1.95 -> 2.02 MiB | Same cause as R-1; paladin's frame crops were re-captured larger. |
| R-6 | P3 | `#/review/paladin` first viewport request count | 19 -> 29 | A split, not a growth: bytes fell 17 %. Only a concern under the `max-age=600` revalidation storm of round one's still-open **P-7**. |
| R-7 | P3 | `#/spells/<class>` is the heaviest non-review route | 59 requests / 339 kB, of which 48 spell-crop PNGs / 190 kB | New route. Same fix as P-4/P-5: ship the spell icon crops as WebP or a per-class sprite. |

Round one findings now **resolved**: P-1 (landing no longer loads nine class
chunks), P-2 (crop registry -92 %), P-3 (zod gone), S-3 (`robots.txt` and
`sitemap.xml` ship). S-1 is partly done - OG, Twitter and canonical tags are in
`index.html`, but there is no `og:image` and the card is `summary`, not
`summary_large_image`. Still open: S-2, P-4, P-5, P-6 (the HTML still ships an
empty `#root`), P-7.

## 4. Data findings

### 4.1 The reader defects round one fixed for talents were never fixed for spells

**D-1 (P1).** `pipeline/stages/11_spellbook.py` merges its two VLM passes by
agreement only, not by shape. Consolidated work package B1 ("second reader wins
on case, punctuation and `%`") was implemented for stage 5 and never reached
stage 11, so the same two defects round one counted 27 and 14 times in the
talent data are back in the spell tooltips, at confidence 1.0, because both
passes make the identical mistake and agreeing on a mistake scores 1.0.

Repository-wide, machine-detectable, over the 112 tooltips: **6 descriptions
where a comma was read as a full stop**, **5 where a lower-case word was
capitalised as `I`**. Every one of those 11 that fell in the sample was
confirmed against its crop; none was a false positive.

Reading the crops found four more that no regex can find: a misspelling
(`mage/dampen-magic` "Dampons"), two footers whose wording does not match the
crop at all (`druid/prowl`, `rogue/shadowmeld`), and a list flattened without a
separator (`mage/languages`). So the 11 are a floor, not the count. All are
listed with evidence in §7.

Fix: port the shape-aware merge from `pipeline/src/wowtalents/merge.py` to
`spells.py`'s tooltip merge - that is the only fix that reaches the four
undetectable ones. At minimum add the two cheap post-checks of V-5 to
`validate_spells.py` so a reviewer sees the 11.

### 4.2 Four fabricated spell records are published as "new in Forever"

**D-2 (P1).** All four are the ones `docs/handover/2026-09-13-spells-data.md`
§2 itself calls "readings the model invented ... the first thing a reviewer
should delete". They were never deleted, they carry `classic.status: "new"` and
`tags: ["new"]`, and `web/scripts/gen-data-index.mjs:799` counts
`status === 'new'` with no confidence filter, so `spells-index.json` publishes
`new: 2` for druid and `new: 3` for mage. The site's "16 new spell names" is
**12 plus four OCR artefacts**.

| Record | Crop says | Why it is wrong |
|---|---|---|
| `data/spells/druid.json` `shapeshift` | "Bear Form" with the subtitle "Shapeshift" | "Shapeshift" is the school subtitle of Bear Form, not a spell. Its `source.crop` is `_page-druid-20923.png`, a whole-page composite - the record has no row crop at all. |
| `data/spells/mage.json` `evocation-dampen-magic` | "Dampen Magic", Rank 3 | Two rows merged into one name. The real row already exists as `dampen-magic` at confidence 1.0 in the same tab, so this is a duplicate under a fabricated name, and its `new` verdict is false (Dampen Magic is Classic). |
| `data/spells/shaman.json` `reincarnation-passive` | "Reincarnation" + "Passive" subtitle | The `(Passive)` subtitle was glued into the name. There is **no** `reincarnation` record, so the real spell exists only under the wrong name, and `new` is false. |
| `data/spells/warrior.json` `rummel-whirlwind` | "Whirlwind" | "Rummel" is hallucinated. `whirlwind` already exists at confidence 1.0 in the same tab - duplicate under a fabricated name, `new` false. |

Fix: delete the four records (an overrides mechanism for spells does not exist
yet - see D-9), and until then filter `status === 'new' && confidence >= 0.8`
in `gen-data-index.mjs` so the headline number cannot be inflated by a record
the data itself flags as unreliable.

Related: `validate_spells.py:380 rule_14_kind` catches a `Rank N` subtitle
glued into a name but not a `(Passive)` one, which is exactly how
`reincarnation-passive` got through. One extra pattern fixes it.

### 4.3 `ranksSeen` values with no supporting reading

**D-3 (P2).** 16 records carry a `ranksSeen` entry that no stored
`source.readings[]` entry mentions. For 11 of them the class had
"Show all spell ranks" on, so the value plausibly comes from a sibling row
whose reading was not kept - defensible, but then `readings[]` is not the
evidence the schema says it is. For **5** there is no such excuse:

| Record | `ranksSeen` | reading ranks | `showAllSpellRanks` |
|---|---|---|---|
| `data/spells/rogue.json` `shoot-crossbow` | `[1]` | none | not observed |
| `data/spells/rogue.json` `shoot-gun` | `[1]` | none | not observed |
| `data/spells/rogue.json` `throw` | `[1]` | none | not observed |
| `data/spells/mage.json` `remove-lesser-curse` | `[3]` | none | not observed |
| `data/spells/shaman.json` `frostbrand-weapon` | `[3]` | none | on (single state) |

The three rogue rows were checked against their crops: no rank is printed on
any of them. Their `ranksSeen: [1]` is not in the evidence, and the page
renders it. The same three also carry `confidence: 0.7` while both stored
readings agree exactly (same name, both `rank: null`), which by the handover's
own rule is a 1.0 - so the confidence is not explained by the readings either.

Fix: make `build` derive `ranksSeen` only from readings that carry a rank, and
add a validator rule asserting `ranksSeen ⊆ {readings[].rank}` unless
`showAllSpellRanks == "on"`.

### 4.4 Four low-confidence tooltips are in no review queue

**D-4 (P1).** `pipeline/validate_spells.py:368-378 rule_13_confidence` iterates
`doc["spells"]` and reads `s["source"]["confidence"]` only. It never descends
into `s["tooltips"][j]["source"]`. Four tooltips sit below the 0.8 threshold and
appear in neither `--check` nor `--report`:

| Record | Tooltip confidence |
|---|---:|
| `data/spells/mage.json` `blink` | 0.3 |
| `data/spells/mage.json` `conjure-food` | 0.3 (second tooltip) |
| `data/spells/mage.json` `cone-of-cold` | 0.3 |
| `data/spells/druid.json` `cower` | 0.7 |

Two of the three 0.3 tooltips do contain errors (§7). The 0.8 threshold is the
project's whole review contract; a whole field of 112 records escaping it is the
kind of gap that makes "0 errors, 12 warnings" misleading.

Fix: extend `rule_13_confidence` over `tooltips[]` and add them to
`result.queue` with a `/spells/{i}/tooltips/{j}` path.

### 4.5 The talent review queue is exactly 6, the spell queue exactly 10

**Confirmed.** Recomputed from the files, not from the validators:

- Talents: 469 total, 57 `reviewed: true`, **6** unreviewed below 0.8 -
  `mage/frost/piercing-ice`, `paladin/holy/infusion-of-light`,
  `shaman/enhancement/rage-of-the-farseer`, `warlock/destruction/bane-of-havoc`,
  `warrior/arms/bloodthrill`, `warrior/fury/blood-crazed`, all at 0.70.
- Spell rows: 327 total, **10** below 0.8 (the four from D-2 at 0.0, the three
  rogue rows and `shaman/poison-cleansing-totem`, `shaman/tremor-totem` at 0.7,
  `warrior/slam` at 0.0).
- Racial traits: 37 total, **0** below 0.8.

Plus the 4 invisible tooltips of D-4. Nothing else is low-confidence.

### 4.6 Anticipated percentages above 100 % still ship

**D-5 (P2).** Consolidated work package B6 asked to "cap **or** flag" values
above 100 %. The validator flags them (`R20-PERCENT-OVER-100`, 5 hits) and
nothing caps them, so the tooltip tells a player that
`warrior/fury/enrage` gives a **150 % chance** and
`paladin/holy/illumination` a **250 %** one. There is no guard anywhere in
`web/src/ui/tooltipText.ts` or `web/src/rules/`.

| Talent | Slot values |
|---|---|
| `data/talents/warrior.json` `warrior/fury/enrage` | 30 / 60 / 90 / **120** / **150** % |
| `data/talents/paladin.json` `paladin/holy/illumination` | 50 / 100 / **150** / **200** / **250** % |
| `data/talents/rogue.json` `rogue/subtlety/quietus` | 35 / 70 / **105** / **140** / **175** % |
| `data/talents/druid.json` `druid/feral-combat/predatory-strikes` | 50 / 100 / **150** % |
| `data/talents/hunter.json` `hunter/beast-mastery/improved-aspect-of-the-monkey` | 50 / 100 / **150** % |

Fix: in stage 6, when a proportional scaling of a `%` slot crosses 100, emit
`ranksSource: "manual"` with the ranks left at rank 1 (the `mage/shatter`
treatment that the consolidated review already accepted) rather than publishing
an impossible number. Three `R20-THRESHOLD-SCALED` talents
(`priest/shadow-magic/devouring-contagion`, `priest/shadow-magic/early-demise`,
`rogue/subtlety/quietus`) need the same treatment for the opposite reason: a
condition like "below 35 % health" must not scale at all.

### 4.7 Classic diff: the "reworked" verdicts are mostly real

**Sampled 20 `text-changed` talents** (seeded random over all 195 with
`textChange: "text"`), rendered at rank 1 on both sides and read by hand.
**16 are genuine rewrites** - added clauses (`druid/brutal-impact` gains a
cooldown reduction), added spell names (`druid/ferocity` gains Mangle),
whole re-designs (`shaman/stormstrike`, `druid/swiftmend`). The talent prior is
real sourced Wowhead text (`data/prior/classic-era/SOURCES.md`), not the
hand-written paraphrase the racial prior is, so these verdicts rest on real
Classic wording.

**D-6 (P2).** Re-running all 195 through a deliberately aggressive normaliser
(drop hyphens, plural `s`, and the articles `a/an/the/your/all/of`) finds
**5 normalisation misses**:

| Talent | Classic | Forever | The whole difference |
|---|---|---|---|
| `rogue/dual-wield-specialization` | "your offhand weapon by 10%" | "your off-hand weapon by 5%" | a hyphen - and because of it the real change (10 % -> 5 %) is reported as **"Reworked."** instead of **"Values changed: 10% -> 5%."** |
| `mage/frost-warding` | "the armor and resistances given" | "the Armor and resistance given" | a plural |
| `druid/gift-of-nature` | "all healing spells" | "all your healing spells" | one article |
| `hunter/survivalist` | "Increases total health" | "Increases your total Health" | one article |
| `warrior/deep-wounds` | "cause the opponent to bleed" | "cause your opponent to Bleed" | one article |

`dual-wield-specialization` is the only one that actually costs the player
information; the other four say "Reworked" for a word that is not a rework.

Fix in `web/scripts/gen-data-index.mjs:200 normalizeText`: strip `-` (line 211
currently keeps it in the allowed character class) before comparing, and fold
`your`/`the` when they are the sole difference. Keep the raw sentences for
`compactDiff`, which already renders from raw text - only the classifier needs
the stronger normaliser.

**D-7 (P3).** `docs/handover/2026-09-13-classic-diff-v2.md` §2 publishes the
count table `145 / 123 / 18 / 111 / 16 / 56 / 108`. The shipped
`web/src/data/classic-diff.json` says `145 / 81 / 26 / 127 / 22 / 68 / 108`,
because `cell-attribution-audit` later redefined `moved` as row-or-tree only.
The newer handover is right and `ui-round2` quotes the new numbers, but the
classic-diff-v2 table is now wrong and is the one a reader finds first when
searching for "how many were reworked". Add a superseded-by line.

### 4.8 Coverage records agree with `data/extracted/spells.md`

**Confirmed, no defects.** All eight classes match on `entriesRead`,
`tooltipsRead`, `tabsSeen`, `tabsMissing`, `pagesSeen`, `showAllSpellRanks` and
minimum confidence; the per-entry table has exactly 327 rows and the per-class
row counts match the JSON one for one. The two apparent tooltip mismatches
(mage 32 vs 29, shaman 9 vs 8) are the four spells that carry two tooltips
(`mage/arcane-explosion`, `mage/conjure-food`, `mage/teleport-stormwind`,
`shaman/flame-shock`); total is 112 either way.

**D-8 (P3).** `coverage.states` and `len(coverage.windows)` disagree for druid
(15 vs 14) and shaman (16 vs 15) - two states share a stream second and the
window list dedupes. Harmless, but nothing in `validate_spells.py`
`rule_5_coverage` relates the two, so a genuinely truncated window list would
not be caught either. Add `len(windows) <= states` as a warning.

### 4.9 The racial dataset is clean

11 traits over all 9 races were transcribed from their crops: **11 of 11 match
exactly** on name, description text and `kind`, including the two traits the
survey had never seen (`dwarf/big-game-hunter`, `troll/rapid-regeneration`) and
two Skyborne traits. `matrix.json` agrees with every race file on `classes` and
`faction`; 37 traits, 14 new / 16 changed / 7 same, exactly as the handover
claims; `validate_races.py` reports 0 errors and 0 warnings.

Two observations, neither an error:

- 27 of the 37 descriptions do not end in a full stop. Verified against the
  crops: the character-creation box genuinely prints no terminator. The talent
  validator's `R17-TERMINATOR` rule must therefore **not** be copied into
  `validate_races.py`.
- **D-9 (P3).** Row crops vary from 48 px to 167 px tall against a ~50 px row
  pitch (`data/review/races/troll/regeneration.png` is 286x167), so a "row"
  crop can contain two or three neighbouring rows plus lore. The reviewer sees
  the right row plus noise, which is safe but makes the review slower. Tighten
  the crop to the row band, or draw the band on the crop.

### 4.10 Still missing: an overrides mechanism for races and spells

**D-10 (P2).** Both `docs/handover/2026-09-13-races-data.md` §6.1 and
`docs/handover/2026-09-13-spells-data.md` §7.1 flag that
`data/overrides/races/` and `data/overrides/spells/` do not exist and that the
next rebuild will discard any correction. That is still true, and it now blocks
every fix in D-1, D-2 and D-3: there is no way to record a correction to the
364 race+spell records other than hand-editing generated files, which
`CLAUDE.md` forbids. This is the prerequisite for the whole non-talent review
round and is estimated at an hour for both.

## 5. Validator gaps

Tested by construction against the live data, then by reading the rules.

| # | Sev | Gap | Where | Evidence |
|---|---|---|---|---|
| V-1 | **P1** | Tooltip confidence is never checked or queued | `pipeline/validate_spells.py:368` | 4 tooltips below 0.8 invisible (D-4) |
| V-2 | P2 | Duplicate spell **names** are not checked; the uniqueness key is `(id, sorted(ranksSeen))` | `pipeline/validate_spells.py:196-206` | `evocation-dampen-magic` and `dampen-magic` are the same spell under two names and both pass. Also `(id, [1])` and `(id, [1,2])` are different keys, so overlapping rank sets pass. Add a name-level duplicate warning and an overlap check. |
| V-3 | P2 | `ranksSeen` is checked for sort order but not for duplicates, positivity, or support in `readings[]` | `pipeline/validate_spells.py:245-252` | D-3; `sorted(r) != list(r)` passes `[2, 2]` |
| V-4 | P2 | `rule_14_kind` catches `Rank N` glued into a name but not `(Passive)` / `Passive` | `pipeline/validate_spells.py:380-383` | `shaman/reincarnation-passive` |
| V-5 | P2 | Text hygiene only looks for the characters `\| \ ~` | `pipeline/validate_spells.py:352`, `validate_races.py:270`, `validate.py:873` | Misses all 11 defects of D-1. Add: a full stop followed by whitespace and a lower-case letter; a bare capital `I` between two lower-case words; a description ending without a terminator (for spells only - see §4.9). |
| V-6 | P3 | `coverage.windows` is not related to `coverage.states` | `pipeline/validate_spells.py:222-243` | D-8 |
| V-7 | P2 | `id == slug(name)` is checked by **no** validator - all three check only the slug *shape* | `validate.py:383`, `validate_races.py:190`, `validate_spells.py:188` | Only bites a hand edit, which is exactly what validators are for |
| V-8 | P2 | `rule_10_complete`'s explanation guard is dead in both new validators | `validate_races.py:340`, `validate_spells.py:341` | K-10: `"not"` matches inside `"nothing"`, and every race file carries a note containing "nothing" |

Two things the task asked about are **not** gaps:

- **Traits without `kind`** is enforced: `kind` is `required` in
  `data/schema/race.schema.json` `$defs/trait` and `spell.schema.json`
  `$defs/spell`, and `rule_1_schema` runs jsonschema first. Verified: 0 traits
  and 0 spells lack it.
- **Rank lists are monotonic** across the live data (0 unsorted, 0 duplicated
  in 327 spell records), and talent rank progressions are checked by
  `validate.py:796 rule_14_progression`. The only gap is the missing strictness
  noted in V-3.

The three validators also duplicate a large amount of structure - `Ctx`,
`err`/`warn`, the `--check/--report/--json/--strict` CLI, `canonical_dumps`,
the source-field rule and the file-existence rule are near-identical triplicates
across `validate.py`, `validate_races.py` and `validate_spells.py`. Round one's
"three slug implementations" finding was fixed for slugs; the validators are the
same pattern one level up. See the code section.

## 6. Privacy scan

**Verdict: clean.** All tracked files at HEAD (2095 files) and all 58 commit
messages were scanned.

- Zero `Claude-Session:` lines and zero `claude.ai/code/session` URLs in any
  commit message, including all 28 since round one. The rule is holding.
- No home paths, hostnames, e-mail addresses or API keys in tracked files.
  `~/Dev/llama.cpp` in `docs/briefs/pipeline.md` and
  `docs/handover/2026-09-13-llama-build.md` carries no username. The
  `reviewedBy: "deradon"` values in example and test fixtures, the
  `github.com/deradon/...` schema `$id`s and the Pages URL are the public
  repository identity, which `CLAUDE.md` permits.
- Everything added since round one - all of `data/races/`, `data/spells/`,
  `data/review/races`, `data/review/spells`, and the fifteen new handovers -
  is clean on a targeted re-grep. `source.frame` and `source.crop` values are
  all repository-relative; none starts with `/`.
- 25 PNG/JPG files under `data/review/**` and `web/public/**` were spot-checked
  with `strings` (no `exiftool` available); no embedded paths or author tags.
  A full EXIF pass is still worth doing once.
- Approximate VRAM/RAM figures in `docs/handover/2026-09-13-llama-build.md` and
  `docs/research/2026-09-13-extraction-pipeline.md` predate round one and were
  explicitly accepted there as non-identifying. No new instances.

**PR-1 (P2), the one actionable item.** The `commit-msg` hook that rejects
session links exists only in this checkout's `.git/hooks/commit-msg`. It is not
tracked, `core.hooksPath` is unset, and no setup script installs it, so a fresh
clone has no protection for the rule `CLAUDE.md` states most firmly. Ship it as
`.githooks/commit-msg` with `git config core.hooksPath .githooks` documented in
the README, or wire it into CI as a `git log` check on the pushed range.

## 7. Per-record data errors, with evidence

Every row was transcribed from the named crop by an independent reader and then
read by hand. "JSON" is the exported value; "crop" is what the pixels say.

### 7.1 Spell tooltips at `confidence: 1.0` (10 of 12 sampled are wrong)

| # | Record | Field | JSON | Crop | Evidence |
|---|---|---|---|---|---|
| E-1 | `data/spells/druid.json` `enrage` | description | "...over 10 sec**.** but reduces base armor..." | "...over 10 sec**,** but..." | `data/review/spells/druid/enrage.tooltip.png` |
| E-2 | `data/spells/druid.json` `prowl` | description | "prowl around**.** but reduces" | "prowl around**,** but reduces" | `data/review/spells/druid/prowl.tooltip.png` |
| E-3 | `data/spells/druid.json` `prowl` | footer | "but **on** a different stance" | "but **in** a different stance." | same crop |
| E-4 | `data/spells/hunter.json` `scare-beast` | description | "Scares a beast**.** causing it" | "Scares a beast**,** causing it" | `data/review/spells/hunter/scare-beast.tooltip.png` |
| E-5 | `data/spells/mage.json` `dampen-magic` | description | "**Dampons** magic used" | "**Dampens** magic used" | `data/review/spells/mage/dampen-magic.tooltip.png` |
| E-6 | `data/spells/mage.json` `dampen-magic` | description | "party member**.** decreasing" | "party member**,** decreasing" | same crop |
| E-7 | `data/spells/rogue.json` `shadowmeld` | description | "into the shadows**.** reducing" | "into the shadows**,** reducing" | `data/review/spells/rogue/shadowmeld.tooltip.png` |
| E-8 | `data/spells/rogue.json` `shadowmeld` | footer | "You haven't added this to your action bars" | "You haven't added this to your Action Bar yet." | same crop |
| E-9 | `data/spells/mage.json` `languages` | description | "languages: Common Gnomish" | the crop lists "Common" and "Gnomish" on **separate lines** | `data/review/spells/mage/languages.tooltip.png` - a list flattened with no separator |
| E-10 | `data/spells/hunter.json` `mine` | description | "with **Its** talons" | "with **its** talons" | `data/review/spells/hunter/mine.tooltip.png` |
| E-11 | `data/spells/mage.json` `conjure-water` | description | "Conjured **Items** disappear" | "Conjured **items** disappear" | `data/review/spells/mage/conjure-water.tooltip.png` |
| E-12 | `data/spells/mage.json` `armor-proficiency` | description | "proficient **In** the use" | "proficient **in** the use" | `data/review/spells/mage/armor-proficiency.tooltip.png` |
| E-13 | `data/spells/mage.json` `expansive-mind` | description | "Maximum Mana **Increased** by 5%." | "Maximum Mana **increased** by 5%." | `data/review/spells/mage/expansive-mind.tooltip.png` |

Clean at 1.0: `mage/conjure-food`, `shaman/stoneclaw-totem` - every field,
including the footer, matched verbatim.

### 7.2 Spell tooltips below 0.8

| # | Record | Conf | Error |
|---|---|---:|---|
| E-14 | `data/spells/mage.json` `blink` | 0.3 | "20 yards forward**.** unless" - crop says "forward**,** unless". `data/review/spells/mage/blink.tooltip.png` |
| E-15 | `data/spells/mage.json` `cone-of-cold` | 0.3 | "Targets **In** a cone **In** front" - crop says "in ... in" (two instances). `data/review/spells/mage/cone-of-cold.tooltip.png` |
| - | `data/spells/druid.json` `cower` | 0.7 | **clean**; every field including `requires: ["Cat Form"]` and the footer matched |

### 7.3 Spell list rows

| # | Record | Conf | Error |
|---|---|---:|---|
| E-16 | `data/spells/druid.json` `shapeshift` | 0.0 | fabricated; see D-2. Crop `data/review/spells/druid/_page-druid-20923.png` shows "Bear Form / Shapeshift" |
| E-17 | `data/spells/mage.json` `evocation-dampen-magic` | 0.0 | name is two rows merged; crop `data/review/spells/mage/evocation-dampen-magic.png` shows "Dampen Magic, Rank 3" |
| E-18 | `data/spells/shaman.json` `reincarnation-passive` | 0.0 | subtitle glued into the name; crop `data/review/spells/shaman/reincarnation-passive.png` shows "Reincarnation" + "Passive" |
| E-19 | `data/spells/warrior.json` `rummel-whirlwind` | 0.0 | "Rummel" hallucinated; crop `data/review/spells/warrior/rummel-whirlwind.png` shows "Whirlwind" |
| E-20 | `data/spells/rogue.json` `shoot-crossbow` | 0.7 | `ranksSeen: [1]`; crop prints no rank and neither reading carries one |
| E-21 | `data/spells/rogue.json` `shoot-gun` | 0.7 | as E-20 |
| E-22 | `data/spells/rogue.json` `throw` | 0.7 | as E-20 |
| E-23 | `data/spells/shaman.json` `poison-cleansing-totem` | 0.7 | `kind: "passive"` for a castable totem; `readings[1]` reports `rank: 1`, which a passive should not have. Same for `tremor-totem`. Suspect, no printed evidence either way - flag for the reviewer rather than auto-fix. |

Correct on every checked field: `warrior/slam` (despite confidence 0.0),
`paladin/holy-strike`, `paladin/seal-of-fury`, `shaman/fire-nova`,
`mage/arcane-blast`, `warlock/bane-of-agony`, `warrior/victory-rush`,
`druid/revive`, `hunter/aimed-shot`.

### 7.4 Racial traits

No errors. `dwarf/stoneform`, `dwarf/big-game-hunter`, `gnome/escape-artist`,
`human/will-to-survive`, `night-elf/elunes-light`, `orc/blood-fury`,
`skyborne/walk-on-air`, `skyborne/skysight`, `tauren/war-stomp`,
`troll/rapid-regeneration`, `undead/will-of-the-forsaken` all match their crops
under `data/review/races/<race>/` exactly on name, description and kind.

### 7.5 Talents

The 6 review-queue talents were confirmed as the only unreviewed records below
0.8; no new talent text errors were sampled this round (round one's audit
covered 87 of 469 and its 53 overrides were applied). The five talents of D-5
are value errors, not reading errors.

## 8. Code and docs

Reviewed at `872ec96`. **Caveat: another session was editing the tree
throughout this review.** On the web side `AboutPage.tsx`, `copy.ts`,
`site.ts`, `overrideEntry.ts`, `review.css` and
`tests/review-writeback.spec.ts` appeared as untracked while `App.tsx`,
`url/route.ts`, `ui/ClassPicker.tsx` and `ui/ReviewPage.tsx` changed under us;
on the pipeline side `pipeline/src/wowtalents/db2.py`,
`pipeline/stages/10_import_db2.py`, `pipeline/tests/test_db2.py` and
`data/datamined/` appeared, and `export.py` and `validate.py` were modified -
i.e. the DB2 importer of `docs/PLAN.md` phase 3 is being built right now.
Everything below is stated against HEAD; line numbers in those files may have
drifted, and the two independent measurements of the web suite taken twenty
minutes apart disagree (523 vs 542 tests) for the same reason. The data
findings in §4 and §7 are unaffected - `data/talents/`, `data/races/`,
`data/spells/` and `data/review/` were untouched throughout.

### 8.1 P1 - correctness and data-loss

**K-1 (P1). `12_races.py build` can silently publish an empty race and then
delete its crops.** `pipeline/stages/12_races.py:562`

```python
for race in sorted({r for r, _ in per_unit} | {k.split("/")[0] for k in bars}):
```

The loop is driven by the union of races that have readings **and** races that
merely have a class bar in `states.json`. A race in the second set only - after
`read --only <race>`, after `read --limit N`, or after a `scan` whose ffmpeg
produced nothing (K-6) - reaches `_race_doc` with no units, yields
`traits: []`, and `write_text_atomic` at `:565` overwrites the good file.
`_prune_crops` (`:589-616`) then `unlink()`s every non-`_` PNG under
`data/review/races/<race>/`. Exit code 0, no warning.

Worse, the emptied file passes every gate: `data/schema/race.schema.json` sets
`traits.minItems: 0`, and `validate_races.py:337 rule_10_complete` only fires
`COMPLETE-EMPTY` when `complete` is **true**. CI would deploy it.
`11_spellbook.py:821` has the milder per-class analogue - it only rewrites
classes present in `readings.json`, but `--limit`/`--only` still shrink them.

Fix: skip a race with no units and say so on stderr; extend the shrink guard
that already exists in `pipeline/src/wowtalents/fsio.py:66-75`
(`write_candidates_atomic`) to both stages' document writes; give both `build`
commands a `--dry-run` (neither has one) and make `_prune_crops` honour it.

**K-2 (P1). The "generated files are up to date" guard is circular and cannot
fail.** `web/vite.config.ts:19-24` and `web/src/data/generated.test.ts:28-46`

The plugin calls `generate()` from **both** `config()` and `buildStart()`, and
`generate()` writes the generated files in place. Vitest resolves the same
`vite.config.ts`, so the files are rewritten before `generated.test.ts` reads
them and compares them to `expected()`. Demonstrated: injecting
`"className": "STALE-MARKER"` into `src/data/classes-index.json` passed 11/11
and the marker was gone afterwards; the same perturbation of
`classic-index.json`, whose generator is *not* in the plugin, correctly failed
`classicIndex.test.ts:16`.

The two docstrings contradict each other - `vite.config.ts:8-15` says the plugin
regenerates on dev, build and vitest; `generated.test.ts:4-7` says the test
fails when the data changed without a regeneration. Consequences: a commit with
a stale `classes-index.json`, `iconCrops.ts`, `classic-diff.json`,
`races-index.json`, `raceCrops.ts`, `spells-index.json` or `spellCrops/*.ts`
passes CI, the deploy builds from content regenerated in CI and never reviewed,
and every `npm test` / `npm run dev` / `npm run build` silently mutates tracked
source. Nothing is stale today; nothing holds it there.

Fix: `apply: 'serve'` on the plugin; add
`"gen": "node scripts/gen-data-index.mjs && node scripts/gen-classic-index.mjs"`
to `web/package.json`; add `npm run gen && git diff --exit-code -- src/data`
to the `check` job.

**K-3 (P1). Round one's A2 (unbounded decode from a hostile link) is untouched,
and the new import dialog adds a second delivery route.**
`web/src/url/codec.ts:66`, `web/src/url/import.ts:64`,
`web/src/ui/ImportDialog.tsx:43-51`

`git diff 038080e -- web/src/url/codec.ts` is empty. The loop still runs once
per input character; `:70` pushes one string per surplus non-zero digit into an
uncapped `unknown[]`; `:77` joins the whole list into one notice that
`Notice.tsx:11` renders as a single text node (only `violations` got the
`.slice(0, 8)` cap; `missing` at `:113` and `clamped` at `:116` did not).
Measured on the loop: a `t=` of 1,000,000 characters produces 999,970 entries
and a 13.2 MB message in 145 ms; 5,000,000 characters produces 70.5 MB in
847 ms. New since round one, `import.ts:64` (`/^[0-9]*(-[0-9]*)*$/`) accepts an
unbounded digit string and `ClassPage.applyImport` writes it into the hash - so
the payload now arrives by paste, not only by crafted link.

Fix: bound the input at the boundary (`if (s.length > 512) return badString`),
stop the loop at `Math.min(segment.length, ids.length)`, count the surplus once,
and cap every rendered list the way `import.ts:228` already does.

**K-4 (P1). Single-pass readings are published as facts.**
`pipeline/stages/11_spellbook.py:788` (`if e["confidence"] < min_confidence:
continue`, default `min_confidence = 0.0`)

`_pair_entries` (`:417-419`) emits an entry that only one VLM pass ever saw at
`confidence: 0.0`; the default floor lets it through; `_classic_for` (`:743`)
marks any name absent from the baseline `"new"`; `:967-968` turns that into
`tags: ["new"]`, the tag the web app surfaces. This is the mechanism behind
D-2 - the four fabricated "new in Forever" spells - reached independently from
the code side. Contributing gap: `spells.py` has `strip_rank` (`:439`) but no
analogue of `races.py:304 strip_kind`, so a glued "Passive" subtitle survives
into the name, which is exactly how `shaman/reincarnation-passive` was created.

Fix: default `--min-confidence` above 0.0 (0.5 keeps the 0.7 rows and drops the
single-pass ones), or refuse `tags: ["new"]` below the review threshold; add a
`strip_kind` to `spells.py`; extend `validate_spells.rule_14_kind` to
`\b(passive|racial)\s*$` (V-4).

**K-5 (P2, was P1 in round one). `data/encoding/v1.json` is still
`frozen: false` while the site is public and minting share links.** The
machinery round one asked for exists and is good -
`pipeline/src/wowtalents/export.py:631 _fork_frozen` copies rather than mutates
and `:675` refuses to rewrite a frozen file - it is simply not switched on, by
recorded owner decision (`docs/reviews/2026-09-13-consolidated.md:5`). The
premise has moved since that decision: the app is live and links are being
shared, so the exact failure A1 documented recurs on the next
`--update-encoding`. `validate.py` rule 11 compares a version file only against
the *current* data, so a rewrite passes by construction. Either set
`frozen: true` now and let the fork path create `v2` automatically, or add a
committed checksum so a rewrite fails loudly.

### 8.2 P2 - pipeline

| # | Finding | Where | Fix |
|---|---|---|---|
| K-6 | `mkv.decode_range` repeats round one's E4 in the new module: `stderr=DEVNULL` and the `finally` never inspects `returncode`. `ui.decode_frames` was fixed (`ui.py:166-169` raises `DecodeError`); both new stages use `MK.decode_range` instead, so a missing mkv or a bad seek yields zero frames, a `states.json` with `states: []`, and exit 0 - which feeds K-1. | `pipeline/src/wowtalents/mkv.py:95,106-109` | Capture stderr, raise on non-zero exit, and guard `if not states:` in both `scan` commands. |
| K-7 | Nine helpers duplicated between the two new stages: `codex_opinion`, `_json_object`, `hms`, `now`, `parse_window`, `_source`, `_ensure`, `_apply_third`, `_prune_crops`. `_apply_third` shares the identical 0.9/0.85/0.7 ladder; `codex_opinion` differs only in its prompt. Round one's E8, repeated. | `11_spellbook.py:337,366,107,112,116,648,749,423,1053` vs `12_races.py:237,266,93,111,98,431,584,371,589` | A `wowtalents/stagekit.py` for the six generic ones; parameterise `codex_opinion(image, out_dir, prompt, key)`. |
| K-8 | Four implementations of the same 1.0/0.7/0.3 confidence ladder, plus two near-identical `_score` rankers and two near-identical mergers. | `reader.py:436`, `spells.py:568`, `races.py:386`, `11_spellbook.py:471`; `races.py:461`/`spells.py:598`; `races.merge_traits:470`/`spells.merge_entries:606` | One `agreement(a, b, key, weak_key)` and one `merge_by(records, key, score)`. |
| K-9 | **Round one's E7 regressed**: `sys.path.insert` sites went 22 -> 36, and two of the new ones run inside a function called once per class/race, so `sys.path` grows by 8-10 duplicate entries per `build`. | `11_spellbook.py:1132`, `12_races.py:875` | Move the import to module scope, or move `canonical_dumps` into `wowtalents` and have the validators import it. |
| K-10 | `validate_races.rule_10_complete`'s explanation guard can never fire: `"not"` is a substring of `"nothing"`, and `12_races.py:796` appends `"...read from stream video; nothing here is reviewed."` to every race file unconditionally. Verified across all nine files. The spells analogue is dead for the same structural reason. | `pipeline/validate_races.py:340`, `validate_spells.py:341` | Match a real explanation pattern, or drop the rule and say so. |
| K-11 | `_check_source` is a weaker fork of the talent validator's `check_source`, copied byte-identically into both new validators: it never rejects video-only fields on a `manual`/`datamined` source, and never checks `reviewedAt` against `RFC3339_RE`. A race record with `kind: "manual"`, a stray `video`/`t`/`frame` and `reviewedAt: "yesterday"` passes. | `validate_races.py:287`, `validate_spells.py:285` vs `validate.py:596-624` | One `validators/common.py` holding the finding types, the CLI driver and a single `check_source`. The three files already carry triplicate `Finding`/`FileResult`/`Ctx`/`find_root`/`main`/`SLUG_RE`, and have already drifted (`validate_spells.Ctx` has no `info()`; `validate_races.Ctx:109` does). |
| K-12 | `class_availability` returns `float("inf")` when one side is empty, and that reaches JSON. An all-dark frame gives `classes: [], margin: inf`; `json.dumps` emits non-standard `Infinity`; and because `12_races.py:176` keeps the frame with the **highest** margin, that frame wins permanently - publishing an empty class list at `confidence: 1.0`. | `pipeline/src/wowtalents/races.py:205` | Return `None` when either side is empty and treat it as untrustworthy. |
| K-13 | Silent drops in the new stages: a tooltip whose crop is missing vanishes with no message, while the sibling `dedupe_states` documents the opposite policy; a corrupt `data/talents/<class>.json` silently disables the class cross-check and the racial lookup. Round one's E5 is only partly fixed - fatal paths use `err=True`, warnings still go to stdout, and `pipeline/README.md` still documents no exit-code convention. | `spells.py:669`, `11_spellbook.py:613-614,500,685,549,629`, `12_races.py:323` | Warn on every drop; one exit-code convention in the README. |
| K-14 | `validate_races.py` has **one** negative test (`test_races.py:327`); `validate_spells.py` has ten. Untested error paths for races include `RACE-FILENAME`, `BAD-ID`, `DUPLICATE-TRAIT`, `DUPLICATE-ORDER`, `ORDER-GAPS`, all of `rule_4_variants`, `rule_6_descriptions`, `rule_8_sources`, `rule_9_files`, `rule_11_lore`, rules 13-15 and every matrix rule but the pass. | `pipeline/tests/test_races.py` | Mirror the `test_spells.py:602-660` block. |
| K-15 | **The two functions that produce the published datasets have no tests**: `11_spellbook._class_doc` (`:888`, ~145 lines) and `12_races._race_doc` (`:708`, ~125 lines), plus `_prune_crops`, `_write_row_crops`, `_inventory_md`, `_matrix_doc`, `distinct_states`, `_pair_traits`, `_find_tooltips` and both `scan`s. In `wowtalents`, untested: `spells.page_slug/entry_key/cell_filled/cell_variance/_score`, `races.trait_kind/strip_kind/reading_key/_fragment_of/variant_of/_score/border_brightness/class_colourfulness/banner_fractions`. | - | Both document builders are pure given dicts; K-1's evidence is a ready-made harness. |
| K-16 | There is no `docs/DATA-SCHEMA-SPELLS.md`. Talents and races each have a normative prose contract that their validator cites; `validate_spells.py:2` can only cite the machine schema, and `docs/DATA-SCHEMA.md:40` names only the first two. The third dataset shipped without the contract the other two have. | - | Write it, from `docs/handover/2026-09-13-spells-data.md` §5, which is already the spec. |

### 8.3 P2 - web

| # | Finding | Where | Fix |
|---|---|---|---|
| K-17 | `classic-diff.json` for **all nine classes** is inlined into the entry chunk: a static import reachable from `TalentCell.tsx:23` -> `ClassPage` -> `App.tsx:4`, which is not lazy. Measured **60,458 B of the 411,674 B entry (14.7 %), 8,094 B gzipped**; the landing page needs none of it and a class page one ninth. Its sibling `classic-text.json` is already lazy in the same file. | `web/src/ui/classicDiff.ts:20` | Emit `classic-diff/<class>.json` per class the way `renderSpellCrops` already splits, and glob it lazily. This is the largest remaining byte win in the entry chunk. |
| K-18 | The 667-entry review crop registry is pulled onto the **player** route: `crops.ts:23` is still an eager glob and `Tooltip.tsx:508-519` dynamically imports it for every talent tooltip with a `source.crop`. Opening one tooltip on `#/mage` downloads `crops-*.js`, 63,024 B / 14,430 B gzip, containing every class's and every race's URLs. The docstring at `crops.ts:10-15` still claims "The single importer is ReviewPage". | `web/src/data/crops.ts:23`, `web/src/ui/Tooltip.tsx:513` | A generated `talentCrops/talent-<class>.ts`, same shape as the existing `spellCrops`; leave the wholesale glob to `ReviewPage`; fix the docstring. Race and spell crops were **not** given this defect - both got the correct per-scope generated-module treatment. |
| K-19 | Generator writes are truncating, and now run unattended on every dev/test/build (K-2). An interrupt mid-write truncates a **tracked** file - `classic-diff.json` is 120 kB, `classic-text.json` 84 kB. `:908-914` also `rmSync`s stale `spellCrops/*.ts` unguarded. Round one's E1 defect class, repeated on the JS side. | `web/scripts/gen-data-index.mjs:884-889`, `gen-classic-index.mjs:52` | `writeFileSync(path + '.tmp-' + process.pid, ...)` then `renameSync`. |
| K-20 | `NaN` version survives `??` and empties an imported build: `route.ts:73` returns `version: NaN` for `?v=abc`, `import.ts:56` copies it, `ImportDialog.tsx:55` previews it with no warning, and `ClassPage.tsx:296` does `targetVersion ?? cls.dataVersion` - `NaN ?? x` is `NaN`. The player presses "Use this build" and lands on `?v=NaN`, which `codec.ts:40` rejects with an empty build. Untested in both `route.test.ts` and `import.test.ts`. | `web/src/url/route.ts:73` | Normalise at the boundary: `Number.isInteger(version) ? version : undefined`. |
| K-21 | `embed=1` suppresses **every** decode notice (`unknown-version`, `clamped`, `unknown-talent`, `adjusted`), and embed also hides the header and summary, so an embedded old-version link renders a silently different build with no channel to say so. | `web/src/ui/ClassPage.tsx:337` | One condensed warning line in the `embed-bar` (`:419`) linking out to the full calculator. |
| K-22 | `sel=` naming a talent that does not exist is a silent no-op: no tooltip, no page switch, no message, and the dead parameter stays in the hash so a reload repeats it. An unknown *class* is reported (`ClassPage.tsx:82`) and an unknown *race* is reported (`RacesPage.tsx:201`); `sel` is the odd one out. The validation itself is sound - `sel` is checked against the class-id slug pattern before it reaches `querySelector`. | `web/src/ui/ClassPage.tsx:202-206` | Route it through the existing `blocked-message` channel and call `deselect()`. |
| K-23 | Import failures are invisible and unrecoverable: `ImportDialog.tsx:67-87` is `try`/`finally` with no `catch`, so a failed chunk fetch is an unhandled rejection and the button flips back to "Check"; and `classicIndex.ts:30` (`cached ??= import(...)`) caches the **rejected** promise forever, so every retry fails instantly with no network attempt. The sibling got this right - `classicDiff.ts:157-163` resets `loading = undefined` in its `catch`. | `web/src/ui/ImportDialog.tsx:67`, `web/src/data/classicIndex.ts:30` | A `catch` setting a visible message, plus `.catch(e => { cached = undefined; throw e })`. |
| K-24 | **Duplicated helpers, round one's E2/C3 class now on the TypeScript side.** Four `initials` implementations producing three different strings (`ui/initials.ts:8` two letters, `TalentCell.tsx:275-280` three, `ClassIcon.tsx:21` `className.slice(0,2)`). Four "is this a text field" predicates, one of which omits `SELECT` so `/` steals focus from a `<select>` (`history.ts:110`, `ShortcutsOverlay.tsx:63`, `TalentCell.tsx:256`, `Header.tsx:36`). Four crop-path lookups and three `*CropCount()`. Three copies of `stem()` and of the whole lazy-registry body (`load.ts:26`, `races.ts:21`, `spells.ts:18`). Three renderers inside one generator differing only in `../` depth. And the `SLUG` regex is declared twice in production code - `data/schema.ts:14` exports it, `url/route.ts:36` re-declares the literal - which is round one's C3, unfixed. | as listed | One helper each; import the exported `SLUG`. |
| K-25 | `raceTrustLines` and `spellTrustLines` are line-for-line identical apart from a noun, and **both assert `Read from BlizzCon 2026 footage` regardless of `source.kind`** - overclaiming provenance in a codebase whose whole thesis is not overclaiming it. Two confidence formatters print `100%`, a string `trust.ts:118` classifies as pipeline-internal. | `web/src/ui/racesModel.ts:222-240`, `spellsModel.ts:273-287`, `ReviewPage.tsx:271,312` | One `datasetTrustLines(records, noun)` that branches on `source.kind`. |
| K-26 | `crops.test.ts` still lacks the inverse assertion round one asked for - it checks only "every referenced crop is shipped", never "every shipped crop is referenced". The orphan count is down to 2 shipped files (263,944 B) purely because the data was cleaned. | `web/src/data/crops.test.ts:35-45` | Assert `cropCount()` equals the referenced-path count with a named allowlist. |
| K-27 | Untested branches in the new web models: `interaction.blockedMessage`'s `page-full`, `not-spent`, `default` and the `remove` variant of `prereq` (a different sentence from the tested one); `classicDiff.classChanges/classCounts/comparedClasses` - the three that drive `#/changes` - plus the `catch { loading = undefined; return {} }` degradation path. No test file at all for `highlightNew.ts`, `classIcon.ts`, `trust.ts`, or `stickyTooltip`'s `claimTooltip`/`releaseTooltip` single-owner rule. Round one's B3.2 (migration `removed`/`moved`) was not added and `codec.ts` was never touched, so A4's dead `moved` branch, A5 and A6 all stand. | `web/src/ui/interaction.ts:16-37`, `classicDiff.ts:104,109,114,159-162` | - |

### 8.4 CI

All three validators run, all in the `check` job, all with `--check`, all gating
the deploy through `needs: check` - `validate.py` at `deploy.yml:28`,
`validate_races.py` at `:31`, `validate_spells.py` at `:34`. Both test suites
run and block: pipeline `pytest -q` at `:24`, web `vitest run` at `:43`, plus
Playwright at `:49`, with no `continue-on-error`. Round one's B1 and B2 are
fixed and exceeded.

| # | Finding | Where | Fix |
|---|---|---|---|
| K-28 | **The `npm run e2e` process exited 1 on a clean local run that reported `57 passed (3.3 m)`.** In CI that fails the deploy despite an all-green suite. It could not be reproduced because a concurrent edit then broke `build:e2e`'s `tsc -b`. | - | Re-check on a clean tree before trusting the green; this is the highest-value CI item. |
| K-29 | No `pull_request` trigger: `deploy.yml:2-5` fires on `push` to `main` and `workflow_dispatch` only, so the whole gate runs *after* the commit is already on `main` and already deploying. | `.github/workflows/deploy.yml:2-5` | Add `pull_request:` and run `check` on it. |
| K-30 | `tsc` is the last gate, not the first, and `vitest` runs twice. `deploy.yml:66` is `npx vitest run && npm run build`, and `npm run build` is `tsc -b && vite build`, so a type error surfaces only after the 2 m 06 s `check` job passed. `check` type-checks only incidentally, inside Playwright's `webServer`, where a `tsc` failure appears as "webServer was not able to start. Exit code: 2". | `.github/workflows/deploy.yml:66`, `web/playwright.config.ts:21` | `npm run typecheck` right after `npm ci` in `check`; reduce the deploy step to `npm run build`. |
| K-31 | `oxlint` is defined in `web/package.json:11` and is a devDependency, but is never run. Round one had 3 warnings; there are now **11** (8 `react(set-state-in-effect)` in `ChangesPage.tsx:124`, `SpellsPage.tsx:135`, `ReviewPage.tsx:47`, `RacesPage.tsx:201`, `TalentCell.tsx:238`, `ClassPage.tsx:82,110,206`). | `.github/workflows/deploy.yml` | Add `npm run lint` to `check`, allowlisting the three floating-ui false positives. |
| K-32 | Validators run without `--strict`, so their warnings never fail - including the 12 `NEEDS-REVIEW` warnings that cover the four fabricated spells of D-2. `validate_races.py --check --strict` is green **today**. | `.github/workflows/deploy.yml:28,31,34` | Turn `--strict` on for races now; ratchet the other two. |
| K-33 | The comment above the Playwright step still says it is "Non-blocking until the suite has run green in CI a few times ... Drop the flag then." The flag was dropped in `f2f2a46`; the comment stayed. This is round one's C5 (a comment describing a deleted setting), fixed once and immediately repeated. | `.github/workflows/deploy.yml:47-48` | Delete the two lines. |
| K-34 | Playwright browsers are not cached (~30-60 s per run). `check` is ~95 % of the pipeline (2 m 06 s of 2 m 34 s) and its cost is Playwright plus the uncached browser install plus `apt-get install ffmpeg`, not the suites, which total under 13 s locally. | `.github/workflows/deploy.yml` | Cache `~/.cache/ms-playwright` keyed on the lockfile. |

Measured timings (local, this machine):

| Command | Result | Wall |
|---|---|---:|
| `uv run --directory pipeline pytest -q` | 461 passed | 5.8-6.2 s |
| `npx vitest run` (web) | 542 tests / 26 files passed | 2.1-2.6 s |
| `npm run build` (web) | ok (`vite build` itself 654-661 ms) | 3.83-3.89 s |
| `validate.py --check` | exit 0, 0 errors / 97 warnings | 0.35 s |
| `validate.py --check --strict` | exit **1** | 0.35 s |
| `validate_races.py --check` | exit 0, 0 errors / 0 warnings | 0.11 s |
| `validate_spells.py --check` | exit 0, 0 errors / 12 warnings | 0.18 s |
| `npm run e2e` | 57 passed, **exit code 1** (K-28) | 217 s |
| GitHub Actions, last five *Deploy to Pages* | 2:41, 2:26, 2:28, 2:10 (fail), 2:16 | `check` 2:06 + `deploy` 0:28 |

### 8.5 P3

`12_races.py:547` picks `_panel.png` by "last state with a race name" rather
than by sharpness, because `unit["lore"]` is only assigned at `:549-554`, after
the test that reads it. `RC.normalise_trait` runs three times per state
(`12_races.py:514,523,526,542`). `11_spellbook.py:818` decodes and re-encodes a
PNG where `shutil.copyfile` would do, and does not check `imread` for `None`.
`11_spellbook.py:965` sorts tooltips by description text, so output order
depends on wording - sort by rank. `_tree_names()` re-reads all nine talent
files per class (`11_spellbook.py:1048,539-540`). Both stages check `readings`
with `.is_file()` but not `states`, so a missing `states.json` gives a raw
traceback instead of "run `scan` first". `races.py:378 norm` duplicates half of
`text.clean_text`; `races.py:386 confidence(a, b: dict)` is annotated
non-optional but tests `b is None`. `validate.py:1140-1141`'s dead `pass`
conditional (round one's E9.3) is unchanged. `pipeline/README.md:389-492`
documents both new stages accurately but never mentions that `build` **deletes**
committed crops under `data/review/`.

`pipeline/src/wowtalents/db2.py` is untracked and imported by nothing - either
commit it with tests or delete it.

Web: dead exports `listRaces` (`data/races.ts:29`), `listSpellClasses`
(`data/spells.ts:24`), `emptyBuild` (`rules/points.ts:65`, still unused from
round one's C3). Missing zero-result states on `RacesPage.tsx:285`,
`SpellsPage.tsx:206` and `ChangesPage.tsx:218` (which renders `Nothing matches
""` for a class with no changes). `race.variants: []` renders an empty `<nav>`
(`RacesPage.tsx:246`). `useTitle` has no cleanup (`ui/title.ts:6-10`), so a
loading page keeps the previous tab title. `readLastBuild`
(`ui/storage.ts:42-56`) does not shape- or length-check `classId`/`t` before
they reach `#/${classId}` and a text node. Unescaped `querySelector` at
`ClassPage.tsx:288` and `TreePanel.tsx:158` where two sibling sites do use
`CSS.escape`. `ReviewPage.tsx:152` assigns `e.target.value = ''` on a
React-controlled `<select>`. Stale comments at `TreePanel.tsx:67` and
`TalentCell.tsx:234`. The fictional `tinker` class is baked into the production
entry chunk because `gen-data-index.mjs:54-58` ignores `VITE_INCLUDE_EXAMPLES`.
28 `_header.png` tree strips (~0.8 MB) ship in `dist` reachable from no
rendering code.

### 8.6 Round-one findings: what actually happened

| Round one | Status |
|---|---|
| E1 five stages write candidates non-atomically | **FIXED** - `fsio.py` is used at every pipeline write site. **Repeated on the JS side** (K-19). |
| E2 three slug implementations | **FIXED** - `wowtalents/text.py` is the single `slug`; `spells.py` and `races.py` import it. No fourth. **But the web grew a second `SLUG`** (K-24). |
| E3 `05_read --add` dedupe bug | **FIXED** (`05_read.py:138-150`). |
| E4 silent zero-exit ffmpeg failures | **PARTIALLY** - `ui.decode_frames` raises; the new `mkv.decode_range` repeats the original defect (K-6). |
| E5 stdout logging / exit codes | **PARTIALLY** - fatal messages use `err=True`; warnings still on stdout; no convention documented. |
| E6 CLI conventions, `--dry-run` | **PARTIALLY** - stages 11/12 share a clean `scan`/`read`/`build` shape; neither has `--dry-run` despite deleting committed PNGs (K-1). |
| E7 repeated `sys.path.insert` | **REGRESSED** 22 -> 36 (K-9). |
| E8 duplicated logic | **REGRESSED** - nine helpers duplicated between the new stages (K-7), fourth confidence ladder (K-8). |
| E9.3 dead conditional | **NOT FIXED**. |
| A1 encoding rewritten in place | **PARTIALLY** - machinery exists, not switched on (K-5). |
| A2 unbounded decode | **NOT FIXED**, and widened (K-3). |
| A4 / A5 / A6 codec dead branches | **NOT FIXED** - `codec.ts` is byte-identical to `038080e`. |
| B1 CI runs no pipeline tests or validator | **FIXED and exceeded** - pytest, all three validators, vitest and Playwright all gate the deploy. |
| B2 Playwright never ran | **FIXED** - it runs and blocks. Only the comment is stale (K-33). |
| B3 test gaps | **MIXED** - 171 -> 461 pipeline tests, 81 -> 542 web tests, 86 Playwright tests. B3.1 and B3.2 not done. |
| C4 430 orphaned PNGs | **FIXED on the data side** (430 -> 12 on disk, 2 shipped); the `crops.test.ts` inverse assertion was not added (K-26). |
| C5 dangling workflow comment | **FIXED, then REPEATED** (K-33). |
| P-1 landing loads nine class chunks | **FIXED** (-49.6 kB, -9 requests). |
| P-2 eager 971-path crop glob | **PARTIALLY** - out of the entry chunk (-92 %), but pulled onto the player route by the tooltip (K-18). **Not repeated** for race, spell or icon crops. |
| P-3 zod in the client | **FIXED, verified empirically** - zero hits across all 46 emitted chunks. |
| D2 / D4 / D5 doc items | **FIXED** apart from C-1 and C-2 below. |

### 8.7 Documentation drift (the same finding as round one's C2/C4, again)

**C-1 (P2).** `CLAUDE.md` §State (lines 10-17) says "Everything is
**unreviewed**: 0 talents have `source.reviewed: true`, 77 sit below the 0.8
confidence threshold, plus 21 low-confidence prerequisite arrows." The real
numbers are **57 reviewed** and **6** below 0.8, and the file does not mention
`data/races/`, `data/spells/` or the three non-talent routes at all in its state
paragraph, although its Layout section does. `CLAUDE.md` is the first file every
session reads; it currently argues for work that is already done.

**C-2 (P2).** `docs/PLAN.md:129-156` ("Immediate next actions") is the same
drift one level down: it says "nothing is reviewed", points at "the 77-record
review queue", asks for "77 talents below the 0.8 confidence threshold plus 21
low-confidence prerequisite arrows", and lists Phase 2b (races), 2c (changes)
and 2d (spellbook) as future work. All three phases shipped. The status log
further down the same file (line 270) records the correct numbers, so the
document contradicts itself.

**C-3 (P3).** `docs/handover/README.md` indexes all 30 handovers - no gap.
`docs/handover/2026-09-13-classic-diff-v2.md` §2 is the one stale handover; see
D-7.

## 9. Suggested order of work

1. **K-1** - the shrink guard and the `build` skip. It is the only finding here
   that can destroy committed data, and it is about ten lines.
2. **K-28** - find out why `npm run e2e` exits 1 on a green suite, before
   trusting any deploy gate.
3. **D-2 / K-4** - delete the four fabricated records and stop
   `min_confidence = 0.0` from minting `tags: ["new"]`. "16 new spells" is the
   project's loudest public claim and four of them are OCR noise.
4. **D-4 / V-1** - queue tooltip confidence. One function, and it is the
   difference between "0 errors, 12 warnings" being true and being misleading.
5. **K-2** - `apply: 'serve'` plus a `gen` script and a `git diff --exit-code`
   in CI, so the generated-file guard means something.
6. **D-10** - build `data/overrides/{races,spells}/`; nothing else in the
   non-talent data can be corrected until it exists. Roughly an hour for both,
   and both handovers have been asking for it since they shipped.
7. **D-1 / V-5** - port the shape-aware merge to stage 11, or at minimum add
   the two post-checks so the 11 machine-detectable text defects surface in
   `--report`. Note that four of the thirteen errors in §7.1 (a misspelling,
   two wrong footers, one flattened list) are not detectable by any regex and
   need the reader fixed rather than a validator rule.
8. **D-5** - stop publishing percentages above 100 %.
9. **K-3** - bound the decode loop. It is round one's A2, still open, now with
   a second entry point.
10. **D-3 / V-2 / V-3 / V-4 / K-10 / K-11** - the remaining validator work,
    about an afternoon, ending in one shared `validators/common.py`.
11. **K-17 / K-18** - the two remaining bundle wins, ~22 kB gzip off the entry
    chunk and 14 kB off every class page that opens a tooltip.
12. **C-1 / C-2 / D-7 / K-16 / K-33** - the documentation round: `CLAUDE.md`,
    `PLAN.md`, the superseded diff table, the missing spells schema doc, the
    workflow comment.
13. **PR-1** - ship the commit-msg hook so it survives a clone.
14. **D-6** - two lines in `normalizeText`, recovers one real value change.
15. Performance: **P-4 (WebP for the crops)** is the only large win left and is
    worth ~20 MB of `dist/`; the entry stylesheet (R-2) is the only thing that
    grew on the critical path.

## 10. What was checked and found sound

Worth recording, because a review that only lists defects misrepresents the
state of the work:

- The **racial dataset** is the best-evidenced thing in the repository: 11 of 11
  sampled traits exact against their crops, 0 below threshold, 0 validator
  warnings, matrix consistent with all nine race files.
- **Coverage records** match `data/extracted/spells.md` on every field for all
  eight classes, including the deliberately awkward ones (rogue 1 of 4 tabs,
  warlock 1 of 4, priest absent entirely).
- The **web layer handles the unverified priors correctly**: `racesModel.ts:281`
  carries an `UNVERIFIED` constant rendered on every Classic paraphrase,
  `spellsModel.ts:168` explains that `new` means "missing from a list written
  from memory", and `racesModel.ts:322` deliberately strips the repo path out of
  the note before rendering. Every rule the two data handovers set out for the
  UI is implemented.
- The **`#/changes` precedence** is genuinely one-section-per-talent: the six
  section counts sum to 469.
- **Round one's C4** (430 orphaned PNGs) is properly fixed: 12 files remain
  unreferenced on disk and 11 of them are deliberate `_page` / `_panel` /
  `_general` context crops.
- The **encoding freeze machinery** (`export.py:631,675`) is correct and
  complete; it is only waiting on the owner's launch call.
- **CI went from running neither the pipeline tests nor the validator to
  running both plus all three validators plus Playwright**, all gating the
  deploy. That is the single largest improvement since round one.

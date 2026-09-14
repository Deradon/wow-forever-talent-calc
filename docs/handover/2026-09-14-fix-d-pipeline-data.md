# Review round two, package D: pipeline and data (2026-09-14)

Scope: `docs/reviews/2026-09-14-consolidated.md` package D, items 1-7, against
the detail in `docs/reviews/2026-09-14-data-code-perf.md`. Nothing under `web/`,
`pipeline/stages/10_import_db2.py` or `data/datamined/` was touched.

## 1. What was done

### D1 - the shape-aware merge reaches stage 11

The defect was structural, not a bad threshold. `read` scores a row or a
tooltip by comparing **two passes of the same VLM over the same pixels**, and
two passes agree on their own mistakes: agreeing on a misread comma scored 1.0.
Ten of twelve sampled `confidence: 1.0` tooltips were wrong.

* New command `uv run stages/11_spellbook.py opinions` fetches an independent
  reading of every list column and every tooltip crop from the codex CLI and
  stores it in `work/spells/readings.json` as `reader: "codex"`. 354 crops, 315
  new calls, 12 minutes at `--jobs 6`, 0 failures; answers cached per crop under
  `work/spells/codex/`, so a re-run is free. **114 of 114 tooltips and 915 list
  rows now carry a second reader.**
* `wowtalents/spells.py` grew `merge_tooltip`, `merge_entry`, `split_readings`
  and `merged_confidence`, built on `wowtalents/merge.py`. `build` runs them
  over every row and tooltip.
* `wowtalents/merge.py` gained `normalise_capital_i(..., min_tail=1)` so the
  spellbook's commonest defect - a two-letter `In`/`Its` - is reachable, plus
  `Ironforge` and `Isle` in the allow-list. The talent default is unchanged.

**Policy, and where it differs from the talent merge.** Case, punctuation and
`%` go to the codex reading, as for talents. A **word** the two readers spell
differently is *not* voted away: it keeps the first reader's text, drops the
record to 0.7 and names both variants in `source.note`. The talent merge could
let a vote settle wording because its 2026-09-13 audit had measured the primary
reader at ~70 % on words; no such audit exists for the spellbook, so a wording
disagreement between two independent readers goes to a human. `confidence` is
now about *who* agreed: `1.0` an independent reading that agreed verbatim, `0.9`
the authority corrected a shape (or there is no independent reading at all),
`0.7` the readers still differ, `0.0` one reader only.

Counts over all spell tooltips and list entries, by the detectors now in
`validate_spells.text_defects`:

| Defect shape | Before | After |
|---|---:|---:|
| Comma read as a full stop (`. ` + lower case) | 6 | **0** |
| Spurious mid-sentence capital `I` | 8 | **0** |
| Whitespace / OCR artefact characters | 2 | **0** |
| Tooltips carrying at least one of the above | 13 | **0** |
| The four defects no regex can find (§7.1) | 4 | **3**, all named below |
| Records at `confidence: 1.0` | 317 | 318 (now corroborated) |
| Spell review queue below 0.8 | 14 (10 rows + **4 invisible** tooltips) | **21** (2 rows + 19 tooltips, all listed) |

The merge applied 20 case, 9 punctuation and 3 word corrections. The queue grew
on purpose: 19 tooltips are queued because the two readers differ on a word, a
footer or a cost line, and each one names the disagreement in `source.note`.

Of the four undetectable defects: `rogue/shadowmeld`'s footer is no longer the
invented "added this to your action bars" and the record sits at 0.7 with
`footer 'bars' vs ''` named; `mage/dampen-magic` ("Dampons") and
`mage/languages` (a list flattened without a separator) are at 0.7 with the
codex alternative in `source.readings`. `druid/prowl`'s footer ("but **on** a
different stance") is unchanged and **not** queued - the independent reader read
it the same way, so nothing in the data disagrees with it. It needs an eye on
`data/review/spells/druid/prowl.tooltip.png`.

### D2 - fabricated records never reach `data/spells`

`build --min-confidence` now defaults to 0.5 instead of 0.0, so a row only one
reader ever saw is not published, and `validate_spells.rule_16_publishable`
(ERROR) is the gate that keeps it out. `spells.py` gained `strip_kind`, the
analogue `races.py` has always had, so a glued `(Passive)` subtitle goes back
into `kind` instead of into the id.

Removed, and nothing else: `druid/shapeshift`, `mage/evocation-dampen-magic`,
`shaman/reincarnation-passive`, `warrior/rummel-whirlwind`. **327 -> 323 rows,
16 -> 12 "new in Forever" names**, both recounted in `data/extracted/spells.md`.
`warrior/slam`, correct but at 0.0 before, picked up a codex reading and stayed.

### D3 - neither stage can empty a file or delete committed crops

A class (stage 11) or race (stage 12) that produced no records, **or fewer than
the file already on disk**, is skipped with a message on stderr; its file and
its crops are left alone. A run in which no unit produced a record exits 1
instead of writing. A skipped race keeps its existing `matrix.json` row. Both
`build` commands gained `--dry-run`, which writes nothing and deletes nothing.
`readings.json` is written through a shrink guard of its own.

### D4 - the validator looks inside `tooltips[]`

`rule_13_confidence` descends into `tooltips[]` and queues them at
`/spells/{i}/tooltips/{j}`; `rule_11_tooltips` checks the footer as well as the
description and adds the two V-5 post-checks; `rule_14_kind` catches a glued
`(Passive)`; `rule_16_publishable` is new. `validate_spells.py --check` is
**0 errors, 22 warnings**; all three validators exit 0.

### D5 - one stage kit

`wowtalents/stagekit.py` holds `hms`, `now`, `parse_window`, `json_object`,
`codex_opinion`, `source`, `ensure`, `apply_third` and `prune_crops` - the nine
helpers K-7 found duplicated, including the two copies of the 0.9/0.85/0.7
ladder that had already drifted. `sys.path.insert(... / "src")` is gone from
every stage and script (the package is installed; `uv run` puts it on the path);
stages 11 and 12 keep one module-level entry for the top-level validators, so
`sys.path` no longer grows once per class.

### D6 - the commit-msg hook travels with the repository

`scripts/git-hooks/commit-msg` is tracked and executable; `CONTRIBUTING.md`,
`README.md` and `CLAUDE.md` tell contributors to run
`git config core.hooksPath scripts/git-hooks` once per clone. Set in this
checkout.

### D7 - the numbers

`CLAUDE.md` §State and `docs/PLAN.md` §"Immediate next actions" now say 469
talents / 57 reviewed / 6 below 0.8, 37 racial traits / 0 below, 323 spell rows
and 112 tooltips / 21 below, and point at the round-two review. `README.md`'s
spellbook line went 327 -> 323.

## 2. State of long-running things

Nothing is running. llama-server was up on 8089 but was never needed - the
`opinions` pass uses the codex CLI only. `pipeline/work/spells/readings.json`
now carries the codex readings and is git-ignored; re-fetching them costs
another twelve minutes if it is ever lost, and `work/spells/codex/` is the cache
that makes a re-run free.

## 3. What is next, in order

1. **`data/overrides/{races,spells}/` (review D-10).** They do not exist, so
   none of the 21 queued spell records can be corrected without hand-editing a
   generated file, which `CLAUDE.md` forbids. This blocks the whole non-talent
   review round.
2. **The 21 queued spell records**, from `validate_spells.py --report`. Each
   names its disagreement in `source.note` and keeps both readings.
3. **D-3** (`ranksSeen` values no reading supports), **D-5** (percentages above
   100 %), **V-2/V-3/V-7** and the shared `validators/common.py` of K-11.
4. **K-16**: there is still no `docs/DATA-SCHEMA-SPELLS.md`.

## 4. Surprises and decisions

* **The codex CLI is fast and accurate on tooltips.** Ten seconds a crop, and it
  read the `mage/dampen-magic` comma and "Dampens" correctly on the first try.
  Six parallel processes is comfortable.
* **A tie is not a decision.** The tempting fix was to let the authority win a
  word hunk outright, which would have "fixed" all four undetectable defects in
  one line. It would also have replaced an audited reader with an unaudited one
  on 3 words out of 112 tooltips, on no evidence. Queueing the disagreement is
  the smaller claim, and it is why the queue grew from 14 to 21.
* **Dropping single-reading rows cost exactly the four fabricated records.** The
  other three rows the threshold dropped (`Dash`, `Evocation`,
  `Grounding Totem`) survive from a second page state, so the id sets differ by
  the four and nothing else - verified against `HEAD` before committing.
* **`shaman/reincarnation` is now absent rather than wrong.** `strip_kind` fixes
  the name, but in that state the reader produced more names than the column had
  icons, so the row is dropped by the icon-count rule. Absent and honest beats
  present under a fabricated id.

## 5. Verification

```
cd pipeline && uv run pytest -q                                   # 555 passed
uv run python validate.py        --check ../data/talents/*.json   # 0 errors
uv run python validate_races.py  --check ../data/races/*.json     # 0 errors, 0 warnings
uv run python validate_spells.py --check ../data/spells/*.json    # 0 errors, 22 warnings
cd web && npx vitest run                                          # 573 passed
```

The four data-count assertions in `web/src/ui/spellsModel.test.ts` that this
package invalidated (druid 41 -> 40 entries, new-in-Forever 16 -> 12, the druid
"1 of 41 entries is uncertain" line, the shaky-row count 10 -> 2) failed on the
first run and were updated by the package-E owner working in the same tree while
this was in flight; the suite is green as of the final run. Nothing about
loading or validating the data ever failed - the schema and crop-registry suites
passed throughout.

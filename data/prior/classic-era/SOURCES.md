# Classic Era prior: sources

Reference data for rank anticipation (`ranksSource: "classic-prior"`) and
for validator rules 14/15. Retrieved 2026-09-13 by the data lead; rebuild
with `python3 data/prior/classic-era/build.py` (standard library only).

## Files

| File | Content | Origin |
|---|---|---|
| `raw/talents-classic.js` | Wowhead Classic talent calculator data: `trees[tabId] = {id, description ("PaladinProtection"), role}`, `talents[tabId][talentId] = {id, row, col, icon, ranks: [spellId per rank], requires: [{id, qty}]}`. No names, no text. 1.27 MB, `WH.setPageData(...)` wrapper, parsed with `json.JSONDecoder.raw_decode`. | `https://nether.wowhead.com/classic/data/talents-classic`, HTTP 200, 2026-09-13 00:42 CEST, one request with a descriptive User-Agent |
| `raw/spells.json` | `{spellId: {name, icon, rank, description}}` for the 1357 rank spells; per-rank tooltip text as rendered by Wowhead's Classic tooltip endpoint, scraped by the repo author in 2023. | `https://raw.githubusercontent.com/melv-n/wow-talent-calculator/master/src/data/spells.json`, HTTP 200, 2026-09-13 00:42 CEST (branch `master`; `main` is 404) |
| `racials.json` | Classic Era racial traits per race (name, kind, short paraphrase) plus the Classic class list per race. **Written from memory by the data lead, not retrieved from anywhere**; `"verified": false`. Used by `pipeline/stages/12_races.py build` to decide whether a Forever racial is new. | hand-written 2026-09-13, unverified |
| `racial-diff.json` | Per-trait `same` / `changed` verdicts for the racials that exist in both games, with a one-line reason. Separate from `racials.json` because a text diff against a paraphrase says "changed" every time; these are judgements, not computation. `"verified": false`. | hand-written 2026-09-13, unverified |
| `talents.json` | Derived: class -> trees -> talents with `classicTalentId, id, name, row, col, maxRank, icon, requires[{talent, classicTalentId, rank}], spellIds, ranks[per-rank text], description ({n} template), slots[per-rank values]`. | `build.py` over the two raw files |

Wowhead's per-spell tooltip endpoint (`https://nether.wowhead.com/classic/tooltip/spell/<id>`)
was not used: `spells.json` already covers all 1357 rank spells (checked:
0 missing), which saves 1357 requests. It remains the fallback if a text
looks wrong (`build.py` reports missing ids).

## Normalisation decisions

- Class and tree name come from Wowhead's tree `description`
  (`HunterBeastMastery` -> hunter / "Beast Mastery"). Four internal names
  differ from the in-game names and are mapped explicitly: tab 381
  `PaladinCombat` -> Retribution, 261 `ShamanElementalCombat` -> Elemental,
  302 `WarlockCurses` -> Affliction, 303 `WarlockSummoning` -> Demonology.
- Tree `order` is alphabetical by tree id, which equals the in-game
  left-to-right order for all nine Classic classes. `classicTabId` is
  Wowhead's tab id (= `TalentTab.ID`).
- `role` maps Wowhead's code 1 -> healer, 2 -> dps, 3 -> tank (raw value
  kept in `wowheadRole`; the four tank trees carry a code outside 1..3 and
  get `null`). Informational only.
- Talent `id` is the slug of the name per DATA-SCHEMA.md section 3; a name
  used in two trees of one class gets `-<treeId>` appended (none occur in
  Classic Era). `requires[].talent` is resolved to that slug; all 65
  prerequisites point inside their own tree.
- Text: non-breaking and repeated spaces collapsed, curly quotes
  straightened, trimmed. `spells.json` lost line breaks in a few
  multi-paragraph tooltips (e.g. Master Demonologist: "active.Imp - ...");
  left as is, the rank-1 text of Forever comes from the stream anyway.
- `description` / `slots`: numbers (including `.2`-style decimals) that
  change between ranks become `{n}` placeholders, words that differ only by
  a plural `s` become `""`/`"s"` slots, everything else stays literal
  (Improved Heroic Strike: `"... by {0} rage point{1}."`,
  `[[1, ""], [2, "s"], [3, "s"]]`). For 4 talents the sentence shape changes
  between ranks (unit switch `45 sec` -> `1.5 min` in Endurance and
  Elusiveness; extra "More effective than ... (Rank N)" sentence in Master of
  Deception and Heightened Senses); these have `description: null`,
  `slots: null` and a `note`, and rank anticipation must use the per-rank
  strings.

## Statistics (2026-09-13)

9 classes, 27 trees, 432 talents, 1357 rank spells, 65 talents with
prerequisites, 0 missing texts, 4 shape-changing talents. maxRank
distribution: 5 -> 162, 3 -> 88, 2 -> 95, 1 -> 85, 4 -> 2.

## License situation

- Neither `melv-n/wow-talent-calculator` nor Wowhead's data endpoint carry a
  license that covers this use. Wowhead's ToS could not be read by a
  non-browser client (403); treat the endpoint as tolerated, not permitted:
  one request, cached here forever, no hotlinking, no re-fetch loops.
- The tooltip text, talent names and icon names are Blizzard Entertainment's
  copyrighted game content, reproduced here as reference data for a fan
  tool. The repository's MIT license covers our code and data shapes, not
  this text. If a takedown request arrives, delete `raw/` and `talents.json`
  and switch `ranksSource` to `extrapolated`/`manual`.
- Structural facts (positions, ranks, prerequisites, spell ids) are also
  available from Blizzard's own DB2 tables via wago.tools (brief section (e));
  the datamined importer will replace this prior for Forever data.

## Racials (added 2026-09-13)

`racials.json` and `racial-diff.json` are the only files here that were not
retrieved from a source. They exist because Phase 2b needed a "what changed"
verdict before any Forever or Classic racial data could be datamined, and they
are marked `"verified": false` so nothing downstream can mistake them for
sourced data. `data/races/*.json` copies their text into `classic.classicText`
with the warning repeated in `classic.note`.

Replace them with a sourced racial list (Wowhead Classic racial spell ids, or
the beta DB2 from 2026-09-17) and re-run `12_races.py build`; no other file
changes. Contract: `docs/DATA-SCHEMA-RACES.md` section 4.4.

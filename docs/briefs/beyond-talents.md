# Brief: beyond talents (spells, races, Legacy, what changed vs Classic)

Status: proposal, 2026-09-13, written from the survey in
`data/extracted/other-content.md`. Not yet in `docs/PLAN.md`; the owner
integrates. Talent extraction (workstreams A-C) is untouched and stays first.

## (a) Prioritised content types

Value = usefulness to a player before datamining lands (2026-09-17 + a few
days) and afterwards; effort = pipeline + review, in person-hours of a
session that already has the talent pipeline running.

| Prio | Content | What is new vs Classic (from the footage) | Value | Effort | Notes |
|---|---|---|---|---|---|
| 1 | Racial traits (10 races, two Skyborne variants) | ~60 % of traits new or reworked: Will to Survive, Elune's Light, Eureka!, Shatter Curse, Plainsrunning, Touch of the Grave, weapon specs give crit, Blood Fury percentage, Expansive Mind for all resources; Skyborne 100 % new | High: small, complete, nobody has it, feeds "what changed" | 4-6 h: 15 native frames, VLM or hand transcription, scroll stitching for 4 races | Undead panel not on screen; fall back to the spellbook General page and mark `partial` |
| 1 | Race/class matrix | 5 new combos seen (Human Hunter, Gnome Priest, Orc Mage, Troll Warlock, Dwarf Shaman) + Skyborne x5; Undead Paladin reported, not seen | High, trivial | 1 h: read the class bar in the same frames | Feed into the class picker (`#/`) as "playable by" |
| 2 | Spellbook lists (name, rank, tab) per class | New baseline spells: Holy Strike, Seal of Fury, Call of the Ancestors, Call of the Elements, Totemic Recall, Fire Nova (spell), Arcane Blast, Presence of Mind baseline, Blessing of Kings baseline, Elune's Light; tree names (Elemental Combat, Shadow Magic) | Medium-high: spell inventory at level 38 for 7 classes, links talents to what they modify | 6-8 h: window detector, page reader, dedupe across pages | ~14 pages seen; Rogue, Warlock, Priest pages not seen |
| 2 | Spellbook hover tooltips (full text) | Numbers and durations differ (Blessing of Might rank 1: 14 AP for 1 hour; Viper Sting 616 over 8 s; Seal of the Crusader judgement) | Medium: 10-20 tooltips only, but each is a confirmed Forever spell text | 3-4 h on top of the list reader: reuse the talent tooltip stages | Rank scaling visible where "Show all spell ranks" was on (paladin) |
| 2 | "What changed vs Classic" diff view | Derived from 1-2 plus talents | Highest UI value; durable after datamining because it is curated | 6-8 h web + 2-4 h data/prior for spells and racials | Needs a Classic spell/racial prior (see (b)) |
| 3 | Legacy system (Legacy Tree, Legacy Challenges) | 100 % new: seasonal Legacy Points (cap 16, 66 challenge points), categories, Hyjal Summit and Barrow Deeps as raid targets | High news value, low calculator value; mostly placeholder text | 2-3 h hand transcription from 6 frames; no pipeline | Publish as a notes page with frames, not as structured data |
| 3 | Skyborne starting zone and lore | 100 % new: Thendal Village/Grove, "shen'dorei", Rorian the Dayseeker, Coming of Age, Pesky Cirrusfly | Medium news value | 2 h hand transcription; 1 fps pass over 03:19-03:47 if more quest text is wanted | Long text; licensing risk highest here, keep to names and one quest |
| 3 | Character sheet | New layout, Spell Damage/Spell Healing split, Equipment Sets on items | Low-medium | 1 h transcription of 2 frames | A "UI notes" entry, not a dataset |
| 4 | Onboarding screens, panel slides, UI notes | Presets, rulesets (PvP/PvE/Roleplay/Hardcore), Edit Mode, Map & Quest Log | Low for a calculator | 1 h | One markdown page |
| 5 | Dungeon Experience footage | Nothing confirmed new | Skip | - | Revisit only if a new instance name shows up |

## (b) How the existing pipeline generalises

Reusable as-is (from `docs/briefs/pipeline.md` and `pipeline/src/wowtalents/`):

- `fragments.py` (`FragmentClient`, `FragmentCache`, `decode_frame`) and stage
  `01_index` once the mkv exists. All non-talent windows are short (10-40 s),
  so fragment fetching at 1 s granularity is enough for lists; hovers need
  the mkv at 4 fps like talents.
- Stage 4 tooltip detection (absdiff against a per-window median, blob with
  the tooltip aspect, dHash runs = one hover, sharpest frame). The spellbook
  tooltip is the same dark box on a light parchment background, so the
  contrast is better than on the talent grid. Anchor changes: the tooltip
  sits to the right of the hovered list entry, not on a grid cell.
- Stage 5 reader (llama-server, 2x upscale, two passes, agreement
  confidence) with a new prompt/schema per content type (section (c)).
- `validate.py` conventions (`canonical_dumps`, slug ids, `source`
  provenance, `reviewed` never overwritten), `08_export` promote flow with
  `data/overrides/`, the review UI pattern (crop beside rendered record).

What changes:

- No grid calibration. Instead a **window classifier** on each sampled frame:
  template-match the title strings ("Spellbook", "Legacy Tree", "Legacy
  Challenges", "Map & Quest Log") and the character-creation layout (three
  boxes at x 1500-1920). Cheap: OpenCV `matchTemplate` on a title crop, or
  the VLM yes/no already used in stage 0.
- **List pages instead of tooltips.** The spellbook page is a fixed 3-column
  list at known pixel columns (x ~ 235/445/655 in the 970 px crop starting at
  x 80): icon 36 px, name line, "Rank N" line, 63 px row pitch. Read the
  whole page with one VLM call returning an array (`{name, rank, tab}`), then
  cross-check the row count against detected icon squares. Page flips are
  detected by dHash of the parchment area.
- **Scroll stitching** for race panels: the trait box scrolls; dHash the box,
  read each distinct scroll position, merge by trait name, keep the frame
  with the most complete description per trait.
- **Row readers** for the character sheet: label/value pairs at fixed x;
  VLM reads the group as key-value JSON.
- **Anchoring hovers to list entries**: hovered entry = the list row whose
  y-range contains the tooltip's top-left anchor and whose icon shows the
  highlight border; cross-check name in tooltip header equals list name.
- **Classic prior** for the diff: `data/prior/classic-era/talents.json` is
  talents only. Add `data/prior/classic-era/spells.json` (name -> rank texts)
  and `racials.json` (race -> traits). Source candidates: Wowhead Classic
  spell tooltips by id (needs an id list per class, e.g. from the Classic
  spellbook dumps used by addons) or a hand-written racial file (10 races x
  ~4 traits, 1 h). Record sources in `data/prior/classic-era/SOURCES.md`.

Proposed stages (numbering continues after the talent stages so nothing
collides): `10_windows` (classify frames in the survey windows, output
`work/windows.json`), `11_spellbook` (pages + hovers -> candidates),
`12_races` (panels + class bar -> candidates), `13_changes` (diff builder,
runs on canonical files, writes `data/changes/index.json`). Hand-transcribed
content (Legacy, lore, character sheet, UI notes) goes straight to
`data/overrides/`-style manual records with `source.kind: "manual"` and a
frame reference, no stage.

## (c) Data model per content type

Same conventions as `docs/DATA-SCHEMA.md` sections 2-4: camelCase, slugs,
`additionalProperties: false`, sorted arrays, `source` on every record, one
serializer, hand edits through overrides. New schema files under
`data/schema/`; validator gains one rule set per file type.

### `data/spells/<class>.json` (schema `data/schema/spells.schema.json`)

```
{
  "schemaVersion": 1, "class": "paladin", "className": "Paladin",
  "dataSource": "video", "generatedAt": "...",
  "observedLevel": 38,                       // the demo character's level; lists are complete only up to here
  "tabs": [ { "id": "general", "name": "General", "order": 0 },
            { "id": "holy", "name": "Holy", "order": 1, "tree": "holy" } ],   // tree: link to talents/<class>.json trees[].id
  "spells": [ {
    "id": "seal-of-fury", "name": "Seal of Fury", "tab": "retribution",
    "icon": "crop-seal-of-fury", "iconSource": "crop", "iconCrop": "data/review/spells/paladin/seal-of-fury.icon.png",
    "kind": "active" | "passive" | "racial" | "racial-passive",
    "ranksSeen": [1, 2, 4],                  // "Rank N" labels seen in lists
    "tooltips": [ {                          // one per hovered rank, may be empty
      "rank": 1, "cost": "60 Mana", "range": null, "castTime": "Instant", "cooldown": null, "tools": null,
      "description": "Fills the Paladin with divine fury for 30 sec, ...",
      "source": { "kind": "video", "video": "DxtVEhjyROU", "t": 14450.0, "frame": 867000, "crop": "data/review/spells/paladin/seal-of-fury.r1.png", "confidence": 0.9, "reader": "...", "reviewed": false }
    } ],
    "classic": { "match": "none" | "exact-name" | "fuzzy-name", "spellId": 20375, "status": "new" | "changed" | "same" | "unknown", "note": "not in Classic Era" },
    "tags": ["new"],
    "source": { ...list reading provenance (frame of the page)... }
  } ],
  "notes": ["Pages seen: General, Holy, Retribution; Protection not shown on stream."]
}
```

### `data/races/<race>.json` (schema `races.schema.json`)

```
{
  "schemaVersion": 1, "race": "skyborne", "raceName": "Skyborne",
  "faction": "alliance" | "horde" | "neutral", "dataSource": "video", "generatedAt": "...",
  "variants": [ { "id": "high-order", "name": "High Order Skyborne", "faction": "alliance" },
                { "id": "windshaper", "name": "Windshaper Skyborne", "faction": "horde" } ],   // omitted for ordinary races
  "classes": ["warrior", "hunter", "mage", "rogue", "druid"],
  "classesSource": { "kind": "video", "t": 11680.0, "frame": ..., "crop": "data/review/races/skyborne/classbar.png", "reviewed": false },
  "lore": "The High Order is made up of ...",   // optional, keep short (licensing)
  "traits": [ {
    "id": "walk-on-air", "name": "Walk on Air", "kind": "active" | "passive",
    "variants": ["high-order", "windshaper"],   // omitted when shared by all
    "description": "Glide downward through the air for 10 sec",
    "icon": "crop-walk-on-air", "iconSource": "crop", "iconCrop": "...",
    "classic": { "status": "new" | "changed" | "same", "classicText": "...", "note": "..." },
    "source": { "kind": "video", ..., "reviewed": false }
  } ],
  "complete": false,                          // true once every scroll position was read
  "notes": ["Panel scrolled; second active of the Windshaper variant not seen."]
}
```

### Small hand-made files (`source.kind: "manual"`, `reviewed: true`, frame in `note`)

- `data/legacy/tree.json`: categories `[ {id, name, nodes:[{id, name, maxRank, description, placeholder: true}]} ]`, `pointsCap: 16`, `notes`.
- `data/legacy/challenges.json`: `categories` tree and `entries: [{id, name, category, description, targets: ["Ragefire Chasm", ...], points}]`.
- `data/lore/skyborne.json`: `zones`, `npcs`, `quests: [{name, giver, text?, rewards}]`, `cinematicLines`, `terms: ["shen'dorei"]`.
- `data/ui/notes.json` or `docs/research/2026-09-1x-ui-differences.md`: character sheet groups and values, onboarding texts, UI observations. Markdown is enough; no schema.

### `data/changes/index.json` (generated by `13_changes`, never hand-edited)

```
{ "schemaVersion": 1, "generatedAt": "...", "classicPrior": "data/prior/classic-era",
  "entries": [ { "id": "race:orc:shatter-curse", "type": "racial" | "spell" | "talent" | "combo" | "system",
                 "status": "new" | "changed" | "removed" | "same",
                 "class": null, "race": "orc", "name": "Shatter Curse",
                 "forever": "Immunity to Curses and Banes ...", "classic": null,
                 "ref": "data/races/orc.json#traits/shatter-curse", "confidence": 0.9, "reviewed": false } ] }
```

`status` for talents comes from `ranksPrior.match` and a text diff; for
spells and racials from the new prior files. Overrides can pin a status
(`data/overrides/changes.json`) when the automatic diff is wrong.

Review crops: `data/review/spells/<class>/<spellId>[.rN].png`,
`data/review/races/<race>/<traitId>.png`, `.../classbar.png`.

## (d) UI proposal (web app, hash routes as in `web/src/url/route.ts`)

- `#/changes` (headline for non-talent content): one list, filter chips
  by type (racial, spell, talent, combo, system), class, race and status
  (new/changed); each row shows Forever text and Classic text side by side,
  the provenance badge ("read from stream at 04:00:50, unreviewed") and a
  link to the record. Search box. Counts in the chips ("Racials: 27 changed").
- `#/races` (matrix: races x classes with new combos highlighted) and
  `#/races/<race>` (traits with icon crops, variant tabs for Skyborne, lore
  collapsed, `complete: false` caveat).
- `#/spells/<class>` (tabs as in the spellbook, list of name + ranks seen,
  hover/expand shows the tooltip(s) read from stream; entries without a
  tooltip show "list only"). Optional `?tab=holy`.
- `#/legacy` (tree categories and challenge list from the manual files, with
  the frames as images) and `#/notes` (UI differences, onboarding texts,
  Skyborne lore). Both mostly static.
- Cross-links: in the talent `Tooltip`, spell names that occur in the
  description (matched against `data/spells/<class>.json` names, longest
  match first, pure function in `web/src/rules/spellLinks.ts` with tests)
  become links to `#/spells/<class>?spell=<id>`; the spell page lists
  "modified by" talents back (same match, reversed). Race pages link to
  `#/<class>` for each playable class; the class picker shows "playable by"
  race icons.
- Header nav gains Changes / Races / Spells; the class picker stays the
  home page. Data loading follows `web/src/data/load.ts` (static JSON,
  schema-checked at build time; new schema tests next to `schema.test.ts`).

## (e) Phased plan (after Phase 2 "all classes" in `docs/PLAN.md`)

Phase 2b: races and combos (target 2026-09-16, half a day)
- Fetch the character-creation windows at 1 fps (six windows, ~9 min, from
  the mkv), classify frames, read panels and class bars, stitch scrolls.
- Hand-write `data/prior/classic-era/racials.json`.
- Acceptance: `data/races/*.json` for all 10 races validate; every trait has
  a frame and crop; 9 races `complete: true` or a note saying what is
  missing; class matrix matches the frames; `#/races` and `#/races/<race>`
  live; at least 20 racial entries appear in `#/changes` with status.

Phase 2c: spellbook (target 2026-09-17, one day)
- `10_windows` over the survey windows, `11_spellbook` lists + hovers for
  the classes seen (paladin, mage, warrior, shaman, druid, hunter, rogue
  General), Classic spell prior by name.
- Acceptance: every spellbook page in the inventory produces a list whose
  row count equals the detected icons; every hover in the inventory is
  attached to a spell with a crop; `data/spells/<class>.json` validate;
  `#/spells/<class>` live; talent tooltips link to at least one spell for
  paladin and shaman.

Phase 2d: changes view and notes (target 2026-09-18, one day)
- `13_changes`, `#/changes` with filters, `data/legacy/*`, `data/lore/
  skyborne.json`, UI notes page, `#/legacy`, `#/notes`.
- Acceptance: `#/changes` shows talents + racials + spells with Classic
  text where a prior exists; every entry links to its record and frame;
  owner review pass on all `new` entries; OG/SEO for `#/changes`.

Phase 3 (existing): the datamined importer also fills `data/spells/` and
`data/races/` (Spell.db2, ChrRaces/ChrRaceXChrModel, SkillLine), which
turns the `changes` diff from "what we saw" into "what the client says";
the curated statuses survive as overrides.

## (f) Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Game text licensing: spell, racial, quest and lore text is Blizzard's; we republish it verbatim in a public MIT repo | Takedown or reputational risk; larger for long lore/quest text than for tooltip fragments | Mirror Wowhead's practice: short tooltip text with attribution and a data notice ("game text (c) Blizzard Entertainment, reproduced for reference"); keep quest text to a name and one line; license the repo's data directory separately from the code (note in README); no cinematic transcript |
| Review effort: scroll stitching and list reading multiply records (~110 spells, ~50 traits, ~20 tooltips) on top of ~450 talents | Owner review becomes the bottleneck | Review only `new`/`changed` entries first (the diff builder flags them); list entries (name + rank) need no per-record review beyond a spot check; ship unreviewed with the provenance badge as for talents |
| Low value after datamining (2026-09-17 + days): spells and racials will be in DB2 within a week | Days of work superseded | Do 2b (small, cheap, high news value) before beta; make `#/changes` the durable feature (curation, side-by-side Classic text, links) that datamined data feeds rather than replaces; skip 2c if the download or talents slip |
| Demo build differs from beta (Legacy nodes say "To be added in future patch content"; level-38 demo characters; premade UI settings) | Published data goes stale or is wrong for beta | Tag every record with `build: "blizzcon-demo-2026-09-12"` in `notes`/`source.note`; date the pages; datamined import replaces by id |
| Pages never shown (Rogue, Warlock, Priest spellbooks; Undead race panel) | Incomplete datasets look broken | `complete: false` + "not shown on stream" notes in the UI; do not fill from Classic |
| VLM misreads on dense lists (3 columns, 12 px rank labels) | Wrong ranks/names | Two reads, icon-count cross-check, name match against Classic names, review queue as for talents |
| Scope creep on lore and UI notes | Time lost on low-value pages | Time-box hand transcription to the numbers in (a); markdown pages, no schemas for lore/UI |

# Handover: races (Phase 2b data half)

Date 2026-09-13. Owner of this session: pipeline and data. `web/` was not
touched; section 5 is the spec the web owner needs.

## 1. What was done

Phase 2b of `docs/briefs/beyond-talents.md`, the data half: every racial trait
and the race/class matrix, extracted, validated, with provenance and crops.

New code:

| File | What |
|---|---|
| `pipeline/src/wowtalents/races.py` | Pure helpers: screen classification, portrait selection, class bar, race-box geometry, trait text, fragment removal, order stitching, band alignment, merge. |
| `pipeline/stages/12_races.py` | `scan` / `read` / `build`. |
| `pipeline/validate_races.py` | Rules R1-R15 and M1-M4, `--check`, `--report`, `--json`, `--strict`. Owns the race serializer. |
| `pipeline/tests/test_races.py` | 44 tests, all pure. |
| `data/schema/race.schema.json`, `race-matrix.schema.json` | Machine schemas. |
| `docs/DATA-SCHEMA-RACES.md` | Normative contract. |

Changed code: `reader.py` gains `RACE_PANEL_*` and `RACIAL_LIST_*` plus two
`Reader` methods; `mkv.decode_cmd/decode_range` gain `every=` (section 4);
`export.orphan_crops` gains `FOREIGN_REVIEW_DIRS` so promoting a class no
longer deletes race crops; CI validates `data/races/` too.

New data: `data/races/<race>.json` (9 files), `data/races/matrix.json`,
`data/review/races/<race>/*.png` (91 crops, 3.6 MB),
`data/extracted/races.json` (all readings), `data/extracted/races.md`
(inventory), `data/prior/classic-era/racials.json` and `racial-diff.json`
(both `verified: false`).

Commands, in order, from `pipeline/`:

```bash
uv run stages/12_races.py scan                  # 63 s, 2980 frames -> 119 panel states
uv run stages/12_races.py read --codex race     # 148 s VLM + ~8 min codex, 33 distinct states
uv run stages/12_races.py build                 # < 2 s
uv run python validate_races.py --check ../data/races/*.json    # 0 errors, 0 warnings
uv run pytest -q                                # 363 passed
```

## 2. Counts and confidence

**37 traits over 9 races; 14 new, 16 changed, 7 same versus Classic Era.**
Every trait has `source.confidence 1.0`, a row crop and a 36 px icon crop.
Every race is `complete: true`. Nothing is reviewed (`source.reviewed` is
`false` everywhere), so the review queue is all 37.

| Race | Faction | Traits | Classes | Lore |
|---|---|---|---|---|
| Dwarf | alliance | 4 (2 new) | 6 | partial |
| Gnome | alliance | 4 (1 new) | 5 | partial |
| Human | alliance | 4 (1 new) | 7 | partial |
| Night Elf | alliance | 4 (1 new) | 5 | partial |
| Orc | horde | 4 (1 new) | 6 | partial |
| Skyborne | neutral | 5 (5 new) | 5 per variant | Windshaper full, High Order one line |
| Tauren | horde | 4 (1 new) | 4 | full |
| Troll | horde | 4 (1 new) | 7 | partial |
| Undead | horde | 4 (1 new) | 6 | partial |

Confidence is the agreement of two VLM passes (3x and 2x upscale) on the same
crop: 1.0 identical, 0.7 same name and kind, 0.3 otherwise. One scroll position
per race also went through the `codex` CLI as a third opinion; **all ten agreed
verbatim with both passes**, which is why nothing sits below 1.0. Class lists
come from OpenCV only (lit icons score 19-101 on mean saturation x value,
greyed ones 5-9; the smallest separation margin seen was 10.5).

The full per-trait table is `data/extracted/races.md`.

## 3. What the survey got wrong (corrections recorded in `data/extracted/other-content.md`)

1. **Undead does have a race panel.** 05:23:40-05:24:20 plus two shorter
   looks at 03:15:06 and 03:45:02, all in minutes the 60 s probe grid stepped
   over. All four Undead racials were read from the box with descriptions;
   the spellbook General page fallback was built but is now only a
   cross-check (`_read_undead`, `source.panel: "spellbook-general"` is
   supported and currently unused).
2. **The two Skyborne variants have different class lists.** High Order
   (Alliance): Warrior, Hunter, Mage, Rogue, Druid. Windshaper (Horde):
   Warrior, Hunter, Rogue, Druid, **Shaman**, no Mage. The survey listed one
   row for both.
3. Two more character-creation windows exist (05:23:40 and 05:50:10), found
   by classifying all 541 stage-0 probe minutes for the two faction banners.
4. Two traits nobody had seen: Dwarf **Big Game Hunter** (Damage to Beasts
   increased by 5%) and Troll **Rapid Regeneration** (Regenerate 50% of
   maximum Health over time).
5. The "~45-55 traits" estimate is really 37: four per race, five for
   Skyborne across both variants.

Race/class matrix: all three combinations Warcraft Tavern reported are
confirmed on screen — **Undead Paladin**, **Dwarf Shaman**, **Tauren
Shaman and Druid**. No disagreements. Every race's class bar was read, so
`matrix.json` has no `observed: false` row. New versus Classic on screen:
Human Hunter, Gnome Priest, Orc Mage, Troll Warlock, Dwarf Shaman, Undead
Paladin, Tauren Druid, plus both Skyborne variants.

## 4. Surprises and decisions

- **`-vf fps=2` lies.** ffmpeg's `fps` filter returns a frame up to a quarter
  second away from the nominal time. At stream 11520 that is the difference
  between the Dwarf box and the Human box, i.e. a trait filed under the wrong
  race. `mkv.decode_range(..., every=30)` now uses `select=not(mod(n,30))`
  plus `-vsync 0` (ffmpeg 4.4 has no `-fps_mode`) and is exact to the frame.
  Stages 3/4/4b are unaffected — they run at 60 fps — but any future stage
  that subsamples must use `every`.
- **No VLM for the race or the class list.** The selected portrait's gold
  border and the greyed-out class icons are unambiguous in pixels (margin 56+
  and 10+ respectively), so the two facts most likely to be misattributed are
  never read by a model. The VLM only reads text.
- **Row fragments.** A row whose name has scrolled above the box edge still
  shows its icon, so the reader files the tail as its own trait ("Damage to
  Beasts: increased by 5%"). Such a record is always contained in the row it
  came from; `races.drop_fragments` removes it on that test, at the unit level
  rather than per state, because the parent row usually appears in a different
  scroll position.
- **A text diff against a paraphrase is useless.** `racials.json` is written
  from memory, so comparing it to the Forever text says "changed" 23 times out
  of 23. The same/changed verdict therefore lives in
  `racial-diff.json` as a hand judgement, and a matched name with no verdict
  is `unknown`, not a guess. Both files carry `verified: false`; replace them
  as soon as a sourced Classic racial list exists and rebuild.
- **Lore is stored.** Roughly a paragraph per race, the same order of
  magnitude as one tooltip, with `loreComplete: false` where it ran past the
  box. Only the Skyborne paragraphs are new text; the rest is Classic
  character-creation copy. If the owner prefers the brief's stricter reading
  of the licensing risk, delete `lore`/`loreSource` from the eight non-Skyborne
  files and drop the fields from `_race_doc`; nothing else depends on them.
- **`complete` means two anchors**, not "we read a lot": some frame showed the
  box scrolled to the top (race name above the first row) and some frame
  showed the lore (below the last row). Scroll positions overlap, so those two
  anchors prove the stitched list is the whole list.

## 5. The JSON the web page reads (spec for the web owner)

Static files, loaded like class files (`web/src/data/load.ts`). Full field
tables: `docs/DATA-SCHEMA-RACES.md` sections 4 and 5. The short version:

```jsonc
// data/races/<race>.json    -- one per race, nine files, ids:
// human dwarf night-elf gnome skyborne orc undead tauren troll
{
  "schemaVersion": 1,
  "race": "skyborne", "raceName": "Skyborne",
  "faction": "alliance" | "horde" | "neutral",   // neutral = shown in both columns
  "dataSource": "video", "generatedAt": "2026-09-13T...Z",

  // present ONLY for skyborne today; omit-safe
  "variants": [
    { "id": "high-order", "name": "High Order Skyborne", "faction": "alliance",
      "classes": ["druid","hunter","mage","rogue","warrior"],
      "lore": "...", "loreComplete": false }
  ],

  "classes": ["druid","hunter","mage","rogue","shaman","warrior"],  // sorted; UNION over variants
  "classesSource": { /* Source, panel: "class-bar", reader: "opencv-classbar" */ },

  "lore": "...", "loreComplete": false, "loreSource": { /* Source */ },  // absent for a race with variants

  "traits": [{
    "id": "walk-on-air", "name": "Walk on Air",
    "kind": "active" | "passive",
    "order": 0,                                  // row position in the box; render in this order
    "variants": ["high-order","windshaper"],     // present iff the file has variants
    "description": "Glide downward through the air for 10 sec",   // MAY BE ABSENT
    "icon": "crop-walk-on-air", "iconSource": "crop",
    "iconCrop": "data/review/races/skyborne/walk-on-air.icon.png", // 36x36 PNG, render directly
    "classic": { "status": "new" | "changed" | "same" | "unknown",
                 "classicName": "...", "classicText": "...", "note": "..." },
    "tags": ["new"],                             // new | reworked | classic-unchanged
    "source": { "kind": "video", "video": "DxtVEhjyROU", "t": 11680.5, "frame": 700830,
                "crop": "data/review/races/skyborne/walk-on-air.png",
                "panel": "race-panel" | "class-bar" | "spellbook-general",
                "confidence": 1.0, "reader": "Qwen3VL-4B-Instruct-Q4_K_M",
                "readings": [{ "reader": "...", "name": "...", "description": "...", "confidence": 1.0 }],
                "reviewed": false, "note": "..." }
  }],
  "complete": true,
  "notes": ["..."]                               // show these; they carry the caveats
}
```

```jsonc
// data/races/matrix.json    -- derived, one file
{ "schemaVersion": 1, "dataSource": "video", "generatedAt": "...",
  "classes": ["warrior","hunter","mage","rogue","priest","warlock","paladin","druid","shaman"],  // bar order
  "races": [{ "race": "skyborne", "raceName": "Skyborne", "faction": "neutral",
              "classes": [...],                       // equals the race file's classes
              "byVariant": { "high-order": [...], "windshaper": [...] },   // optional
              "observed": true,                       // false = class bar never seen; render as "unknown"
              "reportedElsewhere": ["paladin"],       // optional third-party claim
              "agreement": "confirmed on screen",     // optional
              "disagreement": "..." }],               // optional; show it, do not resolve it
  "notes": ["..."] }
```

Rules the UI must follow:

1. `classes: []` and `observed: false` mean **unknown**, never "no classes".
   Today no race is in that state, but keep the branch.
2. Every trait is unreviewed. Show the same trust line the talent tooltip
   shows, with `source.t` formatted as a stream timestamp
   (`t / 3600` -> `HH:MM:SS`) and a link to `source.crop`.
3. `description` may be absent (a racial known only by name); render
   `source.note`, which then says why, instead of an empty line.
4. `classic.classicText` is an **unverified paraphrase written from memory**.
   Label it as such wherever it appears; never present it as game text. The
   note field repeats the warning, so rendering `note` satisfies this.
5. Sort traits by `order` (the box order); do not sort by name or kind.
6. Icons exist only as PNG crops. Render `iconCrop` directly; fall back to the
   trait's initials when it is missing, as the talent grid does.
7. Skyborne: pick a variant (default Alliance), filter `traits` by
   `variants.includes(id)` and show that variant's `classes`, not the union.
   `variants[].lore` replaces the top-level `lore` for this race.
8. `complete: false` and every `notes[]` entry are caveats the page must show.
   Nothing is `false` today, so the state needs a design but no data yet.

Routes proposed in the brief: `#/races` (the matrix, new combos highlighted)
and `#/races/<race>` (traits with crops, variant tabs for Skyborne, lore
collapsed). Suggested highlight rule for "new combo": a cell in `matrix.json`
that is not in `data/prior/classic-era/racials.json`'s `races[race].classes`
— that list is in the same prior file and equally unverified, so label it.

## 6. What is missing / next

1. **Review.** 37 of 37 traits are unreviewed. The crops are in
   `data/review/races/<race>/`; `uv run python validate_races.py --report
   ../data/races/*.json` prints the queue. There is no overrides mechanism for
   races yet: `DATA-SCHEMA-RACES.md` section 1 says what to build
   (`data/overrides/races/<race>.json` plus a "never overwrite `reviewed`"
   rule in `build`), roughly an hour of work, and it should exist before the
   first review round or the next rebuild will discard the corrections.
2. **The Classic prior.** `racials.json` and `racial-diff.json` are from
   memory. Replacing them with a sourced list (Wowhead Classic racial spell
   ids, or the beta DB2 from 2026-09-17) changes 23 `classic` blocks and needs
   only a rebuild.
3. **High Order Skyborne lore** is one line; no frame showed that box scrolled
   into the paragraph. Low value, but a 4 fps pass over 03:14:30-03:15:00 and
   06:07:00-06:07:20 would probably get it.
4. **Racial icons are crops only.** Stage 9's matcher runs on talents; pointing
   it at `data/review/races/*/*.icon.png` would resolve the Classic ones to
   icon names and leave the genuinely new ones (all five Skyborne, Will to
   Survive, Eureka!, Shatter Curse, Touch of the Grave, Rapid Regeneration,
   Big Game Hunter) as crops. Maybe an hour.
5. **Faction and class descriptions** (the first and third box of the same
   screen) were never read. The faction text is two paragraphs of Classic
   copy; the class descriptions are Classic flavour text. Low value, and the
   geometry is already there if wanted.
6. **Phase 2c (spellbook)** is untouched; the brief's plan still stands and
   `12_races.py` is the template for `11_spellbook` (window classifier, list
   reader, dedupe by dHash, two passes plus codex).

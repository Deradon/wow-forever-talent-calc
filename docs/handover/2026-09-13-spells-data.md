# Handover: spellbook (Phase 2d)

Date 2026-09-13. Owner of this session: pipeline and data. `web/` was not
touched; section 5 is the spec the web owner needs and section 6 is the
recommendation on whether to build the page at all.

## 1. What was done

Phase 2d of `docs/PLAN.md` (brief: `docs/briefs/beyond-talents.md`): the spell list of every class the
stream showed, the full text of every hover tooltip it showed, and an explicit
coverage record per class, with provenance and crops.

New code:

| File | What |
|---|---|
| `pipeline/src/wowtalents/spells.py` | Pure helpers: window locator, page geometry, page-state comparison, tooltip detection and anchoring, list-text parsing, merging, dedupe. |
| `pipeline/stages/11_spellbook.py` | `scan` / `read` / `build`. |
| `pipeline/validate_spells.py` | Rules S1-S15, `--check`, `--report`, `--json`, `--strict`. Owns the spell serializer. |
| `pipeline/tests/test_spells.py` | 98 tests, all pure. |
| `pipeline/assets/spellbook-title.png` | The 733x26 title-bar template the locator matches. |
| `data/schema/spell.schema.json` | Machine schema. |
| `data/prior/classic-era/spells-baseline.json` + `.md` | The Classic Era name prior, `verified: false`. |

Changed code: `reader.py` gains `SPELL_LIST_*`, `PAGE_HEAD_*`, `SPELL_TOOLTIP_*`
and three `Reader` methods; `export.FOREIGN_REVIEW_DIRS` gains `"spells"` so
promoting a class no longer deletes spell crops; CI validates `data/spells/`
too; `data/prior/classic-era/SOURCES.md` and `data/extracted/other-content.md`
record the new prior and seven survey corrections.

New data: `data/spells/<class>.json` (8 files), `data/review/spells/<class>/*.png`
(765 crops, 14 MB), `data/extracted/spells.json` (all readings),
`data/extracted/spells.md` (inventory with the coverage table).

Commands, in order, from `pipeline/`:

```bash
uv run stages/11_spellbook.py scan                 # 196 s, 6680 frames -> 213 page states, 118 tooltips
uv run stages/11_spellbook.py read --codex page    # 600 s VLM (818 calls) + ~4 min codex, 90 distinct pages
uv run stages/11_spellbook.py build                # < 30 s
uv run python validate_spells.py --check ../data/spells/*.json   # 0 errors, 12 warnings
uv run pytest -q                                   # 461 passed
```

## 2. Counts and confidence

**327 list entries over 8 classes, 112 full hover tooltips, 16 names with no
Classic Era counterpart.** Priest is the only class the stream never shows.
Every entry has a row crop and a 40 px icon crop; every tooltip has its own
crop. Nothing is reviewed (`source.reviewed` is `false` everywhere).

| Class | Entries | Tooltips | New names | Tabs seen | Tabs missing | Show all ranks | Below 0.8 |
|---|---|---|---|---|---|---|---|
| Druid | 41 | 27 | 2 | Balance, Feral Combat, Restoration | General | not observed | 1 |
| Hunter | 63 | 36 | 0 | General, Beast Mastery, Marksmanship, Survival, **Pet** | - | on | 0 |
| Mage | 45 | 32 | 3 | General, Arcane, Fire, Frost | - | not observed | 1 |
| Paladin | 48 | 6 | 2 | General, Holy, Protection, Retribution | - | on | 0 |
| Rogue | 15 | 1 | 0 | General | all three trees | not observed | 3 |
| Shaman | 59 | 9 | 6 | General, Elemental Combat, Enhancement, Restoration | - | on | 3 |
| Warlock | 10 | 0 | 1 | General | all three trees | on | 0 |
| Warrior | 46 | 1 | 2 | General, Arms, Fury, Protection | - | not observed | 2 |
| **Priest** | **-** | **-** | **-** | **never on screen** | all four | - | - |

Confidence is the agreement of two VLM passes (3x and 2x upscale) on the same
crop: 1.0 identical, 0.7 same name at a different rank or kind, 0.3 otherwise,
0.0 when only one pass saw the row. One column per class and tab also went
through the `codex` CLI as a third opinion (28 calls); a codex reading that
differs from two agreeing passes caps the row at 0.9. **315 of 327 entries sit
at 1.0.** The 10 rows below 0.8 are in the review queue
(`validate_spells.py --report`); four of them are readings the model invented
while a tooltip stood over the column (`Shapeshift`, `Evocation Dampen Magic`,
`Reincarnation Passive`, `Rummel Whirlwind`) and are the first thing a reviewer
should delete.

The 16 names with no Classic Era counterpart, which is the headline for a
"what changed" page:

| Class | New names |
|---|---|
| Paladin | **Holy Strike**, **Seal of Fury** |
| Shaman | **Call of the Ancestors**, **Call of the Elements**, **Fire Nova** (a spell, not the totem), **Totemic Recall**, **Totemic Projection** |
| Mage | **Arcane Blast**, **Comprehend Scroll** |
| Warlock | **Bane of Agony** (Classic's Curse of Agony, renamed -- the whole curse line probably follows) |
| Warrior | **Victory Rush** |
| Druid | **Revive** |

Six more are Classic *talents* that appear in a Forever spellbook: Aimed Shot,
Presence of Mind, Blessing of Kings, Tactical Mastery, Nature's Grasp, Omen of
Clarity. The records say so and explicitly refuse to conclude "now baseline" --
the demo characters have talent points spent and may simply have taken them.

The full per-entry table is `data/extracted/spells.md`.

## 3. What the survey got wrong (corrections recorded in `data/extracted/other-content.md`)

1. **Rogue and Warlock were both on screen.** Rogue General at 06:13:45 (the
   spellbook is on the right half of the screen next to the Map & Quest Log,
   which is why an eyeball pass over a fixed rectangle missed it); a **Warlock**
   searching "Bane of Agony" at 05:18:40-05:19:10, a window the survey does not
   list at all. **Priest is the only class never shown.**
2. **Almost every "page not seen" was seen**: Paladin Protection, Mage Frost,
   Warrior Arms and Protection, Shaman Enhancement and Restoration, Druid
   Balance and Feral Combat, Hunter Beast Mastery and Survival. Genuinely
   missing: the Druid General page and the three tree pages each of Rogue and
   Warlock.
3. **The hunter has a Pet page** (05:56:17) with the pet's own abilities.
4. **The counts are three times the estimate**: 213 page states, 90 distinct
   pages, 327 entries, 112 tooltips.
5. **"Show all spell ranks" is real** and confirmed on for paladin, hunter,
   shaman and warlock; the dropdown is caught mid-toggle at 04:00:11.
6. **The spellbook window moves** (x 232 normally, 1013 at 06:14, 813 at 06:20).
7. The shaman window at 05:41:30-05:42:40 ends on a **druid** page; stage 11
   reassigns such a state by its heading, because "Feral Combat" belongs to
   exactly one class.

## 4. Surprises and decisions

- **A dHash of flat UI is noise.** The first state grouper hashed the tab strip
  and search box and split a 3-minute window into 41 "states", one per second:
  the blinking search caret is the only structure in that crop, so 12-19 of the
  64 bits flip between two identical frames. Everything now compares
  *changed-pixel fractions* over tight crops (`spells.change_fraction`), and the
  crops must be tight: over the generous title box "Retribution" and
  "Protection" differ in 3.8 % of pixels, which is the level at which the
  stream's one-second keyframes make unchanged text flicker. Over the tight box
  the same page scores 0.000-0.002 and a different one 0.069-0.093.
- **Three signals decide "same page", not one.** The heading catches a tab
  switch, the search text catches a second query under the same "Name Matches"
  heading, and the list itself catches a change with neither -- which is exactly
  what toggling "Show all spell ranks" does. The list test is the **median** of
  the 21 per-cell change fractions, because a hover tooltip blots out four to
  six cells and a mean would sit halfway between "same" and "different"
  (measured: 0.000-0.003 holding still, 0.14 on a real change, tooltip or no).
- **The background must be a high quantile, not a median.** The paladin's Seal
  of the Crusader hover covers 20 of its state's 38 frames, so the median frame
  *contains* the tooltip and differencing against it finds nothing. The tooltip
  is dark and the parchment under it is bright, so the per-pixel 85th percentile
  removes it (`spells.composite`) and doubles as the clean page the list reader
  gets.
- **The spellbook tooltip is not the talent tooltip.** Its body is translucent,
  grey 20-90 over parchment, where the talent window's is grey 1-3.
  `ui.find_tooltip`'s darkness gate (fraction below 40) rejects it outright,
  which is why stage 11 has its own detector instead of reusing stage 4's.
- **The anchor is the filter.** A tooltip box must sit with its left edge at a
  column's name start and its bottom edge within 30 px of a row's icon top;
  candidates that fit no cell are dropped. That one test removes every dark
  patch of moving world from the results, and it is also how a tooltip gets its
  rank (23 of 112 resolved; the rest come from pages that deduplication did not
  read).
- **Group hovers by cell, not by image.** The box fades in over two or three
  frames, so a hash-based run tracker filed the rogue's single Shadowmeld hover
  as fourteen, eleven of them half-drawn. Grouping by the anchored cell and
  keeping the largest box per cell fixed it.
- **OpenCV counts the icons, the model reads the names.** Where the model
  returns more names than the column has icon discs, the surplus is dropped
  (4 cases). Where it returns a sentence as a name, `looks_like_prose` drops it
  (too long, sentence punctuation, or four-plus words that are not Title Case).
  Both are cheap and they removed every schema violation in the first build.
- **Racials and pet abilities are not class spells.** The General page lists the
  character's racials, and diffing those against a class spell list made every
  one of them "new" (86 false positives). They are recognised by the row's own
  "Racial" subtitle and by name against `data/races/*.json`, and the record
  points at `data/races/<race>.json` where the verdict already lives. The hunter
  Pet page gets its own `_pet` bucket in the prior. That is what took the "new"
  count from 86 to 16.
- **The prior can only say "new" or "unknown".** `spells-baseline.json` holds
  names, no tooltip text, so a spell whose numbers moved cannot be told from one
  that did not. `Blessing of Might` rank 1 giving 14 attack power for **one
  hour** is exactly that case. Replacing the prior with a sourced list *with
  text* is the single biggest improvement available here (section 6).

## 5. The JSON the web page reads (spec for the web owner)

Static files, loaded like class files (`web/src/data/load.ts`). Machine schema:
`data/schema/spell.schema.json`. The short version:

```jsonc
// data/spells/<class>.json -- one per class, eight files today (no priest):
// druid hunter mage paladin rogue shaman warlock warrior
{
  "schemaVersion": 1,
  "class": "shaman", "className": "Shaman",
  "dataSource": "video", "generatedAt": "2026-09-13T...Z",
  "observedLevel": 38,          // the demo character's level; lists stop here

  "tabs": [ { "id": "general", "name": "General", "order": 0 },
            { "id": "elemental-combat", "name": "Elemental Combat", "order": 1 } ],
  // ONLY the tabs that were opened on stream. A tab that was not is in
  // coverage.tabsMissing and simply has no spells here.

  "spells": [{
    "id": "stoneclaw-totem", "name": "Stoneclaw Totem",
    "kind": "active" | "passive" | "racial" | "racial-passive",
    "tab": "elemental-combat",          // ABSENT when the row was only seen on a
                                        // search page or under an unreadable heading
    "ranksSeen": [4],                   // ABSENT for a rankless row; see rule 3
    "icon": "crop-stoneclaw-totem", "iconSource": "crop",
    "iconCrop": "data/review/spells/shaman/stoneclaw-totem.icon.png",   // 40x40 PNG
    "tooltips": [{                      // ABSENT unless the spell was hovered
      "rank": 4,                        // optional, see rule 4
      "cost": "75 Mana", "range": "8-35 yd range", "castTime": "Instant",
      "cooldown": "30 sec cooldown", "tools": "Earth Totem", "requires": ["..."],
      "description": "Summons a Stoneclaw Totem with 280 health ...",
      "footer": "You haven't added this to your action bars",
      "source": { /* Source, panel: "tooltip" */ }
    }],
    "classic": { "status": "new" | "changed" | "same" | "unknown",
                 "classicName": "...", "note": "..." },   // note is ALWAYS present
    "tags": ["new"],
    "source": { "kind": "video", "video": "DxtVEhjyROU", "t": 20015.5, "frame": 1200930,
                "crop": "data/review/spells/shaman/stoneclaw-totem.png",
                "panel": "spell-list", "confidence": 1.0,
                "reader": "Qwen3VL-4B-Instruct-Q4_K_M",
                "readings": [{ "reader": "...", "name": "...", "rank": 4 }],
                "reviewed": false, "note": "..." }
  }],

  "coverage": {
    "pagesSeen": ["Elemental Combat", "Enhancement", "General", "Name Matches", "Restoration"],
    "tabsSeen": ["elemental-combat","enhancement","general","restoration"],
    "tabsMissing": [],                  // General + trees never opened
    "states": 16, "entriesRead": 59, "tooltipsRead": 9, "tooltipsUnmatched": 3,
    "showAllSpellRanks": "on" | "off" | "not observed",
    "observedLevel": 38,
    "windows": ["05:33:35", "..."]      // stream times of the page states
  },
  "complete": false,                    // false for every class read from this stream
  "notes": ["..."]                      // show these; they carry the caveats
}
```

Rules the UI must follow:

1. **This is not a spell list, it is a coverage record.** Render
   `coverage.tabsMissing` as prominently as the spells: for the rogue and the
   warlock the page is one General tab and three empty ones, and a reader who
   does not see that will read "the Forever rogue has 15 spells". Priest has no
   file at all; the class picker must say "never shown on stream", not 404.
2. Every entry is unreviewed. Show the same trust line the talent tooltip shows,
   with `source.t` formatted as a stream timestamp (`t / 3600` -> `HH:MM:SS`)
   and a link to `source.crop`.
3. `ranksSeen` is **what was on screen**, not the spell's rank range. With
   "Show all spell ranks" off it is the single highest rank the character knew;
   `coverage.showAllSpellRanks` says which. Never render it as "ranks 1-4".
4. A tooltip's `rank` is present only when the hover could be tied to a list
   row on a page that was read (23 of 112). Without it, show the tooltip as
   "one rank, which one is not known" -- `source.note` says exactly that.
5. Sort spells the way the file does (tab, then id); the page itself is
   alphabetical within a tab, so that matches the game.
6. Icons exist only as PNG crops. Render `iconCrop` directly; fall back to the
   spell's initials when it is missing, as the talent grid does.
7. `classic.status` is **name-level only**. `new` means "this name is not in an
   unverified list written from memory"; `unknown` means "the name exists in
   Classic, and nothing is claimed about the text". There is no `same` and no
   `changed` in the data today. `classic.note` always spells this out -- render
   it.
8. A spell with no `tab` came from a search-results page or from a page whose
   heading a tooltip covered; group those under "seen only in a search" rather
   than inventing a tab for them.

Route proposed in the brief: `#/spells/<class>` with the tabs as in the
spellbook, optional `?tab=holy`. Cross-links to and from the talent tooltip
(`web/src/rules/spellLinks.ts`) are still worth building: 327 names is enough
for a longest-match matcher to light up most talent descriptions.

## 6. Is `#/spells/<class>` worth building? **Yes, but as a tooltip page, not a spell list.**

The case for it: 112 verbatim Forever tooltips with cost, cast time, range,
cooldown and reagents is content that exists nowhere else until datamining
lands on 2026-09-17, and it stays interesting afterwards because it is a
*confirmed screenshot* of the demo build. Seven of the eight classes have their
whole tree tab set. The 16 new names are the sharpest "what changed" evidence
the project has, sharper than the talent diff, because a new baseline spell is a
bigger deal than a moved talent.

The case against it: the lists are **not** spell lists. They are a level-38
character's spellbook, filtered by which tabs Xaryu happened to open. A page
titled "Shaman spells" showing 59 rows will be read as a claim about the game
and it is not one, and the rogue (15 rows, one tab) and the warlock (10 rows)
are actively misleading if presented as a list. Priest is absent entirely.

The recommendation, in order:

1. **Build it, but scope it as "spells seen on stream", and put the coverage
   record in the header, not in a footnote.** One line per class: "4 of 4 tabs,
   48 entries, 6 tooltips, level 38" / "1 of 4 tabs -- only the General page was
   ever open". The route earns its place on the tooltips, so lead with the
   spells that have one (the shaman's 9, the hunter's 36, the mage's 32) and
   render the rest as a plain secondary list.
2. **Ship `#/changes` first if only one can be built.** The 16 new names plus
   the six Classic-talents-now-in-the-spellbook are a single screen, they need
   no coverage caveat beyond the one sentence the prior demands, and they are
   the part a player actually wants. `#/spells/<class>` is the supporting
   detail behind it.
3. **Do not ship the cross-links from talent tooltips until the review round is
   done.** Linking a talent description to a name that a 4B model read once is
   how a typo becomes a permanent id.

Effort estimate for the page as scoped: half a day on a pure `spellsModel.ts`
plus a generated `spells-index.json`, the same shape as `racesModel.ts`.

## 7. What is missing / next

1. **Review.** 327 of 327 entries and 112 of 112 tooltips are unreviewed. The
   crops are in `data/review/spells/<class>/`;
   `uv run python validate_spells.py --report ../data/spells/*.json` prints the
   queue. Start with the 10 rows below 0.8 and the two `TAB-OVER-CAPACITY`
   warnings (druid Feral Combat 22 and mage Arcane 23 entries against a 21-row
   page -- both are one invented row). There is **no overrides mechanism for
   spells yet**; build one (`data/overrides/spells/<class>.json` plus a "never
   overwrite `reviewed`" rule in `build`) before the first review round or the
   next rebuild discards the corrections. Roughly an hour, and it is the same
   gap `docs/handover/2026-09-13-races-data.md` section 6 reports for races --
   worth doing once for both.
2. **The Classic prior.** `spells-baseline.json` is names, written from memory,
   `verified: false`. Replacing it with a sourced list *including tooltip text*
   turns 300 `unknown` verdicts into real `same` / `changed` ones and needs only
   a rebuild. This is the highest-value follow-up in the whole spell dataset.
3. **Priest.** Never on screen in 03:00:00-06:20:00. Nothing to extract; the
   class file is genuinely absent rather than empty, and the UI must handle that.
4. **The tabs nobody opened**: Druid General, Rogue Assassination / Combat /
   Subtlety, Warlock Affliction / Demonology / Destruction. A 4 fps pass over
   the rest of the stream (outside the 03:00-06:20 source window) is the only
   way to find more, and `WINDOWS` in `pipeline/stages/11_spellbook.py` plus the
   title-bar locator makes that a one-line change if the owner wants it.
5. **Spell icons are crops only.** Stage 9's matcher runs on talents; pointing
   it at `data/review/spells/*/*.icon.png` would resolve the Classic ones to
   icon names and leave the genuinely new ones as crops. Maybe an hour, and it
   would cut the 14 MB of review crops substantially.
6. **`data/changes/index.json`** (brief section (c), stage `13_changes`) is
   still unbuilt. It now has three inputs instead of two: talents, races and
   spells.

# Classic Era baseline spells: an unverified prior

`spells-baseline.json` next to this file lists, per class, the **names** of the
spells a Classic Era (patch 1.12) character learns from a trainer, plus a
`_shared` bucket for the rows every class has on the spellbook's General page
(Attack, Shoot, Dodge, Parry, the armour and weapon proficiencies, the
professions). Stage 11 (`pipeline/stages/11_spellbook.py build`) uses it for one
question and one question only:

> Does Classic Era have a spell of this name for this class?

## Status: written from memory, `verified: false`

Nobody retrieved this list. The data lead wrote it out from memory on
2026-09-13, the same way `racials.json` was written, and it carries the same
flag. Treat it accordingly:

- A **`new`** verdict in `data/spells/*.json` means "this name is not in the
  list above". If the list is missing a real Classic spell, that produces a
  false `new`. Every `new` is a lead to check, never a fact to publish
  unqualified. The per-spell `classic.note` says so in the data itself.
- There is **no `same` and no `changed`**. The file holds no tooltip text, so a
  spell whose numbers moved cannot be told from one that did not; a matched name
  is recorded as `unknown`, which is the honest answer. `Blessing of Might`
  rank 1 giving 14 attack power for **one hour** is exactly such a case: the
  name is Classic, the duration is not, and only a sourced Classic tooltip can
  make that a `changed`.
- **Talent-taught abilities are deliberately absent** (Aimed Shot, Mind Flay,
  Presence of Mind, Blessing of Kings, Seal of Command, ...). They are in the
  *sourced* `talents.json` instead. A Forever spellbook that lists one of them is
  the interesting case, but not proof: the demo characters have talent points
  spent, so the record says "a Classic Era talent of the same name exists" and
  explicitly refuses to claim the ability became baseline.
- **Racials are absent.** Stage 11 recognises a racial by the list row's own "Racial" /
  "Racial Passive" subtitle and by name against `data/races/*.json`, and points the
  record at `data/races/<race>.json`, where the vs-Classic verdict already lives.
- **Hunter pet abilities** live in the `_pet` bucket, applied only to the hunter;
  the spellbook has a Pet page and its rows are pet abilities, not class spells.
- **Levels are ignored.** The demo characters are level 38, so their lists stop
  far short of these; a name here that the stream never showed is not missing
  data, it is a spell the character had not learned yet.

## Replacing it

The moment a sourced Classic Era spell list per class exists — a DB2 dump, a
Wowhead query by class and level, or the spell ids an addon's spellbook export
carries — drop it in, set `verified: true`, and re-run
`uv run stages/11_spellbook.py build`. Nothing else has to change: every
`classic` block in `data/spells/*.json` is regenerated from this file on each
build. Adding tooltip text to the prior at the same time is what turns the
`unknown` verdicts into real `same` / `changed` ones, and it is the single
biggest improvement available to the spell data.

Recorded in `SOURCES.md` alongside the other prior files.

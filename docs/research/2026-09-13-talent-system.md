# Research: WoW Forever talent system (2026-09-13, ~1 day after reveal)

Role: research analyst (sub-agent). Sources are linked inline. Public
information is thin: the talent UI was shown once (a Paladin window in the
"What's Next" panel); the Deep Dive panel with talent details had not yet
happened at the time of writing. No real Forever talent data exists anywhere
yet. Beta (and thus datamining) starts Thu 2026-09-17.

## 1. Talent system structure

Confirmed
- Level cap stays 60 permanently
  ([Blizzard recap](https://www.bluetracker.gg/wow/topic/us-en/24303862-world-of-warcraft-forever-whats-next-panel-recap/),
  [Warcraft Tavern](https://www.warcrafttavern.com/wow-classic/news/warcraft-forever-classic-announced-at-blizzcon-2026/)).
- Classic-style trees are retained. The panel showed a Paladin window with
  Holy / Protection / Retribution plus **"Primary" and "Secondary" tabs** at the
  top; the tabs were not explained
  ([Output Lag](https://outputlag.com/news/world-of-warcraft-forever-reworks-talents-so-paladins-can-tank-and-group-heal/)).
- Panel screenshot
  (`outputlag.com/wp-content/uploads/2026/09/world-of-warcraft-forever-blizzcon-2026-21.jpg`)
  shows Protection and Retribution **side by side**, tiered grid of 4 columns x
  7 rows, arrow prerequisites, per-tree point counters next to each tree icon,
  "Unspent Talents [1]" top right, green-bordered available talents in row 1
  with "0" rank badges. Both trees look denser than vanilla (Retribution rows
  approx 2/3/4/3/3/2/1 vs vanilla 2/3/4/2/2/1/1). Image is blurry; indicative
  only.
- Design intent: "talents that you notice", "real meaningful trade-offs", no
  more +1% rows; Paladins get a tanking seal and light group healing
  ([Out of Games](https://outof.games/news/9946-world-of-warcraft-forever-whats-next-at-blizzcon-2026-ended/)).

Unconfirmed: total points (51?), 5-points-per-row unlock, capstone rule, what
"Secondary" means. "Hero talents" are not mentioned anywhere.

## 2. Classes, specs, races

Confirmed: the 9 vanilla classes, no new class. New race: Skyborne (neutral
elves). New combos: Undead Paladin, Dwarf Shaman, Tauren Shaman/Druid, etc.
([Warcraft Tavern](https://www.warcrafttavern.com/forever/news/undead-paladins-other-race-class-combos-in-world-of-warcraft-forever/)).
Only the three-tree Paladin split is confirmed on-screen; Blizzard says "class
changes for every class". A leak thread claimed new Shaman/Warlock specs,
unverified ([MMO-Champion](https://www.mmo-champion.com/threads/2669761-World-of-Warcraft-Forever)).

## 3. Official talent data / datamining

- No real Forever data exists yet. Wowhead launched
  `https://www.wowhead.com/forever/talent-calc` (per class:
  `/forever/talent-calc/paladin`). Its data endpoint
  `https://nether.wowhead.com/forever/data/talents-classic?dv=17&db=1789102903`
  diffed against `nether.wowhead.com/classic/data/talents-classic` is
  **identical to Classic Era**: 27 trees, 432 talents, same spell IDs,
  positions and prerequisites. Placeholder.
- Its calculator JS (`wow.zamimg.com/js/WH/Wow/TalentCalcClassic.js`) uses
  `maxTalentPoints = maxLevel - 9` (51) and `pointsRequiredPerRow: 5`.
- Wowhead JSON shape (useful prior for our schema):
  `{talents: {treeId: {talentId: {id,row,col,icon,ranks:[spellIds],requires:[{id,qty}]}}}, trees: {id, description, role}, abilities: {classId: [{id,level}]}}`.
  Tooltips: `nether.wowhead.com/forever/tooltip/spell/<id>?dataEnv=Forever`.
- Beta client: Battle.net from 2026-09-17 for pre-purchasers, level cap 30 in
  beta, runs to 2026-10-22
  ([Vice](https://www.vice.com/en/article/world-of-warcraft-forever-beta-access-date/)).
  Expect wago.tools / Wowhead DB2 dumps (Talent.db2, TalentTab.db2, Spell*) from
  2026-09-17. Classic build 1.60.1.69704 flagged as a likely Forever build
  ([PCGamesN](https://www.pcgamesn.com/world-of-warcraft/forever-blizzcon-2026-wow-classic-plus)).

## 4. Existing Forever talent calculators

- Wowhead `https://www.wowhead.com/forever/talent-calc`: live, all 9 classes,
  Classic placeholder data.
- wowtbc.gg: news section with a "Talents" nav entry, no calculator yet.
- GitHub: nothing Forever-specific. Closest Classic projects:
  [TalentedClassic](https://github.com/anon1231823/TalentedClassic) (addon),
  [wowtbc.gg Classic calc](https://wowtbc.gg/classic/talent-calculator/),
  [talentcalc.com](https://www.talentcalc.com/) (Project Epoch).

## 5. Xaryu video and other footage

- `https://www.youtube.com/watch?v=DxtVEhjyROU`: "BLIZZCON DAY 1 | OPENING
  CEREMONY | CLASSIC+ ????", channel Xaryu, live stream started ~15:22 UTC
  2026-09-12, still live at time of writing, no chapters. The project owner
  has watched it: the first ~3 hours are not gameplay; afterwards Xaryu hovers
  every talent tooltip in direct game capture at rank 0.
- Other footage: only the Output Lag panel screenshot. Blizzard press images:
  [worldofwarcraft.blizzard.com/news/24301145](https://worldofwarcraft.blizzard.com/news/24301145).

## 6. Tooltip appearance

No public tooltip screenshot. Assume Classic layout (name, Rank x/y,
description, "Requires N points in Tree" / "Requires X") until confirmed from
our own frames.

## Recommendation

Build the data model on Wowhead's Classic JSON shape (tree/row/col/ranks/
requires) plus a Primary/Secondary page dimension; keep points-per-row and max
points configurable; plan to ingest real data from beta DB2 dumps after
2026-09-17.

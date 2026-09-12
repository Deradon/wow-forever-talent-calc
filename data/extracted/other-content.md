# Non-talent content in DxtVEhjyROU, 03:00:00 to 06:20:00 (survey, 2026-09-13)

Survey of everything in the source window that is not the talent window.
Method: the 60 s probe frames and contact sheets from stage 0
(`pipeline/work/probe/sheets/`), plus 74 native 1920x1080 frames fetched
with the fragment client and kept under `pipeline/work/probe/extra/<sec>.png`
(git-ignored; `<sec>` is the stream second). Timestamps are stream time
(HH:MM:SS = seconds / 3600). Everything here is unreviewed and read by eye
from single frames; counts are estimates. Companion brief:
`docs/briefs/beyond-talents.md`.

## Summary table

| # | Content | Where (stream time) | Footage | Rough count | Differs from Classic Era | Priority |
|---|---|---|---|---|---|---|
| 1 | Character creation: racial trait panels, race lore, faction text | 03:12:00-03:16:00, 03:45:00-03:46:30, 04:04:00-04:05:30, 05:30:00, 05:57:00-05:59:10, 06:06:00-06:10:30 | ~9 min in 6 windows | 10 races (9 with a visible trait panel), ~45-55 traits, 10 lore paragraphs | High: ~60 % of traits new or reworked; Skyborne 100 % new | 1 |
| 2 | Race/class matrix (class bar under the character creation screen) | same frames as 1 | free | 10 races x 9 classes | 5 new combos seen on screen, plus Skyborne (5 classes) | 1 |
| 3 | Spellbook pages (spell lists with rank; hover tooltips with full text) | 03:59:40-04:01:30, 04:15:00, 04:18:00, 05:03:00, 05:35:00, 05:38:50-05:40:00, 05:42:00, 05:49:00, 05:56:00, 06:00:20, 06:01:40-06:02:10, 06:09:00, 06:14:00, 06:17:40-06:18:00, 06:20:00 | ~16 windows of 10-40 s each, ~6 min | ~14 distinct pages, ~110 list entries (name + rank), 10-20 full hover tooltips | Medium: ~10-15 % of names new; numbers/durations differ in many hover texts | 2 |
| 4 | Legacy system: "Legacy Tree" (Legacy Points, seasonal cap) and "Legacy Challenges" (achievement-like list) | 03:34:00-03:35:40, 05:15:00, 06:20:00 | ~2 min | 2 windows, 3 tree categories, ~8 challenge entries visible, 1 readable node | 100 % new | 2 |
| 5 | Skyborne starting experience: zone, NPCs, quests, cinematic subtitles | 03:19:00-03:47:00 | ~28 min (with settings menus interleaved) | 2 zone names, 1 full quest text, ~4 quest titles, ~5 NPC/mob names, cinematic lines | 100 % new | 3 |
| 6 | Character sheet (paper doll, stats, item tooltip) | 05:40:00-05:40:30, 05:44:00 | ~1 min | 2 windows, ~20 stat rows, 1 item tooltip | Medium: new layout and stat categories | 3 |
| 7 | Onboarding: "Choose Your Experience Preset" (Classic / Enhanced), "Choose Your Gameplay Style" (PvP / PvE / Roleplay / Hardcore) | 03:08:00-03:11:30 | ~3.5 min | 6 text cards, fully legible | 100 % new UI | 3 |
| 8 | BlizzCon panel slides shown on stream ("And more...", 2026/2027 roadmap, Transmog, HD/SD models) | 03:49:00-03:58:10 | ~9 min | 4 slides | Announcement text, not game data | 4 |
| 9 | UI differences seen in passing (Edit Mode, combined Map & Quest Log, objective tracker, spellbook and talent search, loading-screen tips, demo chooser) | throughout | - | ~10 observations | UI only | 4 |
| 10 | "Dungeon Experience" demo: 5-man group in a desert troll instance (Zul'Farrak look), loot tooltips | 04:19:00-04:52:30 | ~33 min | a few item tooltips | Low; not verified as new | 5 |

## 1. Character creation: racial traits (frames `extra/<sec>.png`)

The right-hand column shows three scrollable boxes: faction text, race
("Racial Traits" with icon, name, description; lore paragraph below), class
description. The race box scrolls, so a single frame shows 3-4 of 4-6
traits; Xaryu scrolls in several windows, which gives the rest. Class
descriptions are Classic flavour text (low value).

| Race | Frames (sec) | Traits read from frames | vs Classic |
|---|---|---|---|
| Human | 11600 (03:13:20), 13500 (03:45:00), 21960 (06:06:00), spellbook 21620 | Will to Survive: Remove Stuns; Perception: Detect Stealthed enemies for 20 sec; Sword Specialization (Passive): Swords increase spell and ability critical chance by 2%; The Human Spirit (Passive): 5% increased Spirit; (Mace Specialization, Diplomacy not seen) | Will to Survive new; weapon specs give crit instead of weapon skill; Perception reworded |
| Dwarf | 11520 (03:12:00), 11660 (03:14:20), 22200 (06:10:00) | Stoneform: Immunity to Bleeds, Poisons, and Diseases and reduce Physical damage taken for 8 sec; Find Treasure: Track nearby treasure chests; Mace Specialization (Passive) (rest scrolled off) | Stoneform reworded (Classic: +10% armor); rest not seen |
| Night Elf | 11620 (03:13:40), 21980 (06:06:20), spellbook 22440 | Elune's Light: Increases critical chance by 10% for 15 sec; Shadowmeld: Gain Stealth while immobile; Quickness (Passive): 1% increased Dodge chance and 2% increased run speed; Wisp Spirit (Passive): 75% increased run speed while dead | Elune's Light new (active racial); Quickness reworked (Classic 1% dodge only) |
| Gnome | 11640 (03:14:00), 22000 (06:06:40), 22100 (06:08:20) | Escape Artist: Brief Immunity to Roots and Snares; Eureka!: Reduced cost and 10% increased damage or healing on next 3 spells or abilities; Expansive Mind (Passive): Maximum Mana, Rage, or Energy increased by 5%; Engineering Specialization (Passive): More reliable engineering devices | Eureka! new; Expansive Mind covers all resources; Escape Artist reworked; Engineering spec reworded |
| High Order Skyborne (Alliance) | 11680 (03:14:40), 22020 (06:07:00) | Walk on Air: Glide downward through the air for 10 sec; Read Ley Line: Activate a ley line to gain 100% increased Health and Mana regeneration; Wind Blessed (Passive): 1% increased melee, ranged, and spellcasting Haste; Elemental Insight (Passive): Damage to Elementals increased by 5%. Lore: "The High Order is made up of the descendants of the ancient Highborne..." | New race |
| Windshaper Skyborne (Horde) | 14640 (04:04:00), 14660 (04:04:20) | Walk on Air (same); Skysight: Receive an Elemental Blessing increasing run speed by 10%; Wind Blessed (Passive) (same); rest scrolled off | New race; the two Skyborne variants share Walk on Air and Wind Blessed and differ in the second active |
| Orc | 11700 (03:15:00), 19800 (05:30:00), 22040 (06:07:20), 22060 (06:07:40), spellbook 20330 | Blood Fury: Increases Attack Power and Spell Power by 10% for 15 sec; Shatter Curse: Immunity to Curses and Banes and reduce Magical damage taken for 8 sec; Axe Specialization (Passive): Axes increase spell and ability critical chance by 1%; Hardiness (Passive): Stun durations decreased by 20% | Shatter Curse new; Command gone; Blood Fury percentage-based; Hardiness 25% -> 20% |
| Tauren | 11720 (03:15:20), 14680 (04:04:40), 22080 (06:08:00) | War Stomp: Stuns nearby enemies for 2 sec; Cultivation: Grow bonus herbs that don't require herbalism to gather; Plainsrunning (Passive): Gain increased movement speed the longer you stay moving; Endurance (Passive): Total Health increased by 5% and Hit Chance increased by 1% | Plainsrunning new (the cut alpha racial returns); Endurance adds hit; Cultivation reworked; Nature Resistance not seen |
| Troll | 11740 (03:15:40) | (Berserking scrolled off); Beast Slaying (Passive): Damage to Beasts increased by 5%; Regeneration (Passive): 10% of Health regeneration continues during combat. Lore paragraph visible | Regeneration and Beast Slaying as Classic; Berserking, Bow/Throwing spec not seen |
| Undead | no race panel; spellbook General page 15300 (04:15:00) | Will of the Forsaken (Racial), Touch of the Grave (Racial Passive), Cannibalize (Racial), Underwater Breathing (Racial Passive) | Touch of the Grave new (from later expansions); no trait text seen |

Faction texts (Alliance, Horde) and per-race lore paragraphs are shown in the
same panel; all readable in the frames above.

## 2. Race/class matrix (class bar, same frames)

Lit classes in the bar under the character preview (greyed = unavailable):

| Race | Frame | Classes |
|---|---|---|
| Human | 11600, 21960 | Warrior, Hunter, Mage, Rogue, Priest, Warlock, Paladin |
| Dwarf | 11520, 22200 | Warrior, Hunter, Rogue, Priest, Paladin, Shaman |
| Night Elf | 11620, 21980 | Warrior, Hunter, Rogue, Priest, Druid |
| Gnome | 11640, 22000 | Warrior, Mage, Rogue, Priest, Warlock |
| Skyborne (both) | 11680, 14640, 22020 | Warrior, Hunter, Mage, Rogue, Druid |
| Orc | 11700, 19800 | Warrior, Hunter, Mage, Rogue, Warlock, Shaman |
| Tauren | 11720, 22080 | Warrior, Hunter, Druid, Shaman |
| Troll | 11740 | Warrior, Hunter, Mage, Rogue, Priest, Warlock, Shaman |
| Undead | not seen | (reported: Undead Paladin; verify) |

New versus Classic on screen: Human Hunter, Gnome Priest, Orc Mage, Troll
Warlock, Dwarf Shaman, all five Skyborne classes. Priest and Warlock for
Undead, Tauren Priest and Paladin, Dwarf Mage were not confirmed.

## 3. Spellbook

New UI: title "Spellbook", tabs General + one per tree (Paladin: Holy,
Protection, Retribution; Shaman tab named "Elemental Combat"), three-column
list of icon + name + "Rank N", search box "Search abilities, keywords",
options dropdown "Hide Passives / Group Similar Spells / Show all spell
ranks", "Page 1/1". With "Show all spell ranks" on (paladin, 04:00), every
learned rank is listed separately (Blessing of Might Rank 1-4, Holy Strike
1-5, Seal of the Crusader 1-4), which exposes low-rank scaling. Hover
tooltip (dark box, ~225 px wide, anchored to the list entry): name, cost,
range, cast time, cooldown, "Tools:" line for totems, description, and the
blue line "You haven't added this to your action bars". Search results are
shown as "Name Matches" or "Exact Matches / Related Matches" pages.

| Stream time | Frame | Class (character) | Page | Hover | Notes |
|---|---|---|---|---|---|
| 03:59:40 | 14380 | Paladin (Horde, lvl 38) | Retribution | - | all ranks shown |
| 04:00:10 | 14410 | Paladin | Retribution | Seal of the Crusader (65 mana, 107 AP, 40% faster, judgement +58 Holy damage taken) | |
| 04:00:20 | 14420 | Paladin | Holy | - | Blessing of Wisdom, Consecration, Exorcism, Flash of Light, Holy Light, Lay on Hands, Purify, Redemption, Seal of Light, Seal of Righteousness, Seal of Wisdom, Sense Undead, Turn Undead |
| 04:00:50-04:01:30 | 14450-14490 | Paladin | search "seal of fury" | Seal of Fury rank 1 (60 mana; melee +9 Holy damage; shield absorb 50%; unleash 47-52 Holy damage and taunt 4 sec) | Seal of Fury is new; Righteous Fury also listed |
| 04:15:00 | 15300 | Mage (Undead) | General | - | racials listed here (see section 1) |
| 04:18:00 | 15480 | Mage | Arcane | - | Amplify Magic, Arcane Blast, Arcane Explosion, Arcane Intellect, Arcane Missiles, Blink, Conjure Food/Water/Mana Agate/Mana Jade, Counterspell, Dampen Magic, Evocation, Mage Armor, Mana Shield, Polymorph, Presence of Mind, Remove Lesser Curse, Slow Fall (Arcane Blast and Presence of Mind baseline: new) |
| 05:03:00 | 18180 | Warrior | Fury | - | Battle Shout, Berserker Rage, Berserker Stance, Challenging Shout, Cleave, Demoralizing Shout, Execute, Intimidating Shout, Pummel, Slam, Whirlwind |
| 05:35:00 | 20100 | Shaman (Orc) | Elemental Combat | Stoneclaw Totem (75 mana, 280 health, taunts within 8 yards) | Call of the Ancestors, Call of the Elements, Fire Nova (spell), Totemic Recall: new; Chain Lightning, Earth Shock, Earthbind, Flame/Frost Shock, Lightning Bolt, Magma Totem |
| 05:38:50-05:40:00 | 20330-20400 | Shaman | General; search "wind" | - | |
| 05:42:00 | 20520 | Shaman | General | - | |
| 05:49:00 | 20940 | Druid (Tauren) | Restoration | Tranquility (375 mana, 5 min cooldown, 92 every 2 sec for 10 sec) | Abolish Poison, Healing Touch, Mark of the Wild, Rebirth, Regrowth, Rejuvenation, Remove Curse, Tranquility |
| 05:56:00 | 21360 | Hunter (Night Elf) | Marksmanship | Viper Sting (135 mana, 8-35 yd, 15 sec cooldown, drains 616 mana over 8 sec) | Aimed Shot, Arcane Shot, Auto Shot, Concussive Shot, Distracting Shot, Flare, Hunter's Mark, Multi-Shot, Rapid Fire, Scorpid Sting, Serpent Sting, Viper Sting |
| 06:00:20 | 21620 | Paladin (Human; segment list says Dwarf, the General page shows Human racials) | General | - | |
| 06:01:40-06:02:10 | 21700-21730 | Paladin | search "seal of fury", search "blessing" | Seal of Fury rank 4 (120 mana, +19 Holy, 81-90 unleash); Blessing of Might rank 1 (20 mana, +14 attack power for 1 hour) | Blessing of Kings, Freedom, Salvation baseline; 1-hour blessings |
| 06:09:00 | 22140 | Mage (Gnome, Alliance) | Fire | Fire Ward rank 2 (135 mana, absorbs 285, 30 sec cooldown) | only Fire Ward, Fireball, Flamestrike, Scorch listed |
| 06:14:00 | 22440 | Rogue (Night Elf) | General | - | Pick Lock, Shadowmeld, Elune's Light, Quickness, Wisp Spirit; Map & Quest Log open beside it |
| 06:17:40-06:18:00 | 22660-22680 | Warrior | search "thunder clap" | - | Thunder Clap rank 4 |
| 06:20:00 | 22800 | Warrior | search "whirl" | - | Legacy Tree open beside it |

Pages not seen: Paladin Protection, Mage Frost, Warrior Arms/Protection,
Rogue (all), Warlock (all), Priest (all), Shaman Enhancement/Restoration,
Druid Balance/Feral, Hunter Beast Mastery/Survival. The 10 s sampling may
hide short page flips; a 1 fps pass over the windows above will tell.

## 4. Legacy system (new)

- Legacy Challenges window (03:34:00, frames 12840, 12860): header bar
  "Legacy Points 0 / 66"; category tree Adventure > Explorer > Eastern
  Kingdoms, Kalimdor; Classes; Tradeskills; Player vs. Player > Ranks,
  Reputations, Season Journey; Dungeons; Raids. Dungeons: "Novice /
  Experienced / Master Spelunker: Complete the following dungeons: ..."
  (list partly legible: Ragefire Chasm, Deadmines, Wailing Caverns,
  Shadowfang Keep, ...). Raids: "Conqueror of the Wilds: Defeat the following
  encounters in Hyjal Summit" (about 13 boss names, partly legible),
  "Conqueror of the Deeps: Defeat the following encounters in the Barrow
  Deeps", "Conqueror of the Lair: Defeat Onyxia". Each entry has a Track
  checkbox and a point value.
- Legacy Tree window (03:34:40 frame 12880, 03:35:00 frame 12900, 05:15:00
  frame 18900, 06:20:00 frame 22800): "Available points: N LP", tooltip "You
  can spend up to your current seasonal cap of 16 Legacy Points in total.",
  three categories with a round icon and points badge (Professions,
  Adventure, Resourcefulness), a small node grid per category, search box,
  "Apply Changes". Readable node: "Bountiful Harvest, Rank 0/5, Passive: You
  discover 20% more Scarce materials from Mining, Herbalism, and Skinning."
  Every other node: "Unknown, Rank 0/1, Passive, To be added in future patch
  content."

## 5. Skyborne starting experience (03:19:00-03:47:00)

Night-elf-style character in the new zone "Thendal Village" / "Thendal
Grove" (minimap labels, frames 12180, 12240, 12900), misty elven island with
airships. Cinematic with subtitles at 03:20:00 ("For thousands of years, ...",
frame 12000). Quest "Coming of Age" from Rorian the Dayseeker (frame 12240):
full text legible ("...the potential you bring to the shen'dorei..."),
reward "Ancient Heirloom" (ring, flavour text). Objective tracker shows
"Infestation Investigation" (5/8 Pesky Cirrusfly slain) and "Harmony in
Balance" (frames 12840-12940). Chat line "Edit Mode layout 'Classic'
applied" (retail-style Edit Mode). Map at 03:23 shows the combined "Map &
Quest Log" window ("Quests: 0/40").

## 6. Character sheet (05:40:00 frame 20400, 05:44:00 frame 20640)

Modern layout: paper doll left, right column with tabs, "Level 38 Shaman",
collapsible groups "Primary Attributes" (Strength 60, Agility 39, Intellect
132, Stamina 83, Spirit 89, Armor 421, Attack Power 176, Spell Damage 83,
Spell Healing 109), "Weapons" (Main Hand 53-74, ...), "Modifiers" (Hit
Chance 1.0%, Critical Strike 11.1%, Movement Speed 126%), "Defense"
(Defense 190/190, Dodge 11%), "Resistances" (Arcane, Fire, Frost, Nature,
...). Item tooltip on the druid (Manual Crowd Pummeler) has a new line
"Equipment Sets: Feral Combat". Spell Damage and Spell Healing are separate
stats.

## 7. Onboarding screens (03:08:00-03:11:30, frames 11280, 11340)

"Choose Your Experience Preset": Classic (Standard Definition character
models, quest points of interest and objective blobs off, one-bag off,
transmog off) vs Enhanced (High Definition models, POI on, one-bag on,
transmog on). "Choose Your Gameplay Style: Select a ruleset to play with":
PvP, PvE, Roleplay, Hardcore, each with a one-sentence description. Fully
legible; transcribe by hand.

## 8. Panel slides (03:49:00-03:58:10)

Transmog before/after (13800), "Character Models HD/SD" (13860), "And
more..." list (13980: New Professions Content, New Reputations, New
Itemization & Rewards, Updated PvP System, First New LEGENDARY, Riding Skill
Updates, Gamepad Support, Previously Unfinished & Unused Vanilla WoW
Content), "2026 | 2027 Roadmap" (14040: Beta Sept 17 - Oct 22, Launch,
Raids unlock, major updates in spring and summer; small text not legible at
this sampling; fetch 14040-14100 at native resolution if wanted). Public
information; useful only for a "what's new" page.

## 9. UI observations (for a "UI differences" note, no extraction needed)

Talent window (see the probe handover), spellbook search and options, Legacy
windows, combined Map & Quest Log, "All Objectives" tracker with quest POIs,
Edit Mode layouts, "Time Left: NN min" demo timer, Starting Experience /
Dungeon Experience chooser (03:17, 05:41, 05:50, 05:58, 06:04, 06:15),
photosensitivity warning on restart (06:03:50), loading-screen tips (04:57,
05:24: generic Classic tips), game menu (05:11).

## 10. Dungeon Experience (04:19:00-04:52:30)

Five-player group (party frames top left), desert troll instance with pools
and ziggurats, mob and item tooltips at 04:24 and 04:26. Not identified as
new content; skip unless a boss or item name turns out to be new.

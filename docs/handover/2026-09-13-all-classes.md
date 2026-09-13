# Handover: all nine classes through the pipeline, 2026-09-13

`data/extracted/<class>.json` now exists and validates (0 errors) for all
nine classes; the coverage table is in `data/extracted/SUMMARY.md`. Nothing
committed. `pipeline/work/video/` untouched beyond reading `download.log`.
llama-server (Qwen3-VL-4B, port 8089) reused; one class at a time; codex
second opinion on every crop. Follow-up to
`docs/handover/2026-09-13-paladin-e2e.md`, which still documents the
prompt, the reader contract and the error model.

## Order and timings (wall, this machine, including the codex pass)

| class | segments | full run | notes |
|---|---|---|---|
| paladin | 8 | re-run 05-08 from cache, ~1 min | after the ranks/reader fixes below |
| warrior | 12, 13, 28 | 707 s | plus a cached 05-08 re-run after the `missing_cells` fix |
| rogue | 14, 15 | 685 s | plus segment 14 at 60 fps + cached re-run (+1 cell) |
| warlock | 16, 17 | 174 s (aborted by the skip guard) + 715 s | plus segment 16 at 60 fps + cached re-run (+1 cell) |
| priest | 18 | 770 s | complete, 53/53 |
| shaman | 19, 20, 21 | 717 s | |
| druid | 22 | 623 s + cached re-run after the header-less-tooltip fix | plus segment 22 at 60 fps (315 s) + cached re-run (+5 cells, 46 -> 51) |
| hunter | 23, 24 | 671 s | plus cached re-run after the tree-name snap |
| mage | 6-11 | 608 s | plus segment 6 at 60 fps + cached re-run (+3 cells) |

Stage 3+4 dominate (fragment fetch once, then ~13 s per minute of footage at
15 fps, 4x that at 60 fps); stage 5 is 110-155 s per class (2 Qwen passes,
~2.5 s per crop); codex ~4-5 min per class, both cached in `work/read/`.
Cached re-runs of 05-08 take a few seconds plus codex for new crops only.
A full class is 10-13 minutes wall. Memory stayed modest (one VLM, one
fetcher); the video download ran throughout.

## Problems met and what was changed (all general, no class special-cased)

1. **Ranks: unit-aware durations** (`ranks.py`). Guardian's Favor read
   "1 min" against Classic "60/120 sec" and got `[1, 61]`. `_from_classic`
   now compares the unit word after each aligned duration; Classic values are
   converted into Forever's unit (`convert_duration`, 60 sec -> 1 min) before
   scaling, the note says so ("Classic 60/120 sec taken as 1/2 min") and the
   record stays in the review queue; a conversion that is not whole (45 sec
   vs "1 min") or a duration aligned with a bare Classic number goes
   `manual` with reason "units differ". Tests added.
2. **Ranks: no token-subset "exact" matches** (`ranks.py`). The fuzzy name
   tier used `token_ratio` (= max with `token_set_ratio`), so "Divine
   Precision" scored 1.0 against rogue "Precision". `name_similarity` is
   `token_sort_ratio`; the exact tier stays full-key equality; fuzzy and
   description matches report at most 0.99, so only exact names can be 1.0.
   Divine Precision now lands on a cross-class description match at 0.91,
   medium, review queue.
3. **Reader: dropped "Requires" prefix** (`reader.clean_reading`). Both Qwen
   passes filed `["Shields"]` under `requires` for Holy Shield. The field
   holds only "Requires ..." lines by contract, so a bare entry gets the
   prefix back; nothing else is invented. Export note now reads
   "unparsed requirement: Requires Shields". Model behaviour, not a parser
   bug, but the fix lives in the parser. 13 such equipment/stance/form
   requirements across classes (`Requires Bear Form, Dire Bear Form` x6,
   `Requires Cat Form, Bear Form, Dire Bear Form` x4, Shields, Battle
   Stance, Defensive Stance); the review UI should show the note.
4. **`data/review/<class>/` naming**: stage 5 no longer copies
   `r<row>c<col>.png` crops; it only places `_header.png` per tree (which
   `export.py` references). Stage 8 places `<id>.png` / `<id>.icon.png`. The
   Paladin duplicates were deleted (3.8 MB -> 2.0 MB); other classes never
   had them. README and stage docstrings updated.
5. **`run_class.sh` skip guard** printed `0\n0` (`grep -c ... || echo 0`)
   and refused every class. Replaced by the Python guard below.
6. **Download health guard** (`fragments.DownloadHealth`, used by
   `FragmentCache.get`, stage 0 and `run_class.sh`). During the warlock run
   `download.log` gained `Skipping fragment 30806/30807`, each preceded by
   `ERROR: Did not get any data blocks` / `fragment not found`: yt-dlp asking
   for the not-yet-available head fragment of the live stream (sq 30806 =
   8.5 h in, while our fetches were at sq ~19000, one per 0.3 s). The old
   rule ("any skip aborts") was written for the 403 storm of the first
   download. The guard now classifies skips: a skip after an HTTP error
   aborts unconditionally; a live-edge skip that predates the process only
   warns; a live-edge skip that appears *while we fetch* aborts. Two more
   live-edge skips appeared between runs (4 total, none during a fetch).
   **Decision to confirm**: continuing after live-edge skips was my call;
   if you disagree, `DownloadHealth.check` is the one place to tighten.
   Tests added (`test_fragments.py`).
7. **Stage 5 `missing_cells` used the first segment's page.** Warrior
   segment 12 (settings dialog over the tab bar) was read as "Secondary", so
   all 54 cells were reported missing although 52 were read. The page is now
   the one most hovers resolved on.
8. **Tree-strip typos** (`reader.same_tree_name`). Hunter's tree 2 read
   "Marksmananship" in both segments and became the tree id. A reading
   within `token_sort_ratio >= 90` of the segments.md label snaps to the
   label; real renames ("Shadow Magic" 63, "Elemental Combat" 72) are kept
   from the footage as before.
9. **Header-less tooltip** (druid Feral Combat r3c3). The game showed the
   dual-form Feral Charge tooltip without a name or "Rank N/M" line (verified
   on the decoded frame); Qwen read the name as "5 Rage", `rank_max` null,
   and the exported `readings[].maxRank: null` failed the schema (file not
   written). Now: `assemble_record` caps such a record at confidence 0.3
   with note "no Rank line in the tooltip; ..."; export omits null reading
   fields. The record is exported as `druid/feral-combat/5-rage` (maxRank 1)
   and needs a manual rename to Feral Charge in review.
10. **Points already spent** (mage segments 10-11, `reader.rank0_order` +
    stage 5). The sharpest crop per cell used to win regardless of rank.
    Stage 5 now reads crops in order (best, then other segments' crops by
    not-cut-off/sharpness) until one shows `rank_current == 0`; a cell where
    every crop shows spent points keeps the text with a note and confidence
    <= 0.7. Fired once: Frost r4c4 Shatter exists only as a 3/3 crop
    (segment 10) and is flagged; export also warns "hover shows rank 3/3".
11. **Flash hovers**: for cells listed as "< 3 frames" the affected segment
    was re-run at 60 fps (`--every 1 --min-frames 1`): mage 6 (+3), rogue 14
    (+1), warlock 16 (+1), druid 22 (+5). The darkness gate and
    the duplicate-name check kept these safe (0 duplicates, 0 cut off).

## Error signals across classes (see SUMMARY.md for per-tree numbers)

- Validator: 0 errors everywhere. Warnings are the expected kinds:
  `NEEDS-REVIEW` (codex disagreement, 56 before the mage/druid re-runs),
  `MAXRANK-DIFFERS-FROM-CLASSIC` (30; many Forever talents have 2-3 ranks
  where Classic had 5), `R18-TREE-TOO-SMALL` (13 trees cannot absorb 51
  points with the read maxRanks; the `rules` block is still the assumed
  Classic one), `R19-EMPTY-ROWS` (rows with no read talent: rogue Combat
  r7, druid Balance r1 / Restoration r6-7, warlock Affliction r6 - all
  never-hovered cells), `NONLINEAR-RANKS` (Inspiration, Ancestral Healing,
  Elemental Weapons copied from Classic 8/16/25 patterns),
  `R17-TERMINATOR` (rogue Venom ends with a per-combo-point list).
- Codex vs Qwen on 385 records (before the last re-runs): names differ on
  4 (Bloodthrill/Bloodthirst, Blood Crazed/Blood Craze, Rage of the
  Farseer/Farseeer, 5 Rage/Feral Charge), maxRank on 1 (the header-less
  record), descriptions on 59: 48 one-character (dropped `%`, "In..."
  capitalised, comma/period), 6 up to four characters, 5 larger (Binding
  Heal " Low threat." dropped by one reader, Stormstrike, Improved Stings,
  Rapid Killing "critter"/"it die", Feral Charge second paragraph). All are
  at 0.7 in the review queue with both readings in `source.readings`.
  Warlock has the most (14 of 51), its tooltips are the longest.
- Qwen pass agreement stayed at 1.0 on nearly everything; as with Paladin,
  the codex pass is the effective error detector.

## Coverage summary

434 of 470 consensus cells read, 36 never hovered, 73 records at
confidence < 0.8, 128 with manual/extrapolated ranks (per tree in
SUMMARY.md). Complete: priest (53/53), hunter (50/50), warrior
Arms/Protection, rogue Subtlety, shaman Enhancement/Restoration, warlock
Affliction/Destruction, mage Frost, druid Balance/Feral Combat. The holes
are footage, not pipeline: mage Fire (10 of 17 never hovered), rogue Combat
(8 of 17), paladin Retribution/Holy (7).

## What the review step needs

1. Confidence 0.7 records first (codex disagreement): take the codex
   reading where the crop confirms it (the Paladin sample suggests codex is
   right on the one-character cases). The four name disagreements and
   `druid/feral-combat/5-rage` (rename to Feral Charge, maxRank 1, requires
   Bear/Dire Bear Form + Cat Form part) need a look at the crop.
2. `mage/frost/shatter`: text read at rank 3/3; verify against Classic
   wording whether the numbers are rank-1 values.
3. `ranksSource manual` / `extrapolated` (about 12-22 per class), then the
   `MAXRANK-DIFFERS-FROM-CLASSIC` ones.
4. The 13 unparsed equipment/stance/form requirements are in `source.note`;
   the schema's `requires` only models talent prerequisites.
5. Tree names: priest "Shadow Magic", shaman "Elemental Combat" come from
   the footage; mage segment 11 read tree 3 as "Shadow" (settings dialog),
   outvoted 5:1.
6. Missing cells cannot be recovered from this VOD (never hovered); they
   need another source or the datamined pass (Phase 3).

## Open points

- The `rules` block (51 points, 5 per row) is still assumed; 13 of 27 trees
  fail rule 18 with the read maxRanks.
- Two Qwen passes are not independent readers (see the Paladin handover);
  codex remains the second reader. If codex goes away, budget a third
  scale pass for descriptions ending in a bare number.
- The live-edge skip decision (item 6 above).
- `data/review/` is 19 MB for nine classes (crops + icons).

## Recovery (2026-09-13, cursor-track pass)

The cursor-track forensics (`pipeline/work/cursor/report.md`) found that 34
of the 36 "never hovered" cells did have a tooltip on screen and wrote one
hovers-shaped record per cell and segment to `pipeline/work/cursor/recovered.json`
with tight crops under `work/cursor/recovered/<class>/`. Those were folded
into the class data as follows; nothing committed, no hand edits to `data/`.

1. **Read** with stage 5's reader (`wowtalents.reader`: prompt `tooltip-v3`,
   3x/2x passes, temperature 0, JSON schema, `work/read/cache/`) through a
   scratch driver, because `stages/05_read.py run` only takes
   `work/hovers/*.json` (a `--hovers` option would make this repeatable).
   Page and tree names per segment came from the class's existing
   `candidates.json` (`segments[]`, `trees`), `tree_source` confidence from
   the same tree-name votes. The primary (rank-0) segment's crop was read
   first, `rank0_order` as in stage 5; all 34 read at rank 0. Every name
   matches the by-eye list in the cursor report. Qwen pass agreement 1.0 on
   33 of 34 (Pyroblast differed in the description).
2. **Codex second opinion** (`scripts/second_opinion.py --candidates`) on all
   34: 4 disagreements, all one-character and routed to 0.7: mage Pyroblast
   "Hurts"/"Hurls" (codex right), Improved Scorch "fire"/"Fire", paladin
   Infusion of Light "15 sec."/"15 sec", shaman Concussion "Bolt."/"Bolt,".
3. **Merge** into `data/extracted/<class>.candidates.json`: new cells appended
   in (page, tree, row, col) order; existing records untouched except where
   stage 5's duplicate-name rule fires (below). `missing_cells` and `stats`
   updated; a `recovery` block lists the added ids. Candidate records carry
   `source.crop_path` under `work/cursor/recovered/` and a `source.recovered`
   block (dwell, cursor cell); export drops the latter as usual.
4. **06 rankfill without `--force`** (fills only the 34 new records, keeps
   every existing `ranks_anticipated`), then `08_export.py all <class>
   --update-encoding` (extract + promote, crops and icons placed under
   `data/review/<class>/<tree>/<id>.png`), validator on `data/talents/` and
   `data/extracted/`: **0 errors** for all seven classes. `web`: 81 vitest
   tests pass (validate-data included), `npm run build` OK.

Read counts (records exported), before -> after:

| class | before | after | cells | still missing |
|---|---|---|---|---|
| mage | 42 | 53 | 54 | fire-r1c3 |
| paladin | 45 | 51 | 52 | holy-r2c1 |
| warrior | 52 | 54 | 54 | - |
| rogue | 43 | 53 | 53 | - |
| shaman | 47 | 50 | 50 | - |
| warlock | 51 | 52 | 52 | - |
| druid | 51 | 52 | 52 | - |

Total 434 -> 468 of 470. The two remaining cells were fly-overs (pointer on
the icon for 1-2 frames, no tooltip rendered) and need another source.
Needs-review 73 -> 79 (+4 codex, +2 below); ranks manual/extrapolated
128 -> 134 (Infusion of Light manual; Holy Conduit, Boundless Rage, Vigor,
Endurance, Demonic Embrace extrapolated). Of the other 28: 18 `classic-prior`
(11 copied, 7 re-based/extended, medium) and 4 `observed` (1-rank talents).
`R19-EMPTY-ROWS` no longer fires for rogue Combat r7, druid Restoration r7,
warlock Demonology.

**Collisions.** None by cell (no recovered cell had an existing record). One
by name: mage Fire **Master of Elements** was already recorded at r4c3
(`08-mage-14970` @ 04:10:03.7) and the cursor track recovers the same
tooltip at r4c4 with the pointer on r4c4 for 100 % of that run (the r4c3
record is the ghost-blob mis-attribution described in the cursor report,
item 1). Stage 5's duplicate-name rule was applied: both records at
confidence 0.3 with the note "name also read at r4c3@..., r4c4@...; cell
attribution needs review"; export ids `mage/fire/master-of-elements` (r4c3)
and `mage/fire/master-of-elements-r3c3` (r4c4). Review should keep the r4c4
record and treat r4c3 as unread: its true tooltip is the one baked into
segment 08's median ("Hot Streak" per the report) and has no clean crop, so
mage Fire effectively still lacks two cells (r1c3, r4c3).

**Odd readings.** "Arcane Impact" (Arcane r3c2, 0/3) reads cleanly in both
readers, but the Classic prior has no such talent: the validator's fuzzy
match pairs it with Classic "Impact" (`MAXRANK-DIFFERS-FROM-CLASSIC`, 5
ranks) while stage 6 copied its ranks from Classic Fire "Critical Mass" by
description match (`classic-prior` medium, review queue); the real Fire
"Impact" (r2c3, 0/3) is now also present. Check the crop before accepting
either pairing. New names with no same-class Classic counterpart: Boundless
Rage (warrior), Infusion of Light, Holy Conduit (paladin), Wild Growth
(druid). `data/review/` is now 20 MB.

# Missing-cells forensics, 2026-09-13

Question: the owner is confident every talent was hovered on stream, the
pipeline reported 36 consensus cells "never hovered". Where did the pipeline
lose them?

Answer: 34 of the 36 were on screen in the cached fragments and stage 4 lost
them; one further cell (mage Fire r4c3) carried the wrong talent. All 34 are
recovered with the fixes below (468 of 470 cells hovered, up from 434), no
cell was lost anywhere. The remaining two (paladin Holy r2c1, mage Fire
r1c3) are absent from every cached frame and can only sit in footage that no
segment covers.

Paths below are relative to `pipeline/` unless they start with `docs/`.

## Result per class

| class | cells | hovered before | after | recovered from the missing list | still missing |
|---|---|---|---|---|---|
| warrior | 54 | 52 | 54 | fury-r3c4 Boundless Rage, fury-r5c4 Improved Intercept | - |
| paladin | 52 | 45 | 51 | holy-r4c1 Infusion of Light, holy-r4c3 Divine Favor, retribution-r1c3 Benediction, retribution-r2c1 Improved Judgement, retribution-r2c2 Holy Conduit, retribution-r2c3 Conviction | holy-r2c1 |
| rogue | 53 | 43 | 53 | assassination-r5c1 Vigor, assassination-r5c3 Improved Kidney Shot, combat-r1c3 Lightning Reflexes, combat-r2c2 Deflection, combat-r2c3 Precision, combat-r3c1 Endurance, combat-r4c1 Improved Kick, combat-r4c3 Dual Wield Specialization, combat-r6c2 Weapon Expertise, combat-r7c2 Adrenaline Rush | - |
| shaman | 50 | 47 | 50 | elemental-combat-r1c3 Concussion, elemental-combat-r2c2 Reverberation, elemental-combat-r2c3 Call of Flame | - |
| mage | 54 | 42 | 53 | arcane-r1c2 Arcane Focus (crop shows rank 4/5, see notes), arcane-r3c2 Arcane Impact, fire-r2c3 Impact, fire-r3c1 Burning Soul, fire-r3c2 Improved Flamestrike, fire-r3c3 Pyroblast, fire-r4c1 Improved Scorch, fire-r4c2 Improved Fire Ward, fire-r4c4 Master of Elements, fire-r5c2 Critical Mass, fire-r6c3 Fire Power; corrected: fire-r4c3 is Hot Streak (was read as Master of Elements) | fire-r1c3 |
| warlock | 52 | 51 | 52 | demonology-r1c3 Demonic Embrace | - |
| druid | 52 | 51 | 52 | restoration-r7c2 Wild Growth | - |
| priest | 53 | 53 | 53 | - | - |
| hunter | 50 | 50 | 50 | - | - |
| total | 470 | 434 | 468 | 34 (+1 corrected) | 2 |

Names are the local VLM's reading of the recovered crop (3x pass); codex
agreed on the three spot checks (Deflection, Pyroblast, Hot Streak). Every
recovered crop is complete (`cut_off` false) and, except Arcane Focus, at
rank 0.

Per-class stage-5 dry runs on the installed hovers confirm the counts
(`uv run stages/05_read.py run <class> --dry-run`).

## Verdict per missing cell

Root-cause codes: **A** tooltip invisible to the pixel-area gate (over a
dark panel only border and text differ from the median, the component had
fewer than 9000 pixels and was filed as a "small blob"); **B** diff blob
merged with something next to the tooltip (ghost tooltip in the median, the
game world past the window's right edge, a brightened panel) and failed the
width or darkness gate; **C** ghost tooltip in the median (the streamer
rested on that talent for most of the sampled frames, so it became
background and its own cell could never diff); **D** hover outside every
segment (10 s probe boundaries, uncached fragments).

| cell | verdict | cause | recovered from | crop |
|---|---|---|---|---|
| warrior fury-r3c4 | recovered, Boundless Rage 0/3 | A | 13 @ 04:59:29 | work/forensics/recovered/warrior/fury-r3c4.png |
| warrior fury-r5c4 | recovered, Improved Intercept 0/2 | A | 28 @ 06:16:44 | .../warrior/fury-r5c4.png |
| paladin holy-r2c1 | truly absent from cached footage | D (see below) | - | - |
| paladin holy-r4c1 | recovered, Infusion of Light 0/2 | A | 25 @ 05:59:37 | .../paladin/holy-r4c1.png |
| paladin holy-r4c3 | recovered, Divine Favor 0/1 | A | 25 @ 05:59:36 | .../paladin/holy-r4c3.png |
| paladin retribution-r1c3 | recovered, Benediction 0/5 | A (+C: Twist of Light ghost in that median made every frame a reject) | 27 @ 06:02:22 | .../paladin/retribution-r1c3.png |
| paladin retribution-r2c1 | recovered, Improved Judgement 0/2 | A | 27 @ 06:02:25 | .../paladin/retribution-r2c1.png |
| paladin retribution-r2c2 | recovered, Holy Conduit 0/2 | A | 27 @ 06:02:24 | .../paladin/retribution-r2c2.png |
| paladin retribution-r2c3 | recovered, Conviction 0/5 | A | 27 @ 06:02:23 | .../paladin/retribution-r2c3.png |
| rogue assassination-r5c1 | recovered, Vigor 0/2 | A | 15 @ 05:05:15 | .../rogue/assassination-r5c1.png |
| rogue assassination-r5c3 | recovered, Improved Kidney Shot 0/2 | A | 15 @ 05:05:10 | .../rogue/assassination-r5c3.png |
| rogue combat-r1c3 | recovered, Lightning Reflexes 0/5 | A | 15 @ 05:05:46 | .../rogue/combat-r1c3.png |
| rogue combat-r2c2 | recovered, Deflection 0/3 | A | 15 @ 05:05:50 | .../rogue/combat-r2c2.png |
| rogue combat-r2c3 | recovered, Precision 0/3 | A | 15 @ 05:05:52 | .../rogue/combat-r2c3.png |
| rogue combat-r3c1 | recovered, Endurance 0/2 | A | 15 @ 05:06:22 | .../rogue/combat-r3c1.png |
| rogue combat-r4c1 | recovered, Improved Kick 0/2 | A | 15 @ 05:07:24 | .../rogue/combat-r4c1.png |
| rogue combat-r4c3 | recovered, Dual Wield Specialization 0/5 | A | 15 @ 05:06:43 | .../rogue/combat-r4c3.png |
| rogue combat-r6c2 | recovered, Weapon Expertise 0/2 | A | 15 @ 05:08:18 | .../rogue/combat-r6c2.png |
| rogue combat-r7c2 | recovered, Adrenaline Rush 0/1 | A | 15 @ 05:08:06 | .../rogue/combat-r7c2.png |
| shaman elemental-combat-r1c3 | recovered, Concussion 0/5 | A | 21 @ 05:35:38 | .../shaman/elemental-combat-r1c3.png |
| shaman elemental-combat-r2c2 | recovered, Reverberation 0/5 | A | 21 @ 05:35:46 | .../shaman/elemental-combat-r2c2.png |
| shaman elemental-combat-r2c3 | recovered, Call of Flame 0/3 | A | 21 @ 05:35:44 | .../shaman/elemental-combat-r2c3.png |
| mage arcane-r1c2 | recovered, Arcane Focus, but 4/5 (points already spent; text may be rank 5) | A | 09 @ 04:11:54 | .../mage/arcane-r1c2.png |
| mage arcane-r3c2 | recovered, Arcane Impact 0/3 | A | 06 @ 04:06:17 | .../mage/arcane-r3c2.png |
| mage fire-r1c3 | truly absent from cached footage | D (see below) | - | - |
| mage fire-r2c3 | recovered, Impact 0/3 | A | 08 @ 04:09:31 | .../mage/fire-r2c3.png |
| mage fire-r3c1 | recovered, Burning Soul 0/3 | B (glued to the Hot Streak ghost, 330 px) | 08 @ 04:09:34 | .../mage/fire-r3c1.png |
| mage fire-r3c2 | recovered, Improved Flamestrike 0/3 | A | 08 @ 04:09:32 | .../mage/fire-r3c2.png |
| mage fire-r3c3 | recovered, Pyroblast 0/1 | B + C (box truncated where it overlapped the ghost; needed the median repair) | 08 @ 04:09:30 | .../mage/fire-r3c3.png |
| mage fire-r4c1 | recovered, Improved Scorch 0/3 | B (330 px with the ghost) | 08 @ 04:09:36 | .../mage/fire-r4c1.png |
| mage fire-r4c2 | recovered, Improved Fire Ward 0/2 | B + C (270-279 px with the ghost) | 08 @ 04:09:37 | .../mage/fire-r4c2.png |
| mage fire-r4c3 | corrected: Hot Streak 0/1 (previous crop was Master of Elements) | C (Hot Streak was the ghost in segment 08's median) | 08 @ 04:10:02 | .../mage/fire-r4c3.png |
| mage fire-r4c4 | recovered, Master of Elements 0/3 | B + C (box started inside the ghost, attributed to r4c3) | 08 @ 04:10:03 | .../mage/fire-r4c4.png |
| mage fire-r5c2 | recovered, Critical Mass 0/3 | B (270-279 px with the ghost) | 08 @ 04:10:04 | .../mage/fire-r5c2.png |
| mage fire-r6c3 | recovered, Fire Power 0/5 | A | 08 @ 04:10:06 | .../mage/fire-r6c3.png |
| warlock demonology-r1c3 | recovered, Demonic Embrace 0/5 | A | 17 @ 05:19:54 | .../warlock/demonology-r1c3.png |
| druid restoration-r7c2 | recovered, Wild Growth 0/1 | B (moving game world past the window edge, 430 frames at 290-309 px) | 22 @ 05:48:30 | .../druid/restoration-r7c2.png |

Counts: A 24 cells, B 7 (4 of them also C), C 1 corrected cell, D 2.
`work/forensics/recovered/recovered.json` lists the same 35 records in the
stage-4 hover shape (per class, `files.tooltip` relative to `pipeline/`,
plus `read` with the VLM name/rank and `in_missing_list`).

## Hypotheses, in the order asked

1. **Tooltip anchoring** - rejected. In every inspected frame (grid overlay
   drawn on the decoded frame) the tooltip's bottom-left corner sits on the
   hovered cell's top-right corner; accepted hovers have corner distances of
   1-5 px in all rows and columns, including column 4 and row 7. Apparent
   anchor shifts were measurement artefacts: the diff blob had merged with
   something next to the tooltip (2). The missing cells do not cluster by
   row or column.
2. **Gates dropping real tooltips** - confirmed, the main cause, but the
   gate *values* were fine; the blob handed to them was wrong:
   - Pixel-area gate (`min_area = 9000` on the component's pixel count).
     Over a dark panel (rogue Combat, Fire rows 3-6, Elemental Combat,
     Retribution) the tooltip body is grey 1-3 against a panel of 5-19, so
     it never crosses the diff threshold; only the grey border, the text and
     the icons underneath differ. A complete 196 x 75 Deflection tooltip
     had about 5000 changed pixels and was silently filed as a "small blob"
     (cursor candidate). 24 of the 36 cells.
   - Width ceiling (270 px) and darkness gate on merged blobs. Whatever
     changed next to a tooltip merged with it through the close: the Hot
     Streak ghost in segment 08's median (every Fire row 3-5 tooltip came out
     270-330 px wide, 85 rejected frames), the moving game world past the
     window's right edge (Wild Growth, 430 frames), a panel region that
     brightens by ~25 grey while a tree is hovered (segment 06), the header
     region above a box (paladin 01, darkness 0.55). `trim_bbox` cannot cut
     these because the appendage rows are as densely filled as the tooltip.
   - Wrong cell from a merged box: Master of Elements' box started 60 px too
     far left inside the ghost and landed on r4c3 (corner distance 11 px,
     cursor on r4c4; the cursor veto only applied to the column fallback).
   - Neither the darkness gate nor the cursor veto rejected a clean real
     tooltip in any inspected frame; `min-frames` was not involved (none of
     the 36 cells appears in any `dropped_runs`).
3. **Segmentation** - partly confirmed, not measurable from the cache.
   - The 04:12:30-04:53:00 mage gap holds no talent window (probe frames at
     one per minute checked; sheet in the forensics dir).
   - 12 of 28 segments start with a hover already on screen at
     `t_start + 0.0 s` (02, 06, 09, 13, 15, 18, 19, 21, 23, 24, 25, 26) and
     two end with one (06 at 04:07:10, 24 at 05:55:20): the probe boundaries
     are 10 s coarse, so up to 10 s of hovering before/after each of these is
     outside every segment. Fragments for these margins, and for
     04:07:10-04:07:30 / 04:08:20-04:09:30 where the Fire pass must have
     continued (Fire r1c1-r1c2 at 04:07:0x, Fire r2c3 onwards from 04:09:30),
     are not cached and could not be fetched any more (the live fragment URL
     expired; the VOD URL that `yt-dlp -j` returns now does not serve
     `&sq=N`). The mkv in `work/video/` is the only remaining source.
   - Median contamination: in six segments the streamer rested on one
     talent for most of the sampled frames and that tooltip became part of
     the background: 04 (Templar's Bulwark), 08 (Hot Streak, 24 of 30
     frames), 14 (Assassination r1c3), 17 (Affliction r7c2), 25 (Light's
     Vigil, blend), 27 (Twist of Light). A ghost hides its own cell for the
     whole segment and widens every neighbouring tooltip (2).
4. **Duplicate attribution** - not a cause: no name was read at two cells in
   any class. The one mis-attribution (Master of Elements at Fire r4c3) had
   no duplicate because the true r4c3 talent was invisible.
5. **Fast sweeps** - not a cause: none of the 36 cells appears in the
   `dropped_runs` of any segment; the earlier 60 fps re-runs already
   harvested the flashes. (The recovered crops come from runs of 4-90
   frames.)

## Root causes, ranked

| # | cause | where | cells |
|---|---|---|---|
| 1 | pixel-area gate misses tooltips over dark panels (sparse diff mask) | `ui.find_tooltip` | 24 |
| 2 | blob merged with a ghost / the game world / a brightened panel, then width or darkness gate, or wrong anchor | `ui.find_tooltip` + stage 3 median | 7 (+1 corrected) |
| 3 | ghost tooltip in the median hides its own cell | stage 3 | 1 (Hot Streak) and 3 of the row-2 cells |
| 4 | hover outside every segment (10 s probe boundaries, uncached gaps) | stage 0 | 2 |

Rejected frames over all segments went from 9294 to 7364, unique cells from
434 to 468. Per segment: 08-mage 3 -> 13, 15-rogue 40 -> 50, 27-paladin
2 -> 20, 09-mage 23 -> 31, 25-paladin 8 -> 11, 21-shaman 29 -> 32; no
segment lost a cell that another segment of the class does not still have
(09 lost arcane-r4c3 to a stricter veto, 10 lost frost-r5c2; both are in
06 and 09).

## Fixes applied (general, no class special-cased)

`src/wowtalents/ui.py`
- `find_tooltip`: a component is a candidate by the area of its *bounding
  box* (`min_area` unchanged at 9000); the close kernel is 7 x 7 so a border
  outline stays connected; when the frame is passed (`gray`) each candidate
  is trimmed to the frame's dark core (`dark_trim`: rows by the truly black
  fraction at grey < 16, columns by the longest smoothed run at grey < 40
  because text is left-aligned) and then snapped to the tooltip's 1 px
  border line (`border_snap`: uniform grey row/column with mean >= 55, black
  inner neighbour, non-black outer neighbour). Only candidates whose crop
  passes the darkness gate compete for "largest", so a large sparse blob of
  game-world change cannot win the frame and then fail the gate (that
  regression showed up in a first forensic pass). Rejected blobs carry a
  reason (`narrow` / `wide` / `short` / `not_dark x.xx`).
- Ghost repair for stage 3: `ghost_candidates` (tooltip-shaped dark boxes
  where the median differs from a donor median of the same class, or where
  pixels are unstable across the sampled frames and dark in the median),
  `ghost_boxes` (a black box in >= 2 sampled frames; blackness at grey < 16
  tells a tooltip from a dark panel), `patch_from_donor` (window must match
  within 8 grey outside the box), `repair_ghosts` (median of tooltip-free
  frames or the donor region, whichever is blacker-free; must lower the
  blackness by 0.15).

`stages/03_calibrate.py`: `remove_ghosts` after the median, donors = the
other calibrated segments of the class nearest in time; `ghosts` recorded
in the calibration JSON. Donors must exist, so calibrate a class's cleanest
segment first or run stage 3 twice (segments 14 and 17 kept their ghost in
this run because their donors came later; both cells were read from other
segments anyway).

`stages/04_hovers.py`: passes the frame to `find_tooltip`, records
`rejected_frames[].reasons`, and refuses a corner match farther than 8 px
when the cursor blob sits on another cell (`CORNER_STRICT`).

Tests: `tests/test_ui.py` gained `dark_trim`, sparse-outline candidate,
wide-blob rescue, ghost repair from frames, from a donor, and the dark-panel
non-repair; 130 tests pass. README (stages 3/4) and the stage-4 docstring
updated.

## What was re-run and where it lives

- `work/forensics/calib` + `work/forensics/hovers`: new finder, medians
  without the final ghost repair (isolates fix 1+2: recovers 31 cells).
- `work/forensics/calib2` + `work/forensics/hovers2`: new finder plus ghost
  repair (recovers 34 cells and corrects Fire r4c3). Same `--every` /
  `--min-frames` per segment as the original run.
- `work/forensics/before/{calib,hovers}`: the previous stage-3/4 outputs of
  all 28 segments. The `calib2`/`hovers2` results were installed into
  `work/calib` and `work/hovers` (all 28 segments), so
  `run_class.sh <class> --skip-video` (stages 5-8) picks them up.
  `data/extracted` and `data/talents` were not touched.
- `work/forensics/recovered/<class>/<tree>-r<row>c<col>.png` (+ `-icon.png`)
  and `recovered.json`; `work/forensics/logs/` has the stage-3/4 logs.

## Review notes for the re-export

- mage `arcane-r1c2` (Arcane Focus) exists only as a 4/5 crop from the
  points-spent phase (04:11:54); stage 5 will flag it like Shatter.
- mage `fire-r4c3` changes from Master of Elements to Hot Streak; Master of
  Elements moves to `fire-r4c4`. The old record's id/slug should disappear
  from the export.
- The two truly absent cells: paladin Holy r2c1 and mage Fire r1c3. No
  rejected blob, dropped run or unresolved run is anchored at either cell
  in any segment, old or new. Both fit the boundary story: Holy row 2 was
  swept in segment 02 seconds before the spellbook covered the window and in
  segment 25 the streamer started at Holy r3c1 at `t_start`; Fire r1c1-r1c2
  were hovered at 04:07:0x and the pass resumed at Fire r2c3 at 04:09:30, so
  r1c3 lies in the uncached 04:07:10-04:09:30 stretch. Recovering them
  needs the mkv (decode 03:58:20-03:58:40, 04:07:10-04:07:30,
  04:08:20-04:09:30, 05:59:00-05:59:30 at 1 fps and look for a tooltip
  anchored at (588, 292) or (1003, 238)).

## Limitations left in place

- A tooltip half over a dark panel and half over the bright game world
  (druid Restoration r4c4 Swiftmend at 05:48:32) still yields a box that
  starts at the window edge: the weak diff on the left is not in the mask
  and the trims only shrink. The cell was found from other frames.
- The cursor cross-check treats every 80-3000 px diff blob on a cell as the
  cursor; a stale icon (state changed after the median) sits on one cell in
  every frame of some segments (warrior 13 and rogue 15 report
  `cursor_cell` [3,2,1] on most runs). With the 8 px corner veto such a blob
  can turn a loose match into "unresolved" rather than a guess.
- Segment 09 (points being spent) now has 23 unresolved runs: the rank>0
  tooltips with a "Next rank" block are tall, get clamped, and the cursor
  veto refuses the guess. Nothing there is missing from the class.

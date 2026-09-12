# Handover: stages 3 and 4 on the first Paladin segment (2026-09-13)

Stages `03_calibrate` and `04_hovers` of `docs/briefs/pipeline.md` are
implemented and were run on segment 1 (`01-paladin-13640`, 03:47:20-03:48:20,
Horde paladin, Primary page). Everything ran on fragment streams; the mkv
download was still at frag ~5500/23077 and was not touched. Nothing here was
committed.

## What was built

- `pipeline/src/wowtalents/ui.py`: layout priors (window, grid columns/rows,
  tab strips, overlay masks), `decode_frames` (ffmpeg rawvideo pipe, every
  N-th frame, streamed one frame at a time; stdin is fed from a thread
  because a serial write-then-read deadlocks on the 6 MB frames),
  `detect_grid` (prior cell positions refined by a 35-37 px square-outline
  search on Sobel gradients, min of the four edges, threshold 3.5, normalised
  to 36 px), `tab_state` (saturation of the tab strips), `diff_mask`,
  `find_tooltip` (closed diff blobs, width 120-270, height >= 50, trimmed to
  the mostly-filled rows/columns so the cursor does not stretch the box),
  `cell_for_tooltip` (cell whose top-right corner is nearest the tooltip's
  bottom-left, with a same-column fallback for vertically clamped boxes),
  `dhash`/`hamming`/`sharpness`, `RunTracker`/`group_runs` (online grouping,
  keeps only the sharpest crop of the current run in memory), contact sheet
  and overlay drawing.
- `pipeline/src/wowtalents/fragments.py`: `FragmentCache` (raw fragments in
  `work/frags/<sq>.bin`, one request at a time, 0.3 s sleep, refresh after 3
  failures, abort on skipped fragments in `download.log`).
- `pipeline/stages/03_calibrate.py run <segment>`: 30 frames spread over the
  segment (one per fragment, first frame), median over the work ROI
  (x 400-1780, y 0-720; ~2.8 MB per frame), grid, tab state, header and
  tree-name crops. Output `work/calib/<id>.json`, `-median.png`,
  `-overlay.png`, `-header.png`, `-tree{1,2,3}.png`.
- `pipeline/stages/04_hovers.py run <segment>`: every 4th frame (15 fps) of
  every fragment, diff against the median, tooltip blob, hash, grouping
  (Hamming <= 2 and same cell, >= 3 frames), sharpest frame per run, dedupe
  per (tree, row, col). Output `work/hovers/<id>/<tree>-r<row>c<col>.png`,
  `...-icon.png` (36 px from the median), `unresolved-<n>.png`,
  `work/hovers/<id>.json` (also lists short runs dropped and frames with a
  big non-tooltip blob) and `<id>-sheet.png`.
- `pipeline/tests/test_ui.py` (10 tests: segment ids, corner and column cell
  lookup, tie-break, cursor cell, dHash, run grouping, tracker payload
  handling, bbox trimming, blob shape filter). `uv run pytest`: 81 passed.
- `pipeline/README.md` documents the commands.

## Calibration result (segment 1)

- Tab state: Primary active (Primary strip saturation clearly above
  Secondary). Window geometry matches the probe handover to the pixel; no
  refinement moved a cell by more than 3 px.
- Cells found: Holy 18, Protection 16, Retribution 18 (52 total), every
  present icon boxed on the overlay and no box on an empty position. Row
  occupancy: Holy 3/4/3/3/3/1/1, Protection 2/3/4/3/2/1/1, Retribution
  2/3/4/3/3/2/1. Classic Paladin has 15/14/15, so WoW Forever trees are
  bigger; expect the same for other classes.
- Score separation on the median: present cells >= 4.19, absent <= 2.7
  (threshold 3.5). The median still carries a faint ghost of the Reckoning
  tooltip near the Protection header (it was open in many sampled frames);
  harmless for detection but a longer segment or `--every` spacing would
  remove it.

## Hover result (segment 1)

900 frames decoded, 544 with a tooltip, 38 runs, 15 unique cells, 0
unresolved, 13 s wall time from cached fragments.

| tree | hovered / cells | cells |
|---|---|---|
| Holy | 4 / 18 | r1c1 Improved Holy Strike, r1c2 Divine Strength, r2c2 Spiritual Focus, r7c2 Light's Vigil |
| Protection | 10 / 16 | r1c2 Toughness, r1c3 Redoubt, r2c1 Precision, r2c2 Guardian's Favor, r2c4 Anticipation, r3c3 Shield Specialization, r3c4 Sacred Duty, r5c3 Reckoning, r6c3 Iron Creed, r7c2 Holy Shield |
| Retribution | 1 / 18 | r1c2 Deflection |

(Names read by eye from the contact sheet, not by the VLM.) The streamer
simply did not hover the other 37 cells in this 60 s window; the talent
window closes at about 03:48:12 (13692), after which every frame is a
whole-ROI change and is correctly rejected. Segments 2-5 and 25-27 (second
paladin) should fill in the rest.

Crop quality: all 15 crops complete, borders on all sides, name / "Rank
0/N" / Passive or cost lines / gold description / "Click to learn" legible
at native resolution. Widths 181-228 px (the box is sized to the longest
line, 227-228 is the wrap width), heights 81-190. Largest file 78 KB. Every
cell was resolved by the corner rule with distance <= 5 px; the cursor
cross-check never disagreed.

Copied to `data/review/paladin/<tree>/r<row>c<col>.png` and
`r<row>c<col>.icon.png` (30 files, 636 KB) as provisional ids.

## Problems and caveats

- Double hovers: the same cell often produced several runs (up to 5 for
  holy-r1c1) because the dHash flips by more than 2 bits while the cursor or
  the hovered icon's highlight shares the crop rectangle. Dedupe on the cell
  absorbs this; `superseded` in the JSON counts the merged runs. Raising
  `--max-dist` to 6 would merge most of them at the grouping stage.
- Missed hovers: 12 runs were shorter than 3 frames (< 200 ms) and dropped;
  10 of them are cells that also have a proper hover. The other two
  (protection-r3c1 at 13640.3, holy-r4c2 at 13660.2) are single-frame
  flashes while the cursor swept across; they are listed in `dropped_runs`
  and should recur in later segments.
- Tooltip width: one real hover (holy-r1c2, 177 px diff box) was rejected
  until the width floor went from 180 to 120 px. Very short tooltips are
  narrow; keep the floor low.
- Semi-transparent box: where a tooltip lies over the bright row-1 icons
  (protection-r2c1, r2c4) the icons bleed through the black. Text stays
  readable but the VLM prompt should say the background may show artefacts.
- No tooltip was clipped at the frame edge in this segment (`cut_off` false
  everywhere); tree-3 hovers can extend past x 1510 and are still inside the
  work ROI, but the ROI ends at x 1780, so a tooltip wider than 270 px there
  would be flagged.
- Unresolved cells: none here. The column fallback in `cell_for_tooltip` is
  untested on real footage (no clamped tooltips occurred); rows 1-2 with long
  tooltips (Light's Vigil is 190 px tall) would be the case to watch.
- Per-segment ids are positional (`01-paladin-13640`); regenerating
  `segments.json` with different boundaries renames outputs.

## What stage 5 (VLM read) needs

- Input: `work/hovers/<id>.json` -> `hovers[].files.tooltip` (native crop,
  180-230 px wide, 80-200 px tall; upscale 2x cubic as the brief says) plus
  `page`, `tree`, `tree_name`, `row`, `col`, `t`, `sq`, `offset`, `bbox`,
  `sharpness` for the `source` record.
- Tree names: `work/calib/<id>-tree{1,2,3}.png` (45 px strips) and
  `-header.png` for the class/page label; not OCR'd yet.
- Prompt hints: layout is name, "Rank 0/N", blank, optional cost/range/cast
  lines in white, optional red requirement line ("Requires Shields"), gold
  description, optional green "Click to learn". Read `max_rank` from the
  "Rank 0/N" line. Ignore icon artefacts showing through the box.
- Dedupe across segments on (class, page, tree, row, col); prefer the
  sharpest crop; keep every candidate's `t` for provenance.

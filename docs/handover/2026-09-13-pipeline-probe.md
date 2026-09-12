# Handover: pipeline probe session (2026-09-13, 00:40-01:40 CEST)

Stage 0 of `docs/briefs/pipeline.md` executed against the live fragment URL
while the full download was still running. Output: the talent segment list
and a pixel-level description of the WoW Forever talent UI. Nothing here was
committed; the main session commits.

## What was built

- `pipeline/` uv project (Python 3.12, `uv_build`, src layout). Deps per the
  brief plus `jsonschema`; dev `pytest`. `av` pinned `>=14.0,<14.3` because
  14.4 has no wheel here and its sdist needs ffmpeg 7 headers (system ffmpeg
  is 4.4). CUDA, llama.cpp and model weights are not set up (owner installs
  the toolkit; weights wait for the download to finish).
- `pipeline/src/wowtalents/fragments.py`: fragment URL lookup
  (`requested_formats` first, then `formats`), expiry parsing, `yt-dlp -j`
  refresh into `work/probe/info.refreshed.json` (the download's own
  `info.json` is never written), single-fragment GET, ffmpeg decode from a
  pipe, download-log health check, `FragmentClient`.
- `pipeline/stages/00_probe_live.py` (typer): `scan` (resumable, 0.3 s sleep,
  3 consecutive failures -> one URL refresh, failing again -> abort, any
  `Skipping fragment` in `download.log` -> abort), `sheets` (contact sheets
  with burned-in timestamps), `sample` (native 1920x1080 PNG), `segments`
  (hand-made `work/probe/labels.json` -> `data/extracted/segments.{json,md}`).
- `pipeline/tests/test_fragments.py` (3 tests), `pipeline/README.md`.
- Verified: `uvx --python 3.12 --from yt-dlp@latest yt-dlp --js-runtimes node
  --live-from-start -j URL` returns a fresh from-start 299 URL in ~40 s (new
  `expire=` about 6 h ahead). 541 fragments were fetched with zero failures
  and zero effect on the download (0 skipped fragments throughout).

## Artefacts (all under `pipeline/work/probe/`, git-ignored)

- `frames/<N>.jpg`: 640-px frames, 60 s over 10800-22800 plus 10 s over every
  candidate region (541 total).
- `sheets/sheet_*.jpg` (coarse 4x5), `sheets/fine_*.jpg` (5x6 at 10 s),
  `sheets/headers.png`, `sheets/treenames.png` (header/tree-name strips of
  all samples), `sheets/panel_13680.png`, `sheets/tooltip_13680.png`,
  `sheets/check_mage.jpg`.
- `samples/<N>.png`: 17 native-resolution frames, one per segment. Best three
  for calibration: `13680.png` (Paladin, tooltip open), `19080.png`
  (Warlock), `21120.png` (Hunter).
- `labels.json`: the 69 observations behind the segment list.

## Findings: segments

`data/extracted/segments.json` / `segments.md`: 28 segments, 2960 s
(49.3 min) of open talent window, all nine classes, boundaries accurate to
10 s. Nothing talent-related exists before 03:47:20. Per class (stream
time, HH:MM:SS):

| class | windows | trees |
|---|---|---|
| paladin | 03:47:20-03:48:20, 03:58:40-04:02:00 (Horde, level 38); 05:59:30-06:03:50 (Alliance dwarf) | Holy, Protection, Retribution |
| mage | 04:06:00-04:12:30; 04:53:00-04:53:40 (points already spent, rank>0 risk) | Arcane, Fire, Frost |
| warrior | 04:57:10-05:01:30; 06:16:40-06:17:40 | Arms, Fury, Protection |
| rogue | 05:04:20-05:10:00 | Assassination, Combat, Subtlety |
| warlock | 05:16:20-05:23:20 | Affliction, Demonology, Destruction |
| priest | 05:24:20-05:29:40 | Discipline, Holy, Shadow Magic |
| shaman | 05:30:30-05:38:50 | Elemental Combat, Enhancement, Restoration |
| druid | 05:44:10-05:48:40 | Balance, Feral Combat, Restoration |
| hunter | 05:50:30-05:55:20 | Beast Mastery, Marksmanship, Survival |

Caveats per segment are in the `notes` column: settings/spellbook windows
interleave with the talent window (10-60 s gaps), an Accept/Decline dialog
covers the Fury header at 04:59:00, bag windows sit on the right edge during
the second shaman pass, and the mage spends points at 04:12:00-04:12:20 and
04:53:00-04:53:40 (unspent 18->0 and 22->0), so hovers there are not
guaranteed rank 0. Every other frame checked shows "Unspent Talents 29" and
"0" on every tree.

## Findings: the talent UI (1920x1080 direct capture)

The window sits at the same pixel position in all 17 samples across all
classes, so one calibration should hold; keep the per-segment check anyway.

- Window frame: x 410-1510, y 30-678 (about 1100x650 px), upper-left/centre
  of the screen. Title "Talents" centred at (975, 47); red close X at
  (1495, 46); class medallion overlapping the top-left corner at (433, 55).
  Left frame edge x~412. "Time Left: NN min" demo timer sits above the
  window at y~18 (not part of the UI).
- Tab strip at y 80-100: "Primary" with a check mark (x 478-608, gold when
  active) and "Secondary" with a padlock (x 615-742, grey). Secondary was
  locked in every frame; no secondary trees were ever shown. Search box with
  magnifier at x 1310-1480, y 74-90 (used twice: "Improved Seal of Fury",
  "charge") plus a dropdown arrow at x~1495.
- "Unspent Talents" label with a boxed green number at x 1443-1485,
  y 108-142 (29 at level 38, consistent with one point per level from 10).
  Horizontal divider at y~145.
- All three trees are visible at once, side by side, under the Primary tab:
  tree 1 x 445-770, tree 2 x 780-1140, tree 3 x 1150-1490, y 150-630, each
  with its own background art. Tree header at y~187: round icon at
  x~535/895/1257 with a small "0" points badge below-right, tree name in
  white to its right (~16 px). Thin divider at y~225 under each header.
- Grid: 4 columns x 7 rows per tree, icon cells 36x36 px (measured 35-38),
  pitch ~54 px both ways. Column left edges: tree 1 500/552/608/664,
  tree 2 860/912/966/1020, tree 3 1226/1278/1332/1388. Row top edges
  236/292/346/400/454/510/562 (centres y ~254/310/364/418/472/528/580).
  Row 1 icons are lit with a bright green border and a "0" badge at the
  lower-right corner; deeper rows are dark grey with no badge until
  unlocked. Prerequisite arrows are thin dark lines between cells, as in
  Classic. Not all rows have 4 talents; empty positions have no cell.
- "Apply Changes" button at x 890-1030, y 645-660 (greyed until points are
  staged; lit yellow when spending). Points are staged, not committed on
  click.
- Tooltip: near-black semi-transparent box with a thin grey border,
  ~225 px wide, height by content (the Reckoning tooltip is 222x117 at
  x 1003-1225, y 335-452). Anchored ANCHOR_RIGHT style: its bottom-left
  corner sits at the top-right corner of the hovered cell (cell centre
  (984, 472) -> tooltip bottom 452, left 1003). Layout, top to bottom:
  name in white (~16 px), "Rank 0/5" in white (~12 px; yes, it shows
  Rank N/max), blank line, "Passive" in white, description in gold/yellow
  (~12 px, wraps at ~215 px), and when the talent is learnable a
  "Click to learn" line at the bottom. Rank>0 tooltips (mage at 04:53) look
  the same with "Rank 0/3" style counters.
- Overlays: webcam bottom-left x 8-470, y 598-905 with a gold border (its
  right edge is 30 px left of the tree-1 grid, no cell overlap; it does
  overlap the window's left frame in y 598-678). Chat text under/over the
  webcam at y 915-950. Player frame x 495-670, y 785-835. Right-hand action
  bars x 1830-1910; bottom bars from y 950. Minimap top-right. A "Damage
  Done" meter appears bottom-right from 04:53. Bags open on the right edge
  in the second shaman pass (x > 1700). None of these intersect the grid or
  tooltip area, but the tooltip can extend past x 1510 for tree-3 hovers
  (still on screen; the right edge of the screen is 1920).
- Differences from vanilla Classic: three trees at once instead of one tab
  per tree; Primary/Secondary page tabs (Secondary locked); search box;
  "Unspent Talents" badge instead of "Talent Points"; staged "Apply
  Changes"; per-tree points badge under the tree icon; "Passive" line in the
  tooltip; "0" badge only on available cells. Tree names differ in two
  places: priest "Shadow Magic" and shaman "Elemental Combat".

## What the next pipeline session should do first

1. Check `pipeline/work/video/download.log` (`grep -c 'Skipping fragment'`
   must stay 0; frag 4568/23077 at 01:35 CEST). Do not start another
   download.
2. Stage 3 calibration can start from `work/probe/samples/13680.png`,
   `19080.png` and `21120.png` with the numbers above; verify with an
   overlay drawing and compare against the per-segment median once the mkv
   exists. Expect the same geometry for every class.
3. Because the mkv is not there yet, stage 4 can run on fragment streams:
   `FragmentClient.fetch(sq)` for every second of a segment gives ~60 frames
   per fragment; a 320 s segment is 320 requests at ~0.6 s each. Refresh the
   URL before it expires (`refresh_info()`; current one expires 04:44 UTC).
4. Treat the mage at 04:53:00-04:53:40 and 04:12:00-04:12:20 as rank>0;
   dedupe should prefer the earlier mage pass (04:06-04:12).
5. Model choice per the plan: check free VRAM, then download Qwen3-VL
   weights only after the stream download finishes.

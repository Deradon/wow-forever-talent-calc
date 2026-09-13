# pipeline

Python (uv) side of the WoW Forever talent calculator: probes and reads the
BlizzCon stream, writes candidates to `../data/extracted/`. Brief:
`../docs/briefs/pipeline.md`. Shared code in `src/wowtalents/`, stages in
`stages/NN_name.py`, all artefacts under `work/` (git-ignored).

Every `uv run` command below assumes the working directory is `pipeline/`.
From the repo root, prefix them: `uv run --directory pipeline pytest`,
`uv run --directory pipeline stages/08_export.py --help`.

## Setup

```bash
cd pipeline
uv sync                      # Python 3.12, deps from uv.lock
uv run python -c "import cv2, av; print(cv2.__version__, av.__version__)"
```

`av` is pinned `>=14.0,<14.3`: 14.4 has no wheel for this platform and its
source build needs ffmpeg 7 headers. System `ffmpeg`/`ffprobe` (4.4) must be
on PATH. CUDA toolkit, llama.cpp and the Qwen3-VL weights are not part of the
uv project (see the brief, section 2).

## Stage 0: probe the live stream

Works while the download in `work/video/` is still running. Never writes into
`work/video/`; a refreshed fragment URL goes to `work/probe/info.refreshed.json`.

```bash
# health of the running download (must print 0)
grep -c 'Skipping fragment' work/video/download.log

# coarse scan 03:00:00-06:20:00, one 640-px frame per minute (resumable)
uv run stages/00_probe_live.py scan

# refine boundaries at 10 s
uv run stages/00_probe_live.py scan --start 13800 --end 13860 --step 10
uv run stages/00_probe_live.py scan --times 03:51:10,03:51:20

# contact sheets (4x5 grid, timestamp burned in) for visual classification
uv run stages/00_probe_live.py sheets
uv run stages/00_probe_live.py sheets --start 13800 --end 14400 --cols 3 --rows 3 --prefix fine

# native 1920x1080 PNG samples
uv run stages/00_probe_live.py sample 03:51:12,04:10:00

# observations (work/probe/labels.json) -> data/extracted/segments.{json,md}
uv run stages/00_probe_live.py segments
```

Rules baked into `scan`/`sample`: one request at a time, 0.3 s sleep, 3
consecutive failures trigger one `yt-dlp -j` URL refresh, failing again
aborts. `Skipping fragment` lines in `work/video/download.log` are classified
(`fragments.DownloadHealth`): a skip after an HTTP error (403 throttling)
aborts at once; a live-edge skip ("Did not get any data blocks", the head
fragment of the still-running stream) only warns when it predates the run
and aborts when a new one appears while we are fetching.

## Stages 3 and 4: calibrate a segment, crop its tooltip hovers

Both run on fragment streams while the mkv download is still going, using
the segment list in `../data/extracted/segments.json`. A segment is addressed
by its 1-based index, its id (`<index>-<class>-<t_start>`, e.g.
`01-paladin-13640`) or its `t_start`. Raw fragments are cached in
`work/frags/<sq>.bin` (about 400 KB each) so re-runs cost no requests; the
same one-request-at-a-time / 0.3 s / refresh-on-failure / download-health
rules as stage 0 apply.

```bash
# stage 3: median background (30 frames), icon grid, tab state, header crops
uv run stages/03_calibrate.py run 1
#   -> work/calib/01-paladin-13640.json, -median.png, -overlay.png (eyeball this),
#      -header.png, -tree{1,2,3}.png (tree-name strips for the VLM)
#   A tooltip the streamer rested on for most sampled frames wins the median
#   ("ghost"); stage 3 detects such boxes (against the other calibrated
#   segments of the class, or the frames themselves) and replaces them with
#   the median of tooltip-free frames or the same region of a donor segment
#   (`ghosts` in the JSON; calibrate the class's other segments first so
#   donors exist, or run the class twice).

# stage 4: hovers at 15 fps (every 4th frame), one native crop per hovered cell
uv run stages/04_hovers.py run 1
uv run stages/04_hovers.py run 1 --start 13680 --end 13682   # a sub-range
#   -> work/hovers/01-paladin-13640/<tree>-r<row>c<col>.png (tooltip),
#      ...-icon.png (36 px icon from the median), unresolved-<n>.png,
#      work/hovers/01-paladin-13640.json (per hover: t, sq, offset, bbox,
#      cell, sharpness, hash, frames, cursor cross-check, cut_off) and
#      work/hovers/01-paladin-13640-sheet.png (contact sheet)
```

Shared helpers (grid detection, tooltip blob, dHash grouping, cell lookup)
live in `src/wowtalents/ui.py` and are unit-tested in `tests/test_ui.py`.

### Stage 4b: hovers from the merged mkv

Footage between segments (10 s probe boundaries, ranges whose live fragments
were never cached) exists only in `work/video/<vod>.mkv`. Stage 4b decodes a
stream-time range from it (`ffmpeg -ss -i -t -vf fps=60`, streamed frame by
frame), runs stage 4's detector with a neighbouring segment's calibration and
writes stage-4-shaped output under a synthetic segment id
`m<NN>-<class>-<t_start>` (NN = donor segment) plus a `work/calib/` copy with
`borrowed_from`, so stage 5 picks it up like any segment. Stream time vs file
time: the mkv starts at pts 0 but fragment `sq` begins at file time
`sq - 0.467` (`wowtalents.mkv.OFFSET`, measured against the stage-0 sample of
fragment 13680); `gaps` checks that the range has no missing packets first.

```bash
uv run stages/04b_hovers_mkv.py offset                      # re-measure the offset
uv run stages/04b_hovers_mkv.py gaps 04:07:00 04:09:40      # packet continuity of a range
uv run stages/04b_hovers_mkv.py run mage --calib 7 --start 04:07:05 --end 04:09:35
#   -> work/hovers/m07-mage-14825.json, crops, sheet; work/calib/m07-mage-14825.json
uv run stages/05_read.py run mage --segments 8,m07 --add    # read only the cells the candidates file lacks
```

Helpers in `src/wowtalents/mkv.py` (`tests/test_mkv.py`).

### Stage 5b: adjudicate the readings (`scripts/merge_readers.py`)

`05_read.py` stores two Qwen passes, `scripts/second_opinion.py` adds a codex
reading. The merge decides between them shape by shape (`src/wowtalents/merge.py`):
the second reader wins on case, punctuation and `%`, wording goes to whichever
variant the other readings back, then a capital-`I` normaliser and a spell-name
repair against the Classic prior run over the result. It also re-derives
`source.confidence` and `source.note` from the evidence, so it is idempotent.

```bash
uv run scripts/second_opinion.py mage                      # codex reading into the candidates file
uv run scripts/merge_readers.py all --dry-run              # report, write nothing
uv run scripts/merge_readers.py all                        # rewrite every candidates file
uv run scripts/merge_readers.py all --reread               # one more VLM pass (4x) over the queue crops first
```

`--reread` needs llama-server: `LLAMA_PORT=8089 scripts/llama-server.sh 4b`.
Records it rewrites lose their `ranks_anticipated` block, so re-run stage 6/8.

## Tests and validation

```bash
uv run pytest
uv run python validate.py --check ../data/talents/*.json   # must exit 0
uv run python validate.py --report ../data/extracted/warrior.json   # review queue
```

`validate.py` is the standalone validator for `docs/DATA-SCHEMA.md` rules
1-19; `--check` is rule 12 (the file must be byte-identical to the canonical
serializer output). The `check` job in `.github/workflows/deploy.yml` runs
`pytest` and the `--check` line above, and the deploy job waits on it.

<!-- data-side stages (ranks + export); keep this section self-contained -->
## Stage 6 and 8: rank anticipation and export (data side)

Shared code: `src/wowtalents/ranks.py` (brief `data-prior-and-review.md`
section (b)) and `src/wowtalents/export.py` (`DATA-SCHEMA.md` sections 4-6).
Both stages import `validate.py` for the canonical serializer and the rules.

```bash
# ranks 2..N for every hover record; writes ranks_anticipated into the candidates file
uv run stages/06_rankfill.py warrior                      # data/extracted/warrior.candidates.json in place
uv run stages/06_rankfill.py warrior --dry-run            # table only (* = review queue)
uv run stages/06_rankfill.py warrior --force --out /path/to/copy.json

# candidates -> data/extracted/warrior.json (raw pipeline output, validated before writing)
uv run stages/08_export.py extract warrior --update-encoding
# extracted + data/overrides/warrior.json (all nine classes have one) + reviewed records
# -> data/talents/warrior.json
uv run stages/08_export.py promote warrior
uv run stages/08_export.py all warrior --update-encoding  # both; -v prints dedupe/encoding INFO lines

# after promoting every class: delete data/review crops nothing references any more
uv run stages/08_export.py prune --dry-run
uv run stages/08_export.py prune
```

`--update-encoding` refuses to rewrite a `data/encoding/v<N>.json` marked
`"frozen": true` and forks `v<N+1>.json` instead (see `data/encoding/README.md`).
`v1` is deliberately unfrozen until launch. `prune` needs all nine class files
present and keeps everything `data/talents/*.json` and `data/examples/*.json`
point at.

Scaling rule (changed 2026-09-13, `docs/handover/2026-09-13-rank-scaling.md`,
section 6): **anticipated ranks are `v1 * k`.** A Forever talent scales
proportionally from its own rank 1 whatever shape Classic has. The one
exception is a verbatim copy: an exact same-name Classic talent with the same
rank count whose rank 1 equals Forever's - then Classic's own numbers are used,
because they are Blizzard's and not our arithmetic (that is also why 8/16/25
stays 8/16/25 and is not re-derived as 8/16/24). Classic's additive step and
offset are never re-based onto a foreign rank 1; where the matched slot is not
proportional (*affine*, 10/15/20 = 5k + 5, or *irregular*, 15/30/45/65) the
pattern that was **not** applied is named in `ranksNote` and the record drops
to `low` confidence. Values that look rounded in game (51 -> 50) are reported
in a `Rounding:` clause of `ranksNote` and never rounded in the data.

Decision table of stage 6 (`ranksSource` / confidence): 1-rank talent
`observed`; exact same-class Classic name with the same rank-1 value and rank
count `classic-prior` high (copied, no review); the same across classes
`classic-prior` medium; any match re-based or with a different rank count
`classic-prior` medium (`v1 * k`), dropping to low when Classic's own slot was
not proportional; shape-changing per-rank strings with an identical rank-1 text
`classic-prior` medium; no match with one or two numbers `extrapolated`
(`v1 * k`, low); no match with zero, three or more numbers, or any `sec`/`min`
slot, `manual`. `ranksNote` states the rule, `needsManual` marks copies of
rank 1.

`extract` never applies overrides (override targets are the ids as they
appear in `extracted/`, section 6.2). `promote` applies them in file order,
keeps every `reviewed: true` talent of the existing `talents/` file that no
override targets (`REVIEWED-DIFF` warning when the pipeline now disagrees),
strips `source.readings`, and validates with `--check`. Validation rule 11
needs the class in the highest `data/encoding/v<N>.json`: `--update-encoding`
upserts it while that version is unpublished; afterwards bump per
`data/encoding/README.md`. Any validation error leaves the target untouched
and exits 1. Crops are copied from the candidates' `source.crop_path` to
`data/review/<class>/<tree>/<id>.png`; `iconCrop` uses `<id>.icon.png` when
`source.icon_crop_path` exists, else the tooltip crop.

Tests: `tests/test_ranks.py` (real Classic talents as fixtures) and
`tests/test_export.py` (synthetic `tests/fixtures/warrior.candidates.json`,
end to end through the stage CLI in a temporary repo root).

<!-- stage 9 (icon matching); keep this section self-contained -->
<!-- stage 7 (prerequisite arrows); keep this section self-contained -->
## Stage 7: prerequisite arrows

Rank-0 tooltips never list a talent prerequisite (0 of 1155 cached readings
carry a "Requires <talent> (Rank N)" line; the 10 "Requires ..." lines that
exist are stances, forms, shields and a level), so `requires` comes from the
arrows drawn between cells. Shared code `src/wowtalents/arrows.py`, stage
`stages/07_arrows.py`, tests `tests/test_arrows.py` (synthetic tree).

```bash
uv run stages/07_arrows.py detect warrior     # -> work/arrows/warrior.json + warrior-overlay.png (eyeball this)
uv run stages/07_arrows.py merge warrior      # requires_arrows into data/extracted/warrior.candidates.json
uv run stages/07_arrows.py all all            # both, every class; run_class.sh runs it between 06 and 08
uv run stages/08_export.py all warrior --update-encoding
```

How it works: the class's own Primary-page calibration medians (stage 3,
`>= 40` cells, borrowed `m*` calibrations skipped) give the un-hovered tree;
the consensus grid (cells in more than half of the medians, median rects) the
cell rects. The arrow texture is a bevelled ~2 px stroke (dark outline, 1 px
lighter core) ending in a small filled triangle at the dependent talent; on
the stream it reads as a thin line about half as bright as the art 4-7 px to
either side (dark art: 12 vs 20, bright art: 31 vs 60). For every ordered
cell pair of a tree (up to 4 rows down, 3 columns across) the candidate paths
that cross no cell are tested: `straight` (same column), `row` (same row),
`L-top` (along the required talent's row, then down) and `L-bottom` (down,
then along the dependent's row). A path counts when every leg has at least
50 % of its pixels on a ridge (`ridge_masks`: centre darker than both sides
by `max(5, 0.22 x side)`, or brighter for a satisfied gold arrow) and the
head end shows an arrowhead: mean |Laplacian| over a 9 px band in the 8 px
before the dependent cell (cell border skipped) of at least 9.5 (measured
arrows 9.6-22, stroke 8-12, art between cells 2-8.4; a same-row arrow points
at the end with more energy). Medians vote (seen in more than half), an L
whose vertical leg is a detected straight arrow is dropped, and `confidence`
is mean coverage x vote share, capped at 0.7 for a weak arrowhead (below 11
or under 1.3 x the stroke) and 0.5 for an unreadable same-row direction.

`merge` puts `requires_arrows` (target cell, name, `rank` = the target's max
rank, shape, confidence, medians) on the dependent record and an `arrows`
block on the candidates file; stage 5 rewrites the candidates file, so run
stage 7 again after it. Stage 8 (`export.merge_arrow_requires`) resolves the
target id by (row, col), never overwrites a tooltip-derived requirement
(`ARROW-CONFLICT` when the tooltip names another talent or rank; the tooltip
stays), keeps a same-row arrow as a `source.note` only (the schema needs an
earlier row) and notes every arrow-derived entry: `prerequisite from tree
arrow (stage 7): <name> at rank N = its max rank (Classic rule; rank-0
tooltips do not list talent prerequisites)`. The max-rank rule is the Classic
Era behaviour (all 65 prerequisites in `data/prior/classic-era/talents.json`
require the target's max rank) and cannot be confirmed from this footage.

Cross-checks on the BlizzCon footage (2026-09-13): 67 arrows over 27 trees;
codex reading the same tree crops confirms 66 (every direction agrees), 22
match a Classic Era prerequisite by name; one known false positive
(warlock Shadowburn -> Conflagrate, an art stripe, confidence 0.7) and two
known misses (warrior Improved Bloodrage -> Last Stand, the stroke sits on
an art edge; priest Mind Flay -> Improved Mind Flay, same-row, head energy
8.3) are listed in `docs/handover/2026-09-13-prerequisites.md`.

## Stage 9: icons

Shared code: `src/wowtalents/icons.py` (features, NCC scoring, pHash re-rank,
Classic-prior hint, decision, `apply_matches`); stage `stages/09_icons.py`.
Sources, method and licensing: `data/icons/SOURCES.md`.

```bash
uv run stages/09_icons.py refs --fetch-lists   # reference list + 36 px icons into work/icons/ (git-ignored, ~70 min to rebuild; one request per icon, 0.3 s pause)
uv run stages/09_icons.py match all --sheet    # crops of data/extracted/<class>.json -> data/icons/matches.json, sheets in work/icons/sheets/
uv run stages/09_icons.py fetch                # 56 px icon per accepted match -> web/public/icons/<name>.jpg
uv run stages/09_icons.py apply all --dry-run  # then without --dry-run: icon / icon_source into the candidates files
uv run stages/08_export.py extract <class> && uv run stages/08_export.py promote <class>   # picks the icon fields up
```

A talent with an accepted match exports as `icon: <name>`, `iconSource:
"classic"` and no `iconCrop`; everything else stays a crop. Hand verdicts go
into `data/icons/verified.json` (`true` / `false` / `"<icon name>"` per
`class -> tree/talent`) and are merged on the next `match`; the file is
optional and does not exist yet. Tests:
`tests/test_icons.py` (synthetic icons and cells) and the icon case in
`tests/test_export.py`.

<!-- stage 5 (VLM read) and the per-class wrapper; keep this section self-contained -->
## Stage 5: read the crops, and `run_class.sh`

Shared code: `src/wowtalents/reader.py` (prompt, JSON schema, crop
preparation, confidence, record assembly, on-disk reading cache) and the
stage `stages/05_read.py`. Needs llama-server (`scripts/llama-server.sh 4b`,
default `http://127.0.0.1:8089`, override with `--server`).

```bash
uv run stages/05_read.py one ../data/review/paladin/holy/holy-power.png   # both passes of one crop
uv run stages/05_read.py run paladin --dry-run                       # merged hovers, no VLM calls
uv run stages/05_read.py run paladin                                 # -> data/extracted/paladin.candidates.json
uv run stages/05_read.py run paladin --segments 1,25 --limit 5 --no-copy --out /path/x.json
uv run stages/05_read.py run paladin --segments m25 --add                # append cells missing from the candidates file
```

What `run` does: merges every `work/hovers/<segment>.json` of the class on
(page, tree, row, col), keeping the crop that is not cut off and then the
sharpest (when that crop reads `rank_current > 0`, points already spent in a
later segment, the next crops are read until one shows rank 0; a cell where
every crop shows spent points keeps a note and confidence <= 0.7); takes the icon grid as the consensus of all calibrations (a cell
must be present in more than half of the calibrations with >= 40 cells, so a
spellbook or search-box median cannot add cells); reads the header strip and
the three tree strips of every segment once (display names from the
footage, tab state cross-checked against the saturation test); sends every
crop twice (3x and 2x cubic upscale, temperature 0, `response_format:
json_schema`) and sets `source.confidence` to 1.0 when both passes agree on
every field, 0.7 when name and rank agree, else 0.3; caps the confidence at
0.3 when one name is read at two cells of a tree (cell-attribution error);
writes 0-based `row`/`col` (what `export.py` expects; hover files are
1-based, the original cell is kept in `source.cell`) and copies the tree
header strip to `data/review/<class>/<tree>/_header.png` (the tooltip and
icon crops are placed by stage 8 under talent ids). Readings are cached in `work/read/cache/` by
content hash + prompt, so a re-run only pays for new crops. `--add` keeps the
existing candidates file, reads only the hovered cells it has no record for,
appends them and logs the run in an `additions` block (stats and
`missing_cells` recomputed, the duplicate-name rule applied across old and
new records). Output is an
object: `candidates` (brief section 1 shape), `segments`, `trees`,
`missing_cells` (with the reason: never hovered / only a flash shorter than
`--min-frames`), `stats`.

Reader contract (schema in `reader.TOOLTIP_SCHEMA`): `name`,
`rank_current`, `rank_max`, `kind` (`"Passive"` or null), `extra_lines`
(cost / range / cast lines), `requires` (only lines starting with
"Requires"), `description` (gold paragraph only), `footer` ("Click to
learn"), `cut_off` (text truncated or touching the border). `clean_reading`
re-files a misplaced Passive / Requires / Click-to-learn line and never
invents text. Stage 4 rejects diff blobs whose interior is less than 65 %
near-black (`ui.darkness`; real tooltips measure >= 0.69, dimmed-grid junk
<= 0.59), refuses to guess a cell when the column fallback (or a corner match
looser than 8 px) disagrees with the cursor, and flags boxes at the width
ceiling as cut off. Since the missing-cells forensics
(`docs/handover/2026-09-13-missing-cells-forensics.md`) a diff blob is a
candidate by the area of its bounding box (over a dark panel only the border
and the text differ from the median), is trimmed to the frame's black core
(`ui.dark_trim`) and snapped to the tooltip's border line (`ui.border_snap`)
before the width test, and only near-black candidates compete, so a ghost,
the game world past the window edge or a brightened panel glued to the box
no longer pushes it over the width ceiling or wins the frame as junk.
`rejected_frames[].reasons` names the failed test per blob.

Second opinion (optional, `scripts/second_opinion.py <class>`): transcribes
every crop of the candidates file with the local `codex` CLI (about 5 s per
crop, cached in `work/read/codex/`), appends the reading to
`source.readings` and lowers `source.confidence` to 0.7 with a note where
name, `rank_max` or description differ from the Qwen reading, so the record
lands in the review queue (validator `NEEDS-REVIEW` below 0.8). Records that
already carry a codex reading are skipped, so it can follow a `--add` run. On Paladin
this caught the six one-character defects that two Qwen passes agreed on
(mid-sentence "In..." words capitalised, a dropped `%`).

Whole class in one go (stops at the first error, one fragment request at a
time by construction):

```bash
scripts/run_class.sh paladin                # 03+04 per segment, then 05, 06 --force, 08 extract --update-encoding, validate
scripts/run_class.sh paladin --skip-video   # hovers exist: 05 -> 08
scripts/run_class.sh paladin --skip-read    # candidates exist: 06 -> 08
scripts/run_class.sh paladin --second-opinion   # 05, then scripts/second_opinion.py, then 06 -> 08
```

Tests: `tests/test_reader.py` (confidence levels, re-filing of misplaced
lines, record shape and 0-based indices, cross-segment merge, consensus
grid, cache keys) and `tests/test_ui.py::test_darkness_*`.

<!-- stage 12 (races); independent of stages 3-9, shares only reader.py and the serializer -->
## Stage 12: racial traits and the race/class matrix

Phase 2b of `docs/briefs/beyond-talents.md`. Shared code:
`src/wowtalents/races.py` (screen classification, portrait selection, class
bar, race box geometry, trait text, fragment and order stitching — all pure),
the race prompts in `src/wowtalents/reader.py`, the stage
`stages/12_races.py` and the validator `validate_races.py`. Normative data
contract: `docs/DATA-SCHEMA-RACES.md`. Needs the mkv and, for `read`,
llama-server.

```bash
uv run stages/12_races.py scan                       # -> work/races/states.json + native crops
uv run stages/12_races.py scan --window 03:11:00-03:16:40 --fps 4
uv run stages/12_races.py read                       # -> work/races/readings.json
uv run stages/12_races.py read --codex race          # + one codex opinion per race
uv run stages/12_races.py build                      # -> data/races/, data/review/races/, data/extracted/races.{json,md}
uv run python validate_races.py --check ../data/races/*.json
uv run python validate_races.py --report ../data/races/*.json     # review queue
```

`scan` decodes seven character-creation windows (the minutes whose stage-0
probe frame shows both faction banners, padded either side) at 2 fps **by
frame index**, not with ffmpeg's `fps` filter: `-vf fps=2` returns a frame up
to a quarter second away from the nominal time, and at stream 11520 that is
the difference between the Dwarf box and the Human one. `mkv.decode_range(...,
every=30)` uses `select` plus `-vsync 0` instead and is exact. Each frame is
classified (both banners), the selected portrait is found by its gold border
(~125 mean grey against ~58), which gives race and Skyborne variant from a
fixed 2x5 layout, and frames are grouped into runs of one scroll position by
dHash of the box; the sharpest frame of each run is written out at native
resolution. The class bar is read from the same frames without a VLM: a
greyed-out icon scores under 10 on mean saturation x value, an available one
19 to 101.

`read` deduplicates scroll positions across windows (119 states -> 33), sends
each box to llama-server twice (3x and 2x) with `reader.RACE_PANEL_SCHEMA`,
and scores agreement exactly as stage 5 does. `--codex race|disagree|all`
adds a third opinion from the `codex` CLI; a codex reading that disagrees with
two agreeing passes caps the trait at 0.9 instead of lifting it.

`build` drops row fragments (a row whose name scrolled off the edge is read as
its own trait and is always contained in the row it came from), stitches the
panel order out of the overlapping windows, merges one record per trait,
cuts the per-trait and per-icon review crops, diffs against
`data/prior/classic-era/racials.json` plus the hand verdicts in
`racial-diff.json`, and writes the race files, `matrix.json` and the
inventory. `complete: true` needs both anchors: some frame showed the box
scrolled to the top and some frame showed the lore below the last row.

Tests: `tests/test_races.py` (trait text, fragments, order stitching, band
alignment, agreement, synthetic-frame geometry, the shipped files against the
validator, and `decode_cmd`'s two frame-picking modes).

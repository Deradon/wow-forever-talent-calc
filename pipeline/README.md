# pipeline

Python (uv) side of the WoW Forever talent calculator: probes and reads the
BlizzCon stream, writes candidates to `../data/extracted/`. Brief:
`../docs/briefs/pipeline.md`. Shared code in `src/wowtalents/`, stages in
`stages/NN_name.py`, all artefacts under `work/` (git-ignored).

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

## Tests

```bash
uv run pytest
```

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
# extracted + data/overrides/warrior.json + reviewed records -> data/talents/warrior.json
uv run stages/08_export.py promote warrior
uv run stages/08_export.py all warrior --update-encoding  # both; -v prints dedupe/encoding INFO lines
```

Decision table of stage 6 (`ranksSource` / confidence): 1-rank talent
`observed`; exact same-class Classic name with constant/arithmetic slots and
the same rank-1 value `classic-prior` high (copied, no review); fuzzy,
cross-class or description match, re-based (ratio or +step), rank count
extended, or shape-changing per-rank strings `classic-prior` medium (review
queue); non-linear Classic with a different rank-1 value `manual`; no match
with one or two numbers `extrapolated` (`v1 * k`, low); no match with zero,
three or more numbers, or any `sec`/`min` slot, `manual`. `ranksNote` states
the rule, `needsManual` marks copies of rank 1.

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
content hash + prompt, so a re-run only pays for new crops. Output is an
object: `candidates` (brief section 1 shape), `segments`, `trees`,
`missing_cells` (with the reason: never hovered / only a flash shorter than
`--min-frames`), `stats`.

Reader contract (schema in `reader.TOOLTIP_SCHEMA`): `name`,
`rank_current`, `rank_max`, `kind` (`"Passive"` or null), `extra_lines`
(cost / range / cast lines), `requires` (only lines starting with
"Requires"), `description` (gold paragraph only), `footer` ("Click to
learn"), `cut_off` (text truncated or touching the border). `clean_reading`
re-files a misplaced Passive / Requires / Click-to-learn line and never
invents text. Stage 4 now rejects diff blobs whose interior is less than 65 %
near-black (`ui.darkness`; real tooltips measure >= 0.69, dimmed-grid junk
<= 0.59), refuses to guess a cell when the column fallback disagrees with the
cursor, and flags boxes at the width ceiling as cut off.

Second opinion (optional, `scripts/second_opinion.py <class>`): transcribes
every crop of the candidates file with the local `codex` CLI (about 5 s per
crop, cached in `work/read/codex/`), appends the reading to
`source.readings` and lowers `source.confidence` to 0.7 with a note where
name, `rank_max` or description differ from the Qwen reading, so the record
lands in the review queue (validator `NEEDS-REVIEW` below 0.8). On Paladin
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

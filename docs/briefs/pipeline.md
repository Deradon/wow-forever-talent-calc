# Brief: talent-extraction pipeline (build session)

Written 2026-09-13 00:30 CEST. Everything marked **[verified]** was checked on
this machine or the live URL today; **[unverified]** means confirm before
relying on it. Read `CLAUDE.md` and `docs/research/2026-09-13-*.md` first.

## 1. Objective, inputs, outputs

Extract every talent tooltip of WoW: Forever from Xaryu's BlizzCon day-1 VOD
(`DxtVEhjyROU`, 1080p60 avc1, direct game capture, Classic-style UI, only
rank-0 hovers) into per-class candidate JSON, before beta datamining exists
(2026-09-17).

Inputs
- `pipeline/work/video/xaryu-blizzcon-day1.mkv` (yt-dlp `--live-from-start`,
  299+140). **Do not start a second download.** While the download runs, only
  `xaryu-blizzcon-day1.f299.mkv` exists; it is ffprobe/ffmpeg-readable and
  grows [verified]. The merged `.mkv` appears only after the stream has ended
  and every fragment is fetched. Health check:
  `grep -c 'Skipping fragment' pipeline/work/video/download.log` (must stay 0;
  the earlier run skipped 1186 fragments with 403s on yt-dlp 2026.07.04; the
  fix is in 2026.08.19 [verified via yt-dlp issues]).
- `pipeline/work/video/xaryu-blizzcon-day1.info.json` – the format-299 `url`
  plus `&sq=N` returns fragment N, and fragment N covers stream second N
  (`sq=11000` decodes with PTS 11000.5 s) [verified]. URL carries `expire=`
  (currently 2026-09-13 03:46 UTC); refresh with
  `yt-dlp --live-from-start -j URL > info.json` [unverified that `-j` yields
  the from-start URL].
- Classic prior: `https://github.com/maladr0it/classic-talent-calculator`,
  `src/trees/<Class>/data.ts`; each talent has `pos`, `maxRank`, `reqPoints`,
  icon name and a template with per-rank arrays
  (``talentText`...${[2,4,6,8,10]}%` ``) [verified].
- Stream facts: started 2026-09-12 15:22 UTC; at 3h03m the screen is still the
  Battle.net launcher; webcam overlay bottom-left, x 0-470, y 600-905, no chat
  overlay [verified from one frame].

Outputs (never written by hand, never overwritten once reviewed)
- `pipeline/work/frames/<class>/<t>.png` full frames,
  `pipeline/work/crops/<class>/<t>.png` tooltip crops.
- `data/extracted/<class>.candidates.json` – one record per hover:

```json
{ "id": "paladin/protection/r2c1", "class": "paladin", "tree": "Protection",
  "page": "Primary", "row": 2, "col": 1, "name": "Toughness",
  "rank": {"current": 0, "max": 5},
  "description_rank1": "Increases your armor value from items by 2%.",
  "requires": ["Requires 5 points in Protection Talents"], "extra_lines": [],
  "ranks_anticipated": {"values": [[2],[4],[6],[8],[10]], "method": "classic-linear",
                        "classic_match": "Toughness", "needs_manual": false},
  "source": {"video": "DxtVEhjyROU", "t": 13872.25, "timestamp": "03:51:12.250",
             "frame_index": 832335, "frame_path": "...", "crop_path": "...",
             "reader": "Qwen3VL-4B-Instruct-Q4_K_M+mmproj-Q8_0", "confidence": 0.93,
             "reviewed": false} }
```
- `data/overrides/<class>.json` (human edits; format in `docs/DATA-SCHEMA.md`
  section 6.2), `data/extracted/<class>.json` (merged export in the canonical
  schema, input to `data/talents/`). Field names in the candidate file above
  are pipeline-internal; `08_export` maps them onto the canonical schema
  (`ranks_anticipated.method` -> `ranksSource`, etc.).

## 2. Environment setup

```bash
cd pipeline && uv init --name wowtalents --python 3.12 --no-workspace   # uv 0.11 [verified]; cpython 3.12.13 already installed
uv add "opencv-python-headless~=4.10" "numpy~=2.0" "imagehash~=4.3" "pillow~=11.0" \
  "av~=14.0" "rapidfuzz~=3.0" "pydantic~=2.0" "openai~=1.0" "typer~=0.15" "requests~=2.32"
uv add --dev pytest
# CUDA toolkit for WSL2: pick the newest toolkit the host driver supports (driver table in the
# CUDA release notes); 13.3 is used in this project.
# Never install a Linux driver or the "cuda" metapackage in WSL:
# https://docs.nvidia.com/cuda/wsl-user-guide/index.html  and  .../cuda-toolkit-release-notes/
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb && sudo apt-get update
sudo apt-get install -y cuda-toolkit-13-3 cmake build-essential          # cmake is missing [verified]
export PATH=/usr/local/cuda-13.3/bin:$PATH; nvcc --version
# llama.cpp (tags are bNNNNN, latest b10931 [verified]); docs/build.md: cmake -B build -DGGML_CUDA=ON
git clone https://github.com/ggml-org/llama.cpp ~/Dev/llama.cpp && cd ~/Dev/llama.cpp
cmake -B build -DGGML_CUDA=ON && cmake --build build --config Release -j 6 --target llama-server llama-mtmd-cli
# Model: measure first. The host OS and other apps can hold a share of the VRAM. Rule: run
#   nvidia-smi --query-gpu=memory.free --format=csv,noheader
# with nothing else using the GPU. Free >= 7 GB -> Qwen3-VL-8B Q4_K_M (5.03 GB + 0.75 GB mmproj + KV).
# Free < 7 GB -> Qwen3-VL-4B Q4_K_M (~4 GB total). Commands below show 4B; swap names for 8B.
# Files [verified on HF]: Qwen3VL-4B-Instruct-Q4_K_M.gguf (2.5 GB), mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf (454 MB)
uvx --from huggingface_hub hf download Qwen/Qwen3-VL-4B-Instruct-GGUF \
  Qwen3VL-4B-Instruct-Q4_K_M.gguf mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf --local-dir pipeline/work/models
~/Dev/llama.cpp/build/bin/llama-server -m pipeline/work/models/Qwen3VL-4B-Instruct-Q4_K_M.gguf \
  --mmproj pipeline/work/models/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf -ngl 99 -c 4096 \
  --image-min-tokens 512 --image-max-tokens 1536 --host 127.0.0.1 --port 8080 -np 1
```
Smoke test: crop any text box from the 11000-s frame (probe stage) and POST it
base64 to `/v1/chat/completions` with `response_format: {type: "json_schema"}`
and the schema in section 4; expect valid JSON in < 3 s and
`nvidia-smi` < 5 GB used. If free VRAM later exceeds 7 GB, swap in
`Qwen3VL-8B-Instruct-Q4_K_M.gguf` + `mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf`
(same repo pattern) – higher fidelity on long descriptions. Sampling: `temperature 0`
(the card's 0.7 is for chat). `--image-*-tokens` values are a starting point [unverified].

## 3. Stages (`pipeline/stages/NN_name.py`, shared code in `pipeline/src/wowtalents/`)

All positional work is OpenCV; the VLM only reads text or answers yes/no.

0. `00_probe_live` – *find the talent footage before the mkv exists.* Input:
   info.json. For N in 10800..22800 step 60 (owner: nothing relevant after 6h20m), GET `url&sq=N` (1 request at a
   time, 0.3 s sleep; abort on 3 consecutive 403s so the main download is not
   harmed), `ffmpeg -i - -frames:v 1` -> 640-px frame -> VLM yes/no
   `{talent_window_open, class_name}`. Refine each true/false boundary at 5 s
   steps. Output `work/segments/probe.json` `[{t_start, t_end, class}]`.
   Accept: first talent segment found within 15 min wall time. Test: N=11000
   must return false.
1. `01_index` – once the mkv exists: ffprobe duration/fps, check for timestamp
   gaps (`ffprobe -show_packets`, dts jumps > 1 s -> log), write
   `work/index.json`. Accept: gaps listed, fps 60.
2. `02_segments` – 1 fps (`ffmpeg -ss T -t D -vf fps=1,scale=960:-1`) over the
   probe windows; pHash the grid region (excluding the tooltip and webcam
   boxes); runs with Hamming <= 6 -> segments; label each once by VLM
   reading the header (class, tree names, Primary/Secondary). Output
   `work/segments/segments.json`. Accept: 9 classes, ~27 trees, no segment
   < 20 s unlabeled. Test: on one 5-min clip, segments match manual watch.
3. `03_calibrate` – per segment: median of 30 frames = background; Canny +
   contours on the median -> icon squares -> grid cells (row, col) per tree;
   detect tab state and tree names from the header crop. Output
   `work/calib/<segment>.json`. Accept: cell count equals visible icons; all
   cells >= 36 px. Test: overlay drawn boxes on the median frame, eyeball.
4. `04_hovers` – 4 fps at native resolution; `absdiff(frame, median) > 25` ->
   close -> largest blob (area > 15k, aspect 1.2-3.5) = tooltip; dHash of
   the crop; runs of >= 3 near-identical hashes = one hover; take the middle
   frame, hovered cell = cell nearest the tooltip anchor corner, cross-checked
   by cursor template. Dedupe on (tree, row, col), keep sharpest (Laplacian
   variance). Output frames + crops + `work/hovers/<class>.json`. Accept: one
   crop per visible talent; no crop clipped at the frame edge. Test: clip of
   one tree, count == icons.
5. `05_read` – crop upscaled 2x (cubic) -> llama-server, schema in section 4,
   temperature 0, 2 passes (raw crop and 1.5x crop); confidence = agreement
   (1.0 identical, 0.7 name+rank identical, else 0.3). Output
   `data/extracted/<class>.candidates.json`. Accept: 100 % valid JSON, >= 95 %
   pass 1/pass 2 agreement on the test tree.
6. `06_rankfill` – match `name` (rapidfuzz `token_ratio >= 90`) against the
   Classic prior; if the Classic template has the same number of placeholders,
   reuse its scaling pattern (linear: value_k = v1 * k, or the Classic
   per-rank ratios), else linear extrapolation of every number in
   `description_rank1`; set `needs_manual` when no match, > 2 numbers, or
   `max_rank` differs from Classic. Accept: every record has
   `ranks_anticipated` with a `method`.
7. `07_validate` – section 5 rules -> `work/validation/<class>.json`.
8. `08_export` – merge candidates + overrides -> `data/extracted/<class>.json`.
   Review UI lives in `tools/review/` (static HTML, crop + editable JSON,
   writes `overrides/<class>.json`).

`09_icons` (pHash against the Classic icon set) is day 2; the web app can ship
with crops.

## 4. Reader prompt and schema

System: "You transcribe World of Warcraft talent tooltips. Copy text exactly,
including punctuation and numbers. Never paraphrase. If a field is not
visible, use null."
User (with image): "Return the tooltip content as JSON."

```json
{"type":"object","additionalProperties":false,
 "required":["name","rank_current","rank_max","description","requires","header","extra_lines","cut_off"],
 "properties":{
  "name":{"type":"string"},
  "rank_current":{"type":["integer","null"]},"rank_max":{"type":["integer","null"]},
  "description":{"type":"string"},
  "requires":{"type":"array","items":{"type":"string"}},
  "header":{"type":"object","properties":{"tree":{"type":["string","null"]},
            "page":{"type":["string","null"],"enum":["Primary","Secondary",null]}}},
  "extra_lines":{"type":"array","items":{"type":"string"}},
  "cut_off":{"type":"boolean"}}}
```
`header` is filled from a second call on the window-header crop, not the
tooltip. `cut_off` true when text touches the crop edge.

## 5. Validation and review

- Structural: one talent per (page, tree, row, col); `rank_max` in 1..5;
  `rank_current` == 0; every `requires` target resolves to a talent in an
  earlier row of the same tree; row count <= 7, col <= 4.
- Text: name fuzzy-matches Classic (record `classic_match` or null); numbers in
  the description parse; no `cut_off`; confidence >= 0.7.
- Anything failing goes to the review UI; edits land only in
  `data/overrides/<class>.json` with `reviewed: true`. Export
  merges overrides last; a record with `reviewed: true` is never replaced by
  a re-run (compare `source.t`; keep the reviewed one, log the diff).
- Promotion to `data/talents/<class>.json` is a separate manual step.

## 6. Risks specific to this footage

- Webcam overlay (bottom-left) can cover the lower rows of the left tree ->
  mask that box in every diff and hash; flag talents whose cell intersects it.
- UI scale or window moves -> calibration is per segment, and a pHash jump
  inside a segment forces re-calibration.
- Tooltip off-screen/clipped near the right edge -> `cut_off` flag, second
  hover later in the stream usually recovers it.
- Primary/Secondary tabs and side-by-side trees -> the header read is part of
  every segment label; dedupe key includes `page`.
- Scrolling inside a tree page -> grid rows re-detected from the median
  frame per segment; row index from the y position relative to the topmost
  detected row, not absolute pixels.
- Download gaps (403 skips) -> stage 1 gap list; re-probe those windows via
  fragment URLs.
- VRAM pressure -> stop llama-server before running OpenCV stages in
  parallel; never run two VLM instances.

## 7. First working day (time boxes)

- 0:00-1:00 uv project, CUDA, cmake, llama.cpp build started in background.
- 1:00-2:00 `00_probe_live` running against fragment URLs; model download;
  smoke test.
- 2:00-3:30 `02_segments` + `03_calibrate` on the first found segment.
- 3:30-5:30 `04_hovers` + `05_read` on that segment; fix crop/bbox issues.
- 5:30-7:00 `06_rankfill`, `07_validate`, `08_export`, minimal review page.
- 7:00-8:00 run the first full class end to end; write
  `docs/handover/<date>-pipeline.md`.

Definition of done, "first class fully extracted": every talent visible in
that class's segments has a candidate record with a crop, a reading with
confidence >= 0.7 or a reviewed override, `ranks_anticipated` with a method,
zero validation errors, and `data/extracted/<class>.json` loads in
`web/` via the schema validator.

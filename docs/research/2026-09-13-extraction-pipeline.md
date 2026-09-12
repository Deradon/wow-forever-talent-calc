# Research: tooltip extraction pipeline (2026-09-13)

Role: computer-vision / data-extraction engineer (sub-agent). Machine: WSL2
Ubuntu, NVIDIA GPU with 8 GB VRAM, Python 3.12 via uv, ffmpeg 4.4, yt-dlp. Decision taken afterwards: **local Qwen3-VL is the text
reader** (not the Claude API); the comparison below is kept for reference.

## Recommended pipeline (stages = scripts)

1. `01_download` – yt-dlp, highest resolution, merge to MKV, save info JSON.
2. `02_sample` – ffmpeg -> frames at 4 fps, downscaled to 960 px for hashing;
   PyAV for random access at native resolution later.
3. `03_segment` – pHash-cluster the *talent-grid region* (icon layout is unique
   per tree) -> contiguous segments; label each cluster once by reading the
   frame header with the VLM.
4. `04_tooltip_detect` – per-segment median background; frame diff -> tooltip
   mask -> bounding box. Hovered cell = grid cell nearest the tooltip anchor
   (verified by icon pHash).
5. `05_stable_frames` – dHash on the tooltip ROI; a talent = run of >= 3
   identical hashes; take the middle frame at full resolution; dedupe repeated
   hovers by (tree, cell).
6. `06_read_tooltip` – VLM with a JSON schema; returns
   `{name, rank_current, rank_max, description, requires}`.
7. `07_icons` – crop grid cell, pHash + colour histogram against the Classic
   icon set -> canonical icon name.
8. `08_validate` – schema check, reader agreement, name-dictionary fuzzy match
   against Classic data, numeric-progression checks, row/col uniqueness,
   prerequisite consistency.
9. `09_review_ui` – static HTML page: crop + reading + editable JSON; writes
   `overrides.json`. Only records failing step 8 go here.
10. `10_export` – merge into per-class talent JSON for the app.

Everything positional (bbox, grid cell, icon) is deterministic OpenCV; only
*reading text* uses ML. Do not ask a VLM for coordinates.

Caveat: a tooltip at "Rank 0/5" shows only rank-1 text. Plan to (a) capture
whatever ranks appear, (b) synthesise the rest from the numeric progression
when linear, (c) flag non-linear talents for manual entry using the Classic
prior dataset.

## 1. Download

```
yt-dlp -f "bv*+ba/b" -S "res,fps,vcodec:av01,vcodec:vp9,br" \
  --merge-output-format mkv --write-info-json -o "%(title)s.%(ext)s" URL
```
Prefer resolution over framerate for small text. (Reality for this source:
the stream tops out at 1080p60 avc1; a live stream must be fetched with
`--live-from-start` and cannot be partially downloaded.)

## 2. Segmentation (grid-region pHash clustering)

Scene-change detection is noisy because tooltips popping in/out are "scene
changes". Instead: at 1 fps, pHash the talent-grid ROI (icons only, excluding
the tooltip area). Runs of the same hash (Hamming <= 6) are segments. ~27
trees, so label each cluster once with one VLM call on the frame header.

## 3. Stable tooltip frames

Sample at 4 fps (hover dwell is usually > 0.5 s). dHash (imagehash, 16x16) on
the detected tooltip bbox. Hovered talent = maximal run with hash distance
<= 2; require run length >= 3; pick the middle frame, re-extract at native
resolution. Dedup on (tree, row, col); keep the sharpest crop (Laplacian
variance).

## 4. Text reading engine comparison

| Engine | Stylised gold text on dark | Setup on WSL2 | Structured output | Verdict |
|---|---|---|---|---|
| Tesseract 5 | Poor without heavy preprocessing | trivial | No | Skip |
| EasyOCR | OK, slow | easy | No | Skip |
| PaddleOCR PP-OCRv5 | Best classic OCR; cuDNN clashes with torch | painful | No | Optional third reader |
| RapidOCR (onnxruntime) | ~PP-OCRv4, CPU-fast | trivial | No | Best pure-OCR fallback |
| Qwen3-VL-8B Q4_K_M (llama.cpp) | Very good, keeps line structure | build llama.cpp with CUDA; ~5 GB weights + mmproj | Yes (JSON schema grammar) | **Chosen: local primary** |
| Claude Opus 5 (API) | Best | pip | Yes | Not chosen (cost/keys) |

Why VLM over OCR+regex: the tooltip is colour-coded (yellow name, white
"Rank 0/5", gold description, red "Requires ..."). A VLM returns the fields
directly; OCR forces rebuilding that from line boxes and colour sampling and
breaks on multi-line descriptions.

Local setup: `Qwen/Qwen3-VL-8B-Instruct-GGUF` Q4_K_M (~5 GB) +
`mmproj-…-F16.gguf`, `llama-server --n-gpu-layers 99 --ctx-size 4096`,
OpenAI-compatible endpoint with `response_format: json_schema`. If VRAM is
tight, Qwen3-VL-4B (~3 GB). Expect 1-2 s per crop on an 8 GB GPU.

## 5. Tooltip and hovered-cell localisation

- Tooltip bbox: talent frame is static per segment, so `median(frames)` is a
  clean background. `absdiff(frame, median) > 25` -> morphological close ->
  largest blob with area > 15k px and aspect 1.5-3 = tooltip. Refine edges by
  thresholding the near-black backdrop (HSV V < 40, S < 60) inside the blob.
- Hovered cell: calibrate the grid once per resolution (Canny + contours on
  the median frame give the icon squares); store cell centres. Hovered talent
  = cell nearest the tooltip anchor corner; cross-check with cursor template
  match and icon match. Three weak signals agreeing beat one strong one.

## 6. Icons

Crop the grid cell from the median (un-hovered) frame, resize to 64x64.
Reference set: Classic icon names from an existing Classic talent dataset,
fetched from `https://wow.zamimg.com/images/wow/icons/large/{name}.jpg`. Match
with pHash (top-10) then re-rank with a 3x3 HSV histogram. Store the canonical
icon name, not the crop; new talents get a crop with `iconSource: "crop"`.

## 7. Validation

- Prior dataset: Classic talent JSON (Wowhead-derived, e.g. in
  `maladr0it/classic-talent-calculator` or `melv-n/wow-talent-calculator`)
  gives name, max rank, position, prerequisites, icon and per-rank text.
  rapidfuzz `token_ratio >= 90` on names; compare max rank and position.
- Numeric progression: numbers per rank must form an arithmetic progression
  (or be constant); flag otherwise.
- Structural: one talent per (tree,row,col); ranks <= 5; prerequisite target
  exists in the same tree in an earlier row.
- Review UI: one HTML page listing flagged records with crop and reading;
  edits go to `overrides.json`. Expect 5-10% of records.

## 8. Effort and packages

- Stages 1-5, 7: ~1.5 days. Stage 6: ~0.5 day. Validation + review UI: ~1 day.
  Human review: 2-3 h. Total ~3-4 working days, dominated by calibration edge
  cases (UI scale changes, streamer moving the frame).
- `uv add opencv-python-headless~=4.10 imagehash~=4.3 pillow~=11.0 numpy~=2.0
  av~=14.0 rapidfuzz~=3.0 pydantic~=2.0 openai~=1.0` (openai client only for
  llama-server), optional `rapidocr-onnxruntime~=1.4`.
- llama.cpp: `cmake -B build -DGGML_CUDA=ON`; requires the CUDA 12.x toolkit
  inside WSL (`cuda-toolkit-12-x`, not a Linux driver). Check `nvidia-smi`
  works in WSL first.
- Gotchas: WSL2 RAM cap in `.wslconfig`; write frames to the Linux filesystem,
  not `/mnt/c`.

Sources: [Qwen3-VL-8B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF),
[Unsloth Qwen3-VL guide](https://unsloth.ai/docs/models/tutorials/qwen3-how-to-run-and-fine-tune/qwen3-vl-how-to-run-and-fine-tune),
[maladr0it/classic-talent-calculator](https://github.com/maladr0it/classic-talent-calculator),
[melv-n/wow-talent-calculator](https://github.com/melv-n/wow-talent-calculator).

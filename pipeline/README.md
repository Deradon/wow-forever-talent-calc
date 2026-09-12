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
aborts, and any `Skipping fragment` line in `work/video/download.log` aborts
immediately.

## Tests

```bash
uv run pytest
```

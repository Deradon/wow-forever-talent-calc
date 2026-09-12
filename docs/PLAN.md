# Project plan: WoW Forever Talent Calculator

Last updated: 2026-09-13. Owner: Deradon. Read this first; details live in the
briefs under `docs/briefs/` and the decisions in `docs/decisions/`.

## Goal

A public, static talent calculator for World of Warcraft: Forever with real
Forever talent data, live **before** datamined data exists (beta opens
2026-09-17, datamining follows within days). Data comes from Xaryu's BlizzCon
day-1 stream, in which every talent tooltip is hovered at rank 0.

## Facts that shape the plan

- Source: https://www.youtube.com/watch?v=DxtVEhjyROU, 1080p60 direct game
  capture. Relevant window: **03:00:00 to 06:20:00** into the stream (owner
  watched it). Nothing before 3 h is gameplay; nothing after 6:20 matters.
- Talent UI is Classic-style (4 x 7 grids, arrows, rank badges) with unknown
  "Primary / Secondary" tabs and trees possibly shown side by side. Total
  points, points per row and tab semantics are unconfirmed; keep them
  configurable per class file.
- Tooltips show rank-1 text only. Higher ranks are anticipated from Classic
  Era scaling patterns, marked as such in the data.
- Text reading: local Qwen3-VL via llama.cpp on a local 8 GB NVIDIA GPU. Positions,
  crops and icon matching: OpenCV. No cloud APIs.
- Web: Vite + React + TypeScript, static, GitHub Pages. MIT.
- Wowhead already has a Forever calculator page with Classic placeholder
  data. Being first with real data is the differentiator; correctness and
  visible provenance ("read from stream at 03:41:12, unreviewed") is how we
  stay credible.

## Contract between workstreams

`docs/DATA-SCHEMA.md` is authoritative for every path and field under
`data/`. Where a brief disagrees with it, the schema wins. Summary:

- `data/schema/class.schema.json` validates `data/talents/<class>.json`
  (canonical) and `data/extracted/<class>.json` (pipeline export).
- Human edits go to `data/overrides/<class>.json`; reviewed records are
  never overwritten by a pipeline re-run.
- `data/encoding/v<N>.json` is global (all classes) and immutable once merged;
  migrations under `data/encoding/migrations/`.
- Review crops: `data/review/<class>/<tree>/<talentId>.png`.
- Classic Era prior: `data/prior/classic-era/`.
- `requires` is an array. Every talent carries `source` and `ranksSource`.

## Workstreams

Three workstreams, each with a brief a fresh session can execute:

| Workstream | Brief | Owner role | Output |
|---|---|---|---|
| A. Extraction pipeline | `docs/briefs/pipeline.md` | pipeline lead (CV + Python) | `data/extracted/<class>.json` candidates with crops |
| B. Data model and review | `docs/DATA-SCHEMA.md`, `docs/briefs/data-prior-and-review.md` | data lead | schema, validator, Classic prior, rank anticipation, review flow, `data/talents/<class>.json` |
| C. Web app | `docs/briefs/web-app.md` | frontend lead | `web/` deployed to GitHub Pages |

A and C can run in parallel from day one; C starts on a hand-written sample
class file that follows the schema. B sits between them and owns the
contract.

## Phases and milestones

### Phase 0: bootstrap (2026-09-13) - done
- Repo, CLAUDE.md, README, license, research, decisions, briefs, this plan.
- Full stream download running in `pipeline/work/video/` (see Risks).

### Phase 1: first class end to end (target: 2026-09-14)
1. Pipeline env: uv project, CUDA toolkit, llama.cpp with CUDA, Qwen3-VL GGUF,
   llama-server smoke test on one tooltip crop.
2. Segment finder: scan 03:00-06:20 at ~1 frame / 5 s, detect the talent
   frame, produce a segment list with class/tree labels
   (`data/extracted/segments.json`).
3. Tooltip pipeline on one class: stable-frame selection, crop, VLM read,
   grid cell, icon match, candidate JSON with provenance.
4. Schema + validator; Classic prior dataset acquired; rank anticipation for
   that class; review pass by owner -> `data/talents/<class>.json`.
5. Web M1: that class rendered, point rules, share link, deployed to Pages.

Definition of done: a public URL shows one Forever class with all its
talents, every talent traceable to a frame, rules working, links shareable.

### Phase 2: all classes (target: 2026-09-16)
- Run the pipeline over all segments; review queue per class; publish
  classes as they pass review. Web M2: tooltips with next rank, self-hosted
  icons, review route, class picker, provenance badge.

### Phase 3: harden and prepare for datamined data (from 2026-09-17)
- Importer path from DB2/Wowhead data into the same schema; data version bump
  and encoding migrations; addon export; SEO/OG; polish.

## Fast path while the download runs

The format-299 fragment URL in `pipeline/work/video/xaryu-blizzcon-day1.info.json`
plus `&sq=N` returns one self-contained fragment covering roughly stream
second N (verified 2026-09-13). Stage `00_probe_live` in the pipeline brief
uses this to find the talent segments between 03:00:00 and 06:20:00 before
the merged file exists. The URL expires (see `expire=` in the URL) and must be
refreshed with yt-dlp. Text reader is Qwen3-VL-8B if at least 7 GB of VRAM is free
when nothing else uses the GPU, otherwise Qwen3-VL-4B; measure before
choosing. The CUDA toolkit version must be one the host driver supports (see
the pipeline brief).

## Immediate next actions (in order)

1. Confirm the download finishes and merges (check
   `pipeline/work/video/download.log`); if the stream is over, a
   `--download-sections "*03:00:00-06:20:00"` re-download of the VOD is the
   fallback.
2. Start workstream A step 1 and 2 in one session; start workstream C M1 in
   a second session using a hand-written sample class file.
3. Workstream B: write `data/schema/class.schema.json` and `validate.py`
   first, since both other streams depend on it.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Live-stream download stalls (403 on fragments, seen once already) | No source | Restart with latest yt-dlp (done); once the stream ends, section download of the VOD works. Keep the partial files. |
| VOD removed or set private | No source | Download now (running). |
| UI scale or window position changes mid-stream | Grid calibration breaks | Calibrate per segment from the median frame, not once. |
| Overlay (webcam, chat) covers tooltip or grid | Missing talents | Detect overlap; flag talents whose crop intersects overlay regions; manual entry fallback. |
| Qwen3-VL misreads numbers | Wrong scaling | Two reads per crop at different settings, numeric-progression checks, Classic prior comparison, owner review before publish. |
| Rank anticipation wrong for reworked talents | Misleading tooltips | `ranksSource` shown as a caveat in the UI; only rank 1 shown as confirmed. |
| Talent rules differ from Classic (points, rows, tabs) | Wrong calculator logic | Rules per class file; confirm from the Deep Dive panel recap and first beta reports. |
| Datamined data arrives and makes our data obsolete | Wasted effort | Same schema for both; importer is Phase 3. Our value is the head start plus a nicer UI. |

## Open questions

- Total talent points and points-per-row in Forever (assume 51 and 5).
- Meaning of Primary / Secondary tabs; whether both trees on screen belong to
  the same page.
- Eventual custom domain (would change the Vite base path from
  `/wow-forever-talent-calc/` to `/`).
- Whether any talents were hovered above rank 0 anywhere in the window.

## Repository

https://github.com/Deradon/wow-forever-talent-calc (pushed 2026-09-13).
Pages must be enabled once with source "GitHub Actions"; the deploy
workflow then publishes to https://deradon.github.io/wow-forever-talent-calc/
on every push to `main`.

## Status log

- 2026-09-13 ~01:30: all three workstreams have a first increment. Data:
  schema, validator (17 tests), encoding v1, Classic Era prior (432 talents).
  Web: milestone 1 live at https://deradon.github.io/wow-forever-talent-calc/
  on the example class (40 unit tests, 4 browser tests). Pipeline: uv project,
  fragment client, stage 0 probe done: 28 segments, 49 min of talent footage
  from 03:47:20 to 06:17, all nine classes, UI measured pixel-exact (see
  `docs/handover/2026-09-13-pipeline-probe.md`). llama.cpp built with CUDA;
  model weights not yet downloaded (waiting for the video download).
- Next: `03_calibrate` and `04_hovers` on the Paladin segment using the probe
  samples; download the 4B model once the video is in; then `05_read`.

- 2026-09-13 00:27: download restarted with yt-dlp 2026.08.19 after the
  first attempt (2026.07.04) skipped ~1,200 fragments on 403s. Zero skips
  since; ETA ~02:50 local.
- 2026-09-13 00:50: Phase 0 complete: research, decisions, schema, three
  briefs, plan, handover.

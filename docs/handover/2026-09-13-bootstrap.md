# Handover: bootstrap session (2026-09-13)

## Done
- Repo initialised (`main`), CLAUDE.md, README, MIT LICENSE, .gitignore.
- Research (three sub-agents) saved under `docs/research/`.
- Decisions recorded in `docs/decisions/0001-initial-decisions.md`.
- Master plan `docs/PLAN.md`; data contract `docs/DATA-SCHEMA.md`; briefs
  for the three workstreams under `docs/briefs/`.

## Running
- Stream download: `pipeline/work/video/` (git-ignored). Started 00:27 local
  with `uvx --from yt-dlp@latest yt-dlp --live-from-start` (2026.08.19),
  formats 299+140, merge to `xaryu-blizzcon-day1.mkv`. Check:
  `tr '\r' '\n' < pipeline/work/video/download.log | tail -1` and
  `grep -c 'Skipping fragment' pipeline/work/video/download.log` (must be 0).
  Until the merge finishes only `xaryu-blizzcon-day1.f299.mkv` exists; it is
  readable by ffmpeg. The first attempt's log is `download.attempt1.log`.
- The stream was still live at 00:16 local; the merged file appears only after
  it ends and all fragments are fetched.

## Next (in order)
1. Pipeline session: execute `docs/briefs/pipeline.md` sections 2 and 3
   (stage 0 first: probe fragments between 03:00:00 and 06:20:00).
2. Data session: `data/schema/class.schema.json` and `pipeline/validate.py`
   from `docs/DATA-SCHEMA.md`, then the Classic prior per
   `docs/briefs/data-prior-and-review.md`.
3. Web session: `docs/briefs/web-app.md` M1 on a hand-written sample class
   file (use the `tinker` example in `docs/DATA-SCHEMA.md` section 11).
4. Repository exists: git@github.com:Deradon/wow-forever-talent-calc.git
   (pushed). Enable Pages with source "GitHub Actions" in the repo settings.

## Surprises
- yt-dlp cannot partially download a live stream from its start; the full
  download is the only option until the VOD is finalised.
- yt-dlp 2026.07.04 silently skipped fragments after 403s; 2026.08.19 fixes it.
- Free VRAM varies with what else uses the GPU; the pipeline brief says to
  measure at setup and pick the 8B model when at least 7 GB is free, else 4B.
- Wowhead's Classic talent endpoint has positions and spell ids but no text;
  per-rank text comes from `melv-n/wow-talent-calculator` `spells.json` or
  Wowhead spell tooltips (see the data brief).

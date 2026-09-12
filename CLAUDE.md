# WoW Forever Talent Calculator

Talent calculator for **World of Warcraft: Forever** (Classic+, announced at
BlizzCon 2026-09-12). Two halves: a data-extraction pipeline that turns
gameplay video into talent JSON, and a static web app that renders it.

## Layout

- `pipeline/` – Python (uv). Video download, frame extraction, tooltip OCR,
  JSON assembly, validation. Never edits `data/` by hand; writes to
  `data/extracted/`.
- `data/` – Canonical talent data (`data/talents/<class>.json`) plus the raw
  pipeline output it was reviewed from. Hand corrections go into
  `data/talents/`, with provenance kept (`source` field).
- `web/` – Static talent calculator (no backend). Reads `data/talents/`.
- `docs/` – Plans, briefs, handovers, decisions. Read `docs/PLAN.md` first.
- `tools/` – One-off scripts (review UI, diffing, icon matching).

## Rules

- Data source of truth is `data/talents/*.json`. Schema in
  `docs/DATA-SCHEMA.md`. Run the validator before committing data changes.
- Every talent record keeps `source` (video id, timestamp, frame path,
  confidence). Data corrected by hand keeps `source.reviewed: true`.
- Web app must stay deployable as static files (GitHub/Cloudflare Pages).
- Pure rules (point allocation, row gating, prerequisites, URL encoding) live
  in `web/src/rules/` with unit tests. No DOM access there.
- Large artefacts (video, frames) are git-ignored. Keep them under
  `pipeline/work/`. Small sample frames used as test fixtures may be committed.
- Docs in English. Keep `docs/PLAN.md` status section current when a phase
  finishes; write handovers to `docs/handover/`.

## Decisions (see docs/decisions/)

- Local Qwen3-VL via llama.cpp reads tooltip text; no cloud APIs. OpenCV
  owns all positional work.
- Vite + React + TypeScript, Tailwind, Vitest. GitHub Pages hosting, so the
  app needs a base path and hash/query routing. MIT license.
- Source window in the stream: 03:00:00 to 06:20:00. Only rank-0 tooltips
  exist; higher ranks are anticipated from Classic Era scaling and marked via
  `ranksSource`.

## Commits and privacy

- Public repository. No real names, e-mail addresses, home paths, hostnames
  or hardware readouts in tracked files. Commit author identity is the
  owner's normal git identity and is fine.
- Commit messages: a `Co-Authored-By` line for Claude is fine; never add a
  `Claude-Session:` line or any claude.ai session URL. A local commit-msg
  hook rejects them.

## Commands

See `README.md` (filled in as tooling lands). The stream download lives in
`pipeline/work/video/` (git-ignored); check `download.log` before touching it.

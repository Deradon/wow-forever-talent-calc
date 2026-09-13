# Project plan: WoW Forever Talent Calculator

Last updated: 2026-09-13. Owner: Deradon. Read this first; details live in the
briefs under `docs/briefs/`, the decisions in `docs/decisions/`, the ranked
findings in `docs/reviews/2026-09-13-consolidated.md` and the session
handovers indexed in `docs/handover/README.md`.

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
- Text reading: local Qwen3-VL via llama.cpp on a local GPU. Positions,
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

### Phase 1: first class end to end (target: 2026-09-14) - done 2026-09-13
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

### Phase 2: all classes (target: 2026-09-16) - done 2026-09-13
- Run the pipeline over all segments; review queue per class; publish
  classes as they pass review. Web M2: tooltips with next rank, self-hosted
  icons, review route, class picker, provenance badge.

### Phase 2b-2d: beyond talents (after Phase 2; brief: `docs/briefs/beyond-talents.md`)

The stream also shows character creation with racial trait panels for 9 of
10 races (about 60 % differ from Classic, Skyborne has two faction variants),
a redesigned spellbook with new baseline spells, a new Legacy system, the
Skyborne starting zone and a new character sheet. Inventory with timestamps:
`data/extracted/other-content.md`.

- 2b Races and race/class combos (done 2026-09-13): `data/races/<race>.json`,
  route `#/races`. Cheapest, complete, highest news value.
- 2c "What changed vs Classic" view (done 2026-09-13): route `#/changes`, generated
  `data/changes/index.json`; stays valuable after datamining.
- 2d Spellbook lists and hover tooltips (data half done 2026-09-13):
  `data/spells/<class>.json`, 327 entries and 112 tooltips over eight classes
  (priest never on screen), route `#/spells/<class>` not built yet -- see the
  recommendation in `docs/handover/2026-09-13-spells-data.md` section 6.
  Legacy and lore still open, as a hand-written notes page (2-3 h).

### Phase 3: harden and prepare for datamined data (from 2026-09-17)
- Importer path from DB2/Wowhead data into the same schema; data version bump
  and encoding migrations; addon export; SEO/OG; polish.

## Fast path while the download runs (historical, 2026-09-13)

Kept for the record: the download finished and both questions below were
settled (Qwen3-VL-4B, llama-server on port 8089). Nothing here is a live
concern.


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

Where we are: all nine classes are live with 469 of 470 talents, nothing is
reviewed, and a full review round (usability, text quality, data audit, code
and docs, performance and accessibility) landed on 2026-09-13. The ranked
findings and their work packages are in
`docs/reviews/2026-09-13-consolidated.md`; read that before picking work.

1. **Work the review packages A1, A2, B and C** from the consolidated review.
   B is the one that changes the product: the two-reader shape-aware merge
   and a re-read of the 77-record review queue, where every text error found
   in the audit sits. A1/A2 are the tooltip and interaction fixes; C is CI
   and docs (this file included).
2. **Owner review of the queue** via `#/review/<class>`: 77 talents below the
   0.8 confidence threshold plus 21 low-confidence prerequisite arrows.
   Corrections go into `data/overrides/<class>.json` by hand — the review
   route is read-only (`docs/DATA-SCHEMA.md` section 7) — then
   `08_export.py promote`. This is the only path to `source.reviewed: true`,
   and it is at 0 of 469 today.
3. **Declare launch and freeze the encoding.** By owner decision `v1` stays
   mutable until then; freezing sets `frozen: true` in
   `data/encoding/v1.json`, after which any id set or order change needs a
   `v2` plus a migration (`docs/DATA-SCHEMA.md` section 8).
4. **Phase 2b: races** (`docs/briefs/beyond-talents.md`) — `data/races/`,
   route `#/races`. Cheapest complete increment, highest news value. Then 2c
   ("what changed vs Classic") and 2d (spellbook), in that order.
5. **Phase 3 groundwork** once the beta opens on 2026-09-17: the DB2 importer
   (`docs/DATA-SCHEMA.md` section 9, still unwritten) writing the same schema,
   so datamined data is a drop-in replacement rather than a rewrite.

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

- **Total talent points and points-per-row.** Still unconfirmed. The
  assumption (51 points, 5 per row, first point at level 10, level cap 60) is
  already baked into all nine class files as `rules` with
  `rulesSource: "assumed"`, so correcting it means editing nine `rules`
  blocks, not touching code. Confirm from the Deep Dive recap or beta.
- **Primary / Secondary tabs.** Every class file ships a single page
  `primary`; no secondary tab was ever opened on stream. If Forever has a
  second page, it is a new `pages[]` entry plus `pointsPerPage`, and the
  encoding order gains its trees at the end — a version bump once frozen.
- **Rank scaling beyond rank 1.** Tooltips only ever showed rank 1, so all
  higher ranks are anticipated from the Classic prior and marked via
  `ranksSource`. The data audit found 24 talents above 1.6x the Classic max
  and cases where a constant (a health threshold) was scaled as if it were a
  coefficient. Which of these are real Forever changes is unknown until the
  beta.
- **Non-rank-0 hovers.** Not "none" as originally assumed: at least
  `mage/shatter` was captured at a rank above 1, which made its extracted
  rank-1 values wrong. Whether more exist is unknown; the fix is to never
  scale from a reading whose rank is not 1 (review package B5).
- **Eventual custom domain** would change the Vite base path from
  `/wow-forever-talent-calc/` to `/` (and the `VITE_BASE` env in
  `.github/workflows/deploy.yml`).
- **When to declare launch**, which is what freezes the encoding and turns
  build links into a compatibility promise.

## Repository

https://github.com/Deradon/wow-forever-talent-calc (pushed 2026-09-13).
Pages must be enabled once with source "GitHub Actions"; the deploy
workflow then publishes to https://deradon.github.io/wow-forever-talent-calc/
on every push to `main`.

## Status log

- 2026-09-14 ~02:30: Phase 2d data half done. Stage 11 (`11_spellbook.py`,
  `spells.py`, `validate_spells.py`, `data/schema/spell.schema.json`) read the
  spellbook: **327 list entries and 112 full hover tooltips over eight classes**
  with crops and provenance, an explicit coverage record per class, and 16 names
  with no Classic Era counterpart (Holy Strike, Seal of Fury, Call of the
  Ancestors/Elements, Totemic Recall/Projection, Fire Nova, Arcane Blast, Bane
  of Agony, Victory Rush, ...). Priest is the only class the stream never shows;
  rogue and warlock *were* shown, contrary to the survey. Pipeline 461 tests, CI
  validates `data/spells/`. Next: the `#/spells/<class>` route (scoped as
  "spells seen on stream"), an overrides mechanism for races and spells, and a
  sourced Classic spell prior with tooltip text.

- 2026-09-14 ~01:00: UI round 2 live (`#/changes` page with inline diffs,
  `sel=` deep links pinning a tooltip, level control, `?` shortcuts overlay,
  print view, embed mode). Phase 2b live: 37 racial traits for 9 races and
  the race/class matrix (16 new combinations) at `#/races`. Phases 2b and 2c
  done. Web 437 unit + 70 browser tests, pipeline 363. Remaining: optional
  2d spellbook, Phase 3 datamined importer once beta data exists
  (2026-09-17), owner review of the 6 queued records, launch freeze of
  encoding v1.

- 2026-09-13 ~23:00: landing page reduced to class crests; cell attribution
  audited and confirmed correct (Blackout/Spirit Tap swap is a real game
  change); "moved" now means row or tree change only (123 -> 81); same-row
  prerequisites allowed and detected (2 found: Holy Shock -> Divine
  Precision, Mind Flay -> Improved Mind Flay) with horizontal arrows; browser
  tests now block the deploy. Web 329 unit + 54 browser tests, pipeline 319.

- 2026-09-13 ~21:00: owner feedback round. What's new toggle moved to the
  class header; class crests on switcher and landing cards; landing page
  without per-card provenance or review links (review route by URL only);
  ranks always proportional from rank 1 (Twilight Focus 23/46/69); Classic
  diff v2 maps renamed trees (false "moved" 132 -> 123 incl. 8 real cross-tree
  moves) and adds reworked (111) and values-changed (16) categories with a
  nested word-diff card. Web 281 unit + 51 browser tests, pipeline 313.

- 2026-09-13 ~18:30: UI round 1 live: build summary column with copy-as-text,
  build code and import (our code or Wowhead Classic strings mapped by name),
  class switcher chips, wide-desktop layout up to 56 px cells, undo/redo with
  undoable reset, continue card from local storage, "New in Forever" markers
  from a build-time Classic diff (145 new, 132 moved, 18 re-ranked, 108 gone),
  shift/ctrl modifier clicks, tier gutter, cleaner arrows. Web 237 unit +
  49 browser tests. Next: round 2 of `docs/briefs/ui-improvements.md`
  (`#/changes` page, level slider, shortcuts overlay), then Phase 2b races.

- 2026-09-13 ~16:00: review round done. Five role reviews consolidated in
  `docs/reviews/2026-09-13-consolidated.md`; fix packages A1 (tooltip meta
  text: median meta/description ratio 1.80 -> 0.26), A2 (keyboard grid, touch,
  blocked-action feedback, zero-points state, search, a11y, bundle -25 %),
  B (atomic writes, one slug rule, encoding freeze flag, override `unset`,
  shape-aware reader merge: review queue 77 -> 6, 57 records marked reviewed)
  and C (CI check job gates deploy, CLAUDE.md rewrite, schema/plan refresh)
  are live. Pipeline 308 tests, web 131 unit + 18 browser tests. UI
  improvement brief at `docs/briefs/ui-improvements.md`; nested sticky
  tooltips in progress.

- 2026-09-13 ~15:00: prerequisites (67 arrows from tree backgrounds),
  proportional rank scaling (63 talents corrected, e.g. Meditation 17/34/51),
  and clean icons for 397 talents matched against a 6,631-icon reference set
  (72 keep crops, 24 of them likely new Forever icons) are live. Pipeline 171
  tests, web 81 tests. Review queue: 79 talents plus 21 low-confidence arrows
  and the doubtful rank cases in `docs/handover/2026-09-13-rank-scaling.md`.

- 2026-09-13 ~06:40: 469 of 470 talents live. Healing Light (paladin) and
  Hot Streak (mage) recovered from the merged mkv; mage Fire r1c3 proven
  absent from the footage (streamer skipped it). Master of Elements id
  collision resolved. 141 pipeline tests, 81 web tests. Next: owner review
  of the 79 flagged talents, then Phase 2b (races).

- 2026-09-13 ~06:00: owner insisted every talent was hovered; two
  independent investigations (tooltip-detector forensics, cursor tracking)
  recovered 34 of the 36 gaps and found the causes: dark-panel tooltips under
  the pixel-area gate, ghost tooltips baked into the median, merged blobs.
  Detector fixed generally. 468 of 470 live. Remaining: mage Fire r1c3,
  paladin Holy r2c1 (never cached as fragments; recovering from the merged
  mkv) and the Hot Streak / Master of Elements id collision in mage Fire.

- 2026-09-13 ~03:45: Phase 2 done. All nine classes live, 434 of 470
  talents, unreviewed; 73 flagged (orange badge) after a Codex second
  opinion on every crop; 36 cells never hovered on stream (see
  `data/extracted/SUMMARY.md`). Web M2 live (crop icons, review route,
  titles). Next: owner review via `#/review/<class>`, then Phase 2b races.

- 2026-09-13 ~evening: Phase 2 extraction done. `data/extracted/<class>.json`
  for all nine classes, 0 validation errors each: 434 of 470 cells read (36
  never hovered on stream, mostly mage Fire and rogue Combat), 73 records
  flagged by the codex second opinion, 128 with manual/extrapolated ranks.
  Nothing reviewed or promoted yet. Coverage in `data/extracted/SUMMARY.md`,
  pipeline fixes and decisions in `docs/handover/2026-09-13-all-classes.md`.

- 2026-09-13 ~03:30: Phase 1 done. Paladin live at
  https://deradon.github.io/wow-forever-talent-calc/#/paladin with 45 of 52
  talents (7 cells never hovered on stream), unreviewed, 7 flagged with an
  orange badge. Names and ranks correct on all 45 per Codex second opinion;
  ~15 % of descriptions carry a one-character defect, all routed to review.
  Remaining eight classes running through `pipeline/scripts/run_class.sh`.
  Web M2 (crop icons, review route) in progress.

- 2026-09-13 ~01:30: all three workstreams have a first increment. Data:
  schema, validator (17 tests), encoding v1, Classic Era prior (432 talents).
  Web: milestone 1 live at https://deradon.github.io/wow-forever-talent-calc/
  on the example class (40 unit tests, 4 browser tests). Pipeline: uv project,
  fragment client, stage 0 probe done: 28 segments, 49 min of talent footage
  from 03:47:20 to 06:17, all nine classes, UI measured pixel-exact (see
  `docs/handover/2026-09-13-pipeline-probe.md`). llama.cpp built with CUDA;
  model weights not yet downloaded (waiting for the video download).
- 2026-09-13 ~02:15: Qwen3-VL-4B weights downloaded; llama-server runs on
  port 8089 (8080 was taken on this machine) at ~1.6 s per crop. Stages 03/04
  work: Paladin grid calibrated (52 cells: Holy 18, Protection 16,
  Retribution 18, so Forever trees are larger than Classic's 15/14/15), 15
  crops from the first segment. Rank anticipation and export scripts done
  (81 pipeline tests). Stage 05 (read) in progress on Paladin end to end.

- 2026-09-13 00:27: download restarted with yt-dlp 2026.08.19 after the
  first attempt (2026.07.04) skipped ~1,200 fragments on 403s. Zero skips
  since; ETA ~02:50 local.
- 2026-09-13 00:50: Phase 0 complete: research, decisions, schema, three
  briefs, plan, handover.

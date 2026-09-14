# Consolidated review findings, round 2 (2026-09-14)

Sources: `2026-09-14-ux-text.md`, `2026-09-14-data-code-perf.md`. Round-one
fixes verified on the live site: all eight hold. Measurements improved where
round one asked (landing first load -24 %, main chunk -13 %, crop registry
-92 %, TTI -27 %); `dist/` grew 44 % from spell crops and entry CSS doubled.

## Headline

- Spell tooltips are the weak spot: 10 of 12 sampled "confidence 1.0"
  tooltips carry the catalogued reader defects because the shape-aware merge
  from round one never reached stage 11; four fabricated records at
  confidence 0.0 are published and counted as "new in Forever"; the spells
  validator never inspects tooltips. Racial data is clean (11/11 exact).
- Player-facing text still leaks a few pipeline words and now contradicts
  itself: 57 talents say "Checked by a reviewer" while every page header says
  "unreviewed".
- Robustness: a malformed share link prints internal ids in three bars; the
  print view is unusable; the Wowhead import report is confusing and cramped.
- Engineering: stage 12 can publish an empty race file and delete crops with
  exit 0; the stale-generated-file test cannot fail; helpers duplicated across
  stages 11/12; the commit-msg hook is not distributed.

## Package D: pipeline and data (pipeline/, data/, CLAUDE.md, PLAN.md numbers)
1. Apply the shape-aware reader merge (`merge.py`) to stage 11 list entries
   and tooltips; re-read the spell queue; confidence must reflect merge
   agreement, not two identical passes. Report before/after defect counts.
2. Fabricated or unpublishable records (confidence 0.0, no crop, no frame)
   must never reach `data/spells`; drop the four, add a validator rule, and
   recount "new" names in `data/extracted/spells.md`.
3. Stage 12: never write an empty race file, never delete committed crops on
   a failed run, non-zero exit on empty results; same guard in stage 11.
4. `validate_spells.py` inspects `tooltips[]` (confidence, cut-off, empty
   text) and lists them in the review queue.
5. Move the nine duplicated helpers from stages 11/12 into `wowtalents/`;
   remove the `sys.path.insert` pattern in favour of package imports
   (`uv run -m` or a console script), keeping every stage runnable.
6. Distribute the commit-msg hook: `scripts/git-hooks/commit-msg` plus
   `git config core.hooksPath scripts/git-hooks` in CONTRIBUTING and README.
7. CLAUDE.md and PLAN.md state numbers: 57 reviewed, 6 queued talents, spell
   queue count after fix 1.
Do not touch `pipeline/stages/10_import_db2.py` or `data/datamined/` (importer
agent in flight).

## Package E: web (web/)
1. Malformed `t=` (or any decode problem): one friendly notice ("This link
   could not be read; showing an empty build"), internal ids and reasons to
   the console only; no repeated title; fuzz test the codec with random and
   pasted strings.
2. Print view: light print palette, black text, no stars or rings, trees plus
   a two-column summary, the share URL in plain black; verify with a PDF
   screenshot.
3. Import report: modal dialog; one line per talent (dedupe per talent, not
   per point); "fewer ranks in Forever" reworded to what happened ("placed
   3 of 5 points: Forever has 3 ranks"); "and N more" only when the list is
   actually truncated.
4. Review wording consistency: page headers and landing say
   "57 of 469 talents checked" style facts from the build-time index; the
   per-talent line "Checked" stays; no page says "unreviewed" wholesale when
   part is reviewed.
5. Remaining pipeline words: "vision model", "rank-0", "frame crops",
   "70% confidence", "the reading in use", "2 readings" -> player words
   (source line: "Read from BlizzCon 2026 footage"; details: "Two
   transcriptions disagree; the one shown is the more likely.").
6. Reworked diff: show the Classic sentence and the Forever sentence as two
   lines, each with its own highlights, never one interleaved run; same on
   the nested card.
7. What's new consistency: the toggle highlights every changed talent and the
   marker shows the kind (blue star = new; small amber mark = reworked or
   values changed; nothing for column-only); rings and stars must agree.
8. Build tooling: make the stale-generated-file test able to fail (compare a
   fresh generation against the committed file in a way vitest cannot
   regenerate); `npm run e2e` exit code 0 on a green suite; classic-diff
   counting ignores unpublishable spell records; fix the five normalisation
   misses listed in the data review (one hides a real 10 % -> 5 % change).
9. Entry CSS: route stylesheets loaded with their lazy routes; entry CSS back
   near round one's size.

## Not doing now
- Mobile layout (owner: not important now).
- Replacing the review page with an editor beyond the copy-override buttons.

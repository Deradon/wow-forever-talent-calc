# Consolidated review findings (2026-09-13)

Source reviews in this folder: usability, text-quality, data-audit,
code-and-docs, performance-a11y. This file ranks what they found and assigns
work packages. Owner decision recorded: encoding v1 stays mutable until launch
is declared; add a freeze flag so it cannot change afterwards.

## Headline

- Data text is reliable where the pipeline said so: 0 errors in 68 sampled
  confidence-1.0 records; 68 % of the 77 review-queue records are wrong, and
  every text error found sits inside that queue. Systematic reader defects
  (spurious capital I x27, comma read as period x14, dropped % x7, mangled
  spell names x6) are fixable by a shape-aware merge of the two readers.
- The tooltip drowns the game text: on 70 % of tooltips the meta text is
  longer than the description; pipeline prose (Classic ids, similarity
  scores, "needs manual ranks") is printed verbatim; provenance repeats
  "unreviewed" and a timestamp on all 469.
- Interaction gaps: no search or visible names, silent blocked clicks, no
  "no points left" state, keyboard refund broken, touch cannot see tooltips
  or refund, tooltips not exposed to screen readers.
- Engineering hygiene: five stages write candidates non-atomically; three
  slug implementations; CI runs neither pipeline tests nor the validator;
  CLAUDE.md and DATA-SCHEMA.md have drifted from the code.

## Work packages

### A1. Tooltip content and player-facing text (web/src/ui/Tooltip.tsx, review route, copy)
1. One amber trust line <= 60 chars, never two: "Ranks 2-5 estimated.",
   "Only rank 1 is known.", "Uncertain reading, check." Everything else
   (derivation, rounding, confidence, timestamp, source.note) behind a
   Details toggle; Classic ids, similarity scores, reader model only on
   `#/review/<class>`. Meta never longer than the description.
2. Render `source.note` where it carries game info (stance/form requirements)
   as a proper requirement line; requirement lines end with a period and never
   leak internal ids ("on page primary").
3. Global caveat shown once per page, not four times plus per tooltip.
4. "Higher ranks unknown" wording; article and unit normalisation at render
   time only where safe (a/an before numbers, "sec" everywhere).
5. Review route: filters (class/tree/flag), jump links, show both readings
   as a diff, show the matched icon image, compact rows.

### A2. Interaction, accessibility, performance (web/src/ui/TalentCell.tsx, ClassPage, Header, App, css, build)
1. Search box filtering/highlighting talents by name; talent names available
   in the DOM (aria-label already, add a visible name on focus/hover and in
   search results).
2. Zero points left: dim available cells, tooltip and header say so.
3. Feedback for blocked actions: a small transient message near the header
   ("Requires 5 points in Holy", "Refund would orphan Consecration", ...).
4. Keyboard: pass onClick/onContextMenu/onKeyDown through getReferenceProps;
   Backspace/Delete/minus refund; WAI grid pattern (one tab stop per tree,
   arrows move); Enter/Space add.
5. Touch: tap shows tooltip with +/- buttons inside it (or tap = tooltip,
   second tap = add, long-press = refund); no hover-only paths.
6. Tooltip role and aria-describedby; live region for point changes;
   `<main>` landmark; locked border contrast >= 3:1; badge legend near the
   header; badge must not overlap neighbouring cells.
7. Crop icons: clip the in-game border and rank box out of the 36 px crop
   (inset by ~3 px) so cells do not show doubled borders and numbers.
8. Landing page: build a classes index (name, trees, counts) at build time
   instead of importing nine class chunks; code-split the review-only crop
   registry; drop runtime zod (keep it for tests), or justify keeping it.
9. SEO basics: title/description/OG tags, robots.txt, sitemap; per-class
   prerender optional.

### B. Pipeline and data (pipeline/, data/)
1. Shape-aware merge of the two readers: second reader wins on case,
   punctuation and `%`; first reader wins on wording; spell-name dictionary
   from the Classic prior for name repairs; re-read the 77 queue records.
2. Fix the five stage scripts that write candidates non-atomically (temp +
   os.replace, as export.write_validated does); one slug implementation;
   `05_read --add` dedupe bug; zero-frame guard and ffmpeg exit code in
   04_hovers/ui.decode_frames; 03_calibrate exit message.
3. Encoding: `frozen` flag in data/encoding/v<N>.json; `--update-encoding`
   refuses to modify a frozen file and creates v<N+1> instead; v1 stays
   unfrozen for now.
4. Override format: allow deleting a field (needed for requires removal).
5. Apply the data audit's 53 description overrides and the 5 decisions:
   `5-rage` re-crop from the mkv and rename to its real name; `shatter`
   ranks manual with rank 3 observed = 50 %; `improved-ghost-wolf` 1 -> 1.0;
   remove `shadowburn -> conflagrate`; add `improved-bloodrage -> last-stand`.
   Fix `mage/shatter`-style non-rank-0 crops generally (never scale from a
   rank > 0 reading).
6. Rank anticipation sanity: cap or flag values > 100 % and constants that
   should not scale (thresholds like "below 35% health"); 24 talents exceed
   1.6x Classic max, review them.
7. Remove orphaned PNGs under data/review (430 not referenced by any record).
8. Re-export all nine classes; validator 0 errors; web validate-data green.

### C. CI, docs, CLAUDE.md (.github, docs, CLAUDE.md, README)
1. CI: pipeline pytest + validate.py on data/talents + vitest + Playwright
   before deploy; fail the deploy on data errors.
2. Rewrite CLAUDE.md per code-and-docs review section 7 (accurate layout,
   where things live, current state pointer, encoding rule, privacy rule).
3. DATA-SCHEMA.md: fix the five contradictions; document iconSource values,
   requires.rank, override field deletion, frozen encoding.
4. PLAN.md: refresh "Immediate next actions"; add docs/handover/README index
   listing every handover with one line each.
5. pipeline/README and web/README: commands verified to run.

## Not doing now
- Per-class prerender and OG images beyond basic tags.
- Replacing the review page with a write-back editor.

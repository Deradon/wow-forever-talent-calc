# Handover: work package B (pipeline and data), 2026-09-13

Implements items B1-B8 of `docs/reviews/2026-09-13-consolidated.md`, against
`docs/reviews/2026-09-13-data-audit.md` (the 53 prepared overrides, the 5
decisions, the systematic error shapes) and section 5 of
`docs/reviews/2026-09-13-code-and-docs.md` (the pipeline findings).

**Result: `pipeline/validate.py --check` reports 0 errors on all nine class
files; `cd pipeline && uv run pytest -q` is 308 passed (171 before).**

## 1. Headline numbers

| | before | after |
|---|---|---|
| review queue (`source.confidence < 0.8`, not reviewed) | 77 | **6** |
| records marked `source.reviewed: true` | 0 | **57** |
| spurious capital `I` mid-sentence (census over all 469) | 27 | **0** |
| comma read as period (the audit's 14 records) | 14 | **0** |
| dropped `%` (the audit's 7 records) | 7 | **0** |
| mangled spell names (the audit's 8 records) | 8 | **0** |
| orphaned PNGs under `data/review/` | 405 | **0** |
| rank-sanity warnings (new rule 20) | - | 27 above-Classic, 5 over-100 %, 2 scaled thresholds |

The reader merge alone rewrote **63 of 469 records**, applying 42 case fixes,
16 punctuation fixes, 7 percent-sign insertions, 5 wording decisions and 3
spell-name repairs. The 53 audit overrides were then applied on top and all 53
descriptions match the audit's text byte for byte.

## 2. What was done, in the order it was done

### B2 — engineering fixes first (so the later steps are safe)

- **Atomic writes.** New `pipeline/src/wowtalents/fsio.py`: `write_text_atomic`
  / `write_json_atomic` (temp file in the same directory + `os.replace`, with
  the destination's mode preserved — `mkstemp` makes 0600 files and a rewrite
  must not quietly restrict a tracked file). Every one of the 19 truncating
  `Path.write_text` sites in `stages/`, `scripts/` and `src/` now goes through
  it. `write_candidates_atomic` additionally **refuses a rewrite that would
  shrink the record count** — stages 6, 7 and 9 rewrite the candidates file
  wholesale and only stage 8 validated first.
- **One slug.** New `src/wowtalents/text.py` holds the DATA-SCHEMA section 3
  slug and the section 2 text normaliser; `ranks.slug` and `ui.slug` are now
  re-exports and `reader.py`'s inlined copy is gone. The two naive copies did
  not collapse punctuation runs or strip accents, so `Nature's Grace` was
  `nature-s-grace` in stage-4 crop names and `natures-grace` in the exported id.
  Checked before switching: of 474 tree and talent names in the work
  directories, 15 differ between the two rules and **all 15 are talent names**,
  never a tree name, so no artefact on disk needed renaming.
- **`05_read.py --add` dedupe.** `record_key` now keys on `source.cell`
  (which stage 5 writes itself) and only falls back to the tree display name,
  compared by slug. A record that cannot be keyed at all makes the run refuse
  rather than re-read and append the cell a second time. `additive_merge` no
  longer re-stamps `generated_at` or logs an `additions` entry for a no-op run.
- **Silent failures.** `ui.decode_frames` raises `DecodeError` on a non-zero
  ffmpeg exit (stderr is drained by its own thread so a corrupt fragment cannot
  deadlock the decoder); `04_hovers` has 04b's zero-frame guard and both
  `None`-check `cv2.imread` of the calibration median; `03_calibrate` says why
  before `Exit(2)`. Every message that precedes a non-zero exit now goes to
  stderr (21 sites).

### B3 — encoding freeze flag

`data/encoding/v<N>.json` gained a `frozen` flag.
`08_export.py --update-encoding` refuses to touch a frozen file: it copies it to
`v<N+1>.json` (unfrozen), writes an empty `migrations/v<N>-v<N+1>.json` and warns
that every class file must move to `dataVersion N+1`. This is the guard for
review finding A1, where v1 was rewritten in place four times and every shared
`?v=1&t=...` link silently decoded to different talents.

**`v1.json` stays `"frozen": false`** per the owner's decision — the data is
still being corrected and no link is promised yet. `data/encoding/README.md`
now says so and says what to do at launch (set `frozen: true`).

### B4 — override field deletion

`unset: ["requires"]` is implemented in `export.apply_overrides` and in the
validator's overrides schema, exactly as `docs/DATA-SCHEMA.md` section 6.2
already described it: only optional fields, dotted `source.*` names allowed,
unsetting an absent field is a no-op, `unset` runs before `set`. `delete` and
`add` are now schema-exclusive with the other verbs. Separately, `set.source`
may be partial (it is a shallow merge, and the full record is validated after
the merge anyway) — that was rejected before.

### B1 — shape-aware merge of the two readers

New `src/wowtalents/merge.py` (pure) and `scripts/merge_readers.py` (stage 5b).

- **case / punctuation / `%`** go to the second reader. The audit adjudicated
  all 72 stored disagreements against the crops and codex was right ~100 % of
  the time on those three shapes.
- **wording** goes to whichever variant the other readings back, with the
  primary reader winning a tie — the audit's ~70 % for Qwen on wording, with
  the second Qwen pass breaking ties. That is what turns `Hurts` into `Hurls`
  (mage/pyroblast) while leaving `regain` alone (druid/furor), where codex was
  the one that was wrong.
- **spell names** are snapped to the Classic prior, but only for records
  already in the review queue and only against **that class's** vocabulary,
  within two character edits, with a unique nearest candidate. A census over
  all 469 records is why: inside the queue the dictionary is right 6 times out
  of 6; outside it, it is wrong 8 times out of 8 ("fixing" real plurals like
  `Poisons`, `Daggers`, `Soul Shards`). A prior-wide dictionary is worse still
  — at two edits it reaches `Mangle` → `Mage` and `Bleeding` → `Blessing`.
  Talent *names* are never repaired: Forever renames talents on purpose.
- **capital-`I` normaliser** behind the merge, with the audit's allow-list of
  game terms; it catches records where *both* readers agreed on a wrong capital.
- **Re-read of the review queue.** All 77 queue crops were read once more at 4x
  through llama-server and stored as a third voting reading before merging.

`source.confidence` and `source.note` are **recomputed from the evidence on
every run**, never nudged: a record is in the queue iff something is still open
(a disputed word or name, a field the merge does not adjudicate, a cut-off
crop). Running the script twice therefore says the same thing as running it
once, and a doubt that has since been settled does not linger in the note.
`source.merge` records what each run did; the superseded text is kept in
`source.readings` as `"reader": "pre-merge"` and is excluded from later votes.

Two things the merge deliberately does **not** clear: a disagreement about a
field it cannot adjudicate (`extra_lines`, the `Rank` line), and a name
disagreement — that is the shape that produced `5 Rage` for `Feral Charge`.
A `footer`-only difference is ignored entirely: the green "Click to learn" line
is not talent data, and stage 5 lists it in `differs_in` while keeping full
confidence.

**One new finding.** `mage/frost/piercing-ice` is physically truncated (line 1
ends mid-word at "Increases the damage done by yo") and no reader flagged it —
each simply guessed a plausible ending, so the readers agreed and the record
would have left the queue. A geometry check now catches it: a crop is suspect
when it has **no tooltip border on one side and** is below the class median
width. Both halves are needed — over all 469 crops a missing border alone flags
6 (5 just sit on a dark background), a narrow box alone flags 10 (9 are
genuinely short tooltips), and together they flag exactly one.

### B5 — the 53 overrides and the 5 decisions

`data/overrides/<class>.json` now exists for all nine classes: **58 entries**
(the audit's 53 plus the 5 decisions), all validating with `--overrides --check`.

1. **`druid/feral-combat/5-rage` → `feral-charge`.** Re-cropped from
   `pipeline/work/video/xaryu-blizzcon-day1.mkv` at stream t = 20800.0 with
   headroom and re-read (Qwen 3x and 4x, plus codex). The finding is stronger
   than the audit's: **the tooltip has no name line at all** in the footage —
   17 frames across the whole dwell were checked and the box begins at
   `5 Rage  8-25 yd range`, which is the Bear-form rage cost. The talent is
   named by its own second block, `Feral Charge (Cat)`. The record was renamed
   upstream in the candidates file (so the exported id, the crop filename and
   the encoding entry all agree) and both clauses are now in the description.
   `maxRank: 1` stays unverified: the crop has no `Rank x/y` line.
2. **`mage/frost/shatter`.** The pipeline now refuses to derive rank 1 from a
   non-rank-0 tooltip: `ranks.anticipate` takes an `observed_rank` and, above 1,
   returns `ranksSource: "manual"` with the observed value copied and
   `ranksObserved: [<observed rank>]`. Shatter goes from `50/100/150`
   ("150 % critical strike chance") to `50/50/50` with `ranksObserved: [3]`.
   This is a general rule, not a per-record fix — any future crop taken with
   points spent takes the same path.
3. **`shaman/enhancement/improved-ghost-wolf`** reads `1.0 sec`; the merge
   carries the decimal through and the override pins `ranks: [[1.0], [2]]`.
4. **`warlock/destruction/conflagrate`**: `unset: ["requires"]` — the arrow
   detector fired on a stripe of tree art.
5. **`warrior/protection/last-stand`**: `requires: [{improved-bloodrage, 2}]`
   added, with the same `source.note` wording the other 67 entries use.

### B6 — rank sanity flags

New validator rule 20, three warnings (warnings by design: they are review
prompts, not gate failures):

- `R20-PERCENT-OVER-100` — **5** records where a percentage slot exceeds 100 %
  at a rank that was *not* observed (`warrior/enrage` 30→150 %,
  `paladin/illumination` 50→250 %, `rogue/quietus`, `druid/predatory-strikes`,
  `hunter/improved-aspect-of-the-monkey`).
- `R20-THRESHOLD-SCALED` — **2** records where a condition was scaled like a
  magnitude (`rogue/quietus` "below 35 % health" → "below 175 %";
  `priest/early-demise`). A threshold is not a quantity and the extrapolator
  cannot tell from the numbers alone.
- `R20-ABOVE-CLASSIC` — **27** records more than 1.6x the matched Classic
  talent's maximum, the review's "24 talents" list plus a few the corrected
  texts added. Worst: `warlock/pandemic` 16.5x, `hunter/careful-aim` 10x,
  `warlock/master-demonologist` 10x, `warrior/improved-bloodrage` 10x.

### B7 — orphaned review crops

`08_export.py prune` deletes PNGs under `data/review/` that no
`data/talents/*.json` or `data/examples/*.json` references (it refuses to run
against fewer than nine class files). **405 files, 1.0 MB** removed — 399 icon
crops of talents stage 9 later matched to a real Blizzard icon, plus a stale
tree header and the pre-rename `5-rage` crops. Tooltip crops named in
`source.crop` are provenance and are never orphans.

The exporter no longer creates them in the first place: when stage 9 has
matched an icon, the record keeps no `iconCrop`, so copying the crop would only
make work for `prune`.

### B8 — re-export

All nine classes re-exported (`08_export.py all <class> --update-encoding`),
pruned, and validated: **0 errors each**. `data/encoding/v1.json` was updated in
place (it is unfrozen) and now carries `feral-charge` in place of `5-rage`.

## 3. Remaining doubtful records

**Six records are still in the review queue.** All six are named here; none is
believed wrong, each is unresolved.

| record | why it is still open | what would close it |
|---|---|---|
| `mage/frost/piercing-ice` | the crop is truncated (181 px, no right border); line 1 ends mid-word. The two readers guessed different endings. | re-crop the cell from the mkv. **Do not** override it from the Classic wording. |
| `warrior/arms/bloodthrill` | readers split on the name: `Bloodthrill` vs `Bloodthirst`. Forever renaming Bloodthirst is entirely plausible, which is exactly why a reader vote cannot settle it. | read the crop by eye |
| `warrior/fury/blood-crazed` | same shape: `Blood Crazed` vs Classic's `Blood Craze` | read the crop by eye |
| `shaman/enhancement/rage-of-the-farseer` | `Rage of the Farseer` vs `Rage of the Farseeer` (a reader typo, but which one?) | read the crop by eye |
| `paladin/holy/infusion-of-light` | `sec` vs `sec.` — a sentence-final period the readers disagree about | read the crop by eye |
| `warlock/destruction/bane-of-havoc` | the two Qwen passes differ in `extra_lines`, which the merge does not adjudicate | compare the extra lines against the crop |

**Two records read oddly but match the audit's adjudicated text exactly** and
were left alone rather than second-guessed:

- `hunter/marksmanship/improved-stings` opens "Increased the damage of your
  Serpent Sting ability" — "Increased" at a sentence start is not the capital-`I`
  shape, and the audit's override only corrected `Scorpion` → `Scorpid`.
- `warlock/destruction/shadow-and-flame` still has "for {1} sec. and hitting an
  enemy" — the audit flagged the `Immolates. and Shadowburn` clause in the same
  sentence (now fixed) but not this one.

**Not a data fix, still the largest open unknown:** `rules` is `assumed` and
16 of 27 trees cannot absorb 51 points (`R18-TREE-TOO-SMALL`). That is a
modelling question for the next footage or datamining pass.

## 4. Tests

`cd pipeline && uv run pytest -q` — **308 passed** (171 before; 137 added).
New files: `tests/test_merge.py` (66), `tests/test_fsio.py` (14),
`tests/test_text.py` (13); additions to `test_export.py`, `test_ranks.py`,
`test_validate.py`, `test_stage05_add.py`, `test_ui.py`.

Every pure change is covered, and the cases are the audit's own records, so the
tests say what the merge is *for* as well as what it does. Three assertions
guard the whole-repo state and will fail if it drifts:
`test_the_repo_has_no_orphaned_review_crops`,
`test_the_repos_encoding_v1_is_unfrozen_and_says_so`,
`test_the_repo_override_files_validate`.

## 5. Follow-ups this handover does not do

1. `web/src/data/crops.ts` still globs `data/review/*/*/*.png` eagerly; the
   inverse assertion in `crops.test.ts` (review C4) belongs to the web agents.
2. `mage/frost/piercing-ice` needs a re-crop; `04_hovers`/`04b` have no
   "tooltip border visible on all four sides" check at crop time yet — the
   check now lives downstream in `scripts/merge_readers.py`
   (`suspect_crops`) and should move into the crop stage.
3. Stage 7's arrowhead gate still reproduces both known errors
   (`Shadowburn -> Conflagrate` at head energy 10.2 over a 9.5 gate, and the
   missed `Improved Bloodrage -> Last Stand` at coverage 0.08); they are fixed
   per record by overrides here, not in the detector.
4. The percent-sign and enumeration-punctuation *guards* of audit 8.1.3-8.1.4
   were not added as validator rules — the merge removed every instance they
   would have caught, so they would fire on nothing today. Add them if a future
   reading pass reintroduces the shapes.

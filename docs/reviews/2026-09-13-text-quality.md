# Text quality review: tooltips and app copy

Date: 2026-09-13. Scope: all 469 talents in `data/talents/*.json` (9 classes,
27 trees; `ranksSource`: 230 `classic-prior`, 109 `observed`, 70
`extrapolated`, 60 `manual`), rendered as `web/src/ui/Tooltip.tsx` renders
them at rank 0, rank 1 and max rank, plus the landing-page and footer copy in
`web/src`. Read-only review; no data or code was changed.

Method: a throwaway script reimplemented `TooltipContent` +
`renderDescription` (`web/src/data/schema.ts:151`) and emitted all 469
tooltips at three ranks (1407 renders), which were then linted and compared
against `data/prior/classic-era/talents.json`.

The tooltip box is 300px wide, 13px text, 12px for the caveat
(`web/src/ui/talents.css:162`) - roughly 45 characters per line. Every length
below translates to about one line per 45 characters.

---

## 1. Meta text outweighs the talent text (systemic, affects 330 of 469)

The caveat line + provenance line are longer than the talent description
itself on **330 of 469 talents (70%)**; median meta-to-description length
ratio **1.79**. 55 caveat lines exceed 200 characters (~5 lines of orange
text); the longest is 401 characters (~9 lines) against a 3-line description.
360 talents carry a `ranksNote` (median 102 chars, max 363) and all 360 are
printed verbatim into the tooltip.

Examples:

1. `mage/burning-soul` - current tooltip at rank 1 is 4 lines of description +
   next rank, then:
   `Ranks 2+ anticipated (classic-prior): Classic mage/fire/Burning Soul (talent 23): Classic 35/70 is proportional, Classic has 2 ranks; Forever rank 1 is 23: scaled proportionally (23 x rank); Classic 15/30 is proportional, Classic has 2 ranks; Forever rank 1 is 10: scaled proportionally (10 x rank). Rounding: {0} rank 2 46 may read 45, rank 3 69 may read 70 (values above are the raw scaled numbers).`
   Proposed: `Ranks 2-3 estimated from Classic. Details` (link/toggle), with the
   full note only behind the toggle and on `#/review/mage`.
2. `priest/twilight-focus` - 359-char caveat naming a cross-class Classic
   match and a 0.93 similarity score. Proposed: `Ranks 2-3 estimated (no
   Forever data). Details`.
3. `shaman/mindfulness` - 321-char caveat. Proposed: `Ranks 2-3 estimated
   from Classic. Details`.

## 2. `ranksNote` is pipeline prose, not player prose (360 notes)

Of the 360 notes shown in tooltips: **302** name a Classic talent id
(`(talent 829)`), **60** start with the internal instruction `needs manual
ranks:`, **33** carry a `Rounding: ...` clause, **26** print a similarity
score, **15** print `(cross-class)`, **10** chain three or more clauses with
semicolons, and **8** contain a stray placeholder label (`{0}`, `{1}`) that
reads to a player like an unfilled template slot.

Examples:

1. `druid/improved-wrath` - current: `Ranks 2+ unknown: needs manual ranks:
   Classic match druid/balance/Improved Wrath (talent 762) has no alignable
   slots; ranks 2..5 are copies of rank 1.` Proposed tooltip text: `Only rank
   1 is known. Ranks 2-5 are not shown.` (the "copies of rank 1" internals
   belong in the data, not on screen).
2. `mage/arcane-shielding` - current note contains `Rounding: {0} rank 2 34
   may read 35 (values above are the raw scaled numbers).` Proposed: drop the
   `{0}` label and move the whole clause behind the details toggle as `Rank 2
   may read 35 in game (we show the unrounded 34).`
3. `warlock/pandemic` - current: `... Classic mage/fire/Critical Mass (talent
   33) (cross-class), matched on description (0.89): ...` Proposed tooltip:
   `Ranks 2-3 estimated from a similar Classic talent. Details`.

## 3. The provenance line is noise on almost every talent (469 of 469)

Every tooltip ends with a stream timestamp; **392 of 469** read `confidence
100%` (76 read 70%, one 30%), and **all 469** read `unreviewed` - which the
landing page, the class-page footer and the class `notes` already say. The
one genuinely useful per-talent flag, `source.note` (present on **134**
talents: `second reader (codex) differs in description`, `text may not be rank
1`, unparsed requirements), is never rendered: `provenance()` only prints
`note` for `kind: "manual"`, and all 469 records are `kind: "video"`.

Examples:

1. `druid/improved-wrath` - current: `Read from stream at 5:44:11, confidence
   100%, unreviewed`. Proposed: omit entirely at confidence >= 0.8; the global
   "unreviewed" notice covers it.
2. `warrior/enrage` - current: `Read from stream at 5:00:02, confidence 70%,
   unreviewed`. Proposed: `Uncertain reading - check`, with timestamp and
   percentage on the details toggle and the review page.
3. `druid/5-rage` - current provenance says `confidence 100%`, while
   `source.note` (hidden) says `every crop of this cell shows rank 5/None
   (points already spent); text may not be rank 1; second reader differs in
   name, rank_max, description`. Proposed: show `Uncertain reading - check`
   here, not `confidence 100%`.

## 4. Template and typography errors in the descriptions (~25 talents)

- **Article disagreement, 11 talents**: the template writes `a {0}%` and the
  anticipated value starts with a vowel sound (8, 80).
- **Unit inconsistency**: `sec` 407 uses vs `seconds` 7 and `secs` 3;
  `yards` 26 vs `yds` 2. **8 descriptions mix units inside one sentence**
  (`shaman/mana-tide-totem` uses `sec`, `seconds` and `yards` in one line).
- **Plural slot in the wrong place, 1**: `druid/thick-hide`.
- **Unit dropped from the template, 4**: `mage/shatter`,
  `warlock/improved-life-tap`, `shaman/healing-way`, `warlock/suppression` -
  Classic has `%` in the same sentence.
- **Misread literal that should be a number, 1**: `mage/winters-chill`.
- **Run-on enumeration with no separators and no final period, 1**:
  `rogue/venom`.

Examples:

1. `hunter/frenzy`, rank 4: current `Gives your pet a 80% chance to gain a
   30% attack speed increase for 8 sec...` Proposed: `Gives your pet an 80%
   chance ...` (render-time article fix, or `a{1}` slot).
2. `druid/thick-hide`, rank 3: current `you gain 3 additional bases Armor per
   level` (template `{0} additional base{1} Armor`). Proposed template:
   `{0} additional base Armor per level` - the count noun is "Armor", so the
   `{1}` plural slot should be deleted, not moved.
3. `mage/shatter`, rank 3: current `Increases the critical strike chance of
   all your spells against Frozen targets by 150.` (Classic: `... by 50%.`)
   Proposed: restore the `%` and cap the value - `... by 50%.` at rank 1,
   with ranks 2-3 flagged as estimated.

Also: `rogue/venom` currently renders `... Lasts longer per combo point: 1
point: 9 seconds 2 points: 12 seconds 3 points: 15 seconds 4 points: 18
seconds 5 points: 21 seconds` - no list separators, no terminal period, and
`seconds` where the rest of the corpus says `sec`. Proposed: one slot per
line (`\n` renders: `.desc` is `white-space: pre-line`) and `sec`.

## 5. Reader capitalisation leaking into mid-sentence text (~27 occurrences, 20 talents)

Words the Classic corpus always writes lowercase appear capitalised
mid-sentence, a known artefact of tooltip OCR of small caps / line starts:
`Increases`/`Increased`/`Increasing`/`Increase` 8, `Instant` 4, `Bleed` 3,
`Frozen` 3, `Interruption` 2, `Skill` 2, and one each of `Instantly`,
`Dodging`, `Freeze`, `Daze`, `Value`. (Game terms such as `Combo Points`,
`Poisons`, `Spell Lock`, `Rapid Killing` were excluded - those are legitimate.)

Examples:

1. `warrior/enrage`: current `... to deal 2% Increased Physical damage for 12
   sec ...` Proposed: `... to deal 2% increased Physical damage ...`.
2. `paladin/anticipation` and `warrior/anticipation`: current `Increases your
   Defense Skill by 20.` Proposed: `Increases your Defense skill by 20.`
   (Classic wording).
3. `warlock/fel-concentration`: current `Gives you a 23% chance to avoid
   Interruption caused by damage ...` Proposed: `... to avoid interruption
   caused by damage ...`.

## 6. Numbers that stop being plausible after anticipation (24 talents)

24 talents render a max-rank value above 1.6x the Classic max; 5 render a
percentage above 100% at max rank; 1 is outright impossible; at least 4 scale
a number that is a threshold and should stay constant. Cause is the
proportional rule in `docs/DATA-SCHEMA.md` section 5 applied to every numeric
slot, including slots whose Classic counterpart is a different quantity.

Examples:

1. `warrior/enrage`, rank 5: current `Gives you a 150% chance to deal 2%
   Increased Physical damage ...` - a chance above 100%. Classic scales a
   *damage bonus* 5/10/15/20/25, not a chance. Proposed: cap chance slots at
   100% and mark the talent for manual ranks; display `Gives you a 100%
   chance ...` with an estimate badge.
2. `rogue/quietus`, rank 5: current `... cause 10% more damage against
   targets below 175% health.` Proposed: hold the threshold constant -
   `... against targets below 35% health.`
3. `priest/meditation` / `druid/reflection` / `shaman/mindfulness`, rank 3:
   current `Allows 51% of your Mana regeneration to continue while casting.`
   (Classic tops out at 15%). Proposed: keep 51 in the data if that is what
   the arithmetic says, but the tooltip should say `Ranks 2-3 estimated` and
   the review page should carry these three in a "check this number" bucket.

Related: **60 talents** (all `ranksSource: manual`) store ranks 2..N as copies
of rank 1. The tooltip handles this correctly (`Higher ranks unknown (only
rank 1 was read).` / `Rank 5 values unknown; showing the rank 1 text.`), so
this is a data gap, not a rendering bug - but it is 60 tooltips where three
separate lines all say "unknown" (see section 7).

## 7. Wording of the unknown/anticipated lines (3 variants, redundant)

On a `manual` talent at max rank the player sees `Rank 5 values unknown;
showing the rank 1 text.` and `Ranks 2+ unknown: needs manual ranks: ...` -
"unknown" three times, plus the leaked instruction. `Ranks 2+` also reads
oddly when max rank is 2 (`Ranks 2+` is exactly one rank) and `+` is
programmer shorthand.

Examples:

1. `druid/improved-wrath` at rank 1 - current: `Next rank: Higher ranks
   unknown (only rank 1 was read).` Proposed: `Next rank: not known yet.`
2. Same talent, caveat - current: `Ranks 2+ unknown: needs manual ranks: ...`
   Proposed: `Only rank 1 was readable on stream.` (one line, no note).
3. `warrior/improved-bloodrage` (maxRank 2) - current: `Ranks 2+ anticipated
   (classic-prior): ...` Proposed: `Rank 2 estimated from Classic.`
   Generally: `Rank N estimated` / `Ranks N-M estimated`, never `N+`, never
   the raw enum value `classic-prior` / `extrapolated`.

## 8. Requirement lines (3 wordings, all unpunctuated; one leaks an id)

`requirementLine()` produces: `Requires 10 points in Balance Talents`,
`Requires 2 points in Improved Moonfire`, and `No points left on this page (51
points on page primary)`. None ends in a period (every other line in the
tooltip does), and the third exposes the internal page id. `maxed` and
`no-points` verdicts return no line at all, so a player clicking a maxed
talent gets no explanation.

Examples:

1. Current: `Requires 10 points in Balance Talents` -> proposed: `Requires 10
   points in Balance Talents.`
2. Current: `No points left on this page (51 points on page primary)` ->
   proposed: `No points left (51 of 51 spent).`
3. Currently nothing for `maxed` -> proposed: `Already at maximum rank.`

## 9. Naming (1 clear defect; trees and casing otherwise consistent)

Tree names match the Classic Era client (`Shadow Magic`, `Elemental Combat`,
`Feral Combat`); all 27 are title case, all 9 classes expose a single page
named `Primary`. Talent names are title case throughout, with colons handled
correctly (`Improved Power Word: Shield`). One record is a misread:

1. `druid/5-rage`, name `5 Rage`, description `Charge an enemy, immobilizing
   them and interrupting any spell they are casting for 4 sec.` - the header
   is a cost stripped off the tooltip. Proposed: `Feral Charge` (matches the
   description and the Classic tree slot); its `source.note` already flags the
   cell as unreliable.
2. `druid/gift-of-the-earthmother` - `Reduces the global cooldown by 0.5
   seconds` -> `by 0.5 sec` for corpus consistency.
3. `rogue/improved-distract` - `by 3 yds` -> `by 3 yards`.

## 10. Landing page and footer copy

The same caveat is stated **four times** on a class page: the nav subtitle
(`Classic+ talent calculator, data read from BlizzCon 2026 footage`), the
picker paragraph (90 words), the class-page footer line (`Data was read from
stream footage (video); talent rules are assumed. Hover a talent for its
provenance.`), and `cls.notes` (`Extracted from BlizzCon 2026 stream footage
(rank-0 tooltips only); ranks 2+ are anticipated, point rules assumed from
Classic.`) - then a fifth and sixth time inside every tooltip. The global
footer (`web/src/App.tsx`) is well-judged: disclaimer, ownership, licence,
source link, in three lines.

Examples:

1. `web/src/ui/ClassPicker.tsx` - current 90-word paragraph. Proposed two
   sentences: `Read from BlizzCon 2026 demo footage by a local vision model
   and unreviewed - expect wrong names and numbers. Only rank 1 was on
   screen; higher ranks and the point rules are estimated from Classic
   Era.` plus the repo link on its own line.
2. `web/src/ui/ClassPage.tsx` footer - current: `Data was read from stream
   footage (video); talent rules are assumed. Hover a talent for its
   provenance.` Proposed: drop it; keep only `Left click adds a point, right
   click removes one.` and the single class note.
3. `web/src/App.tsx` nav subtitle - current: `Classic+ talent calculator, data
   read from BlizzCon 2026 footage`. Proposed: `Classic+ talent calculator -
   unofficial, unreviewed data` (the provenance detail is one click away on
   the picker).

---

## Proposed style guide: player-facing meta text

**Principle.** The tooltip is a game object. A player reads it to decide
whether to spend a point. Anything that does not change that decision is not
tooltip text. Meta text earns its place only when it tells the player *how
much to trust the number in front of them* - and that fits in one short line.

### Always in the tooltip

- Name, `Rank x/y`, `Capstone` badge.
- Description at the current rank (rank 0 shows rank 1), `Next rank:` block.
- Requirement line when locked, red, ending in a period, never naming an
  internal id.
- **At most one amber trust line**, max ~60 characters, chosen by priority:
  1. `Ranks 2-5 estimated.` (anticipated ranks)
  2. `Only rank 1 is known.` (manual / unknown higher ranks)
  3. `Uncertain reading - check.` (confidence < 0.8)
  Never two amber lines at once; never the raw `ranksSource` enum.
- A `Details` affordance next to the trust line, only when meta exists.

### Behind the details toggle (click, not hover)

- The derivation in plain words: `Rank 1 (23%) was read from stream; ranks
  2-3 are rank 1 multiplied by the rank, the way the Classic talent scales.`
- The rounding caveat, reworded: `Rank 2 may read 45 in game; we show the
  unrounded 46.`
- Reading confidence and stream timestamp as a single line: `Read from stream
  at 4:09:33, 70% confidence.`
- `source.note` when present, verbatim - it is the most useful sentence we
  have and it is currently invisible.

### Review page only (`#/review/<class>`)

- Classic talent ids, tree paths, similarity scores, `cross-class`, reader
  model and quantisation, crop paths, second-reader diffs, `needs manual
  ranks`, `has no alignable slots`, `ranks 2..5 are copies of rank 1`, the raw
  `{0}` slot labels, `frame` indexes.

### Wording rules

- Units: `sec`, `min`, `yards`, `%` - never `secs`, `seconds`, `yds`. One
  unit vocabulary per sentence.
- Say `estimated`, not `anticipated`/`extrapolated`/`classic-prior`.
- Ranges are `2-3`, never `2+`; name the ranks that exist (`Rank 2
  estimated.` when max rank is 2).
- Sentence case in prose; capitalise only game terms (Combo Point, Rage,
  Bear Form, spell and ability names).
- Every visible line ends in a period, requirement lines included.
- No parentheses containing an identifier (`(classic-prior)`, `(talent 23)`,
  `(page primary)`).
- Percentages that are chances are capped at 100% before display.
- Never show `confidence 100%` - certainty is the default; only doubt is
  worth a word.
- Global caveats are stated once, on the picker; the class page and the
  tooltip must not repeat them.

### Budget

Meta text (trust line + any provenance) should not exceed **one line at 300px
(~45 characters)** by default, and never exceed the description's own length.
Today 70% of tooltips break that budget; applying the rules above brings
every one of the 469 under it.

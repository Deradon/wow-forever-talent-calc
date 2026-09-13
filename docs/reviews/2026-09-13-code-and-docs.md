# Code and docs review, 2026-09-13

Reviewer: fresh session, read-only except this file. Scope: `web/src`,
`pipeline/src/wowtalents`, `pipeline/stages`, `pipeline/scripts`, both test
suites, `.github/workflows`, and the docs (`CLAUDE.md`, `README.md`,
`docs/PLAN.md`, `docs/DATA-SCHEMA.md`, `docs/briefs`, `docs/handover`,
`pipeline/README.md`, `web/README.md`).

Severity: **critical** = ships wrong data or breaks users; **high** = will
cause a wrong result or a wasted session soon; **medium** = maintainability
debt with a concrete failure mode; **low** = tidy-up.

## Top findings, in the order I would fix them

| # | Severity | Finding |
|---|---|---|
| 1 | critical | Five stages rewrite `data/extracted/<class>.candidates.json` with a truncating `write_text`; an interrupt destroys hours of VLM reads (E1). |
| 2 | high | The published encoding `v1.json` was rewritten three times, shifting digit positions in nine trees; build links shared earlier now decode to different talents, silently (A1). |
| 3 | high | Three slug implementations, two of which neither collapse punctuation runs nor normalise accents (E2). |
| 4 | high | `05_read.py --add` re-reads and duplicates cells whose tree display name is missing from the `trees` block (E3). |
| 5 | high | `04_hovers` exits 0 after decoding zero frames; `03_calibrate` exits 2 with no message (E4). |
| 6 | high | `CLAUDE.md` is wrong about `tools/`, about URL encoding living in `web/src/rules/`, and about what the pipeline writes; and it carries no current state and no encoding-immutability rule (D1, section 7). |
| 7 | medium | CI runs neither the pipeline tests nor `validate.py` before deploying data — both together cost under six seconds (B1). |
| 8 | medium | `docs/PLAN.md`'s "Immediate next actions" is Phase-0 vintage; a fresh session that obeys it does archaeology (D2). |
| 9 | medium | `docs/DATA-SCHEMA.md` contradicts the code in five places, including a decoder path and a review workflow that do not exist (D3, D4). |
| 10 | medium | 430 orphaned PNGs (1.5 MB) are globbed into the bundle and deployed; 13 handovers have no index (C4, D5). |

## 0. Baseline: everything green, everything fast

| Suite | Command | Result | Wall |
|---|---|---|---|
| pipeline | `uv run pytest` (in `pipeline/`) | 171 passed | 4.5 s (5.1 s incl. uv) |
| web unit | `npx vitest run` (in `web/`) | 81 passed, 7 files | 2.5 s (3.1 s incl. npx) |
| web types | `npx tsc -b` | clean | ~3 s |
| web lint | `npx oxlint` | 0 errors, 3 warnings | <1 s |
| validator | `uv run python validate.py --check ../data/talents/*.json` | 0 errors, 133 warnings, 138 info, exit 0 | 0.6 s |

The three oxlint warnings are `react(set-state-in-effect)` at
`web/src/ui/ClassPage.tsx:34` and `web/src/ui/ReviewPage.tsx:24`, and
`react(refs)` at `web/src/ui/TalentCell.tsx:99`. All benign; they are the
reason `npm run lint` is worth wiring into CI only after they are addressed
or downgraded.

Everything cheap enough that there is no excuse for CI not running all of it
(finding B1).

## 1. Correctness

### A1 — Published encoding version v1 was mutated in place; shared build links silently decode to different talents — **high**

`data/encoding/README.md:21` ("A version file is immutable once merged to
`main`") and `docs/DATA-SCHEMA.md` section 8 ("an encoding file is immutable
once merged to `main`") state the invariant. Git says it was broken three
times:

```
68b1f7b data: JSON schema, encoding v1, example class and Classic Era prior   (v1 created: tinker only)
6ccdab0 pipeline: tooltip reader ... Paladin extracted                        (v1 rewritten)
3facc32 data: publish all nine classes                                        (v1 rewritten)
797fb2e data: 34 recovered talents merged, 468 of 470 live                    (v1 rewritten)
f1db0f6 data+pipeline: Healing Light and Hot Streak recovered                 (v1 rewritten)
```

The last two rewrites *inserted* recovered talents into the middle of
`order[<tree>]`, shifting every digit after them. Diffing `3facc32` against
`f1db0f6`:

```
mage/arcane:              pos  1 was 'improved-channeling'       now 'arcane-focus'        (len 16->18)
mage/fire:                pos  4 was 'master-of-elements'        now 'impact'              (len  7->16)
paladin/holy:             pos  3 was 'spiritual-focus'           now 'healing-light'       (len 15->18)
paladin/retribution:      pos  1 was 'vindication'               now 'benediction'         (len 14->18)
rogue/assassination:      pos 12 was 'mutilate'                  now 'vigor'               (len 15->17)
rogue/combat:             pos  2 was 'puncturing-wounds'         now 'lightning-reflexes'  (len  9->17)
shaman/elemental-combat:  pos  1 was 'elemental-warding'         now 'concussion'          (len 13->16)
warlock/demonology:       pos  2 was 'unholy-power'              now 'demonic-embrace'     (len 18->19)
warrior/fury:             pos  7 was 'dual-wield-specialization' now 'boundless-rage'      (len 16->18)
```

Nine trees across seven classes. Every `#/paladin?v=1&t=...` link that was
copied from the site between those commits now points at different talents,
and it does so **silently**: the digits are still in range, so
`decode` (`web/src/url/codec.ts:59-75`) produces a perfectly valid build with
no notice. This is exactly the failure the version mechanism exists to
prevent.

Two things let it happen:

1. `pipeline/stages/08_export.py --update-encoding` upserts the class into
   "the highest `v<N>.json` while that version is unpublished"
   (`pipeline/README.md:166-168`) — but nothing checks that "unpublished" is
   still true. It was published on 2026-09-13 with the Paladin deploy.
2. `validate.py` rule 11 (`docs/DATA-SCHEMA.md` section 10) only checks that
   the class's *current* talent id set equals the version's `order` sets. A
   file that was rewritten to match the new data passes by construction.

Fix, in order:

- Freeze `data/encoding/v1.json` as it stands (rolling back would break the
  links minted most recently, which are the ones people actually hold).
- Create `data/encoding/v2.json` covering all ten classes and an (empty)
  `data/encoding/migrations/v1-v2.json`, set `dataVersion: 2` in all nine
  class files and in `data/examples/tinker.json`, and do this *before* the
  next data change rather than after it.
- Correct the `note` in `v1.json` and `data/encoding/README.md:33-39`, which
  both still claim v1 holds only `tinker` (finding D4).
- Make `--update-encoding` refuse when the target version file is already
  reachable from `origin/main`, and add a validator rule that compares each
  `v<N>.json` against its committed ancestor (or a checksum file) so a
  rewrite fails loudly.
- Add the regression test in B3.5.

### A2 — `decode` does unbounded work and builds an unbounded notice from a hostile link — **medium**

`web/src/url/codec.ts:66-75` iterates `segment.length`, not
`min(segment.length, ids.length)`, and pushes one string into `unknown` for
every surplus non-zero digit:

```ts
for (let j = 0; j < segment.length; j++) {
  ...
  if (id === undefined) { if (digit > 0) unknown.push(`${treeId} #${j + 1}`); continue }
```

`#/paladin?v=1&t=` + a megabyte of `9`s produces ~10^6 entries that are then
joined into one notice string (`codec.ts:77`) and rendered into the DOM
(`web/src/ui/Notice.tsx:162`). The `violations` list in the same component is
already capped at 8 (`Notice.tsx:165`); `unknown` and `missing`
(`codec.ts:112-113`) are not. Fix: stop the loop at `ids.length`, count the
surplus, and report `Ignored N points for talents this class does not have`
with at most a handful of names. Cheap, and it also removes the only
user-reachable quadratic-ish path in the app.

### A3 — Requirement wording is computed twice, in the rules engine and in the UI — **medium**

`web/src/rules/mutate.ts:30` and `:35` build human strings inside the pure
rules layer:

```ts
return { ok: false, reason: 'row-locked', detail: `${needed} points in ${tree.name}` }
...
return { ok: false, reason: 'prereq', detail: `${req.rank} point${req.rank === 1 ? '' : 's'} in ${target?.name ?? req.talent}` }
```

and `web/src/ui/Tooltip.tsx:181-195` re-derives the same two sentences from
scratch (`Requires ${cls.rules.pointsPerRow * talent.row} points in
${tree.name} Talents`, `${r.rank} point${r.rank === 1 ? '' : 's'} in
${target?.name ?? r.talent}`). The tooltip never uses `verdict.detail`. Two
consequences: the strings can drift (they already differ — "5 points in Holy"
vs "Requires 5 points in Holy Talents"), and the `detail` field is dead weight
carried through `Verdict` for the prereq/row-locked cases.

Fix: either make the tooltip render `verdict.detail`, or (better, keeps the
rules layer presentation-free) change `detail` to structured data
(`{ needed: number }` / `{ talentId, rank }`) and keep all wording in
`Tooltip.tsx`. The `Reason` union already carries the semantics.

### A4 — The `moved` migration branch is unreachable, and `removed`/`moved` are untested — **medium**

`web/src/url/codec.ts:86-89` resolves a `moved` entry and stores
`moved.to` as the talent's tree:

```ts
const moved = m.moved?.[newId] ?? m.moved?.[id]
next.set(newId, { treeId: moved ? moved.to : entry.treeId, rank: entry.rank })
```

but step 3 immediately discards it: `codec.ts:99` looks the talent up by id
across *all* trees first and only falls back to `entry.treeId`:

```ts
const tree = cls.trees.find((t) => findTalent(t, id)) ?? findTree(cls, entry.treeId)
```

Since talent ids are unique per class file (`docs/DATA-SCHEMA.md` section 3,
enforced by `web/src/data/validateData.test.ts:61` and validator rule 5), the
first branch always wins and `moved` changes nothing. That is defensible —
but then the `moved` machinery is dead code that a future reader will trust.
Either delete it and document "moves need no migration entry because ids are
unique per class", or make step 3 honour `entry.treeId` first.

Worse, none of it is tested: `web/src/url/codec.test.ts:50` covers `renamed`
only. `removed` (`codec.ts:86`) has no test at all, so a typo there would ship.

### A5 — Dead unreachable branch in `encode` that would silently mint an empty link — **low**

`web/src/url/codec.ts:27-28`:

```ts
const order = orderFor(registry, cls, cls.dataVersion)
if (!order) return ''
```

`orderFor` (`web/src/data/encoding.ts:64-69`) falls back to `derivedOrder(cls)`
whenever `version === cls.dataVersion`, which is exactly what `encode` passes,
so the branch cannot fire. If it ever could, the user would get a share link
with an empty build and no warning. Delete the branch, or throw.

### A6 — `sanitize` can return an invalid build without saying so — **low**

`web/src/rules/mutate.ts:105-127`: the `for (let guard = 0; guard < 10_000; guard++)`
loop simply falls out when the guard is exhausted (and at `:123` when `last`
is undefined), returning `current` and whatever `dropped` accumulated. The
caller (`codec.ts:121`) treats the result as valid. Practically unreachable,
but a one-line `if (validate(cls, current).length > 0)` post-condition — throw
in dev, empty build in prod — turns a silent wrong answer into a loud one.

### A7 — Row gating counts "points in rows above", Classic counts points in the tree — **low, but document it**

`web/src/rules/points.ts:16` (`pointsInRowsAbove`, rows `< row`) implements
exactly what `docs/briefs/web-app.md:139` specifies, so the code is not wrong
against its spec. It differs from live WoW, where the gate is the tree total
including the current and lower rows. The two agree for every build reachable
by clicking; they diverge only for builds that arrive through a link with
points already below the gate, where this implementation is stricter and
`sanitize` will drop points a real client would keep.
`rules.rulesSource` is `assumed` for all nine classes, so this is an open
assumption, not a bug. Record it in `docs/DATA-SCHEMA.md` section 4.1 next to
`pointsPerRow` so the next reviewer does not have to rediscover it.

### A8 — `maxLevel` is validated but never used; `requiredLevel` is unclamped — **low**

`web/src/rules/level.ts:4` returns `firstPointLevel - 1 + total` with no cap.
`rules.maxLevel` is read in exactly one place in the whole app —
`web/src/data/validateData.test.ts:48` — and never by `Header.tsx:62`, which
displays the number. With the current data (`10 - 1 + 51 = 60 = maxLevel`)
they coincide, so nothing shows; a future class with a smaller `maxLevel`
would display an impossible level. One line: `Math.min(rules.maxLevel, ...)`,
or delete `maxLevel` from the schema if nothing is meant to use it.

## 2. Tests

### B1 — CI runs neither the pipeline tests nor the data validator before deploying — **medium**

`.github/workflows/deploy.yml:28` is the whole test story:

```yaml
      - run: npx vitest run && npm run build
```

So the deploy job publishes `data/talents/*.json` — 469 talents, the actual
product — without ever running `pipeline/validate.py`, which is the tool
`docs/DATA-SCHEMA.md` section 6.3 promises CI runs ("CI runs `validate.py`
and rejects a canonical file that does not round-trip through `export.py`").
It also never runs the 171 pipeline tests. Both cost together under six
seconds (section 0). A hand edit to a class file that breaks rule 6, 8 or 11
would reach Pages; only the Zod-level subset in
`web/src/data/validateData.test.ts` would catch it.

Concrete fix — add before the build step:

```yaml
      - uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }
      - run: uv sync --frozen
        working-directory: pipeline
      - run: uv run pytest -q
        working-directory: pipeline
      - run: uv run python validate.py --check ../data/talents/*.json
        working-directory: pipeline
```

`--check` is the byte-equality rule 12 and passes today, so it can go in
strict from day one.

### B2 — The Playwright suite was written for a CI that does not exist — **medium**

`web/playwright.config.ts:31-32` branches on `process.env.CI` for retries and
the `github` reporter, and `web/tests/paladin.spec.ts` (66 lines) plus
`web/tests/smoke.spec.ts` (104 lines) assert real user-visible behaviour
(crop icons decoding, per-tree points in the document title, the review
route). Nothing runs them. `docs/briefs/web-app.md:105-106` says "Playwright
runs in a separate, non-blocking job later" — "later" has arrived; the app is
public. Add a non-blocking job (`continue-on-error: true` at first) with
`npx playwright install --with-deps chromium` and `npm run e2e`.

Note while you are there: `paladin.spec.ts:23` asserts
`[data-talent][data-icon="initials"]` has count 0. Since the icon commit
(`de7f059`) 397 talents load `public/icons/<name>.jpg`, and
`TalentCell.tsx:50` falls back to initials on an `onError`, so this assertion
now depends on 312 JPEGs decoding in the preview server. It should still
pass, but it is the first thing that will go red when the suite is switched
on — expect it, do not "fix" it by weakening the assertion.

### B3 — Test gaps, in the order I would close them

The spec table in `docs/briefs/web-app.md:166-185` (cases 1-18) is fully
implemented across `web/src/rules/rules.test.ts` and
`web/src/url/codec.test.ts` — that part is genuinely good. The gaps are the
branches nobody specified:

1. **Hostile-input property test for `decode`.** Today case 17
   (`codec.test.ts:68-92`) only round-trips builds produced by legal clicks.
   Add `fc.stringMatching(/^[0-9-]{0,60}$/)`: `decode` must not throw,
   `validate(cls, decoded.build)` must be `[]`, and
   `encode(cls, decoded.build)` must be a fixed point. That single test
   covers A2, A5, A6 and every clamping path at once.
2. **Migration `removed` and `moved`** (`codec.ts:86-89`) — see A4. The
   fixture already has a v1→v2 migration (`web/src/rules/fixture.ts:95`);
   extend it with a removed id and a moved id.
3. **`cellState` has no test at all** (`web/src/ui/cellState.ts`), and it
   decides how every cell in the app looks, including the deliberate
   "out of points keeps the colour" rule at `cellState.ts:11`. Four
   assertions.
4. **Route edge cases** (`web/src/url/route.test.ts` is 21 lines): `?v=abc`
   (→ `NaN` → `unknown-version` notice), `?v=` (→ `Number('') === 0` → also
   a notice, with a confusing message), `#/review/Warrior` (bad slug →
   `unknown`), `buildHash({kind:'unknown'})`.
5. **An encoding-immutability regression test** (A1): for every
   `data/encoding/v<N>.json`, assert the file is unchanged against a
   committed checksum, and that every class in `data/talents/` appears in the
   highest version with its exact id set. This is the test whose absence cost
   the project its v1 links.

On the Python side the corresponding gaps are in section 5.

## 3. Duplication, dead code, scratch leftovers (web + data)

### C1 — Two copies of the tinker example that have already drifted — **medium**

`data/examples/tinker.json` and `web/tests/fixtures/tinker.json` are the same
file except for five `spellIds` (19407-19415 vs 12960-12964). Both are loaded
by the app (`web/src/data/load.ts:13-14`, `examples` wins by precedence) and
both are validated by `web/src/data/validateData.test.ts:15-19`, so the drift
is invisible. `web/src/url/codec.test.ts:7` imports the fixture copy;
`web/src/data/schema.test.ts:13` imports the fixture copy too. Delete
`web/tests/fixtures/tinker.json` and import `../../../data/examples/tinker.json`
in both tests (the Vite `fs.allow: ['..']` in `vite.config.ts:9` already
permits it).

### C2 — The encoding fixture is a strict subset of the real file, and the machinery that merges it is dead — **low**

`web/tests/fixtures/encoding/v1.json` contains only `tinker`, byte-identical
to the `tinker` entry now inside `data/encoding/v1.json`. Since
`buildRegistry` keeps the first file per version (`encoding.ts:54`,
`versions[f.version] ??= f`) and the real glob is listed first
(`encoding.ts:103`), the fixture can never win. So the fixture, the
`import.meta.glob` at `encoding.ts:95`, the `includeExamples` export at
`encoding.ts:97` and the doc comment at `encoding.ts:5-8` all exist for
nothing. Remove them (keep the fixture only if C1 is resolved the other way).

### C3 — Small duplications and one unused export — **low**

- `includeExamples` is exported from two modules with identical bodies:
  `web/src/data/load.ts:16` and `web/src/data/encoding.ts:97`.
- The slug regex exists twice: `web/src/data/schema.ts:12` (exported as
  `SLUG`, imported by nobody) and `web/src/url/route.ts:11` (a private copy).
  Import the one from `schema.ts`.
- `ClassOrder` (`encoding.ts:43-46`) is field-for-field identical to
  `EncodingClass` (`encoding.ts:13-16`). One of them is redundant.
- `emptyBuild()` (`web/src/rules/points.ts:65`) has no callers anywhere;
  `resetAll()` (`mutate.ts:85`) does the same thing and is used.

### C4 — 430 orphaned PNGs (1.5 MB) are globbed into the bundle and deployed — **medium**

`data/review/` holds 971 PNGs (18.3 MB); the nine class files reference 541
of them. The other 430 are 398 `<talent>.icon.png` files for talents that
stage 9 later switched to `iconSource: "classic"` (so their `iconCrop` is
gone), 28 `_header.png` tree strips that no class file has ever referenced,
and 4 others. `web/src/data/crops.ts:10` globs `data/review/*/*/*.png`
eagerly, so all 971 become entries in the bundle's path map and all 971 are
emitted into `dist/assets/` — the 430 orphans included. Nothing detects them:
`crops.test.ts` only checks the other direction (every referenced crop is
shipped).

Fix: a cleanup step in stage 9 / stage 8 `promote` that deletes crop files no
class file references any more (the tooltip crops in `source.crop` must stay —
they are the provenance), and an inverse assertion in `crops.test.ts`
(`cropCount()` equals the number of referenced paths) so it cannot silently
regrow.

### C5 — Dangling comment in the deploy workflow — **low**

`.github/workflows/deploy.yml:32`:

```yaml
        env:
          VITE_BASE: /${{ github.event.repository.name }}/
          # Ship the example class until the first real class lands in data/talents/; then remove.
```

The `VITE_INCLUDE_EXAMPLES: '1'` this comment explained was deleted in
`d2ff0df`; the comment stayed behind, now sitting under `env:` describing
nothing. Delete it.

Otherwise the web tree is clean: no `TODO`/`FIXME`/`XXX`/`HACK`, no
`console.log`, no `@ts-ignore`, no commented-out blocks, no scratch files, and
`web/public/icons/` is exactly the 312 icons the data references — no orphans,
no misses.

## 4. Docs

### D1 — `CLAUDE.md` has drifted on layout, on where the rules live, and on what a fresh session should do — **high**

Details and a proposed replacement in section 7.

### D2 — `docs/PLAN.md`'s "next" section is three phases out of date and the status log is out of order — **medium**

`docs/PLAN.md:118-128`, "Immediate next actions (in order)", still says:

> 1. Confirm the download finishes and merges …
> 3. Workstream B: write `data/schema/class.schema.json` and `validate.py`
>    first, since both other streams depend on it.

All three items are Phase-0 vintage and long done; the schema and validator
have existed since `68b1f7b`. A fresh session that follows `CLAUDE.md:16`
("Read `docs/PLAN.md` first") and then obeys the section labelled *immediate
next actions* will do archaeology instead of work. The real next step is
buried in the status log at `:170` ("owner review of the 79 flagged talents,
then Phase 2b (races)").

Also:

- "Fast path while the download runs" (`:106-116`) describes a download that
  finished twelve hours ago and a VRAM measurement that has been made.
- The status log (`:158-221`) is not in any consistent order: it runs
  15:00, 06:40, 06:00, 03:45, **evening**, 03:30, 01:30, **02:15**, 00:27,
  00:50. The "~evening" entry at `:187` also duplicates the "~03:45" entry
  at `:181` (both describe "Phase 2 extraction done, 434 of 470").
- `:144` still lists "Total talent points and points-per-row in Forever
  (assume 51 and 5)" as open — correct, and worth keeping, but it should
  cross-reference `rulesSource: "assumed"` in the data so a reader knows the
  assumption is already encoded in all nine files.

Fix: replace "Immediate next actions" with the current three (owner review of
the 79 flagged talents via `#/review/<class>`; bump the encoding to v2 per
A1; Phase 2b races), collapse the duplicate log entry, and sort the log
newest-first.

### D3 — `docs/DATA-SCHEMA.md` contradicts the code in five places — **medium**

| Doc | Says | Reality |
|---|---|---|
| §8, decoder paragraph | "Decoder in `web/src/rules/encoding.ts` … then run `validateTree`" | `web/src/data/encoding.ts` (registry) + `web/src/url/codec.ts` (decoder); the functions are `validate` / `sanitize` (`web/src/rules/validate.ts:8`, `mutate.ts:96`). There is no `validateTree` and no `web/src/rules/encoding.ts`. |
| §6.1 | "Written by `pipeline/10_export`" | `pipeline/stages/08_export.py`. There is no stage 10. |
| §7 step 3 | "Reviewer opens the review UI (`tools/review/`, or the hidden `/review/<class>` route)" | `tools/` does not exist. `#/review/<class>` exists (`web/src/ui/ReviewPage.tsx`), is linked from the class picker (not hidden), and is **read-only** — it writes no overrides. |
| §7 closing + §6.2 | Reviewing writes `data/overrides/<class>.json`; "there is no other way to mark a talent reviewed" | `data/overrides/` is an empty directory (no override file for any class) and 0 of 469 talents are `reviewed: true`. The documented review loop has no implementation, which is precisely why the review backlog (79 talents) has not moved. |
| §6.3 step 4 | "CI runs `validate.py` and rejects a canonical file that does not round-trip" | CI runs neither (B1). |

Also `§9` describes `pipeline/import_db2.py`, which does not exist yet —
fine, but mark the section "planned" so a reader does not go looking.

What I checked and found **consistent** (no action):

- `iconSource` enum `classic | crop | datamined | manual` in §4.4 matches
  `web/src/data/schema.ts:67` and the data uses only `crop` (72) and
  `classic` (397).
- `requires` is `{talent, rank}` everywhere — all 67 entries in
  `data/talents/*.json`, `schema.ts:44-47`, `mutate.ts:32-36`,
  `validate.ts:39-43`, `Arrows.tsx:17-20`. No `points` spelling anywhere.
- `maxRank` 1..9 (§4.4) matches `schema.ts:65` and is asserted by
  `schema.test.ts:48`.
- The encoding string rules in §8 (one digit per talent, trailing zeros
  trimmed per tree, trees joined by `-`, trailing empty trees omitted) match
  `codec.ts:29-35` exactly, and `web/README.md:407` documents the same.
- `iconCrop` present iff `iconSource == "crop"` (§4.4 / rule 9) is enforced
  by `validateData.test.ts:76` and holds in the data.

### D4 — `data/encoding/README.md` and `v1.json`'s own `note` describe a file that no longer exists — **medium**

`data/encoding/README.md:33-39` ("Current state"):

> `v1.json` (2026-09-13): only the fictional `tinker` example class … Real
> classes are added as they pass review; the first real class bumps to
> `v2.json`

and `data/encoding/v1.json`'s `note` field says the same. In fact v1 now
contains all nine real classes plus `tinker`, and no class has passed review.
This is the documentation half of A1 — and note the irony: the README
correctly prescribed the bump to v2 that was never done.

### D5 — 13 handovers, no index — **medium**

`docs/handover/` holds 13 files, all `2026-09-13-*.md`, 40 to 319 lines each.
`docs/handover/README.md` is a four-line *template* ("One file per session …
1. What was done …"), not an index. Nothing lists which handover covers what,
so finding "where is the rank-scaling rule explained" means `ls` plus
guessing — even though `pipeline/README.md:140` and `docs/DATA-SCHEMA.md`
section 5 both cross-reference `2026-09-13-rank-scaling.md` by name.

Fix: append a table to `docs/handover/README.md` — date, file, one line of
"what state this passes on", newest first. It costs ten minutes and it is the
single highest-leverage doc change after `CLAUDE.md`.

Gap while you are there: there is **no handover for web M2** (class picker,
review route, crop icons, titles — commit `035bc37`) or for the web side of
the icons/prerequisites work. `2026-09-13-web.md` stops at M1. Everything the
web app gained since exists only in commit messages and the PLAN status log.

### D6 — `docs/briefs/web-app.md` §5 shows a superseded encoding shape — **low**

`docs/briefs/web-app.md:198-200` documents

```
data/encoding/v3.json: { "version": 3, "classes": { "warrior": { "arms": [...], "fury": [...] } } }  tree order = key order
```

while `docs/DATA-SCHEMA.md` section 8, `data/encoding/README.md:9` and
`web/src/data/encoding.ts:13-23` all use `{ trees: [...], order: { ... } }`.
`docs/PLAN.md:34-35` already declares that the schema wins when a brief
disagrees, so this is not ambiguous — but a one-line "superseded by
DATA-SCHEMA §8" note in the brief saves the next reader the cross-check.
The rest of the brief is accurate: the folder structure at `:108-129` matches
the repo exactly (including `url/codec.ts`, which is what `CLAUDE.md` gets
wrong), and the rules API at `:140-150` matches the implementation.

### D7 — Root `README.md` still says "bootstrapping" — **low**

`README.md:7`: "Status: **bootstrapping** – see `docs/PLAN.md`". Nine classes
and 469 talents are live on Pages. Same file, `:22`: "Tooling is documented
per subfolder once it exists" — it exists; link `pipeline/README.md` and
`web/README.md` directly. This is the first file a stranger reads.

### D8 — `pipeline/README.md` references paths that do not exist — **low**

`pipeline/README.md:135` (`data/overrides/<class>.json`), `:251`
(`data/icons/verified.json`) and `:243` (`work/icons/lists/`, git-ignored).
None exist in the tree. The commands still work (they treat the files as
optional), but a reader cannot tell "not yet used" from "you deleted it".
Mark them "(optional; none exist yet)".

Otherwise `pipeline/README.md` is in good shape — I spot-checked the stage
CLIs and they match the documented commands (`uv run stages/08_export.py
--help` lists exactly `extract` / `promote` / `all`). Note that all `uv run`
examples assume cwd `pipeline/`; `uv run --directory pipeline ...` from the
repo root is the form that always works and is worth adding once at the top.

## 5. Python pipeline

The Python side is in better shape than its size suggests: no `TODO`/`FIXME`/
`XXX`/`HACK` markers anywhere in `stages/`, `scripts/`, `src/` or
`validate.py`; every stage carries a real module docstring with runnable
examples; `06_rankfill.fill`, `04_hovers.finish`, `07_arrows._merge` and
`icons.apply_matches` are correctly idempotent and are the pattern to copy.
What follows are the gaps.

### E1 — Five stages destroy the candidates file with a truncating write — **critical**

`data/extracted/<class>.candidates.json` is the most expensive artefact in the
repo (hours of VLM reads). Five code paths overwrite it with a plain
`Path.write_text`, which truncates before it writes:

```
pipeline/stages/05_read.py:380      dest.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", ...)
pipeline/stages/06_rankfill.py:111  dest.write_text(...)
pipeline/stages/07_arrows.py:154    cand_path.write_text(...)
pipeline/stages/09_icons.py:397     path.write_text(...)
pipeline/scripts/second_opinion.py:118  src.write_text(...)
```

Ctrl-C or an exception between truncate and flush leaves a half-written or
empty JSON and there is no backup. `export.write_validated`
(`pipeline/src/wowtalents/export.py:636-651`) already does it correctly — temp
file, validate, `os.replace` — so the pattern exists; it just is not reused.

Fix: put `write_json_atomic(path, text)` (temp file in the same directory +
`os.replace`) in `wowtalents` and use it at those five sites plus
`03_calibrate.py:182`, `04_hovers.py:184`, `04b_hovers_mkv.py:185`,
`07_arrows.py:90`, `09_icons.py:336` and the six write sites in
`scripts/cursor_recover.py`.

Related (**high**): of the four stages that rewrite the candidates file, only
stage 8 validates before writing. `07_arrows.py:126-154` pops
`requires_arrows` off every record and writes the result even when
`stats["unmatched"]` is non-empty; `09_icons.py:390-397` and
`06_rankfill.py:98-111` write unconditionally. At minimum, refuse to write
when the record count shrank.

### E2 — Three different slug implementations, two of them wrong — **high**

| Where | Behaviour |
|---|---|
| `pipeline/src/wowtalents/ranks.py:86` | The DATA-SCHEMA section 3 rule: NFKD, strip combining marks, drop apostrophes, collapse `[^a-z0-9]+` runs. Correct. |
| `pipeline/src/wowtalents/ui.py:801` | `"".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")` — does **not** collapse runs and does **not** normalise accents. `"Anti-Magic  Shell"` → `anti-magic--shell`. |
| `pipeline/src/wowtalents/reader.py:277` | `ui.slug`'s body inlined verbatim. |

Stage-4 crop filenames and stage-5 record ids use the naive one; export ids
use the strict one. Any talent name with a punctuation run, a double space or
an accent produces two different slugs for the same talent — which is exactly
the class of bug that produced the "Master of Elements id collision" in
`docs/PLAN.md:178`. Fix: one `slug` (the `ranks.py` implementation) in a new
`wowtalents/text.py`; the other two become imports.

### E3 — `05_read.py --add` can read and append the same cell twice — **high**

`pipeline/stages/05_read.py:233`:

```python
have = {record_key(r, tree_index) for r in existing.get("candidates") or []} - {None}
```

and `record_key` (`:137-142`) returns `None` whenever a record's `tree`
display name is not a key of the existing `trees` block. Those records are
silently excluded from `have`, so their cells are re-read and appended a
second time. This is reachable: stage 5 itself warns that tree display names
differ between segments (`:263`), and with an absent `trees` block *every*
record duplicates. `export.dedupe` does not save it — it keys on the tree
string, so the duplicates land in two different trees.

Fix: key on `(page, row, col, slug(tree))` with a fallback to `source.cell`
(stage 5 already writes it, `reader.py:308`), and refuse the run when any
existing record cannot be keyed. Related (**medium**): `additive_merge`
(`:162-166`) appends an `additions` entry and rewrites `generated_at` even
for a no-op run with `records == []`.

### E4 — Two failure modes exit silently or exit 0 — **high**

- `pipeline/stages/03_calibrate.py:60-61`: `if not stack: raise typer.Exit(code=2)`
  with no message at all. A segment whose fragments decode to zero frames
  fails with an empty terminal.
- `pipeline/stages/04_hovers.py:225-256` has no zero-frame guard, while
  `04b_hovers_mkv.py:175-177` does (`if n_frames == 0: … Exit(1)`). If ffmpeg
  fails — and `ui.decode_frames:143-144` never checks `proc.returncode` —
  stage 4 writes a hovers JSON containing zero hovers and **exits 0**. Stage 5
  then reports every cell of the segment as never hovered, with no clue why.
  That is plausibly one of the causes the missing-cells forensics
  (`docs/handover/2026-09-13-missing-cells-forensics.md`) had to chase.

Fix: a message before every `Exit`, mirror 04b's guard in 04, and raise from
`decode_frames` when ffmpeg returns non-zero. While there:
`04_hovers.py:218` / `04b:131` never `None`-check `cv2.imread` of the median,
so a missing PNG surfaces as a numpy shape error deep inside `ui.diff_mask`.

### E5 — Every stage prints errors to stdout; three logging conventions — **medium**

There is no logger anywhere in the tree. Stages use `typer.echo` (stdout),
`validate.py` uses `print()` (`:1117-1123`), `export.py` has its own `Log`
dataclass (`:58-72`). `typer.echo(..., err=True)` is used **nowhere**, so
failures such as `04_hovers.py:214` ("no calibration at …" before `Exit(2)`)
go to stdout — and `scripts/run_class.sh:47` pipes stage output through
`grep -v`, which only happens to be safe today. Prefixes are split between
uppercase `WARNING`/`INFO`/`ERROR` (export, validate — these have machine
consumers) and lowercase `warn:` / `note:` / `conflict:` / `ABORT` (stages).
Exit codes are overloaded: `1` means both "empty result"
(`00_probe_live.py:165`, `04b:177`) and "validation failed"
(`08_export.py:114`), `2` = missing prerequisite, `3` = external abort.

Fix: errors through `err=True`, one prefix convention (the uppercase one), and
three documented exit codes in `pipeline/README.md`.

### E6 — CLI conventions diverge across the nine stages — **medium**

- **Class argument, three spellings**: positional `cls` (05-09,
  `second_opinion`), `--class` option (`scripts/cursor_recover.py:641`), and
  `04b_hovers_mkv.py:100-104` takes `cls` positionally but its equally
  required `--calib/--start/--end` as options.
- **Output flag, three spellings**: `--out` (`00:117`, `05:199`, `06:89`),
  `--out-dir` (`03:129`, `04:206`), and none at all in 07/08/09 — exactly the
  stages that rewrite the candidates file in place.
- **`--dry-run`** exists on 05, 06, 08, 09 and `second_opinion` but not on
  `07_arrows merge`, which mutates the candidates file in place
  (`07_arrows.py:154`).
- **Sub-commands** are split four ways: verbs (`00`, `07`, `08`, `09`), a
  contentless `run` (`03`, `04`, `04b`, `05`), and none (`06`,
  `second_opinion`, `cursor_recover`). `no_args_is_help=True` is missing on
  those last three (`06:44`, `cursor_recover:50`, `second_opinion:34`).
- `08_export.py:139`: `all_` calls `_extract` with eleven positional
  arguments and silently drops `--candidates`, `--tree-order`, `--video`,
  `--fps`, `--no-copy` and `--dry-run` that `extract` offers. Make the tail
  keyword-only.

Also **medium**: `validate.py` is the only argparse CLI (deliberate — it is
meant to be stdlib-only), and `export.py:623-626` bridges to it by
constructing a fake `argparse.Namespace`. Adding one option to validate's
parser breaks `write_validated` with an `AttributeError`. Give `validate.py` a
`ValidateOptions` dataclass that both `main()` and `run_validator` build.

Footnote on the docstring: `validate.py:4-5` claims "needs only the standard
library plus `jsonschema`", but rule 15 uses `rapidfuzz`, which is a hard
dependency in `pyproject.toml:19`, and its 25-line difflib fallback
(`validate.py:279-299`) is therefore dead. Delete the fallback or fix the
claim.

### E7 — The `sys.path.insert` preamble is repeated 22 times and is redundant — **medium**

Every stage (`00:27`, `03:29`, `04:36`, `04b:35`, `05:38`, `06:37`, `07:38`,
`08:31`, `09:37`), `scripts/cursor_recover.py:46`, `export.py:42` and eleven
of twelve test files carry:

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wowtalents import ... # noqa: E402
```

It is unnecessary: `pipeline/.venv/lib/python3.12/site-packages/wowtalents.pth`
already contains `/…/pipeline/src` (verified), which is why
`pipeline/tests/test_fragments.py` imports `wowtalents` with no preamble and
passes. Worse, `export.py:42` mutates `sys.path` **at import time inside a
library module** so that `import validate` resolves — every consumer of
`wowtalents.export` inherits the mutation. Delete all 22; for `validate`,
either move it to `src/wowtalents/validate.py` with a three-line shim at
`pipeline/validate.py`, or add a second `.pth` entry.

### E8 — Other duplicated logic — **medium/low**

| What | Where |
|---|---|
| "bare array or object with `candidates`" decided five times, two of them real functions with different error types | `export.py:87-94`, `06_rankfill.py:47-55`, inline at `07:116`, `09:391`, `second_opinion:84` |
| "UTC now as RFC 3339" written four ways, two `strftime` and two `isoformat` | `export.py:75`, `07_arrows.py:52`, `09_icons.py:326`, `05_read.py:363` |
| Two `Prior` classes parsing the same `data/prior/classic-era/talents.json` | `validate.py:249-272`, `ranks.py:248-277` |
| Four fuzzy-name thresholds all equal to 90, with three different rapidfuzz scorers | `validate.py:56`, `ranks.py:77`, `export.py:52`, `reader.py:353` |
| Two "cells seen in more than half the calibrations" implementations, both with the magic 40 | `arrows.py:69-77`, `reader.py:375-391` |
| `tree_slugs(calib)` copied verbatim, comment included | `04_hovers.py:50-52`, `cursor_recover.py:80-83` |
| Four `load_json` helpers with three different missing-file behaviours | `09_icons.py:181`, `validate.py:640`, `cursor_recover.py:635`, `08_export.py:44` |
| Three class lists, two hard-coded | `07_arrows.py:59` (glob), `09_icons.py:46`, `validate.py:51` |
| Six JSON dialects: `ensure_ascii` True in calib/hover files and False in candidates, `indent` 1 / 2 / compact | see the E1 write-site list |
| `prep_crop` and `prep_ref` are byte-identical; `arrows._centre` ≡ `ui.Cell.centre`; `arrows.laplacian` ≡ `ui.sharpness` | `icons.py:105,109`, `arrows.py:193,186`, `ui.py:75,687` |

### E9 — Dead code and leftovers — **low, except E9.3**

1. `ui.py:485` `looks_like_tooltip`, `cursor_recover.py:91` `parse_cell_id`:
   called only by tests. `ui.py:755` `group_runs` is a second implementation
   of `RunTracker` kept alive solely by `tests/test_ui.py:72`.
2. `04b_hovers_mkv.py:182`: `finish = getattr(st4, "finish")` — `st4.finish`
   works.
3. **`validate.py:1036-1039`** — a dead conditional whose entire body is
   `pass` (`# partial merge is allowed`). It reads like a check and performs
   none; delete it and keep the comment on the `elif` above. **medium**,
   because it sits in the override-validation path.
4. `04b_hovers_mkv.py:40-43` loads stage 4 through
   `importlib.util.spec_from_file_location` (stage filenames start with
   digits) purely to reuse `observe`/`finish`, making one stage an import
   target of another. Move `observe`, `finish` and `tree_slugs` into
   `wowtalents/hovers.py`.
5. Unused parameters: `05_read.py:121` (`hover`), `cursor_recover.py:541`
   (`cid`), `ranks.py:554` (`text`, `tokens`). `07_arrows.py:88` `A_DIR =
   ARROWS_DIR` is a pointless alias that reads as "the arrows module's dir".
   `src/wowtalents/__init__.py:6` `__all__` lists three of eight modules.
6. Stale docstrings: `05_read.py:8` and `reader.py:130` still describe "the
   brief's 2x/1.5x pair" although the defaults are 3x/2x
   (`05_read.py:195`).
7. `05_read.py:190-386`: `run` is ~200 lines covering hover merge, header
   reads, the VLM loop, duplicate-name detection, stats and writing, with the
   local `k` rebound to three different meanings (`:258`, `:261`, `:326`).
   The comment-delimited blocks are already the four functions it should be.

Path references in `pipeline/README.md` check out better than expected:
`data/overrides/` and `work/icons/lists/` exist (empty), and
`data/icons/verified.json` is hand-written and guarded
(`09_icons.py:308-309`) — though a malformed one gives a raw
`JSONDecodeError` traceback.

### E10 — Python test gaps, first five to add

`validate.py` is the worst ratio in the repo — 1153 lines gated by 231 lines
of test (16 tests) — and it is the gate every export passes through.
Completely untested: rule 10 `check_source` (`:586-614`, ~30 branches), the
rule-11 **migration chain** (`:690-729` — the most intricate logic in the
file, and the mechanism finding A1 says must now be exercised for real),
`R08-CYCLE` (`:535-553`), `build_review_queue` (`:920-944`), and rules 3, 4,
13-19 individually. `ui.py` grid detection (`square_score:156`,
`refine_cell:171`, `detect_grid:184`, `tab_state:213`) — the foundation of
stage 3 — has no test at all. Stages 03, 04, 04b, 06, 07 and 09 have zero
tests; 07 and 09 both mutate committed data.

1. **`validate.check_source` matrix** — parametrise `kind` ∈ {video,
   datamined, manual, absent} × field presence, assert exactly
   `R10-SOURCE-VIDEO`, `R10-SOURCE-DATAMINED`, `R10-REVIEWED`,
   `R10-REVIEWED-AT`, `MANUAL-UNREVIEWED`. Pure function, ~20 lines.
2. **Rule-11 migration totality** — a tmp repo with `v1.json`, `v2.json` and
   `migrations/v1-v2.json`; assert `R11-MIGRATION-NOT-TOTAL`,
   `R11-MIGRATION-RENAME`, `R11-MIGRATION-MISSING` and the clean pass.
   `tests/test_validate.py:29` already builds most of the scaffolding. This
   is the test that makes the A1 fix safe.
3. **`07_arrows._merge`** — one arrow merged; one arrow whose target cell has
   no record (`stats["unmatched"]`); a tooltip naming a different talent and
   one naming a different rank (two `stats["conflicts"]`); then run `_merge`
   **again** and assert `requires_arrows` still has one entry (pins the
   pop-then-append idempotence at `:126-127`).
4. **`05_read --add` keying** (E3) — an existing file whose `trees` block
   omits one tree name; assert the affected cell is not re-appended, and that
   a second no-op `--add` adds no `additions` entry.
5. **Stage-5 crop selection** — sharpest crop reads `rank_current: 2`, a
   blurrier later crop reads `rank_current: 0`; assert the rank-0 crop wins
   and `source.note` carries the explanation (`05_read.py:294-296`). This is
   the subtlest correctness rule in stage 5 and only its ordering helper is
   tested today (`tests/test_reader.py:168`).

### E11 — Reproducibility note — **medium**

`03_calibrate.py:142` builds ghost repairs from `donor_medians`, a glob over
`work/calib/*-<class>-*-median.png`. The median a segment gets therefore
depends on which *other* segments happen to be calibrated at that moment, so
re-running stage 3 for segment 1 after calibrating 2-8 can yield a different
median → different grid → different stage-4 hovers. The calib JSON already
records `ghosts[].donor`; record the full donor list and add
`--donors`/`--no-donors` so a run can be reproduced from its inputs alone.
Same class of problem, smaller: `cursor_recover.py:677` decides track-cache
freshness from `every` and the matcher name only, ignoring `MATCH_MIN`
(`:62`), `CELL_MARGIN` (`:63`) and the template PNG, so threshold tuning
silently reuses stale tracks.

## 6. Privacy scan

**Clean.** All 1,449 tracked files were swept (971 PNG, 312 JPG, 43 JSON
including the large `data/icons/matches.json`, 34 MD, 33 PY, 27 TS, 12 TSX,
3 SH, both lockfiles, the CI YAML and the `.env` files), plus image metadata
and all 29 commit messages.

- No `/home/<user>`, `/Users/`, `C:\Users\`, `/mnt/c/` or `\\wsl$` paths.
  Docs use `~/Dev/llama.cpp` (`docs/briefs/pipeline.md:77,86`,
  `docs/handover/2026-09-13-llama-build.md:5,18`) — no username exposed.
- No e-mail addresses in tracked content. No real names: the only "helm"
  matches are WoW icon ids (`inv_misc_desecrated_platehelm`).
- No hostnames, no `platform.node()` / `socket.gethostname()` / `$HOSTNAME`
  usage, no MAC addresses, no IPs beyond `127.0.0.1` / `localhost`.
- Hardware mentions are generic and non-identifying: "8 GB NVIDIA GPU"
  (`docs/PLAN.md:24,113`), "8 GB Ampere GPU = sm_86", CUDA 13.3, WSL2, and
  the *command* `nvidia-smi --query-gpu=memory.free`. No pasted tool output,
  no GPU/CPU product name, no `uname -a`, no `/proc/cpuinfo`.
- Image metadata: no PNG `tEXt`, no EXIF `Author`/`Software`/`Comment`, no GPS.
- Commit messages: zero `Claude-Session:` lines, zero `claude.ai` URLs, zero
  `session_*` tokens across all 29 commits — the local `commit-msg` hook
  (present at `.git/hooks/commit-msg`) is holding. The only occurrence of the
  string in the repo is the rule that forbids it (`CLAUDE.md:49`).

Two observations, neither a violation:

- The handle `Deradon`/`deradon` appears as repo URL, Pages URL, LICENSE
  holder, `pyproject.toml:7` author and as `reviewedBy`/`by` values in data
  and fixtures. `CLAUDE.md:45-47` explicitly permits this.
- Commit *metadata* carries the owner's real name and a personal-domain
  e-mail on all 29 commits. `CLAUDE.md:46-47` declares author identity
  acceptable, so this is by design — flagged only so the choice stays a
  conscious one, since `git log` is public.

## 7. What `CLAUDE.md` should say instead

### What has drifted

`CLAUDE.md` is 56 lines and reads well, which is why the errors in it are
expensive — a fresh session trusts it and skips the cross-check.

| Line | Says | Reality |
|---|---|---|
| 17 | "`tools/` – One-off scripts (review UI, diffing, icon matching)" | No `tools/` directory. One-off scripts are `pipeline/scripts/` (`cursor_recover.py`, `second_opinion.py`, three shell scripts); icon matching is `pipeline/stages/09_icons.py` + `src/wowtalents/icons.py`; the review UI is `web/src/ui/ReviewPage.tsx` at `#/review/<class>`. |
| 26-27 | "Pure rules (point allocation, row gating, prerequisites, **URL encoding**) live in `web/src/rules/`" | URL encoding lives in `web/src/url/` (`codec.ts`, `route.ts`); encoding-version loading in `web/src/data/encoding.ts`. `web/src/rules/` holds `points`, `level`, `validate`, `mutate`, `types`. The brief (`docs/briefs/web-app.md:108-129`) has this right; `CLAUDE.md` does not. |
| 9-11 | "`pipeline/` … Never edits `data/` by hand; writes to `data/extracted/`" | Stage 8 `promote` writes `data/talents/`, stage 9 writes `data/icons/matches.json` and `web/public/icons/`, stages 5 and 8 write `data/review/`. The intent (no hand edits) is right; the scope is wrong. |
| 22 | "Run the validator before committing data changes" | Does not say where it is or how to run it; nothing enforces it (no pre-commit hook, no CI — finding B1). |
| 52-55 | "Commands: See `README.md` (filled in as tooling lands). The stream download lives in `pipeline/work/video/`; check `download.log`" | The root README has no commands; they are in `pipeline/README.md` and `web/README.md`. The download finished on 2026-09-13 and is no longer a live concern. |
| — | *missing* | The current state (nine classes, 469/470 talents, live, **unreviewed**), the encoding-immutability rule (the invariant that has already been broken once, A1), and the test/validate commands with their runtimes. |

Accurate and worth keeping as-is: the data-source-of-truth rule (21-24), the
static-deploy constraint (25), the git-ignore rule for large artefacts
(28-29), the decisions block (33-41) and the whole privacy/commit section
(43-50) — the last of which is demonstrably working (section 6).

### Proposed replacement

```markdown
# WoW Forever Talent Calculator

Talent calculator for **World of Warcraft: Forever** (Classic+, announced at
BlizzCon 2026-09-12). Two halves: a data-extraction pipeline that turns
gameplay video into talent JSON, and a static web app that renders it.

Live: https://deradon.github.io/wow-forever-talent-calc/

## State (2026-09-13)

All nine classes published, 469 of 470 talents (mage Fire r1c3 was never
hovered on stream). Everything is **unreviewed**: 0 talents have
`source.reviewed: true`; 79 are flagged for review plus 21 low-confidence
prerequisite arrows. Next: owner review via `#/review/<class>`, bump the
encoding to v2 (see Rules), then Phase 2b (races). Detail and history:
`docs/PLAN.md`.

## Layout

- `pipeline/` – Python (uv). Stages `00,03,04,04b,05..09` under
  `pipeline/stages/` (numbering has gaps; there is no stage 1, 2 or 10),
  shared code in `pipeline/src/wowtalents/`, one-off scripts in
  `pipeline/scripts/`, the standalone validator at `pipeline/validate.py`.
  Large artefacts stay under `pipeline/work/` (git-ignored).
- `data/` – Canonical talent data (`data/talents/<class>.json`), the raw
  pipeline output it came from (`data/extracted/`), frame crops
  (`data/review/`), the frozen build-link orders (`data/encoding/`) and the
  Classic Era prior (`data/prior/`).
- `web/` – Static talent calculator (no backend). Reads `data/talents/`.
  `web/src/rules/` pure rules, `web/src/url/` link codec and hash routing,
  `web/src/data/` schema + loading, `web/src/ui/` React.
- `docs/` – `PLAN.md` (read first), `DATA-SCHEMA.md` (normative for `data/`),
  briefs, decisions, handovers, reviews.

## Rules

- Data source of truth is `data/talents/*.json`; the schema is
  `docs/DATA-SCHEMA.md` (normative) mirrored in `data/schema/class.schema.json`
  and `web/src/data/schema.ts`. Where a brief disagrees, the schema wins.
- Run the validator before committing any data change:
  `uv run --directory pipeline python validate.py --check ../data/talents/*.json`
  (0.6 s, must exit 0).
- **`data/encoding/v<N>.json` is immutable once pushed.** Any change to the
  set or order of talent ids needs a new `v<N+1>.json` covering every class
  plus `migrations/v<N>-v<N+1>.json`, and `dataVersion` bumped in every class
  file. Rewriting a published version silently breaks every shared build
  link — it has happened once already (`docs/reviews/2026-09-13-code-and-docs.md`,
  finding A1). `08_export.py --update-encoding` does not check this; you must.
- Every talent record keeps `source` (video id, timestamp, frame path,
  confidence). Data corrected by hand keeps `source.reviewed: true`.
- The pipeline owns `data/extracted/`, `data/review/`, `data/icons/` and
  `web/public/icons/`, and writes `data/talents/` only through
  `08_export.py promote` (which never overwrites a `reviewed: true` record).
  Never hand-edit `data/extracted/`.
- Pure rules (point allocation, row gating, prerequisites) live in
  `web/src/rules/`, the build-link codec and hash routing in `web/src/url/`.
  No DOM access in either.
- Web app must stay deployable as static files (GitHub/Cloudflare Pages).
- Docs in English. Keep the status section of `docs/PLAN.md` current when a
  phase finishes; write handovers to `docs/handover/` and add a line to
  `docs/handover/README.md`.

## Commands

```bash
# web (in web/)
npm test          # vitest, 81 tests, ~3 s
npm run build     # tsc -b && vite build
npm run e2e       # playwright, needs `npx playwright install chromium` once

# pipeline (from the repo root)
uv run --directory pipeline pytest                 # 171 tests, ~5 s
uv run --directory pipeline python validate.py --check ../data/talents/*.json
uv run --directory pipeline stages/08_export.py --help
```

Stage-by-stage documentation: `pipeline/README.md`. Web details:
`web/README.md`.

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
```

Net change: 56 → ~95 lines. The extra length buys the two things a fresh
session cannot derive from the tree — the current state and the encoding
invariant — and removes three statements that are actively false.

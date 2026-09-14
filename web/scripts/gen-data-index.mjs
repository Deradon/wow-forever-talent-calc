/**
 * Build-time data indexes. Run from vite.config.ts (every dev server, build and
 * vitest run) and asserted fresh by src/data/generated.test.ts.
 *
 * Writes two generated files into src/data/:
 *
 *   classes-index.json  the landing page's whole data source (id, class name,
 *                       tree names, counts). Without it ClassPicker had to
 *                       import all nine class chunks to print a few hundred
 *                       bytes of text.
 *   iconCrops.ts        static `?url` imports for exactly the crops the
 *                       calculator renders (`iconSource: "crop"`), so the
 *                       class route no longer carries the review-only registry
 *                       of every crop in data/review/.
 *   classic-diff.json   what changed against Classic Era (brief idea 3): per
 *                       class, the talents that are new, moved or have a
 *                       different rank count, plus the Classic talents with no
 *                       counterpart. Unchanged talents are *not* listed - a
 *                       missing entry in a class that has a diff means "same",
 *                       which keeps the file to a few kB on the class route.
 *   races-index.json    the `#/races` overview's whole data source: race names,
 *                       factions, variants, class lists, trait counts and the
 *                       new-versus-Classic combination flags. Without it the
 *                       matrix would have to pull all nine race files plus
 *                       matrix.json to draw one table.
 *   raceCrops.ts        static `?url` imports for the crops the races routes
 *                       render or link (icon crops, trait row crops, the class
 *                       bar and panel evidence).
 *   spells-index.json   the `#/spells` overview's whole data source: per class
 *                       the tabs that were opened, the entry and full-text
 *                       counts and the new-name count, plus the classes with no
 *                       spellbook file at all. The overview therefore fetches
 *                       no spell file.
 *   spellCrops/spells-<class>.ts  static `?url` imports for the crops one class page
 *                       renders or links - the 40 px row icons and the tooltip
 *                       frames. One module per class, loaded through a lazy
 *                       `import.meta.glob` in spellCrop.ts, so the 14 MB of
 *                       spellbook crops land in no chunk but the one class the
 *                       visitor opened.
 */
import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { compactDiff } from './diffWords.mjs'

const here = dirname(fileURLToPath(import.meta.url))
export const webRoot = join(here, '..')
export const repoRoot = join(webRoot, '..')

/** Mirrors REVIEW_THRESHOLD in src/ui/review.ts (DATA-SCHEMA.md section 4.5). */
const REVIEW_THRESHOLD = 0.8

/** Same precedence as src/data/load.ts: talents > examples > fixtures. */
const SOURCES = [
  ['talents', join(repoRoot, 'data/talents')],
  ['examples', join(repoRoot, 'data/examples')],
  ['fixtures', join(webRoot, 'tests/fixtures')],
]

/** The Classic Era prior the diff compares against (data/prior/classic-era). */
const PRIOR = join(repoRoot, 'data/prior/classic-era/talents.json')

/** Races: the canonical files, the derived matrix and the Classic racial prior. */
const RACES_DIR = join(repoRoot, 'data/races')
const RACE_PRIOR = join(repoRoot, 'data/prior/classic-era/racials.json')
export const RACE_PRIOR_PATH = 'data/prior/classic-era/racials.json'

/** Spells: the per-class spellbook files and the Classic Era name prior. */
const SPELLS_DIR = join(repoRoot, 'data/spells')
const SPELL_PRIOR = join(repoRoot, 'data/prior/classic-era/spells-baseline.json')
export const SPELL_PRIOR_PATH = 'data/prior/classic-era/spells-baseline.json'

function readClasses() {
  const seen = new Map()
  for (const [origin, dir] of SOURCES) {
    if (!existsSync(dir)) continue
    for (const file of readdirSync(dir).sort()) {
      if (!file.endsWith('.json')) continue
      const id = file.replace(/\.json$/, '')
      if (seen.has(id)) continue
      seen.set(id, { id, origin, dir, data: JSON.parse(readFileSync(join(dir, file), 'utf8')) })
    }
  }
  return [...seen.values()].sort((a, b) => a.id.localeCompare(b.id))
}

function needsReview(source) {
  if (!source || source.reviewed) return false
  return typeof source.confidence === 'number' && source.confidence < REVIEW_THRESHOLD
}

/**
 * A spell record the site may state anything about. Round two found four
 * fabricated entries in `data/spells` at `confidence: 0` with no crop and no
 * frame, counted as "new in Forever" on `#/spells` and in the Classic diff
 * (data review D-2). The pipeline is dropping them; until then, and for
 * anything like them later, nothing generated here counts a record that has no
 * evidence behind it.
 */
export function publishable(spell) {
  const s = spell.source
  if (!s) return false
  if (s.reviewed) return true
  if (typeof s.confidence === 'number' && s.confidence <= 0) return false
  return Boolean(s.crop || s.frame || s.kind === 'manual' || s.kind === 'datamined')
}

export function buildClassesIndex(classes) {
  return classes.map(({ id, origin, data }) => {
    const talents = data.trees.flatMap((t) => t.talents)
    return {
      id,
      origin,
      className: data.className,
      dataSource: data.dataSource,
      maxPoints: data.rules.maxPoints,
      talents: talents.length,
      reviewed: talents.filter((t) => t.source?.reviewed).length,
      needsReview: talents.filter((t) => needsReview(t.source)).length,
      trees: data.trees
        .slice()
        .sort((a, b) => a.order - b.order)
        .map((t) => ({ id: t.id, name: t.name, talents: t.talents.length })),
    }
  })
}

/**
 * The site-wide review facts, in one small file (~220 B) so that any route can
 * state them without importing an index it does not otherwise need.
 *
 * Only `origin: 'talents'` classes count: the fictional tinker class and the
 * arrow fixture are present in dev and e2e builds and must not move the number
 * a player reads. The counts exist because round two found 57 talents saying
 * "Checked by a reviewer" on a site whose header, landing page and footer all
 * said "unreviewed" (UX review finding 5); a number that the build computes
 * cannot drift the way a hand-written adjective does.
 */
export function buildFacts(classes, races, spells) {
  const real = classes.filter((c) => c.origin === 'talents')
  const talents = real.flatMap((c) => c.data.trees.flatMap((t) => t.talents))
  const traits = races.flatMap((r) => r.data.traits ?? [])
  const entries = spells.flatMap((s) => (s.data.spells ?? []).filter(publishable))
  const tooltips = entries.flatMap((s) => s.tooltips ?? [])
  const reviewed = (rs) => rs.filter((r) => r.source?.reviewed).length
  return {
    talents: { total: talents.length, reviewed: reviewed(talents), queued: talents.filter((t) => needsReview(t.source)).length },
    racialTraits: { total: traits.length, reviewed: reviewed(traits) },
    spellEntries: { total: entries.length, reviewed: reviewed(entries) },
    spellTooltips: { total: tooltips.length, reviewed: reviewed(tooltips) },
  }
}

/** Repo-relative crop paths for talents the calculator renders as a crop icon. */
export function collectIconCrops(classes) {
  const paths = new Set()
  for (const { data } of classes) {
    for (const tree of data.trees) {
      for (const t of tree.talents) {
        if (t.iconSource === 'crop' && t.iconCrop) paths.add(t.iconCrop.replace(/^\.?\//, ''))
      }
    }
  }
  return [...paths].sort()
}

export function renderIconCrops(paths) {
  const imports = paths.map((p, i) => `import c${i} from '../../../${p}?url'`).join('\n')
  const entries = paths.map((p, i) => `  ${JSON.stringify(p)}: c${i},`).join('\n')
  return `/**
 * GENERATED by scripts/gen-data-index.mjs - do not edit.
 *
 * The ${paths.length} crops the calculator actually renders. The full registry of
 * every crop under data/review/ lives in crops.ts and is review-only.
 */
${imports}

export const iconCropUrls: Record<string, string> = {
${entries}
}
`
}

// --- Classic Era diff (brief docs/briefs/ui-improvements.md, idea 3) --------
//
// Round 2 (docs/handover/2026-09-13-classic-diff-v2.md). Round 1 compared the
// raw `(tree id, row, col)` triples and called every priest Shadow and shaman
// Elemental talent `moved`, because Forever renamed those two trees. It also
// had nothing to say about the change players actually notice: the wording and
// the numbers. Both are fixed here:
//
//   - trees are matched before cells are compared (`matchTrees`), and rows and
//     columns are rebased per class (`cellBase`), so a `moved` verdict means
//     the talent really sits somewhere else;
//   - round 3: a *column*-only change inside the same row is not reported at
//     all. A talent's row is what gates it (5 points per tier); its column is
//     cosmetic ordering that Forever reshuffled in almost every tree, and the
//     attribution audit in docs/handover/2026-09-13-cell-attribution-audit.md
//     confirmed those column changes are real, not a pipeline artefact. The
//     prior cell is still recorded (`prior.movedCol`) for the review route;
//   - descriptions are rendered at rank 1 on both sides and compared through a
//     normaliser that forgives whitespace, punctuation, case and unit spelling
//     ("15 sec" == "15 seconds"). What survives that is either a pure value
//     change (`values-changed`) or a rewrite (`text-changed`), and the entry
//     carries the Classic rank-1 text plus a compact word diff so the tooltip
//     can show what the talent used to say.

/**
 * Talent names are the only stable join between the Classic prior and the
 * Forever data (talent ids are per class and were re-slugged). Normalising
 * drops apostrophes, punctuation and case so "Nature's Grasp" matches
 * "Natures Grasp" and "Shield Specialization" matches "Shield specialization".
 */
export function normalizeName(name) {
  return String(name ?? '')
    .toLowerCase()
    .replace(/[‘’']/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

// --- description comparison ------------------------------------------------

/**
 * Unit spellings that mean the same thing to a player. The Classic prior was
 * scraped from a database that writes "15 sec"; the stream reader sometimes
 * reads "15 seconds". That is not a change and must never be reported as one.
 */
const UNITS = [
  [/\b(?:seconds?|secs?)\b/g, 'sec'],
  [/\b(?:minutes?|mins?)\b/g, 'min'],
  [/\b(?:yards?|yds?)\b/g, 'yd'],
  [/\bpercent\b/g, '%'],
]

/**
 * Both descriptions reduced to what they actually claim: lower case, one
 * spelling per unit, no punctuation that is not part of a number, single
 * spaces. Used for the *decision* only - the word diff the tooltip renders is
 * taken from the untouched sentences, so a player reads real words.
 */
export function normalizeText(text) {
  let s = String(text ?? '').toLowerCase()
  s = s
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/[‒-―]/g, '-')
  for (const [re, to] of UNITS) s = s.replace(re, to)
  s = s.replace(/\s+%/g, '%')
  // A full stop or comma between digits is part of the number; anywhere else
  // it is punctuation.
  s = s.replace(/(?<!\d)[.,](?!\d)/g, ' ')
  s = s.replace(/[^a-z0-9%+\-./]+/g, ' ')
  return s.replace(/\s+/g, ' ').trim()
}

/**
 * Words that carry no claim about the game. Dropping them makes "all healing
 * spells" and "all your healing spells" the same sentence.
 */
const FILLER = new Set(['a', 'an', 'the', 'your', 'all', 'of'])

/**
 * `normalizeText` plus the three differences that are spelling rather than
 * change: an inner hyphen ("off-hand" == "offhand"), a trailing plural
 * ("resistances" == "resistance") and a filler word.
 *
 * Used for the *classification* only, never for what a player reads: the word
 * diff is still taken from the untouched sentences. Round two found five
 * talents reported as "Reworked" for a hyphen, a plural or a single article,
 * and one of those five - `rogue/dual-wield-specialization`, "offhand ... 10%"
 * against "off-hand ... 5%" - hid a real 10 % -> 5 % nerf behind the word
 * "Reworked" (data review D-6).
 */
export function classifierText(text) {
  return normalizeText(text)
    .replace(/(?<=[a-z])-(?=[a-z])/g, '')
    .split(' ')
    .filter((w) => w !== '' && !FILLER.has(w))
    .map((w) => (/^[a-z]{4,}s$/.test(w) && !/ss$/.test(w) ? w.slice(0, -1) : w))
    .join(' ')
}

/** A number, with its percent sign when it has one: "15", "1.5", "20%". */
const NUMBER = /\d+(?:\.\d+)?%?/g

/** `"deals 15% more"` -> `{ masked: "deals # more", values: ["15%"] }`. */
export function maskNumbers(text) {
  const values = []
  const masked = String(text ?? '').replace(NUMBER, (m) => {
    values.push(m)
    return '#'
  })
  return { masked, values }
}

/**
 * What changed between the Classic rank-1 sentence and the Forever one.
 *
 * `undefined` when they say the same thing. `values` when the sentences are
 * word for word the same and only numbers moved - the common case, and the one
 * worth spelling out as "15% -> 20%". `text` otherwise, with the word diff
 * taken from the raw sentences so the tooltip can strike what went and mark
 * what arrived.
 */
export function compareDescriptions(classicText, foreverText) {
  const classic = String(classicText ?? '')
  const forever = String(foreverText ?? '')
  if (!classic || !forever) return undefined
  const a = classifierText(classic)
  const b = classifierText(forever)
  if (a === b) return undefined
  const ma = maskNumbers(a)
  const mb = maskNumbers(b)
  const diff = compactDiff(classic, forever)
  if (ma.masked === mb.masked) {
    const values = []
    for (const [i, was] of ma.values.entries()) {
      const now = mb.values[i]
      if (was !== now) values.push([was, now])
    }
    // Same words, same numbers, different normalised text is impossible; guard
    // anyway rather than emit an empty "values changed".
    if (values.length > 0) return { kind: 'values', values, diff }
  }
  return { kind: 'text', diff }
}

// --- the prior, flattened --------------------------------------------------

/**
 * Rank `r` (0-based) of a record that carries a `{n}` template plus per-rank
 * slot values. Mirrors `renderDescription` in src/data/schema.ts, which cannot
 * be imported here: this script is plain ESM run by node.
 */
function renderRank(description, rank) {
  if (rank === undefined) return String(description ?? '')
  if (typeof rank === 'string') return rank
  if (!Array.isArray(rank)) return String(description ?? '')
  return String(description ?? '').replace(/\{(\d+)\}/g, (_, i) => String(rank[Number(i)] ?? `{${i}}`))
}

/**
 * The numbers a rank series shows, e.g. `"20/40/60"`. Picks the slot that
 * actually changes between ranks, the same rule `foreverSeries` uses in
 * src/ui/tooltipText.ts, so the Classic series beside ours is read off the same
 * way. Undefined when the ranks are whole sentences or nothing varies.
 */
export function rankSeries(ranks) {
  if (!Array.isArray(ranks) || ranks.length < 2) return undefined
  const rows = ranks.filter(Array.isArray)
  if (rows.length !== ranks.length) return undefined
  const width = Math.min(...rows.map((r) => r.length))
  let fallback
  for (let j = 0; j < width; j++) {
    const column = rows.map((r) => r[j])
    if (!column.every((v) => typeof v === 'number')) continue
    if (fallback === undefined) fallback = j
    if (new Set(column).size > 1) return column.join('/')
  }
  return fallback === undefined ? undefined : rows.map((r) => r[fallback]).join('/')
}

/** Flattens one prior class entry into comparable talent records. */
function priorTalents(priorClass) {
  const out = []
  for (const tree of priorClass?.trees ?? []) {
    for (const t of tree.talents ?? []) {
      out.push({
        id: t.id,
        name: t.name,
        tree: tree.id,
        treeName: tree.name,
        row: t.row,
        col: t.col,
        maxRank: t.maxRank,
        text: t.ranks?.[0] ?? renderRank(t.description, t.slots?.[0]),
        series: rankSeries(t.slots),
      })
    }
  }
  return out
}

/** Flattens one Forever class file the same way. */
function currentTalents(cls) {
  const out = []
  for (const tree of cls.trees) {
    for (const t of tree.talents) {
      out.push({
        id: t.id,
        name: t.name,
        tree: tree.id,
        treeName: tree.name,
        row: t.row,
        col: t.col,
        maxRank: t.maxRank,
        text: renderRank(t.description, t.ranks?.[0]),
      })
    }
  }
  return out
}

// --- tree identity and the cell base ---------------------------------------

/**
 * Which Forever tree each Classic tree became. Forever renamed two of the
 * twenty-seven (priest Shadow -> Shadow Magic, shaman Elemental -> Elemental
 * Combat) and round 1 read both renames as thirty-three moved talents.
 *
 * A tree is the same tree when it is the same class (the caller only ever
 * passes one class) and
 *
 *   1. the ids match, or
 *   2. the names match after `normalizeName`, or
 *   3. the majority of its talents match by name - the fallback that survives
 *      a rename we have not seen, and the reason the mapping is computed
 *      rather than hard-coded.
 *
 * Pass 3 is greedy on the strongest overlap first, so a tree that merely traded
 * a talent or two with its neighbour cannot steal the neighbour's identity.
 *
 * @returns {Map<string, string>} Classic tree id -> Forever tree id.
 */
export function matchTrees(currentTrees, priorTrees) {
  const map = new Map()
  const takenCurrent = new Set()
  const left = []

  for (const p of priorTrees) {
    const byId = currentTrees.find((c) => c.id === p.id && !takenCurrent.has(c.id))
    if (byId) {
      map.set(p.id, byId.id)
      takenCurrent.add(byId.id)
      continue
    }
    left.push(p)
  }

  const stillLeft = []
  for (const p of left) {
    const byName = currentTrees.find((c) => !takenCurrent.has(c.id) && normalizeName(c.name) === normalizeName(p.name))
    if (byName) {
      map.set(p.id, byName.id)
      takenCurrent.add(byName.id)
      continue
    }
    stillLeft.push(p)
  }

  // Majority-of-talents fallback, strongest overlap first.
  const scores = []
  for (const p of stillLeft) {
    const names = new Set((p.talents ?? []).map((t) => normalizeName(t.name)))
    for (const c of currentTrees) {
      if (takenCurrent.has(c.id)) continue
      const mine = (c.talents ?? []).map((t) => normalizeName(t.name))
      const shared = mine.filter((n) => names.has(n)).length
      const smaller = Math.min(names.size, mine.length) || 1
      const ratio = shared / smaller
      if (ratio > 0.5) scores.push({ prior: p.id, current: c.id, ratio })
    }
  }
  scores.sort((a, b) => b.ratio - a.ratio)
  for (const s of scores) {
    if (map.has(s.prior) || takenCurrent.has(s.current)) continue
    map.set(s.prior, s.current)
    takenCurrent.add(s.current)
  }
  return map
}

/**
 * Which index a set of talents counts from. Our data is 0-based
 * (DATA-SCHEMA.md section 3); a prior that counted rows from 1 would otherwise
 * report every single talent in the game as having moved up one row.
 * Subtracting each side's own base makes the comparison independent of the
 * convention. The Classic Era prior turns out to be 0-based too, so the shift
 * is zero today - the guard is here so that a future prior cannot quietly
 * invent 470 moves.
 *
 * Only an exact minimum of 1 counts as a 1-based origin. A minimum of 2 or more
 * is a sparse tree - real ones always fill row 0 and column 0 - and rebasing on
 * it would shift a tree that simply has a gap at the top left.
 */
export function cellBase(talents) {
  if (talents.length === 0) return { row: 0, col: 0 }
  const base = (key) => (Math.min(...talents.map((t) => t[key])) === 1 ? 1 : 0)
  return { row: base('row'), col: base('col') }
}

// --- classification --------------------------------------------------------

/** Statuses in the order they are reported; `same` is never written out. */
export const STATUSES = ['new', 'moved', 'rank-changed', 'text-changed', 'values-changed', 'same']

/**
 * One talent against its Classic counterpart, worst news first:
 *
 *   new > moved > rank-changed > text-changed > values-changed > same
 *
 * The cell wins over the rank count because the cell is what the player is
 * looking at, and a rewrite wins over a value tweak because it is the larger
 * claim. The entry carries everything the losing categories would have said -
 * the old cell, the old rank count, the old sentence - so the tooltip can be
 * as precise as it likes without a second lookup.
 *
 * `current.tree` and `prior.tree` are compared **after** `matchTrees`, which is
 * what `prior.sameTree` records. `prior.tree` stays the Classic id, because
 * that is what `removed[]` and the later `#/changes` page speak.
 *
 * A move is a change of **tree or row**. A different column inside the same row
 * is not: rows gate points, columns are ordering, and Forever reshuffled the
 * order in most trees without moving anything a player has to plan around. Such
 * a talent keeps its real status (`same`, `text-changed`, ...) and records
 * `prior.movedCol` so the review route can still show where it used to sit;
 * nothing in the player-facing UI says "moved" for it.
 *
 * `prior` is undefined when no Classic talent of that name exists in the class.
 */
export function classifyTalent(current, prior) {
  if (!prior) return { status: 'new' }
  const sameTree = prior.sameTree ?? prior.tree === current.tree
  const entry = {
    status: 'same',
    prior: {
      tree: prior.tree,
      treeName: prior.treeName,
      row: prior.row,
      col: prior.col,
      maxRank: prior.maxRank,
    },
  }
  if (!sameTree) entry.prior.movedTree = true
  if (prior.row !== current.row) {
    entry.prior.movedRow = true
    // Where it went. The change line names both ends of a row move, and the
    // tooltip should not have to look the talent up a second time to say so.
    entry.row = current.row
  } else if (sameTree && prior.col !== current.col) {
    entry.prior.movedCol = true
  }

  const text = compareDescriptions(prior.text, current.text)
  if (text) {
    // The sentence and its word diff are bulky and only wanted when a player
    // opens the card, so they go to the lazily fetched companion file; what
    // stays here is the flag the change line needs, plus the value pairs,
    // which the line itself prints.
    entry.textChange = text.kind
    if (text.kind === 'values') entry.values = text.values
    entry.classic = {
      text: prior.text,
      ...(prior.series ? { series: prior.series } : {}),
      diff: text.diff,
      ...(text.kind === 'values' ? { values: text.values } : {}),
    }
  }

  if (!sameTree || prior.row !== current.row) entry.status = 'moved'
  else if (prior.maxRank !== current.maxRank) entry.status = 'rank-changed'
  else if (text?.kind === 'text') entry.status = 'text-changed'
  else if (text?.kind === 'values') entry.status = 'values-changed'
  return entry
}

/**
 * Diffs one class. Matching is exclusive and two-pass: same tree first (after
 * `matchTrees`), then anywhere in the class, so a talent that merely moved
 * between trees is `moved` rather than `new` plus a phantom removal.
 */
export function diffClass(cls, priorClass) {
  const treeMap = matchTrees(cls.trees ?? [], priorClass?.trees ?? [])
  const pool = priorTalents(priorClass)
  const current = currentTalents(cls)

  // Each side rebased on its own origin, so a 1-based prior cannot manufacture
  // a whole tree of moves. Both are 0-based today, which the tests pin down.
  const priorBase = cellBase(pool)
  const currentBase = cellBase(current)
  for (const p of pool) {
    p.row -= priorBase.row
    p.col -= priorBase.col
    p.mapsTo = treeMap.get(p.tree) ?? p.tree
  }
  for (const t of current) {
    t.row -= currentBase.row
    t.col -= currentBase.col
  }

  const used = new Set()
  const byName = new Map()
  for (const [i, p] of pool.entries()) {
    const key = normalizeName(p.name)
    if (!byName.has(key)) byName.set(key, [])
    byName.get(key).push(i)
  }

  current.sort((a, b) => a.tree.localeCompare(b.tree) || a.row - b.row || a.col - b.col)

  const matched = new Map()
  const take = (t, sameTreeOnly) => {
    const candidates = byName.get(normalizeName(t.name)) ?? []
    for (const i of candidates) {
      if (used.has(i)) continue
      if (sameTreeOnly && pool[i].mapsTo !== t.tree) continue
      used.add(i)
      matched.set(t.id, { ...pool[i], sameTree: pool[i].mapsTo === t.tree })
      return true
    }
    return false
  }
  const rest = current.filter((t) => !take(t, true))
  for (const t of rest) take(t, false)

  const talents = {}
  const text = {}
  const counts = Object.fromEntries(STATUSES.map((s) => [s, 0]))
  for (const t of current) {
    const entry = classifyTalent(t, matched.get(t.id))
    counts[entry.status] += 1
    const { classic, ...light } = entry
    if (classic) text[t.id] = classic
    // `same` is the default: leaving it out keeps the shipped file small. The
    // one exception is a column-only move, which is `same` to a player but
    // still carries the Classic cell the review route wants to see.
    if (light.status !== 'same' || light.prior?.movedCol) talents[t.id] = light
  }

  const removed = pool
    .filter((_, i) => !used.has(i))
    .map((p) => ({
      id: p.id,
      name: p.name,
      tree: p.tree,
      treeName: p.treeName,
      row: p.row,
      col: p.col,
      maxRank: p.maxRank,
    }))

  return { counts: { ...counts, removed: removed.length }, talents, removed, text }
}

/**
 * Both halves at once: only classes that have a Classic counterpart appear, so
 * the example classes (tinker) simply carry no diff and the UI shows no markers
 * for them rather than claiming every talent is new.
 *
 *   `diff`  the class route's file: statuses, the Classic cell, the value pairs
 *           the change line prints, and `removed[]`.
 *   `text`  the Classic sentence, its per-rank values and the word diff, keyed
 *           by class and talent id and fetched with a dynamic `import()` only
 *           when a player opens the card - the same deal the 971-entry crop
 *           registry gets.
 */
export function buildClassic(classes, prior) {
  const per = {}
  for (const { id, data } of classes) {
    const priorClass = prior?.classes?.[id]
    if (!priorClass) continue
    per[id] = diffClass(data, priorClass)
  }
  const totals = Object.fromEntries([...STATUSES, 'removed'].map((s) => [s, 0]))
  const light = {}
  const text = {}
  for (const [id, entry] of Object.entries(per)) {
    for (const key of Object.keys(totals)) totals[key] += entry.counts[key] ?? 0
    light[id] = { counts: entry.counts, talents: entry.talents, removed: entry.removed }
    if (Object.keys(entry.text).length > 0) text[id] = entry.text
  }
  return {
    diff: { prior: 'Classic Era (data/prior/classic-era/talents.json)', totals, classes: light },
    text,
  }
}

/** The class route's half. */
export function buildClassicDiff(classes, prior) {
  return buildClassic(classes, prior).diff
}

/** The lazily fetched half. */
export function buildClassicText(classes, prior) {
  return buildClassic(classes, prior).text
}

// --- races (docs/handover/2026-09-13-races-data.md, section 5) -------------

/** The nine race files, sorted by id; matrix.json is not a race. */
export function readRaces() {
  if (!existsSync(RACES_DIR)) return []
  return readdirSync(RACES_DIR)
    .sort()
    .filter((f) => f.endsWith('.json') && f !== 'matrix.json')
    .map((f) => ({ id: f.replace(/\.json$/, ''), data: JSON.parse(readFileSync(join(RACES_DIR, f), 'utf8')) }))
}

export function readMatrix() {
  const file = join(RACES_DIR, 'matrix.json')
  if (!existsSync(file)) return undefined
  return JSON.parse(readFileSync(file, 'utf8'))
}

function readRacePrior() {
  if (!existsSync(RACE_PRIOR)) return undefined
  return JSON.parse(readFileSync(RACE_PRIOR, 'utf8'))
}

/**
 * Which of a race's classes are new against Classic Era.
 *
 * The rule the data handover proposes: a class that the Classic racial prior
 * does not list for that race. `undefined` when the prior knows nothing about
 * the race at all, which is not the same as "everything is new" - the UI then
 * marks no cell rather than claiming a combination is new on no evidence.
 * Skyborne is the one race the prior lists with an empty class list, which is a
 * real statement (it did not exist in Classic) and therefore flags all of them.
 */
export function newCombos(classes, priorClasses) {
  if (!Array.isArray(priorClasses)) return undefined
  const had = new Set(priorClasses)
  return classes.filter((c) => !had.has(c))
}

/** Per-race trait counts by Classic status, plus the total. */
export function traitCounts(traits) {
  const counts = { total: traits.length, new: 0, changed: 0, same: 0, unknown: 0 }
  for (const t of traits) {
    const status = t.classic?.status ?? 'unknown'
    if (status in counts) counts[status] += 1
  }
  return counts
}

/**
 * The `#/races` overview's data source. Everything the matrix table and the
 * race links need, and nothing a race page would want - descriptions, crops and
 * provenance stay in the race files, which are fetched one at a time.
 *
 * `classes` is the class-bar order from matrix.json, because that is the order
 * the game shows and therefore the column order of the table.
 */
export function buildRacesIndex(races, matrix, racePrior) {
  const byRace = new Map((matrix?.races ?? []).map((r) => [r.race, r]))
  const priorRaces = racePrior?.races ?? {}
  return {
    prior: RACE_PRIOR_PATH,
    // The prior is a paraphrase written from memory; the flag travels with the
    // data so the page can say so instead of hard-coding a caveat.
    priorVerified: Boolean(racePrior?.verified),
    classes: matrix?.classes ?? [],
    races: races.map(({ id, data }) => {
      const row = byRace.get(id)
      const prior = priorRaces[id]
      const counts = traitCounts(data.traits ?? [])
      const entry = {
        id,
        raceName: data.raceName,
        faction: data.faction,
        classes: data.classes ?? [],
        observed: row ? row.observed : (data.classes ?? []).length > 0,
        complete: Boolean(data.complete),
        traits: counts.total,
        counts: { new: counts.new, changed: counts.changed, same: counts.same, unknown: counts.unknown },
      }
      const combos = newCombos(entry.classes, prior?.classes)
      if (combos) entry.newCombos = combos
      if (data.variants) {
        entry.variants = data.variants.map((v) => {
          const variant = { id: v.id, name: v.name, faction: v.faction, classes: v.classes ?? [] }
          const own = newCombos(variant.classes, prior?.classes)
          if (own) variant.newCombos = own
          return variant
        })
      }
      if (row?.reportedElsewhere) entry.reportedElsewhere = row.reportedElsewhere
      if (row?.agreement) entry.agreement = row.agreement
      if (row?.disagreement) entry.disagreement = row.disagreement
      return entry
    }),
    notes: matrix?.notes ?? [],
  }
}

/** Repo-relative crop paths the races routes render or link. */
export function collectRaceCrops(races) {
  const paths = new Set()
  const add = (p) => {
    if (typeof p === 'string' && p) paths.add(p.replace(/^\.?\//, ''))
  }
  for (const { data } of races) {
    add(data.classesSource?.crop)
    add(data.loreSource?.crop)
    for (const trait of data.traits ?? []) {
      if (trait.iconSource === 'crop') add(trait.iconCrop)
      add(trait.source?.crop)
    }
  }
  return [...paths].sort()
}

export function renderRaceCrops(paths) {
  const imports = paths.map((p, i) => `import r${i} from '../../../${p}?url'`).join('\n')
  const entries = paths.map((p, i) => `  ${JSON.stringify(p)}: r${i},`).join('\n')
  return `/**
 * GENERATED by scripts/gen-data-index.mjs - do not edit.
 *
 * The ${paths.length} crops the races routes render or link: 36 px racial icons,
 * the trait row crops behind each card's Details line, and the class-bar and
 * panel evidence. The full registry of every crop under data/review/ lives in
 * crops.ts and is review-only.
 */
${imports}

export const raceCropUrls: Record<string, string> = {
${entries}
}
`
}

// --- spells (docs/handover/2026-09-13-spells-data.md, section 5) -----------
//
// The spellbook is a coverage record, not a spell list: it holds what the
// stream happened to show of a level-38 demo character's book. The index
// therefore carries the counts *and* the gaps - which tabs were opened, which
// were not, and which classes have no file at all (priest was never on screen).

/** The eight spellbook files, sorted by id. Priest has none. */
export function readSpells() {
  if (!existsSync(SPELLS_DIR)) return []
  return readdirSync(SPELLS_DIR)
    .sort()
    .filter((f) => f.endsWith('.json'))
    .map((f) => ({ id: f.replace(/\.json$/, ''), data: JSON.parse(readFileSync(join(SPELLS_DIR, f), 'utf8')) }))
}

function readSpellPrior() {
  if (!existsSync(SPELL_PRIOR)) return undefined
  return JSON.parse(readFileSync(SPELL_PRIOR, 'utf8'))
}

/**
 * The tabs of one class in spellbook order, each with the number of entries
 * read from it. A tab with no entries stays in the list: it was opened, and
 * "opened and empty" is a different statement from "never opened".
 */
export function tabCounts(data) {
  const byTab = new Map()
  for (const spell of (data.spells ?? []).filter(publishable)) {
    if (!spell.tab) continue
    byTab.set(spell.tab, (byTab.get(spell.tab) ?? 0) + 1)
  }
  return (data.tabs ?? [])
    .slice()
    .sort((a, b) => a.order - b.order)
    .map((t) => ({ id: t.id, name: t.name, spells: byTab.get(t.id) ?? 0 }))
}

/** Entries, spells with a full tooltip, tooltips read, and new names. */
export function spellCounts(data) {
  // Records with no evidence behind them are counted nowhere: a fabricated
  // name is otherwise *guaranteed* to be counted as "new in Forever", because
  // "new" means "not in our Classic list" (data review D-2, UX finding 18).
  const spells = (data.spells ?? []).filter(publishable)
  return {
    entries: spells.length,
    withText: spells.filter((s) => (s.tooltips ?? []).length > 0).length,
    tooltips: spells.reduce((n, s) => n + (s.tooltips ?? []).length, 0),
    new: spells.filter((s) => s.classic?.status === 'new').length,
    searchOnly: spells.filter((s) => !s.tab).length,
  }
}

/**
 * The `#/spells` overview's data source. Counts, tabs and gaps only: names,
 * tooltip text, crops and provenance stay in the per-class files, which the
 * class page fetches one at a time.
 *
 * `absent` is the other half of the record. A class with no spellbook file was
 * never on screen, and the overview has to say so rather than 404.
 */
export function buildSpellsIndex(spells, classes, prior) {
  const seen = new Set(spells.map((s) => s.id))
  return {
    prior: SPELL_PRIOR_PATH,
    // Names written from memory: the page says "unverified" because the data does.
    priorVerified: Boolean(prior?.verified),
    classes: spells.map(({ id, data }) => {
      const counts = spellCounts(data)
      const coverage = data.coverage ?? {}
      return {
        id,
        className: data.className,
        observedLevel: data.observedLevel,
        entries: counts.entries,
        withText: counts.withText,
        tooltips: counts.tooltips,
        new: counts.new,
        searchOnly: counts.searchOnly,
        tabs: tabCounts(data),
        tabsMissing: coverage.tabsMissing ?? [],
        showAllSpellRanks: coverage.showAllSpellRanks ?? 'not observed',
        complete: Boolean(data.complete),
      }
    }),
    absent: classes
      .filter((c) => c.origin === 'talents' && !seen.has(c.id))
      .map((c) => ({ id: c.id, className: c.data.className })),
  }
}

/**
 * The crops one class page renders or links: the 40 px row icon of every entry
 * and the frame behind every full tooltip. Row crops are deliberately not
 * collected - a row without a tooltip shows no disclosure, so nothing links
 * them, and they are the bulk of the 14 MB.
 */
export function collectSpellCrops(data) {
  const paths = new Set()
  const add = (p) => {
    if (typeof p === 'string' && p) paths.add(p.replace(/^\.?\//, ''))
  }
  for (const spell of data.spells ?? []) {
    if (spell.iconSource === 'crop') add(spell.iconCrop)
    for (const tooltip of spell.tooltips ?? []) add(tooltip.source?.crop)
  }
  return [...paths].sort()
}

export function renderSpellCrops(classId, paths) {
  const imports = paths.map((p, i) => `import s${i} from '../../../../${p}?url'`).join('\n')
  const entries = paths.map((p, i) => `  ${JSON.stringify(p)}: s${i},`).join('\n')
  return `/**
 * GENERATED by scripts/gen-data-index.mjs - do not edit.
 *
 * The ${paths.length} crops the ${classId} spell page renders or links: the row icon of
 * every entry and the frame behind every full tooltip. One module per class,
 * reached through the lazy glob in spellCrop.ts, so a visitor downloads the
 * URLs of one class and never the whole spellbook.
 */
${imports}

export const spellCropUrls: Record<string, string> = {
${entries}
}
`
}

function readPrior() {
  if (!existsSync(PRIOR)) return undefined
  return JSON.parse(readFileSync(PRIOR, 'utf8'))
}

/**
 * Write through a temporary file in the same directory and rename over the
 * target. `classic-diff.json` is 120 kB and `classic-text.json` 84 kB, both
 * tracked: a truncating write interrupted halfway leaves a corrupt file in the
 * working tree. The pipeline fixed this class of defect on the Python side in
 * round one (`wowtalents/fsio.py`); the generator repeated it (code review
 * K-19).
 */
function writeIfChanged(path, content) {
  if (existsSync(path) && readFileSync(path, 'utf8') === content) return false
  mkdirSync(dirname(path), { recursive: true })
  const tmp = `${path}.tmp-${process.pid}`
  try {
    writeFileSync(tmp, content)
    renameSync(tmp, path)
  } finally {
    if (existsSync(tmp)) rmSync(tmp)
  }
  return true
}

/** Regenerates every generated file; true when anything changed on disk. */
export function generate(root = webRoot) {
  const out = expected()
  const cropDir = join(root, 'src/data/spellCrops')
  const written = [
    writeIfChanged(join(root, 'src/data/classes-index.json'), out.index),
    writeIfChanged(join(root, 'src/data/iconCrops.ts'), out.crops),
    writeIfChanged(join(root, 'src/data/classic-diff.json'), out.classicDiff),
    writeIfChanged(join(root, 'src/data/classic-text.json'), out.classicText),
    writeIfChanged(join(root, 'src/data/races-index.json'), out.racesIndex),
    writeIfChanged(join(root, 'src/data/raceCrops.ts'), out.raceCrops),
    writeIfChanged(join(root, 'src/data/spells-index.json'), out.spellsIndex),
    writeIfChanged(join(root, 'src/data/facts.json'), out.facts),
    ...Object.entries(out.spellCrops).map(([id, content]) =>
      writeIfChanged(join(cropDir, `spells-${id}.ts`), content),
    ),
    // A class whose spellbook file was deleted must not leave a module behind:
    // spellCrop.ts globs this directory, so a stale file would still be served.
    ...(existsSync(cropDir) ? readdirSync(cropDir) : [])
      .filter((f) => f.endsWith('.ts') && !(f.replace(/^spells-/, '').replace(/\.ts$/, '') in out.spellCrops))
      .map((f) => {
        rmSync(join(cropDir, f))
        return true
      }),
  ]
  return written.some(Boolean)
}

export function expected() {
  const classes = readClasses()
  const classic = buildClassic(classes, readPrior())
  const races = readRaces()
  const spells = readSpells()
  return {
    index: `${JSON.stringify(buildClassesIndex(classes), null, 2)}\n`,
    crops: renderIconCrops(collectIconCrops(classes)),
    classicDiff: `${JSON.stringify(classic.diff, null, 2)}\n`,
    // No indentation: nobody reads this one, and it is fetched over the wire.
    classicText: `${JSON.stringify(classic.text)}\n`,
    racesIndex: `${JSON.stringify(buildRacesIndex(races, readMatrix(), readRacePrior()), null, 2)}\n`,
    raceCrops: renderRaceCrops(collectRaceCrops(races)),
    spellsIndex: `${JSON.stringify(buildSpellsIndex(spells, classes, readSpellPrior()), null, 2)}\n`,
    facts: `${JSON.stringify(buildFacts(classes, races, spells), null, 2)}\n`,
    spellCrops: Object.fromEntries(
      spells.map(({ id, data }) => [id, renderSpellCrops(id, collectSpellCrops(data))]),
    ),
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  generate()
  console.log('data indexes generated')
}

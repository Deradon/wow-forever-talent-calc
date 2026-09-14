/**
 * Import a build (brief "UI and UX improvements", idea 9).
 *
 * Three inputs, tried in this order:
 *   a) a link to this site        -> parse the hash, navigate
 *   b) a bare build code `30250-005-32` -> the current class, decoded by codec.ts
 *   c) a Wowhead Classic link     -> one digit per talent, per tab, row-major
 *      against the Classic prior, then mapped Classic -> Forever *by name*
 *      within the class and sanitized under our rules.
 *
 * Nothing here touches our own `t=` encoding, so it is unaffected by the
 * encoding-freeze decision. Pure: no DOM, no globals.
 */
import type { ClassicClass } from '../data/classicIndex'
import type { ClassData } from '../data/schema'
import { add, canAdd, rankOf, totalPoints, type Build } from '../rules'
import { parseHash } from './route'

export type ImportSource =
  | { kind: 'link'; classId: string; version?: number; build: string }
  | { kind: 'code'; build: string }
  | { kind: 'wowhead'; classId: string; code: string }
  | { kind: 'error'; message: string }

/** Our own build code: decimal digits per tree, trees joined by `-`. */
const CODE = /^[0-9]*(-[0-9]*)*$/

const WOWHEAD_CLASSES = new Set([
  'druid',
  'hunter',
  'mage',
  'paladin',
  'priest',
  'rogue',
  'shaman',
  'warlock',
  'warrior',
])

/**
 * Classifies whatever the player pasted. The Wowhead test runs first, because
 * a Wowhead build string is also "digits and hyphens" and would otherwise be
 * read as one of ours.
 */
export function parseImport(input: string): ImportSource {
  const text = input.trim()
  if (text === '') return { kind: 'error', message: 'Paste a build link, a build code, or a Wowhead Classic talent link.' }

  // Our own hash comes first: this site's own path contains "talent-calc"
  // (the repository is wow-forever-talent-calc), so the Wowhead test would
  // otherwise swallow every link we hand out.
  const hash = text.indexOf('#/')
  if (hash !== -1) {
    const route = parseHash(text.slice(hash))
    if (route.kind === 'class') {
      return { kind: 'link', classId: route.classId, version: route.version, build: route.build ?? '' }
    }
    if (route.kind === 'review') return { kind: 'link', classId: route.classId, build: '' }
    return { kind: 'error', message: 'That link does not point at a class page.' }
  }

  if (/talent-calc/i.test(text)) return parseWowhead(text)

  if (CODE.test(text) && /[0-9]/.test(text)) return { kind: 'code', build: text }

  if (/^https?:\/\//i.test(text)) {
    return { kind: 'error', message: 'That link is not a build link for this site or for the Wowhead Classic calculator.' }
  }
  return { kind: 'error', message: 'Not a build link, a build code, or a Wowhead Classic talent link.' }
}

function parseWowhead(text: string): ImportSource {
  // .../classic/talent-calc/<class>/<code>, optionally /embed/ before the class
  // and optionally a fourth segment (the level-by-level talent order), which we
  // ignore. A Season of Discovery link appends `_<runes>` to the last tab.
  const match = /talent-calc\/(?:embed\/)?([a-z-]+)(?:\/([^/?#\s]*))?/i.exec(text)
  if (!match) return { kind: 'error', message: 'Could not read the class out of that Wowhead link.' }
  const classId = match[1]!.toLowerCase()
  const code = (match[2] ?? '').trim().split('_')[0]!
  if (!WOWHEAD_CLASSES.has(classId)) {
    return { kind: 'error', message: `"${classId}" is not one of the nine Classic classes.` }
  }
  if (code === '') return { kind: 'error', message: 'That Wowhead link carries no build - open a build and copy the URL again.' }
  if (!/^[0-9-]+$/.test(code)) {
    // wowhead.com/talent#<letters> is the old retail calculator, a different
    // alphabet entirely; /talent-calc/ has always been decimal digits.
    return {
      kind: 'error',
      message: 'That looks like an old Wowhead talent string. Open the build on the current Classic calculator and copy the URL again.',
    }
  }
  return { kind: 'wowhead', classId, code }
}

/**
 * Splits a Wowhead code into one segment per talent tab: `tab1-tab2-tab3`,
 * trailing tabs omitted, empty tabs written as empty segments (`-05`,
 * `0503--550340510553151`). A code with no hyphen is the first tab alone.
 * Wowhead itself serves tabs padded past the talent count, so a segment that is
 * longer than its tab is accepted and the surplus digits are ignored.
 */
export function splitWowheadCode(code: string, tabSizes: number[]): { segments: string[] } | { error: string } {
  const segments = code.split('-')
  if (segments.length > tabSizes.length) {
    return { error: `That code has ${segments.length} talent tabs; this class has ${tabSizes.length}.` }
  }
  return { segments }
}

/**
 * One talent that did not arrive whole, stated once per talent rather than
 * once per lost point. The round-two UX review (finding 3) found `Improved
 * Charge`, `Deep Wounds` and four others listed twice on one 46-point link,
 * because a talent that Forever shortened *and* the rules then refused wrote
 * two rows with two different numbers beside them.
 */
export interface UnplacedTalent {
  name: string
  /** Points the pasted build put on this talent. */
  requested: number
  /** Points that survived onto it. */
  kept: number
  /** Ranks the talent has in Forever; `undefined` when it has none. */
  maxRank?: number
  reason: 'not-in-forever' | 'fewer-ranks' | 'rules'
}

function points(n: number): string {
  return `${n} point${n === 1 ? '' : 's'}`
}

/**
 * The player-facing line for one such talent. It says what happened and with
 * which numbers - "fewer ranks in Forever" alone read as "this talent is gone"
 * when the talent is there and only the surplus was dropped.
 */
export function unplacedLine(u: UnplacedTalent): string {
  if (u.reason === 'not-in-forever') return `${u.name}: ${points(u.requested)} lost, not in Forever.`
  if (u.reason === 'fewer-ranks') {
    const ranks = u.maxRank ?? u.kept
    return `${u.name}: placed ${u.kept} of ${points(u.requested)}, Forever has ${ranks} rank${ranks === 1 ? '' : 's'}.`
  }
  return `${u.name}: placed ${u.kept} of ${points(u.requested)}, the rest does not fit the tree.`
}

export interface ImportOutcome {
  build: Build
  /** Points in the pasted string. */
  requested: number
  /** Points that survived the mapping and the rules. */
  placed: number
  left: number
  unplaced: UnplacedTalent[]
}

/** `Improved Heroic Strike` and `improvedheroicstrike` are the same talent. */
export function normalizeName(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '')
}

interface ForeverTalent {
  treeId: string
  talentId: string
  name: string
  maxRank: number
}

function foreverByName(cls: ClassData): Map<string, ForeverTalent> {
  const map = new Map<string, ForeverTalent>()
  for (const tree of cls.trees) {
    for (const talent of tree.talents) {
      const key = normalizeName(talent.name)
      if (!map.has(key)) map.set(key, { treeId: tree.id, talentId: talent.id, name: talent.name, maxRank: talent.maxRank })
    }
  }
  return map
}

/**
 * Maps a decoded Classic build onto the Forever class by talent name, then
 * spends the points top-down through the ordinary `canAdd` verdict - never a
 * special case, so an imported build is a build the player could have clicked.
 *
 * Talents that moved rows in Forever are the reason a second pass exists: a
 * row can become affordable once the rows above it have been filled.
 */
export function mapClassicBuild(cls: ClassData, classic: ClassicClass, segments: string[]): ImportOutcome {
  const byName = foreverByName(cls)
  const unplaced: UnplacedTalent[] = []
  const wanted = new Map<string, { treeId: string; talentId: string; name: string; rank: number; maxRank: number }>()
  let requested = 0

  segments.forEach((segment, tab) => {
    const tree = classic.trees[tab]
    if (!tree) return
    for (let i = 0; i < segment.length; i++) {
      const rank = Number(segment[i])
      if (!Number.isFinite(rank) || rank <= 0) continue
      const entry = tree.talents[i]
      if (!entry) continue
      const [name] = entry
      requested += rank
      const target = byName.get(normalizeName(name))
      if (!target) {
        unplaced.push({ name, requested: rank, kept: 0, reason: 'not-in-forever' })
        continue
      }
      wanted.set(`${target.treeId}/${target.talentId}`, {
        treeId: target.treeId,
        talentId: target.talentId,
        name: target.name,
        rank,
        maxRank: target.maxRank,
      })
    }
  })

  // Class order, rows top-down: the order a player would have to click in.
  const order = cls.trees.flatMap((tree) =>
    [...tree.talents]
      .sort((a, b) => a.row - b.row || a.col - b.col)
      .map((t) => wanted.get(`${tree.id}/${t.id}`))
      .filter((w): w is NonNullable<typeof w> => w !== undefined),
  )

  let build: Build = {}
  for (let pass = 0; pass < 3; pass++) {
    let changed = false
    for (const want of order) {
      const target = Math.min(want.rank, want.maxRank)
      while (rankOf(build, want.treeId, want.talentId) < target && canAdd(cls, build, want.treeId, want.talentId).ok) {
        build = add(cls, build, want.treeId, want.talentId)
        changed = true
      }
    }
    if (!changed) break
  }

  // One row per talent: the shortfall is stated once, with the reason that
  // accounts for most of it.
  for (const want of order) {
    const kept = rankOf(build, want.treeId, want.talentId)
    if (kept >= want.rank) continue
    const shortened = want.rank > want.maxRank
    unplaced.push({
      name: want.name,
      requested: want.rank,
      kept,
      maxRank: want.maxRank,
      reason: shortened && kept === want.maxRank ? 'fewer-ranks' : 'rules',
    })
  }

  const placed = totalPoints(build)
  return { build, requested, placed, left: cls.rules.maxPoints - placed, unplaced }
}

/**
 * The headline above the list: "21 of 51 points placed. 6 talents did not fit.
 * 30 points left to spend."
 *
 * It no longer names talents. The names used to be squeezed into it, truncated
 * at six with "and N more", and then the full list was printed underneath
 * anyway - so the truncation bought nothing and the reasons were stated twice
 * in two different shapes (UX review round two, finding 3). One line per talent
 * now lives in the list; `unplacedLine` writes it.
 */
export function importReport(outcome: ImportOutcome): string {
  const parts = [`${outcome.placed} of ${points(outcome.requested)} placed.`]
  const n = outcome.unplaced.length
  if (n > 0) parts.push(`${n} talent${n === 1 ? '' : 's'} did not fit.`)
  if (outcome.left > 0) parts.push(`${points(outcome.left)} left to spend.`)
  return parts.join(' ')
}

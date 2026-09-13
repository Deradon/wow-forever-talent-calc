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

export interface UnplacedTalent {
  name: string
  points: number
  reason: 'not-in-forever' | 'clamped' | 'rules'
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
  maxRank: number
}

function foreverByName(cls: ClassData): Map<string, ForeverTalent> {
  const map = new Map<string, ForeverTalent>()
  for (const tree of cls.trees) {
    for (const talent of tree.talents) {
      const key = normalizeName(talent.name)
      if (!map.has(key)) map.set(key, { treeId: tree.id, talentId: talent.id, maxRank: talent.maxRank })
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
  const wanted = new Map<string, { treeId: string; talentId: string; rank: number }>()
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
        unplaced.push({ name, points: rank, reason: 'not-in-forever' })
        continue
      }
      const capped = Math.min(rank, target.maxRank)
      if (capped < rank) unplaced.push({ name, points: rank - capped, reason: 'clamped' })
      wanted.set(`${target.treeId}/${target.talentId}`, { treeId: target.treeId, talentId: target.talentId, rank: capped })
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
      while (rankOf(build, want.treeId, want.talentId) < want.rank && canAdd(cls, build, want.treeId, want.talentId).ok) {
        build = add(cls, build, want.treeId, want.talentId)
        changed = true
      }
    }
    if (!changed) break
  }

  for (const want of order) {
    const short = want.rank - rankOf(build, want.treeId, want.talentId)
    if (short <= 0) continue
    const tree = cls.trees.find((t) => t.id === want.treeId)
    const talent = tree?.talents.find((t) => t.id === want.talentId)
    unplaced.push({ name: talent?.name ?? want.talentId, points: short, reason: 'rules' })
  }

  const placed = totalPoints(build)
  return { build, requested, placed, left: cls.rules.maxPoints - placed, unplaced }
}

const REASON_TEXT: Record<UnplacedTalent['reason'], string> = {
  'not-in-forever': 'not in Forever',
  clamped: 'fewer ranks in Forever',
  rules: 'does not fit the tree',
}

/**
 * "37 of 41 points placed. Dropped: Sword Specialization (not in Forever),
 * Improved Battle Shout (not in Forever). 4 points left to spend."
 */
export function importReport(outcome: ImportOutcome): string {
  const parts = [`${outcome.placed} of ${outcome.requested} point${outcome.requested === 1 ? '' : 's'} placed.`]
  if (outcome.unplaced.length > 0) {
    const listed = outcome.unplaced.slice(0, 6).map((u) => `${u.name} (${REASON_TEXT[u.reason]})`)
    const rest = outcome.unplaced.length - listed.length
    parts.push(`Dropped: ${listed.join(', ')}${rest > 0 ? `, and ${rest} more` : ''}.`)
  }
  if (outcome.left > 0) parts.push(`${outcome.left} point${outcome.left === 1 ? '' : 's'} left to spend.`)
  return parts.join(' ')
}

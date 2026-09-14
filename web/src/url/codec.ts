/**
 * Build-link codec (brief section 5, DATA-SCHEMA.md section 8).
 *
 * One decimal digit per talent in the order frozen by the encoding version;
 * trailing zeros trimmed per tree; trees joined by `-`; trailing empty trees
 * omitted. Pure: no DOM, no globals; the registry is passed in.
 */
import { migrationChain, orderFor, type EncodingRegistry } from '../data/encoding'
import type { ClassData } from '../data/schema'
import { findTalent, findTree, rankOf, sanitize, totalPoints, withRank } from '../rules'
import type { Build, Violation } from '../rules'

export type NoticeKind = 'unknown-version' | 'clamped' | 'unknown-talent' | 'adjusted' | 'bad-string'

/**
 * One thing the link asked for that the current trees could not give.
 *
 * `message` is engineering prose and `detail` carries slugs, encoding
 * positions and rule reasons: neither is shown to a player. The player sees
 * `summarizeNotices()` only, one sentence with counts and no ids. The rest
 * goes to the console, which is where the round-two UX review (finding 1) put
 * it after a hand-edited `t=` stacked three developer bars on the page.
 */
export interface Notice {
  kind: NoticeKind
  message: string
  /** Talent points this notice accounts for; talents capped, for `clamped`. */
  count?: number
  /** Ids, positions and reasons. Console and `#/review/<class>` only. */
  detail?: string[]
  violations?: Violation[]
}

export interface Decoded {
  build: Build
  notices: Notice[]
}

/** The one bar a player sees, plus the lines that go to the console. */
export interface DecodeSummary {
  /** `unreadable` means nothing was recovered; `adjusted` means part was. */
  kind: 'unreadable' | 'adjusted'
  message: string
  detail: string[]
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

/**
 * Fold every decode notice into a single player-facing sentence. Returns
 * `undefined` when the link decoded cleanly, so the caller renders nothing.
 */
export function summarizeNotices(notices: Notice[]): DecodeSummary | undefined {
  if (notices.length === 0) return undefined
  const detail = notices.flatMap((n) => [n.message, ...(n.detail ?? [])])
  const unreadable = notices.some((n) => n.kind === 'bad-string' || n.kind === 'unknown-version')
  if (unreadable) {
    return { kind: 'unreadable', message: 'This link could not be read; showing an empty build.', detail }
  }
  const dropped = notices
    .filter((n) => n.kind === 'unknown-talent' || n.kind === 'adjusted')
    .reduce((sum, n) => sum + (n.count ?? 0), 0)
  const capped = notices.filter((n) => n.kind === 'clamped').reduce((sum, n) => sum + (n.count ?? 0), 0)
  const clauses: string[] = []
  if (dropped > 0) clauses.push(`${plural(dropped, 'point was', 'points were')} dropped`)
  if (capped > 0) clauses.push(`${plural(capped, 'talent', 'talents')} capped at ${capped === 1 ? 'its' : 'their'} Forever rank`)
  if (clauses.length === 0) {
    return { kind: 'adjusted', message: 'This link did not fit the current trees. The build below is what fits.', detail }
  }
  return {
    kind: 'adjusted',
    message: `This link did not fit the current trees: ${clauses.join(' and ')}. The build below is what fits.`,
    detail,
  }
}

export function encode(cls: ClassData, build: Build, registry: EncodingRegistry): string {
  const order = orderFor(registry, cls, cls.dataVersion)
  if (!order) return ''
  const parts = order.trees.map((treeId) => {
    const ids = order.order[treeId] ?? []
    const digits = ids.map((id) => String(Math.min(9, Math.max(0, rankOf(build, treeId, id)))))
    return digits.join('').replace(/0+$/, '')
  })
  while (parts.length > 0 && parts[parts.length - 1] === '') parts.pop()
  return parts.join('-')
}

export function decode(cls: ClassData, s: string, version: number, registry: EncodingRegistry): Decoded {
  const notices: Notice[] = []
  if (!Number.isInteger(version) || version < 1) {
    return { build: {}, notices: [{ kind: 'unknown-version', message: `Unknown data version ${String(version)}.` }] }
  }
  const order = orderFor(registry, cls, version)
  const chain = migrationChain(registry, version, cls.dataVersion)
  if (!order || !chain) {
    return {
      build: {},
      notices: [{ kind: 'unknown-version', message: `Unknown data version ${version}; started with an empty build.` }],
    }
  }
  if (s !== '' && !/^[0-9-]*$/.test(s)) {
    return {
      build: {},
      notices: [{ kind: 'bad-string', message: 'The build string contains invalid characters.', detail: [`t=${s}`] }],
    }
  }

  // 1. digits -> (treeId, talentId, rank) in the old version's order
  let ranks = new Map<string, { treeId: string; rank: number }>()
  const segments = s === '' ? [] : s.split('-')
  const unknown: string[] = []
  let unknownPoints = 0
  segments.forEach((segment, i) => {
    const treeId = order.trees[i]
    if (treeId === undefined) {
      if (segment !== '') {
        unknown.push(`tree #${i + 1}`)
        unknownPoints += [...segment].reduce((sum, c) => sum + (Number(c) || 0), 0)
      }
      return
    }
    const ids = order.order[treeId] ?? []
    for (let j = 0; j < segment.length; j++) {
      const digit = Number(segment[j])
      const id = ids[j]
      if (id === undefined) {
        if (digit > 0) {
          unknown.push(`${treeId} #${j + 1}`)
          unknownPoints += digit
        }
        continue
      }
      if (digit > 0) ranks.set(id, { treeId, rank: digit })
    }
  })
  if (unknown.length > 0) {
    notices.push({
      kind: 'unknown-talent',
      message: 'Ignored points for positions that no talent occupies.',
      count: unknownPoints,
      detail: unknown,
    })
  }

  // 2. migrations up to the current version (renamed: keep, removed: drop, moved: keep)
  for (const step of chain) {
    const m = step.classes[cls.class]
    if (!m) continue
    const next = new Map<string, { treeId: string; rank: number }>()
    for (const [id, entry] of ranks) {
      if (m.removed?.includes(id)) continue
      const newId = m.renamed?.[id] ?? id
      const moved = m.moved?.[newId] ?? m.moved?.[id]
      next.set(newId, { treeId: moved ? moved.to : entry.treeId, rank: entry.rank })
    }
    ranks = next
  }

  // 3. place into the current class file (talent ids are unique per class)
  let build: Build = {}
  const clamped: string[] = []
  const missing: string[] = []
  let missingPoints = 0
  for (const [id, entry] of ranks) {
    const tree = cls.trees.find((t) => findTalent(t, id)) ?? findTree(cls, entry.treeId)
    const talent = tree && findTalent(tree, id)
    if (!tree || !talent) {
      missing.push(id)
      missingPoints += entry.rank
      continue
    }
    let rank = entry.rank
    if (rank > talent.maxRank) {
      clamped.push(`${talent.name} ${rank} -> ${talent.maxRank}`)
      rank = talent.maxRank
    }
    build = withRank(build, tree.id, id, rank)
  }
  if (missing.length > 0) {
    notices.push({
      kind: 'unknown-talent',
      message: 'Ignored points for talents that are not in this class.',
      count: missingPoints,
      detail: missing,
    })
  }
  if (clamped.length > 0) {
    notices.push({
      kind: 'clamped',
      message: 'Reduced ranks above the maximum.',
      count: clamped.length,
      detail: clamped,
    })
  }

  // 4. sanitize under the rules
  const currentOrder = orderFor(registry, cls, cls.dataVersion)
  const result = sanitize(cls, build, currentOrder?.trees)
  if (result.dropped.length > 0) {
    const lost = totalPoints(build) - totalPoints(result.build)
    notices.push({
      kind: 'adjusted',
      message: 'Dropped points the talent rules do not allow.',
      count: lost,
      detail: result.dropped.map((v) => `${v.treeId}/${v.talentId}: ${v.reason}${v.detail ? ` (${v.detail})` : ''}`),
      violations: result.dropped,
    })
  }
  return { build: result.build, notices }
}

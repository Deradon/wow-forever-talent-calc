/**
 * Build-link codec (brief section 5, DATA-SCHEMA.md section 8).
 *
 * One decimal digit per talent in the order frozen by the encoding version;
 * trailing zeros trimmed per tree; trees joined by `-`; trailing empty trees
 * omitted. Pure: no DOM, no globals; the registry is passed in.
 */
import { migrationChain, orderFor, type EncodingRegistry } from '../data/encoding'
import type { ClassData } from '../data/schema'
import { findTalent, findTree, rankOf, sanitize, withRank } from '../rules'
import type { Build, Violation } from '../rules'

export type NoticeKind = 'unknown-version' | 'clamped' | 'unknown-talent' | 'adjusted' | 'bad-string'

export interface Notice {
  kind: NoticeKind
  message: string
  violations?: Violation[]
}

export interface Decoded {
  build: Build
  notices: Notice[]
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
    return { build: {}, notices: [{ kind: 'unknown-version', message: `Unknown data version ${version}.` }] }
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
    return { build: {}, notices: [{ kind: 'bad-string', message: 'The build string contains invalid characters.' }] }
  }

  // 1. digits -> (treeId, talentId, rank) in the old version's order
  let ranks = new Map<string, { treeId: string; rank: number }>()
  const segments = s === '' ? [] : s.split('-')
  const unknown: string[] = []
  segments.forEach((segment, i) => {
    const treeId = order.trees[i]
    if (treeId === undefined) {
      if (segment !== '') unknown.push(`tree #${i + 1}`)
      return
    }
    const ids = order.order[treeId] ?? []
    for (let j = 0; j < segment.length; j++) {
      const digit = Number(segment[j])
      const id = ids[j]
      if (id === undefined) {
        if (digit > 0) unknown.push(`${treeId} #${j + 1}`)
        continue
      }
      if (digit > 0) ranks.set(id, { treeId, rank: digit })
    }
  })
  if (unknown.length > 0) {
    notices.push({ kind: 'unknown-talent', message: `Ignored points for unknown talents (${unknown.join(', ')}).` })
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
  for (const [id, entry] of ranks) {
    const tree = cls.trees.find((t) => findTalent(t, id)) ?? findTree(cls, entry.treeId)
    const talent = tree && findTalent(tree, id)
    if (!tree || !talent) {
      missing.push(id)
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
    notices.push({ kind: 'unknown-talent', message: `Ignored points for unknown talents (${missing.join(', ')}).` })
  }
  if (clamped.length > 0) {
    notices.push({ kind: 'clamped', message: `Clamped ranks above the maximum (${clamped.join(', ')}).` })
  }

  // 4. sanitize under the rules
  const currentOrder = orderFor(registry, cls, cls.dataVersion)
  const result = sanitize(cls, build, currentOrder?.trees)
  if (result.dropped.length > 0) {
    const n = result.dropped.length
    notices.push({
      kind: 'adjusted',
      message: `Build adjusted: ${n} point${n === 1 ? '' : 's'} dropped because the link did not satisfy the talent rules.`,
      violations: result.dropped,
    })
  }
  return { build: result.build, notices }
}

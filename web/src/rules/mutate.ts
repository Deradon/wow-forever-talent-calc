import {
  defaultTreeOrder,
  findTalent,
  findTree,
  pointsInPage,
  pointsInRowsAbove,
  rankOf,
  totalPoints,
  withRank,
} from './points'
import type { Build, ClassData, TreeOrder, Verdict, Violation } from './types'
import { validate } from './validate'

export function canAdd(cls: ClassData, build: Build, treeId: string, talentId: string): Verdict {
  const tree = findTree(cls, treeId)
  const talent = tree && findTalent(tree, talentId)
  if (!tree || !talent) return { ok: false, reason: 'unknown-talent' }
  const { pointsPerRow, maxPoints, pointsPerPage } = cls.rules

  const rank = rankOf(build, treeId, talentId)
  if (rank >= talent.maxRank) return { ok: false, reason: 'maxed' }
  if (totalPoints(build) >= maxPoints) return { ok: false, reason: 'no-points' }
  const budget = pointsPerPage?.[tree.page]
  if (budget !== undefined && pointsInPage(cls, build, tree.page) >= budget) {
    return { ok: false, reason: 'page-full', detail: `${budget} points on page ${tree.page}` }
  }
  const needed = pointsPerRow * talent.row
  const above = pointsInRowsAbove(tree, build, talent.row)
  if (above < needed) {
    return { ok: false, reason: 'row-locked', detail: `${needed} points in ${tree.name}` }
  }
  for (const req of talent.requires ?? []) {
    if (rankOf(build, treeId, req.talent) < req.rank) {
      const target = findTalent(tree, req.talent)
      return { ok: false, reason: 'prereq', detail: `${req.rank} point${req.rank === 1 ? '' : 's'} in ${target?.name ?? req.talent}` }
    }
  }
  return { ok: true }
}

/**
 * Remove is allowed when rank > 0 and the simulated removal introduces no
 * new violation (simulate, do not special-case). Violations that were
 * already present before the removal are not held against it.
 */
export function canRemove(cls: ClassData, build: Build, treeId: string, talentId: string): Verdict {
  const tree = findTree(cls, treeId)
  const talent = tree && findTalent(tree, talentId)
  if (!tree || !talent) return { ok: false, reason: 'unknown-talent' }
  const rank = rankOf(build, treeId, talentId)
  if (rank <= 0) return { ok: false, reason: 'not-spent' }

  const before = new Set(validate(cls, build).map(keyOf))
  const after = validate(cls, withRank(build, treeId, talentId, rank - 1)).filter((v) => !before.has(keyOf(v)))
  const first = after[0]
  if (!first) return { ok: true }
  if (first.reason === 'row-locked') {
    return { ok: false, reason: 'would-orphan', detail: `${first.talentId} would lose its row requirement` }
  }
  return { ok: false, reason: first.reason, detail: first.talentId }
}

function keyOf(v: Violation): string {
  return `${v.treeId}/${v.talentId}/${v.reason}`
}

/** Adds one point; returns the same build object when the verdict fails. */
export function add(cls: ClassData, build: Build, treeId: string, talentId: string): Build {
  if (!canAdd(cls, build, treeId, talentId).ok) return build
  return withRank(build, treeId, talentId, rankOf(build, treeId, talentId) + 1)
}

/** Removes one point; returns the same build object when the verdict fails. */
export function remove(cls: ClassData, build: Build, treeId: string, talentId: string): Build {
  if (!canRemove(cls, build, treeId, talentId).ok) return build
  return withRank(build, treeId, talentId, rankOf(build, treeId, talentId) - 1)
}

export function resetTree(build: Build, treeId: string): Build {
  const next: Build = { ...build }
  delete next[treeId]
  return next
}

export function resetAll(): Build {
  return {}
}

/**
 * Makes an arbitrary build valid by walking trees in `order` (default: page
 * order), rows top-down, dropping ranks until `validate` is empty. Structural
 * violations (unknown, row-locked, prereq, over maxRank) are dropped where
 * they occur; budget violations (no-points, page-full) drop from the end of
 * the walk so the top of the build survives.
 */
export function sanitize(
  cls: ClassData,
  build: Build,
  order: TreeOrder = defaultTreeOrder(cls),
): { build: Build; dropped: Violation[] } {
  let current = build
  const dropped: Violation[] = []
  const walk = walkOrder(cls, order, current)

  for (let guard = 0; guard < 10_000; guard++) {
    const violations = validate(cls, current)
    if (violations.length === 0) break
    const structural = violations
      .filter((v) => v.treeId !== '')
      .sort((a, b) => walkIndex(walk, a) - walkIndex(walk, b))
    const first = structural[0]
    if (first) {
      const talent = findTree(cls, first.treeId) && findTalent(findTree(cls, first.treeId)!, first.talentId)
      const rank = rankOf(current, first.treeId, first.talentId)
      const target = first.reason === 'maxed' && talent ? talent.maxRank : 0
      current = withRank(current, first.treeId, first.talentId, target)
      dropped.push({ ...first, detail: first.detail ?? `dropped ${rank - target}` })
      continue
    }
    // Budget violation: take one point from the last spent talent in walk order.
    const budget = violations[0]!
    const last = [...walk].reverse().find((k) => rankOf(current, k.treeId, k.talentId) > 0)
    if (!last) break
    current = withRank(current, last.treeId, last.talentId, rankOf(current, last.treeId, last.talentId) - 1)
    dropped.push({ treeId: last.treeId, talentId: last.talentId, reason: budget.reason, detail: budget.detail })
  }
  return { build: current, dropped }
}

interface WalkKey {
  treeId: string
  talentId: string
}

function walkOrder(cls: ClassData, order: TreeOrder, build: Build): WalkKey[] {
  const keys: WalkKey[] = []
  const seenTrees = new Set<string>()
  const treeIds = [...order, ...cls.trees.map((t) => t.id), ...Object.keys(build)]
  for (const treeId of treeIds) {
    if (seenTrees.has(treeId)) continue
    seenTrees.add(treeId)
    const tree = findTree(cls, treeId)
    if (tree) {
      const sorted = [...tree.talents].sort((a, b) => a.row - b.row || a.col - b.col)
      for (const t of sorted) keys.push({ treeId, talentId: t.id })
      for (const talentId of Object.keys(build[treeId] ?? {})) {
        if (!findTalent(tree, talentId)) keys.push({ treeId, talentId })
      }
    } else {
      for (const talentId of Object.keys(build[treeId] ?? {})) keys.push({ treeId, talentId })
    }
  }
  return keys
}

function walkIndex(walk: WalkKey[], v: Violation): number {
  const i = walk.findIndex((k) => k.treeId === v.treeId && k.talentId === v.talentId)
  return i === -1 ? Number.MAX_SAFE_INTEGER : i
}

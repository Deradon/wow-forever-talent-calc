import { findTalent, findTree, pointsInPage, pointsInRowsAbove, rankOf, totalPoints } from './points'
import type { Build, ClassData, Violation } from './types'

/**
 * Every rule broken by `build`, in tree order of the class file, rows
 * top-down. Empty array = valid build. All thresholds come from `cls.rules`.
 */
export function validate(cls: ClassData, build: Build): Violation[] {
  const out: Violation[] = []
  const { pointsPerRow, maxPoints, pointsPerPage } = cls.rules

  for (const treeId of Object.keys(build)) {
    const tree = findTree(cls, treeId)
    if (!tree) {
      for (const talentId of Object.keys(build[treeId] ?? {})) {
        out.push({ treeId, talentId, reason: 'unknown-talent', detail: `unknown tree ${treeId}` })
      }
      continue
    }
    const spent = build[treeId] ?? {}
    const entries = Object.entries(spent)
      .filter(([, rank]) => rank > 0)
      .map(([talentId, rank]) => ({ talentId, rank, talent: findTalent(tree, talentId) }))
      .sort((a, b) => (a.talent?.row ?? 99) - (b.talent?.row ?? 99) || (a.talent?.col ?? 99) - (b.talent?.col ?? 99))

    for (const { talentId, rank, talent } of entries) {
      if (!talent) {
        out.push({ treeId, talentId, reason: 'unknown-talent' })
        continue
      }
      if (rank > talent.maxRank) {
        out.push({ treeId, talentId, reason: 'maxed', detail: `${rank} > maxRank ${talent.maxRank}` })
      }
      const needed = pointsPerRow * talent.row
      const above = pointsInRowsAbove(tree, build, talent.row)
      if (above < needed) {
        out.push({ treeId, talentId, reason: 'row-locked', detail: `${above}/${needed} points above row ${talent.row}` })
      }
      for (const req of talent.requires ?? []) {
        if (rankOf(build, treeId, req.talent) < req.rank) {
          out.push({ treeId, talentId, reason: 'prereq', detail: `needs ${req.talent} ${req.rank}` })
        }
      }
    }
  }

  const total = totalPoints(build)
  if (total > maxPoints) {
    out.push({ treeId: '', talentId: '', reason: 'no-points', detail: `${total} > maxPoints ${maxPoints}` })
  }
  if (pointsPerPage) {
    for (const page of cls.pages) {
      const budget = pointsPerPage[page.id]
      if (budget === undefined) continue
      const n = pointsInPage(cls, build, page.id)
      if (n > budget) {
        out.push({ treeId: '', talentId: '', reason: 'page-full', detail: `${n} > ${budget} on page ${page.id}` })
      }
    }
  }
  return out
}

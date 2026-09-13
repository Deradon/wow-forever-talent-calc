/**
 * Pure build-summary model and text export (brief "UI and UX improvements",
 * idea 1). No DOM, no React: the panel renders `summarizeBuild`, the
 * "Copy as text" button copies `buildAsText`.
 */
import type { ClassData } from '../data/schema'
import { pointsInTree, rankOf, requiredLevel, totalPoints, type Build } from '../rules'

export interface SummaryTalent {
  treeId: string
  id: string
  name: string
  rank: number
  maxRank: number
  row: number
  col: number
}

export interface SummaryTree {
  id: string
  name: string
  points: number
  talents: SummaryTalent[]
}

export interface BuildSummary {
  className: string
  /** Every tree of the class, in class-file order, spent or not. */
  trees: SummaryTree[]
  /** Only the trees with at least one point, for the text export and the panel. */
  spentTrees: SummaryTree[]
  spread: string
  spent: number
  maxPoints: number
  left: number
  level: number
}

/** Talents with points, grouped by tree, each tree in row order then column. */
export function summarizeBuild(cls: ClassData, build: Build): BuildSummary {
  const trees: SummaryTree[] = cls.trees.map((tree) => ({
    id: tree.id,
    name: tree.name,
    points: pointsInTree(build, tree.id),
    talents: tree.talents
      .filter((t) => rankOf(build, tree.id, t.id) > 0)
      .map((t) => ({
        treeId: tree.id,
        id: t.id,
        name: t.name,
        rank: rankOf(build, tree.id, t.id),
        maxRank: t.maxRank,
        row: t.row,
        col: t.col,
      }))
      .sort((a, b) => a.row - b.row || a.col - b.col),
  }))
  const spent = totalPoints(build)
  return {
    className: cls.className,
    trees,
    spentTrees: trees.filter((t) => t.points > 0),
    spread: trees.map((t) => t.points).join('/'),
    spent,
    maxPoints: cls.rules.maxPoints,
    left: cls.rules.maxPoints - spent,
    level: requiredLevel(spent, cls.rules),
  }
}

/** `Warrior 31/0/20 - level 60`, the summary column's heading. */
export function summaryTitle(s: BuildSummary): string {
  return `${s.className} ${s.spread} - level ${s.level}`
}

export const SITE_NAME = 'WoW Forever'

/**
 * A Discord-ready block: class and spread, one line per spent tree with every
 * talent as `Name rank/max`, then the link. Plain text on purpose - no
 * markdown, so it survives a paste into a forum, a wiki or a code fence.
 */
export function buildAsText(cls: ClassData, build: Build, link?: string): string {
  const s = summarizeBuild(cls, build)
  const lines: string[] = [`${s.className} ${s.spread} (level ${s.level}) - ${SITE_NAME}`]
  if (s.spentTrees.length === 0) {
    lines.push('No points spent yet.')
  } else {
    for (const tree of s.spentTrees) {
      lines.push(`${tree.name} (${tree.points}): ${tree.talents.map((t) => `${t.name} ${t.rank}/${t.maxRank}`).join(', ')}`)
    }
  }
  if (s.left > 0 && s.spent > 0) lines.push(`${s.left} point${s.left === 1 ? '' : 's'} left.`)
  if (link) lines.push(link)
  return lines.join('\n')
}

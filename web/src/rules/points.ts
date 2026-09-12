import type { Build, ClassData, Talent, Tree, TreeOrder } from './types'

export function rankOf(build: Build, treeId: string, talentId: string): number {
  return build[treeId]?.[talentId] ?? 0
}

export function pointsInTree(build: Build, treeId: string): number {
  const tree = build[treeId]
  if (!tree) return 0
  let n = 0
  for (const v of Object.values(tree)) n += v
  return n
}

/** Points spent in rows strictly above `row` of the given tree. */
export function pointsInRowsAbove(tree: Tree, build: Build, row: number): number {
  const spent = build[tree.id]
  if (!spent) return 0
  let n = 0
  for (const t of tree.talents) {
    if (t.row < row) n += spent[t.id] ?? 0
  }
  return n
}

export function totalPoints(build: Build): number {
  let n = 0
  for (const treeId of Object.keys(build)) n += pointsInTree(build, treeId)
  return n
}

export function pointsInPage(cls: ClassData, build: Build, pageId: string): number {
  let n = 0
  for (const tree of cls.trees) {
    if (tree.page === pageId) n += pointsInTree(build, tree.id)
  }
  return n
}

export function findTree(cls: ClassData, treeId: string): Tree | undefined {
  return cls.trees.find((t) => t.id === treeId)
}

export function findTalent(tree: Tree, talentId: string): Talent | undefined {
  return tree.talents.find((t) => t.id === talentId)
}

/** Tree ids in page order, then `tree.order`; the default codec walk. */
export function defaultTreeOrder(cls: ClassData): TreeOrder {
  const pageIndex = new Map(cls.pages.map((p, i) => [p.id, i]))
  return [...cls.trees]
    .sort((a, b) => {
      const pa = pageIndex.get(a.page) ?? 99
      const pb = pageIndex.get(b.page) ?? 99
      return pa - pb || a.order - b.order
    })
    .map((t) => t.id)
}

/** Talent ids of one tree, row-major; the default codec order. */
export function rowMajor(tree: Tree): string[] {
  return [...tree.talents].sort((a, b) => a.row - b.row || a.col - b.col).map((t) => t.id)
}

export function emptyBuild(): Build {
  return {}
}

/** Structural copy of a build with a single rank replaced. Drops zero entries. */
export function withRank(build: Build, treeId: string, talentId: string, rank: number): Build {
  const tree = { ...(build[treeId] ?? {}) }
  if (rank <= 0) delete tree[talentId]
  else tree[talentId] = rank
  const next: Build = { ...build }
  if (Object.keys(tree).length === 0) delete next[treeId]
  else next[treeId] = tree
  return next
}

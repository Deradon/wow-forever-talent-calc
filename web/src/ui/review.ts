import type { Talent, Tree } from '../data/schema'

/** Review-queue threshold from DATA-SCHEMA.md section 4.5. */
export const REVIEW_THRESHOLD = 0.8

export function needsReview(t: { source?: { confidence?: number; reviewed?: boolean } }): boolean {
  const s = t.source
  if (!s || s.reviewed) return false
  return s.confidence !== undefined && s.confidence < REVIEW_THRESHOLD
}

export interface ReviewRow {
  tree: Tree
  talent: Talent
  confidence: number
  group: 0 | 1 | 2
}

/**
 * Order for the review route: unreviewed low-confidence records first, then
 * other unreviewed ones, then reviewed; within a group by confidence
 * ascending, then tree order, row, column. Pure; unit tested.
 */
export function reviewRows(trees: Tree[]): ReviewRow[] {
  const treeIndex = new Map(trees.map((t, i) => [t.id, i]))
  const rows: ReviewRow[] = trees.flatMap((tree) =>
    tree.talents.map((talent) => {
      const confidence = talent.source.confidence ?? 1
      const group: ReviewRow['group'] = talent.source.reviewed ? 2 : needsReview(talent) ? 0 : 1
      return { tree, talent, confidence, group }
    }),
  )
  return rows.sort(
    (a, b) =>
      a.group - b.group ||
      a.confidence - b.confidence ||
      treeIndex.get(a.tree.id)! - treeIndex.get(b.tree.id)! ||
      a.talent.row - b.talent.row ||
      a.talent.col - b.talent.col,
  )
}

/** `h:mm:ss` into the stream for a `source.t` value. */
export function streamStamp(t: number): string {
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const sec = Math.floor(t % 60)
  return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

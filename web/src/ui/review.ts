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

// --- review route filtering and reading diffs (pure; unit tested) ----------

export type ReviewFlag = 'all' | 'queue' | 'unreviewed' | 'manual' | 'crops'

export interface ReviewFilter {
  flag: ReviewFlag
  /** Tree id, or "all". */
  tree: string
  /** Free text matched against name, id and description. */
  query: string
}

export const ALL_FLAGS: ReviewFlag[] = ['all', 'queue', 'unreviewed', 'manual', 'crops']

export function matchesFlag(row: ReviewRow, flag: ReviewFlag): boolean {
  switch (flag) {
    case 'queue':
      return row.group === 0
    case 'unreviewed':
      return !row.talent.source.reviewed
    case 'manual':
      return row.talent.ranksSource === 'manual'
    case 'crops':
      return row.talent.iconSource === 'crop'
    default:
      return true
  }
}

/** Rows the review route should show; order is left as `reviewRows` set it. */
export function filterRows(rows: ReviewRow[], filter: ReviewFilter): ReviewRow[] {
  const q = filter.query.trim().toLowerCase()
  return rows.filter((row) => {
    if (!matchesFlag(row, filter.flag)) return false
    if (filter.tree !== 'all' && row.tree.id !== filter.tree) return false
    if (!q) return true
    const hay = `${row.talent.name} ${row.talent.id} ${row.talent.description}`.toLowerCase()
    return hay.includes(q)
  })
}

export type DiffOp = { type: 'same' | 'add' | 'del'; text: string }

/**
 * Word-level diff of two readings of the same tooltip, so a reviewer sees what
 * the second reader actually read instead of the words "differs in
 * description". Longest common subsequence over whitespace-separated tokens;
 * the strings involved are one tooltip long, so the O(n*m) table is fine.
 */
export function diffWords(a: string, b: string): DiffOp[] {
  const left = a.split(/\s+/).filter(Boolean)
  const right = b.split(/\s+/).filter(Boolean)
  const n = left.length
  const m = right.length
  const lcs: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i]![j] = left[i] === right[j] ? lcs[i + 1]![j + 1]! + 1 : Math.max(lcs[i + 1]![j]!, lcs[i]![j + 1]!)
    }
  }
  const ops: DiffOp[] = []
  const push = (type: DiffOp['type'], text: string) => {
    const last = ops[ops.length - 1]
    if (last && last.type === type) last.text += ` ${text}`
    else ops.push({ type, text })
  }
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (left[i] === right[j]) {
      push('same', left[i]!)
      i++
      j++
    } else if (lcs[i + 1]![j]! >= lcs[i]![j + 1]!) {
      push('del', left[i]!)
      i++
    } else {
      push('add', right[j]!)
      j++
    }
  }
  for (; i < n; i++) push('del', left[i]!)
  for (; j < m; j++) push('add', right[j]!)
  return ops
}

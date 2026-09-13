/**
 * "New in Forever" markers: the read side of `src/data/classic-diff.json`,
 * which `scripts/gen-data-index.mjs` generates by diffing `data/talents/*` in
 * the Classic Era prior (brief `docs/briefs/ui-improvements.md`, idea 3).
 *
 * The generated file lists only the talents that actually changed. A class that
 * has a diff therefore reports `same` for every talent it does not mention; a
 * class that has none (the tinker example) reports `undefined` everywhere, so
 * an example class never claims that all of its talents are new.
 */
import diff from '../data/classic-diff.json'

export type ChangeStatus = 'new' | 'moved' | 'rank-changed' | 'same'

export interface PriorCell {
  tree: string
  treeName: string
  row: number
  col: number
  maxRank: number
}

export interface Change {
  status: ChangeStatus
  prior?: PriorCell
}

interface ClassDiff {
  counts: Record<string, number>
  talents: Record<string, { status: string; prior?: PriorCell }>
  removed: (PriorCell & { id: string; name: string })[]
}

const CLASSES = diff.classes as unknown as Record<string, ClassDiff>

/** True when this class was compared against Classic at all. */
export function hasClassicDiff(classId: string): boolean {
  return classId in CLASSES
}

/** Number of talents in the class that are new, moved or re-ranked. */
export function changedCount(classId: string): number {
  const c = CLASSES[classId]?.counts
  if (!c) return 0
  return (c.new ?? 0) + (c.moved ?? 0) + (c['rank-changed'] ?? 0)
}

/** Classic talents with no counterpart in Forever - for a later `#/changes`. */
export function removedTalents(classId: string): (PriorCell & { id: string; name: string })[] {
  return CLASSES[classId]?.removed ?? []
}

/**
 * How this talent stands against Classic. `undefined` means "not comparable"
 * (no prior for this class), which is different from `same`.
 */
export function changeOf(classId: string, talentId: string): Change | undefined {
  const cls = CLASSES[classId]
  if (!cls) return undefined
  const entry = cls.talents[talentId]
  if (!entry) return { status: 'same' }
  return { status: entry.status as ChangeStatus, prior: entry.prior }
}

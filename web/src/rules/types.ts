/**
 * Types for the pure rules engine. No DOM, no React.
 */
import type { ClassData, Talent, Tree } from '../data/schema'

export type { ClassData, Talent, Tree }

/** Points spent per tree per talent. Missing entries mean 0. */
export type Build = Record<string, Record<string, number>>

export type Reason =
  | 'maxed' // rank == maxRank
  | 'no-points' // totalPoints >= maxPoints
  | 'page-full' // rules.pointsPerPage budget of the tree's page reached
  | 'row-locked' // pointsInRowsAbove < pointsPerRow * row
  | 'prereq' // a `requires` entry is not met (or removing would break one)
  | 'would-orphan' // removing would leave a lower row without enough points above
  | 'not-spent' // nothing to remove
  | 'unknown-talent' // talent or tree id not in the class file

export type Verdict = { ok: true } | { ok: false; reason: Reason; detail?: string }

export interface Violation {
  treeId: string
  talentId: string
  reason: Reason
  detail?: string
}

/** Tree ids in the order the URL codec walks them (pages flattened). */
export type TreeOrder = string[]

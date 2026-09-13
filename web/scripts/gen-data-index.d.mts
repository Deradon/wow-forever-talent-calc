/** Types for the generator so `tsc -b` can check src/data/generated.test.ts. */
export interface ClassIndexTree {
  id: string
  name: string
  talents: number
}

export interface ClassIndexEntry {
  id: string
  origin: 'talents' | 'examples' | 'fixtures'
  className: string
  dataSource: string
  maxPoints: number
  talents: number
  reviewed: number
  needsReview: number
  trees: ClassIndexTree[]
}

/** One talent's standing against Classic Era; `same` is never written out. */
export type ChangeStatus = 'new' | 'moved' | 'rank-changed' | 'same'

export interface PriorCell {
  tree: string
  treeName: string
  row: number
  col: number
  maxRank: number
}

export interface ChangeEntry {
  status: ChangeStatus
  /** The Classic counterpart; absent exactly when the talent is new. */
  prior?: PriorCell
}

export interface RemovedTalent extends PriorCell {
  id: string
  name: string
}

export interface ClassDiff {
  counts: Record<'new' | 'moved' | 'rank-changed' | 'same' | 'removed', number>
  /** Keyed by Forever talent id; unchanged talents are omitted. */
  talents: Record<string, ChangeEntry>
  removed: RemovedTalent[]
}

export interface ClassicDiff {
  prior: string
  totals: Record<'new' | 'moved' | 'rank-changed' | 'same' | 'removed', number>
  classes: Record<string, ClassDiff>
}

export declare const webRoot: string
export declare const repoRoot: string
export declare function buildClassesIndex(classes: unknown[]): ClassIndexEntry[]
export declare function collectIconCrops(classes: unknown[]): string[]
export declare function renderIconCrops(paths: string[]): string
export declare function normalizeName(name: string): string
export declare function classifyTalent(
  current: { tree: string; row: number; col: number; maxRank: number },
  prior: PriorCell | undefined,
): ChangeEntry
export declare function diffClass(cls: unknown, priorClass: unknown): ClassDiff
export declare function buildClassicDiff(classes: unknown[], prior: unknown): ClassicDiff
export declare function generate(root?: string): boolean
export declare function expected(): { index: string; crops: string; classicDiff: string }

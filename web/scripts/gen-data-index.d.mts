/** Types for the generator so `tsc -b` can check src/data/generated.test.ts. */
import type { CompactDiff } from './diffWords.mjs'

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
export type ChangeStatus = 'new' | 'moved' | 'rank-changed' | 'text-changed' | 'values-changed' | 'same'

/** Which kind of description change a talent has, whatever its headline status. */
export type TextChange = 'text' | 'values'

/** `["15%", "20%"]`: what one number said in Classic and says in Forever. */
export type ValuePair = [string, string]

export interface PriorCell {
  tree: string
  treeName: string
  row: number
  col: number
  maxRank: number
  /** Set only when the talent really changed tree, i.e. after `matchTrees`. */
  movedTree?: boolean
  /** Set when the row changed. A move is a change of tree or row, never of column alone. */
  movedRow?: boolean
  /**
   * Set when only the column inside the same row changed. Such a talent keeps its real
   * status (`same`, `text-changed`, ...); the flag is here so the review route can still
   * show where it used to sit.
   */
  movedCol?: boolean
}

export interface ChangeEntry {
  status: ChangeStatus
  /** The Classic counterpart; absent exactly when the talent is new. */
  prior?: PriorCell
  /** Set whenever the rank-1 sentence differs at all, whatever `status` says. */
  textChange?: TextChange
  /** Present with `textChange: "values"`: only the numbers that differ. */
  values?: ValuePair[]
  /** The Forever row, 0-based. Written for a row move only, so the change line can name both ends. */
  row?: number
}

/** The lazily fetched half, one entry per talent whose sentence differs. */
export interface ClassicText {
  /** The Classic Era rank-1 sentence, verbatim. */
  text: string
  /** Classic values per rank, e.g. `"2/4/6/8/10"`. */
  series?: string
  /** `[op, text]` runs: `=` keep, `-` Classic only, `+` Forever only. */
  diff: CompactDiff
  values?: ValuePair[]
}

export interface RemovedTalent extends PriorCell {
  id: string
  name: string
}

export type CountKey = ChangeStatus | 'removed'

export interface ClassDiff {
  counts: Record<CountKey, number>
  /** Keyed by Forever talent id; unchanged talents are omitted. */
  talents: Record<string, ChangeEntry>
  removed: RemovedTalent[]
  /** Only on the raw `diffClass` result; split out before either file is written. */
  text?: Record<string, ClassicText>
}

export interface ClassicDiff {
  prior: string
  totals: Record<CountKey, number>
  classes: Record<string, ClassDiff>
}

export interface PriorTree {
  id: string
  name: string
  talents?: { name: string }[]
}

export declare const webRoot: string
export declare const repoRoot: string
export declare function buildClassesIndex(classes: unknown[]): ClassIndexEntry[]
export declare function collectIconCrops(classes: unknown[]): string[]
export declare function renderIconCrops(paths: string[]): string
export declare function normalizeName(name: string): string
export declare function normalizeText(text: string): string
export declare function maskNumbers(text: string): { masked: string; values: string[] }
export declare function compareDescriptions(
  classicText: string,
  foreverText: string,
): { kind: 'values'; values: ValuePair[]; diff: CompactDiff } | { kind: 'text'; diff: CompactDiff } | undefined
export declare function rankSeries(ranks: unknown): string | undefined
export declare function matchTrees(currentTrees: PriorTree[], priorTrees: PriorTree[]): Map<string, string>
export declare function cellBase(talents: { row: number; col: number }[]): { row: number; col: number }
export declare const STATUSES: ChangeStatus[]
export declare function classifyTalent(
  current: { tree: string; row: number; col: number; maxRank: number; text?: string },
  prior: (PriorCell & { sameTree?: boolean; text?: string; series?: string }) | undefined,
): ChangeEntry & { classic?: ClassicText }
export declare function diffClass(cls: unknown, priorClass: unknown): ClassDiff
export declare function buildClassic(
  classes: unknown[],
  prior: unknown,
): { diff: ClassicDiff; text: Record<string, Record<string, ClassicText>> }
export declare function buildClassicDiff(classes: unknown[], prior: unknown): ClassicDiff
export declare function buildClassicText(classes: unknown[], prior: unknown): Record<string, Record<string, ClassicText>>
export declare function generate(root?: string): boolean
export declare function expected(): { index: string; crops: string; classicDiff: string; classicText: string }

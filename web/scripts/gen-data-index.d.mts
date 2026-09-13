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

export declare const webRoot: string
export declare const repoRoot: string
export declare function buildClassesIndex(classes: unknown[]): ClassIndexEntry[]
export declare function collectIconCrops(classes: unknown[]): string[]
export declare function renderIconCrops(paths: string[]): string
export declare function generate(root?: string): boolean
export declare function expected(): { index: string; crops: string }

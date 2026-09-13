/** Types for the generator so `tsc -b` can check src/data/classicIndex.test.ts. */
export interface ClassicIndexTree {
  id: string
  name: string
  talents: [string, number][]
}

export interface ClassicIndexClass {
  className: string
  trees: ClassicIndexTree[]
}

export interface ClassicIndexFile {
  source: string
  classes: Record<string, ClassicIndexClass>
}

export declare function buildIndex(prior: unknown): ClassicIndexFile
export declare function generate(): { text: string; changed: boolean }
export declare function priorPath(): string
export declare function outPath(): string

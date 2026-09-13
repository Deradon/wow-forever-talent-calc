/** Types for the shared word diff, so `tsc -b` can check src/ui/review.ts. */
export type DiffOp = { type: 'same' | 'add' | 'del'; text: string }

/** `[op, text]` pairs: `=` keep, `-` Classic only, `+` Forever only. */
export type CompactDiff = [string, string][]

export declare function diffWords(a: string, b: string): DiffOp[]
export declare function compactDiff(a: string, b: string): CompactDiff

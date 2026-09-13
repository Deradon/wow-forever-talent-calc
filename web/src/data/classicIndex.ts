/**
 * The Classic Era tab/talent order, generated from
 * data/prior/classic-era/talents.json by scripts/gen-classic-index.mjs.
 *
 * Only the import flow needs it (a Wowhead Classic build string is one digit
 * per talent, per tab, row-major), so it is reached through a dynamic
 * `import()` and lands in its own chunk that a player only fetches after
 * pasting such a string.
 */
export interface ClassicTree {
  id: string
  name: string
  /** `[name, maxRank]`, row-major: the digit order of one Wowhead tab segment. */
  talents: [string, number][]
}

export interface ClassicClass {
  className: string
  trees: ClassicTree[]
}

export interface ClassicIndex {
  source: string
  classes: Record<string, ClassicClass>
}

let cached: Promise<ClassicIndex> | undefined

export function loadClassicIndex(): Promise<ClassicIndex> {
  cached ??= import('./classic-index.json').then((m) => m.default as unknown as ClassicIndex)
  return cached
}

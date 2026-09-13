/**
 * Runtime-facing mirror of docs/DATA-SCHEMA.md (schema version 1): plain types
 * plus `renderDescription`. Deliberately free of zod, so the ~25 kB gzip of
 * validator does not ship to every visitor (performance review P-3).
 *
 * The zod mirror and `parseClass` live in schema.zod.ts and run in dev, in the
 * unit tests and in `validate-data`; schema.zod.ts type-asserts that its
 * inferred shapes still satisfy the types below, so the two cannot drift.
 *
 * The JSON Schema in data/schema/class.schema.json stays authoritative and
 * rejects unknown keys; these types, like the zod mirror, let unknown keys pass
 * so the data lead can add fields without breaking the app.
 */
export const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/

/** Page ids; extend when the UI shows more tabs (DATA-SCHEMA.md section 3). */
export type PageId = 'primary' | 'secondary'

export interface Reading {
  reader: string
  name?: string
  description?: string
  maxRank?: number
  confidence?: number
}

export interface Source {
  kind: 'video' | 'datamined' | 'manual'
  video?: string
  t?: number
  frame?: number
  crop?: string
  confidence?: number
  reader?: string
  readings?: Reading[]
  build?: string
  talentId?: number
  reviewed: boolean
  reviewedBy?: string
  reviewedAt?: string
  note?: string
}

export interface Requirement {
  talent: string
  rank: number
}

export interface RanksPrior {
  classicTalentId: number
  classicSpellIds: number[]
  match: 'exact-name' | 'fuzzy-name' | 'description'
  similarity: number
}

/** One rank: slot values for the `{n}` placeholders, or a full sentence. */
export type Rank = (number | string)[] | string

export interface Talent {
  id: string
  name: string
  row: number
  col: number
  /** One decimal digit per talent in build links; the schema caps this at 9. */
  maxRank: number
  icon: string
  iconSource: 'classic' | 'crop' | 'datamined' | 'manual'
  iconCrop?: string
  description: string
  ranks: Rank[]
  ranksObserved: number[]
  ranksSource: 'observed' | 'classic-prior' | 'extrapolated' | 'manual'
  ranksPrior?: RanksPrior
  ranksNote?: string
  requires?: Requirement[]
  capstone?: boolean
  spellIds?: number[]
  tags?: string[]
  source: Source
}

export interface Tree {
  id: string
  name: string
  page: PageId
  order: number
  icon: string
  background?: string
  rows: number
  cols: number
  role?: 'tank' | 'healer' | 'dps' | 'hybrid'
  datamined?: { talentTabId: number; build: string }
  source?: Source
  talents: Talent[]
}

export interface Page {
  id: PageId
  name: string
  note?: string
}

export interface Rules {
  pointsPerRow: number
  maxPoints: number
  firstPointLevel: number
  maxLevel: number
  pointsPerPage?: Record<string, number>
  rulesSource: 'observed' | 'classic-prior' | 'assumed'
}

export interface ClassData {
  $schema?: string
  schemaVersion: 1
  class: string
  className: string
  dataVersion: number
  dataSource: 'video' | 'datamined' | 'mixed' | 'manual'
  generatedAt: string
  rules: Rules
  pages: Page[]
  trees: Tree[]
  notes?: string[]
}

/**
 * Render a talent's description at rank index `r` (0 = rank 1) per
 * DATA-SCHEMA.md section 5. Out-of-range indices clamp into `ranks`.
 */
export function renderDescription(talent: Pick<Talent, 'description' | 'ranks'>, r: number): string {
  const idx = Math.max(0, Math.min(talent.ranks.length - 1, r))
  const rank = talent.ranks[idx]
  if (rank === undefined) return talent.description
  if (typeof rank === 'string') return rank
  return talent.description.replace(/\{(\d+)\}/g, (_, i: string) => String(rank[Number(i)] ?? `{${i}}`))
}

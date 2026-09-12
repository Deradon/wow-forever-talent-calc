/**
 * Zod mirror of docs/DATA-SCHEMA.md (schema version 1).
 *
 * The JSON Schema in data/schema/class.schema.json is authoritative and
 * rejects unknown keys; this mirror deliberately lets unknown keys pass
 * through (looseObject) so the data lead can add fields without breaking the
 * app. A Vitest (schema.test.ts) checks required keys and enums against the
 * JSON Schema when that file exists.
 */
import { z } from 'zod'

export const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/
const slug = z.string().min(1).max(64).regex(SLUG)
/** Page ids; extend when the UI shows more tabs (DATA-SCHEMA.md section 3). */
export const PageIdSchema = z.enum(['primary', 'secondary'])

export const SourceSchema = z.looseObject({
  kind: z.enum(['video', 'datamined', 'manual']),
  video: z.string().optional(),
  t: z.number().min(0).optional(),
  frame: z.int().min(0).optional(),
  crop: z.string().optional(),
  confidence: z.number().min(0).max(1).optional(),
  reader: z.string().optional(),
  readings: z
    .array(
      z.looseObject({
        reader: z.string(),
        name: z.string().optional(),
        description: z.string().optional(),
        maxRank: z.int().optional(),
        confidence: z.number().optional(),
      }),
    )
    .optional(),
  build: z.string().optional(),
  talentId: z.int().optional(),
  reviewed: z.boolean(),
  reviewedBy: z.string().optional(),
  reviewedAt: z.string().optional(),
  note: z.string().optional(),
})

export const RequirementSchema = z.looseObject({
  talent: slug,
  rank: z.int().min(1),
})

export const RanksPriorSchema = z.looseObject({
  classicTalentId: z.int(),
  classicSpellIds: z.array(z.int()),
  match: z.enum(['exact-name', 'fuzzy-name', 'description']),
  similarity: z.number().min(0).max(1),
})

/** One rank: slot values for the `{n}` placeholders, or a full sentence. */
export const RankSchema = z.union([z.array(z.union([z.number(), z.string()])), z.string()])

export const TalentSchema = z.looseObject({
  id: slug,
  name: z.string().min(1).max(80),
  row: z.int().min(0),
  col: z.int().min(0),
  /** One decimal digit per talent in build links; the schema caps this at 9. */
  maxRank: z.int().min(1).max(9),
  icon: z.string().min(1),
  iconSource: z.enum(['classic', 'crop', 'datamined', 'manual']),
  iconCrop: z.string().optional(),
  description: z.string(),
  ranks: z.array(RankSchema).min(1),
  ranksObserved: z.array(z.int().min(1)),
  ranksSource: z.enum(['observed', 'classic-prior', 'extrapolated', 'manual']),
  ranksPrior: RanksPriorSchema.optional(),
  ranksNote: z.string().optional(),
  requires: z.array(RequirementSchema).min(1).max(3).optional(),
  capstone: z.boolean().optional(),
  spellIds: z.array(z.int()).optional(),
  tags: z.array(z.string()).optional(),
  source: SourceSchema,
})

export const TreeSchema = z.looseObject({
  id: slug,
  name: z.string().min(1),
  page: PageIdSchema,
  order: z.int().min(0),
  icon: z.string().min(1),
  background: z.string().optional(),
  rows: z.int().min(1),
  cols: z.int().min(1),
  role: z.enum(['tank', 'healer', 'dps', 'hybrid']).optional(),
  datamined: z.looseObject({ talentTabId: z.int(), build: z.string() }).optional(),
  source: SourceSchema.optional(),
  talents: z.array(TalentSchema).min(1),
})

export const PageSchema = z.looseObject({
  id: PageIdSchema,
  name: z.string().min(1),
  note: z.string().optional(),
})

export const RulesSchema = z.looseObject({
  pointsPerRow: z.int().min(0),
  maxPoints: z.int().min(1),
  firstPointLevel: z.int().min(1),
  maxLevel: z.int().min(1),
  pointsPerPage: z.record(z.string(), z.int().min(0)).optional(),
  rulesSource: z.enum(['observed', 'classic-prior', 'assumed']),
})

export const ClassSchema = z.looseObject({
  $schema: z.string().optional(),
  schemaVersion: z.literal(1),
  class: slug,
  className: z.string().min(1),
  dataVersion: z.int().min(1),
  dataSource: z.enum(['video', 'datamined', 'mixed', 'manual']),
  generatedAt: z.string(),
  rules: RulesSchema,
  pages: z.array(PageSchema).min(1),
  trees: z.array(TreeSchema).min(1),
  notes: z.array(z.string()).optional(),
})

export type ClassData = z.infer<typeof ClassSchema>
export type Tree = z.infer<typeof TreeSchema>
export type Talent = z.infer<typeof TalentSchema>
export type Rules = z.infer<typeof RulesSchema>
export type Page = z.infer<typeof PageSchema>
export type Requirement = z.infer<typeof RequirementSchema>
export type Source = z.infer<typeof SourceSchema>
export type Rank = z.infer<typeof RankSchema>

/** Parse and throw a readable error listing every issue. */
export function parseClass(raw: unknown, label = 'class file'): ClassData {
  const result = ClassSchema.safeParse(raw)
  if (!result.success) {
    const issues = result.error.issues
      .map((i) => `  ${i.path.join('.') || '(root)'}: ${i.message}`)
      .join('\n')
    throw new Error(`Invalid ${label}:\n${issues}`)
  }
  return result.data
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

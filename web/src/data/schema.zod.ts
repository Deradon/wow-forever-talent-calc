/**
 * Zod mirror of docs/DATA-SCHEMA.md (schema version 1).
 *
 * The JSON Schema in data/schema/class.schema.json is authoritative and
 * rejects unknown keys; this mirror deliberately lets unknown keys pass
 * through (looseObject) so the data lead can add fields without breaking the
 * app. A Vitest (schema.test.ts) checks required keys and enums against the
 * JSON Schema when that file exists.
 *
 * This module is *not* on the production path: load.ts imports it dynamically
 * behind `import.meta.env.DEV`, so zod (~25 kB gzip) is bundled for the dev
 * server, the unit tests and `validate-data` only. Production data is validated
 * at build time by those same tests in CI (performance review P-3).
 */
import { z } from 'zod'
import { SLUG, type ClassData } from './schema'

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

const TreeObject = z.looseObject({
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

/**
 * `requires` is the one cross-talent rule the object shapes cannot express
 * (DATA-SCHEMA.md section 10.8). Forever has same-row prerequisites - priest
 * Improved Mind Flay requires Mind Flay in the same row - so the prerequisite
 * must live in the same tree, in the same row or an earlier one, and in a
 * different cell. A later row, the talent's own cell and a cycle stay errors:
 * all three describe an arrow no player could ever satisfy.
 */
export const TreeSchema = TreeObject.superRefine((tree, ctx) => {
  const byId = new Map(tree.talents.map((t) => [t.id, t]))
  tree.talents.forEach((t, i) => {
    (t.requires ?? []).forEach((req, r) => {
      const path = ['talents', i, 'requires', r, 'talent']
      const target = byId.get(req.talent)
      if (!target) {
        ctx.addIssue({ code: 'custom', path, message: `${t.id} requires ${req.talent}, which is not in tree ${tree.id}` })
        return
      }
      if (target.id === t.id || (target.row === t.row && target.col === t.col)) {
        ctx.addIssue({ code: 'custom', path, message: `${t.id} requires its own cell` })
        return
      }
      if (target.row > t.row) {
        ctx.addIssue({
          code: 'custom',
          path,
          message: `${t.id} (row ${t.row}) requires ${req.talent}, which sits lower at row ${target.row}`,
        })
      }
      if (req.rank > target.maxRank) {
        ctx.addIssue({
          code: 'custom',
          path: ['talents', i, 'requires', r, 'rank'],
          message: `${t.id} requires ${req.talent} at rank ${req.rank} > maxRank ${target.maxRank}`,
        })
      }
    })
  })
  for (const t of cycleOf(tree.talents)) {
    ctx.addIssue({ code: 'custom', path: ['talents'], message: `prerequisite cycle through ${t}` })
  }
})

/**
 * Ids on a `requires` cycle. Rows alone no longer rule cycles out: two talents
 * in the same row may point at each other, and the calculator would offer a
 * pair nothing can ever unlock.
 */
function cycleOf(talents: { id: string; requires?: { talent: string }[] }[]): string[] {
  const edges = new Map(talents.map((t) => [t.id, (t.requires ?? []).map((r) => r.talent)]))
  const state = new Map<string, 'open' | 'done'>()
  const found: string[] = []
  const walk = (id: string) => {
    const seen = state.get(id)
    if (seen === 'done') return
    if (seen === 'open') {
      found.push(id)
      return
    }
    state.set(id, 'open')
    for (const next of edges.get(id) ?? []) if (edges.has(next)) walk(next)
    state.set(id, 'done')
  }
  for (const t of talents) walk(t.id)
  return [...new Set(found)]
}

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

/**
 * Compile-time guard that the hand-written types in schema.ts still describe
 * what this mirror parses. `tsc -b` fails here if the two drift apart.
 */
type Assert<T extends true> = T
export type _InferredMatchesTypes = Assert<z.infer<typeof ClassSchema> extends ClassData ? true : false>

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

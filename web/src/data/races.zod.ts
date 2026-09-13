/**
 * Zod mirror of `docs/DATA-SCHEMA-RACES.md` (schema version 1), the races
 * counterpart of `schema.zod.ts`.
 *
 * `data/schema/race.schema.json` and `race-matrix.schema.json` are
 * authoritative and reject unknown keys; this mirror lets unknown keys through
 * (`looseObject`) so the data lead can add a field without breaking the app.
 * `validateRaces.test.ts` runs it over every file in `data/races/` and also
 * checks the rules that a JSON Schema cannot express (R2-R5, R9, M1-M4).
 *
 * Not on the production path: `races.ts` imports it dynamically behind
 * `import.meta.env.DEV`, exactly as `load.ts` does for classes, so zod stays
 * out of the shipped bundle.
 */
import { z } from 'zod'
import { SLUG } from './schema'
import { SourceSchema } from './schema.zod'
import type { RaceData, RaceMatrix } from './schema.races'

const slug = z.string().min(1).max(64).regex(SLUG)

export const FactionSchema = z.enum(['alliance', 'horde', 'neutral'])
export const VariantFactionSchema = z.enum(['alliance', 'horde'])
export const ClassicStatusSchema = z.enum(['new', 'changed', 'same', 'unknown'])

export const RaceVariantSchema = z.looseObject({
  id: slug,
  name: z.string().min(1),
  faction: VariantFactionSchema,
  classes: z.array(slug),
  lore: z.string().optional(),
  loreComplete: z.boolean().optional(),
})

export const RaceClassicSchema = z.looseObject({
  status: ClassicStatusSchema,
  classicName: z.string().optional(),
  classicText: z.string().optional(),
  note: z.string().optional(),
})

export const RaceTraitSchema = z.looseObject({
  id: slug,
  name: z.string().min(1).max(60),
  kind: z.enum(['active', 'passive']),
  order: z.int().min(0),
  variants: z.array(slug).min(1).optional(),
  description: z.string().min(1).max(400).optional(),
  icon: z.string().min(1).optional(),
  iconSource: z.enum(['classic', 'crop', 'datamined', 'manual']).optional(),
  iconCrop: z.string().optional(),
  classic: RaceClassicSchema,
  tags: z.array(z.string()).optional(),
  source: SourceSchema,
})

export const RaceSchema = z.looseObject({
  schemaVersion: z.literal(1),
  race: slug,
  raceName: z.string().min(1),
  faction: FactionSchema,
  dataSource: z.enum(['video', 'datamined', 'mixed', 'manual']),
  generatedAt: z.string(),
  variants: z.array(RaceVariantSchema).min(2).optional(),
  classes: z.array(slug),
  classesSource: SourceSchema.optional(),
  lore: z.string().optional(),
  loreComplete: z.boolean().optional(),
  loreSource: SourceSchema.optional(),
  traits: z.array(RaceTraitSchema),
  complete: z.boolean(),
  notes: z.array(z.string()).optional(),
})

export const MatrixRaceSchema = z.looseObject({
  race: slug,
  raceName: z.string().min(1),
  faction: FactionSchema,
  classes: z.array(slug),
  byVariant: z.record(slug, z.array(slug)).optional(),
  observed: z.boolean(),
  reportedElsewhere: z.array(slug).optional(),
  agreement: z.string().optional(),
  disagreement: z.string().optional(),
})

export const RaceMatrixSchema = z.looseObject({
  schemaVersion: z.literal(1),
  dataSource: z.enum(['video', 'datamined', 'mixed', 'manual']),
  generatedAt: z.string(),
  classes: z.array(slug).min(1),
  races: z.array(MatrixRaceSchema),
  notes: z.array(z.string()).optional(),
})

/**
 * Compile-time guard that the hand-written types still describe what this
 * mirror parses; `tsc -b` fails here if the two drift apart.
 */
type Assert<T extends true> = T
export type _RaceMatchesTypes = Assert<z.infer<typeof RaceSchema> extends RaceData ? true : false>
export type _MatrixMatchesTypes = Assert<z.infer<typeof RaceMatrixSchema> extends RaceMatrix ? true : false>

function parse<T>(schema: z.ZodType<T>, raw: unknown, label: string): T {
  const result = schema.safeParse(raw)
  if (!result.success) {
    const issues = result.error.issues.map((i) => `  ${i.path.join('.') || '(root)'}: ${i.message}`).join('\n')
    throw new Error(`Invalid ${label}:\n${issues}`)
  }
  return result.data
}

export function parseRace(raw: unknown, label = 'race file'): RaceData {
  return parse(RaceSchema, raw, label) as RaceData
}

export function parseRaceMatrix(raw: unknown, label = 'matrix.json'): RaceMatrix {
  return parse(RaceMatrixSchema, raw, label) as RaceMatrix
}

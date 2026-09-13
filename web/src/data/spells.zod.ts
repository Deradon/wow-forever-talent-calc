/**
 * Zod mirror of `data/schema/spell.schema.json` (schema version 1), the
 * spellbook counterpart of `races.zod.ts`.
 *
 * The JSON Schema is authoritative and rejects unknown keys; this mirror lets
 * them through (`looseObject`) so the data lead can add a field without
 * breaking the app. `validateSpells.test.ts` runs it over every file in
 * `data/spells/` and adds the rules a JSON Schema cannot state - the ones that
 * relate coverage to the entries it describes.
 *
 * Not on the production path: `spells.ts` imports it dynamically behind
 * `import.meta.env.DEV`, so zod stays out of the shipped bundle.
 */
import { z } from 'zod'
import { SLUG } from './schema'
import { SourceSchema } from './schema.zod'
import type { SpellData } from './schema.spells'

const slug = z.string().min(1).max(64).regex(SLUG)

/** `Source` plus the spellbook's own `panel`. */
export const SpellSourceSchema = SourceSchema.extend({
  panel: z.enum(['spell-list', 'tooltip', 'page-head']).optional(),
})

export const SpellTabSchema = z.looseObject({
  id: slug,
  name: z.string().min(1).max(40),
  order: z.int().min(0),
  tree: slug.optional(),
})

export const SpellTooltipSchema = z.looseObject({
  rank: z.int().min(1).max(20).optional(),
  cost: z.string().max(60).optional(),
  range: z.string().max(60).optional(),
  castTime: z.string().max(60).optional(),
  cooldown: z.string().max(60).optional(),
  tools: z.string().max(120).optional(),
  requires: z.array(z.string()).optional(),
  description: z.string().min(1).max(1200),
  footer: z.string().max(120).optional(),
  source: SpellSourceSchema,
})

export const SpellClassicSchema = z.looseObject({
  status: z.enum(['new', 'changed', 'same', 'unknown']),
  classicName: z.string().optional(),
  classicText: z.string().optional(),
  note: z.string().optional(),
})

export const SpellSchema = z.looseObject({
  id: slug,
  name: z.string().min(1).max(60),
  kind: z.enum(['active', 'passive', 'racial', 'racial-passive']),
  tab: slug.optional(),
  ranksSeen: z.array(z.int().min(1).max(20)).min(1).optional(),
  icon: z.string().min(1).max(80).optional(),
  iconSource: z.enum(['classic', 'crop', 'datamined', 'manual']).optional(),
  iconCrop: z.string().regex(/^data\/review\/spells\//).optional(),
  tooltips: z.array(SpellTooltipSchema).min(1).optional(),
  classic: SpellClassicSchema,
  tags: z.array(z.string()).optional(),
  source: SpellSourceSchema,
})

export const SpellCoverageSchema = z.looseObject({
  pagesSeen: z.array(z.string()),
  tabsSeen: z.array(slug),
  tabsMissing: z.array(slug),
  states: z.int().min(0),
  entriesRead: z.int().min(0),
  tooltipsRead: z.int().min(0),
  tooltipsUnmatched: z.int().min(0),
  showAllSpellRanks: z.enum(['on', 'off', 'not observed']),
  observedLevel: z.int().min(1).max(60),
  windows: z.array(z.string().regex(/^\d{2}:\d{2}:\d{2}$/)),
})

export const SpellFileSchema = z.looseObject({
  schemaVersion: z.literal(1),
  class: slug,
  className: z.string().min(1).max(40),
  dataSource: z.enum(['video', 'datamined', 'mixed', 'manual']),
  generatedAt: z.string(),
  observedLevel: z.int().min(1).max(60),
  tabs: z.array(SpellTabSchema),
  spells: z.array(SpellSchema),
  coverage: SpellCoverageSchema,
  complete: z.boolean(),
  notes: z.array(z.string()).optional(),
})

/**
 * Compile-time guard that the hand-written types still describe what this
 * mirror parses; `tsc -b` fails here if the two drift apart.
 */
type Assert<T extends true> = T
export type _SpellsMatchTypes = Assert<z.infer<typeof SpellFileSchema> extends SpellData ? true : false>

export function parseSpells(raw: unknown, label = 'spell file'): SpellData {
  const result = SpellFileSchema.safeParse(raw)
  if (!result.success) {
    const issues = result.error.issues.map((i) => `  ${i.path.join('.') || '(root)'}: ${i.message}`).join('\n')
    throw new Error(`Invalid ${label}:\n${issues}`)
  }
  return result.data as SpellData
}

/// <reference types="node" />
/**
 * The Zod mirror must agree with data/schema/class.schema.json on required
 * keys and enums (brief section 3). Skipped while the JSON Schema does not
 * exist yet.
 */
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { z } from 'zod'
import { ClassSchema, TalentSchema, TreeSchema, parseClass } from './schema.zod'
import { renderDescription } from './schema'
import tinker from '../../tests/fixtures/tinker.json'

const here = fileURLToPath(new URL('.', import.meta.url))
const jsonSchemaPath = join(here, '../../../data/schema/class.schema.json')

type Json = Record<string, unknown>

/** Collect `required` sets and `enum` lists from every object node, skipping conditional branches. */
function collect(node: unknown, out: { required: Set<string>; enums: Set<string> }, inConditional = false): void {
  if (Array.isArray(node)) {
    for (const n of node) collect(n, out, inConditional)
    return
  }
  if (!node || typeof node !== 'object') return
  const o = node as Json
  if (Array.isArray(o.required) && !inConditional && o.properties && Object.keys(o.properties as Json).length >= 2) {
    out.required.add([...(o.required as string[])].sort().join(','))
  }
  if (Array.isArray(o.enum)) out.enums.add([...(o.enum as unknown[])].map(String).sort().join('|'))
  for (const [key, value] of Object.entries(o)) {
    const conditional = inConditional || key === 'if' || key === 'then' || key === 'else' || key === 'allOf' || key === 'anyOf' || key === 'oneOf' || key === 'not'
    collect(value, out, conditional)
  }
}

describe('Zod schema', () => {
  it('parses the tinker example from DATA-SCHEMA.md section 11', () => {
    const cls = parseClass(tinker)
    expect(cls.class).toBe('tinker')
    expect(cls.trees).toHaveLength(2)
    // unknown keys pass through
    const extra = parseClass({ ...tinker, futureField: 42 }) as unknown as Record<string, unknown>
    expect(extra.futureField).toBe(42)
  })

  it('caps maxRank at 9 (one digit per talent in build links)', () => {
    const talent = { ...tinker.trees[0]!.talents[0]!, maxRank: 10, ranks: Array(10).fill([1, '']) }
    expect(TalentSchema.safeParse(talent).success).toBe(false)
  })

  it('requires an array for `requires` and rejects an empty one', () => {
    const base = tinker.trees[0]!.talents[2]!
    expect(TalentSchema.safeParse({ ...base, requires: { talent: 'x', rank: 1 } }).success).toBe(false)
    expect(TalentSchema.safeParse({ ...base, requires: [] }).success).toBe(false)
  })

  /**
   * Forever has same-row prerequisites (priest Improved Mind Flay requires
   * Mind Flay in its own row), so the mirror checks the relaxed rule from
   * DATA-SCHEMA.md section 10.8: same tree, same row or earlier, other cell.
   */
  describe('same-row prerequisites', () => {
    const tree = tinker.trees[0]!
    const [wrench, hands] = [tree.talents[0]!, tree.talents[1]!]
    /** A tree whose row-0 `steady-hands` requires row-0 `improved-wrench`. */
    function withRequires(requires: unknown, on = hands): unknown {
      return { ...tree, talents: tree.talents.map((t) => (t.id === on.id ? { ...t, requires } : t)) }
    }

    it('accepts a prerequisite in the same row and a different cell', () => {
      expect(TreeSchema.safeParse(withRequires([{ talent: wrench.id, rank: 3 }])).success).toBe(true)
      expect(parseClass({ ...tinker, trees: [withRequires([{ talent: wrench.id, rank: 3 }]), tinker.trees[1]!] })).toBeTruthy()
    })

    it('rejects a prerequisite in a later row', () => {
      const boots = tree.talents[2]! // row 2
      const bad = TreeSchema.safeParse(withRequires([{ talent: boots.id, rank: 1 }]))
      expect(bad.success).toBe(false)
      expect(JSON.stringify(bad.error?.issues)).toContain('sits lower at row 2')
    })

    it('rejects a talent that requires its own cell, an unknown id or too high a rank', () => {
      expect(TreeSchema.safeParse(withRequires([{ talent: hands.id, rank: 1 }])).success).toBe(false)
      expect(TreeSchema.safeParse(withRequires([{ talent: 'not-a-talent', rank: 1 }])).success).toBe(false)
      expect(TreeSchema.safeParse(withRequires([{ talent: wrench.id, rank: 4 }])).success).toBe(false)
    })

    it('rejects a cycle between two talents in the same row', () => {
      const cyclic = {
        ...tree,
        talents: tree.talents.map((t) =>
          t.id === hands.id
            ? { ...t, requires: [{ talent: wrench.id, rank: 3 }] }
            : t.id === wrench.id
              ? { ...t, requires: [{ talent: hands.id, rank: 5 }] }
              : t,
        ),
      }
      const bad = TreeSchema.safeParse(cyclic)
      expect(bad.success).toBe(false)
      expect(JSON.stringify(bad.error?.issues)).toContain('cycle')
    })
  })

  it('renders description templates and string-form ranks', () => {
    const wrench = tinker.trees[0]!.talents[0]!
    expect(renderDescription(wrench, 0)).toBe('Reduces the cost of your Wrench Strike ability by 1 energy point.')
    expect(renderDescription(wrench, 1)).toBe('Reduces the cost of your Wrench Strike ability by 2 energy points.')
    const medic = tinker.trees[1]!.talents[1]!
    expect(renderDescription(medic, 1)).toBe('Your bandages heal 20% more and can be used while moving.')
  })

  it.skipIf(!existsSync(jsonSchemaPath))('matches data/schema/class.schema.json on required keys and enums', () => {
    const jsonSchema = JSON.parse(readFileSync(jsonSchemaPath, 'utf8')) as Json
    const zodSchema = z.toJSONSchema(ClassSchema, { unrepresentable: 'any' }) as Json
    const fromJson = { required: new Set<string>(), enums: new Set<string>() }
    const fromZod = { required: new Set<string>(), enums: new Set<string>() }
    collect(jsonSchema, fromJson)
    collect(zodSchema, fromZod)

    const rootRequired = [...((jsonSchema.required as string[] | undefined) ?? [])].sort().join(',')
    expect(fromZod.required.has(rootRequired), `root required: ${rootRequired}`).toBe(true)
    for (const e of fromJson.enums) expect(fromZod.enums.has(e), `enum ${e} missing in Zod mirror`).toBe(true)
    for (const r of fromJson.required) expect(fromZod.required.has(r), `required set [${r}] missing in Zod mirror`).toBe(true)
  })
})

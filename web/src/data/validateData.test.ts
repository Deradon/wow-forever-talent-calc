/// <reference types="node" />
/**
 * validate-data: every JSON under data/talents/ and data/examples/ (and the
 * web fixtures) must pass the Zod schema and basic structural rules. Passes
 * trivially when the folders are empty or missing.
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { parseClass } from './schema.zod'
import { renderDescription, type ClassData } from './schema'
import { validate } from '../rules'

const here = fileURLToPath(new URL('.', import.meta.url))
const folders = [
  join(here, '../../../data/talents'),
  join(here, '../../../data/examples'),
  join(here, '../../tests/fixtures'),
]

const files = folders.flatMap((dir) =>
  existsSync(dir)
    ? readdirSync(dir)
        .filter((f) => f.endsWith('.json'))
        .map((f) => join(dir, f))
    : [],
)

describe('validate-data', () => {
  it(`found ${files.length} class file(s)`, () => {
    expect(files.length).toBeGreaterThanOrEqual(0)
  })

  for (const file of files) {
    describe(file.replace(/^.*\/data\//, 'data/').replace(/^.*\/web\//, 'web/'), () => {
      let cls: ClassData

      it('passes the Zod schema', () => {
        cls = parseClass(JSON.parse(readFileSync(file, 'utf8')), file)
      })

      it('class id equals the file stem', () => {
        expect(cls.class).toBe(file.slice(file.lastIndexOf('/') + 1).replace(/\.json$/, ''))
      })

      it('structural rules from DATA-SCHEMA.md section 10', () => {
        const { rules } = cls
        expect(rules.firstPointLevel - 1 + rules.maxPoints).toBeLessThanOrEqual(rules.maxLevel)
        const pageIds = new Set<string>(cls.pages.map((p) => p.id))
        expect(pageIds.size).toBe(cls.pages.length)
        for (const key of Object.keys(rules.pointsPerPage ?? {})) expect(pageIds.has(key)).toBe(true)

        const talentIds = new Set<string>()
        const treeIds = new Set<string>()
        for (const tree of cls.trees) {
          expect(treeIds.has(tree.id)).toBe(false)
          treeIds.add(tree.id)
          expect(pageIds.has(tree.page)).toBe(true)
          const cells = new Set<string>()
          for (const t of tree.talents) {
            expect(talentIds.has(t.id), `duplicate talent id ${t.id}`).toBe(false)
            talentIds.add(t.id)
            expect(t.row).toBeLessThan(tree.rows)
            expect(t.col).toBeLessThan(tree.cols)
            expect(cells.has(`${t.row},${t.col}`), `duplicate cell ${t.row},${t.col} in ${tree.id}`).toBe(false)
            cells.add(`${t.row},${t.col}`)
            expect(t.ranks, `${t.id}: ranks.length == maxRank`).toHaveLength(t.maxRank)
            const slots = new Set([...t.description.matchAll(/\{(\d+)\}/g)].map((m) => Number(m[1])))
            for (const rank of t.ranks) {
              if (Array.isArray(rank)) expect(rank, `${t.id}: slot count`).toHaveLength(slots.size)
              else expect(rank).not.toMatch(/\{\d+\}/)
            }
            for (let r = 0; r < t.maxRank; r++) expect(renderDescription(t, r)).not.toMatch(/\{\d+\}/)
            expect(t.ranksSource === 'observed').toBe(t.ranksObserved.length === t.maxRank)
            expect(t.ranksPrior !== undefined).toBe(t.ranksSource === 'classic-prior')
            expect(t.iconCrop !== undefined).toBe(t.iconSource === 'crop')
            for (const req of t.requires ?? []) {
              const target = tree.talents.find((x) => x.id === req.talent)
              expect(target, `${t.id} requires unknown ${req.talent}`).toBeDefined()
              expect(target!.row).toBeLessThan(t.row)
              expect(req.rank).toBeLessThanOrEqual(target!.maxRank)
            }
          }
        }
        expect(validate(cls, {})).toEqual([])
      })
    })
  }
})

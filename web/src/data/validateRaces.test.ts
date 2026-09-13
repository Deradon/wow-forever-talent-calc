/// <reference types="node" />
/**
 * validate-data for races: every file in `data/races/` must pass the Zod mirror
 * and the structural rules of `docs/DATA-SCHEMA-RACES.md` section 7 that a JSON
 * Schema cannot express. The same arrangement `validateData.test.ts` has for
 * classes, and the web-side twin of `pipeline/validate_races.py` - the two are
 * independent implementations of the same contract, which is the point: a rule
 * the pipeline forgets to enforce still fails here before the page renders it.
 *
 * Passes trivially when `data/races/` is missing.
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { parseRace, parseRaceMatrix } from './races.zod'
import type { RaceData, RaceMatrix } from './schema.races'
import { raceCropUrl } from './raceCrop'

const here = fileURLToPath(new URL('.', import.meta.url))
const repo = join(here, '../../..')
const dir = join(repo, 'data/races')

const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/

const files = existsSync(dir)
  ? readdirSync(dir)
      .sort()
      .filter((f) => f.endsWith('.json') && f !== 'matrix.json')
  : []

/** Every race file, parsed once; the matrix rules need all of them at hand. */
const races = new Map<string, RaceData>()

describe('validate-races', () => {
  it(`found ${files.length} race file(s)`, () => {
    expect(files.length).toBeGreaterThanOrEqual(0)
  })

  for (const file of files) {
    const id = file.replace(/\.json$/, '')
    describe(`data/races/${file}`, () => {
      let race: RaceData

      it('passes the Zod schema', () => {
        race = parseRace(JSON.parse(readFileSync(join(dir, file), 'utf8')), `data/races/${file}`)
        races.set(id, race)
      })

      it('R2/R3: ids are slugs, the race matches the file stem, orders are unique', () => {
        expect(race.race).toBe(id)
        expect(SLUG.test(race.race)).toBe(true)
        const ids = new Set<string>()
        const orders = new Set<number>()
        for (const t of race.traits) {
          expect(SLUG.test(t.id), `${t.id} is not a slug`).toBe(true)
          expect(ids.has(t.id), `duplicate trait id ${t.id}`).toBe(false)
          ids.add(t.id)
          expect(orders.has(t.order), `duplicate order ${t.order}`).toBe(false)
          orders.add(t.order)
          // `(Passive)` is a suffix of the rendered name, never part of the id
          // or the stored name (R14).
          expect(t.name).not.toMatch(/\(passive\)/i)
        }
      })

      it('R4: variants have distinct factions and every trait names an existing one', () => {
        const variants = race.variants
        if (!variants) {
          for (const t of race.traits) expect(t.variants, `${t.id} names a variant`).toBeUndefined()
          return
        }
        expect(new Set(variants.map((v) => v.faction)).size).toBe(variants.length)
        const known = new Set(variants.map((v) => v.id))
        for (const t of race.traits) {
          expect(t.variants, `${t.id} must name its variants`).toBeDefined()
          expect(t.variants!.length).toBeGreaterThan(0)
          for (const v of t.variants!) expect(known.has(v), `${t.id} names unknown variant ${v}`).toBe(true)
        }
        // A neutral race is exactly the race shown in both columns.
        expect(race.faction).toBe('neutral')
      })

      it('R5: classes are sorted and equal the union over the variants', () => {
        expect(race.classes).toEqual([...race.classes].sort())
        if (!race.variants) return
        const union = [...new Set(race.variants.flatMap((v) => v.classes))].sort()
        expect(race.classes).toEqual(union)
        for (const v of race.variants) expect(v.classes).toEqual([...v.classes].sort())
      })

      it('R6/R7: a trait without a description explains itself; Classic verdicts are consistent', () => {
        for (const t of race.traits) {
          if (!t.description) expect(t.source.note, `${t.id} has no description and no note`).toBeTruthy()
          const c = t.classic
          if (c.status === 'new') {
            expect(c.classicName, `${t.id} is new but names a Classic racial`).toBeUndefined()
          }
          if (c.status === 'changed' || c.status === 'same') {
            expect(c.classicName, `${t.id} is ${c.status} without a Classic name`).toBeTruthy()
            expect(c.classicText, `${t.id} is ${c.status} without Classic text`).toBeTruthy()
          }
          // The tags mirror the verdict (R17 TAG-MISMATCH).
          const expected = { new: 'new', changed: 'reworked', same: 'classic-unchanged', unknown: undefined }[c.status]
          if (expected && t.tags) expect(t.tags, `${t.id} tags`).toContain(expected)
        }
      })

      it('R9/R11: every crop the page renders or links is shipped', () => {
        for (const t of race.traits) {
          expect(t.iconCrop !== undefined, `${t.id} iconCrop iff iconSource crop`).toBe(t.iconSource === 'crop')
          if (t.iconSource === 'crop') {
            expect(raceCropUrl(t.iconCrop), `${t.id} icon crop ${t.iconCrop}`).toBeDefined()
          }
          if (t.source.kind === 'video') {
            expect(raceCropUrl(t.source.crop), `${t.id} row crop ${t.source.crop}`).toBeDefined()
          }
        }
        if (race.lore !== undefined) {
          expect(race.loreComplete, 'lore needs loreComplete').toBeDefined()
          expect(race.loreSource, 'lore needs loreSource').toBeDefined()
        }
        // A race with variants carries its lore per variant, not at the top.
        if (race.variants) expect(race.lore).toBeUndefined()
      })

      it('R10: a complete race has traits, and every source is video with a timestamp', () => {
        if (race.complete) expect(race.traits.length).toBeGreaterThan(0)
        for (const t of race.traits) {
          if (t.source.kind !== 'video') continue
          expect(t.source.t, `${t.id} has no timestamp`).toBeGreaterThanOrEqual(0)
          expect(t.source.confidence, `${t.id} has no confidence`).toBeGreaterThan(0)
          expect(t.source.reviewed === true).toBe(Boolean(t.source.reviewedBy))
        }
      })
    })
  }

  describe('data/races/matrix.json', () => {
    const file = join(dir, 'matrix.json')
    let matrix: RaceMatrix

    it('passes the Zod schema', () => {
      if (!existsSync(file)) return
      matrix = parseRaceMatrix(JSON.parse(readFileSync(file, 'utf8')), 'data/races/matrix.json')
    })

    it('M1-M4: one row per race, sorted classes, observed and byVariant consistent', () => {
      if (!matrix) return
      const seen = new Set<string>()
      const known = new Set(matrix.classes)
      for (const row of matrix.races) {
        expect(seen.has(row.race), `duplicate matrix row ${row.race}`).toBe(false)
        seen.add(row.race)
        expect(row.classes).toEqual([...row.classes].sort())
        for (const c of row.classes) expect(known.has(c), `${row.race}: unknown class ${c}`).toBe(true)
        expect(row.observed).toBe(row.classes.length > 0)

        const race = races.get(row.race)
        expect(race, `${row.race} has no race file`).toBeDefined()
        expect(row.classes, `${row.race}: matrix disagrees with the race file`).toEqual(race!.classes)
        expect(row.faction).toBe(race!.faction)

        if (row.byVariant) {
          const union = [...new Set(Object.values(row.byVariant).flat())].sort()
          expect(union).toEqual(row.classes)
          expect(Object.keys(row.byVariant).sort()).toEqual((race!.variants ?? []).map((v) => v.id).sort())
        }
      }
      // Every race file appears in the matrix.
      expect([...seen].sort()).toEqual([...races.keys()].sort())
    })
  })
})

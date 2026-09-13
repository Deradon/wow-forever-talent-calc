/// <reference types="node" />
/**
 * validate-data for spellbooks: every file in `data/spells/` must pass the Zod
 * mirror and the structural rules that a JSON Schema cannot express - the ones
 * that tie the coverage record to the entries it describes.
 *
 * The same arrangement `validateRaces.test.ts` has for races, and the web-side
 * twin of `pipeline/validate_spells.py`. The two are independent
 * implementations of one contract on purpose: a rule the pipeline forgets to
 * enforce still fails here, before the page renders it.
 *
 * Passes trivially when `data/spells/` is missing.
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { parseSpells } from './spells.zod'
import type { SpellData } from './schema.spells'
import { loadSpellCrops, spellCropClasses } from './spellCrop'

const here = fileURLToPath(new URL('.', import.meta.url))
const repo = join(here, '../../..')
const dir = join(repo, 'data/spells')

const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/

const files = existsSync(dir)
  ? readdirSync(dir)
      .sort()
      .filter((f) => f.endsWith('.json'))
  : []

describe('validate-spells', () => {
  it(`found ${files.length} spellbook file(s)`, () => {
    expect(files.length).toBeGreaterThanOrEqual(0)
  })

  it('every spellbook file has a crop module, and no module is orphaned', () => {
    expect(spellCropClasses()).toEqual(files.map((f) => f.replace(/\.json$/, '')))
  })

  for (const file of files) {
    const id = file.replace(/\.json$/, '')
    describe(`data/spells/${file}`, () => {
      let data: SpellData

      it('passes the Zod schema', () => {
        data = parseSpells(JSON.parse(readFileSync(join(dir, file), 'utf8')), `data/spells/${file}`)
      })

      it('ids are unique slugs and the class matches the file stem', () => {
        expect(data.class).toBe(id)
        const seen = new Set<string>()
        for (const spell of data.spells) {
          expect(SLUG.test(spell.id), `${spell.id} is not a slug`).toBe(true)
          expect(seen.has(spell.id), `duplicate spell id ${spell.id}`).toBe(false)
          seen.add(spell.id)
        }
      })

      it('tabs are ordered without gaps and every spell names one that exists', () => {
        const orders = data.tabs.map((t) => t.order).sort((a, b) => a - b)
        expect(orders).toEqual(orders.map((_, i) => i))
        expect(new Set(data.tabs.map((t) => t.id)).size).toBe(data.tabs.length)
        const known = new Set(data.tabs.map((t) => t.id))
        for (const spell of data.spells) {
          if (spell.tab === undefined) {
            // Rule 8: a row with no tab came from a search page and has to say so.
            expect(spell.source.note, `${spell.id} has no tab and no note`).toBeTruthy()
            continue
          }
          expect(known.has(spell.tab), `${spell.id} names unknown tab ${spell.tab}`).toBe(true)
        }
      })

      it('the coverage record describes the entries it ships with', () => {
        const coverage = data.coverage
        expect(coverage.entriesRead, 'entriesRead disagrees with spells[]').toBe(data.spells.length)
        expect(coverage.tooltipsRead, 'tooltipsRead disagrees with the tooltips').toBe(
          data.spells.reduce((n, s) => n + (s.tooltips ?? []).length, 0),
        )
        expect(coverage.observedLevel).toBe(data.observedLevel)
        // A tab is either seen or missing, never both and never neither.
        expect(coverage.tabsSeen.sort()).toEqual([...data.tabs.map((t) => t.id)].sort())
        for (const missing of coverage.tabsMissing) {
          expect(coverage.tabsSeen, `${missing} is both seen and missing`).not.toContain(missing)
        }
        // Nothing read from this stream is a complete book (rule 1).
        expect(data.complete).toBe(false)
        expect(data.dataSource).toBe('video')
      })

      it('ranks are what was on screen, and a Classic verdict explains itself', () => {
        for (const spell of data.spells) {
          if (spell.ranksSeen) {
            expect(spell.ranksSeen.length).toBeGreaterThan(0)
            expect(new Set(spell.ranksSeen).size).toBe(spell.ranksSeen.length)
            // Rule 3: several ranks on one row only happen with the option on.
            if (spell.ranksSeen.length > 1) expect(data.coverage.showAllSpellRanks).toBe('on')
          }
          // Rule 7: the verdict is name-level, so it always carries its reasoning.
          expect(spell.classic.note, `${spell.id} has no Classic note`).toBeTruthy()
          expect(['new', 'changed', 'same', 'unknown']).toContain(spell.classic.status)
          if (spell.classic.status === 'new') expect(spell.tags ?? []).toContain('new')
          for (const tooltip of spell.tooltips ?? []) {
            expect(tooltip.description.length).toBeGreaterThan(0)
            expect(tooltip.source.panel).toBe('tooltip')
          }
        }
      })

      it('every source is a video reading with a timestamp and a confidence', () => {
        for (const spell of data.spells) {
          expect(spell.source.kind).toBe('video')
          expect(spell.source.t, `${spell.id} has no timestamp`).toBeGreaterThanOrEqual(0)
          // 0 is a real value here - it means only one reading pass saw the
          // row at all, which is exactly the case the review queue wants first.
          expect(spell.source.confidence, `${spell.id} has no confidence`).toBeGreaterThanOrEqual(0)
          expect(spell.source.reviewed === true).toBe(Boolean(spell.source.reviewedBy))
        }
      })

      it('every crop the page renders or links is shipped', async () => {
        const crops = await loadSpellCrops(id)
        for (const spell of data.spells) {
          if (spell.iconSource === 'crop') {
            expect(spell.iconCrop, `${spell.id} has no iconCrop`).toBeDefined()
            expect(crops[spell.iconCrop!], `${spell.id} icon crop ${spell.iconCrop}`).toBeDefined()
          }
          for (const tooltip of spell.tooltips ?? []) {
            expect(crops[tooltip.source.crop!], `${spell.id} tooltip crop`).toBeDefined()
          }
        }
        // Row crops are not linked, so they are deliberately not in the module.
        expect(Object.keys(crops).every((p) => p.startsWith(`data/review/spells/${id}/`))).toBe(true)
      })
    })
  }
})

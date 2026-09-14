/// <reference types="node" />
/**
 * The generated files under `src/data/` are committed, and this is the guard
 * that says they are current.
 *
 * It generates into a **temporary directory** and compares byte for byte. That
 * indirection is the whole point: the previous version compared the committed
 * files against `expected()` while `vite.config.ts` regenerated those same
 * files from `config()` on every vitest run, so the comparison was circular and
 * could not fail - a `STALE-MARKER` injected into `classes-index.json` passed
 * 11/11 and was erased in the process (code review K-2). The generator plugin
 * is dev-only now, and this test writes nowhere inside the repository.
 *
 * `npm run gen` is how you make it pass.
 */
import { mkdtempSync, readFileSync, readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { generate, publishable, readRaces, readSpells } from '../../scripts/gen-data-index.mjs'
import classesIndex from './classes-index.json'
import racesIndex from './races-index.json'
import spellsIndex from './spells-index.json'
import { iconCropUrl, iconCropCount } from './iconCrop'
import { parseClass } from './schema.zod'
import { parseRace } from './races.zod'
import { raceCropUrl, raceCropCount } from './raceCrop'
import { parseSpells } from './spells.zod'
import { loadSpellCrops, spellCropClasses } from './spellCrop'

const here = fileURLToPath(new URL('.', import.meta.url))
const repo = join(here, '../../..')

/** A fresh generation, outside the repository, made once for the whole file. */
let fresh: string

beforeAll(() => {
  fresh = mkdtempSync(join(tmpdir(), 'wow-forever-gen-'))
  generate(fresh)
})

afterAll(() => {
  if (fresh) rmSync(fresh, { recursive: true, force: true })
})

/** The committed file and the freshly generated one, ready to compare. */
function pair(rel: string): [string, string] {
  const generated = readFileSync(join(fresh, 'src/data', rel), 'utf8')
  let committed: string
  try {
    committed = readFileSync(join(here, rel), 'utf8')
  } catch {
    committed = `<<missing: src/data/${rel} is not committed>>`
  }
  return [committed, generated]
}

function expectCurrent(rel: string) {
  const [committed, generated] = pair(rel)
  expect(committed, `src/data/${rel} is stale - run \`npm run gen\``).toBe(generated)
}

describe('generated data indexes', () => {
  it('classes-index.json is up to date', () => {
    expectCurrent('classes-index.json')
  })

  it('facts.json is up to date', () => {
    expectCurrent('facts.json')
  })

  it('iconCrops.ts is up to date', () => {
    expectCurrent('iconCrops.ts')
  })

  it('classic-diff.json and classic-text.json are up to date', () => {
    expectCurrent('classic-diff.json')
    expectCurrent('classic-text.json')
  })

  it('races-index.json and raceCrops.ts are up to date', () => {
    expectCurrent('races-index.json')
    expectCurrent('raceCrops.ts')
  })

  it('spells-index.json and every spellCrops module are up to date', () => {
    expectCurrent('spells-index.json')
    const generated = readdirSync(join(fresh, 'src/data/spellCrops')).sort()
    // The set has to match too: a class whose spellbook file was deleted must
    // not leave its module committed behind.
    expect(readdirSync(join(here, 'spellCrops')).sort()).toEqual(generated)
    for (const file of generated) expectCurrent(`spellCrops/${file}`)
  })

  it('cannot pass on a stale file: the comparison is against a directory vitest never writes', () => {
    const [committed] = pair('classes-index.json')
    expect(fresh.startsWith(tmpdir())).toBe(true)
    expect(committed).not.toContain('STALE-MARKER')
    // If the generator wrote into the repository, the two paths would be one.
    expect(join(fresh, 'src/data')).not.toBe(here.replace(/\/$/, ''))
  })

  it('indexes every spellbook with its tabs, counts and gaps - and the class that has none', () => {
    const spells = readSpells()
    expect(spellsIndex.classes.map((c) => c.id)).toEqual(spells.map((s) => s.id))
    // Priest was never on screen. The overview has to know that, so the index
    // carries the classes with no file rather than the page guessing.
    expect(spellsIndex.absent.map((c) => c.id)).toEqual(['priest'])
    expect(spellsIndex.priorVerified).toBe(false)
    for (const { id, data } of spells) {
      const entry = spellsIndex.classes.find((c) => c.id === id)!
      const file = parseSpells(data, id)
      // A record with no evidence behind it is counted nowhere: "new" means
      // "not in our Classic list", so a fabricated name would otherwise be
      // guaranteed a New chip (data review D-2).
      const shown = file.spells.filter(publishable)
      expect(entry.className).toBe(file.className)
      expect(entry.entries).toBe(shown.length)
      expect(entry.withText).toBe(shown.filter((s) => (s.tooltips ?? []).length > 0).length)
      expect(entry.new).toBe(shown.filter((s) => s.classic.status === 'new').length)
      expect(entry.tabs.map((t) => t.id)).toEqual(
        [...file.tabs].sort((a, b) => a.order - b.order).map((t) => t.id),
      )
      expect(entry.tabs.reduce((n, t) => n + t.spells, 0) + entry.searchOnly).toBe(shown.length)
      expect(entry.tabsMissing).toEqual(file.coverage.tabsMissing)
      expect(entry.observedLevel).toBe(file.observedLevel)
    }
  })

  it("ships one crop module per class, holding only that class's crops", async () => {
    expect(spellCropClasses()).toEqual(readSpells().map((s) => s.id))
    for (const { id, data } of readSpells()) {
      const crops = await loadSpellCrops(id)
      const file = parseSpells(data, id)
      for (const spell of file.spells) {
        if (spell.iconSource === 'crop') expect(crops[spell.iconCrop!], `${id}/${spell.id}`).toBeDefined()
        for (const tooltip of spell.tooltips ?? []) expect(crops[tooltip.source.crop!]).toBeDefined()
      }
      for (const path of Object.keys(crops)) expect(path.startsWith(`data/review/spells/${id}/`)).toBe(true)
    }
  })

  it('keeps the spellbook crops out of the review registry', async () => {
    const { cropUrl } = await import('./crops')
    const mage = await loadSpellCrops('mage')
    const [first] = Object.keys(mage)
    expect(first).toBeDefined()
    // 765 files and 14 MB: the review route must not carry their URLs.
    expect(cropUrl(first)).toBeUndefined()
  })

  it('indexes every race file with its variants, classes and trait counts', () => {
    const races = readRaces()
    expect(racesIndex.races.map((r) => r.id)).toEqual(races.map((r) => r.id))
    for (const { id, data } of races) {
      const entry = racesIndex.races.find((r) => r.id === id)!
      const race = parseRace(data, id)
      expect(entry.raceName).toBe(race.raceName)
      expect(entry.faction).toBe(race.faction)
      expect(entry.classes).toEqual(race.classes)
      expect(entry.traits).toBe(race.traits.length)
      expect(entry.complete).toBe(race.complete)
      expect(entry.variants?.map((v) => v.id)).toEqual(race.variants?.map((v) => v.id))
      for (const v of entry.variants ?? []) {
        expect(v.classes).toEqual(race.variants!.find((x) => x.id === v.id)!.classes)
      }
    }
    // The column order is the class bar's, not alphabetical.
    expect(racesIndex.classes[0]).toBe('warrior')
    // The prior is a paraphrase written from memory; the page says so because
    // the index says so.
    expect(racesIndex.priorVerified).toBe(false)
  })

  it('resolves every race crop the pages render or link, and nothing else', () => {
    expect(raceCropCount()).toBeGreaterThan(0)
    expect(raceCropUrl(undefined)).toBeUndefined()
    expect(raceCropUrl('data/review/races/nope/nope.png')).toBeUndefined()
    let seen = 0
    for (const { id, data } of readRaces()) {
      const race = parseRace(data, id)
      for (const t of race.traits) {
        seen++
        expect(raceCropUrl(t.iconCrop), `${id}/${t.id} icon`).toBeDefined()
        expect(raceCropUrl(t.source.crop), `${id}/${t.id} crop`).toBeDefined()
        expect(raceCropUrl(`./${t.iconCrop}`)).toBe(raceCropUrl(t.iconCrop))
      }
    }
    expect(seen).toBeGreaterThan(0)
    // Talent crops belong to the calculator's map, not to this one.
    expect(raceCropUrl('data/review/paladin/holy/_header.png')).toBeUndefined()
  })

  it('indexes every class file with its trees and counts', () => {
    const ids = classesIndex.map((c) => c.id)
    expect(new Set(ids).size).toBe(ids.length)
    for (const entry of classesIndex) {
      const cls = parseClass(
        JSON.parse(readFileSync(join(repo, entry.origin === 'fixtures' ? 'web/tests/fixtures' : `data/${entry.origin}`, `${entry.id}.json`), 'utf8')),
        entry.id,
      )
      expect(entry.className).toBe(cls.className)
      expect(entry.maxPoints).toBe(cls.rules.maxPoints)
      expect(entry.talents).toBe(cls.trees.flatMap((t) => t.talents).length)
      expect(entry.trees.map((t) => t.name)).toEqual(
        [...cls.trees].sort((a, b) => a.order - b.order).map((t) => t.name),
      )
    }
  })

  it('resolves every crop icon the calculator renders, and nothing else', () => {
    expect(iconCropCount()).toBeGreaterThan(0)
    expect(iconCropUrl(undefined)).toBeUndefined()
    expect(iconCropUrl('data/review/nope/nope/nope.icon.png')).toBeUndefined()
    let seen = 0
    for (const entry of classesIndex) {
      const cls = parseClass(
        JSON.parse(readFileSync(join(repo, entry.origin === 'fixtures' ? 'web/tests/fixtures' : `data/${entry.origin}`, `${entry.id}.json`), 'utf8')),
        entry.id,
      )
      for (const tree of cls.trees) {
        for (const t of tree.talents) {
          if (t.iconSource !== 'crop') continue
          seen++
          expect(iconCropUrl(t.iconCrop), `${t.id} iconCrop ${t.iconCrop}`).toBeDefined()
          expect(iconCropUrl(`./${t.iconCrop}`)).toBe(iconCropUrl(t.iconCrop))
        }
      }
    }
    expect(seen).toBeGreaterThan(0)
    // review-only frame crops must not be in the calculator's map
    expect(iconCropUrl('data/review/paladin/holy/_header.png')).toBeUndefined()
  })
})

/// <reference types="node" />
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import racesIndexJson from '../data/races-index.json'
import type { RaceData, RaceTrait } from '../data/schema.races'
import {
  activeVariant,
  cellLabel,
  cellState,
  classicCardTitle,
  classicNoteLines,
  initials,
  matrixRows,
  newComboCount,
  playerNoteLines,
  raceTrustLines,
  traitDetailLines,
  traitTrustLine,
  variantClasses,
  variantLore,
  variantTraits,
  type RacesIndex,
} from './racesModel'

const index = racesIndexJson as RacesIndex

/** The canonical race files, for the assertions that want the whole corpus. */
function raceFiles(): RaceData[] {
  const dir = join(fileURLToPath(new URL('.', import.meta.url)), '../../../data/races')
  if (!existsSync(dir)) return []
  return readdirSync(dir)
    .sort()
    .filter((f) => f.endsWith('.json') && f !== 'matrix.json')
    .map((f) => JSON.parse(readFileSync(join(dir, f), 'utf8')) as RaceData)
}

function trait(over: Partial<RaceTrait> = {}): RaceTrait {
  return {
    id: 'stoneform',
    name: 'Stoneform',
    kind: 'active',
    order: 0,
    description: 'Immunity to Bleeds for 8 sec',
    classic: { status: 'new' },
    source: { kind: 'video', video: 'X', t: 11680.5, crop: 'c.png', confidence: 1, reviewed: false },
    ...over,
  }
}

/** A two-variant race, the shape only Skyborne has today. */
function twoVariantRace(): RaceData {
  return {
    schemaVersion: 1,
    race: 'skyborne',
    raceName: 'Skyborne',
    faction: 'neutral',
    dataSource: 'video',
    generatedAt: '2026-09-13T00:00:00Z',
    variants: [
      { id: 'high-order', name: 'High Order Skyborne', faction: 'alliance', classes: ['mage'], lore: 'A' },
      { id: 'windshaper', name: 'Windshaper Skyborne', faction: 'horde', classes: ['shaman'], lore: 'B', loreComplete: true },
    ],
    classes: ['mage', 'shaman'],
    traits: [
      trait({ id: 'shared', name: 'Shared', order: 1, variants: ['high-order', 'windshaper'] }),
      trait({ id: 'only-horde', name: 'Only Horde', order: 0, variants: ['windshaper'] }),
    ],
    complete: true,
  }
}

describe('the matrix', () => {
  const rows = matrixRows(index)

  it('gives the two Skyborne variants a row each, on their own faction side', () => {
    const skyborne = rows.filter((r) => r.raceId === 'skyborne')
    expect(skyborne.map((r) => r.name)).toEqual(['High Order Skyborne', 'Windshaper Skyborne'])
    expect(skyborne.map((r) => r.faction)).toEqual(['alliance', 'horde'])
    // Their class lists differ, which is the whole reason they are two rows.
    expect(skyborne[0]!.classes).toContain('mage')
    expect(skyborne[0]!.classes).not.toContain('shaman')
    expect(skyborne[1]!.classes).toContain('shaman')
    expect(skyborne[1]!.classes).not.toContain('mage')
    expect(skyborne.map((r) => r.href)).toEqual([
      '#/races/skyborne?variant=high-order',
      '#/races/skyborne?variant=windshaper',
    ])
  })

  it('groups Alliance before Horde and keeps one row per playable identity', () => {
    const factions = rows.map((r) => r.faction)
    expect(factions).toEqual([...factions].sort((a, b) => (a === b ? 0 : a === 'alliance' ? -1 : 1)))
    expect(new Set(rows.map((r) => r.key)).size).toBe(rows.length)
    // Nine race files, one of which splits in two.
    expect(rows).toHaveLength(index.races.length + 1)
  })

  it('marks exactly the combinations the Classic prior did not have', () => {
    const human = rows.find((r) => r.key === 'human')!
    expect(cellState(human, 'hunter')).toBe('new')
    expect(cellState(human, 'mage')).toBe('playable')
    expect(cellState(human, 'druid')).toBe('no')
    const undead = rows.find((r) => r.key === 'undead')!
    expect(cellState(undead, 'paladin')).toBe('new')
    // Night Elf gained no combination; its row must mark nothing.
    expect(rows.find((r) => r.key === 'night-elf')!.newCombos).toEqual([])
    expect(newComboCount(rows)).toBeGreaterThan(0)
  })

  it('calls an unread class bar unknown, never "no classes"', () => {
    const blank = { ...rows[0]!, classes: [], observed: false }
    expect(cellState(blank, 'mage')).toBe('unknown')
    expect(cellLabel(blank, 'Mage', 'unknown')).toContain('never read')
    // Observed but empty is the same statement, and is also unknown.
    expect(cellState({ ...blank, observed: true }, 'mage')).toBe('unknown')
  })

  it('labels every cell in words a screen reader can use', () => {
    const human = rows.find((r) => r.key === 'human')!
    expect(cellLabel(human, 'Hunter', 'new')).toBe('Human Hunter - new in Forever')
    expect(cellLabel(human, 'Mage', 'playable')).toBe('Human Mage')
    expect(cellLabel(human, 'Druid', 'no')).toBe('Human cannot be a Druid')
  })

  it('never marks a combination when the prior knows nothing about the race', () => {
    const unknownPrior = { ...index, races: [{ ...index.races[0]!, newCombos: undefined }] }
    const row = matrixRows(unknownPrior as RacesIndex)[0]!
    expect(row.newCombos).toBeUndefined()
    expect(cellState(row, row.classes[0]!)).toBe('playable')
  })
})

describe('one race', () => {
  const race = twoVariantRace()

  it('defaults to the Alliance variant and falls back rather than emptying the page', () => {
    expect(activeVariant(race, undefined)!.id).toBe('high-order')
    expect(activeVariant(race, 'windshaper')!.id).toBe('windshaper')
    expect(activeVariant(race, 'nonsense')!.id).toBe('high-order')
    expect(activeVariant({ ...race, variants: undefined }, 'windshaper')).toBeUndefined()
  })

  it('shows the variant, not the union: its traits, its classes, its lore', () => {
    const horde = activeVariant(race, 'windshaper')!
    expect(variantTraits(race, horde).map((t) => t.id)).toEqual(['only-horde', 'shared'])
    expect(variantTraits(race, activeVariant(race, 'high-order')!).map((t) => t.id)).toEqual(['shared'])
    expect(variantClasses(race, horde)).toEqual(['shaman'])
    expect(variantClasses(race, undefined)).toEqual(['mage', 'shaman'])
    expect(variantLore(race, horde)).toEqual({ text: 'B', complete: true })
    expect(variantLore(race, activeVariant(race, 'high-order')!)).toEqual({ text: 'A', complete: false })
  })

  it('renders traits in box order, never by name', () => {
    const plain = { ...race, variants: undefined }
    expect(variantTraits(plain as RaceData, undefined).map((t) => t.order)).toEqual([0, 1])
  })
})

describe('trust', () => {
  it('states the source once for the page and says nothing was reviewed', () => {
    const lines = raceTrustLines([trait(), trait({ id: 'b' })])
    expect(lines).toHaveLength(1)
    expect(lines[0]).toContain('Read from BlizzCon 2026 footage')
    expect(lines[0]).toContain('not yet reviewed')
  })

  it('counts reviewed traits and flags low-confidence readings', () => {
    const shaky = trait({ id: 'shaky', source: { kind: 'video', t: 1, confidence: 0.3, reviewed: false } })
    const done = trait({ id: 'done', source: { kind: 'video', t: 1, confidence: 1, reviewed: true } })
    const lines = raceTrustLines([shaky, done])
    expect(lines[0]).toContain('1 of 2 traits reviewed')
    expect(lines[1]).toContain('uncertain')
    expect(raceTrustLines([done])[0]).toContain('and reviewed')
    expect(raceTrustLines([])).toEqual([])
  })

  it('puts the tooltip’s own amber line on a shaky card, and nothing on a solid one', () => {
    expect(traitTrustLine(trait())).toBeUndefined()
    expect(traitTrustLine(trait({ source: { kind: 'video', t: 1, confidence: 0.3, reviewed: false } }))).toBe(
      'Uncertain reading, check.',
    )
  })

  it('puts the timestamp behind Details and keeps pipeline internals out', () => {
    const lines = traitDetailLines(trait())
    expect(lines[0]).toBe('Read from the stream at 3:14:40.')
    // 100% confidence is never spelled out, and a reader model name never
    // reaches a player.
    expect(lines.join(' ')).not.toMatch(/100%|Qwen|confidence/i)
    expect(traitDetailLines(trait({ source: { kind: 'video', t: 1, confidence: 1, reviewed: true } }))).toContain(
      'Checked by a reviewer.',
    )
  })

  it('drops the pipeline half of a source note and keeps the player half', () => {
    expect(playerNoteLines('lit/greyed separation margin 21.2')).toEqual([])
    expect(playerNoteLines('paragraph continues past the box edge')).toEqual([
      'Paragraph continues past the box edge.',
    ])
  })
})

describe('the Classic side', () => {
  it('titles the card by the verdict and names the Classic racial', () => {
    expect(classicCardTitle({ status: 'new' })).toBe('Not in Classic Era')
    expect(classicCardTitle({ status: 'changed', classicName: 'Stoneform' })).toBe('In Classic Era: Stoneform')
    expect(classicCardTitle({ status: 'same' })).toBe('In Classic Era')
  })

  it('keeps the reasoning and drops the repo path and the memory disclaimer', () => {
    const note =
      'Classic removes bleed, poison and disease and adds 10% armor; Forever grants immunity to them; ' +
      'Classic side written from memory and unverified (data/prior/classic-era/racials.json)'
    const lines = classicNoteLines(note)
    expect(lines).toEqual([
      'Classic removes bleed, poison and disease and adds 10% armor.',
      'Forever grants immunity to them.',
    ])
    expect(lines.join(' ')).not.toContain('data/prior')
    expect(classicNoteLines(undefined)).toEqual([])
  })

  it('leaves every real verdict with something to say, and no path behind', () => {
    // The pipeline appends the same disclaimer to all 23 matched verdicts. If
    // the cleaner ever ate a whole note the card would open on an empty body,
    // so this runs it over the corpus rather than over a fixture.
    let seen = 0
    for (const file of raceFiles()) {
      for (const t of file.traits) {
        const lines = classicNoteLines(t.classic.note)
        if (!t.classic.note) continue
        seen++
        expect(lines.length, `${file.race}/${t.id} lost its whole note`).toBeGreaterThan(0)
        for (const line of lines) {
          expect(line, `${file.race}/${t.id}`).not.toMatch(/data\/|\.json\b|written from memory/i)
          expect(line).toMatch(/\.$/)
        }
      }
    }
    expect(seen).toBeGreaterThan(20)
  })

  it('accounts for every trait with a verdict the page can render', () => {
    for (const race of index.races) {
      expect(race.counts.new + race.counts.changed + race.counts.same + race.counts.unknown).toBe(race.traits)
    }
  })
})

describe('fallbacks', () => {
  it('uses initials when a racial icon crop is missing', () => {
    expect(initials('Walk on Air')).toBe('WO')
    expect(initials('Stoneform')).toBe('St')
    expect(initials('')).toBe('?')
  })
})

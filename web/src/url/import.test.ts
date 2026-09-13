import { describe, expect, it } from 'vitest'
import type { ClassicClass } from '../data/classicIndex'
import classicIndex from '../data/classic-index.json'
import { makeClass } from '../rules/fixture'
import { parseClass } from '../data/schema.zod'
import { pointsInTree, totalPoints, validate } from '../rules'
import { importReport, mapClassicBuild, normalizeName, parseImport, splitWowheadCode } from './import'
import warriorRaw from '../../../data/talents/warrior.json'

const cls = makeClass()

/** Two tabs that mirror the fixture class, plus talents Forever does not have. */
const classic: ClassicClass = {
  className: 'Test Class',
  trees: [
    {
      id: 'alpha',
      name: 'Alpha',
      talents: [
        ['A One', 5],
        ['A Two', 5],
        ['Sword Specialization', 5],
        ['B Two', 5],
      ],
    },
    {
      id: 'beta',
      name: 'Beta',
      talents: [
        ['X One', 5],
        ['Y One', 5],
      ],
    },
  ],
}

describe('parseImport', () => {
  it('reads a link to this site, with or without the origin', () => {
    expect(parseImport('https://deradon.github.io/wow-forever-talent-calc/#/warrior?v=1&t=30250-005-32')).toEqual({
      kind: 'link',
      classId: 'warrior',
      version: 1,
      build: '30250-005-32',
    })
    expect(parseImport('  #/tinker?v=2&t=52  ')).toEqual({ kind: 'link', classId: 'tinker', version: 2, build: '52' })
    expect(parseImport('#/mage')).toEqual({ kind: 'link', classId: 'mage', version: undefined, build: '' })
  })

  it('reads a bare build code', () => {
    expect(parseImport('30250-005-32')).toEqual({ kind: 'code', build: '30250-005-32' })
    expect(parseImport('5')).toEqual({ kind: 'code', build: '5' })
  })

  it('reads a Wowhead Classic link before it reads a build code', () => {
    expect(parseImport('https://www.wowhead.com/classic/talent-calc/warrior/30250-005-32')).toEqual({
      kind: 'wowhead',
      classId: 'warrior',
      code: '30250-005-32',
    })
    expect(parseImport('wowhead.com/classic/talent-calc/mage/2302250310031531--053500030013?locale=de')).toEqual({
      kind: 'wowhead',
      classId: 'mage',
      code: '2302250310031531--053500030013',
    })
  })

  it('handles the shapes Wowhead actually serves: embed, a talent order, SoD runes, the old host', () => {
    expect(parseImport('https://www.wowhead.com/classic/talent-calc/embed/druid/0140003--02')).toEqual({
      kind: 'wowhead',
      classId: 'druid',
      code: '0140003--02',
    })
    // The fourth segment is the level-by-level talent order; we ignore it.
    expect(parseImport('https://www.wowhead.com/classic/talent-calc/priest/05023013-235051002320054-5/2A0B1CEABMJfQ0DEHg1Krrrr')).toEqual({
      kind: 'wowhead',
      classId: 'priest',
      code: '05023013-235051002320054-5',
    })
    expect(parseImport('https://www.wowhead.com/classic/talent-calc/mage/-5050220103033151_156j966j476jh86r9a6rb')).toEqual({
      kind: 'wowhead',
      classId: 'mage',
      code: '-5050220103033151',
    })
    expect(parseImport('https://classic.wowhead.com/talent-calc/warrior/30305001302-05050005525010051')).toEqual({
      kind: 'wowhead',
      classId: 'warrior',
      code: '30305001302-05050005525010051',
    })
  })

  it('rejects what it cannot use, with a sentence a player can act on', () => {
    expect(parseImport('')).toMatchObject({ kind: 'error' })
    expect(parseImport('   ')).toMatchObject({ kind: 'error' })
    expect(parseImport('https://example.com/builds/42')).toMatchObject({ kind: 'error' })
    expect(parseImport('https://www.wowhead.com/classic/talent-calc/deathknight/30250')).toMatchObject({ kind: 'error' })
    expect(parseImport('https://www.wowhead.com/classic/talent-calc/warrior')).toMatchObject({ kind: 'error' })
    expect(parseImport('https://www.wowhead.com/talent-calc/warrior/sbhMZMZfbGsdkszfz')).toMatchObject({
      kind: 'error',
      message: expect.stringContaining('old Wowhead talent string'),
    })
    expect(parseImport('#/review/warrior')).toEqual({ kind: 'link', classId: 'warrior', build: '' })
    expect(parseImport('hello')).toMatchObject({ kind: 'error' })
  })
})

describe('splitWowheadCode', () => {
  it('takes a hyphenated code as written, trailing tabs omitted', () => {
    expect(splitWowheadCode('30305001302-05050005525010051', [18, 17, 17])).toEqual({
      segments: ['30305001302', '05050005525010051'],
    })
    expect(splitWowheadCode('0251030050502', [15, 19, 17])).toEqual({ segments: ['0251030050502'] })
  })

  it('keeps empty tabs, wherever they are', () => {
    expect(splitWowheadCode('-5-550350512553151', [15, 16, 15])).toEqual({ segments: ['', '5', '550350512553151'] })
    expect(splitWowheadCode('2302250310031531--053500030013', [16, 16, 17])).toEqual({
      segments: ['2302250310031531', '', '053500030013'],
    })
    expect(splitWowheadCode('--05', [15, 19, 17])).toEqual({ segments: ['', '', '05'] })
  })

  it('accepts tabs padded past the talent count, as Wowhead\'s own embed links are', () => {
    const padded = '0332400000000000000000000000-0000000000000000000000000000-0000000000000000000000000000'
    expect(splitWowheadCode(padded, [18, 17, 17])).toEqual({ segments: padded.split('-') })
  })

  it('refuses a code with more tabs than the class has', () => {
    expect(splitWowheadCode('1-2-3-4', [18, 17, 17])).toMatchObject({ error: expect.stringContaining('4 talent tabs') })
  })
})

describe('mapClassicBuild', () => {
  it('maps by name, reports what Forever does not have, and respects the rules', () => {
    // Alpha: A One 5, A Two 0, Sword Specialization 3, B Two 2; Beta: X One 1.
    const out = mapClassicBuild(cls, classic, ['5032', '1'])
    expect(out.requested).toBe(11)
    expect(out.build).toEqual({ alpha: { 'a-one': 5, 'b-two': 2 }, beta: { 'x-one': 1 } })
    expect(out.placed).toBe(8)
    expect(out.left).toBe(43)
    expect(out.unplaced).toEqual([{ name: 'Sword Specialization', points: 3, reason: 'not-in-forever' }])
  })

  it('clamps a rank Forever shortened and says so', () => {
    const short: ClassicClass = { className: 'Test Class', trees: [{ id: 'alpha', name: 'Alpha', talents: [['C One', 4]] }] }
    const out = mapClassicBuild(cls, short, ['4'])
    // c-one is maxRank 1 in Forever and needs b-one 3, so the rules drop it too.
    expect(out.unplaced.map((u) => u.reason)).toContain('clamped')
    expect(validate(cls, out.build)).toEqual([])
  })

  it('drops points the rules cannot hold and names the talent', () => {
    // B Two sits in row 1, which needs 5 points above it; nothing else is spent.
    const out = mapClassicBuild(cls, classic, ['0005'])
    expect(out.placed).toBe(0)
    expect(out.unplaced).toEqual([{ name: 'b-two', points: 5, reason: 'rules' }])
    expect(validate(cls, out.build)).toEqual([])
  })

  it('always returns a build that satisfies the rules', () => {
    const out = mapClassicBuild(cls, classic, ['5555', '55'])
    expect(validate(cls, out.build)).toEqual([])
    expect(totalPoints(out.build)).toBeLessThanOrEqual(cls.rules.maxPoints)
  })

  it('ignores digits past the end of a Classic tab and tabs past the end of the class', () => {
    const out = mapClassicBuild(cls, classic, ['5000000', '1', '9', '9'])
    expect(out.build).toEqual({ alpha: { 'a-one': 5 }, beta: { 'x-one': 1 } })
  })
})

describe('importReport', () => {
  it('reads like the brief', () => {
    expect(
      importReport({
        build: {},
        requested: 41,
        placed: 37,
        left: 4,
        unplaced: [
          { name: 'Sword Specialization', points: 3, reason: 'not-in-forever' },
          { name: 'Improved Battle Shout', points: 1, reason: 'not-in-forever' },
        ],
      }),
    ).toBe(
      '37 of 41 points placed. Dropped: Sword Specialization (not in Forever), Improved Battle Shout (not in Forever). 4 points left to spend.',
    )
  })

  it('says nothing about drops when there were none', () => {
    expect(importReport({ build: {}, requested: 51, placed: 51, left: 0, unplaced: [] })).toBe('51 of 51 points placed.')
  })

  it('truncates a long drop list', () => {
    const unplaced = Array.from({ length: 9 }, (_, i) => ({ name: `T${i}`, points: 1, reason: 'not-in-forever' as const }))
    expect(importReport({ build: {}, requested: 9, placed: 0, left: 51, unplaced })).toContain('and 3 more')
  })
})

describe('normalizeName', () => {
  it('ignores punctuation, case and spacing', () => {
    expect(normalizeName("Nature's Grasp")).toBe('naturesgrasp')
    expect(normalizeName('Improved  Heroic-Strike')).toBe('improvedheroicstrike')
  })
})

describe('a real Classic warrior build against the real Forever warrior', () => {
  const warrior = parseClass(warriorRaw, 'talents/warrior.json')
  const classicWarrior = (classicIndex as unknown as { classes: Record<string, ClassicClass> }).classes.warrior!

  it('places the Classic Arms opener into the Forever Arms tree', () => {
    // Improved Heroic Strike 0, Deflection 5, Improved Rend 0, Improved Charge 2.
    const out = mapClassicBuild(warrior, classicWarrior, ['0500002'])
    expect(validate(warrior, out.build)).toEqual([])
    expect(out.requested).toBe(7)
    expect(out.placed).toBeGreaterThan(0)
    expect(pointsInTree(out.build, warrior.trees[0]!.id)).toBe(out.placed)
  })

  it('imports the real Wowhead 17/34/0 Fury build and reports what it lost', () => {
    // Labelled Spec[17/34/0] on Wowhead's own Fury Warrior DPS guide.
    const parsed = parseImport('https://www.wowhead.com/classic/talent-calc/warrior/30305001302-05050005525010051')
    expect(parsed).toMatchObject({ kind: 'wowhead', classId: 'warrior' })
    const split = splitWowheadCode((parsed as { code: string }).code, classicWarrior.trees.map((t) => t.talents.length))
    const segments = (split as { segments: string[] }).segments
    // The digit sums are the labelled spec: this is what makes the string readable.
    expect(segments.map((s) => [...s].reduce((a, d) => a + Number(d), 0))).toEqual([17, 34])

    const out = mapClassicBuild(warrior, classicWarrior, segments)
    expect(out.requested).toBe(51)
    expect(validate(warrior, out.build)).toEqual([])
    expect(out.placed + out.unplaced.reduce((a, u) => a + u.points, 0)).toBe(51)
    // Forever reworked Arms and Fury heavily, so much of a Classic Fury build
    // has nowhere to go; the point of the flow is that the report says so.
    expect(out.placed).toBe(16)
    expect(importReport(out)).toContain('16 of 51 points placed.')
    expect(importReport(out)).toContain('Tactical Mastery (not in Forever)')
    expect(importReport(out)).toContain('35 points left to spend.')
  })

  it('places more of a Classic protection build, whose tree Forever changed less', () => {
    // Labelled Spec[3/31/17] Warrior Tank on Wowhead.
    const parsed = parseImport('https://www.wowhead.com/classic/talent-calc/warrior/03-05050005405010051-502301105')
    const split = splitWowheadCode((parsed as { code: string }).code, classicWarrior.trees.map((t) => t.talents.length))
    const out = mapClassicBuild(warrior, classicWarrior, (split as { segments: string[] }).segments)
    expect(out.requested).toBe(51)
    expect(out.placed).toBe(27)
    expect(validate(warrior, out.build)).toEqual([])
    expect(out.placed + out.unplaced.reduce((a, u) => a + u.points, 0)).toBe(51)
  })

  it('maps a deep Classic build without ever producing an invalid one', () => {
    const full = '5'.repeat(18) + '-' + '5'.repeat(17) + '-' + '5'.repeat(17)
    const split = splitWowheadCode(full, classicWarrior.trees.map((t) => t.talents.length))
    expect(split).toHaveProperty('segments')
    const out = mapClassicBuild(warrior, classicWarrior, (split as { segments: string[] }).segments)
    expect(validate(warrior, out.build)).toEqual([])
    expect(out.placed).toBe(warrior.rules.maxPoints)
    expect(out.left).toBe(0)
  })

  it('reports by name the Classic Arms talents Forever no longer has', () => {
    const forever = new Set(warrior.trees.flatMap((t) => t.talents.map((x) => normalizeName(x.name))))
    const arms = classicWarrior.trees[0]!
    const gone = arms.talents
      .map(([name], i) => ({ name, i }))
      .filter(({ name }) => !forever.has(normalizeName(name)))
    expect(gone.length, 'the Classic Arms tab must have talents Forever dropped').toBeGreaterThan(0)

    const digits = Array.from({ length: arms.talents.length }, () => '0')
    for (const { i } of gone) digits[i] = '1'
    const out = mapClassicBuild(warrior, classicWarrior, [digits.join('')])
    expect(out.placed).toBe(0)
    expect(out.unplaced.map((u) => u.name).sort()).toEqual(gone.map((g) => g.name).sort())
    expect(out.unplaced.every((u) => u.reason === 'not-in-forever')).toBe(true)
    expect(importReport(out)).toContain('0 of')
  })
})

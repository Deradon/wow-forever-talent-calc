import { describe, expect, it } from 'vitest'
import { makeClass } from '../rules/fixture'
import type { Build } from '../rules'
import { buildAsText, summarizeBuild, summaryTitle } from './summaryText'

const cls = makeClass()
const LINK = 'https://example.test/#/testclass?v=2&t=52-5'

describe('summarizeBuild', () => {
  it('groups spent talents by tree in row order and counts the spread', () => {
    const build: Build = { alpha: { 'a-two': 2, 'a-one': 5 }, beta: { 'x-one': 5 } }
    const s = summarizeBuild(cls, build)
    expect(s.spread).toBe('7/5')
    expect(s.spent).toBe(12)
    expect(s.left).toBe(39)
    expect(s.level).toBe(21) // firstPointLevel 10 - 1 + 12
    expect(s.spentTrees.map((t) => t.id)).toEqual(['alpha', 'beta'])
    expect(s.spentTrees[0]!.talents.map((t) => `${t.name} ${t.rank}/${t.maxRank}`)).toEqual(['a-one 5/5', 'a-two 2/5'])
  })

  it('lists every tree but only spent ones in spentTrees', () => {
    const s = summarizeBuild(cls, {})
    expect(s.trees).toHaveLength(2)
    expect(s.spentTrees).toHaveLength(0)
    expect(s.spread).toBe('0/0')
    expect(s.level).toBe(1)
    expect(summaryTitle(s)).toBe('Test Class 0/0 - level 1')
  })

  it('ignores tree entries that are not in the class file', () => {
    const s = summarizeBuild(cls, { ghost: { nope: 3 } })
    expect(s.trees.map((t) => t.points)).toEqual([0, 0])
    expect(s.spent).toBe(3) // totalPoints counts the raw build
  })
})

describe('buildAsText', () => {
  it('writes a Discord-ready block with class, per-tree totals, talents and the link', () => {
    const build: Build = { alpha: { 'a-one': 5, 'b-two': 3 }, beta: { 'x-one': 1 } }
    expect(buildAsText(cls, build, LINK)).toBe(
      [
        'Test Class 8/1 (level 18) - WoW Forever',
        'Alpha (8): a-one 5/5, b-two 3/5',
        'Beta (1): x-one 1/5',
        '42 points left.',
        LINK,
      ].join('\n'),
    )
  })

  it('says so when nothing is spent, and still carries the link', () => {
    expect(buildAsText(cls, {}, LINK)).toBe(['Test Class 0/0 (level 1) - WoW Forever', 'No points spent yet.', LINK].join('\n'))
  })

  it('omits the points-left line on a finished build and the link when there is none', () => {
    const full: Build = { alpha: { 'a-one': 5 } }
    const text = buildAsText(makeClass({ maxPoints: 5 }), full)
    expect(text).toBe(['Test Class 5/0 (level 14) - WoW Forever', 'Alpha (5): a-one 5/5'].join('\n'))
  })

  it('is plain text: no markdown, one line per spent tree', () => {
    const build: Build = { alpha: { 'a-one': 1 }, beta: { 'x-one': 1 } }
    const lines = buildAsText(cls, build, LINK).split('\n')
    expect(lines).toHaveLength(5)
    expect(lines.join('')).not.toMatch(/[*_`]/)
  })
})

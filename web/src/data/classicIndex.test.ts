import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { buildIndex, outPath, priorPath } from '../../scripts/gen-classic-index.mjs'
import type { ClassicIndex } from './classicIndex'
import committed from './classic-index.json'

/**
 * classic-index.json is committed (tsc runs before vite, and the file is
 * imported by the import flow), so it has to stay in step with the prior.
 */
describe('classic-index.json', () => {
  const prior = JSON.parse(readFileSync(priorPath(), 'utf8'))
  const fresh = buildIndex(prior) as ClassicIndex

  it('matches a fresh run of scripts/gen-classic-index.mjs', () => {
    expect(committed as unknown as ClassicIndex).toEqual(fresh)
    // The committed text is what the generator would write, byte for byte.
    expect(readFileSync(outPath(), 'utf8')).toBe(JSON.stringify(fresh, null, 1) + '\n')
  })

  it('covers the nine Classic classes with three tabs each', () => {
    const index = committed as unknown as ClassicIndex
    expect(Object.keys(index.classes)).toHaveLength(9)
    for (const [id, cls] of Object.entries(index.classes)) {
      expect(cls.trees, id).toHaveLength(3)
      for (const tree of cls.trees) {
        expect(tree.talents.length, `${id}/${tree.id}`).toBeGreaterThan(10)
        for (const [name, maxRank] of tree.talents) {
          expect(typeof name).toBe('string')
          expect(maxRank).toBeGreaterThan(0)
        }
      }
    }
  })

  /**
   * The load-bearing claim: digit i of a Wowhead tab segment is talent i of
   * that tab in row-major order. If the order were wrong, a real Wowhead build
   * string would put points into rows that Classic's own 5-points-per-row rule
   * forbids. Checked against three labelled builds from Wowhead's guides.
   */
  it.each([
    ['warrior', '30305001302-05050005525010051', [17, 34, 0]],
    ['mage', '2302250310031531--053500030013', [31, 0, 20]],
    ['rogue', '005023104-0233052000550100221-05', [15, 31, 5]],
  ])('decodes the real Wowhead %s build into a Classic-legal build', (classId, code, spread) => {
    const priorClass = prior.classes[classId]
    const trees = [...priorClass.trees].sort((a: { order: number }, b: { order: number }) => a.order - b.order)
    const segments = code.split('-')

    segments.forEach((segment, tab) => {
      const talents = [...trees[tab].talents].sort(
        (a: { row: number; col: number }, b: { row: number; col: number }) => a.row - b.row || a.col - b.col,
      )
      const ranks = talents.map((_: unknown, i: number) => Number(segment[i] ?? 0) || 0)
      expect(ranks.reduce((a, b) => a + b, 0), `${classId} tab ${tab + 1}`).toBe(spread[tab])

      talents.forEach((talent: { row: number; maxRank: number; name: string }, i: number) => {
        if (ranks[i] === 0) return
        expect(ranks[i], `${talent.name} over maxRank`).toBeLessThanOrEqual(talent.maxRank)
        const above = talents.reduce((n: number, t: { row: number }, j: number) => (t.row < talent.row ? n + ranks[j]! : n), 0)
        expect(above, `${classId}: ${talent.name} (row ${talent.row}) needs ${5 * talent.row} points above it`).toBeGreaterThanOrEqual(
          5 * talent.row,
        )
      })
    })
    expect(segments.length).toBeLessThanOrEqual(3)
  })

  it('keeps the Warrior tabs in Wowhead order, row-major', () => {
    const warrior = (committed as unknown as ClassicIndex).classes.warrior!
    expect(warrior.trees.map((t) => t.id)).toEqual(['arms', 'fury', 'protection'])
    expect(warrior.trees[0]!.talents.slice(0, 3)).toEqual([
      ['Improved Heroic Strike', 3],
      ['Deflection', 5],
      ['Improved Rend', 3],
    ])
    expect(warrior.trees.map((t) => t.talents.length)).toEqual([18, 17, 17])
  })
})

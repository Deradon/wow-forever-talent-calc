/**
 * The Classic Era diff: the classification rules, the exclusive name matching
 * behind them, and the generated src/data/classic-diff.json that ships them.
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { buildClassicDiff, classifyTalent, diffClass, expected, normalizeName } from '../../scripts/gen-data-index.mjs'
import { changeOf, changedCount, hasClassicDiff, removedTalents } from '../ui/classicDiff'
import diff from './classic-diff.json'

const here = fileURLToPath(new URL('.', import.meta.url))

const cell = (over: Partial<{ tree: string; treeName: string; row: number; col: number; maxRank: number }> = {}) => ({
  tree: 'arms',
  treeName: 'Arms',
  row: 2,
  col: 1,
  maxRank: 5,
  ...over,
})

describe('normalizeName', () => {
  it('ignores case, apostrophes and punctuation', () => {
    expect(normalizeName("Nature's Grasp")).toBe('natures grasp')
    expect(normalizeName('Nature’s  Grasp')).toBe('natures grasp')
    expect(normalizeName('One-Handed Weapon Specialization')).toBe('one handed weapon specialization')
    expect(normalizeName('  Enrage ')).toBe('enrage')
  })

  it('never collapses two different talents onto one key', () => {
    expect(normalizeName('Improved Wrath')).not.toBe(normalizeName('Improved Wrench'))
  })
})

describe('classifyTalent', () => {
  it('calls a talent with no Classic counterpart new, and carries no prior', () => {
    const entry = classifyTalent(cell(), undefined)
    expect(entry).toEqual({ status: 'new' })
  })

  it('calls an identical cell unchanged', () => {
    expect(classifyTalent(cell(), cell()).status).toBe('same')
  })

  it('reports a move for a different row, column or tree', () => {
    expect(classifyTalent(cell(), cell({ row: 4 })).status).toBe('moved')
    expect(classifyTalent(cell(), cell({ col: 3 })).status).toBe('moved')
    expect(classifyTalent(cell(), cell({ tree: 'fury', treeName: 'Fury' })).status).toBe('moved')
  })

  it('reports a rank change only when the cell itself did not move', () => {
    expect(classifyTalent(cell({ maxRank: 3 }), cell({ maxRank: 5 })).status).toBe('rank-changed')
    // Both at once: the cell is what the player is looking at, so the move wins,
    // and the prior still carries the old rank count for anyone who wants it.
    const both = classifyTalent(cell({ row: 4, maxRank: 3 }), cell({ maxRank: 5 }))
    expect(both.status).toBe('moved')
    expect(both.prior?.maxRank).toBe(5)
  })

  it('keeps the Classic cell on every matched entry', () => {
    expect(classifyTalent(cell({ row: 4 }), cell()).prior).toEqual(cell())
  })
})

describe('diffClass', () => {
  const forever = {
    trees: [
      {
        id: 'arms',
        name: 'Arms',
        talents: [
          { id: 'stayed', name: 'Stayed', row: 0, col: 0, maxRank: 3 },
          { id: 'slid-down', name: 'Slid Down', row: 3, col: 1, maxRank: 2 },
          { id: 'fewer-ranks', name: 'Fewer Ranks', row: 1, col: 2, maxRank: 3 },
          { id: 'brand-new', name: 'Brand New', row: 4, col: 0, maxRank: 1 },
        ],
      },
      {
        id: 'fury',
        name: 'Fury',
        talents: [{ id: 'changed-tree', name: 'Changed Tree', row: 0, col: 1, maxRank: 5 }],
      },
    ],
  }
  const prior = {
    trees: [
      {
        id: 'arms',
        name: 'Arms',
        talents: [
          { id: 'stayed', name: 'Stayed', row: 0, col: 0, maxRank: 3 },
          { id: 'slid-down', name: 'Slid Down', row: 1, col: 1, maxRank: 2 },
          { id: 'fewer-ranks', name: 'Fewer Ranks', row: 1, col: 2, maxRank: 5 },
          { id: 'changed-tree', name: 'Changed Tree', row: 0, col: 1, maxRank: 5 },
          { id: 'gone', name: 'Gone', row: 6, col: 1, maxRank: 1 },
        ],
      },
    ],
  }
  const result = diffClass(forever, prior)

  it('classifies every talent and counts them', () => {
    expect(result.counts).toEqual({ new: 1, moved: 2, 'rank-changed': 1, same: 1, removed: 1 })
  })

  it('omits unchanged talents from the file, so a missing entry means "same"', () => {
    expect(Object.keys(result.talents).sort()).toEqual(['brand-new', 'changed-tree', 'fewer-ranks', 'slid-down'])
  })

  it('follows a talent that changed tree instead of calling it new and removed', () => {
    expect(result.talents['changed-tree']).toEqual({
      status: 'moved',
      prior: { tree: 'arms', treeName: 'Arms', row: 0, col: 1, maxRank: 5 },
    })
    expect(result.removed.map((r) => r.name)).toEqual(['Gone'])
  })

  it('lists the Classic talents with no counterpart, with their old cell', () => {
    expect(result.removed[0]).toMatchObject({ id: 'gone', name: 'Gone', tree: 'arms', row: 6, maxRank: 1 })
  })

  it('matches exclusively: one Classic talent cannot back two Forever talents', () => {
    const twice = diffClass(
      { trees: [{ id: 'arms', name: 'Arms', talents: [
        { id: 'a', name: 'Twin', row: 0, col: 0, maxRank: 1 },
        { id: 'b', name: 'Twin', row: 1, col: 0, maxRank: 1 },
      ] }] },
      { trees: [{ id: 'arms', name: 'Arms', talents: [{ id: 't', name: 'Twin', row: 0, col: 0, maxRank: 1 }] }] },
    )
    expect(twice.counts.new).toBe(1)
    expect(twice.counts.same).toBe(1)
    expect(twice.removed).toEqual([])
  })

  it('prefers the counterpart in the same tree when a name occurs twice', () => {
    const shared = diffClass(
      { trees: [{ id: 'fury', name: 'Fury', talents: [{ id: 'x', name: 'Cleave', row: 2, col: 2, maxRank: 1 }] }] },
      {
        trees: [
          { id: 'arms', name: 'Arms', talents: [{ id: 'a', name: 'Cleave', row: 0, col: 0, maxRank: 1 }] },
          { id: 'fury', name: 'Fury', talents: [{ id: 'f', name: 'Cleave', row: 2, col: 2, maxRank: 1 }] },
        ],
      },
    )
    expect(shared.counts.same).toBe(1)
    expect(shared.removed.map((r) => r.tree)).toEqual(['arms'])
  })
})

describe('buildClassicDiff', () => {
  it('skips classes with no Classic counterpart rather than calling them all new', () => {
    const out = buildClassicDiff(
      [{ id: 'tinker', data: { trees: [{ id: 't', name: 'T', talents: [{ id: 'a', name: 'A', row: 0, col: 0, maxRank: 1 }] }] } }],
      { classes: {} },
    )
    expect(out.classes).toEqual({})
    expect(out.totals.new).toBe(0)
  })
})

describe('the generated classic-diff.json', () => {
  it('is up to date', () => {
    expect(readFileSync(join(here, 'classic-diff.json'), 'utf8')).toBe(expected().classicDiff)
  })

  it('covers all nine Classic classes and no example class', () => {
    expect(Object.keys(diff.classes).sort()).toEqual([
      'druid', 'hunter', 'mage', 'paladin', 'priest', 'rogue', 'shaman', 'warlock', 'warrior',
    ])
    expect(hasClassicDiff('tinker')).toBe(false)
  })

  it('totals match the per-class counts', () => {
    const sum = (key: 'new' | 'moved' | 'rank-changed' | 'same' | 'removed') =>
      Object.values(diff.classes).reduce((n, c) => n + (c.counts as Record<string, number>)[key]!, 0)
    for (const key of ['new', 'moved', 'rank-changed', 'same', 'removed'] as const) {
      expect((diff.totals as Record<string, number>)[key]).toBe(sum(key))
    }
    expect(diff.totals.new + diff.totals.moved + diff.totals['rank-changed'] + diff.totals.same).toBe(469)
  })

  it('gives every listed entry the prior cell it needs, and new talents none', () => {
    for (const cls of Object.values(diff.classes)) {
      for (const [id, entry] of Object.entries(cls.talents)) {
        expect(entry.status, id).not.toBe('same')
        if (entry.status === 'new') expect(entry).not.toHaveProperty('prior')
        else expect(entry, id).toHaveProperty('prior')
      }
    }
  })
})

describe('changeOf', () => {
  it('reads the talents the brief names for Warrior', () => {
    expect(changeOf('warrior', 'bloodthrill')?.status).toBe('new')
    expect(changeOf('warrior', 'weaponmaster')?.status).toBe('new')
    expect(removedTalents('warrior').map((t) => t.name)).toEqual(
      expect.arrayContaining(['Axe Specialization', 'Mace Specialization', 'Sword Specialization', 'Polearm Specialization']),
    )
  })

  it('reports "same" for a talent the file does not mention, in a class it knows', () => {
    expect(changeOf('warrior', 'a-talent-that-does-not-exist')).toEqual({ status: 'same' })
  })

  it('reports nothing at all for a class with no Classic prior', () => {
    expect(changeOf('tinker', 'improved-wrench')).toBeUndefined()
  })

  it('counts the changed talents for the toggle tooltip', () => {
    const w = diff.classes.warrior.counts
    expect(changedCount('warrior')).toBe(w.new + w.moved + w['rank-changed'])
    expect(changedCount('tinker')).toBe(0)
  })
})

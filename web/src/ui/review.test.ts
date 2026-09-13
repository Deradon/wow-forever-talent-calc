import { describe, expect, it } from 'vitest'
import type { Talent, Tree } from '../data/schema'
import { diffWords, filterRows, needsReview, reviewRows } from './review'

function talent(id: string, row: number, confidence: number | undefined, reviewed = false): Talent {
  return {
    id,
    name: id,
    row,
    col: 0,
    maxRank: 1,
    icon: `crop-${id}`,
    iconSource: 'crop',
    iconCrop: `data/review/x/t/${id}.icon.png`,
    description: 'x',
    ranks: [[]],
    ranksObserved: [1],
    ranksSource: 'observed',
    source: { kind: 'video', reviewed, confidence, ...(reviewed ? { reviewedBy: 'r', reviewedAt: 'now' } : {}) },
  } as Talent
}

function tree(id: string, talents: Talent[]): Tree {
  return { id, name: id, page: 'primary', order: 0, icon: 'x', rows: 7, cols: 4, talents } as Tree
}

describe('review ordering', () => {
  it('needsReview: unreviewed and below 0.8', () => {
    expect(needsReview(talent('a', 0, 0.7))).toBe(true)
    expect(needsReview(talent('a', 0, 0.8))).toBe(false)
    expect(needsReview(talent('a', 0, 0.7, true))).toBe(false)
    expect(needsReview(talent('a', 0, undefined))).toBe(false)
  })

  it('queue first, then unreviewed, then reviewed; confidence ascending within', () => {
    const trees = [
      tree('t1', [talent('rev-low', 0, 0.5, true), talent('hi', 1, 1.0), talent('low-b', 2, 0.7)]),
      tree('t2', [talent('low-a', 0, 0.6), talent('mid', 1, 0.9), talent('rev-hi', 2, 1.0, true)]),
    ]
    expect(reviewRows(trees).map((r) => r.talent.id)).toEqual(['low-a', 'low-b', 'mid', 'hi', 'rev-low', 'rev-hi'])
  })

  it('ties break by tree order, row, col', () => {
    const trees = [tree('t1', [talent('r1', 1, 1.0), talent('r0', 0, 1.0)]), tree('t2', [talent('s0', 0, 1.0)])]
    expect(reviewRows(trees).map((r) => r.talent.id)).toEqual(['r0', 'r1', 's0'])
  })
})

describe('review filters', () => {
  const trees = [
    tree('t1', [talent('low', 0, 0.5), talent('hi', 1, 1.0)]),
    tree('t2', [talent('rev', 0, 1.0, true)]),
  ]
  const rows = reviewRows(trees)

  it('flag chips select a subset, "all" keeps the order', () => {
    expect(filterRows(rows, { flag: 'all', tree: 'all', query: '' }).map((r) => r.talent.id)).toEqual(['low', 'hi', 'rev'])
    expect(filterRows(rows, { flag: 'queue', tree: 'all', query: '' }).map((r) => r.talent.id)).toEqual(['low'])
    expect(filterRows(rows, { flag: 'unreviewed', tree: 'all', query: '' }).map((r) => r.talent.id)).toEqual(['low', 'hi'])
    expect(filterRows(rows, { flag: 'crops', tree: 'all', query: '' })).toHaveLength(3)
  })

  it('narrows by tree and by free text', () => {
    expect(filterRows(rows, { flag: 'all', tree: 't2', query: '' }).map((r) => r.talent.id)).toEqual(['rev'])
    expect(filterRows(rows, { flag: 'all', tree: 'all', query: 'LO' }).map((r) => r.talent.id)).toEqual(['low'])
    expect(filterRows(rows, { flag: 'all', tree: 'all', query: 'nothing' })).toEqual([])
  })
})

describe('reading diff', () => {
  it('marks what the second reader added and dropped', () => {
    expect(diffWords('Increases your Defense Skill by 20.', 'Increases your Defense skill by 20.')).toEqual([
      { type: 'same', text: 'Increases your Defense' },
      { type: 'del', text: 'Skill' },
      { type: 'add', text: 'skill' },
      { type: 'same', text: 'by 20.' },
    ])
  })

  it('is empty-safe and collapses whitespace', () => {
    expect(diffWords('', '')).toEqual([])
    expect(diffWords('a  b', 'a b')).toEqual([{ type: 'same', text: 'a b' }])
    expect(diffWords('a b', '')).toEqual([{ type: 'del', text: 'a b' }])
  })
})

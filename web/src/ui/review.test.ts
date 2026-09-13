import { describe, expect, it } from 'vitest'
import type { Talent, Tree } from '../data/schema'
import { needsReview, reviewRows } from './review'

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

/**
 * Synthetic classes used by the rules and codec tests. Not game data.
 * `makeClass` is the original vertical-prerequisite fixture; the same-row
 * fixture is `makeHorizontalClass` at the bottom of this file.
 *
 * alpha (rows 7):          beta (rows 7):
 *   row0  a-one(5) a-two(5)   row0 x-one(5)
 *   row1  b-one(3)* b-two(5)  row1 y-one(5)
 *   row2  c-one(1)** c-two(5)
 *   row6  cap(1)
 * * b-one requires a-one 5;  ** c-one requires b-one 3 (chain a -> b -> c)
 */
import { parseClass } from '../data/schema.zod'
import type { ClassData, Talent } from '../data/schema'

function talent(id: string, row: number, col: number, maxRank: number, extra: Partial<Talent> = {}): Talent {
  return {
    id,
    name: id,
    row,
    col,
    maxRank,
    icon: 'inv_misc_questionmark',
    iconSource: 'manual',
    description: `${id} rank {0}.`,
    ranks: Array.from({ length: maxRank }, (_, i) => [i + 1]),
    ranksObserved: Array.from({ length: maxRank }, (_, i) => i + 1),
    ranksSource: 'observed',
    source: { kind: 'manual', reviewed: true, reviewedBy: 'test', reviewedAt: '2026-09-13T00:00:00Z' },
    ...extra,
  }
}

export function makeClass(overrides: Partial<ClassData['rules']> = {}): ClassData {
  return parseClass({
    schemaVersion: 1,
    class: 'testclass',
    className: 'Test Class',
    dataVersion: 2,
    dataSource: 'manual',
    generatedAt: '2026-09-13T00:00:00Z',
    rules: { pointsPerRow: 5, maxPoints: 51, firstPointLevel: 10, maxLevel: 60, rulesSource: 'assumed', ...overrides },
    pages: [{ id: 'primary', name: 'Primary' }],
    trees: [
      {
        id: 'alpha',
        name: 'Alpha',
        page: 'primary',
        order: 0,
        icon: 'inv_misc_gear_01',
        rows: 7,
        cols: 4,
        talents: [
          talent('a-one', 0, 0, 5),
          talent('a-two', 0, 1, 5),
          talent('b-one', 1, 0, 3, { requires: [{ talent: 'a-one', rank: 5 }] }),
          talent('b-two', 1, 1, 5),
          talent('c-one', 2, 0, 1, { requires: [{ talent: 'b-one', rank: 3 }] }),
          talent('c-two', 2, 1, 5),
          talent('cap', 6, 1, 1, { capstone: true }),
        ],
      },
      {
        id: 'beta',
        name: 'Beta',
        page: 'primary',
        order: 1,
        icon: 'inv_misc_gear_02',
        rows: 7,
        cols: 4,
        talents: [talent('x-one', 0, 0, 5), talent('y-one', 1, 0, 5)],
      },
    ],
  })
}

export const TEST_ORDER_V2 = {
  version: 2,
  classes: {
    testclass: {
      trees: ['alpha', 'beta'],
      order: { alpha: ['a-one', 'a-two', 'b-one', 'b-two', 'c-one', 'c-two', 'cap'], beta: ['x-one', 'y-one'] },
    },
  },
}

/** Version 1 named `a-one` `a-uno`; migration v1-v2 renames it. */
export const TEST_ORDER_V1 = {
  version: 1,
  classes: {
    testclass: {
      trees: ['alpha', 'beta'],
      order: { alpha: ['a-uno', 'a-two', 'b-one', 'b-two', 'c-one', 'c-two', 'cap'], beta: ['x-one', 'y-one'] },
    },
  },
}

export const TEST_MIGRATION_V1_V2 = {
  from: 1,
  to: 2,
  classes: { testclass: { renamed: { 'a-uno': 'a-one' } } },
}

/**
 * Second synthetic class for the same-row (horizontal) prerequisites Forever
 * added - priest Improved Mind Flay requires Mind Flay in the same row. Kept
 * apart from `makeClass` so the codec fixtures (TEST_ORDER_V2 and the digit
 * strings in codec.test.ts) stay untouched.
 *
 * flay (rows 4, cols 4), pointsPerRow 5:
 *   row0  top-one(5) c0   top-two(5) c1
 *   row1  early(2) c0*    mid(3) c1    near(3) c2**   far(1) c3***
 *   row2  below(1) c1
 * *   early requires mid 3   (right-to-left, adjacent)
 * **  near  requires mid 3   (left-to-right, adjacent)
 * *** far   requires mid 3   (left-to-right, two cells apart)
 */
export function makeHorizontalClass(overrides: Partial<ClassData['rules']> = {}): ClassData {
  return parseClass({
    schemaVersion: 1,
    class: 'testhorizontal',
    className: 'Test Horizontal',
    dataVersion: 1,
    dataSource: 'manual',
    generatedAt: '2026-09-13T00:00:00Z',
    rules: { pointsPerRow: 5, maxPoints: 51, firstPointLevel: 10, maxLevel: 60, rulesSource: 'assumed', ...overrides },
    pages: [{ id: 'primary', name: 'Primary' }],
    trees: [
      {
        id: 'flay',
        name: 'Flay',
        page: 'primary',
        order: 0,
        icon: 'inv_misc_gear_01',
        rows: 4,
        cols: 4,
        talents: [
          talent('top-one', 0, 0, 5),
          talent('top-two', 0, 1, 5),
          talent('early', 1, 0, 2, { requires: [{ talent: 'mid', rank: 3 }] }),
          talent('mid', 1, 1, 3),
          talent('near', 1, 2, 3, { requires: [{ talent: 'mid', rank: 3 }] }),
          talent('far', 1, 3, 1, { requires: [{ talent: 'mid', rank: 3 }] }),
          talent('below', 2, 1, 1),
        ],
      },
    ],
  })
}

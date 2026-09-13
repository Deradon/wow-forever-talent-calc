/**
 * Synthetic class used by the rules and codec tests. Not game data.
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

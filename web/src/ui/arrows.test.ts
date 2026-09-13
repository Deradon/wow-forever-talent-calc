/**
 * Arrow geometry (arrows.ts, drawn by Arrows.tsx). Pure numbers, so it is a unit test rather than
 * a browser one; tests/arrows.spec.ts checks the same three shapes in a real
 * layout on the `fixture-arrows` class.
 *
 * The subject is the same-row arrow Forever needs (priest Improved Mind Flay
 * requires Mind Flay in its own row): it must run along the row in both
 * directions, adjacent or not, and stop in the gutter beside the dependent.
 */
import { describe, expect, it } from 'vitest'
import { CELL, CLEARANCE, GAP, PITCH, arrowLines, type ArrowLine } from './arrows'
import { makeClass, makeHorizontalClass } from '../rules/fixture'
import type { Talent, Tree } from '../data/schema'

const flay = makeHorizontalClass().trees[0]!
const alpha = makeClass().trees[0]!

function point(line: ArrowLine, i: number): { x: number; y: number } {
  const [x, y] = line.points.split(' ')[i]!.split(',').map(Number)
  return { x: x!, y: y! }
}

function ends(line: ArrowLine): { start: { x: number; y: number }; end: { x: number; y: number } } {
  const parts = line.points.split(' ')
  return { start: point(line, 0), end: point(line, parts.length - 1) }
}

function byKey(lines: ArrowLine[], key: string): ArrowLine {
  const line = lines.find((l) => l.key === key)
  expect(line, `no arrow ${key}`).toBeDefined()
  return line!
}

function talentOf(tree: Tree, id: string): Talent {
  return tree.talents.find((t) => t.id === id)!
}

/** The cell's box in the SVG's own coordinates. */
function box(t: Talent) {
  return { left: t.col * PITCH, right: t.col * PITCH + CELL, top: t.row * PITCH, bottom: t.row * PITCH + CELL }
}

describe('arrow geometry', () => {
  const lines = arrowLines(flay, {})

  it('classifies the three shapes', () => {
    expect(arrowLines(flay, {}).map((l) => [l.key, l.kind])).toEqual([
      ['mid->early', 'horizontal'],
      ['mid->near', 'horizontal'],
      ['mid->far', 'horizontal'],
    ])
    const vertical = arrowLines(alpha, {})
    expect(vertical.map((l) => [l.key, l.kind])).toEqual([
      ['a-one->b-one', 'vertical'],
      ['b-one->c-one', 'vertical'],
    ])
  })

  const cases: { name: string; key: string; dx: 'right' | 'left' }[] = [
    { name: 'left-to-right, adjacent', key: 'mid->near', dx: 'right' },
    { name: 'left-to-right, two cells apart', key: 'mid->far', dx: 'right' },
    { name: 'right-to-left, adjacent', key: 'mid->early', dx: 'left' },
  ]

  for (const { name, key, dx } of cases) {
    describe(name, () => {
      const line = byKey(lines, key)
      const { start, end } = ends(line)
      const target = talentOf(flay, line.to)
      const source = talentOf(flay, line.from)

      it('is a straight line on the row centre line', () => {
        expect(line.points.split(' ')).toHaveLength(2)
        expect(start.y).toBe(end.y)
        expect(start.y).toBe(source.row * PITCH + CELL / 2)
        // Inside the row's own band, so it can never share a pixel with the
        // vertical leg of an L crossing the row gap above or below it.
        expect(start.y).toBeGreaterThan(box(source).top)
        expect(start.y).toBeLessThan(box(source).bottom)
      })

      it(`points ${dx}wards, from just outside the prerequisite`, () => {
        if (dx === 'right') {
          expect(end.x).toBeGreaterThan(start.x)
          expect(start.x).toBe(box(source).right + 2)
        } else {
          expect(end.x).toBeLessThan(start.x)
          expect(start.x).toBe(box(source).left - 2)
        }
      })

      it('keeps the arrowhead in the gutter, off the dependent icon', () => {
        const edge = dx === 'right' ? box(target).left : box(target).right
        expect(Math.abs(end.x - edge)).toBe(CLEARANCE)
        expect(CLEARANCE).toBeLessThan(GAP)
        expect(end.x).toBeGreaterThan(box(target).left - GAP)
        expect(end.x).toBeLessThan(box(target).right + GAP)
      })

      it('stays clear of the tier gutter left of the grid', () => {
        expect(Math.min(start.x, end.x)).toBeGreaterThanOrEqual(0)
      })
    })
  }

  it('no arrow ends inside any cell of its tree', () => {
    for (const tree of [flay, alpha]) {
      for (const line of arrowLines(tree, {})) {
        const { end } = ends(line)
        for (const t of tree.talents) {
          const b = box(t)
          const inside = end.x > b.left && end.x < b.right && end.y > b.top && end.y < b.bottom
          expect(inside, `${line.key} ends inside ${t.id}`).toBe(false)
        }
      }
    }
  })

  it('is gold once the prerequisite is at the required rank, grey below it', () => {
    expect(arrowLines(flay, { flay: { mid: 2 } }).every((l) => !l.ok)).toBe(true)
    expect(arrowLines(flay, { flay: { mid: 3 } }).every((l) => l.ok)).toBe(true)
  })

  it('skips an unknown prerequisite and a talent that requires its own cell', () => {
    const broken: Tree = {
      ...flay,
      talents: flay.talents.map((t) =>
        t.id === 'near'
          ? { ...t, requires: [{ talent: 'ghost', rank: 1 }] }
          : t.id === 'far'
            ? { ...t, requires: [{ talent: 'far', rank: 1 }] }
            : t,
      ),
    }
    expect(arrowLines(broken, {}).map((l) => l.key)).toEqual(['mid->early'])
  })

  it('still draws the Classic L when the rows differ', () => {
    const tree: Tree = {
      ...alpha,
      talents: alpha.talents.map((t) => (t.id === 'c-two' ? { ...t, requires: [{ talent: 'a-one', rank: 5 }] } : t)),
    }
    const elbow = byKey(arrowLines(tree, {}), 'a-one->c-two')
    expect(elbow.kind).toBe('elbow')
    // out of a-one's right side, along row 0, then down column 1 to row 2
    expect(elbow.points).toBe('46,22 78,22 78,107')
  })
})

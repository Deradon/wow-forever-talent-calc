/**
 * The two intent predicates that decide whether a tooltip may take the pointer.
 * They are the whole reason the sticky layer can exist without making the cell
 * under it unclickable, so they are tested against the numbers that matter: a
 * 44 px cell with a 12 px gap, and a cursor that jumps instead of travelling.
 */
import { describe, expect, it } from 'vitest'
import { APPROACH_MAX_STEP, isApproachStep, pointInside, stepLength } from './stickyTooltip'

const box = { left: 100, top: 50, right: 400, bottom: 250 }

describe('pointInside', () => {
  it('accepts the inside and the edges, rejects the outside', () => {
    expect(pointInside({ x: 200, y: 100 }, box)).toBe(true)
    expect(pointInside({ x: 100, y: 50 }, box)).toBe(true)
    expect(pointInside({ x: 99, y: 100 }, box)).toBe(false)
    expect(pointInside({ x: 200, y: 251 }, box)).toBe(false)
  })

  it('forgives the sub-pixel edge when asked to', () => {
    expect(pointInside({ x: 99, y: 100 }, box, 2)).toBe(true)
  })
})

describe('isApproachStep', () => {
  it('counts hand-sized steps', () => {
    for (const step of [1, 6, 17, APPROACH_MAX_STEP]) expect(isApproachStep(step), String(step)).toBe(true)
  })

  it('rejects a stand-still and the first sample of a gesture', () => {
    expect(isApproachStep(0)).toBe(false)
    expect(isApproachStep(Infinity)).toBe(false)
  })

  it('rejects a jump from one cell to its neighbour', () => {
    // 44 px cell + 12 px gap: the shortest jump a script can make on this grid
    expect(isApproachStep(56)).toBe(false)
    expect(isApproachStep(stepLength({ x: 0, y: 0 }, { x: 56, y: 0 }))).toBe(false)
  })
})

describe('stepLength', () => {
  it('is infinite without a previous sample, so nothing counts on the first move', () => {
    expect(stepLength(null, { x: 10, y: 10 })).toBe(Infinity)
  })

  it('measures the distance between two samples', () => {
    expect(stepLength({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(5)
  })
})

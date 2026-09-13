/**
 * Where a tooltip opens. The rule is "cover as few cells as possible and never
 * the tree header", which is pure geometry, so it is checked here rather than by
 * squinting at screenshots.
 */
import { describe, expect, it } from 'vitest'
import {
  HEADER_CLEARANCE_ROWS,
  nestedPlacement,
  placementFallbacks,
  preferredAlign,
  preferredPlacement,
  preferredSide,
} from './tooltipPlacement'

const grid = { rows: 7, cols: 4 }

describe('preferred placement', () => {
  it('opens right for every column but the last', () => {
    expect(preferredSide({ row: 0, col: 0 }, grid)).toBe('right')
    expect(preferredSide({ row: 0, col: 2 }, grid)).toBe('right')
    expect(preferredSide({ row: 0, col: 3 }, grid)).toBe('left')
  })

  it('opens upwards in the last two rows', () => {
    expect(preferredAlign({ row: 4, col: 0 }, grid)).toBe('start')
    expect(preferredAlign({ row: 5, col: 0 }, grid)).toBe('end')
    expect(preferredAlign({ row: 6, col: 0 }, grid)).toBe('end')
  })

  it('never opens upwards while the tree header is still within reach', () => {
    const shallow = { rows: 4, cols: 4 }
    for (let row = 0; row < shallow.rows; row++) {
      const align = preferredAlign({ row, col: 0 }, shallow)
      if (row < HEADER_CLEARANCE_ROWS) expect(align, `row ${row}`).toBe('start')
    }
    // one row of clearance short of the rule: still downwards
    expect(preferredAlign({ row: 2, col: 0 }, { rows: 4, cols: 4 })).toBe('start')
  })

  it('combines both into one floating-ui placement', () => {
    expect(preferredPlacement({ row: 0, col: 0 }, grid)).toBe('right-start')
    expect(preferredPlacement({ row: 6, col: 3 }, grid)).toBe('left-end')
  })
})

describe('fallbacks', () => {
  it('mirrors the side before it changes the vertical extent', () => {
    expect(placementFallbacks('right-start')).toEqual([
      'left-start',
      'right-end',
      'left-end',
      'bottom',
      'top',
    ])
  })

  it('never offers the placement it is already using', () => {
    for (const p of ['right-start', 'left-start', 'right-end', 'left-end'] as const) {
      expect(placementFallbacks(p)).not.toContain(p)
    }
  })
})

describe('nested placement', () => {
  it('keeps the chain growing in the parent direction, top-aligned', () => {
    expect(nestedPlacement('right-start')).toBe('right-start')
    expect(nestedPlacement('right-end')).toBe('right-start')
    expect(nestedPlacement('left-end')).toBe('left-start')
    expect(nestedPlacement('bottom')).toBe('right-start')
  })
})

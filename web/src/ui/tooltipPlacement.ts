/**
 * Where a talent tooltip goes, as pure geometry over grid coordinates.
 *
 * A tooltip is 300 px wide and the grid gap is 12 px, so it always covers
 * something. The rule is to cover as little as possible and never the tree
 * header:
 *
 * - the last column opens to the **left**, where the panel edge is, instead of
 *   pushing a flipped tooltip back over the whole row;
 * - the last rows open **upwards** (`-end`), but only once there are enough
 *   rows above the cell that the tooltip cannot reach the tree title;
 * - everything else opens right and downwards, which covers one neighbour.
 *
 * The fallback order keeps the vertical extent and mirrors the side first, so a
 * flip near the viewport edge does not suddenly cover a different row.
 */
export type TipSide = 'right' | 'left'
export type TipAlign = 'start' | 'end'
export type TipPlacement = `${TipSide}-${TipAlign}` | 'top' | 'bottom'

export interface GridCell {
  row: number
  col: number
}

export interface GridSize {
  rows: number
  cols: number
}

/**
 * How many rows must sit above a cell before the tooltip may grow upwards.
 * A tooltip is roughly four cell rows tall; with three rows above it, the top
 * edge still lands inside the grid rather than over the tree title.
 */
export const HEADER_CLEARANCE_ROWS = 3

/** Last column opens left; everything else opens right. */
export function preferredSide(cell: GridCell, grid: GridSize): TipSide {
  return cell.col >= grid.cols - 1 ? 'left' : 'right'
}

/** The bottom two rows grow upwards, unless that would reach the tree header. */
export function preferredAlign(cell: GridCell, grid: GridSize): TipAlign {
  const lastRows = cell.row >= grid.rows - 2
  return lastRows && cell.row >= HEADER_CLEARANCE_ROWS ? 'end' : 'start'
}

export function preferredPlacement(cell: GridCell, grid: GridSize): TipPlacement {
  return `${preferredSide(cell, grid)}-${preferredAlign(cell, grid)}`
}

/** Mirror the side first, then the alignment; top/bottom only as a last resort. */
export function placementFallbacks(placement: TipPlacement): TipPlacement[] {
  if (placement === 'top' || placement === 'bottom') return ['top', 'bottom']
  const [side, align] = placement.split('-') as [TipSide, TipAlign]
  const otherSide: TipSide = side === 'right' ? 'left' : 'right'
  const otherAlign: TipAlign = align === 'start' ? 'end' : 'start'
  return [`${otherSide}-${align}`, `${side}-${otherAlign}`, `${otherSide}-${otherAlign}`, 'bottom', 'top']
}

/**
 * A nested tooltip sits one level deeper: same side as its parent so the chain
 * reads outward, and always top-aligned with the term it belongs to.
 */
export function nestedPlacement(parent: TipPlacement): TipPlacement {
  if (parent === 'top' || parent === 'bottom') return 'right-start'
  const [side] = parent.split('-') as [TipSide, TipAlign]
  return `${side}-start`
}

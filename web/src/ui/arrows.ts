/**
 * Prerequisite-arrow geometry: pure numbers, no DOM, so the unit test
 * (arrows.test.ts) can assert on it. Arrows.tsx renders what this returns.
 */
import type { Talent, Tree } from '../data/schema'
import { rankOf, type Build } from '../rules'

export const CELL = 44
export const GAP = 12
export const PITCH = CELL + GAP
/**
 * How far short of the target cell the line stops (brief idea 6b). The
 * arrowhead's tip sits on that point, so the head lands in the 12px gap and
 * never over the icon it points at - the SVG is painted under the cells too
 * (`.cell` carries z-index 1), so the two rules back each other up.
 */
export const CLEARANCE = 5
/** Where a line leaves its source cell: just outside the border, not under it. */
export const LIFTOFF = 2

/** `vertical` same column, `horizontal` same row, `elbow` the L of both. */
export type ArrowKind = 'vertical' | 'horizontal' | 'elbow'

export interface ArrowLine {
  key: string
  /** Prerequisite talent id. */
  from: string
  /** Dependent talent id: the end the arrowhead points at. */
  to: string
  kind: ArrowKind
  /** `polyline` points, already in the SVG's own coordinates. */
  points: string
  /** The requirement is met by the current build: gold instead of dashed grey. */
  ok: boolean
}

/**
 * Geometry of every prerequisite arrow of one tree, pure so the unit tests can
 * assert on it without a DOM (web/src/ui/arrows.test.ts).
 *
 * Three shapes, all ending `CLEARANCE` short of the dependent cell so the head
 * sits in the gutter between the cells rather than on the icon:
 *
 *   same column  a straight line down (or up) the column;
 *   same row     a straight line along the row, left-to-right or right-to-left
 *                (Forever added same-row prerequisites - priest Improved Mind
 *                Flay requires Mind Flay in the same row);
 *   otherwise    the Classic L: out of the source's side, along the source
 *                row's centre line, then down the dependent's column.
 *
 * A same-row line runs at the row's own centre line, which is inside the row's
 * 44px band, so it can never share a pixel with the vertical leg of an L (those
 * only ever cross a row band at a column centre, behind a cell) and never
 * reaches the tier gutter left of the grid (its smallest x is 49).
 */
export function arrowLines(tree: Tree, build: Build): ArrowLine[] {
  const byId = new Map(tree.talents.map((t) => [t.id, t]))
  const lines: ArrowLine[] = []
  for (const t of tree.talents) {
    for (const req of t.requires ?? []) {
      const from = byId.get(req.talent)
      // Unknown, or a talent requiring itself: nothing sane to draw.
      if (!from || from.id === t.id || (from.row === t.row && from.col === t.col)) continue
      lines.push({
        key: `${from.id}->${t.id}`,
        from: from.id,
        to: t.id,
        ok: rankOf(build, tree.id, from.id) >= req.rank,
        ...shapeOf(from, t),
      })
    }
  }
  return lines
}

function shapeOf(from: Talent, to: Talent): { kind: ArrowKind; points: string } {
  const cx = (col: number) => col * PITCH + CELL / 2
  const cy = (row: number) => row * PITCH + CELL / 2
  const downwards = from.row < to.row
  const rightwards = from.col < to.col
  // Where the head stops: just outside the dependent's leading edge.
  const topEdge = downwards ? to.row * PITCH - CLEARANCE : to.row * PITCH + CELL + CLEARANCE
  const sideEdge = rightwards ? to.col * PITCH - CLEARANCE : to.col * PITCH + CELL + CLEARANCE
  // Where the line leaves the prerequisite: just outside its own border.
  const exitY = downwards ? from.row * PITCH + CELL + LIFTOFF : from.row * PITCH - LIFTOFF
  const exitX = rightwards ? from.col * PITCH + CELL + LIFTOFF : from.col * PITCH - LIFTOFF

  if (from.col === to.col) {
    return { kind: 'vertical', points: `${cx(to.col)},${exitY} ${cx(to.col)},${topEdge}` }
  }
  if (from.row === to.row) {
    // Same row: come in from the side. The old code turned upwards here and
    // drew the head across the target's icon (usability finding 18).
    return { kind: 'horizontal', points: `${exitX},${cy(from.row)} ${sideEdge},${cy(from.row)}` }
  }
  return { kind: 'elbow', points: `${exitX},${cy(from.row)} ${cx(to.col)},${cy(from.row)} ${cx(to.col)},${topEdge}` }
}

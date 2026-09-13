import type { Tree } from '../data/schema'
import { rankOf, type Build } from '../rules'

const CELL = 44
const GAP = 12
const PITCH = CELL + GAP
/**
 * How far short of the target cell the line stops (brief idea 6b). The
 * arrowhead's tip sits on that point, so the head lands in the 12px gap and
 * never over the icon it points at - the SVG is painted under the cells too
 * (`.cell` carries z-index 1), so the two rules back each other up.
 */
const CLEARANCE = 5
/** Where a line leaves its source cell: just outside the border, not under it. */
const LIFTOFF = 2

/**
 * One SVG per tree drawing a line from each prerequisite cell to its
 * dependent: straight when in the same column, L-shaped otherwise (as in
 * Classic). Satisfied requirements are solid gold, unsatisfied ones a dashed
 * slate line - dashed carries the state without colour alone, and it reads as
 * "not yet" rather than as a second kind of arrow.
 */
export function Arrows({ tree, build }: { tree: Tree; build: Build }) {
  const byId = new Map(tree.talents.map((t) => [t.id, t]))
  const lines: { key: string; points: string; ok: boolean }[] = []
  for (const t of tree.talents) {
    for (const req of t.requires ?? []) {
      const from = byId.get(req.talent)
      if (!from) continue
      const ok = rankOf(build, tree.id, from.id) >= req.rank
      const x2 = t.col * PITCH + CELL / 2
      const y2 = t.row * PITCH - CLEARANCE
      let points: string
      if (from.col === t.col) {
        points = `${x2},${from.row * PITCH + CELL + LIFTOFF} ${x2},${y2}`
      } else {
        const rightwards = from.col < t.col
        const yc = from.row * PITCH + CELL / 2
        const x1 = rightwards ? from.col * PITCH + CELL + LIFTOFF : from.col * PITCH - LIFTOFF
        if (from.row === t.row) {
          // Same row: come in from the side. The old code turned upwards here
          // and drew the head across the target's icon (usability finding 18).
          const edge = rightwards ? t.col * PITCH - CLEARANCE : t.col * PITCH + CELL + CLEARANCE
          points = `${x1},${yc} ${edge},${yc}`
        } else {
          points = `${x1},${yc} ${x2},${yc} ${x2},${y2}`
        }
      }
      lines.push({ key: `${from.id}->${t.id}`, points, ok })
    }
  }
  if (lines.length === 0) return null
  const width = tree.cols * PITCH - GAP
  const height = tree.rows * PITCH - GAP
  return (
    <svg className="arrows" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <defs>
        {/* markerWidth 4 rather than 7: the old head was as wide as a third of
            a cell and read as decoration. refX 8 puts the tip on the line's
            end point, which CLEARANCE already keeps clear of the icon. */}
        <marker id={`arrow-gold-${tree.id}`} viewBox="0 0 8 8" refX="8" refY="4" markerWidth="4" markerHeight="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#ffd100" />
        </marker>
        <marker id={`arrow-grey-${tree.id}`} viewBox="0 0 8 8" refX="8" refY="4" markerWidth="4" markerHeight="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#5a5f70" />
        </marker>
      </defs>
      {lines.map((l) => (
        <polyline
          key={l.key}
          points={l.points}
          fill="none"
          stroke={l.ok ? '#ffd100' : '#5a5f70'}
          strokeWidth={l.ok ? 2.5 : 2}
          strokeDasharray={l.ok ? undefined : '4 4'}
          strokeLinejoin="round"
          strokeLinecap="butt"
          markerEnd={`url(#arrow-${l.ok ? 'gold' : 'grey'}-${tree.id})`}
          data-arrow={l.key}
          data-satisfied={l.ok}
        />
      ))}
    </svg>
  )
}

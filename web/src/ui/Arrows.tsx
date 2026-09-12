import type { Tree } from '../data/schema'
import { rankOf, type Build } from '../rules'

const CELL = 44
const GAP = 12
const PITCH = CELL + GAP

/**
 * One SVG per tree drawing a line from each prerequisite cell to its
 * dependent: straight when in the same column, L-shaped otherwise (as in
 * Classic). Gold when the requirement is met, grey otherwise.
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
      const y2 = t.row * PITCH - 2
      let points: string
      if (from.col === t.col) {
        points = `${x2},${from.row * PITCH + CELL + 2} ${x2},${y2}`
      } else {
        const yc = from.row * PITCH + CELL / 2
        const x1 = from.col < t.col ? from.col * PITCH + CELL + 2 : from.col * PITCH - 2
        points = `${x1},${yc} ${x2},${yc} ${x2},${y2}`
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
        <marker id={`arrow-gold-${tree.id}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L8,4 L0,8 z" fill="#ffd100" />
        </marker>
        <marker id={`arrow-grey-${tree.id}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L8,4 L0,8 z" fill="#777" />
        </marker>
      </defs>
      {lines.map((l) => (
        <polyline
          key={l.key}
          points={l.points}
          fill="none"
          stroke={l.ok ? '#ffd100' : '#777'}
          strokeWidth={3}
          strokeLinejoin="round"
          markerEnd={`url(#arrow-${l.ok ? 'gold' : 'grey'}-${tree.id})`}
          data-arrow={l.key}
          data-satisfied={l.ok}
        />
      ))}
    </svg>
  )
}

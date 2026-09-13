import type { Tree } from '../data/schema'
import { arrowLines, GAP, PITCH } from './arrows'
import type { Build } from '../rules'

/**
 * One SVG per tree drawing a line from each prerequisite cell to its
 * dependent. Satisfied requirements are solid gold, unsatisfied ones a dashed
 * slate line - dashed carries the state without colour alone, and it reads as
 * "not yet" rather than as a second kind of arrow.
 */
export function Arrows({ tree, build }: { tree: Tree; build: Build }) {
  const lines = arrowLines(tree, build)
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
          data-arrow-kind={l.kind}
          data-satisfied={l.ok}
        />
      ))}
    </svg>
  )
}

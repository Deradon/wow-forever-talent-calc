import { useState, type CSSProperties, type KeyboardEvent } from 'react'
import type { ClassData, Talent, Tree } from '../data/schema'
import { canAdd, canRemove, pointsInTree, rankOf, type Build } from '../rules'
import { Arrows } from './Arrows'
import { matchesTalent } from './interaction'
import { TalentCell } from './TalentCell'

interface Props {
  cls: ClassData
  tree: Tree
  build: Build
  pointsLeft: number
  coarse: boolean
  query: string
  blocked?: { talentId: string; at: number }
  onAdd: (treeId: string, talentId: string) => void
  onRemove: (treeId: string, talentId: string) => void
  onReset: (treeId: string) => void
}

/**
 * One talent tree as a WAI grid: `role="grid"` with one `role="row"` per talent
 * row (`display: contents`, so the CSS grid still places the cells itself) and
 * a roving tabindex, so a tree is a single tab stop and arrow keys move inside
 * it instead of 50 cells sitting in the tab order (a11y review A-7).
 */
export function TreePanel({ cls, tree, build, pointsLeft, coarse, query, blocked, onAdd, onRemove, onReset }: Props) {
  const spent = pointsInTree(build, tree.id)
  const style = { '--rows': tree.rows, '--cols': tree.cols } as CSSProperties
  const [focused, setFocused] = useState<string>()

  const rows: Talent[][] = Array.from({ length: tree.rows }, () => [])
  for (const t of tree.talents) rows[t.row]?.push(t)
  for (const r of rows) r.sort((a, b) => a.col - b.col)

  // The tab stop: the focused cell, else the first spent one, else the first cell.
  const ordered = rows.flat()
  const fallback = ordered.find((t) => rankOf(build, tree.id, t.id) > 0) ?? ordered[0]
  const tabStop = (focused && ordered.some((t) => t.id === focused) ? focused : fallback?.id) ?? ''

  function move(from: Talent, dRow: number, dCol: number): Talent | undefined {
    if (dRow !== 0) {
      // Nearest talent in the target direction, preferring the same column.
      const candidates = ordered.filter((t) => (dRow > 0 ? t.row > from.row : t.row < from.row))
      if (candidates.length === 0) return undefined
      const bestRow = candidates.reduce((a, b) => (Math.abs(b.row - from.row) < Math.abs(a.row - from.row) ? b : a)).row
      const inRow = candidates.filter((t) => t.row === bestRow)
      return inRow.reduce((a, b) => (Math.abs(b.col - from.col) < Math.abs(a.col - from.col) ? b : a))
    }
    const inRow = rows[from.row] ?? []
    const i = inRow.findIndex((t) => t.id === from.id)
    return inRow[i + dCol]
  }

  function gridKeyDown(talent: Talent, e: KeyboardEvent<HTMLButtonElement>) {
    const target =
      e.key === 'ArrowRight'
        ? move(talent, 0, 1)
        : e.key === 'ArrowLeft'
          ? move(talent, 0, -1)
          : e.key === 'ArrowDown'
            ? move(talent, 1, 0)
            : e.key === 'ArrowUp'
              ? move(talent, -1, 0)
              : e.key === 'Home'
                ? ordered[0]
                : e.key === 'End'
                  ? ordered[ordered.length - 1]
                  : undefined
    if (!target) return
    e.preventDefault()
    setFocused(target.id)
    const el = e.currentTarget.closest('.tree-grid')?.querySelector<HTMLElement>(`[data-talent="${target.id}"]`)
    el?.focus()
  }

  return (
    <section className="panel p-2" data-testid={`tree-${tree.id}`}>
      <div className="mb-2 flex items-center justify-between gap-2 px-1">
        <h2 className="serif text-base text-[var(--gold)]" id={`tree-${tree.id}-name`}>
          {tree.name}
        </h2>
        <div className="flex items-center gap-2 text-sm">
          <span data-testid={`tree-points-${tree.id}`}>{spent}</span>
          <button className="btn text-xs" onClick={() => onReset(tree.id)} disabled={spent === 0} aria-label={`Reset ${tree.name}`}>
            Reset
          </button>
        </div>
      </div>
      <div
        className="tree-grid"
        style={style}
        role="grid"
        aria-labelledby={`tree-${tree.id}-name`}
        aria-rowcount={tree.rows}
        aria-colcount={tree.cols}
      >
        <Arrows tree={tree} build={build} />
        {rows.map((talents, row) => (
          <div key={row} role="row" className="tree-row" aria-rowindex={row + 1}>
            {talents.map((talent) => (
              <TalentCell
                key={talent.id}
                cls={cls}
                tree={tree}
                talent={talent}
                rank={rankOf(build, tree.id, talent.id)}
                addVerdict={canAdd(cls, build, tree.id, talent.id)}
                removeVerdict={canRemove(cls, build, tree.id, talent.id)}
                pointsLeft={pointsLeft}
                maxPoints={cls.rules.maxPoints}
                coarse={coarse}
                tabIndex={talent.id === tabStop ? 0 : -1}
                onGridFocus={() => setFocused(talent.id)}
                onGridKeyDown={(e) => gridKeyDown(talent, e)}
                rankOf={(talentId) => rankOf(build, tree.id, talentId)}
                match={query ? matchesTalent(talent, query) : undefined}
                blockedAt={blocked?.talentId === talent.id ? blocked.at : undefined}
                onAdd={() => onAdd(tree.id, talent.id)}
                onRemove={() => onRemove(tree.id, talent.id)}
              />
            ))}
          </div>
        ))}
      </div>
    </section>
  )
}

import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import type { ClassData, Talent, Tree } from '../data/schema'
import { canAdd, canRemove, pointsInRowsAbove, pointsInTree, rankOf, type Build } from '../rules'
import { Arrows } from './Arrows'
import { useHighlightNew } from './highlightNew'
import { matchesTalent } from './interaction'
import { TalentCell } from './TalentCell'
import './tiers.css'

/** Safety net for the repeat loop below; no talent in the data is near this. */
const REPEAT_CAP = 64

/** A shift- or ctrl-click in flight: one point per render until the rules refuse. */
interface Repeat {
  talentId: string
  action: 'add' | 'remove'
  /** Bumped on every gesture, so clicking the same cell twice restarts it. */
  seq: number
}

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
  /** `sel=<talentId>` from the hash: that cell opens its tooltip, pinned. */
  sel?: string
  /** The pinned card was dismissed; the class page drops `sel` from the hash. */
  onDeselect?: () => void
}

/**
 * One talent tree as a WAI grid: `role="grid"` with one `role="row"` per talent
 * row (`display: contents`, so the CSS grid still places the cells itself) and
 * a roving tabindex, so a tree is a single tab stop and arrow keys move inside
 * it instead of 50 cells sitting in the tab order (a11y review A-7).
 *
 * It also owns two things the class-page header cannot: the tier gutter with
 * the row requirements (brief idea 6) and, in the leftmost panel of the page,
 * the "highlight what's new" state (the switch itself sits in the header), which lives in
 * `highlightNew.ts` because it applies to all three trees at once.
 */
export function TreePanel({
  cls,
  tree,
  build,
  pointsLeft,
  coarse,
  query,
  blocked,
  onAdd,
  onRemove,
  onReset,
  sel,
  onDeselect,
}: Props) {
  const spent = pointsInTree(build, tree.id)
  const style = { '--rows': tree.rows, '--cols': tree.cols } as CSSProperties
  const [focused, setFocused] = useState<string>()
  const highlight = useHighlightNew()
  // One switch for the whole page, so only the leftmost panel renders it.

  const rows: Talent[][] = Array.from({ length: tree.rows }, () => [])
  for (const t of tree.talents) rows[t.row]?.push(t)
  for (const r of rows) r.sort((a, b) => a.col - b.col)

  // The tab stop: the focused cell, else the first spent one, else the first cell.
  const ordered = rows.flat()
  const fallback = ordered.find((t) => rankOf(build, tree.id, t.id) > 0) ?? ordered[0]
  const tabStop = (focused && ordered.some((t) => t.id === focused) ? focused : fallback?.id) ?? ''

  /**
   * Shift-click (max) and Ctrl/Alt-click (clear) are the same point-at-a-time
   * mutation the single click makes, repeated: `onAdd` / `onRemove` are the
   * class page's handlers and each commits one point, so the repeat cannot run
   * as a synchronous loop (every iteration would see the same stale build).
   * It runs one step per render instead and stops the moment the verdict
   * refuses - the rules stay the only authority, and no path bypasses them.
   */
  const [repeat, setRepeat] = useState<Repeat>()
  const seq = useRef(0)
  const steps = useRef(0)
  // The class page rebuilds its handlers on every render, so they are read
  // through a ref: the effect must advance when the *build* changed, not
  // whenever an unrelated re-render handed down a fresh closure.
  const latest = useRef({ cls, build, onAdd, onRemove })
  useEffect(() => {
    latest.current = { cls, build, onAdd, onRemove }
  })

  useEffect(() => {
    if (!repeat) return
    const { cls: c, build: b, onAdd: addOne, onRemove: removeOne } = latest.current
    const verdict =
      repeat.action === 'add' ? canAdd(c, b, tree.id, repeat.talentId) : canRemove(c, b, tree.id, repeat.talentId)
    if (!verdict.ok || steps.current >= REPEAT_CAP) {
      setRepeat(undefined)
      return
    }
    steps.current += 1
    if (repeat.action === 'add') addOne(tree.id, repeat.talentId)
    else removeOne(tree.id, repeat.talentId)
  }, [repeat, build, tree.id])

  function runRepeat(talentId: string, action: 'add' | 'remove') {
    const verdict =
      action === 'add' ? canAdd(cls, build, tree.id, talentId) : canRemove(cls, build, tree.id, talentId)
    // Nothing to repeat: let the single handler run so the refusal is explained
    // by the class page's blocked-action message instead of failing silently.
    if (!verdict.ok) {
      if (action === 'add') onAdd(tree.id, talentId)
      else onRemove(tree.id, talentId)
      return
    }
    seq.current += 1
    steps.current = 0
    setRepeat({ talentId, action, seq: seq.current })
  }

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
      <div className="tree-body">
        <TierGutter tree={tree} build={build} pointsPerRow={cls.rules.pointsPerRow} style={style} />
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
                  highlight={highlight}
                  tabIndex={talent.id === tabStop ? 0 : -1}
                  onGridFocus={() => setFocused(talent.id)}
                  onGridKeyDown={(e) => gridKeyDown(talent, e)}
                  rankOf={(talentId) => rankOf(build, tree.id, talentId)}
                  match={query ? matchesTalent(talent, query) : undefined}
                  blockedAt={blocked?.talentId === talent.id ? blocked.at : undefined}
                  selected={sel === talent.id}
                  onDeselect={onDeselect}
                  onAdd={() => onAdd(tree.id, talent.id)}
                  onRemove={() => onRemove(tree.id, talent.id)}
                  onMax={() => runRepeat(talent.id, 'add')}
                  onClear={() => runRepeat(talent.id, 'remove')}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/**
 * The tier gutter (brief idea 6a): the points each row needs, in a narrow
 * column left of the grid. Dim once the row is unlocked, gold on the first row
 * that is still locked - so the dark bottom of a tree explains itself instead
 * of just looking broken.
 *
 * It mirrors the grid's own track sizing (`--cell` rows, `--gap` between them,
 * the same 14px top padding), which is why it can sit outside the grid without
 * the numbers drifting away from their rows.
 */
function TierGutter({
  tree,
  build,
  pointsPerRow,
  style,
}: {
  tree: Tree
  build: Build
  pointsPerRow: number
  style: CSSProperties
}) {
  const rows = Array.from({ length: tree.rows }, (_, row) => ({
    row,
    needed: pointsPerRow * row,
    unlocked: pointsInRowsAbove(tree, build, row) >= pointsPerRow * row,
  }))
  const firstLocked = rows.find((r) => !r.unlocked)?.row ?? -1

  return (
    <div className="tier-gutter" style={style} aria-hidden="true" data-testid={`tiers-${tree.id}`}>
      {rows.map(({ row, needed, unlocked }) => (
        <span
          key={row}
          className="tier"
          data-row={row}
          data-state={needed === 0 ? 'free' : unlocked ? 'unlocked' : row === firstLocked ? 'next' : 'locked'}
        >
          {needed === 0 ? '' : needed}
        </span>
      ))}
    </div>
  )
}

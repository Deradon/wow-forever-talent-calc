import { useState, type KeyboardEvent } from 'react'
import {
  autoUpdate,
  flip,
  FloatingPortal,
  offset,
  shift,
  useClick,
  useDismiss,
  useFloating,
  useFocus,
  useHover,
  useInteractions,
} from '@floating-ui/react'
import type { ClassData, Talent, Tree } from '../data/schema'
import type { Verdict } from '../rules'
import { iconCropUrl } from '../data/iconCrop'
import { cellState } from './cellState'
import { needsReview } from './review'
import { TooltipContent } from './Tooltip'

interface Props {
  cls: ClassData
  tree: Tree
  talent: Talent
  rank: number
  addVerdict: Verdict
  removeVerdict: Verdict
  onAdd: () => void
  onRemove: () => void
  /** Points still unspent; 0 puts the cell in the dimmed "nothing left" state. */
  pointsLeft: number
  maxPoints: number
  /** Coarse pointer (phone, tablet): tap opens the tooltip, which carries +/-. */
  coarse: boolean
  /** Roving tabindex: exactly one cell per tree is in the tab order. */
  tabIndex: number
  onGridFocus: () => void
  onGridKeyDown: (e: KeyboardEvent<HTMLButtonElement>) => void
  /** Search: false dims the cell, true outlines it. Undefined = no search. */
  match?: boolean
  /** Changes whenever this cell refused an action, to replay the flash. */
  blockedAt?: number
}

/**
 * One talent. Mouse: click adds, right click refunds, hover shows the tooltip.
 * Keyboard: Enter/Space add, Backspace/Delete/- refund, arrows move within the
 * tree (the handlers go through getReferenceProps so floating-ui's own
 * onKeyDown cannot swallow them - a11y review A-1). Touch: a tap opens the
 * tooltip, which then carries explicit +/- buttons (A-2, A-3), because
 * useHover never fires and there is no right click.
 */
export function TalentCell({
  cls,
  tree,
  talent,
  rank,
  addVerdict,
  removeVerdict,
  onAdd,
  onRemove,
  pointsLeft,
  maxPoints,
  coarse,
  tabIndex,
  onGridFocus,
  onGridKeyDown,
  match,
  blockedAt,
}: Props) {
  const [open, setOpen] = useState(false)
  const [imgFailed, setImgFailed] = useState(false)
  const { refs, floatingStyles, context } = useFloating({
    open,
    onOpenChange: setOpen,
    placement: 'right-start',
    middleware: [offset(8), flip(), shift({ padding: 8 })],
    whileElementsMounted: autoUpdate,
  })
  // On a coarse pointer the tooltip is the only way to read a talent, so it
  // opens on tap and stays until dismissed; a mouse keeps hover/focus.
  const hover = useHover(context, { move: false, enabled: !coarse, delay: { open: 60, close: 0 } })
  const focus = useFocus(context, { enabled: !coarse })
  const click = useClick(context, { enabled: coarse })
  const dismiss = useDismiss(context)
  // No useRole: TooltipContent's root already carries role="tooltip" and a
  // deterministic id, so the cell points aria-describedby straight at it
  // rather than nesting a second tooltip role on the floating wrapper (A-4).
  const { getReferenceProps, getFloatingProps } = useInteractions([hover, focus, click, dismiss])
  const tooltipId = `tooltip-${talent.id}`

  const state = cellState(rank, talent.maxRank, addVerdict)
  const outOfPoints = !addVerdict.ok && addVerdict.reason === 'no-points'
  const flagged = needsReview(talent)
  // Unmatched icons render their frame crop; matched ones the fetched icon file.
  const iconUrl =
    talent.iconSource === 'crop' ? iconCropUrl(talent.iconCrop) : `${import.meta.env.BASE_URL}icons/${talent.icon}.jpg`
  const iconKind = iconUrl === undefined || imgFailed ? 'initials' : talent.iconSource === 'crop' ? 'crop' : 'file'
  const initials = talent.name
    .split(/\s+/)
    .map((w) => w[0])
    .join('')
    .slice(0, 3)
    .toUpperCase()

  function keyDown(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key === 'Backspace' || e.key === 'Delete' || e.key === '-') {
      e.preventDefault()
      onRemove()
      return
    }
    onGridKeyDown(e)
  }

  return (
    <>
      <button
        ref={refs.setReference}
        type="button"
        role="gridcell"
        className="cell"
        style={{ gridRow: talent.row + 1, gridColumn: talent.col + 1 }}
        data-testid={`talent-${talent.id}`}
        data-talent={talent.id}
        data-state={state}
        data-review={flagged ? 'true' : undefined}
        data-rank={rank}
        data-row={talent.row}
        data-col={talent.col}
        data-addable={addVerdict.ok}
        data-removable={removeVerdict.ok}
        data-icon={iconKind}
        data-match={match === undefined ? undefined : String(match)}
        tabIndex={tabIndex}
        aria-label={cellLabel(talent, rank, state, addVerdict, flagged)}
        aria-describedby={open ? tooltipId : undefined}
        aria-disabled={state === 'locked' || outOfPoints ? true : undefined}
        onFocus={onGridFocus}
        {...getReferenceProps({
          onClick: coarse ? undefined : onAdd,
          onContextMenu: (e) => {
            e.preventDefault()
            onRemove()
          },
          onKeyDown: keyDown,
        })}
      >
        <span className="icon-clip" aria-hidden="true">
          {iconKind === 'initials' ? (
            <span className="icon-fallback">{initials}</span>
          ) : (
            <img src={iconUrl} alt="" width={44} height={44} draggable={false} onError={() => setImgFailed(true)} />
          )}
        </span>
        <span className="badge">
          {rank}/{talent.maxRank}
        </span>
        {flagged && (
          <span className="review-flag" aria-hidden="true">
            ?
          </span>
        )}
        {/* Remounting on every refusal replays the flash; honours prefers-reduced-motion. */}
        {blockedAt !== undefined && <span key={blockedAt} className="cell-blocked" aria-hidden="true" />}
      </button>
      {open && (
        <FloatingPortal>
          <div
            ref={refs.setFloating}
            className="tooltip-layer"
            data-touch={coarse ? 'true' : undefined}
            style={floatingStyles}
            {...getFloatingProps()}
          >
            <TooltipContent cls={cls} tree={tree} talent={talent} rank={rank} verdict={addVerdict} id={tooltipId} />
            {outOfPoints && (
              <div className="tooltip tooltip-note" data-testid={`no-points-${talent.id}`}>
                No talent points left ({maxPoints}/{maxPoints} spent). Refund a point somewhere to spend it here.
              </div>
            )}
            {coarse && (
              <div className="tooltip tooltip-controls">
                <button
                  type="button"
                  className="btn"
                  data-testid={`touch-add-${talent.id}`}
                  disabled={!addVerdict.ok}
                  onClick={onAdd}
                  aria-label={`Add a point to ${talent.name}`}
                >
                  +
                </button>
                <span className="tooltip-controls-rank">
                  {rank}/{talent.maxRank}
                </span>
                <button
                  type="button"
                  className="btn"
                  data-testid={`touch-remove-${talent.id}`}
                  disabled={!removeVerdict.ok}
                  onClick={onRemove}
                  aria-label={`Remove a point from ${talent.name}`}
                >
                  -
                </button>
                <span className="tooltip-controls-left">{pointsLeft} left</span>
              </div>
            )}
          </div>
        </FloatingPortal>
      )}
    </>
  )
}

/**
 * Cell state in the accessible name, because locked / maxed / out-of-points /
 * flagged are otherwise colour-only cues (a11y review A-5).
 */
function cellLabel(
  talent: Talent,
  rank: number,
  state: string,
  addVerdict: Verdict,
  flagged: boolean,
): string {
  const parts = [`${talent.name}, rank ${rank} of ${talent.maxRank}`]
  if (state === 'maxed') parts.push('maxed')
  else if (!addVerdict.ok) {
    if (addVerdict.reason === 'row-locked' || addVerdict.reason === 'prereq') {
      parts.push(`locked: requires ${addVerdict.detail ?? 'more points'}`)
    } else if (addVerdict.reason === 'no-points') parts.push('no talent points left')
    else if (addVerdict.reason === 'page-full') parts.push(`page full: ${addVerdict.detail ?? 'budget reached'}`)
  }
  if (flagged) parts.push('uncertain reading, check it')
  return parts.join(', ')
}

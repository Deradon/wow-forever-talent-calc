import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react'
import {
  autoUpdate,
  flip,
  FloatingPortal,
  offset,
  safePolygon,
  shift,
  useClick,
  useDismiss,
  useFloating,
  useFocus,
  useHover,
  useInteractions,
  useMergeRefs,
  type Placement,
} from '@floating-ui/react'
import type { ClassData, Talent, Tree } from '../data/schema'
import type { Verdict } from '../rules'
import { iconCropUrl } from '../data/iconCrop'
import { cellState } from './cellState'
import './cells.css'
import { changeOf } from './classicDiff'
import { changeMarker, type ChangeMarker } from './highlightNew'
import { needsReview } from './review'
import {
  APPROACH_TICKS,
  CELL_DWELL_MS,
  claimTooltip,
  isApproachStep,
  pointInside,
  releaseTooltip,
  stepLength,
  type Point,
} from './stickyTooltip'
import { placementFallbacks, preferredPlacement } from './tooltipPlacement'
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
  /** Shift-click / Shift-Enter: add points until `canAdd` refuses. */
  onMax: () => void
  /** Ctrl- or Alt-click, Shift-Backspace: refund until `canRemove` refuses. */
  onClear: () => void
  /** "Highlight what's new" is on, so unchanged talents dim (brief idea 3). */
  highlight: boolean
  /** Points still unspent; 0 puts the cell in the dimmed "nothing left" state. */
  pointsLeft: number
  maxPoints: number
  /** Coarse pointer (phone, tablet): tap opens the tooltip, which carries +/-. */
  coarse: boolean
  /** Roving tabindex: exactly one cell per tree is in the tab order. */
  tabIndex: number
  onGridFocus: () => void
  onGridKeyDown: (e: KeyboardEvent<HTMLButtonElement>) => void
  /** Rank of any talent in this tree, so a nested prerequisite card is honest. */
  rankOf: (talentId: string) => number
  /** Search: false dims the cell, true outlines it. Undefined = no search. */
  match?: boolean
  /** Changes whenever this cell refused an action, to replay the flash. */
  blockedAt?: number
  /** `sel=<talentId>` names this cell: open its tooltip pinned and focus it. */
  selected?: boolean
  /** The pinned tooltip closed, so `sel=` is no longer true. */
  onDeselect?: () => void
}

/**
 * One talent. Mouse: click adds, right click refunds, hover shows the tooltip.
 * Shift-click adds until the rules refuse (a 5/5 talent in one click) and
 * Ctrl- or Alt-click refunds the whole talent; both walk the same `canAdd` /
 * `canRemove` verdicts one point at a time, never a special case (brief idea 4).
 * Keyboard: Enter/Space add, Backspace/Delete/- refund, arrows move within the
 * tree (the handlers go through getReferenceProps so floating-ui's own
 * onKeyDown cannot swallow them - a11y review A-1), `d` opens the derivation.
 * Touch: a tap opens the tooltip, which then carries explicit +/- buttons
 * (A-2, A-3), because useHover never fires and there is no right click.
 *
 * **Sticky tooltips.** The floating layer starts pointer-transparent, exactly as
 * before, so a click always reaches the cell. Once the pointer has dwelled on
 * the cell and then walked into the tooltip (see stickyTooltip.ts for why both
 * are required), the layer takes the pointer and stays open while the pointer is
 * inside it - which is what makes the nested tooltips reachable with a mouse.
 * Leaving it, Escape, a press on its own background, or hovering another cell
 * closes it, and the neighbour it covered is clickable again immediately.
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
  onMax,
  onClear,
  highlight,
  pointsLeft,
  maxPoints,
  coarse,
  tabIndex,
  onGridFocus,
  onGridKeyDown,
  rankOf,
  match,
  blockedAt,
  selected,
  onDeselect,
}: Props) {
  const [open, setOpen] = useState(false)
  const [sticky, setSticky] = useState(false)
  const [derivationOpen, setDerivationOpen] = useState(false)
  const [imgFailed, setImgFailed] = useState(false)

  const armedRef = useRef(false)
  const stickyRef = useRef(false)
  const dwellRef = useRef(0)
  const ticksRef = useRef(0)
  const pointRef = useRef<Point | null>(null)
  const layerRef = useRef<HTMLDivElement | null>(null)

  const reset = useCallback(() => {
    window.clearTimeout(dwellRef.current)
    armedRef.current = false
    stickyRef.current = false
    ticksRef.current = 0
    pointRef.current = null
    setSticky(false)
    setDerivationOpen(false)
    releaseTooltip(talent.id)
  }, [talent.id])

  const closeNow = useCallback(() => {
    reset()
    setOpen(false)
  }, [reset])

  /** True while the cursor is known to sit inside the (still transparent) layer. */
  const pointerOverLayer = useCallback(() => {
    const el = layerRef.current
    const p = pointRef.current
    return Boolean(el && p && pointInside(p, el.getBoundingClientRect(), 2))
  }, [])

  const onOpenChange = useCallback(
    (next: boolean) => {
      if (!next && armedRef.current && !stickyRef.current && pointerOverLayer()) {
        // The pointer left the cell towards the tooltip and is over it now.
        // safePolygon cannot see that while the layer is transparent, so the
        // approach would be cut off under the cursor. Hold instead of closing;
        // the layer is still transparent, so the cell below keeps every click.
        return
      }
      if (next) claimTooltip(talent.id, closeNow)
      else {
        reset()
        // A pinned card that closes has to take `sel=` out of the hash with it,
        // or a reload would pin it again (brief idea 12).
        if (selected) onDeselect?.()
      }
      setOpen(next)
    },
    [closeNow, onDeselect, pointerOverLayer, reset, selected, talent.id],
  )

  const placement = preferredPlacement({ row: talent.row, col: talent.col }, { rows: tree.rows, cols: tree.cols })
  const { refs, floatingStyles, context } = useFloating({
    open,
    onOpenChange,
    placement: placement as Placement,
    middleware: [
      offset(8),
      flip({ fallbackPlacements: placementFallbacks(placement) as Placement[] }),
      shift({ padding: 8 }),
    ],
    whileElementsMounted: autoUpdate,
  })
  // On a coarse pointer the tooltip is the only way to read a talent, so it
  // opens on tap and stays until dismissed; a mouse keeps hover/focus.
  const hover = useHover(context, {
    move: false,
    enabled: !coarse,
    delay: { open: 60, close: 140 },
    handleClose: safePolygon({ buffer: 2 }),
  })
  const focus = useFocus(context, { enabled: !coarse })
  const click = useClick(context, { enabled: coarse })
  const dismiss = useDismiss(context)
  // No useRole: TooltipContent's root already carries role="tooltip" and a
  // deterministic id, so the cell points aria-describedby straight at it
  // rather than nesting a second tooltip role on the floating wrapper (A-4).
  const { getReferenceProps, getFloatingProps } = useInteractions([hover, focus, click, dismiss])
  const tooltipId = `tooltip-${talent.id}`
  const setLayer = useMergeRefs([refs.setFloating, layerRef])

  // Watch the approach while the layer is still transparent (see stickyTooltip.ts).
  useEffect(() => {
    if (!open || coarse || sticky) return
    function onMove(e: PointerEvent) {
      const p = { x: e.clientX, y: e.clientY }
      const step = stepLength(pointRef.current, p)
      pointRef.current = p
      const el = layerRef.current
      if (!armedRef.current || !el) return
      if (!pointInside(p, el.getBoundingClientRect(), 2)) {
        ticksRef.current = 0
        return
      }
      if (!isApproachStep(step)) return
      ticksRef.current += 1
      if (ticksRef.current < APPROACH_TICKS) return
      stickyRef.current = true
      setSticky(true)
    }
    document.addEventListener('pointermove', onMove)
    return () => document.removeEventListener('pointermove', onMove)
  }, [open, coarse, sticky])

  /**
   * The `sel=` deep link. A tooltip normally earns the pointer by dwell and
   * approach (stickyTooltip.ts); a link is a stronger statement of intent than
   * either, so it skips straight to sticky: the card is interactive, its nested
   * terms are reachable, and it claims the single open slot like any other.
   * It closes the way every other tooltip closes - Escape, its own background,
   * or hovering another cell - and says so upwards, which drops `sel=`.
   */
  useEffect(() => {
    if (!selected) return
    armedRef.current = true
    stickyRef.current = true
    setSticky(true)
    claimTooltip(talent.id, closeNow)
    setOpen(true)
    // Focus lands on the cell, not in the card: arrow keys must keep working.
    ;(refs.domReference.current as HTMLElement | null)?.focus({ preventScroll: true })
    // Deliberately keyed on `selected` alone: `closeNow` and `refs` are stable
    // for the life of the cell, and re-running on a fresh closure would re-open
    // a card the player has just dismissed.
  }, [selected, talent.id, closeNow, refs])

  // `d` is the no-pointer way into the derivation: it opens in place, so it
  // works from the keyboard and while the layer is still transparent.
  useEffect(() => {
    if (!open) return
    function onKey(e: globalThis.KeyboardEvent) {
      if (e.key !== 'd' && e.key !== 'D') return
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const t = e.target as HTMLElement | null
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return
      e.preventDefault()
      setDerivationOpen((v) => !v)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  useEffect(() => reset, [reset])

  const state = cellState(rank, talent.maxRank, addVerdict)
  const outOfPoints = !addVerdict.ok && addVerdict.reason === 'no-points'
  const flagged = needsReview(talent)
  const change = changeOf(cls.class, talent.id)
  const marker = changeMarker(change?.status)
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
      if (e.shiftKey) onClear()
      else onRemove()
      return
    }
    if (e.key === 'd' || e.key === 'D') return // handled on the document, once
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
        data-change={change?.status}
        data-highlight={highlight ? 'true' : undefined}
        data-selected={selected ? 'true' : undefined}
        tabIndex={tabIndex}
        aria-label={cellLabel(talent, rank, state, addVerdict, flagged, marker)}
        aria-describedby={open ? tooltipId : undefined}
        aria-disabled={state === 'locked' || outOfPoints ? true : undefined}
        onFocus={onGridFocus}
        {...getReferenceProps({
          onClick: coarse
            ? undefined
            : (e: MouseEvent<HTMLButtonElement>) => {
                // metaKey is left alone: cmd-click is the browser's own gesture.
                if (e.shiftKey) onMax()
                else if (e.ctrlKey || e.altKey) onClear()
                else onAdd()
              },
          onContextMenu: (e) => {
            e.preventDefault()
            onRemove()
          },
          onKeyDown: keyDown,
          onPointerEnter: (e) => {
            if (coarse || e.pointerType !== 'mouse') return
            window.clearTimeout(dwellRef.current)
            dwellRef.current = window.setTimeout(() => {
              armedRef.current = true
            }, CELL_DWELL_MS)
          },
          onPointerLeave: () => window.clearTimeout(dwellRef.current),
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
        {/* Three markers, three slots that cannot collide: `?` top-left, the
            Classic-status marker top-right, the rank badge bottom-right. A
            talent has one status, so the star and the amber mark share the one
            slot and can never both be drawn. */}
        {marker === 'new' && (
          <span className="new-flag" data-testid={`new-flag-${talent.id}`} aria-hidden="true">
            &#9733;
          </span>
        )}
        {marker === 'reworked' && (
          <span className="changed-flag" data-testid={`reworked-flag-${talent.id}`} aria-hidden="true">
            &#9670;
          </span>
        )}
        {/* Remounting on every refusal replays the flash; honours prefers-reduced-motion. */}
        {blockedAt !== undefined && <span key={blockedAt} className="cell-blocked" aria-hidden="true" />}
      </button>
      {open && (
        <FloatingPortal>
          <div
            ref={setLayer}
            className="tooltip-layer"
            data-touch={coarse ? 'true' : undefined}
            data-sticky={sticky ? 'true' : undefined}
            data-testid={`tooltip-layer-${talent.id}`}
            style={floatingStyles}
            {...getFloatingProps({
              // Cells win: pressing the tooltip's own background gets it out of
              // the way instead of eating a second click meant for the grid.
              onPointerDown: (e) => {
                if (!sticky) return
                const t = e.target as HTMLElement
                if (t.closest('button, a, img, input')) return
                closeNow()
              },
            })}
          >
            <TooltipContent
              cls={cls}
              tree={tree}
              talent={talent}
              rank={rank}
              verdict={addVerdict}
              id={tooltipId}
              placement={placement}
              rankOf={rankOf}
              derivationOpen={derivationOpen}
            />
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
  marker: ChangeMarker | undefined,
): string {
  const parts = [`${talent.name}, rank ${rank} of ${talent.maxRank}`]
  if (state === 'maxed') parts.push('maxed')
  else if (!addVerdict.ok) {
    if (addVerdict.reason === 'row-locked' || addVerdict.reason === 'prereq') {
      parts.push(`locked: requires ${addVerdict.detail ?? 'more points'}`)
    } else if (addVerdict.reason === 'no-points') parts.push('no talent points left')
    else if (addVerdict.reason === 'page-full') parts.push(`page full: ${addVerdict.detail ?? 'budget reached'}`)
  }
  if (marker === 'new') parts.push('new in Forever')
  else if (marker === 'reworked') parts.push('reworked in Forever')
  if (flagged) parts.push('uncertain reading, check it')
  return parts.join(', ')
}

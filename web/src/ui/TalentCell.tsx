import { useState } from 'react'
import {
  autoUpdate,
  flip,
  FloatingPortal,
  offset,
  shift,
  useDismiss,
  useFloating,
  useFocus,
  useHover,
  useInteractions,
} from '@floating-ui/react'
import type { ClassData, Talent, Tree } from '../data/schema'
import type { Verdict } from '../rules'
import { cropUrl } from '../data/crops'
import { cellState } from './cellState'
import { needsReview } from './review'
import { TooltipContent } from './Tooltip'

interface Props {
  cls: ClassData
  tree: Tree
  talent: Talent
  rank: number
  addVerdict: Verdict
  onAdd: () => void
  onRemove: () => void
}

export function TalentCell({ cls, tree, talent, rank, addVerdict, onAdd, onRemove }: Props) {
  const [open, setOpen] = useState(false)
  const [imgFailed, setImgFailed] = useState(false)
  const { refs, floatingStyles, context } = useFloating({
    open,
    onOpenChange: setOpen,
    placement: 'right-start',
    middleware: [offset(8), flip(), shift({ padding: 8 })],
    whileElementsMounted: autoUpdate,
  })
  const hover = useHover(context, { move: false, delay: { open: 60, close: 0 } })
  const focus = useFocus(context)
  const dismiss = useDismiss(context)
  const { getReferenceProps, getFloatingProps } = useInteractions([hover, focus, dismiss])

  const state = cellState(rank, talent.maxRank, addVerdict)
  // Unmatched icons render their frame crop; matched ones the fetched icon file.
  const iconUrl =
    talent.iconSource === 'crop' ? cropUrl(talent.iconCrop) : `${import.meta.env.BASE_URL}icons/${talent.icon}.jpg`
  const iconKind = iconUrl === undefined || imgFailed ? 'initials' : talent.iconSource === 'crop' ? 'crop' : 'file'
  const initials = talent.name
    .split(/\s+/)
    .map((w) => w[0])
    .join('')
    .slice(0, 3)
    .toUpperCase()

  return (
    <>
      <button
        ref={refs.setReference}
        type="button"
        className="cell"
        style={{ gridRow: talent.row + 1, gridColumn: talent.col + 1 }}
        data-testid={`talent-${talent.id}`}
        data-talent={talent.id}
        data-state={state}
        data-review={needsReview(talent) ? 'true' : undefined}
        data-rank={rank}
        data-addable={addVerdict.ok}
        data-icon={iconKind}
        aria-label={`${talent.name}, rank ${rank} of ${talent.maxRank}`}
        onClick={onAdd}
        onContextMenu={(e) => {
          e.preventDefault()
          onRemove()
        }}
        onKeyDown={(e) => {
          if (e.key === 'Backspace' || e.key === 'Delete' || e.key === '-') {
            e.preventDefault()
            onRemove()
          }
        }}
        {...getReferenceProps()}
      >
        {iconKind === 'initials' ? (
          <span className="icon-fallback" aria-hidden="true">
            {initials}
          </span>
        ) : (
          <img src={iconUrl} alt="" draggable={false} onError={() => setImgFailed(true)} />
        )}
        <span className="badge">
          {rank}/{talent.maxRank}
        </span>
      </button>
      {open && (
        <FloatingPortal>
          <div ref={refs.setFloating} className="tooltip-layer" style={floatingStyles} {...getFloatingProps()}>
            <TooltipContent cls={cls} tree={tree} talent={talent} rank={rank} verdict={addVerdict} />
          </div>
        </FloatingPortal>
      )}
    </>
  )
}


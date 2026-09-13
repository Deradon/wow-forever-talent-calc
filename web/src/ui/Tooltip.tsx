import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  autoUpdate,
  flip,
  offset,
  safePolygon,
  shift,
  useClick,
  useDismiss,
  useFloating,
  useHover,
  useInteractions,
  type Placement,
} from '@floating-ui/react'
import { renderDescription, type ClassData, type Talent, type Tree } from '../data/schema'
import type { Verdict } from '../rules'
import './tooltip.css'
import { nestedPlacement, placementFallbacks, type TipPlacement } from './tooltipPlacement'
import { needsReview } from './review'
import { changeOf } from './classicDiff'
import {
  changeLine,
  DETAILS_LABEL,
  detailLines,
  fitTrustLine,
  gameRequirement,
  highestObserved,
  rankDerivationLines,
  readerViews,
  requirementLine,
  splitOnNames,
} from './tooltipText'

/** Dwell on a term before its nested tooltip opens - the same intent the cell asks for. */
export const NEST_DWELL_MS = 220

const OK: Verdict = { ok: true }

interface Props {
  cls: ClassData
  tree: Tree
  talent: Talent
  rank: number
  verdict: Verdict
  /**
   * DOM id of the tooltip root, so the cell that owns it can point
   * `aria-describedby` at it. Defaults to `tooltip-<talent id>`, which is
   * unique on a class page (one tooltip is open at a time); the review route
   * renders several per talent and passes its own.
   */
  id?: string
  /** 0 = the cell's own tooltip. Deeper cards render as plain text, no terms. */
  depth?: number
  /** Where the owning layer sits, so nested tooltips grow the same way. */
  placement?: TipPlacement
  /** Ranks of other talents in the same tree, for a nested prerequisite card. */
  rankOf?: (talentId: string) => number
  /** The `d` key (and a tap on the trust line) opens the derivation in place. */
  derivationOpen?: boolean
}

/**
 * Tooltip body: name, "Rank x/y", current-rank text (rank 0 shows rank 1),
 * "Next rank:" block, the game requirement the tooltip itself carried, a red
 * line when the click is blocked, and - at most - one amber trust line.
 *
 * Everything that is about the extraction rather than about the talent
 * (derivation, rounding, confidence, timestamp, notes) hangs off **nested
 * tooltips**: hovering an underline-dotted term in a sticky tooltip opens a
 * second, smaller one (Crusader Kings style). The terms are
 *
 * - the trust line (or `Details`) - the derivation in plain words;
 * - `Rank x/y` - the values per rank and the Classic Era values behind them;
 * - a prerequisite name in the red line - that talent's own card;
 * - the `?` marker - every reading of the tooltip, plus the source crop.
 *
 * The old native `<details>` is gone, because it was never mouse-reachable on a
 * class page. What replaces it stays reachable without a pointer: `d` opens the
 * derivation in place, a tap opens any nested tooltip, and the same lines sit in
 * the tooltip as visually hidden text so `aria-describedby` still resolves them.
 *
 * The text rules live in tooltipText.ts and are unit tested there.
 *
 * `ranksSource: "manual"` means only the observed ranks are real (the data
 * carries copies of rank 1 as placeholders). Those talents never show a
 * placeholder as if it were the next rank.
 */
export function TooltipContent({
  cls,
  tree,
  talent,
  rank,
  verdict,
  id,
  depth = 0,
  placement = 'right-start',
  rankOf,
  derivationOpen = false,
}: Props) {
  const manual = talent.ranksSource === 'manual'
  const observedMax = highestObserved(talent.ranksObserved)
  const currentRank = Math.max(1, rank)
  const currentKnown = !manual || talent.ranksObserved.includes(currentRank)
  const current = renderDescription(talent, (currentKnown ? currentRank : observedMax) - 1)

  const hasNext = rank > 0 && rank < talent.maxRank
  const nextObserved = hasNext && talent.ranksObserved.includes(rank + 1)
  const nextKnown = hasNext && (!manual || nextObserved)
  const next = nextKnown ? renderDescription(talent, rank) : undefined

  const prereqs = (talent.requires ?? []).map((r) => ({
    id: r.talent,
    rank: r.rank,
    talent: tree.talents.find((t) => t.id === r.talent),
  }))
  const blocked = requirementLine(verdict, {
    treeName: tree.name,
    rowPoints: cls.rules.pointsPerRow * talent.row,
    maxPoints: cls.rules.maxPoints,
    pageBudget: cls.rules.pointsPerPage?.[tree.page],
    prereqs: prereqs.map((p) => ({ name: p.talent?.name ?? 'an earlier talent', rank: p.rank })),
  })
  const gameReq = gameRequirement(talent.source.note)
  // Exactly one line, and it is part of the card's line budget rather than an
  // extra appended to it (brief idea 3).
  const changed = changeLine(changeOf(cls.class, talent.id), { tree: tree.id, maxRank: talent.maxRank })

  const details = detailLines(talent)
  const trust = fitTrustLine(talent, current, details.length > 0)
  const rankLines = rankDerivationLines(talent)
  const flagged = needsReview(talent)
  // Terms only on the cell's own card: a nested card is the last level (the
  // spec is one level deep), and the review route renders plain tooltips.
  const nests = depth === 0
  const nestSide = nestedPlacement(placement)

  const [openTerm, setOpenTerm] = useState<string | null>(null)
  const group = useMemo(() => ({ open: openTerm, setOpen: setOpenTerm }), [openTerm])

  const trustLabel = trust ?? (details.length > 0 ? DETAILS_LABEL : undefined)

  return (
    <NestContext.Provider value={group}>
      <div
        className="tooltip"
        data-depth={depth}
        role="tooltip"
        id={id ?? `tooltip-${talent.id}`}
        data-testid={depth === 0 ? `tooltip-${talent.id}` : `nested-tooltip-${talent.id}`}
      >
        <div className="flex items-baseline justify-between gap-2">
          <span className="name">{talent.name}</span>
          {nests && rankLines.length > 0 ? (
            <TipTerm
              termId="ranks"
              className="rank"
              placement={nestSide}
              testId={`term-ranks-${talent.id}`}
              label={`How ranks 1 to ${talent.maxRank} were derived`}
              content={<Lines lines={rankLines} />}
            >
              Rank {rank}/{talent.maxRank}
            </TipTerm>
          ) : (
            <span className="rank">
              Rank {rank}/{talent.maxRank}
            </span>
          )}
        </div>
        {talent.capstone && <div className="text-xs text-[var(--gold-dim)]">Capstone</div>}
        {changed && (
          <div className="changed" data-testid={`changed-${talent.id}`}>
            {changed}
          </div>
        )}
        {gameReq && <div className="req-game">{gameReq}</div>}
        <div className="desc">{current}</div>
        {hasNext && (
          <div className={`next${nextObserved ? '' : ' dim'}`}>
            <div className="text-white">Next rank:</div>
            <div>{next ?? 'Not known yet.'}</div>
          </div>
        )}
        {blocked && (
          <div className="req">
            {nests
              ? splitOnNames(
                  blocked,
                  prereqs.flatMap((p) => (p.talent ? [{ id: p.talent.id, name: p.talent.name }] : [])),
                ).map((seg, i) =>
                  seg.talentId ? (
                    <TipTerm
                      key={i}
                      termId={`prereq-${seg.talentId}`}
                      placement={nestSide}
                      testId={`term-prereq-${seg.talentId}`}
                      label={`The ${seg.text} talent`}
                      content={
                        <TooltipContent
                          cls={cls}
                          tree={tree}
                          talent={tree.talents.find((t) => t.id === seg.talentId)!}
                          rank={rankOf?.(seg.talentId) ?? 0}
                          verdict={OK}
                          id={`nested-tooltip-${seg.talentId}`}
                          depth={depth + 1}
                        />
                      }
                    >
                      {seg.text}
                    </TipTerm>
                  ) : (
                    <span key={i}>{seg.text}</span>
                  ),
                )
              : blocked}
          </div>
        )}
        {(trustLabel || flagged) && (
          <div className="meta" data-testid={`meta-${talent.id}`}>
            {trustLabel &&
              (nests && details.length > 0 ? (
                <TipTerm
                  termId="derivation"
                  className="trust"
                  placement={nestSide}
                  testId={`term-derivation-${talent.id}`}
                  label="Where these numbers come from"
                  content={<Lines lines={details} />}
                >
                  {trustLabel}
                </TipTerm>
              ) : (
                <span className="trust">{trustLabel}</span>
              ))}
            {flagged &&
              (nests ? (
                <TipTerm
                  termId="reading"
                  className="review-chip"
                  placement={nestSide}
                  testId={`term-reading-${talent.id}`}
                  label="What the readers saw"
                  content={<ReadingTip talent={talent} current={current} />}
                >
                  ?
                </TipTerm>
              ) : (
                <span className="review-chip">?</span>
              ))}
          </div>
        )}
        {details.length > 0 &&
          (derivationOpen ? (
            <div className="meta-body" data-testid={`derivation-${talent.id}`}>
              {details.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
          ) : (
            // Not rendered for the eye, but aria-describedby flattens the whole
            // subtree, so a screen reader still hears the derivation (A1 item 4).
            <p className="sr-only">{details.join(' ')}</p>
          ))}
      </div>
    </NestContext.Provider>
  )
}

// --- nested tooltips -------------------------------------------------------

interface NestState {
  open: string | null
  setOpen: (id: string | null) => void
}

/** One nested tooltip open at a time, per card. */
const NestContext = createContext<NestState | null>(null)

interface TermProps {
  termId: string
  testId: string
  /** Spoken name of the button, since the visible text is the talent's own copy. */
  label: string
  content: ReactNode
  placement: TipPlacement
  className?: string
  children: ReactNode
}

/**
 * An underline-dotted term inside a tooltip. Hover (with the same safe-polygon
 * approach the cell uses) or tap opens its nested tooltip.
 *
 * The nested layer is rendered **inside** the parent tooltip's DOM rather than
 * in a portal: floating-ui's `safePolygon` keeps the parent open while the
 * pointer is over a descendant of the floating element, so nesting in the DOM is
 * what makes a two-level chain survivable with the mouse at all.
 */
function TipTerm({ termId, testId, label, content, placement, className, children }: TermProps) {
  const group = useContext(NestContext)
  const open = group?.open === termId
  const setOpen = (next: boolean) => group?.setOpen(next ? termId : null)
  const [term, setTerm] = useState<HTMLButtonElement | null>(null)

  const {
    refs,
    floatingStyles,
    context,
    placement: side,
  } = useFloating({
    open,
    onOpenChange: setOpen,
    placement: placement as Placement,
    middleware: [
      offset(10),
      flip({ fallbackPlacements: placementFallbacks(placement) as Placement[] }),
      shift({ padding: 8 }),
    ],
    whileElementsMounted: autoUpdate,
  })
  const hover = useHover(context, {
    // Touch has no hover: there the tap below is the whole interaction, and
    // letting useHover see it would close the card again on the synthesized
    // mouseleave.
    mouseOnly: true,
    delay: { open: NEST_DWELL_MS, close: 120 },
    handleClose: safePolygon({ buffer: 2 }),
  })
  const click = useClick(context)
  const dismiss = useDismiss(context, { outsidePress: false })
  const { getReferenceProps, getFloatingProps } = useInteractions([hover, click, dismiss])

  // Positioned off the whole card, aligned to the term: anchoring on the term
  // alone would drop the nested tooltip on top of the text it belongs to,
  // because a term usually starts at the card's left edge.
  useEffect(() => {
    if (!term) return
    const card = term.closest('.tooltip')
    refs.setPositionReference({
      contextElement: term,
      getBoundingClientRect() {
        const t = term.getBoundingClientRect()
        const c = card?.getBoundingClientRect() ?? t
        return {
          x: c.left,
          y: t.top,
          left: c.left,
          right: c.right,
          width: c.width,
          top: t.top,
          bottom: t.bottom,
          height: t.height,
        }
      },
    })
  }, [term, refs])

  const setButton = useCallback(
    (node: HTMLButtonElement | null) => {
      refs.setReference(node)
      setTerm(node)
    },
    [refs],
  )

  return (
    <>
      <button
        ref={setButton}
        type="button"
        className={`tip-term${className ? ` ${className}` : ''}`}
        data-testid={testId}
        data-open={open ? 'true' : undefined}
        aria-label={label}
        aria-expanded={open}
        {...getReferenceProps()}
      >
        {children}
      </button>
      {open && (
        <div
          ref={refs.setFloating}
          className="tooltip-nest"
          data-side={side.split('-')[0]}
          data-testid={`nest-${testId}`}
          style={floatingStyles}
          {...getFloatingProps()}
        >
          {content}
        </div>
      )}
    </>
  )
}

function Lines({ lines }: { lines: string[] }) {
  return (
    <div className="tooltip nest-body">
      {lines.map((line) => (
        <p key={line}>{line}</p>
      ))}
    </div>
  )
}

/**
 * What the `?` marker opens: every reading of this tooltip side by side, and the
 * frame the reader looked at. The crop registry is 971 entries and review-only,
 * so it is imported on demand - a player who never opens this never fetches it.
 */
function ReadingTip({ talent, current }: { talent: Talent; current: string }) {
  const views = readerViews(talent.source, { name: talent.name, text: current })
  const crop = useCropUrl(talent.source.crop)
  return (
    <div className="tooltip nest-body" data-testid={`readings-${talent.id}`}>
      {views.map((v) => (
        <div key={v.label} className="reading">
          <div className="reading-label">
            {v.label}
            {v.percent !== undefined && <span className="reading-pct">{v.percent}%</span>}
          </div>
          {v.name && <div className="reading-name">{v.name}</div>}
          {v.text && <div className="reading-text">{v.text}</div>}
        </div>
      ))}
      {views.length === 1 && <p className="reading-text">Only one reading was recorded.</p>}
      {crop && <img className="reading-crop" src={crop} alt={`The captured tooltip for ${talent.name}`} loading="lazy" />}
    </div>
  )
}

function useCropUrl(path: string | undefined): string | undefined {
  const [url, setUrl] = useState<string>()
  useEffect(() => {
    if (!path) return
    let alive = true
    void import('../data/crops').then((m) => {
      if (alive) setUrl(m.cropUrl(path))
    })
    return () => {
      alive = false
    }
  }, [path])
  return url
}

import { renderDescription, type ClassData, type Talent, type Tree } from '../data/schema'
import type { Verdict } from '../rules'
import './tooltip.css'
import {
  DETAILS_LABEL,
  detailLines,
  fitTrustLine,
  gameRequirement,
  highestObserved,
  requirementLine,
} from './tooltipText'

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
}

/**
 * Tooltip body: name, "Rank x/y", current-rank text (rank 0 shows rank 1),
 * "Next rank:" block, the game requirement the tooltip itself carried, a red
 * line when the click is blocked, and - at most - one amber trust line with a
 * "Details" disclosure next to it.
 *
 * Everything that is about the extraction rather than about the talent
 * (derivation, rounding, confidence, timestamp, notes) sits inside that
 * disclosure; ids, scores and reader names sit on `#/review/<class>` only.
 * The text rules live in tooltipText.ts and are unit tested there.
 *
 * `ranksSource: "manual"` means only the observed ranks are real (the data
 * carries copies of rank 1 as placeholders). Those talents never show a
 * placeholder as if it were the next rank.
 */
export function TooltipContent({ cls, tree, talent, rank, verdict, id }: Props) {
  const manual = talent.ranksSource === 'manual'
  const observedMax = highestObserved(talent.ranksObserved)
  const currentRank = Math.max(1, rank)
  const currentKnown = !manual || talent.ranksObserved.includes(currentRank)
  const current = renderDescription(talent, (currentKnown ? currentRank : observedMax) - 1)

  const hasNext = rank > 0 && rank < talent.maxRank
  const nextObserved = hasNext && talent.ranksObserved.includes(rank + 1)
  const nextKnown = hasNext && (!manual || nextObserved)
  const next = nextKnown ? renderDescription(talent, rank) : undefined

  const blocked = requirementLine(verdict, {
    treeName: tree.name,
    rowPoints: cls.rules.pointsPerRow * talent.row,
    maxPoints: cls.rules.maxPoints,
    pageBudget: cls.rules.pointsPerPage?.[tree.page],
    prereqs: (talent.requires ?? []).map((r) => ({
      name: tree.talents.find((t) => t.id === r.talent)?.name ?? 'an earlier talent',
      rank: r.rank,
    })),
  })
  const gameReq = gameRequirement(talent.source.note)

  const details = detailLines(talent)
  const trust = fitTrustLine(talent, current, details.length > 0)

  return (
    <div className="tooltip" role="tooltip" id={id ?? `tooltip-${talent.id}`} data-testid={`tooltip-${talent.id}`}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="name">{talent.name}</span>
        <span className="rank">
          Rank {rank}/{talent.maxRank}
        </span>
      </div>
      {talent.capstone && <div className="text-xs text-[var(--gold-dim)]">Capstone</div>}
      {gameReq && <div className="req-game">{gameReq}</div>}
      <div className="desc">{current}</div>
      {hasNext && (
        <div className={`next${nextObserved ? '' : ' dim'}`}>
          <div className="text-white">Next rank:</div>
          <div>{next ?? 'Not known yet.'}</div>
        </div>
      )}
      {blocked && <div className="req">{blocked}</div>}
      {(trust || details.length > 0) && (
        <details className="meta" data-testid={`meta-${talent.id}`}>
          <summary>
            {trust && <span className="trust">{trust}</span>}
            <span className="more">{DETAILS_LABEL}</span>
          </summary>
          <div className="meta-body">
            {details.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

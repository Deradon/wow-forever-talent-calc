import { renderDescription, type ClassData, type Talent, type Tree } from '../data/schema'
import type { Verdict } from '../rules'

interface Props {
  cls: ClassData
  tree: Tree
  talent: Talent
  rank: number
  verdict: Verdict
}

/**
 * Tooltip body: name, "Rank x/y", current-rank text (rank 0 shows rank 1),
 * "Next rank:" block, red requirement line when locked, a caveat when ranks
 * beyond the observed ones are anticipated, and a provenance line.
 */
export function TooltipContent({ cls, tree, talent, rank, verdict }: Props) {
  const current = renderDescription(talent, Math.max(0, rank - 1))
  const hasNext = rank > 0 && rank < talent.maxRank
  const next = hasNext ? renderDescription(talent, rank) : undefined
  const anticipated = talent.ranksSource !== 'observed'
  const nextObserved = hasNext && talent.ranksObserved.includes(rank + 1)

  const requirement = requirementLine(cls, tree, talent, verdict)

  return (
    <div className="tooltip" role="tooltip" data-testid={`tooltip-${talent.id}`}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="name">{talent.name}</span>
        <span className="rank">
          Rank {rank}/{talent.maxRank}
        </span>
      </div>
      {talent.capstone && <div className="text-xs text-[var(--gold-dim)]">Capstone</div>}
      <div className="desc">{current}</div>
      {next !== undefined && (
        <div className={`next${anticipated && !nextObserved ? ' dim' : ''}`}>
          <div className="text-white">Next rank:</div>
          <div>{next}</div>
        </div>
      )}
      {requirement && <div className="req">{requirement}</div>}
      {anticipated && talent.maxRank > 1 && (
        <div className="caveat">
          Ranks {talent.ranksObserved.length > 0 ? Math.max(...talent.ranksObserved) + 1 : 2}+ anticipated ({talent.ranksSource})
          {talent.ranksNote ? `: ${talent.ranksNote}` : '.'}
        </div>
      )}
      <div className="prov">{provenance(talent)}</div>
    </div>
  )
}

function requirementLine(cls: ClassData, tree: Tree, talent: Talent, verdict: Verdict): string | undefined {
  if (verdict.ok) return undefined
  if (verdict.reason === 'row-locked') {
    return `Requires ${cls.rules.pointsPerRow * talent.row} points in ${tree.name} Talents`
  }
  if (verdict.reason === 'prereq') {
    const parts = (talent.requires ?? []).map((r) => {
      const target = tree.talents.find((t) => t.id === r.talent)
      return `${r.rank} point${r.rank === 1 ? '' : 's'} in ${target?.name ?? r.talent}`
    })
    return `Requires ${parts.join(' and ')}`
  }
  if (verdict.reason === 'page-full') return `No points left on this page (${verdict.detail ?? 'budget reached'})`
  return undefined
}

function provenance(talent: Talent): string {
  const s = talent.source
  const reviewed = s.reviewed ? 'reviewed' : 'unreviewed'
  if (s.kind === 'video') {
    const t = s.t ?? 0
    const h = Math.floor(t / 3600)
    const m = Math.floor((t % 3600) / 60)
    const sec = Math.floor(t % 60)
    const stamp = `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    const conf = s.confidence !== undefined ? `, confidence ${Math.round(s.confidence * 100)}%` : ''
    return `Read from stream at ${stamp}${conf}, ${reviewed}`
  }
  if (s.kind === 'datamined') return `Datamined from build ${s.build ?? '?'}, ${reviewed}`
  return `Entered by hand${s.note ? ` (${s.note})` : ''}, ${reviewed}`
}

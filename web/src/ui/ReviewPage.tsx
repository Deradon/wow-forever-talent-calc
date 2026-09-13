import { useEffect, useState } from 'react'
import { cropUrl } from '../data/crops'
import { hasClass, loadClass } from '../data/load'
import type { ClassData } from '../data/schema'
import { needsReview, reviewRows, streamStamp, type ReviewRow } from './review'
import { SITE_TITLE, useTitle } from './title'
import { TooltipContent } from './Tooltip'

const OK = { ok: true } as const

/**
 * `#/review/<class>`: every talent, worst reading first, with the frame crop
 * beside the rendered tooltip at rank 1 and at max rank. Read-only; edits go
 * through data/overrides/ (DATA-SCHEMA.md section 7).
 */
export function ReviewPage({ classId }: { classId: string }) {
  const [cls, setCls] = useState<ClassData>()
  const [error, setError] = useState<string>()
  useTitle(cls ? `Review ${cls.className} - ${SITE_TITLE}` : undefined)

  useEffect(() => {
    let alive = true
    if (!hasClass(classId)) {
      setError(`Unknown class "${classId}".`)
      return
    }
    loadClass(classId)
      .then((c) => alive && setCls(c))
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : String(e)))
    return () => {
      alive = false
    }
  }, [classId])

  if (error) {
    return (
      <div className="panel p-4">
        <p className="text-[var(--red)]">{error}</p>
        <a href="#/">Pick a class</a>
      </div>
    )
  }
  if (!cls) return <div className="panel p-4 text-[var(--text-dim)]">Loading {classId}...</div>

  const rows = reviewRows(cls.trees)
  const talents = rows.map((r) => r.talent)
  const stats = {
    total: talents.length,
    queue: talents.filter((t) => needsReview(t)).length,
    unreviewed: talents.filter((t) => !t.source.reviewed).length,
    manual: talents.filter((t) => t.ranksSource === 'manual').length,
    crops: talents.filter((t) => t.iconSource === 'crop').length,
  }

  return (
    <div>
      <header className="panel mb-3 flex flex-wrap items-baseline gap-x-6 gap-y-1 px-4 py-3">
        <h1 className="serif text-xl text-[var(--gold)]">Review: {cls.className}</h1>
        <span className="text-sm text-[var(--text-dim)]" data-testid="review-stats">
          {stats.total} talents, <strong className="text-[var(--text)]">{stats.queue}</strong> below 80% confidence,{' '}
          {stats.unreviewed} unreviewed, {stats.manual} with unknown higher ranks, {stats.crops} unmatched icons
        </span>
        <a href={`#/${classId}`} className="ml-auto text-sm">
          Back to the calculator
        </a>
      </header>
      <p className="mb-3 text-xs text-[var(--text-dim)]">
        Sorted worst reading first: unreviewed below 80% confidence, then other unreviewed, then reviewed. Read-only;
        corrections go into <code>data/overrides/{classId}.json</code>.
      </p>
      <ol className="flex flex-col gap-3" data-testid="review-rows">
        {rows.map((row) => (
          <Row key={row.talent.id} cls={cls} row={row} />
        ))}
      </ol>
    </div>
  )
}

function Row({ cls, row }: { cls: ClassData; row: ReviewRow }) {
  const { tree, talent } = row
  const s = talent.source
  const frame = cropUrl(s.crop)
  const icon = talent.iconSource === 'crop' ? cropUrl(talent.iconCrop) : undefined
  const flag = row.group === 0 ? 'queue' : row.group === 1 ? 'unreviewed' : 'reviewed'
  return (
    <li className="panel review-row" data-testid={`review-${talent.id}`} data-group={flag}>
      <div className="review-crops">
        {frame ? (
          <img className="review-frame" src={frame} alt={`Tooltip crop of ${talent.name}`} loading="lazy" />
        ) : (
          <div className="review-frame review-missing">no crop</div>
        )}
        <div className="flex items-center gap-2 text-xs text-[var(--text-dim)]">
          {icon ? (
            <img className="review-icon" src={icon} alt="" loading="lazy" />
          ) : (
            <span className="review-icon review-missing" />
          )}
          <span>
            icon: {talent.iconSource}
            {talent.iconSource !== 'crop' && ` (${talent.icon})`}
          </span>
        </div>
      </div>

      <dl className="review-meta">
        <dt>Talent</dt>
        <dd>
          <strong>{talent.name}</strong> <code>{talent.id}</code>
        </dd>
        <dt>Tree</dt>
        <dd>
          {tree.name}, row {talent.row}, col {talent.col}, {talent.maxRank} rank{talent.maxRank === 1 ? '' : 's'}
        </dd>
        <dt>Confidence</dt>
        <dd className={row.group === 0 ? 'text-[#f0a020]' : undefined}>
          {s.confidence !== undefined ? `${Math.round(s.confidence * 100)}%` : 'n/a'}, {s.reviewed ? `reviewed by ${s.reviewedBy ?? '?'}` : 'unreviewed'}
          {s.reader && <span className="text-[var(--text-dim)]"> ({s.reader})</span>}
        </dd>
        <dt>Ranks</dt>
        <dd>
          {talent.ranksSource}, observed {talent.ranksObserved.join(', ') || 'none'}
          {talent.ranksNote && <div className="text-[var(--text-dim)]">{talent.ranksNote}</div>}
        </dd>
        {s.kind === 'video' && (
          <>
            <dt>Frame</dt>
            <dd>
              {streamStamp(s.t ?? 0)} (t={s.t}, frame {s.frame}), video {s.video}
            </dd>
          </>
        )}
        {s.note && (
          <>
            <dt>Note</dt>
            <dd>{s.note}</dd>
          </>
        )}
        {s.readings && s.readings.length > 0 && (
          <>
            <dt>Readings</dt>
            <dd>
              <ul className="review-readings">
                {s.readings.map((r, i) => (
                  <li key={i}>
                    <span className="text-[var(--text-dim)]">
                      {r.reader}
                      {r.confidence !== undefined ? ` ${Math.round(r.confidence * 100)}%` : ''}:
                    </span>{' '}
                    {r.name && <strong>{r.name}</strong>}
                    {r.maxRank !== undefined && <span className="text-[var(--text-dim)]"> ({r.maxRank} ranks)</span>}
                    {r.description && <div>{r.description}</div>}
                  </li>
                ))}
              </ul>
            </dd>
          </>
        )}
        {talent.requires && (
          <>
            <dt>Requires</dt>
            <dd>{talent.requires.map((r) => `${r.talent} ${r.rank}`).join(', ')}</dd>
          </>
        )}
      </dl>

      <div className="review-tips">
        <TooltipContent cls={cls} tree={tree} talent={talent} rank={1} verdict={OK} />
        {talent.maxRank > 1 && <TooltipContent cls={cls} tree={tree} talent={talent} rank={talent.maxRank} verdict={OK} />}
      </div>
    </li>
  )
}

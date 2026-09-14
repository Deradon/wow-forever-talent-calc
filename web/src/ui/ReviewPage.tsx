import { useEffect, useMemo, useState } from 'react'
import { cropUrl } from '../data/crops'
import { hasClass, listClasses, loadClass } from '../data/load'
import type { ClassData, Talent } from '../data/schema'
import { copyLabel, useCopy } from './copy'
import { buildOverrideEntry, overrideEntriesText, overrideEntryText, wrongReadingUrl } from './overrideEntry'
import './review.css'
import { REPO_URL } from './site'
import {
  ALL_FLAGS,
  diffWords,
  filterRows,
  needsReview,
  reviewRows,
  streamStamp,
  type ReviewFlag,
  type ReviewRow,
} from './review'
import { SITE_TITLE, useTitle } from './title'
import { TooltipContent } from './Tooltip'

const OK = { ok: true } as const

const FLAG_LABEL: Record<ReviewFlag, string> = {
  all: 'all',
  queue: 'queue',
  unreviewed: 'unreviewed',
  manual: 'unknown ranks',
  crops: 'unmatched icons',
}

/**
 * `#/review/<class>`: every talent, worst reading first, with the frame crop
 * beside the rendered tooltip at rank 1 and at max rank. This is the one place
 * where pipeline internals (Classic ids, similarity scores, reader names, crop
 * paths) are allowed on screen.
 *
 * Still read-only in the sense that matters: nothing here writes to the
 * repository, and every correction goes through `data/overrides/<class>.json`
 * and the exporter (DATA-SCHEMA.md section 7). What it does do is hand the
 * reviewer the override entry on the clipboard, prefilled from the record, so
 * the id, the tree, the name and the description are not retyped by hand.
 */
export function ReviewPage({ classId }: { classId: string }) {
  const [cls, setCls] = useState<ClassData>()
  const [error, setError] = useState<string>()
  const [flag, setFlag] = useState<ReviewFlag>('all')
  const [tree, setTree] = useState('all')
  const [query, setQuery] = useState('')
  const [compact, setCompact] = useState(false)
  const [allState, copyAll] = useCopy()
  const [allText, setAllText] = useState('')
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

  const rows = useMemo(() => (cls ? reviewRows(cls.trees) : []), [cls])
  const shown = useMemo(() => filterRows(rows, { flag, tree, query }), [rows, flag, tree, query])

  if (error) {
    return (
      <div className="panel p-4">
        <p className="text-[var(--red)]">{error}</p>
        <a href="#/">Pick a class</a>
      </div>
    )
  }
  if (!cls) return <div className="panel p-4 text-[var(--text-dim)]">Loading {classId}...</div>

  const talents = rows.map((r) => r.talent)
  const stats = {
    total: talents.length,
    queue: talents.filter((t) => needsReview(t)).length,
    unreviewed: talents.filter((t) => !t.source.reviewed).length,
    manual: talents.filter((t) => t.ranksSource === 'manual').length,
    crops: talents.filter((t) => t.iconSource === 'crop').length,
  }
  const count = (f: ReviewFlag) =>
    f === 'all' ? stats.total : f === 'queue' ? stats.queue : f === 'unreviewed' ? stats.unreviewed : f === 'manual' ? stats.manual : stats.crops

  return (
    <div>
      <header className="panel review-toolbar mb-3 flex flex-col gap-2 px-4 py-3">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h1 className="serif text-xl text-[var(--gold)]">Review: {cls.className}</h1>
          <span className="text-sm text-[var(--text-dim)]" data-testid="review-stats">
            {shown.length} of {stats.total} talents shown, <strong className="text-[var(--text)]">{stats.queue}</strong> below 80%
            confidence, {stats.unreviewed} unreviewed, {stats.manual} with unknown higher ranks, {stats.crops} unmatched icons
          </span>
          <span className="ml-auto flex flex-wrap gap-x-3 text-sm">
            {listClasses()
              .filter((c) => c.id !== classId)
              .map((c) => (
                <a key={c.id} href={`#/review/${c.id}`}>
                  {c.id}
                </a>
              ))}
            <a href={`#/${classId}`}>Back to the calculator</a>
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2" data-testid="review-filters">
          {ALL_FLAGS.map((f) => (
            <button key={f} type="button" className="chip" aria-pressed={flag === f} onClick={() => setFlag(f)}>
              {FLAG_LABEL[f]} ({count(f)})
            </button>
          ))}
          <span className="mx-1 text-[var(--text-dim)]">|</span>
          <button type="button" className="chip" aria-pressed={tree === 'all'} onClick={() => setTree('all')}>
            all trees
          </button>
          {cls.trees.map((t) => (
            <button key={t.id} type="button" className="chip" aria-pressed={tree === t.id} onClick={() => setTree(t.id)}>
              {t.name} ({t.talents.length})
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-2">
            <span className="text-[var(--text-dim)]">Find</span>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="name, id or description"
              className="w-56 rounded border border-[var(--grey)] bg-black/40 px-2 py-1"
              data-testid="review-search"
            />
          </label>
          <label className="flex items-center gap-2">
            <span className="text-[var(--text-dim)]">Jump to</span>
            <select
              className="max-w-64 rounded border border-[var(--grey)] bg-black/40 px-2 py-1"
              value=""
              data-testid="review-jump"
              onChange={(e) => {
                const el = document.getElementById(`review-row-${e.target.value}`)
                el?.scrollIntoView({ block: 'start' })
                e.target.value = ''
              }}
            >
              <option value="">{shown.length} rows</option>
              {shown.map((r) => (
                <option key={r.talent.id} value={r.talent.id}>
                  {r.tree.name}: {r.talent.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={compact} onChange={(e) => setCompact(e.target.checked)} />
            <span className="text-[var(--text-dim)]">Compact rows</span>
          </label>
          {/* "Flagged" is whatever the filter above shows: pick `queue`, a tree
              or a search term first, then take the whole set in one go. */}
          <button
            type="button"
            className="btn"
            data-testid="copy-all-overrides"
            disabled={shown.length === 0}
            onClick={() => {
              const text = overrideEntriesText(shown.map((r) => buildOverrideEntry(r)))
              setAllText(text)
              copyAll(text)
            }}
          >
            {copyLabel(allState, `Copy all flagged (${shown.length})`)}
          </button>
        </div>
        {allState === 'failed' && (
          <textarea
            className="review-paste"
            readOnly
            rows={6}
            value={allText}
            data-testid="copy-all-fallback"
            onFocus={(e) => e.currentTarget.select()}
          />
        )}
      </header>

      <p className="review-hint mb-3 text-[var(--text-dim)]">
        Sorted worst reading first: unreviewed below 80% confidence, then other unreviewed, then reviewed. Nothing on
        this page writes to the repository. <strong className="text-[var(--text)]">Copy override</strong> puts one entry
        on the clipboard; paste it inside the <code>"overrides": [ ... ]</code> array of{' '}
        <code>data/overrides/{classId}.json</code>, correct the name and the description in the <code>set</code> block,
        and replace the two <code>TODO</code>s (<code>reason</code>, <code>by</code>). Then, from{' '}
        <code>pipeline/</code>: <code>uv run stages/08_export.py promote {classId}</code> and{' '}
        <code>uv run python validate.py --check ../data/talents/{classId}.json</code>. The full workflow is in{' '}
        <a href={`${REPO_URL}/blob/main/CONTRIBUTING.md`} target="_blank" rel="noreferrer">
          CONTRIBUTING.md
        </a>
        .
      </p>
      <ol className="flex flex-col gap-3" data-testid="review-rows">
        {shown.map((row) => (
          <Row key={row.talent.id} cls={cls} row={row} compact={compact} />
        ))}
        {shown.length === 0 && <li className="panel p-4 text-[var(--text-dim)]">No talent matches this filter.</li>}
      </ol>
    </div>
  )
}

/** Matched icons are fetched files; unmatched ones only exist as frame crops. */
function iconUrl(talent: Talent): string | undefined {
  return talent.iconSource === 'crop' ? cropUrl(talent.iconCrop) : `${import.meta.env.BASE_URL}icons/${talent.icon}.jpg`
}

function Row({ cls, row, compact }: { cls: ClassData; row: ReviewRow; compact: boolean }) {
  const { tree, talent } = row
  const [iconFailed, setIconFailed] = useState(false)
  const s = talent.source
  const frame = cropUrl(s.crop)
  const icon = iconFailed ? undefined : iconUrl(talent)
  const flag = row.group === 0 ? 'queue' : row.group === 1 ? 'unreviewed' : 'reviewed'
  return (
    <li
      className="panel review-row"
      id={`review-row-${talent.id}`}
      data-testid={`review-${talent.id}`}
      data-group={flag}
      style={compact ? { gridTemplateColumns: 'minmax(220px, 1fr) auto' } : undefined}
    >
      {!compact && (
        <div className="review-crops">
          {frame ? (
            <img className="review-frame" src={frame} alt={`Tooltip crop of ${talent.name}`} loading="lazy" />
          ) : (
            <div className="review-frame review-missing">no crop</div>
          )}
          <div className="flex items-center gap-2 text-xs text-[var(--text-dim)]">
            {icon ? (
              <img className="review-icon" src={icon} alt="" loading="lazy" onError={() => setIconFailed(true)} />
            ) : (
              <span className="review-icon review-missing" />
            )}
            <span>
              icon: {talent.iconSource}
              {talent.iconSource !== 'crop' && ` (${talent.icon})`}
            </span>
          </div>
        </div>
      )}

      <div className="review-body">
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
          {s.confidence !== undefined ? `${Math.round(s.confidence * 100)}%` : 'n/a'},{' '}
          {s.reviewed ? `reviewed by ${s.reviewedBy ?? '?'}` : 'unreviewed'}
          {s.reader && <span className="text-[var(--text-dim)]"> ({s.reader})</span>}
        </dd>
        <dt>Ranks</dt>
        <dd>
          {talent.ranksSource}, observed {talent.ranksObserved.join(', ') || 'none'}
          {talent.ranksNote && <div className="text-[var(--text-dim)]">{talent.ranksNote}</div>}
        </dd>
        {talent.ranksPrior && (
          <>
            <dt>Classic</dt>
            <dd className="text-[var(--text-dim)]">
              talent {talent.ranksPrior.classicTalentId}, {talent.ranksPrior.match}, similarity{' '}
              {talent.ranksPrior.similarity.toFixed(2)}
            </dd>
          </>
        )}
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
                    {r.description && <Diff a={talent.description} b={r.description} />}
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
        <RowActions cls={cls} row={row} />
      </div>

      <div className="review-tips">
        <TooltipContent
          cls={cls}
          tree={tree}
          talent={talent}
          rank={1}
          verdict={OK}
          id={`review-tip-${talent.id}-rank1`}
        />
        {!compact && talent.maxRank > 1 && (
          <TooltipContent
            cls={cls}
            tree={tree}
            talent={talent}
            rank={talent.maxRank}
            verdict={OK}
            id={`review-tip-${talent.id}-rank${talent.maxRank}`}
          />
        )}
      </div>
    </li>
  )
}

/**
 * Per row: the override entry on the clipboard, and the same record as a
 * pre-filled issue for someone who is not going to open a pull request. The
 * textarea only appears when the clipboard refused, which is the common case
 * over plain http.
 */
function RowActions({ cls, row }: { cls: ClassData; row: ReviewRow }) {
  const [state, copy] = useCopy()
  const [text, setText] = useState('')
  return (
    <div className="review-actions">
      <button
        type="button"
        className="btn"
        data-testid={`copy-override-${row.talent.id}`}
        onClick={() => {
          const entry = overrideEntryText(buildOverrideEntry(row))
          setText(entry)
          copy(entry)
        }}
      >
        {copyLabel(state, 'Copy override')}
      </button>
      <a
        href={wrongReadingUrl(row, cls.class, REPO_URL)}
        target="_blank"
        rel="noreferrer"
        data-testid={`report-${row.talent.id}`}
      >
        Report on GitHub
      </a>
      <span className="text-[var(--text-dim)]">
        into <code>data/overrides/{cls.class}.json</code>
      </span>
      {state === 'failed' && (
        <textarea
          className="review-paste"
          readOnly
          rows={8}
          value={text}
          data-testid={`copy-fallback-${row.talent.id}`}
          onFocus={(e) => e.currentTarget.select()}
        />
      )}
    </div>
  )
}

/** The stored description against a second reader's, word by word. */
function Diff({ a, b }: { a: string; b: string }) {
  return (
    <div>
      {diffWords(a, b).map((op, i) => (
        <span key={i} className={op.type === 'add' ? 'diff-add' : op.type === 'del' ? 'diff-del' : undefined}>
          {op.text}{' '}
        </span>
      ))}
    </div>
  )
}

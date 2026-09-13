import { useEffect, useMemo, useRef } from 'react'
import type { ClassData } from '../data/schema'
import { pointsInTree, requiredLevel, totalPoints, type Build } from '../rules'
import { ClassSwitcher } from './ClassSwitcher'
import { matchesTalent } from './interaction'

interface Props {
  cls: ClassData
  classId: string
  build: Build
  query: string
  onQuery: (q: string) => void
  onJump: (treeId: string, talentId: string) => void
  onReset: () => void
  /** Set when Reset was just pressed; the button becomes "Build reset - Undo". */
  resetUndoAt?: number
  onUndoReset: () => void
}

const MAX_RESULTS = 8

import { HighlightNewToggle } from './HighlightNewToggle'

export function Header({ cls, classId, build, query, onQuery, onJump, onReset, resetUndoAt, onUndoReset }: Props) {
  const total = totalPoints(build)
  const left = cls.rules.maxPoints - total
  const level = requiredLevel(total, cls.rules)
  const search = useRef<HTMLInputElement>(null)

  // `/` focuses the search box, as on Wowhead (usability 1).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return
      const el = e.target as HTMLElement | null
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return
      e.preventDefault()
      search.current?.focus()
      search.current?.select()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const results = useMemo(() => {
    if (!query.trim()) return []
    return cls.trees.flatMap((tree) =>
      tree.talents.filter((t) => matchesTalent(t, query)).map((talent) => ({ tree, talent })),
    )
  }, [cls, query])

  return (
    <header className="panel mb-3 flex flex-col gap-2 px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <h1 className="serif text-xl text-[var(--gold)]">{cls.className}</h1>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
          <span>
            Points left:{' '}
            <strong data-testid="points-left" className={left === 0 ? 'text-[var(--gold)]' : undefined}>
              {left}
            </strong>
            <span className="text-[var(--text-dim)]"> / {cls.rules.maxPoints}</span>
            {left === 0 && (
              <span className="ml-2 text-xs text-[var(--gold)]" data-testid="no-points-left">
                all spent
              </span>
            )}
          </span>
          <span>
            Required level: <strong data-testid="required-level">{level}</strong>
          </span>
          <span className="text-[var(--text-dim)]" data-testid="tree-counts">
            {cls.trees.map((t, i) => (
              <span key={t.id}>
                {i > 0 && ' / '}
                {t.name} <strong className="text-[var(--text)]">{pointsInTree(build, t.id)}</strong>
              </span>
            ))}
          </span>
        </div>
      </div>

      <ClassSwitcher current={classId} />

      {/* One class-level control row, left to right: search, What's new, Reset
          - all three act on the whole class, all three are the same height, and
          What's new is a `.btn` like the other two rather than the odd chip out
          it was when it still lived in a tree panel header. The legend keeps the
          right edge. */}
      <div className="class-controls">
        <div className="control-field">
          <label className="control-label" htmlFor="talent-search">
            Search
          </label>
          <input
            id="talent-search"
            ref={search}
            className="search-input"
            type="search"
            value={query}
            placeholder="Talent name or text  (/)"
            autoComplete="off"
            data-testid="talent-search"
            aria-describedby="talent-search-count"
            onChange={(e) => onQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Escape' && onQuery('')}
          />
          <span id="talent-search-count" className="control-label" data-testid="search-count">
            {query.trim() ? `${results.length} match${results.length === 1 ? '' : 'es'}` : ''}
          </span>
        </div>
        <HighlightNewToggle classId={classId} />
        {/* A Reset used to destroy a 51-point build silently (usability 10). It
            is an ordinary commit now, so Ctrl+Z takes it back - and for the
            eight seconds after the click, so does the button itself. */}
        {resetUndoAt !== undefined ? (
          <button className="btn reset-undo" onClick={onUndoReset} data-testid="reset-undo">
            Build reset - Undo
          </button>
        ) : (
          <button className="btn" onClick={onReset} data-testid="reset-all" disabled={total === 0}>
            Reset
          </button>
        )}
        {/* The `?` badge is otherwise an unexplained glyph floating over the grid (usability 7). */}
        <p className="control-legend" data-testid="badge-legend">
          <span className="legend-flag" aria-hidden="true">
            ?
          </span>{' '}
          = uncertain reading, check it. The corner number is rank / max rank.
        </p>
      </div>

      {query.trim() !== '' && (
        <ul className="search-results w-full" data-testid="search-results">
          {results.slice(0, MAX_RESULTS).map(({ tree, talent }) => (
            <li key={talent.id}>
              <button
                type="button"
                className="search-result"
                data-testid={`search-result-${talent.id}`}
                onClick={() => onJump(tree.id, talent.id)}
              >
                <span className="text-[var(--text)]">{talent.name}</span>{' '}
                <span className="text-[var(--text-dim)]">
                  {tree.name}, row {talent.row + 1}
                </span>
              </button>
            </li>
          ))}
          {results.length === 0 && (
            <li className="text-xs text-[var(--text-dim)]">No talent matches "{query.trim()}".</li>
          )}
          {results.length > MAX_RESULTS && (
            <li className="text-xs text-[var(--text-dim)]">and {results.length - MAX_RESULTS} more</li>
          )}
        </ul>
      )}
    </header>
  )
}

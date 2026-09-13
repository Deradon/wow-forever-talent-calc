import { useEffect, useMemo, useRef, useState } from 'react'
import type { ClassData } from '../data/schema'
import { pointsInTree, requiredLevel, totalPoints, type Build } from '../rules'
import { matchesTalent } from './interaction'

interface Props {
  cls: ClassData
  build: Build
  link: string
  query: string
  onQuery: (q: string) => void
  onJump: (treeId: string, talentId: string) => void
  onReset: () => void
}

const MAX_RESULTS = 8

export function Header({ cls, build, link, query, onQuery, onJump, onReset }: Props) {
  const total = totalPoints(build)
  const left = cls.rules.maxPoints - total
  const level = requiredLevel(total, cls.rules)
  const [copied, setCopied] = useState<'idle' | 'copied' | 'failed'>('idle')
  const search = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (copied === 'idle') return
    const t = window.setTimeout(() => setCopied('idle'), 2000)
    return () => window.clearTimeout(t)
  }, [copied])

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

  async function copy() {
    try {
      await navigator.clipboard.writeText(link)
      setCopied('copied')
    } catch {
      setCopied('failed')
    }
  }

  return (
    <header className="panel mb-3 flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
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
      <div className="ml-auto flex items-center gap-2">
        <button className="btn" onClick={onReset} data-testid="reset-all" disabled={total === 0}>
          Reset
        </button>
        <button className="btn" onClick={copy} data-testid="copy-link" data-link={link}>
          {copied === 'copied' ? 'Copied!' : copied === 'failed' ? 'Copy failed' : 'Copy link'}
        </button>
      </div>
      {copied === 'failed' && (
        <input className="w-full bg-black/40 px-2 py-1 text-xs" readOnly value={link} onFocus={(e) => e.currentTarget.select()} />
      )}

      <div className="flex w-full flex-wrap items-start gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <label className="text-sm text-[var(--text-dim)]" htmlFor="talent-search">
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
          <span id="talent-search-count" className="text-xs text-[var(--text-dim)]" data-testid="search-count">
            {query.trim() ? `${results.length} match${results.length === 1 ? '' : 'es'}` : ''}
          </span>
        </div>
        {/* The `?` badge is otherwise an unexplained glyph floating over the grid (usability 7). */}
        <p className="ml-auto text-xs text-[var(--text-dim)]" data-testid="badge-legend">
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
          {results.length === 0 && <li className="text-xs text-[var(--text-dim)]">No talent matches "{query.trim()}".</li>}
          {results.length > MAX_RESULTS && (
            <li className="text-xs text-[var(--text-dim)]">and {results.length - MAX_RESULTS} more</li>
          )}
        </ul>
      )}
    </header>
  )
}

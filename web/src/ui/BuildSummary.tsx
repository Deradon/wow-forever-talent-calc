import { useEffect, useState } from 'react'
import type { ClassData } from '../data/schema'
import type { Build } from '../rules'
import { ImportDialog } from './ImportDialog'
import { summarizeBuild, summaryTitle, buildAsText } from './summaryText'

interface Props {
  cls: ClassData
  build: Build
  /** Full shareable URL of the current build. */
  link: string
  /** The bare `t=` string, which the import box accepts. */
  code: string
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  /** Scrolls to a talent and focuses its cell; shared with the search results. */
  onJump: (treeId: string, talentId: string) => void
  onImport: (classId: string, version: number | undefined, build: string) => void
}

type CopyState = 'idle' | 'copied' | 'failed'

/** Copy-to-clipboard with a 2 s confirmation, reused by the three buttons. */
function useCopy(): [CopyState, (text: string) => void] {
  const [state, setState] = useState<CopyState>('idle')
  useEffect(() => {
    if (state === 'idle') return
    const t = window.setTimeout(() => setState('idle'), 2000)
    return () => window.clearTimeout(t)
  }, [state])
  return [
    state,
    (text: string) => {
      // No clipboard at all over plain http, so the textarea fallback has to
      // survive a throw as well as a rejection.
      try {
        navigator.clipboard.writeText(text).then(
          () => setState('copied'),
          () => setState('failed'),
        )
      } catch {
        setState('failed')
      }
    },
  ]
}

function label(state: CopyState, idle: string): string {
  return state === 'copied' ? 'Copied!' : state === 'failed' ? 'Copy failed' : idle
}

/**
 * The right-hand column (brief "UI and UX improvements", idea 1): the spent
 * talents grouped by tree, the three exports, undo/redo and the import box.
 * It is also what finally fills the 360-400 px of empty container beside the
 * trees (idea 5), so the two were designed together.
 */
export function BuildSummary({ cls, build, link, code, canUndo, canRedo, onUndo, onRedo, onJump, onImport }: Props) {
  const summary = summarizeBuild(cls, build)
  const [linkCopy, copyLink] = useCopy()
  const [codeCopy, copyCode] = useCopy()
  const [textCopy, copyText] = useCopy()
  const [importing, setImporting] = useState(false)

  return (
    <aside className="panel summary-panel" aria-labelledby="build-summary-title" data-testid="build-summary">
      <div className="summary-head">
        <h2 className="serif text-base text-[var(--gold)]" id="build-summary-title" data-testid="summary-title">
          {summaryTitle(summary)}
        </h2>
        <p className="text-xs text-[var(--text-dim)]">
          {summary.spent} of {summary.maxPoints} spent
          {summary.left > 0 ? `, ${summary.left} left` : ''}
        </p>
      </div>

      {summary.spentTrees.length === 0 ? (
        <p className="summary-empty" data-testid="summary-empty">
          No points spent yet. Click a talent to start.
        </p>
      ) : (
        <ul className="summary-trees" data-testid="summary-trees">
          {summary.spentTrees.map((tree) => (
            <li key={tree.id}>
              <h3 className="summary-tree-name">
                {tree.name} <span className="text-[var(--gold)]">{tree.points}</span>
              </h3>
              <ul className="summary-talents">
                {tree.talents.map((talent) => (
                  <li key={talent.id}>
                    <button
                      type="button"
                      className="summary-talent"
                      data-testid={`summary-talent-${talent.id}`}
                      onClick={() => onJump(tree.id, talent.id)}
                      onMouseEnter={() => highlight(talent.id, true)}
                      onMouseLeave={() => highlight(talent.id, false)}
                      onFocus={() => highlight(talent.id, true)}
                      onBlur={() => highlight(talent.id, false)}
                    >
                      <span className="summary-talent-name">{talent.name}</span>
                      <span className="summary-talent-rank">
                        {talent.rank}/{talent.maxRank}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}

      <div className="summary-actions">
        <button className="btn" data-testid="copy-link" data-link={link} onClick={() => copyLink(link)}>
          {label(linkCopy, 'Copy link')}
        </button>
        <button className="btn" data-testid="copy-code" data-code={code} onClick={() => copyCode(code)} disabled={code === ''}>
          {label(codeCopy, 'Copy build code')}
        </button>
        <button
          className="btn"
          data-testid="copy-text"
          onClick={() => copyText(buildAsText(cls, build, link))}
        >
          {label(textCopy, 'Copy as text')}
        </button>
        <button className="btn" data-testid="open-import" aria-expanded={importing} onClick={() => setImporting((v) => !v)}>
          Import
        </button>
      </div>

      {(linkCopy === 'failed' || codeCopy === 'failed' || textCopy === 'failed') && (
        <textarea
          className="summary-fallback"
          readOnly
          rows={3}
          data-testid="copy-fallback"
          value={textCopy === 'failed' ? buildAsText(cls, build, link) : codeCopy === 'failed' ? code : link}
          onFocus={(e) => e.currentTarget.select()}
        />
      )}

      <div className="summary-history">
        <button className="btn text-xs" data-testid="undo" onClick={onUndo} disabled={!canUndo} title="Ctrl+Z">
          Undo
        </button>
        <button className="btn text-xs" data-testid="redo" onClick={onRedo} disabled={!canRedo} title="Ctrl+Shift+Z">
          Redo
        </button>
        <span className="text-xs text-[var(--text-dim)]">Ctrl+Z / Ctrl+Shift+Z</span>
      </div>

      {importing && <ImportDialog cls={cls} onClose={() => setImporting(false)} onImport={onImport} />}
    </aside>
  )
}

/**
 * Hovering a summary row outlines its cell. Done imperatively because the cell
 * lives inside TreePanel/TalentCell, which this round does not own; the class
 * React writes there is a constant, so toggling another one is safe.
 */
function highlight(talentId: string, on: boolean): void {
  const cell = document.querySelector<HTMLElement>(`[data-talent="${CSS.escape(talentId)}"]`)
  cell?.classList.toggle('cell-linked', on)
}

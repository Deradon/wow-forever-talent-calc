import { useEffect, useState } from 'react'
import type { ClassData } from '../data/schema'
import { levelLine, levelRange, standingAtLevel, type Build } from '../rules'
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
      {/* data-print-link: the print stylesheet prints the URL under the title,
          which is the only way a printed build stays shareable. */}
      <div className="summary-head" data-print-link={link}>
        <h2 className="serif text-base text-[var(--gold)]" id="build-summary-title" data-testid="summary-title">
          {summaryTitle(summary)}
        </h2>
        <p className="text-xs text-[var(--text-dim)]">
          {summary.spent} of {summary.maxPoints} spent
          {summary.left > 0 ? `, ${summary.left} left` : ''}
        </p>
      </div>

      {summary.spentTrees.length === 0 ? (
        /* The column is `align-self: stretch`, so on an empty build it used to
           be 700px of nothing next to the trees. It is also the one place a
           player is already looking, so the dead space pays for itself as the
           shortcut card - the gestures and keys that are otherwise discoverable
           only by reading the hint line under the trees. It disappears the
           moment the first point is spent. */
        <div className="summary-empty" data-testid="summary-empty">
          <p className="summary-empty-lead">
            No points spent yet. Click a talent to start - what you spend shows up here, tree by tree, with the link to
            share it.
          </p>
          <h3 className="summary-hints-title">Worth knowing</h3>
          <ul className="summary-hints" data-testid="summary-hints">
            <li>
              <kbd>Shift</kbd>+click fills a talent to its last rank in one go.
            </li>
            <li>
              <kbd>Ctrl</kbd>+click empties one; a right click takes back a single point.
            </li>
            <li>
              <kbd>/</kbd> jumps to the search box, <kbd>Esc</kbd> clears it.
            </li>
            <li>
              <kbd>d</kbd> opens, inside a tooltip, where its numbers were read from.
            </li>
            <li>
              <kbd>Ctrl</kbd>+<kbd>Z</kbd> undoes and <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> redoes - a Reset
              too.
            </li>
            <li>
              <strong className="text-[var(--text)]">Highlight changes</strong> in the header dims everything Classic
              already had.
            </li>
          </ul>
        </div>
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

      <LevelControl cls={cls} spent={summary.spent} />

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
        <button
          className="btn"
          data-testid="open-import"
          aria-haspopup="dialog"
          aria-expanded={importing}
          onClick={() => setImporting((v) => !v)}
        >
          Import
        </button>
        {/* The print stylesheet hides every control and lays the trees and this
            list out for one page (brief idea 15); the button is here because
            this column is where a player already goes to take a build away. */}
        <button className="btn" data-testid="print-build" onClick={() => window.print()}>
          Print
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
 * "Points at level X" (brief idea 10). The order in which a build was spent is
 * not tracked - the link carries a set of ranks, not a history - so the panel
 * refuses to point at individual talents and says the one thing it can prove:
 * how many of the spent points a character of that level actually has.
 *
 * The arithmetic is `standingAtLevel` in `src/rules/level.ts`, pure and unit
 * tested; everything here is the control around it.
 */
function LevelControl({ cls, spent }: { cls: ClassData; spent: number }) {
  const { min, max } = levelRange(cls.rules)
  const [level, setLevel] = useState(max)
  const standing = standingAtLevel(level, spent, cls.rules)

  return (
    <div className="summary-level" data-testid="level-control">
      <div className="summary-level-row">
        <label className="control-label" htmlFor="level-slider">
          Level
        </label>
        <input
          id="level-slider"
          className="level-slider"
          type="range"
          min={min}
          max={max}
          step={1}
          value={level}
          data-testid="level-slider"
          aria-describedby="level-line"
          onChange={(e) => setLevel(Number(e.target.value))}
        />
        <output className="summary-level-value" htmlFor="level-slider" data-testid="level-value">
          {level}
        </output>
      </div>
      <p className="summary-level-line" id="level-line" data-testid="level-line" aria-live="polite">
        {levelLine(standing)}
      </p>
    </div>
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

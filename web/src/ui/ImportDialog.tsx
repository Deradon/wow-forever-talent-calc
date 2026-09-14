import { useId, useState } from 'react'
import { loadClassicIndex } from '../data/classicIndex'
import { hasClass } from '../data/load'
import type { ClassData } from '../data/schema'
import { encode } from '../url/codec'
import { loadRegistry } from '../data/encoding'
import { importReport, mapClassicBuild, parseImport, splitWowheadCode, unplacedLine, type ImportOutcome } from '../url/import'
import { Modal } from './Modal'

/**
 * The list is one line per talent and one screen tall at 640 px, so it is
 * shown whole. "and N more" is emitted only from here, and only when this cap
 * actually bit - the round-two UX review found the old report truncating at six
 * and then printing the full list underneath anyway.
 */
const MAX_UNPLACED = 24

interface Props {
  cls: ClassData
  onClose: () => void
  onImport: (classId: string, version: number | undefined, build: string) => void
}

interface Preview {
  classId: string
  version?: number
  build: string
  report: string
  outcome?: ImportOutcome
}

/**
 * Import a build (brief "UI and UX improvements", idea 9): our link, our bare
 * build code, or a Wowhead Classic link. Nothing is applied until the player
 * has read the report, because a Wowhead build rarely survives intact - most of
 * the value is in being told exactly what did not fit.
 */
export function ImportDialog({ cls, onClose, onImport }: Props) {
  const [text, setText] = useState('')
  const [error, setError] = useState<string>()
  const [preview, setPreview] = useState<Preview>()
  const [busy, setBusy] = useState(false)
  const fieldId = useId()

  async function check() {
    setError(undefined)
    setPreview(undefined)
    const parsed = parseImport(text)

    if (parsed.kind === 'error') return setError(parsed.message)

    if (parsed.kind === 'code') {
      return setPreview({
        classId: cls.class,
        version: cls.dataVersion,
        build: parsed.build,
        report: `Read as a build code for ${cls.className}. Anything the rules cannot hold is dropped on arrival.`,
      })
    }

    if (parsed.kind === 'link') {
      if (!hasClass(parsed.classId)) return setError(`This site has no class "${parsed.classId}".`)
      return setPreview({
        classId: parsed.classId,
        version: parsed.version,
        build: parsed.build,
        report: parsed.build === '' ? `An empty ${parsed.classId} build.` : `A build link for ${parsed.classId}.`,
      })
    }

    // Wowhead: the Classic order is a separate chunk, fetched only here.
    if (!hasClass(parsed.classId)) return setError(`This site has no class "${parsed.classId}" yet.`)
    if (parsed.classId !== cls.class) {
      return setError(`That is a ${parsed.classId} build. Open ${parsed.classId} first, then import it.`)
    }
    setBusy(true)
    try {
      const index = await loadClassicIndex()
      const classic = index.classes[parsed.classId]
      if (!classic) return setError(`No Classic Era data for ${parsed.classId}.`)
      const split = splitWowheadCode(
        parsed.code,
        classic.trees.map((t) => t.talents.length),
      )
      if ('error' in split) return setError(split.error)
      const outcome = mapClassicBuild(cls, classic, split.segments)
      setPreview({
        classId: parsed.classId,
        version: cls.dataVersion,
        build: encode(cls, outcome.build, loadRegistry()),
        report: importReport(outcome),
        outcome,
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={`Import a build into ${cls.className}`} titleId="import-title" idBase="import" width="min(640px, 100%)" onClose={onClose}>
      <div className="import-box" data-testid="import-box">
        <label className="text-xs text-[var(--text-dim)]" htmlFor={fieldId}>
          Paste a link to this site, a build code like <code>30250-005-32</code>, or a Wowhead Classic talent link.
        </label>
        <textarea
          id={fieldId}
          className="import-input"
          rows={3}
          spellCheck={false}
          autoFocus
          value={text}
          data-testid="import-input"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void check()
          }}
        />
        <div className="import-actions">
          <button className="btn" data-testid="import-check" onClick={() => void check()} disabled={busy || text.trim() === ''}>
            {busy ? 'Reading...' : 'Check'}
          </button>
          <button
            className="btn"
            data-testid="import-apply"
            disabled={!preview}
            onClick={() => {
              if (!preview) return
              onImport(preview.classId, preview.version, preview.build)
              onClose()
            }}
          >
            Use this build
          </button>
        </div>
        {error && (
          <p className="import-error" role="alert" data-testid="import-error">
            {error}
          </p>
        )}
        {preview && (
          <div className="import-report" data-testid="import-report">
            <p>{preview.report}</p>
            {preview.outcome && preview.outcome.unplaced.length > 0 && (
              <ul className="import-unplaced" data-testid="import-unplaced">
                {preview.outcome.unplaced.slice(0, MAX_UNPLACED).map((u, i) => (
                  <li key={`${u.name}-${i}`}>{unplacedLine(u)}</li>
                ))}
                {preview.outcome.unplaced.length > MAX_UNPLACED && (
                  <li>and {preview.outcome.unplaced.length - MAX_UNPLACED} more</li>
                )}
              </ul>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}

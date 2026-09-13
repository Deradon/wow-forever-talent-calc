import { useId, useState } from 'react'
import { loadClassicIndex } from '../data/classicIndex'
import { hasClass } from '../data/load'
import type { ClassData } from '../data/schema'
import { encode } from '../url/codec'
import { loadRegistry } from '../data/encoding'
import { importReport, mapClassicBuild, parseImport, splitWowheadCode, type ImportOutcome } from '../url/import'

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
          if (e.key === 'Escape') onClose()
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
        <button className="btn" data-testid="import-close" onClick={onClose}>
          Close
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
              {preview.outcome.unplaced.map((u, i) => (
                <li key={`${u.name}-${i}`}>
                  {u.name} <span className="text-[var(--text-dim)]">{u.points}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

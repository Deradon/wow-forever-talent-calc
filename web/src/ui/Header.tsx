import { useEffect, useState } from 'react'
import type { ClassData } from '../data/schema'
import { pointsInTree, requiredLevel, totalPoints, type Build } from '../rules'

interface Props {
  cls: ClassData
  build: Build
  link: string
  onReset: () => void
}

export function Header({ cls, build, link, onReset }: Props) {
  const total = totalPoints(build)
  const left = cls.rules.maxPoints - total
  const level = requiredLevel(total, cls.rules)
  const [copied, setCopied] = useState<'idle' | 'copied' | 'failed'>('idle')

  useEffect(() => {
    if (copied === 'idle') return
    const t = window.setTimeout(() => setCopied('idle'), 2000)
    return () => window.clearTimeout(t)
  }, [copied])

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
          Points left: <strong data-testid="points-left">{left}</strong>
          <span className="text-[var(--text-dim)]"> / {cls.rules.maxPoints}</span>
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
    </header>
  )
}

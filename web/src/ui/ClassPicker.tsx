import { useEffect, useState } from 'react'
import { displayName, listClasses, loadClass, type ClassEntry } from '../data/load'
import type { ClassData } from '../data/schema'
import { needsReview } from './review'
import { SITE_TITLE, useTitle } from './title'

export const REPO_URL = 'https://github.com/Deradon/wow-forever-talent-calc'

type Loaded = { cls?: ClassData; error?: string }

/** Module-level: the registry is fixed at build time. */
const classes = listClasses()

/**
 * Landing page: one card per class file with its trees and talent counts.
 * Example classes are only present when VITE_INCLUDE_EXAMPLES=1 (dev, e2e).
 */
export function ClassPicker() {
  useTitle(SITE_TITLE)
  const [loaded, setLoaded] = useState<Record<string, Loaded>>({})

  useEffect(() => {
    let alive = true
    for (const c of classes) {
      loadClass(c.id)
        .then((cls) => alive && setLoaded((prev) => ({ ...prev, [c.id]: { cls } })))
        .catch((e: unknown) => alive && setLoaded((prev) => ({ ...prev, [c.id]: { error: e instanceof Error ? e.message : String(e) } })))
    }
    return () => {
      alive = false
    }
  }, [])

  return (
    <div>
      <div className="panel p-5">
        <h1 className="serif mb-2 text-lg text-[var(--gold)]">Choose a class</h1>
        <p className="mb-4 max-w-[70ch] text-sm text-[var(--text-dim)]">
          Talent data was read from the BlizzCon 2026 demo footage by a local vision model and is <strong>unreviewed</strong>:
          expect misread names, numbers and ranks. Only rank 1 was visible on stream; higher ranks are anticipated from
          Classic Era. Point rules (51 points, 5 per row, first point at level 10) are assumed. Data, pipeline and this app:{' '}
          <a href={REPO_URL} target="_blank" rel="noreferrer">
            github.com/Deradon/wow-forever-talent-calc
          </a>
          .
        </p>
        {classes.length === 0 ? (
          <p className="text-[var(--text-dim)]">
            No class data yet. Real classes appear here as they pass review; run the dev server to see the example class.
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="class-list">
            {classes.map((c) => (
              <ClassCard key={c.id} entry={c} loaded={loaded[c.id]} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function ClassCard({ entry, loaded }: { entry: ClassEntry; loaded?: Loaded }) {
  const cls = loaded?.cls
  const talents = cls?.trees.flatMap((t) => t.talents) ?? []
  const review = talents.filter((t) => needsReview(t)).length
  return (
    <li className="class-card">
      <a href={`#/${entry.id}`} className="block no-underline" data-testid={`class-${entry.id}`}>
        <div className="flex items-baseline gap-2">
          <span className="serif text-lg text-[var(--gold)]">{cls?.className ?? displayName(entry.id)}</span>
          {entry.origin !== 'talents' && <span className="text-xs text-[var(--text-dim)]">example</span>}
          {cls && (
            <span className="ml-auto text-xs text-[var(--text-dim)]" data-testid={`class-${entry.id}-talents`}>
              {talents.length} talents
            </span>
          )}
        </div>
        {loaded?.error ? (
          <div className="mt-1 text-xs text-[var(--red)]">{loaded.error}</div>
        ) : cls ? (
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm" data-testid={`class-${entry.id}-trees`}>
            {cls.trees.map((t) => (
              <li key={t.id}>
                <span className="text-[var(--text)]">{t.name}</span>{' '}
                <span className="text-[var(--text-dim)]">{t.talents.length}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="mt-2 text-sm text-[var(--text-dim)]">Loading...</div>
        )}
      </a>
      {cls && (
        <div className="mt-2 flex flex-wrap gap-x-3 text-xs text-[var(--text-dim)]">
          <span>{cls.dataSource === 'datamined' ? 'datamined' : `read from ${cls.dataSource}`}</span>
          <span>{talents.filter((t) => t.source.reviewed).length} reviewed</span>
          <a href={`#/review/${entry.id}`} data-testid={`review-${entry.id}`}>
            review queue{review > 0 ? ` (${review})` : ''}
          </a>
        </div>
      )}
    </li>
  )
}

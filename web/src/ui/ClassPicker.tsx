import { useState } from 'react'
import classesIndex from '../data/classes-index.json'
import { includeExamples } from '../data/load'
import { classHash } from '../url/route'
import { ClassIcon } from './ClassIcon'
import { continueLabel, forgetLastBuild, readLastBuild } from './storage'
import { SITE_TITLE, useTitle } from './title'

export const REPO_URL = 'https://github.com/Deradon/wow-forever-talent-calc'

interface IndexEntry {
  id: string
  origin: string
  className: string
  dataSource: string
  maxPoints: number
  talents: number
  reviewed: number
  needsReview: number
  trees: { id: string; name: string; talents: number }[]
}

/**
 * Module-level: the index is generated at build time by
 * scripts/gen-data-index.mjs, so the landing page prints class names, trees and
 * counts from ~5 kB of JSON instead of importing all nine class chunks
 * (344 kB raw / 58 kB gzip and nine extra requests - performance review P-1).
 * Example classes are only present when VITE_INCLUDE_EXAMPLES=1 (dev, e2e).
 */
const classes: IndexEntry[] = (classesIndex as IndexEntry[]).filter((c) => includeExamples || c.origin === 'talents')

/** Landing page: one card per class file with its trees and talent counts. */
export function ClassPicker() {
  useTitle(SITE_TITLE)
  const [last, setLast] = useState(() => readLastBuild())

  return (
    <div>
      {last && (
        <div className="continue-card" data-testid="continue-card">
          <a className="serif text-base" href={classHash(last.classId, last.v, last.t)} data-testid="continue-link">
            {continueLabel(last)}
          </a>
          <span className="text-xs text-[var(--text-dim)]">your last build on this browser, not shared anywhere</span>
          <button
            type="button"
            className="continue-forget ml-auto"
            data-testid="continue-forget"
            onClick={() => {
              forgetLastBuild()
              setLast(undefined)
            }}
          >
            forget
          </button>
        </div>
      )}
      <div className="panel p-5">
        <h1 className="serif mb-2 text-lg text-[var(--gold)]">Choose a class</h1>
        {/* The one place the caveat is stated: tooltips and class pages must not repeat it. */}
        <p className="mb-2 text-sm text-[var(--text-dim)]">
          Read from BlizzCon 2026 demo footage by a local vision model and <strong>unreviewed</strong> - expect wrong
          names and numbers. Only rank 1 was on screen; higher ranks and the point rules are estimated from Classic Era.
        </p>
        <p className="mb-4 text-sm text-[var(--text-dim)]">
          <a href={REPO_URL} target="_blank" rel="noreferrer">
            github.com/Deradon/wow-forever-talent-calc
          </a>
        </p>
        {classes.length === 0 ? (
          <p className="text-[var(--text-dim)]">
            No class data yet. Real classes appear here as they pass review; run the dev server to see the example
            class.
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="class-list">
            {classes.map((c) => (
              <ClassCard key={c.id} entry={c} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function ClassCard({ entry }: { entry: IndexEntry }) {
  // Provenance and the review queue are deliberately not shown here: the caveat
  // above states the data source once, and `#/review/<class>` stays reachable by URL.
  return (
    <li className="class-card">
      <a href={`#/${entry.id}`} className="block no-underline" data-testid={`class-${entry.id}`}>
        <div className="flex items-center gap-3">
          <ClassIcon classId={entry.id} className={entry.className} size={40} />
          <span className="serif text-lg text-[var(--gold)]">{entry.className}</span>
          {entry.origin !== 'talents' && <span className="text-xs text-[var(--text-dim)]">example</span>}
        </div>
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm" data-testid={`class-${entry.id}-trees`}>
          {entry.trees.map((t) => (
            <li key={t.id}>
              <span className="text-[var(--text)]">{t.name}</span>{' '}
              <span className="text-[var(--text-dim)]">{t.talents}</span>
            </li>
          ))}
        </ul>
      </a>
    </li>
  )
}

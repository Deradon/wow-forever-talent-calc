import { useEffect, useMemo, useState } from 'react'
import classesIndex from '../data/classes-index.json'
import { hasClass, includeExamples, loadClass } from '../data/load'
import type { ClassData } from '../data/schema'
import { changesHash, classHash } from '../url/route'
import {
  classChanges,
  classCounts,
  comparedClasses,
  hasClassicDiff,
  loadClassicTexts,
  removedTalents,
  type ClassicText,
} from './classicDiff'
import { changesModel, diffLines, filterModel, type ChangeRow } from './changesModel'
import { DiffLine } from './DiffLine'
import { ClassSwitcher } from './ClassSwitcher'
import { ClassIcon } from './ClassIcon'
import { SITE_TITLE, useTitle } from './title'
import './changes.css'

/**
 * `#/changes` and `#/changes/<class>` - the one question a Classic+ calculator
 * exists to answer (brief `docs/briefs/ui-improvements.md`, idea 13).
 *
 * `#/changes` is the overview: the nine classes with their per-status counts.
 * `#/changes/<class>` is the list, six sections in the generator's precedence
 * order, every talent a deep link to `#/<class>?sel=<id>` which opens that
 * talent's tooltip pinned on the class page.
 *
 * The page is lazily routed in `App.tsx` and the word diffs come from
 * `classic-text.json`, which is fetched on demand exactly as the tooltip card
 * fetches it - so nobody who never opens `#/changes` pays for either.
 */
export function ChangesPage({ classId }: { classId?: string }) {
  return classId ? <OneClass classId={classId} /> : <Overview />
}

interface IndexEntry {
  id: string
  origin: string
  className: string
}

const CLASSES: IndexEntry[] = (classesIndex as IndexEntry[]).filter((c) => includeExamples || c.origin === 'talents')

const OVERVIEW_COLUMNS: { key: string; label: string }[] = [
  { key: 'new', label: 'New' },
  { key: 'moved', label: 'Moved' },
  { key: 'rank-changed', label: 'Ranks' },
  { key: 'text-changed', label: 'Reworked' },
  { key: 'values-changed', label: 'Values' },
  { key: 'removed', label: 'Gone' },
]

function Overview() {
  useTitle(`What changed vs Classic - ${SITE_TITLE}`)
  const compared = new Set(comparedClasses())
  const rows = CLASSES.filter((c) => compared.has(c.id))
  const totals = OVERVIEW_COLUMNS.map(({ key }) => rows.reduce((n, c) => n + (classCounts(c.id)[key] ?? 0), 0))

  return (
    <div className="changes-page" data-testid="changes-overview">
      <ChangesHeader />
      <p className="changes-lead">
        Every talent in the game compared against Classic Era by name within the class. Pick a class for the list, or
        read the counts here first.
      </p>
      <ClassSwitcher current="" hrefFor={(id) => changesHash(id)} hintFor={(name) => `What changed for ${name}`} />
      <table className="changes-table" data-testid="changes-table">
        <thead>
          <tr>
            <th scope="col">Class</th>
            {OVERVIEW_COLUMNS.map((c) => (
              <th scope="col" key={c.key}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => {
            const counts = classCounts(c.id)
            return (
              <tr key={c.id} data-testid={`changes-row-${c.id}`}>
                <th scope="row">
                  <a href={changesHash(c.id)} data-testid={`changes-link-${c.id}`}>
                    <ClassIcon classId={c.id} className={c.className} size={20} />
                    {c.className}
                  </a>
                </th>
                {OVERVIEW_COLUMNS.map((col) => (
                  <td key={col.key}>{counts[col.key] ?? 0}</td>
                ))}
              </tr>
            )
          })}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">All classes</th>
            {totals.map((n, i) => (
              <td key={OVERVIEW_COLUMNS[i]!.key}>{n}</td>
            ))}
          </tr>
        </tfoot>
      </table>
      <p className="changes-note">
        A move is a different tree or a different row; a reshuffled column inside the same row is not one. "Gone" counts
        Classic Era talents with no counterpart of that name in Forever.
      </p>
    </div>
  )
}

function OneClass({ classId }: { classId: string }) {
  const [cls, setCls] = useState<ClassData>()
  const [error, setError] = useState<string>()
  const [texts, setTexts] = useState<Record<string, ClassicText>>()
  const [query, setQuery] = useState('')

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

  // The Classic wording is the bulky half of the diff and lives in its own
  // chunk; the page renders without it and fills the sentences in when it lands.
  useEffect(() => {
    let alive = true
    void loadClassicTexts(classId).then((t) => alive && setTexts(t))
    return () => {
      alive = false
    }
  }, [classId])

  const model = useMemo(
    () =>
      cls
        ? changesModel(cls, classChanges(classId), removedTalents(classId), (id) => Boolean(texts?.[id]))
        : undefined,
    [cls, classId, texts],
  )
  const shown = useMemo(() => (model ? filterModel(model, query) : undefined), [model, query])

  useTitle(cls ? `${cls.className} vs Classic - ${SITE_TITLE}` : undefined)

  if (error) {
    return (
      <div className="panel p-4">
        <p className="text-[var(--red)]">{error}</p>
        <a href={changesHash()}>All classes</a>
      </div>
    )
  }
  if (!cls || !model || !shown) return <div className="panel p-4 text-[var(--text-dim)]">Loading {classId}...</div>

  if (!hasClassicDiff(classId)) {
    return (
      <div className="changes-page">
        <ChangesHeader classId={classId} />
        <ClassSwitcher current={classId} hrefFor={(id) => changesHash(id)} hintFor={(n) => `What changed for ${n}`} />
        <p className="changes-lead" data-testid="changes-nodiff">
          {cls.className} has no Classic Era counterpart to compare against, so nothing here is a change.
        </p>
      </div>
    )
  }

  return (
    <div className="changes-page" data-testid={`changes-${classId}`}>
      <ChangesHeader classId={classId} />
      <ClassSwitcher current={classId} hrefFor={(id) => changesHash(id)} hintFor={(n) => `What changed for ${n}`} />
      <div className="changes-bar">
        <h2 className="serif text-lg text-[var(--gold)]" data-testid="changes-class-title">
          {cls.className} vs Classic Era
        </h2>
        <span className="changes-total" data-testid="changes-total">
          {model.total} {model.total === 1 ? 'entry' : 'entries'}
        </span>
        <a className="changes-open" href={`#/${classId}`}>
          Open the {cls.className} calculator
        </a>
        <div className="control-field changes-filter">
          <label className="control-label" htmlFor="changes-filter">
            Filter
          </label>
          <input
            id="changes-filter"
            className="search-input"
            type="search"
            value={query}
            placeholder="Talent name or wording"
            autoComplete="off"
            data-testid="changes-filter"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Escape' && setQuery('')}
          />
        </div>
      </div>

      <nav className="changes-jump" aria-label="Sections">
        {shown.sections.map((s) => (
          <a key={s.id} href={`#/changes/${classId}`} onClick={jumpTo(`changes-section-${s.id}`)} data-testid={`changes-jump-${s.id}`}>
            {s.title} <strong>{s.rows.length}</strong>
          </a>
        ))}
      </nav>

      {shown.total === 0 && (
        <p className="changes-empty" data-testid="changes-no-match">
          Nothing matches "{query.trim()}".
        </p>
      )}

      {shown.sections.map((section) => (
        <section
          key={section.id}
          className="panel changes-section"
          id={`changes-section-${section.id}`}
          data-testid={`changes-section-${section.id}`}
          hidden={section.rows.length === 0}
        >
          <h3 className="serif text-base text-[var(--gold)]">
            {section.title}{' '}
            <span className="changes-count" data-testid={`changes-count-${section.id}`}>
              {section.rows.length}
            </span>
          </h3>
          <p className="changes-blurb">{section.blurb}</p>
          <ul className="changes-list">
            {section.rows.map((row) => (
              <Row key={`${section.id}-${row.id}`} classId={classId} row={row} text={texts?.[row.id]} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

/** In-page anchors would land in the hash, which is the router. Scroll instead. */
function jumpTo(elementId: string) {
  return (e: React.MouseEvent) => {
    e.preventDefault()
    document.getElementById(elementId)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }
}

function Row({ classId, row, text }: { classId: string; row: ChangeRow; text: ClassicText | undefined }) {
  return (
    <li className="changes-item" data-testid={`changes-item-${row.id}`}>
      <div className="changes-item-head">
        {row.gone ? (
          <span className="changes-name changes-name-gone" data-testid={`changes-gone-${row.id}`}>
            {row.name}
          </span>
        ) : (
          /* The deep link: the class page opens this talent's tooltip pinned. */
          <a
            className="changes-name"
            href={classHash(classId, 0, '', { sel: row.id })}
            data-testid={`changes-deeplink-${row.id}`}
          >
            {row.name}
          </a>
        )}
        <span className="changes-rank">{row.maxRank ? `${row.maxRank} max` : ''}</span>
      </div>
      {row.detail && <p className="changes-detail">{row.detail}</p>}
      {text && <WordDiff text={text} talentId={row.id} />}
    </li>
  )
}

/**
 * The two sentences, each on its own labelled line with its own highlights -
 * exactly as the tooltip's nested card draws them, so a diff looks the same
 * wherever the app shows one.
 */
function WordDiff({ text, talentId }: { text: ClassicText; talentId: string }) {
  return (
    <div className="changes-diff" data-testid={`changes-diff-${talentId}`}>
      <DiffLine label="Classic Era" runs={diffLines(text).classic} side="classic" talentId={talentId} />
      <DiffLine label="Forever" runs={diffLines(text).forever} side="forever" talentId={talentId} />
    </div>
  )
}

function ChangesHeader({ classId }: { classId?: string }) {
  return (
    <div className="changes-head">
      <h1 className="serif text-xl text-[var(--gold)]">What changed against Classic Era</h1>
      {classId && (
        <a href={changesHash()} className="changes-all">
          All classes
        </a>
      )}
    </div>
  )
}

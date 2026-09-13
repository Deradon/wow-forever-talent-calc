import { useEffect, useMemo, useState } from 'react'
import { loadRegistry } from '../data/encoding'
import { hasClass, loadClass } from '../data/load'
import type { ClassData } from '../data/schema'
import { add, pointsInPage, pointsInTree, remove, resetAll, resetTree, type Build } from '../rules'
import { decode, encode, type Notice } from '../url/codec'
import { classHash } from '../url/route'
import { Header } from './Header'
import { Notices } from './Notice'
import { PageTabs } from './PageTabs'
import { SITE_TITLE, useTitle } from './title'
import { TreePanel } from './TreePanel'

interface Props {
  classId: string
  version?: number
  buildString?: string
}

/**
 * The build in the URL is the source of truth on arrival (decoded, sanitized,
 * notices shown). User edits live in state and are written back to the hash
 * with replaceState, which does not fire hashchange; an external hash change
 * (back button, pasted link) re-decodes.
 */
export function ClassPage({ classId, version, buildString }: Props) {
  const [cls, setCls] = useState<ClassData>()
  const [error, setError] = useState<string>()
  const registry = loadRegistry()

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

  const routeKey = `${classId}|${version ?? ''}|${buildString ?? ''}`
  const decoded = useMemo(() => {
    if (!cls) return undefined
    return decode(cls, buildString ?? '', version ?? cls.dataVersion, registry)
  }, [cls, buildString, version, registry])

  const [edit, setEdit] = useState<{ key: string; build: Build }>()
  const [dismissed, setDismissed] = useState<string>()
  const [page, setPage] = useState<string>()

  const liveBuild = cls && decoded ? (edit && edit.key === routeKey ? edit.build : decoded.build) : undefined
  useTitle(
    cls && liveBuild ? `${cls.className} ${cls.trees.map((t) => pointsInTree(liveBuild, t.id)).join('/')} - ${SITE_TITLE}` : undefined,
  )

  if (error) {
    return (
      <div className="panel p-4">
        <p className="text-[var(--red)]">{error}</p>
        <a href="#/">Pick a class</a>
      </div>
    )
  }
  if (!cls || !decoded) return <div className="panel p-4 text-[var(--text-dim)]">Loading {classId}...</div>

  const build = liveBuild!
  const notices: Notice[] = dismissed === routeKey || (edit && edit.key === routeKey) ? [] : decoded.notices
  const encoded = encode(cls, build, registry)
  const hash = classHash(classId, cls.dataVersion, encoded)
  const link = `${window.location.origin}${window.location.pathname}${hash}`

  function commit(next: Build) {
    if (next === build) return
    setEdit({ key: routeKey, build: next })
    const nextHash = classHash(classId, cls!.dataVersion, encode(cls!, next, registry))
    if (window.location.hash !== nextHash) window.history.replaceState(null, '', nextHash)
  }

  const activePage = page && cls.pages.some((p) => p.id === page) ? page : cls.pages[0]!.id
  const trees = cls.trees.filter((t) => t.page === activePage).sort((a, b) => a.order - b.order)
  const pageCounts = Object.fromEntries(cls.pages.map((p) => [p.id, pointsInPage(cls, build, p.id)]))

  return (
    <div>
      <Header cls={cls} build={build} link={link} onReset={() => commit(resetAll())} />
      <Notices notices={notices} onDismiss={() => setDismissed(routeKey)} />
      <PageTabs pages={cls.pages} active={activePage} counts={pageCounts} budgets={cls.rules.pointsPerPage} onSelect={setPage} />
      <div className="flex flex-wrap items-start gap-4">
        {trees.map((tree) => (
          <TreePanel
            key={tree.id}
            cls={cls}
            tree={tree}
            build={build}
            onAdd={(treeId, talentId) => commit(add(cls, build, treeId, talentId))}
            onRemove={(treeId, talentId) => commit(remove(cls, build, treeId, talentId))}
            onReset={(treeId) => commit(resetTree(build, treeId))}
          />
        ))}
      </div>
      <div className="mt-3 text-xs text-[var(--text-dim)]">
        Left click adds a point, right click removes one.
        {cls.dataSource !== 'datamined' && (
          <>
            {' '}
            Data was read from stream footage ({cls.dataSource}); talent rules are {cls.rules.rulesSource}. Hover a talent for its
            provenance.
          </>
        )}
        {cls.notes?.map((n, i) => (
          <div key={i}>{n}</div>
        ))}
      </div>
    </div>
  )
}

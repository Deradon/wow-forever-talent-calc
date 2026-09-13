import { useEffect, useMemo, useState } from 'react'
import { loadRegistry } from '../data/encoding'
import { hasClass, loadClass } from '../data/load'
import type { ClassData } from '../data/schema'
import {
  add,
  canAdd,
  canRemove,
  pointsInPage,
  pointsInTree,
  remove,
  requiredLevel,
  resetAll,
  resetTree,
  totalPoints,
  type Build,
  type Verdict,
} from '../rules'
import { decode, encode, type Notice } from '../url/codec'
import { classHash } from '../url/route'
import { Header } from './Header'
import { Notices } from './Notice'
import { PageTabs } from './PageTabs'
import { blockedMessage } from './interaction'
import { SITE_TITLE, useTitle } from './title'
import { TreePanel } from './TreePanel'

interface Props {
  classId: string
  version?: number
  buildString?: string
}

interface Blocked {
  treeId: string
  talentId: string
  message: string
  at: number
}

/**
 * True on devices without a real hover (phones, tablets). Decides whether a tap
 * spends a point straight away or opens the tooltip with +/- controls, which is
 * the only way to read a talent or refund one there (a11y review A-2/A-3).
 */
function useCoarsePointer(): boolean {
  const [coarse, setCoarse] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(hover: none), (pointer: coarse)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(hover: none), (pointer: coarse)')
    const onChange = () => setCoarse(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return coarse
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
  const coarse = useCoarsePointer()

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
  const [query, setQuery] = useState('')
  const [blocked, setBlocked] = useState<Blocked>()

  // A refused click is otherwise completely silent (usability 4). The message
  // clears itself so it never becomes permanent page furniture.
  useEffect(() => {
    if (!blocked) return
    const t = window.setTimeout(() => setBlocked(undefined), 4000)
    return () => window.clearTimeout(t)
  }, [blocked])

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
  const spent = totalPoints(build)
  const pointsLeft = cls.rules.maxPoints - spent

  function commit(next: Build) {
    if (next === build) return
    setEdit({ key: routeKey, build: next })
    setBlocked(undefined)
    const nextHash = classHash(classId, cls!.dataVersion, encode(cls!, next, registry))
    if (window.location.hash !== nextHash) window.history.replaceState(null, '', nextHash)
  }

  function refuse(treeId: string, talentId: string, verdict: Verdict, action: 'add' | 'remove') {
    const tree = cls!.trees.find((t) => t.id === treeId)
    const talent = tree?.talents.find((t) => t.id === talentId)
    setBlocked({ treeId, talentId, at: Date.now(), message: blockedMessage(talent?.name ?? talentId, verdict, action) })
  }

  function handleAdd(treeId: string, talentId: string) {
    const verdict = canAdd(cls!, build, treeId, talentId)
    if (!verdict.ok) return refuse(treeId, talentId, verdict, 'add')
    commit(add(cls!, build, treeId, talentId))
  }

  function handleRemove(treeId: string, talentId: string) {
    const verdict = canRemove(cls!, build, treeId, talentId)
    if (!verdict.ok) return refuse(treeId, talentId, verdict, 'remove')
    commit(remove(cls!, build, treeId, talentId))
  }

  /** Search result clicked: switch to the talent's page, then focus its cell. */
  function jumpTo(treeId: string, talentId: string) {
    const tree = cls!.trees.find((t) => t.id === treeId)
    if (tree && tree.page !== activePage) setPage(tree.page)
    window.setTimeout(() => {
      const el = document.querySelector<HTMLElement>(`[data-talent="${talentId}"]`)
      el?.scrollIntoView({ block: 'center', behavior: 'auto' })
      el?.focus()
    }, 0)
  }

  const activePage = page && cls.pages.some((p) => p.id === page) ? page : cls.pages[0]!.id
  const trees = cls.trees.filter((t) => t.page === activePage).sort((a, b) => a.order - b.order)
  const pageCounts = Object.fromEntries(cls.pages.map((p) => [p.id, pointsInPage(cls, build, p.id)]))

  return (
    <div>
      <Header
        cls={cls}
        build={build}
        link={link}
        query={query}
        onQuery={setQuery}
        onJump={jumpTo}
        onReset={() => commit(resetAll())}
      />
      {/* Polite, so a screen reader hears the effect of every point without
          interrupting; the blocked line is assertive-by-role="alert". */}
      <p className="sr-only" aria-live="polite" data-testid="live-status">
        {cls.trees.map((t) => `${t.name} ${pointsInTree(build, t.id)}`).join(', ')}. {pointsLeft} points left. Required
        level {requiredLevel(spent, cls.rules)}.
      </p>
      {blocked && (
        <p className="blocked-message" role="alert" data-testid="blocked-message">
          {blocked.message}
        </p>
      )}
      <Notices notices={notices} onDismiss={() => setDismissed(routeKey)} />
      <PageTabs pages={cls.pages} active={activePage} counts={pageCounts} budgets={cls.rules.pointsPerPage} onSelect={setPage} />
      <div className="flex flex-wrap items-start gap-4">
        {trees.map((tree) => (
          <TreePanel
            key={tree.id}
            cls={cls}
            tree={tree}
            build={build}
            pointsLeft={pointsLeft}
            coarse={coarse}
            query={query}
            blocked={blocked?.treeId === tree.id ? { talentId: blocked.talentId, at: blocked.at } : undefined}
            onAdd={handleAdd}
            onRemove={handleRemove}
            onReset={(treeId) => commit(resetTree(build, treeId))}
          />
        ))}
      </div>
      <div className="mt-3 text-xs text-[var(--text-dim)]">
        {coarse
          ? 'Tap a talent for its tooltip, then + to add a point and - to remove one.'
          : 'Left click adds a point, right click removes one. With a talent focused: Enter or Space adds, Backspace removes, arrow keys move. Move the pointer into a tooltip to keep it open, or press d to show where its numbers come from.'}
        {cls.notes?.map((n, i) => (
          <div key={i}>{n}</div>
        ))}
      </div>
    </div>
  )
}

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
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
import { BuildSummary } from './BuildSummary'
import { Header } from './Header'
import { canRedo, canUndo, editReducer, initEdit, isTextEntry, undoShortcut } from './history'
import { Notices } from './Notice'
import { PageTabs } from './PageTabs'
import { blockedMessage } from './interaction'
import { readLastBuild, writeLastBuild, continueLabel, type LastBuild } from './storage'

import { SITE_TITLE, useTitle } from './title'
import { TreePanel } from './TreePanel'

interface Props {
  classId: string
  version?: number
  buildString?: string
  /** `sel=<talentId>`: open that talent's tooltip, pinned (brief idea 12). */
  sel?: string
  /** `embed=1`: trees, a points line and a link back, nothing else (idea 16). */
  embed?: boolean
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
 * notices shown). User edits live in an undo/redo stack keyed by the route and
 * are written back to the hash; an external hash change (back button, pasted
 * link) re-decodes and starts a fresh stack.
 */
export function ClassPage({ classId, version, buildString, sel: selParam, embed }: Props) {
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

  const [edit, dispatch] = useReducer(editReducer, initEdit('', {} as Build))
  const [dismissed, setDismissed] = useState<string>()
  const [page, setPage] = useState<string>()
  const [query, setQuery] = useState('')
  const [blocked, setBlocked] = useState<Blocked>()
  const [resetUndo, setResetUndo] = useState<number>()
  /** The pinned talent. Starts at `sel=` and is dropped when its card closes. */
  const [sel, setSel] = useState(selParam)
  /** The route for which one browser-history entry was already pushed. */
  const pushedFor = useRef<string | undefined>(undefined)

  useEffect(() => setSel(selParam), [selParam])

  const editing = edit.key === routeKey
  const build = editing ? edit.present : decoded?.build

  // A refused click is otherwise completely silent (usability 4). The message
  // clears itself so it never becomes permanent page furniture.
  useEffect(() => {
    if (!blocked) return
    const t = window.setTimeout(() => setBlocked(undefined), 4000)
    return () => window.clearTimeout(t)
  }, [blocked])

  // "Build reset - Undo", for as long as an accidental Reset stays recoverable
  // by looking at the screen rather than by knowing Ctrl+Z (idea 7).
  useEffect(() => {
    if (resetUndo === undefined) return
    const t = window.setTimeout(() => setResetUndo(undefined), 8000)
    return () => window.clearTimeout(t)
  }, [resetUndo])

  /**
   * The hash follows the stack. `replaceState` keeps a shared link live without
   * an entry per click; the first edit of a session pushes exactly one entry, so
   * a single Back leaves the page predictably instead of unwinding 30 clicks.
   */
  useEffect(() => {
    if (!cls || !editing) return
    const nextHash = classHash(classId, cls.dataVersion, encode(cls, edit.present, registry), { sel, embed })
    if (window.location.hash === nextHash) return
    if (pushedFor.current === routeKey) window.history.replaceState(null, '', nextHash)
    else {
      pushedFor.current = routeKey
      window.history.pushState(null, '', nextHash)
    }
  }, [cls, editing, edit.present, classId, registry, routeKey, sel, embed])

  // Remembering the last build is best effort and never authoritative: it is
  // only ever read where the hash carries no build (idea 8).
  useEffect(() => {
    if (!cls || !build) return
    const t = encode(cls, build, registry)
    // An empty build is not worth remembering, and writing one would wipe the
    // entry the moment a player opens a bare `#/<class>` - which is exactly
    // where the card is supposed to appear.
    if (t === '') return
    writeLastBuild({
      classId,
      v: cls.dataVersion,
      t,
      className: cls.className,
      spread: cls.trees.map((tree) => pointsInTree(build, tree.id)).join('/'),
    })
  }, [cls, build, classId, registry])

  /**
   * Back and Forward drop the stack. `replaceState` means the route props can
   * be identical before and after a Back (`#/paladin` -> edits -> `#/paladin`),
   * so the route key alone cannot notice the navigation - without this, Back
   * left the edited build on screen under the pristine URL.
   */
  useEffect(() => {
    function onPop() {
      pushedFor.current = undefined
      dispatch({ type: 'route', key: '', build: {} })
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const undo = useCallback(() => dispatch({ type: 'undo' }), [])
  const redo = useCallback(() => dispatch({ type: 'redo' }), [])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (isTextEntry(e.target as HTMLElement | null)) return
      const action = undoShortcut(e)
      if (!action) return
      e.preventDefault()
      dispatch({ type: action })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  /**
   * A `sel=` link (a `#/changes` row, or a link a player sent a friend) has to
   * land on the talent even when it sits on another page of the class. The page
   * switch happens here; the cell opens and focuses its own tooltip once it
   * renders with `selected` (TalentCell), which is the only place that knows
   * the claim/sticky mechanics.
   */
  useEffect(() => {
    if (!cls || !sel) return
    const tree = cls.trees.find((t) => t.talents.some((x) => x.id === sel))
    if (!tree) return
    setPage(tree.page)
    const timer = window.setTimeout(() => {
      document
        .querySelector<HTMLElement>(`[data-talent="${CSS.escape(sel)}"]`)
        ?.scrollIntoView({ block: 'center', behavior: 'auto' })
    }, 0)
    return () => window.clearTimeout(timer)
  }, [cls, sel])

  const last = useMemo(() => (buildString ? undefined : readLastBuild()), [buildString])

  useTitle(
    cls && build ? `${cls.className} ${cls.trees.map((t) => pointsInTree(build, t.id)).join('/')} - ${SITE_TITLE}` : undefined,
  )

  if (error) {
    return (
      <div className="panel p-4">
        <p className="text-[var(--red)]">{error}</p>
        <a href="#/">Pick a class</a>
      </div>
    )
  }
  if (!cls || !decoded || !build) return <div className="panel p-4 text-[var(--text-dim)]">Loading {classId}...</div>

  const notices: Notice[] = dismissed === routeKey || editing ? [] : decoded.notices
  const encoded = encode(cls, build, registry)
  const hash = classHash(classId, cls.dataVersion, encoded)
  const link = `${window.location.origin}${window.location.pathname}${hash}`
  const spent = totalPoints(build)
  const pointsLeft = cls.rules.maxPoints - spent

  function commit(next: Build) {
    if (next === build) return
    // The first edit after arriving has to seed the stack with the build the
    // URL decoded to, or the first Ctrl+Z would have nothing to go back to.
    if (!editing) dispatch({ type: 'route', key: routeKey, build: build! })
    dispatch({ type: 'commit', key: routeKey, build: next })
    setBlocked(undefined)
  }

  function refuse(treeId: string, talentId: string, verdict: Verdict, action: 'add' | 'remove') {
    const tree = cls!.trees.find((t) => t.id === treeId)
    const talent = tree?.talents.find((t) => t.id === talentId)
    setBlocked({ treeId, talentId, at: Date.now(), message: blockedMessage(talent?.name ?? talentId, verdict, action) })
  }

  function handleAdd(treeId: string, talentId: string) {
    const verdict = canAdd(cls!, build!, treeId, talentId)
    if (!verdict.ok) return refuse(treeId, talentId, verdict, 'add')
    commit(add(cls!, build!, treeId, talentId))
  }

  function handleRemove(treeId: string, talentId: string) {
    const verdict = canRemove(cls!, build!, treeId, talentId)
    if (!verdict.ok) return refuse(treeId, talentId, verdict, 'remove')
    commit(remove(cls!, build!, treeId, talentId))
  }

  /**
   * The pinned card was dismissed. `sel` is view state, so it leaves the hash
   * the moment it stops being true - and it is removed from the hash as it
   * stands rather than rebuilt from the build, so a link whose `t=` needed
   * sanitizing is not silently rewritten by closing a tooltip.
   */
  function deselect() {
    setSel(undefined)
    const h = window.location.hash
    const q = h.indexOf('?')
    if (q === -1) return
    const params = new URLSearchParams(h.slice(q + 1))
    if (!params.has('sel')) return
    params.delete('sel')
    const qs = params.toString()
    window.history.replaceState(null, '', `${h.slice(0, q)}${qs ? `?${qs}` : ''}`)
  }

  /** Search result or summary row clicked: switch page if needed, focus the cell. */
  function jumpTo(treeId: string, talentId: string) {
    const tree = cls!.trees.find((t) => t.id === treeId)
    if (tree && tree.page !== activePage) setPage(tree.page)
    window.setTimeout(() => {
      const el = document.querySelector<HTMLElement>(`[data-talent="${talentId}"]`)
      el?.scrollIntoView({ block: 'center', behavior: 'auto' })
      el?.focus()
    }, 0)
  }

  /** A deliberate navigation, so it gets its own history entry. */
  function applyImport(targetClass: string, targetVersion: number | undefined, targetBuild: string) {
    const next = classHash(targetClass, targetVersion ?? cls!.dataVersion, targetBuild)
    if (window.location.hash === next) return
    window.location.hash = next
  }

  const activePage = page && cls.pages.some((p) => p.id === page) ? page : cls.pages[0]!.id
  const trees = cls.trees.filter((t) => t.page === activePage).sort((a, b) => a.order - b.order)
  const pageCounts = Object.fromEntries(cls.pages.map((p) => [p.id, pointsInPage(cls, build, p.id)]))

  return (
    <div data-embed={embed ? 'true' : undefined}>
      {!embed && (
      <Header
        cls={cls}
        classId={classId}
        build={build}
        query={query}
        onQuery={setQuery}
        onJump={jumpTo}
        resetUndoAt={resetUndo}
        onUndoReset={() => {
          setResetUndo(undefined)
          undo()
        }}
        onReset={() => {
          commit(resetAll())
          setResetUndo(Date.now())
        }}
      />
      )}
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
      {!embed && <Notices notices={notices} onDismiss={() => setDismissed(routeKey)} />}
      {/* Only while the hash is still bare and nothing has been clicked: once
          there is a build on screen, an older one is noise, not an offer. */}
      {!embed && last && !editing && last.classId === classId && last.t !== encoded && (
        <ContinueLine entry={last} version={cls.dataVersion} />
      )}
      {embed && <EmbedBar cls={cls} build={build} spent={spent} link={link} />}
      <div className="class-layout">
        <div className="class-main">
          <PageTabs pages={cls.pages} active={activePage} counts={pageCounts} budgets={cls.rules.pointsPerPage} onSelect={setPage} />
          <div className="tree-columns">
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
                onReset={(treeId) => commit(resetTree(build!, treeId))}
                sel={sel}
                onDeselect={deselect}
              />
            ))}
          </div>
          {!embed && (
          <div className="class-help mt-3 text-xs text-[var(--text-dim)]">
            {coarse
              ? 'Tap a talent for its tooltip, then + to add a point and - to remove one.'
              : 'Left click adds a point, right click removes one. Ctrl+Z undoes, Ctrl+Shift+Z redoes. With a talent focused: Enter or Space adds, Backspace removes, arrow keys move. Move the pointer into a tooltip to keep it open, or press d to show where its numbers come from.'}
            {cls.notes?.map((n, i) => (
              <div key={i}>{n}</div>
            ))}
          </div>
          )}
        </div>
        {!embed && (
          <BuildSummary
            cls={cls}
            build={build}
            link={link}
            code={encoded}
            canUndo={editing && canUndo(edit)}
            canRedo={editing && canRedo(edit)}
            onUndo={undo}
            onRedo={redo}
            onJump={jumpTo}
            onImport={applyImport}
          />
        )}
      </div>
    </div>
  )
}

/** Offered, never applied: a bare `#/<class>` must still show an empty build. */
function ContinueLine({ entry, version }: { entry: LastBuild; version: number }) {
  const summary = `${continueLabel(entry)}`
  return (
    <p className="continue-line" data-testid="continue-line">
      <a href={classHash(entry.classId, entry.v || version, entry.t)} data-testid="continue-link">
        {summary}
      </a>
      <span className="text-[var(--text-dim)]"> - your last build on this browser.</span>
    </p>
  )
}

/**
 * The whole of embed mode's chrome (brief idea 16): who this build belongs to,
 * what it costs, and one way out. An iframe on a forum has no room for the
 * header, the summary column or the footer, and repeating the site caveat in
 * somebody else's page would be furniture rather than information - the link
 * back leads to the page that states it.
 */
function EmbedBar({ cls, build, spent, link }: { cls: ClassData; build: Build; spent: number; link: string }) {
  const spread = cls.trees.map((t) => pointsInTree(build, t.id)).join('/')
  return (
    <div className="embed-bar" data-testid="embed-bar">
      <strong className="serif text-[var(--gold)]">
        {cls.className} {spread}
      </strong>
      <span data-testid="embed-points">
        {spent} of {cls.rules.maxPoints} points - level {requiredLevel(spent, cls.rules)}
      </span>
      <a href={link} target="_blank" rel="noreferrer" data-testid="embed-open">
        Open the full calculator
      </a>
    </div>
  )
}

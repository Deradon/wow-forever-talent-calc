/**
 * Hash routing: `#/`, `#/<class>?v=<N>&t=<build>`, `#/changes[/<class>]`,
 * `#/races[/<race>][?variant=<id>]`, `#/spells[/<class>]`, `#/review/<class>`.
 * No router library: parseHash plus a `hashchange` listener in App.tsx.
 *
 * Two optional parameters ride along on the class route and are ignored by the
 * build codec (brief `docs/briefs/ui-improvements.md`, section 5):
 *
 *   `sel=<talentId>`  open that talent's tooltip, pinned. Written while a
 *                     talent is pinned, dropped when it is dismissed, so a
 *                     `#/changes` row can link at one talent.
 *   `embed=1`         chromeless: trees, a points line and a link back.
 */
export type Route =
  | { kind: 'picker' }
  | { kind: 'class'; classId: string; version?: number; build?: string; sel?: string; embed?: true }
  | { kind: 'changes'; classId?: string }
  /**
   * `#/races` is the race/class matrix, `#/races/<race>` one race. `variant`
   * picks the Skyborne variant and is view state: an unknown id falls back to
   * the Alliance variant rather than emptying the page.
   */
  | { kind: 'races'; raceId?: string; variant?: string }
  /**
   * `#/spells` is the coverage overview, `#/spells/<class>` one class's
   * spellbook as the stream showed it. Priest has no file and is not a route:
   * the page says so rather than rendering an empty book.
   */
  | { kind: 'spells'; classId?: string }
  | { kind: 'review'; classId: string }
  | { kind: 'unknown'; hash: string }

const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/

export function parseHash(hash: string): Route {
  let h = hash.startsWith('#') ? hash.slice(1) : hash
  if (h.startsWith('/')) h = h.slice(1)
  if (h === '') return { kind: 'picker' }

  const q = h.indexOf('?')
  const path = q === -1 ? h : h.slice(0, q)
  const params = new URLSearchParams(q === -1 ? '' : h.slice(q + 1))
  const segments = path.split('/').filter(Boolean)

  if (segments[0] === 'review' && segments[1] && SLUG.test(segments[1])) {
    return { kind: 'review', classId: segments[1] }
  }
  // `#/changes` is the whole-game overview, `#/changes/<class>` one class.
  if (segments[0] === 'changes' && segments.length <= 2) {
    if (segments.length === 1) return { kind: 'changes' }
    if (segments[1] && SLUG.test(segments[1])) return { kind: 'changes', classId: segments[1] }
  }
  // `#/races` is the matrix, `#/races/<race>` one race and its traits.
  if (segments[0] === 'races' && segments.length <= 2) {
    const variant = params.get('variant')
    const view = variant && SLUG.test(variant) ? { variant } : {}
    if (segments.length === 1) return { kind: 'races' }
    if (segments[1] && SLUG.test(segments[1])) return { kind: 'races', raceId: segments[1], ...view }
  }
  // `#/spells` is the coverage overview, `#/spells/<class>` one spellbook.
  if (segments[0] === 'spells' && segments.length <= 2) {
    if (segments.length === 1) return { kind: 'spells' }
    if (segments[1] && SLUG.test(segments[1])) return { kind: 'spells', classId: segments[1] }
  }
  if (segments.length === 1 && segments[0] && SLUG.test(segments[0])) {
    const v = params.get('v')
    const t = params.get('t')
    const sel = params.get('sel')
    const version = v === null ? undefined : Number(v)
    return {
      kind: 'class',
      classId: segments[0],
      version: version !== undefined && Number.isFinite(version) ? version : v === null ? undefined : NaN,
      build: t ?? undefined,
      sel: sel && SLUG.test(sel) ? sel : undefined,
      embed: params.get('embed') === '1' ? true : undefined,
    }
  }
  return { kind: 'unknown', hash }
}

export function buildHash(route: Route): string {
  switch (route.kind) {
    case 'picker':
      return '#/'
    case 'review':
      return `#/review/${route.classId}`
    case 'changes':
      return route.classId ? `#/changes/${route.classId}` : '#/changes'
    case 'spells':
      return route.classId ? `#/spells/${route.classId}` : '#/spells'
    case 'races': {
      if (!route.raceId) return '#/races'
      // The variant only means something on a race that has variants, so it is
      // never written without a race.
      return `#/races/${route.raceId}${route.variant ? `?variant=${route.variant}` : ''}`
    }
    case 'class': {
      const params = new URLSearchParams()
      if (route.build) {
        if (route.version !== undefined) params.set('v', String(route.version))
        params.set('t', route.build)
      }
      // Both are view state, not build state: they come after `t=` so the
      // shareable prefix of a link stays the one round 1 published.
      if (route.sel) params.set('sel', route.sel)
      if (route.embed) params.set('embed', '1')
      const qs = params.toString()
      return `#/${route.classId}${qs ? `?${qs}` : ''}`
    }
    default:
      return route.hash
  }
}

/** View state that rides along on a class hash without touching the build. */
export interface ClassView {
  /** Talent whose tooltip is pinned open. */
  sel?: string
  /** Chromeless embed. */
  embed?: boolean
}

/** Hash for a class build: `#/warrior?v=3&t=30502-05-3`, or `#/warrior` when empty. */
export function classHash(classId: string, version: number, build: string, view: ClassView = {}): string {
  return buildHash({
    kind: 'class',
    classId,
    version,
    build: build || undefined,
    sel: view.sel,
    embed: view.embed ? true : undefined,
  })
}

/** `#/changes` or `#/changes/<class>`. */
export function changesHash(classId?: string): string {
  return buildHash({ kind: 'changes', classId })
}

/** `#/spells` or `#/spells/<class>`. */
export function spellsHash(classId?: string): string {
  return buildHash({ kind: 'spells', classId })
}

/** `#/races`, `#/races/<race>` or `#/races/<race>?variant=<id>`. */
export function racesHash(raceId?: string, variant?: string): string {
  return buildHash({ kind: 'races', raceId, variant })
}

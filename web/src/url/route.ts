/**
 * Hash routing: `#/`, `#/<class>?v=<N>&t=<build>`, `#/review/<class>`.
 * No router library: parseHash plus a `hashchange` listener in App.tsx.
 */
export type Route =
  | { kind: 'picker' }
  | { kind: 'class'; classId: string; version?: number; build?: string }
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
  if (segments.length === 1 && segments[0] && SLUG.test(segments[0])) {
    const v = params.get('v')
    const t = params.get('t')
    const version = v === null ? undefined : Number(v)
    return {
      kind: 'class',
      classId: segments[0],
      version: version !== undefined && Number.isFinite(version) ? version : v === null ? undefined : NaN,
      build: t ?? undefined,
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
    case 'class': {
      const params = new URLSearchParams()
      if (route.build) {
        if (route.version !== undefined) params.set('v', String(route.version))
        params.set('t', route.build)
      }
      const qs = params.toString()
      return `#/${route.classId}${qs ? `?${qs}` : ''}`
    }
    default:
      return route.hash
  }
}

/** Hash for a class build: `#/warrior?v=3&t=30502-05-3`, or `#/warrior` when empty. */
export function classHash(classId: string, version: number, build: string): string {
  return buildHash({ kind: 'class', classId, version, build: build || undefined })
}

/**
 * "Continue: Warrior 31/0/20" (brief "UI and UX improvements", idea 8).
 *
 * Per viewer, best effort, and never authoritative: the URL always wins. The
 * value is only read where the hash carries no build - the landing page, and a
 * bare `#/<class>` - and even then it is offered as a link, never applied
 * automatically, so a shared link or a bookmark can never be overridden.
 *
 * Every access is wrapped: localStorage throws in a private window, when site
 * data is blocked, and when the quota is full.
 */
export const LAST_BUILD_KEY = 'wft.last'

export interface LastBuild {
  classId: string
  /** Encoding version, as in `?v=`. */
  v: number
  /** Build string, as in `?t=`. Empty means an empty build, which is not stored. */
  t: string
  /** Denormalised so the landing page can render the card without a class chunk. */
  className: string
  /** `31/0/20`. */
  spread: string
  savedAt: number
}

export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

function store(explicit?: StorageLike): StorageLike | undefined {
  if (explicit) return explicit
  try {
    return globalThis.localStorage ?? undefined
  } catch {
    return undefined
  }
}

function isLastBuild(value: unknown): value is LastBuild {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return (
    typeof v.classId === 'string' &&
    v.classId !== '' &&
    typeof v.t === 'string' &&
    v.t !== '' &&
    typeof v.v === 'number' &&
    Number.isInteger(v.v) &&
    typeof v.className === 'string' &&
    typeof v.spread === 'string' &&
    typeof v.savedAt === 'number'
  )
}

export function readLastBuild(explicit?: StorageLike): LastBuild | undefined {
  const s = store(explicit)
  if (!s) return undefined
  try {
    const raw = s.getItem(LAST_BUILD_KEY)
    if (!raw) return undefined
    const parsed: unknown = JSON.parse(raw)
    return isLastBuild(parsed) ? parsed : undefined
  } catch {
    return undefined
  }
}

/** Writes, or clears the entry when the build is empty. Never throws. */
export function writeLastBuild(entry: Omit<LastBuild, 'savedAt'> & { savedAt?: number }, explicit?: StorageLike): void {
  const s = store(explicit)
  if (!s) return
  try {
    if (!entry.t) {
      s.removeItem(LAST_BUILD_KEY)
      return
    }
    s.setItem(LAST_BUILD_KEY, JSON.stringify({ ...entry, savedAt: entry.savedAt ?? Date.now() }))
  } catch {
    /* private window, blocked site data, quota: the feature is optional */
  }
}

export function forgetLastBuild(explicit?: StorageLike): void {
  const s = store(explicit)
  if (!s) return
  try {
    s.removeItem(LAST_BUILD_KEY)
  } catch {
    /* see writeLastBuild */
  }
}

/** `Continue: Warrior 31/0/20`. */
export function continueLabel(entry: LastBuild): string {
  return `Continue: ${entry.className} ${entry.spread}`
}

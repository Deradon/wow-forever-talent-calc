/**
 * The "highlight what's new" toggle (brief idea 3).
 *
 * It is one switch for all three trees, but the control itself has to live in
 * the tree panel header: the class-page header is owned elsewhere. A tiny
 * external store is therefore the shared state - every `TreePanel` subscribes,
 * the leftmost one renders the switch, and nothing in `ClassPage` has to know.
 *
 * Deliberately module-level and not persisted: it is a way of looking at a
 * tree, not part of the build, so it must never end up in a shared link.
 */
import { useSyncExternalStore } from 'react'

let on = false
const listeners = new Set<() => void>()

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function snapshot(): boolean {
  return on
}

export function setHighlightNew(next: boolean): void {
  if (on === next) return
  on = next
  for (const l of [...listeners]) l()
}

export function useHighlightNew(): boolean {
  return useSyncExternalStore(subscribe, snapshot, snapshot)
}

/**
 * The corner marker a talent's Classic status earns, if any.
 *
 * Round two found the star and the ring disagreeing about what "new" is: the
 * switch rang 49 of 52 paladin cells in one blue whether a talent was brand new
 * or had one number nudged, while the star meant only `new` (21 cells) - so the
 * ring said "changed" and the star said "new" in the same colour (UX review
 * round two, finding 9). One vocabulary now: a blue star and a blue ring for
 * new, an amber mark and an amber ring for a rewrite, a violet ring and no
 * marker for a move, and nothing at all for a talent that only changed column
 * (which the diff classifies as `same`).
 */
export type ChangeMarker = 'new' | 'reworked'

export function changeMarker(status: string | undefined): ChangeMarker | undefined {
  if (status === 'new') return 'new'
  if (status === 'text-changed' || status === 'values-changed') return 'reworked'
  return undefined
}

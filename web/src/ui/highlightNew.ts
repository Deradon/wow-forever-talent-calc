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

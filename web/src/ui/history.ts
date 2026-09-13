/**
 * Undo / redo for the class page (brief "UI and UX improvements", idea 7).
 *
 * Pure and in memory only: the hash keeps using `replaceState`, so a shared
 * link stays live and the browser history does not gain an entry per click.
 * The reducer is keyed by the route, so arriving at a different build (Back, a
 * pasted link, an import) starts a fresh stack instead of letting Ctrl+Z walk
 * into a build the URL no longer describes.
 */
import type { Build } from '../rules'

/** Stack cap. 50 snapshots of a 51-point build is a few kB. */
export const HISTORY_LIMIT = 50

export interface EditState {
  /** `classId|version|buildString` of the route this stack belongs to. */
  key: string
  past: Build[]
  present: Build
  future: Build[]
}

export type EditAction =
  /** The URL changed under us: drop the stack and adopt the decoded build. */
  | { type: 'route'; key: string; build: Build }
  /** A player edit (add, remove, tree reset, reset all, import). */
  | { type: 'commit'; key: string; build: Build }
  | { type: 'undo' }
  | { type: 'redo' }

export function initEdit(key: string, build: Build): EditState {
  return { key, past: [], present: build, future: [] }
}

export function canUndo(state: EditState): boolean {
  return state.past.length > 0
}

export function canRedo(state: EditState): boolean {
  return state.future.length > 0
}

export function editReducer(state: EditState, action: EditAction): EditState {
  switch (action.type) {
    case 'route':
      if (state.key === action.key && state.present === action.build) return state
      return initEdit(action.key, action.build)

    case 'commit': {
      // A commit for another route replaces the stack rather than appending to
      // a history that belonged to a different build.
      if (state.key !== action.key) return initEdit(action.key, action.build)
      if (action.build === state.present) return state
      const past = [...state.past, state.present]
      return {
        key: state.key,
        past: past.length > HISTORY_LIMIT ? past.slice(past.length - HISTORY_LIMIT) : past,
        present: action.build,
        future: [],
      }
    }

    case 'undo': {
      const previous = state.past[state.past.length - 1]
      if (previous === undefined) return state
      return {
        key: state.key,
        past: state.past.slice(0, -1),
        present: previous,
        future: [state.present, ...state.future],
      }
    }

    case 'redo': {
      const next = state.future[0]
      if (next === undefined) return state
      return {
        key: state.key,
        past: [...state.past, state.present],
        present: next,
        future: state.future.slice(1),
      }
    }

    default:
      return state
  }
}

/**
 * Ctrl/Cmd+Z undoes, Ctrl/Cmd+Shift+Z and Ctrl+Y redo. Returns undefined for
 * everything else, including while a text field has focus, so typing in the
 * search box or the import textarea keeps the browser's own undo.
 */
export function undoShortcut(e: {
  key: string
  ctrlKey: boolean
  metaKey: boolean
  shiftKey: boolean
  altKey?: boolean
}): 'undo' | 'redo' | undefined {
  if (!(e.ctrlKey || e.metaKey) || e.altKey) return undefined
  const key = e.key.toLowerCase()
  if (key === 'z') return e.shiftKey ? 'redo' : 'undo'
  if (key === 'y' && !e.shiftKey) return 'redo'
  return undefined
}

/** True when a keystroke belongs to a text field and must not be hijacked. */
export function isTextEntry(el: { tagName?: string; isContentEditable?: boolean } | null | undefined): boolean {
  if (!el) return false
  return el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable === true
}

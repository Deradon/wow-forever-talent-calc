import { describe, expect, it } from 'vitest'
import type { Build } from '../rules'
import { canRedo, canUndo, editReducer, HISTORY_LIMIT, initEdit, isTextEntry, undoShortcut, type EditState } from './history'

const KEY = 'testclass|2|'
const a: Build = { alpha: { 'a-one': 1 } }
const b: Build = { alpha: { 'a-one': 2 } }
const c: Build = { alpha: { 'a-one': 3 } }

function commit(state: EditState, build: Build, key = KEY): EditState {
  return editReducer(state, { type: 'commit', key, build })
}

describe('editReducer', () => {
  it('starts empty and cannot undo or redo', () => {
    const s = initEdit(KEY, {})
    expect(canUndo(s)).toBe(false)
    expect(canRedo(s)).toBe(false)
    expect(editReducer(s, { type: 'undo' })).toBe(s)
    expect(editReducer(s, { type: 'redo' })).toBe(s)
  })

  it('walks back and forward through commits', () => {
    let s = commit(commit(initEdit(KEY, {}), a), b)
    expect(s.present).toBe(b)
    expect(canUndo(s)).toBe(true)

    s = editReducer(s, { type: 'undo' })
    expect(s.present).toBe(a)
    s = editReducer(s, { type: 'undo' })
    expect(s.present).toEqual({})
    expect(canUndo(s)).toBe(false)
    expect(canRedo(s)).toBe(true)

    s = editReducer(s, { type: 'redo' })
    expect(s.present).toBe(a)
    s = editReducer(s, { type: 'redo' })
    expect(s.present).toBe(b)
    expect(canRedo(s)).toBe(false)
  })

  it('drops the redo branch on a new commit', () => {
    let s = commit(commit(initEdit(KEY, {}), a), b)
    s = editReducer(s, { type: 'undo' })
    s = commit(s, c)
    expect(s.present).toBe(c)
    expect(canRedo(s)).toBe(false)
    expect(editReducer(s, { type: 'undo' }).present).toBe(a)
  })

  it('is a no-op when the build did not change', () => {
    const s = commit(initEdit(KEY, {}), a)
    expect(commit(s, a)).toBe(s)
  })

  it(`caps the stack at ${HISTORY_LIMIT} and keeps the newest entries`, () => {
    let s = initEdit(KEY, { alpha: { 'a-one': 0 } })
    for (let i = 1; i <= HISTORY_LIMIT + 10; i++) s = commit(s, { alpha: { 'a-one': i } })
    expect(s.past).toHaveLength(HISTORY_LIMIT)
    expect(s.past[0]).toEqual({ alpha: { 'a-one': 10 } })
    expect(s.present).toEqual({ alpha: { 'a-one': HISTORY_LIMIT + 10 } })
  })

  it('resets the stack when the route changes (Back, a pasted link, an import)', () => {
    const s = commit(commit(initEdit(KEY, {}), a), b)
    const routed = editReducer(s, { type: 'route', key: 'testclass|2|3', build: c })
    expect(routed.present).toBe(c)
    expect(routed.key).toBe('testclass|2|3')
    expect(canUndo(routed)).toBe(false)
    expect(canRedo(routed)).toBe(false)
  })

  it('keeps the stack when the route event repeats the build it already holds', () => {
    const s = commit(initEdit(KEY, {}), a)
    expect(editReducer(s, { type: 'route', key: KEY, build: a })).toBe(s)
  })

  it('restarts on a commit that belongs to another route', () => {
    const s = commit(initEdit(KEY, {}), a)
    const other = commit(s, b, 'other|2|')
    expect(other.key).toBe('other|2|')
    expect(canUndo(other)).toBe(false)
  })

  it('seeds the stack from the route, so the first edit is undoable back to the URL', () => {
    // What ClassPage does on the first edit after arriving at ?t=...
    let s = initEdit('', {})
    s = editReducer(s, { type: 'route', key: KEY, build: a })
    s = commit(s, b)
    expect(canUndo(s)).toBe(true)
    expect(editReducer(s, { type: 'undo' }).present).toBe(a)
  })

  it('makes a reset undoable, because a reset is an ordinary commit', () => {
    let s = commit(commit(initEdit(KEY, {}), a), b)
    s = commit(s, {})
    expect(s.present).toEqual({})
    expect(editReducer(s, { type: 'undo' }).present).toBe(b)
  })
})

describe('undoShortcut', () => {
  const base = { ctrlKey: false, metaKey: false, shiftKey: false, altKey: false }
  it('maps Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y and their Cmd forms', () => {
    expect(undoShortcut({ ...base, ctrlKey: true, key: 'z' })).toBe('undo')
    expect(undoShortcut({ ...base, metaKey: true, key: 'Z' })).toBe('undo')
    expect(undoShortcut({ ...base, ctrlKey: true, shiftKey: true, key: 'Z' })).toBe('redo')
    expect(undoShortcut({ ...base, ctrlKey: true, key: 'y' })).toBe('redo')
    expect(undoShortcut({ ...base, metaKey: true, shiftKey: true, key: 'z' })).toBe('redo')
  })
  it('ignores a bare z, Alt combinations and anything else', () => {
    expect(undoShortcut({ ...base, key: 'z' })).toBeUndefined()
    expect(undoShortcut({ ...base, ctrlKey: true, altKey: true, key: 'z' })).toBeUndefined()
    expect(undoShortcut({ ...base, ctrlKey: true, key: 'a' })).toBeUndefined()
    expect(undoShortcut({ ...base, ctrlKey: true, shiftKey: true, key: 'y' })).toBeUndefined()
  })
})

describe('isTextEntry', () => {
  it('recognises the fields whose own undo must win', () => {
    expect(isTextEntry({ tagName: 'INPUT' })).toBe(true)
    expect(isTextEntry({ tagName: 'TEXTAREA' })).toBe(true)
    expect(isTextEntry({ tagName: 'DIV', isContentEditable: true })).toBe(true)
    expect(isTextEntry({ tagName: 'BUTTON' })).toBe(false)
    expect(isTextEntry(null)).toBe(false)
  })
})

import { describe, expect, it } from 'vitest'
import {
  continueLabel,
  forgetLastBuild,
  LAST_BUILD_KEY,
  readLastBuild,
  writeLastBuild,
  type LastBuild,
  type StorageLike,
} from './storage'

function memory(initial: Record<string, string> = {}): StorageLike & { data: Record<string, string> } {
  const data = { ...initial }
  return {
    data,
    getItem: (k) => data[k] ?? null,
    setItem: (k, v) => {
      data[k] = v
    },
    removeItem: (k) => {
      delete data[k]
    },
  }
}

const entry: LastBuild = { classId: 'warrior', v: 1, t: '30250-005-32', className: 'Warrior', spread: '31/0/20', savedAt: 17 }

describe('last build storage', () => {
  it('round-trips an entry', () => {
    const s = memory()
    writeLastBuild(entry, s)
    expect(readLastBuild(s)).toEqual(entry)
  })

  it('stamps savedAt when the caller does not', () => {
    const s = memory()
    writeLastBuild({ ...entry, savedAt: undefined }, s)
    expect(readLastBuild(s)!.savedAt).toBeGreaterThan(0)
  })

  it('clears the entry for an empty build instead of storing one', () => {
    const s = memory()
    writeLastBuild(entry, s)
    writeLastBuild({ ...entry, t: '' }, s)
    expect(s.data[LAST_BUILD_KEY]).toBeUndefined()
    expect(readLastBuild(s)).toBeUndefined()
  })

  it('forgets on request', () => {
    const s = memory()
    writeLastBuild(entry, s)
    forgetLastBuild(s)
    expect(readLastBuild(s)).toBeUndefined()
  })

  it('ignores junk, foreign data and half-written entries', () => {
    expect(readLastBuild(memory({ [LAST_BUILD_KEY]: 'not json' }))).toBeUndefined()
    expect(readLastBuild(memory({ [LAST_BUILD_KEY]: '"a string"' }))).toBeUndefined()
    expect(readLastBuild(memory({ [LAST_BUILD_KEY]: '{"classId":"warrior"}' }))).toBeUndefined()
    expect(readLastBuild(memory({ [LAST_BUILD_KEY]: JSON.stringify({ ...entry, v: 1.5 }) }))).toBeUndefined()
    expect(readLastBuild(memory())).toBeUndefined()
  })

  it('never throws when the storage itself throws (private window, blocked site data)', () => {
    const hostile: StorageLike = {
      getItem() {
        throw new Error('denied')
      },
      setItem() {
        throw new Error('denied')
      },
      removeItem() {
        throw new Error('denied')
      },
    }
    expect(() => writeLastBuild(entry, hostile)).not.toThrow()
    expect(() => forgetLastBuild(hostile)).not.toThrow()
    expect(readLastBuild(hostile)).toBeUndefined()
  })

  it('labels the continue card', () => {
    expect(continueLabel(entry)).toBe('Continue: Warrior 31/0/20')
  })
})

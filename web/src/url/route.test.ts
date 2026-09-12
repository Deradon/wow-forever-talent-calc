import { describe, expect, it } from 'vitest'
import { buildHash, classHash, parseHash } from './route'

describe('hash routing', () => {
  it('parses the documented forms', () => {
    expect(parseHash('')).toEqual({ kind: 'picker' })
    expect(parseHash('#/')).toEqual({ kind: 'picker' })
    expect(parseHash('#/warrior')).toEqual({ kind: 'class', classId: 'warrior', version: undefined, build: undefined })
    expect(parseHash('#/warrior?v=3&t=30502-05-3')).toEqual({ kind: 'class', classId: 'warrior', version: 3, build: '30502-05-3' })
    expect(parseHash('#/warrior?v=3&t=--3')).toMatchObject({ build: '--3' })
    expect(parseHash('#/review/warrior')).toEqual({ kind: 'review', classId: 'warrior' })
    expect(parseHash('#/Warrior/extra')).toMatchObject({ kind: 'unknown' })
  })

  it('builds hashes that parse back', () => {
    expect(classHash('warrior', 3, '30502-05-3')).toBe('#/warrior?v=3&t=30502-05-3')
    expect(classHash('warrior', 3, '')).toBe('#/warrior')
    expect(buildHash({ kind: 'review', classId: 'mage' })).toBe('#/review/mage')
    expect(parseHash(classHash('warrior', 3, '--3'))).toMatchObject({ classId: 'warrior', version: 3, build: '--3' })
  })
})

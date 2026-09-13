import { describe, expect, it } from 'vitest'
import { buildHash, changesHash, classHash, parseHash } from './route'

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

  it('parses the round-2 routes and their view parameters', () => {
    expect(parseHash('#/changes')).toEqual({ kind: 'changes' })
    expect(parseHash('#/changes/warrior')).toEqual({ kind: 'changes', classId: 'warrior' })
    expect(parseHash('#/changes/Warrior')).toMatchObject({ kind: 'unknown' })
    expect(parseHash('#/changes/a/b')).toMatchObject({ kind: 'unknown' })

    expect(parseHash('#/warrior?sel=focused-rage')).toMatchObject({ kind: 'class', sel: 'focused-rage' })
    expect(parseHash('#/warrior?v=3&t=30502-05-3&sel=focused-rage&embed=1')).toEqual({
      kind: 'class',
      classId: 'warrior',
      version: 3,
      build: '30502-05-3',
      sel: 'focused-rage',
      embed: true,
    })
    // `sel` is a talent id or it is nothing: it goes straight into a DOM query.
    expect(parseHash('#/warrior?sel=<script>')).toMatchObject({ sel: undefined })
    expect(parseHash('#/warrior?embed=0')).toMatchObject({ embed: undefined })
  })

  it('builds hashes that parse back', () => {
    expect(classHash('warrior', 3, '30502-05-3')).toBe('#/warrior?v=3&t=30502-05-3')
    expect(classHash('warrior', 3, '')).toBe('#/warrior')
    expect(buildHash({ kind: 'review', classId: 'mage' })).toBe('#/review/mage')
    expect(parseHash(classHash('warrior', 3, '--3'))).toMatchObject({ classId: 'warrior', version: 3, build: '--3' })
  })

  it('carries the view parameters without disturbing the build prefix', () => {
    expect(classHash('warrior', 3, '30502-05-3', { sel: 'focused-rage' })).toBe(
      '#/warrior?v=3&t=30502-05-3&sel=focused-rage',
    )
    expect(classHash('warrior', 3, '', { sel: 'focused-rage' })).toBe('#/warrior?sel=focused-rage')
    expect(classHash('warrior', 3, '30502-05-3', { embed: true })).toBe('#/warrior?v=3&t=30502-05-3&embed=1')
    expect(classHash('warrior', 3, '30502-05-3', { embed: false })).toBe('#/warrior?v=3&t=30502-05-3')
    expect(changesHash()).toBe('#/changes')
    expect(changesHash('warrior')).toBe('#/changes/warrior')
    expect(parseHash(changesHash('warrior'))).toEqual({ kind: 'changes', classId: 'warrior' })
    expect(parseHash(classHash('warrior', 3, '--3', { sel: 'x', embed: true }))).toMatchObject({
      build: '--3',
      sel: 'x',
      embed: true,
    })
  })
})

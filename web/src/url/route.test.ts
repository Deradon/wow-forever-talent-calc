import { describe, expect, it } from 'vitest'
import { aboutHash, buildHash, changesHash, classHash, parseHash, racesHash, spellsHash } from './route'

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

  it('reads #/about as the about page, not as a class called "about"', () => {
    expect(parseHash('#/about')).toEqual({ kind: 'about' })
    expect(aboutHash()).toBe('#/about')
    expect(parseHash(aboutHash())).toEqual({ kind: 'about' })
    // Only the bare form; anything deeper is still unknown.
    expect(parseHash('#/about/us')).toMatchObject({ kind: 'unknown' })
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

  it('routes the races pages and their variant parameter', () => {
    expect(parseHash('#/races')).toEqual({ kind: 'races' })
    expect(parseHash('#/races/night-elf')).toEqual({ kind: 'races', raceId: 'night-elf' })
    expect(parseHash('#/races/skyborne?variant=windshaper')).toEqual({
      kind: 'races',
      raceId: 'skyborne',
      variant: 'windshaper',
    })
    // A variant without a race says nothing, and a non-slug variant is dropped
    // rather than carried into the page.
    expect(parseHash('#/races?variant=windshaper')).toEqual({ kind: 'races' })
    expect(parseHash('#/races/skyborne?variant=<script>')).toEqual({ kind: 'races', raceId: 'skyborne' })
    expect(parseHash('#/races/Skyborne')).toMatchObject({ kind: 'unknown' })
    expect(parseHash('#/races/a/b')).toMatchObject({ kind: 'unknown' })

    expect(racesHash()).toBe('#/races')
    expect(racesHash('tauren')).toBe('#/races/tauren')
    expect(racesHash('skyborne', 'high-order')).toBe('#/races/skyborne?variant=high-order')
    expect(racesHash(undefined, 'high-order')).toBe('#/races')
    expect(parseHash(racesHash('skyborne', 'high-order'))).toEqual({
      kind: 'races',
      raceId: 'skyborne',
      variant: 'high-order',
    })
  })

  it('routes the spell pages', () => {
    expect(parseHash('#/spells')).toEqual({ kind: 'spells' })
    expect(parseHash('#/spells/mage')).toEqual({ kind: 'spells', classId: 'mage' })
    // Priest has no spellbook file, but the route still exists: the page says
    // so, which is a better answer than an unknown-route panel.
    expect(parseHash('#/spells/priest')).toEqual({ kind: 'spells', classId: 'priest' })
    expect(parseHash('#/spells/Mage')).toMatchObject({ kind: 'unknown' })
    expect(parseHash('#/spells/mage/fire')).toMatchObject({ kind: 'unknown' })

    expect(spellsHash()).toBe('#/spells')
    expect(spellsHash('shaman')).toBe('#/spells/shaman')
    expect(parseHash(spellsHash('shaman'))).toEqual({ kind: 'spells', classId: 'shaman' })
  })
})

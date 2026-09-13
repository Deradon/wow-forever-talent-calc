import { describe, expect, it } from 'vitest'
import { makeClass } from '../rules/fixture'
import { canAdd, canRemove } from '../rules'
import { blockedMessage, matchesTalent } from './interaction'

const talent = { name: 'Improved Power Word: Shield', description: 'Increases the damage absorbed by 5%.' }

describe('matchesTalent', () => {
  it('matches on name, case-insensitively and on a fragment', () => {
    expect(matchesTalent(talent, 'power word')).toBe(true)
    expect(matchesTalent(talent, 'POWER')).toBe(true)
    expect(matchesTalent(talent, 'shield')).toBe(true)
  })

  it('matches on the description too', () => {
    expect(matchesTalent(talent, 'absorbed')).toBe(true)
  })

  it('rejects a non-match and accepts everything for an empty query', () => {
    expect(matchesTalent(talent, 'fireball')).toBe(false)
    expect(matchesTalent(talent, '   ')).toBe(true)
  })
})

describe('blockedMessage', () => {
  const cls = makeClass()
  const A = 'alpha'

  it('names the row requirement when a talent is locked', () => {
    const verdict = canAdd(cls, {}, A, 'c-one')
    expect(verdict).toMatchObject({ ok: false, reason: 'row-locked' })
    expect(blockedMessage('c-one', verdict, 'add')).toBe('c-one needs 10 points in Alpha.')
  })

  it('names the prerequisite when one is missing', () => {
    const build = { [A]: { 'a-two': 5 } }
    const verdict = canAdd(cls, build, A, 'b-one')
    expect(verdict).toMatchObject({ ok: false, reason: 'prereq' })
    expect(blockedMessage('b-one', verdict, 'add')).toBe('b-one requires 5 points in a-one.')
  })

  it('says a refund would orphan the talent it would break, by name', () => {
    const build = { [A]: { 'a-one': 5, 'b-one': 1 } }
    const verdict = canRemove(cls, build, A, 'a-one')
    expect(verdict).toMatchObject({ ok: false, reason: 'would-orphan' })
    expect(blockedMessage('a-one', verdict, 'remove')).toBe('Refunding a-one would orphan b-one.')
  })

  it('explains a full point pool and a maxed talent', () => {
    expect(blockedMessage('X', { ok: false, reason: 'no-points' }, 'add')).toContain('No talent points left')
    expect(blockedMessage('X', { ok: false, reason: 'maxed' }, 'add')).toBe('X is already at its maximum rank.')
    expect(blockedMessage('X', { ok: true }, 'add')).toBe('')
  })

})

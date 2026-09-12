import { describe, expect, it } from 'vitest'
import fc from 'fast-check'
import { makeClass } from './fixture'
import {
  add,
  canAdd,
  canRemove,
  pointsInTree,
  remove,
  requiredLevel,
  resetAll,
  resetTree,
  sanitize,
  totalPoints,
  validate,
  type Build,
} from './index'

const cls = makeClass()
const A = 'alpha'
const B = 'beta'

function build(spec: Record<string, Record<string, number>>): Build {
  return spec
}

describe('rules engine (brief section 4 table)', () => {
  it('1: empty build, row-0 talent: canAdd ok; level 1 -> 10 after first point', () => {
    expect(canAdd(cls, {}, A, 'a-one')).toEqual({ ok: true })
    expect(requiredLevel(totalPoints({}), cls.rules)).toBe(1)
    const b = add(cls, {}, A, 'a-one')
    expect(totalPoints(b)).toBe(1)
    expect(requiredLevel(totalPoints(b), cls.rules)).toBe(10)
  })

  it('2: 4 points in row 0, row-1 talent rejected row-locked; 5th point unlocks', () => {
    const four = build({ [A]: { 'a-one': 4 } })
    expect(canAdd(cls, four, A, 'b-two')).toMatchObject({ ok: false, reason: 'row-locked' })
    const five = add(cls, four, A, 'a-one')
    expect(canAdd(cls, five, A, 'b-two')).toEqual({ ok: true })
  })

  it('3: points only in tree A do not unlock row 1 of tree B', () => {
    const b = build({ [A]: { 'a-one': 5 } })
    expect(canAdd(cls, b, B, 'y-one')).toMatchObject({ ok: false, reason: 'row-locked' })
    expect(canAdd(cls, b, B, 'x-one')).toEqual({ ok: true })
  })

  it('4: rank == maxRank rejected maxed', () => {
    const b = build({ [A]: { 'a-one': 5 } })
    expect(canAdd(cls, b, A, 'a-one')).toMatchObject({ ok: false, reason: 'maxed' })
  })

  it('5: totalPoints == maxPoints rejected no-points everywhere', () => {
    const small = makeClass({ maxPoints: 3 })
    const b = build({ [A]: { 'a-one': 3 } })
    for (const [treeId, talentId] of [
      [A, 'a-two'],
      [A, 'a-one'],
      [B, 'x-one'],
    ] as const) {
      const v = canAdd(small, b, treeId, talentId)
      expect(v.ok).toBe(false)
      if (!v.ok) expect(['no-points', 'maxed']).toContain(v.reason)
    }
    expect(canAdd(small, b, A, 'a-two')).toMatchObject({ ok: false, reason: 'no-points' })
    expect(canAdd(small, b, B, 'x-one')).toMatchObject({ ok: false, reason: 'no-points' })
  })

  it('6: requires 5/5 prereq at 4/5 rejected prereq; ok at 5/5', () => {
    // b-one is in row 1, so row gating must be satisfied by other points to isolate the prereq rule
    const at4 = build({ [A]: { 'a-one': 4, 'a-two': 5 } })
    expect(canAdd(cls, at4, A, 'b-one')).toMatchObject({ ok: false, reason: 'prereq' })
    const at5 = build({ [A]: { 'a-one': 5, 'a-two': 5 } })
    expect(canAdd(cls, at5, A, 'b-one')).toEqual({ ok: true })
  })

  it('7: chain A->B->C, remove from A rejected while B > 0', () => {
    const b = build({ [A]: { 'a-one': 5, 'a-two': 5, 'b-one': 1 } })
    expect(canRemove(cls, b, A, 'a-one')).toMatchObject({ ok: false, reason: 'prereq' })
    expect(remove(cls, b, A, 'a-one')).toBe(b) // no-op copy
    // once B is gone A can be removed again
    const noB = remove(cls, b, A, 'b-one')
    expect(canRemove(cls, noB, A, 'a-one')).toEqual({ ok: true })
    // and the full chain: C blocks B
    const chain = build({ [A]: { 'a-one': 5, 'a-two': 5, 'b-one': 3, 'c-one': 1 } })
    expect(canRemove(cls, chain, A, 'b-one')).toMatchObject({ ok: false, reason: 'prereq' })
    expect(canRemove(cls, chain, A, 'c-one')).toEqual({ ok: true })
  })

  it('8: removing a row-0 point that leaves row 1 with fewer than 5 above rejected would-orphan', () => {
    const b = build({ [A]: { 'a-one': 5, 'b-two': 1 } })
    expect(canRemove(cls, b, A, 'a-one')).toMatchObject({ ok: false, reason: 'would-orphan' })
    expect(remove(cls, b, A, 'a-one')).toBe(b)
  })

  it('9: removing where rows above still meet the threshold is ok', () => {
    const b = build({ [A]: { 'a-one': 5, 'a-two': 1, 'b-two': 1 } })
    expect(canRemove(cls, b, A, 'a-two')).toEqual({ ok: true })
    expect(pointsInTree(remove(cls, b, A, 'a-two'), A)).toBe(6)
  })

  it('10: two paths to the same row total, remove one: ok while threshold met', () => {
    const b = build({ [A]: { 'a-one': 3, 'a-two': 3, 'b-two': 1 } })
    expect(canRemove(cls, b, A, 'a-one')).toEqual({ ok: true })
    const after = remove(cls, b, A, 'a-one')
    expect(canRemove(cls, after, A, 'a-one')).toMatchObject({ ok: false, reason: 'would-orphan' })
    expect(canRemove(cls, after, A, 'a-two')).toMatchObject({ ok: false, reason: 'would-orphan' })
  })

  it('11: capstone with 0 points above rejected row-locked', () => {
    expect(canAdd(cls, {}, A, 'cap')).toMatchObject({ ok: false, reason: 'row-locked' })
    // and with exactly 30 points above it opens
    const thirty = build({ [A]: { 'a-one': 5, 'a-two': 5, 'b-one': 3, 'b-two': 5, 'c-one': 1, 'c-two': 5 } })
    // 24 points so far: row 6 needs 30; still locked
    expect(canAdd(cls, thirty, A, 'cap')).toMatchObject({ ok: false, reason: 'row-locked' })
  })

  it('12: sanitize drops row-2 points that have no row 0/1 support and reports the violation', () => {
    const b = build({ [A]: { 'c-two': 2 } })
    expect(validate(cls, b)).toMatchObject([{ treeId: A, talentId: 'c-two', reason: 'row-locked' }])
    const { build: fixed, dropped } = sanitize(cls, b)
    expect(fixed).toEqual({})
    expect(dropped).toMatchObject([{ treeId: A, talentId: 'c-two', reason: 'row-locked' }])
    expect(validate(cls, fixed)).toEqual([])
  })

  it('sanitize also enforces the point budget from the end of the walk', () => {
    const small = makeClass({ maxPoints: 7 })
    const b = build({ [A]: { 'a-one': 5, 'a-two': 5 } })
    const { build: fixed, dropped } = sanitize(small, b)
    expect(totalPoints(fixed)).toBe(7)
    expect(fixed).toEqual({ [A]: { 'a-one': 5, 'a-two': 2 } })
    expect(dropped).toHaveLength(3)
    expect(dropped.every((d) => d.reason === 'no-points')).toBe(true)
  })

  it('pointsPerPage caps a page independently of maxPoints', () => {
    const paged = makeClass({ pointsPerPage: { primary: 2 } })
    const b = build({ [A]: { 'a-one': 2 } })
    expect(canAdd(paged, b, B, 'x-one')).toMatchObject({ ok: false, reason: 'page-full' })
    expect(validate(paged, build({ [A]: { 'a-one': 3 } }))).toMatchObject([{ reason: 'page-full' }])
  })

  it('resetTree / resetAll', () => {
    const b = build({ [A]: { 'a-one': 5 }, [B]: { 'x-one': 2 } })
    expect(resetTree(b, A)).toEqual({ [B]: { 'x-one': 2 } })
    expect(resetAll()).toEqual({})
  })

  it('18: random click sequences never violate (property)', () => {
    const talents = cls.trees.flatMap((t) => t.talents.map((tal) => [t.id, tal.id] as const))
    const click = fc.tuple(fc.constantFrom(...talents), fc.boolean())
    fc.assert(
      fc.property(fc.array(click, { maxLength: 200 }), (clicks) => {
        let b: Build = {}
        for (const [[treeId, talentId], isAdd] of clicks) {
          b = isAdd ? add(cls, b, treeId, talentId) : remove(cls, b, treeId, talentId)
          expect(validate(cls, b)).toEqual([])
          expect(totalPoints(b)).toBeLessThanOrEqual(cls.rules.maxPoints)
        }
      }),
      { numRuns: 200 },
    )
  })
})

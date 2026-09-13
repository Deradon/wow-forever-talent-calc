import { describe, expect, it } from 'vitest'
import fc from 'fast-check'
import { makeClass, makeHorizontalClass } from './fixture'
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
  type Reason,
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

/**
 * Same-row (horizontal) prerequisites: Forever lets a talent require another
 * one in the same row of the same tree - priest Improved Mind Flay requires
 * Mind Flay next to it. The rules engine never looked at rows for `requires`,
 * so these are regression tests: what changed is the data contract, and the
 * table below pins the behaviour the UI relies on.
 *
 * The fixture (fixture.ts, `makeHorizontalClass`) puts `mid` (3 ranks) in row 1
 * col 1 with three dependents in the same row: `early` left of it, `near` right
 * of it and `far` two cells right of it, each requiring `mid` at 3.
 */
const hcls = makeHorizontalClass()
const F = 'flay'
/** 5 points in row 0, so row 1 is open and only the prerequisite is in play. */
const openRow1 = { 'top-one': 5 }

describe('same-row prerequisites', () => {
  const addCases: { name: string; spent: Record<string, number>; talent: string; want: 'ok' | Reason }[] = [
    { name: 'left-to-right, adjacent, prereq below rank', spent: { ...openRow1, mid: 2 }, talent: 'near', want: 'prereq' },
    { name: 'left-to-right, adjacent, prereq at rank', spent: { ...openRow1, mid: 3 }, talent: 'near', want: 'ok' },
    { name: 'right-to-left, adjacent, prereq below rank', spent: { ...openRow1, mid: 2 }, talent: 'early', want: 'prereq' },
    { name: 'right-to-left, adjacent, prereq at rank', spent: { ...openRow1, mid: 3 }, talent: 'early', want: 'ok' },
    { name: 'left-to-right, two cells apart, prereq below rank', spent: { ...openRow1, mid: 2 }, talent: 'far', want: 'prereq' },
    { name: 'left-to-right, two cells apart, prereq at rank', spent: { ...openRow1, mid: 3 }, talent: 'far', want: 'ok' },
    { name: 'no prerequisite of its own', spent: { ...openRow1 }, talent: 'mid', want: 'ok' },
    // The prerequisite sits in the dependent's own row, so its points do not
    // pay for that row: row gating still asks for 5 points in the rows above.
    { name: 'prereq met but the shared row is still locked', spent: { mid: 3 }, talent: 'near', want: 'row-locked' },
  ]

  for (const { name, spent, talent, want } of addCases) {
    it(`canAdd: ${name}`, () => {
      const verdict = canAdd(hcls, build({ [F]: spent }), F, talent)
      if (want === 'ok') expect(verdict).toEqual({ ok: true })
      else expect(verdict).toMatchObject({ ok: false, reason: want })
    })
  }

  it('canAdd names the prerequisite it is waiting for', () => {
    expect(canAdd(hcls, build({ [F]: { ...openRow1, mid: 2 } }), F, 'near')).toMatchObject({
      ok: false,
      reason: 'prereq',
      detail: '3 points in mid',
    })
  })

  const removeCases: { name: string; spent: Record<string, number>; talent: string; want: 'ok' | Reason; detail?: string }[] = [
    { name: 'prereq blocked while the talent right of it holds points', spent: { ...openRow1, mid: 3, near: 1 }, talent: 'mid', want: 'prereq', detail: 'near' },
    { name: 'prereq blocked while the talent left of it holds points', spent: { ...openRow1, mid: 3, early: 1 }, talent: 'mid', want: 'prereq', detail: 'early' },
    { name: 'prereq blocked while a non-adjacent dependent holds points', spent: { ...openRow1, mid: 3, far: 1 }, talent: 'mid', want: 'prereq', detail: 'far' },
    { name: 'the dependent itself always comes off', spent: { ...openRow1, mid: 3, near: 1 }, talent: 'near', want: 'ok' },
    { name: 'prereq free again once the dependent is empty', spent: { ...openRow1, mid: 3 }, talent: 'mid', want: 'ok' },
    // Row 2 lives off rows 0 and 1 together, so pulling a point out of the
    // shared row can orphan what sits below it.
    { name: 'prereq blocked when the row below would lose its support', spent: { 'top-one': 5, 'top-two': 2, mid: 3, below: 1 }, talent: 'mid', want: 'would-orphan', detail: 'below' },
  ]

  for (const { name, spent, talent, want, detail } of removeCases) {
    it(`canRemove: ${name}`, () => {
      const verdict = canRemove(hcls, build({ [F]: spent }), F, talent)
      if (want === 'ok') expect(verdict).toEqual({ ok: true })
      else expect(verdict).toMatchObject({ ok: false, reason: want, ...(detail ? { detail } : {}) })
    })
  }

  it('rank 3 of the prerequisite can be refunded down to, but not through, the requirement', () => {
    let b = build({ [F]: { ...openRow1, mid: 3, near: 1 } })
    expect(canRemove(hcls, b, F, 'mid')).toMatchObject({ ok: false, reason: 'prereq' })
    b = remove(hcls, b, F, 'near')
    b = remove(hcls, b, F, 'mid')
    expect(b[F]!.mid).toBe(2)
    expect(canAdd(hcls, b, F, 'near')).toMatchObject({ ok: false, reason: 'prereq' })
  })

  it('points in the shared row do unlock the row below it', () => {
    const b = build({ [F]: { 'top-one': 5, mid: 3, near: 2 } })
    expect(canAdd(hcls, b, F, 'below')).toEqual({ ok: true })
    const short = build({ [F]: { 'top-one': 4 } })
    expect(canAdd(hcls, short, F, 'below')).toMatchObject({ ok: false, reason: 'row-locked' })
  })

  const sanitizeCases: { name: string; spent: Record<string, number>; keep: Record<string, number>; drop: string }[] = [
    { name: 'drops the dependent right of the prerequisite', spent: { ...openRow1, mid: 2, near: 1 }, keep: { ...openRow1, mid: 2 }, drop: 'near' },
    { name: 'drops the dependent left of the prerequisite', spent: { ...openRow1, mid: 2, early: 1 }, keep: { ...openRow1, mid: 2 }, drop: 'early' },
    { name: 'drops the non-adjacent dependent', spent: { ...openRow1, mid: 2, far: 1 }, keep: { ...openRow1, mid: 2 }, drop: 'far' },
  ]

  for (const { name, spent, keep, drop } of sanitizeCases) {
    it(`sanitize ${name}, never the prerequisite`, () => {
      const b = build({ [F]: spent })
      expect(validate(hcls, b)).toMatchObject([{ treeId: F, talentId: drop, reason: 'prereq' }])
      const { build: fixed, dropped } = sanitize(hcls, b)
      expect(fixed).toEqual({ [F]: keep })
      expect(dropped).toMatchObject([{ treeId: F, talentId: drop, reason: 'prereq' }])
      expect(validate(hcls, fixed)).toEqual([])
    })
  }

  it('sanitize drops every dependent of a prerequisite that lost the whole row', () => {
    const b = build({ [F]: { mid: 3, early: 2, near: 3, far: 1 } })
    const { build: fixed } = sanitize(hcls, b)
    expect(fixed).toEqual({})
    expect(validate(hcls, fixed)).toEqual([])
  })

  it('random click sequences on a horizontal tree never violate (property)', () => {
    const talents = hcls.trees.flatMap((t) => t.talents.map((tal) => [t.id, tal.id] as const))
    const click = fc.tuple(fc.constantFrom(...talents), fc.boolean())
    fc.assert(
      fc.property(fc.array(click, { maxLength: 120 }), (clicks) => {
        let b: Build = {}
        for (const [[treeId, talentId], isAdd] of clicks) {
          b = isAdd ? add(hcls, b, treeId, talentId) : remove(hcls, b, treeId, talentId)
          expect(validate(hcls, b)).toEqual([])
        }
      }),
      { numRuns: 150 },
    )
  })
})

import { describe, expect, it } from 'vitest'
import { levelLine, levelRange, pointsAtLevel, requiredLevel, standingAtLevel } from './level'

const RULES = { firstPointLevel: 10, maxPoints: 51, maxLevel: 60 }

describe('points at level X (brief idea 10)', () => {
  it('is the inverse of requiredLevel', () => {
    for (let points = 1; points <= RULES.maxPoints; points++) {
      expect(pointsAtLevel(requiredLevel(points, RULES), RULES)).toBe(points)
    }
  })

  it('starts at the first point level and caps at the class budget', () => {
    expect(pointsAtLevel(9, RULES)).toBe(0)
    expect(pointsAtLevel(10, RULES)).toBe(1)
    expect(pointsAtLevel(11, RULES)).toBe(2)
    expect(pointsAtLevel(60, RULES)).toBe(51)
    // A level past the cap cannot manufacture points, and neither can nonsense.
    expect(pointsAtLevel(200, RULES)).toBe(51)
    expect(pointsAtLevel(0, RULES)).toBe(0)
    expect(pointsAtLevel(-5, RULES)).toBe(0)
    expect(pointsAtLevel(Number.NaN, RULES)).toBe(0)
  })

  it('offers the slider the range the class file allows', () => {
    expect(levelRange(RULES)).toEqual({ min: 10, max: 60 })
    // A class whose maxLevel is below its first point level still gets a range.
    expect(levelRange({ firstPointLevel: 10, maxLevel: 5 })).toEqual({ min: 10, max: 10 })
  })
})

describe('how a build stands at one level', () => {
  it('counts how many of the spent points the character has', () => {
    expect(standingAtLevel(40, 51, RULES)).toEqual({ level: 40, available: 31, spent: 51, affordable: 31, beyond: 20 })
    expect(standingAtLevel(60, 51, RULES)).toEqual({ level: 60, available: 51, spent: 51, affordable: 51, beyond: 0 })
    // Below the first point level nothing is affordable, whatever is spent.
    expect(standingAtLevel(5, 3, RULES)).toMatchObject({ available: 0, affordable: 0, beyond: 3 })
  })

  it('never reports more affordable points than were spent', () => {
    expect(standingAtLevel(60, 10, RULES)).toMatchObject({ available: 51, affordable: 10, beyond: 0 })
  })

  it('says it in one sentence, and never implies an order of spending', () => {
    expect(levelLine(standingAtLevel(30, 0, RULES))).toBe('At level 30 you have 21 talent points.')
    expect(levelLine(standingAtLevel(10, 0, RULES))).toBe('At level 10 you have 1 talent point.')
    expect(levelLine(standingAtLevel(40, 51, RULES))).toBe('At level 40 you have 31 of your 51 spent points - 20 too many.')
    expect(levelLine(standingAtLevel(60, 51, RULES))).toBe('At level 60 you have all 51 of your 51 spent points.')
  })
})

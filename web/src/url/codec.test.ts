import { describe, expect, it } from 'vitest'
import fc from 'fast-check'
import { buildRegistry, derivedOrder, orderFor, type EncodingRegistry } from '../data/encoding'
import { makeClass, TEST_MIGRATION_V1_V2, TEST_ORDER_V1, TEST_ORDER_V2 } from '../rules/fixture'
import { add, remove, validate, type Build } from '../rules'
import { decode, encode, summarizeNotices } from './codec'
import tinkerRaw from '../../tests/fixtures/tinker.json'
import tinkerEncoding from '../../tests/fixtures/encoding/v1.json'
import { parseClass } from '../data/schema.zod'

const cls = makeClass()
const registry: EncodingRegistry = buildRegistry([TEST_ORDER_V1, TEST_ORDER_V2], [TEST_MIGRATION_V1_V2])

describe('encode', () => {
  it('writes one digit per talent, trims trailing zeros and empty trees', () => {
    expect(encode(cls, {}, registry)).toBe('')
    expect(encode(cls, { alpha: { 'a-one': 3 } }, registry)).toBe('3')
    expect(encode(cls, { alpha: { 'a-one': 5, 'b-two': 2 } }, registry)).toBe('5002')
    expect(encode(cls, { beta: { 'y-one': 1 } }, registry)).toBe('-01')
    expect(encode(cls, { alpha: { 'a-two': 1 }, beta: { 'x-one': 5 } }, registry)).toBe('01-5')
  })

  it('falls back to the class file order when the class is missing from the encoding file', () => {
    const empty = buildRegistry([], [])
    expect(orderFor(empty, cls, cls.dataVersion)).toEqual(derivedOrder(cls))
    expect(orderFor(empty, cls, 1)).toBeUndefined()
    expect(encode(cls, { alpha: { 'a-one': 2 } }, empty)).toBe('2')
  })
})

describe('decode (brief cases 13-16)', () => {
  it('13: digit > maxRank clamps to maxRank and reports', () => {
    const { build, notices } = decode(cls, '7', 2, registry)
    expect(build).toEqual({ alpha: { 'a-one': 5 } })
    expect(notices.map((n) => n.kind)).toEqual(['clamped'])
  })

  it('14: more digits than talents: extras ignored, unknown-talent reported', () => {
    const { build, notices } = decode(cls, '50000001-0-1', 2, registry)
    expect(build).toEqual({ alpha: { 'a-one': 5 } })
    expect(notices.map((n) => n.kind)).toEqual(['unknown-talent'])
  })

  it('15: unknown data version: empty build, notice unknown-version', () => {
    const { build, notices } = decode(cls, '5', 99, registry)
    expect(build).toEqual({})
    expect(notices).toMatchObject([{ kind: 'unknown-version' }])
  })

  it('16: older version with renamed id in migrations is mapped without notice', () => {
    const { build, notices } = decode(cls, '3', 1, registry)
    expect(build).toEqual({ alpha: { 'a-one': 3 } })
    expect(notices).toEqual([])
  })

  it('sanitizes rule violations and reports "adjusted"', () => {
    const { build, notices } = decode(cls, '00000-01', 2, registry)
    expect(build).toEqual({})
    expect(notices).toMatchObject([{ kind: 'adjusted' }])
  })

  it('rejects garbage strings without throwing', () => {
    expect(decode(cls, 'abc', 2, registry)).toMatchObject({ build: {}, notices: [{ kind: 'bad-string' }] })
    expect(decode(cls, '', 2, registry)).toEqual({ build: {}, notices: [] })
  })
})

describe('17: encode(decode(s)) == s for valid s (property)', () => {
  const talents = cls.trees.flatMap((t) => t.talents.map((tal) => [t.id, tal.id] as const))
  const click = fc.tuple(fc.constantFrom(...talents), fc.boolean())
  const validBuild = fc.array(click, { maxLength: 120 }).map((clicks) => {
    let b: Build = {}
    for (const [[treeId, talentId], isAdd] of clicks) {
      b = isAdd ? add(cls, b, treeId, talentId) : remove(cls, b, treeId, talentId)
    }
    return b
  })

  it('round-trips through the codec', () => {
    fc.assert(
      fc.property(validBuild, (b) => {
        expect(validate(cls, b)).toEqual([])
        const s = encode(cls, b, registry)
        const decoded = decode(cls, s, cls.dataVersion, registry)
        expect(decoded.notices).toEqual([])
        expect(decoded.build).toEqual(b)
        expect(encode(cls, decoded.build, registry)).toBe(s)
      }),
      { numRuns: 200 },
    )
  })
})

describe('tinker fixture', () => {
  const tinker = parseClass(tinkerRaw, 'tinker fixture')
  const reg = buildRegistry([tinkerEncoding], [])

  it('encodes across both pages', () => {
    const b: Build = { gadgetry: { 'improved-wrench': 3, 'steady-hands': 2 }, chemistry: { 'volatile-mixture': 1 } }
    const s = encode(tinker, b, reg)
    expect(s).toBe('32-1')
    expect(decode(tinker, s, tinker.dataVersion, reg)).toEqual({ build: b, notices: [] })
  })
})

describe('summarizeNotices (UX round two, finding 1)', () => {
  const summary = (s: string, version = 2) => summarizeNotices(decode(cls, s, version, registry).notices)

  it('says nothing when the link decoded cleanly', () => {
    expect(summarizeNotices([])).toBeUndefined()
    expect(summary('3')).toBeUndefined()
  })

  it('gives one friendly sentence for an unreadable link', () => {
    expect(summary('abc')).toMatchObject({
      kind: 'unreadable',
      message: 'This link could not be read; showing an empty build.',
    })
    expect(summary('5', 99)?.message).toBe('This link could not be read; showing an empty build.')
  })

  it('counts the points dropped and the talents capped, without ids', () => {
    const s = summary('50000001-0-1')
    expect(s?.message).toBe(
      'This link did not fit the current trees: 2 points were dropped. The build below is what fits.',
    )
    const capped = summary('7')
    expect(capped?.message).toBe(
      'This link did not fit the current trees: 1 talent capped at its Forever rank. The build below is what fits.',
    )
  })

  it('keeps ids, slugs and rule reasons in the console detail only', () => {
    const s = summary('00000-01')
    expect(s?.message).not.toMatch(/alpha|beta|prereq|row-locked|#\d/)
    expect(s?.detail.join(' ')).toMatch(/beta\/y-one/)
  })

  it('never repeats its own title inside the sentence', () => {
    for (const bad of ['abc', '7', '00000-01', '50000001-0-1', '9999999999-9999999999-9999999999']) {
      const s = summary(bad)
      expect(s).toBeDefined()
      expect(s!.message.match(/This link/g)?.length ?? 0).toBeLessThanOrEqual(1)
    }
  })
})

describe('decode never throws and never leaks ids to the player (fuzz)', () => {
  /** Shapes a pasted link actually takes: digits, dashes, and junk around them. */
  const pasted = fc.oneof(
    fc.string(),
    fc.string({ unit: fc.constantFrom('0', '1', '5', '9', '-') }),
    fc.stringMatching(/^[0-9-]{0,40}$/),
    fc.constantFrom(
      '',
      '-',
      '---',
      '5553253055532530555325305553',
      '0503--550340510553151',
      '99999999999999999999999999999999999999999999',
      'null',
      'undefined',
      '<script>alert(1)</script>',
      '%2F..%2F',
      '0'.repeat(5000),
      '9'.repeat(5000),
    ),
  )
  const version = fc.oneof(fc.integer({ min: -5, max: 5 }), fc.constantFrom(1, 2, 99, NaN, Infinity, 1.5))

  it('returns a valid build and player-safe text for any string', () => {
    fc.assert(
      fc.property(pasted, version, (s, v) => {
        const { build, notices } = decode(cls, s, v, registry)
        expect(validate(cls, build)).toEqual([])
        const sum = summarizeNotices(notices)
        if (!sum) return
        // No slugs, no encoding positions, no engineering words.
        expect(sum.message).not.toMatch(/#\d|alpha|beta|a-one|b-two|x-one|y-one|prereq|clamp|sanitiz|maxRank/i)
        expect(sum.message.endsWith('.')).toBe(true)
      }),
      { numRuns: 400 },
    )
  })

  it('re-encoding a decoded build always round-trips', () => {
    fc.assert(
      fc.property(pasted, (s) => {
        const { build } = decode(cls, s, cls.dataVersion, registry)
        const again = encode(cls, build, registry)
        expect(decode(cls, again, cls.dataVersion, registry).build).toEqual(build)
      }),
      { numRuns: 200 },
    )
  })
})

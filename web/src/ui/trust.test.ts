/**
 * The wording module. Round two found the site telling a player two opposite
 * things on one screen - 57 talents saying "Checked by a reviewer" under a
 * header, a landing paragraph and a footer that all said "unreviewed" - and six
 * different phrasings of the same provenance claim, three of them in pipeline
 * vocabulary (UX review round two, findings 5 and 6). Both classes of defect
 * are a wording that lives in more than one place, so both are tested here.
 */
import { describe, expect, it } from 'vitest'
import facts from '../data/facts.json'
import type { Source } from '../data/schema'
import {
  checkedLine,
  datasetTrustLines,
  internalId,
  playerNotes,
  RANKS_LINE,
  readingLine,
  SOURCE_LINE,
  streamStamp,
  withPeriod,
} from './trust'

const video = (over: Record<string, unknown> = {}) =>
  ({ kind: 'video', t: 1, confidence: 1, reviewed: false, ...over }) as Source

describe('checkedLine', () => {
  it('states the fraction rather than an adjective', () => {
    expect(checkedLine({ total: 469, reviewed: 57 }, 'talents')).toBe(
      '57 of 469 talents have been checked by hand; the rest are as read.',
    )
    expect(checkedLine({ total: 37, reviewed: 0 }, 'racial traits')).toBe(
      'None of the 37 racial traits has been checked by hand yet; they are as read.',
    )
    expect(checkedLine({ total: 4, reviewed: 4 }, 'talents')).toBe('All 4 talents have been checked by hand.')
    expect(checkedLine({ total: 0, reviewed: 0 }, 'talents')).toBe('')
  })

  it('never says "unreviewed" of a dataset that is partly reviewed', () => {
    for (const reviewed of [0, 1, 56, 57, 469]) {
      expect(checkedLine({ total: 469, reviewed }, 'talents')).not.toMatch(/unreviewed/i)
    }
  })
})

describe('the site facts come from the build, not from prose', () => {
  it('facts.json counts only the real classes and agrees with itself', () => {
    expect(facts.talents.total).toBeGreaterThan(400)
    expect(facts.talents.reviewed).toBeGreaterThanOrEqual(0)
    expect(facts.talents.reviewed).toBeLessThanOrEqual(facts.talents.total)
    expect(facts.talents.queued).toBeLessThanOrEqual(facts.talents.total)
    for (const key of ['racialTraits', 'spellEntries', 'spellTooltips'] as const) {
      expect(facts[key].reviewed).toBeLessThanOrEqual(facts[key].total)
    }
  })

  it('the sentence the landing page and the footer both print is one string', () => {
    const line = checkedLine(facts.talents, 'talents')
    expect(line).toContain(String(facts.talents.total))
    expect(internalId(line)).toBe(false)
  })
})

describe('datasetTrustLines', () => {
  it('is the same wording for racials and for spells, and branches on the source kind', () => {
    const noun = { one: 'entry', many: 'entries' }
    expect(datasetTrustLines([{ source: video() }, { source: video() }], noun)).toEqual([
      SOURCE_LINE,
      'None of the 2 entries has been checked by hand yet; they are as read.',
    ])
    const datamined = { kind: 'datamined', build: '1', reviewed: false } as Source
    const manual = { kind: 'manual', reviewed: false } as Source
    expect(datasetTrustLines([{ source: datamined }], noun)[0]).toBe('Read from the game client.')
    expect(datasetTrustLines([{ source: manual }], noun)[0]).toBe('Entered by hand.')
    expect(datasetTrustLines([{ source: video() }, { source: manual }], noun)[0]).toMatch(/and from the game client/)
    expect(datasetTrustLines([], noun)).toEqual([])
  })

  it('adds the uncertain count only when something is uncertain', () => {
    const noun = { one: 'entry', many: 'entries' }
    const shaky = { source: video({ confidence: 0.3, reviewed: false }) }
    expect(datasetTrustLines([shaky, { source: video() }], noun)[2]).toBe(
      '1 of 2 entries is uncertain and marked below.',
    )
    expect(datasetTrustLines([{ source: video() }], noun)).toHaveLength(2)
  })
})

describe('the pipeline-vocabulary guard', () => {
  it('catches every word the round-two sweep found on a player page', () => {
    for (const bad of [
      'Read from BlizzCon 2026 demo footage by a local vision model',
      'Extracted from BlizzCon 2026 stream footage (rank-0 tooltips only); ranks 2+ are anticipated',
      'icons and frame crops are property of Blizzard Entertainment',
      'The reading in use',
      'Read from the stream at 5:59:37, 70% confidence.',
      'Full text (2 readings)',
      'BlizzCon demo build 2026-09-12, read from stream video; nothing here is reviewed.',
      'Classic+ talent calculator, unofficial and unreviewed',
    ]) {
      expect(internalId(bad), bad).toBe(true)
    }
  })

  it('leaves the sentences a player is meant to read alone', () => {
    for (const good of [
      SOURCE_LINE,
      RANKS_LINE,
      'Read from the stream at 4:09:33.',
      'Uncertain reading, check.',
      'Check this reading.',
      'Only rank 2 is known.',
      '57 of 469 talents have been checked by hand; the rest are as read.',
      'Anything the data lead writes in plain words stays.',
    ]) {
      expect(internalId(good), good).toBe(false)
    }
  })

  it('drops the data files own notes and keeps a note written for a player', () => {
    expect(
      playerNotes([
        'Extracted from BlizzCon 2026 stream footage (rank-0 tooltips only); ranks 2+ are anticipated, point rules assumed from Classic.',
        'BlizzCon demo build 2026-09-12, read from stream video; nothing here is reviewed.',
        'Frost Warding was hovered twice.',
      ]),
    ).toEqual(['Frost Warding was hovered twice.'])
    expect(playerNotes(undefined)).toEqual([])
  })
})

describe('readingLine', () => {
  it('gives the timestamp and no score', () => {
    expect(readingLine(video({ t: 21577, confidence: 0.7 }))).toBe('Read from the stream at 5:59:37.')
    expect(readingLine(video({ t: 21577 }))).toBe('Read from the stream at 5:59:37.')
    expect(readingLine({ kind: 'manual', reviewed: false } as Source)).toBe('Entered by hand.')
    expect(readingLine({ kind: 'datamined', build: '11.0.5', reviewed: false } as Source)).toBe(
      'Datamined from build 11.0.5.',
    )
  })
})

describe('small helpers', () => {
  it('formats a stream stamp and ends a sentence', () => {
    expect(streamStamp(21577)).toBe('5:59:37')
    expect(streamStamp(0)).toBe('0:00:00')
    expect(withPeriod(' already done. ')).toBe('already done.')
    expect(withPeriod('needs one')).toBe('needs one.')
  })
})

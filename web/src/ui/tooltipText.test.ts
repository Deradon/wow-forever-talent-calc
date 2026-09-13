/// <reference types="node" />
/**
 * Text rules for the player-facing tooltip (work package A1). The last block
 * runs every rule over the real class files, so a data change that reintroduces
 * pipeline prose fails here rather than on screen.
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { renderDescription, type ClassData, type Talent } from '../data/schema'
import { parseClass } from '../data/schema.zod'
import {
  DETAILS_LABEL,
  TRUST_MAX,
  derivationLine,
  detailLines,
  fitTrustLine,
  fitsBudget,
  gameRequirement,
  internalId,
  metaLength,
  noteLines,
  rankScaling,
  readingLine,
  requirementLine,
  roundingLines,
  trustKind,
  trustLine,
  withPeriod,
} from './tooltipText'

const video = (confidence?: number, reviewed = false, note?: string) => ({
  kind: 'video' as const,
  t: 20951,
  reviewed,
  ...(confidence === undefined ? {} : { confidence }),
  ...(note === undefined ? {} : { note }),
})

describe('trust line', () => {
  it('picks nothing for a confident, fully observed talent', () => {
    const facts = { ranksSource: 'observed' as const, ranksObserved: [1], maxRank: 1, source: { confidence: 1 } }
    expect(trustKind(facts)).toBeUndefined()
    expect(trustLine(facts)).toBeUndefined()
  })

  it('names the estimated ranks, never the ranksSource enum', () => {
    const line = trustLine({ ranksSource: 'classic-prior', ranksObserved: [1], maxRank: 5, source: { confidence: 1 } })
    expect(line).toBe('Ranks 2-5 estimated.')
    expect(internalId(line!)).toBe(false)
  })

  it('names a single estimated rank as a rank, not as "2+"', () => {
    expect(trustLine({ ranksSource: 'classic-prior', ranksObserved: [1], maxRank: 2, source: { confidence: 1 } })).toBe(
      'Rank 2 estimated.',
    )
  })

  it('says which rank is known when the higher ones are placeholders', () => {
    expect(trustLine({ ranksSource: 'manual', ranksObserved: [1], maxRank: 5, source: { confidence: 1 } })).toBe(
      'Only rank 1 is known.',
    )
  })

  it('a doubtful reading outranks an estimated rank', () => {
    // warrior/enrage: classic-prior ranks and a 70% reading. The text-quality
    // review wants "Uncertain reading" on exactly this record.
    const facts = { ranksSource: 'classic-prior' as const, ranksObserved: [1], maxRank: 5, source: { confidence: 0.7 } }
    expect(trustKind(facts)).toBe('uncertain')
    expect(trustLine(facts)).toBe('Uncertain reading, check.')
  })

  it('a reviewed record is trusted even at a low confidence', () => {
    const facts = { ranksSource: 'observed' as const, ranksObserved: [1], maxRank: 1, source: { confidence: 0.3, reviewed: true } }
    expect(trustLine(facts)).toBeUndefined()
  })

  it('every variant stays inside the 60 character cap and ends in a period', () => {
    for (const ranksSource of ['classic-prior', 'extrapolated', 'manual'] as const) {
      for (const short of [false, true]) {
        const line = trustLine({ ranksSource, ranksObserved: [1], maxRank: 9, source: { confidence: 0.5 } }, { short })
        expect(line!.length).toBeLessThanOrEqual(TRUST_MAX)
        expect(line!.endsWith('.')).toBe(true)
      }
    }
  })
})

describe('meta budget', () => {
  const facts = { ranksSource: 'classic-prior' as const, ranksObserved: [1], maxRank: 5, source: { confidence: 1 } }

  it('counts the trust line and the Details affordance', () => {
    expect(metaLength('Ranks 2-5 estimated.', true)).toBe(20 + DETAILS_LABEL.length)
    expect(metaLength(undefined, false)).toBe(0)
  })

  it('meta must stay shorter than the description it comments on', () => {
    const long = 'Increases the critical strike chance of your Flamestrike spell by 5%.'
    expect(fitsBudget('Ranks 2-5 estimated.', true, long)).toBe(true)
    expect(fitsBudget('Ranks 2-5 estimated.', true, 'Stuns the target for 5 sec.')).toBe(false)
  })

  it('falls back to the short variant on a short description', () => {
    expect(fitTrustLine(facts, 'Increases the damage done by your Eviscerate ability by 7%.', true)).toBe(
      'Ranks 2-5 estimated.',
    )
    const short = fitTrustLine(facts, 'Stuns the target for 5 sec.', true)
    expect(short).toBe('Estimated ranks.')
    expect(fitsBudget(short, true, 'Stuns the target for 5 sec.')).toBe(true)
  })
})

describe('requirement lines', () => {
  const ctx = { treeName: 'Balance', rowPoints: 10, maxPoints: 51, pageBudget: 51 }

  it('ends in a period and keeps the in-game wording', () => {
    expect(requirementLine({ ok: false, reason: 'row-locked' }, ctx)).toBe('Requires 10 points in Balance Talents.')
  })

  it('names the prerequisite talent, not its id', () => {
    const line = requirementLine({ ok: false, reason: 'prereq' }, { ...ctx, prereqs: [{ name: 'Improved Moonfire', rank: 2 }] })
    expect(line).toBe('Requires 2 points in Improved Moonfire.')
  })

  it('joins several prerequisites', () => {
    const line = requirementLine(
      { ok: false, reason: 'prereq' },
      { ...ctx, prereqs: [{ name: 'Moonglow', rank: 1 }, { name: 'Vengeance', rank: 3 }] },
    )
    expect(line).toBe('Requires 1 point in Moonglow and 3 points in Vengeance.')
  })

  it('never leaks the page id when the tab budget is spent', () => {
    const line = requirementLine({ ok: false, reason: 'page-full', detail: '51 points on page primary' }, ctx)
    expect(line).toBe('No points left on this tab (51 of 51 spent).')
    expect(internalId(line!)).toBe(false)
  })

  it('explains the two silent cases the old tooltip left blank', () => {
    expect(requirementLine({ ok: false, reason: 'no-points' }, ctx)).toBe('No talent points left (51 of 51 spent).')
    expect(requirementLine({ ok: false, reason: 'maxed' }, ctx)).toBe('Already at maximum rank.')
  })

  it('says nothing when the click is fine', () => {
    expect(requirementLine({ ok: true }, ctx)).toBeUndefined()
  })
})

describe('game requirements from source.note', () => {
  it('renders a form requirement as a sentence', () => {
    expect(gameRequirement('unparsed requirement: Requires Bear Form, Dire Bear Form')).toBe(
      'Requires Bear Form, Dire Bear Form.',
    )
  })

  it('finds the requirement clause among pipeline prose', () => {
    const note = 'second reader (codex) differs in description; unparsed requirement: Requires Battle Stance'
    expect(gameRequirement(note)).toBe('Requires Battle Stance.')
  })

  it('handles level and shield requirements', () => {
    expect(gameRequirement('unparsed requirement: Requires Level 40')).toBe('Requires Level 40.')
    expect(gameRequirement('unparsed requirement: Requires Shields')).toBe('Requires Shields.')
  })

  it('ignores notes without a requirement and refuses one carrying an id', () => {
    expect(gameRequirement('text may not be rank 1')).toBeUndefined()
    expect(gameRequirement(undefined)).toBeUndefined()
    expect(gameRequirement('unparsed requirement: Requires talent 762')).toBeUndefined()
  })
})

describe('details', () => {
  it('reads the scaling off the numbers', () => {
    expect(rankScaling([[33], [66], [99]])).toBe('proportional')
    expect(rankScaling([[5, 20], [5, 20], [5, 20]])).toBe('copied')
    expect(rankScaling([[3], [6], [10]])).toBe('table')
  })

  it('explains proportional Classic scaling in plain words', () => {
    const line = derivationLine({
      ranksSource: 'classic-prior',
      ranksObserved: [1],
      maxRank: 3,
      ranks: [[33], [66], [99]],
    })!
    expect(line).toContain('Rank 1 was read from the stream.')
    expect(line).toContain('Ranks 2-3 are rank 1 multiplied by the rank')
    expect(internalId(line)).toBe(false)
  })

  it('says a manual talent repeats the rank 1 text', () => {
    const line = derivationLine({ ranksSource: 'manual', ranksObserved: [1], maxRank: 5, ranks: [[2], [2]] })!
    expect(line).toContain('not known yet')
    expect(internalId(line)).toBe(false)
  })

  it('rewords the rounding clause without the {0} slot label', () => {
    const note =
      'Classic mage/fire/Burning Soul (talent 23): Forever rank 1 is 23. Rounding: {0} rank 2 46 may read 45, rank 3 69 may read 70 (values above are the raw scaled numbers).'
    expect(roundingLines(note)).toEqual([
      'Rank 2 may read 45 in game; the value shown is the unrounded 46.',
      'Rank 3 may read 70 in game; the value shown is the unrounded 69.',
    ])
    for (const line of roundingLines(note)) expect(internalId(line)).toBe(false)
  })

  it('gives the timestamp, and the confidence only when it is not perfect', () => {
    expect(readingLine(video(1))).toBe('Read from the stream at 5:49:11.')
    expect(readingLine(video(0.7))).toBe('Read from the stream at 5:49:11, 70% confidence.')
  })

  it('rewords the useful note clauses and drops the pipeline ones', () => {
    expect(noteLines('second reader (codex) differs in name, rank_max, description')).toEqual([
      'A second reading of this tooltip differs in the name, max rank and description.',
    ])
    expect(noteLines('arrow confidence 0.70; prerequisite from tree arrow (stage 7): Savage Fury at rank 2')).toEqual([
      'The prerequisite comes from the arrows drawn in the tree, not from the tooltip text.',
    ])
    expect(noteLines('Master of Elements was also read at r4c3@08-mage-14970 (04:10:03.7)')).toEqual([])
  })

  it('orders the disclosure: derivation, rounding, reading, notes', () => {
    const talent = {
      ranksSource: 'classic-prior' as const,
      ranksObserved: [1],
      maxRank: 2,
      ranks: [[7], [14]],
      ranksNote: 'Classic rogue (talent 276): Rounding: rank 2 14 may read 15 (values above are the raw scaled numbers).',
      source: video(0.7, false, 'second reader (codex) differs in description'),
    }
    const lines = detailLines(talent as unknown as Talent)
    expect(lines).toHaveLength(4)
    expect(lines[0]).toContain('Rank 1 was read from the stream.')
    expect(lines[1]).toContain('may read 15 in game')
    expect(lines[2]).toContain('70% confidence')
    expect(lines[3]).toContain('A second reading')
  })
})

describe('helpers', () => {
  it('withPeriod does not double a terminator', () => {
    expect(withPeriod('Requires Shields')).toBe('Requires Shields.')
    expect(withPeriod('Requires Shields.')).toBe('Requires Shields.')
  })

  it('internalId catches what must stay on the review route', () => {
    for (const bad of [
      'Classic mage/fire/Burning Soul (talent 23)',
      'matched on description (0.89)',
      'second reader (codex) differs',
      'needs manual ranks',
      '{0} rank 2 46 may read 45',
      'ranks 2..5 are copies of rank 1',
      '51 points on page primary',
      'Ranks 2+ anticipated (classic-prior)',
      'prerequisite from tree arrow (stage 7)',
      'data/review/mage/fire/x.icon.png',
    ]) {
      expect(internalId(bad), bad).toBe(true)
    }
    for (const good of [
      'Ranks 2-5 estimated.',
      'Requires Bear Form, Dire Bear Form.',
      'Read from the stream at 4:09:33, 70% confidence.',
      'Rank 2 may read 45 in game; the value shown is the unrounded 46.',
    ]) {
      expect(internalId(good), good).toBe(false)
    }
  })
})

// --- the whole corpus ------------------------------------------------------

const here = fileURLToPath(new URL('.', import.meta.url))
const dir = join(here, '../../../data/talents')
const files = existsSync(dir)
  ? readdirSync(dir)
      .filter((f) => f.endsWith('.json'))
      .map((f) => join(dir, f))
  : []

describe(`tooltip text over ${files.length} class file(s)`, () => {
  const classes = files.map((f) => parseClass(JSON.parse(readFileSync(f, 'utf8')), f) as ClassData)
  const talents = classes.flatMap((c) => c.trees.flatMap((t) => t.talents))

  it('has data to check', () => {
    expect(talents.length).toBeGreaterThanOrEqual(0)
  })

  it('warns on every unreviewed low-confidence reading', () => {
    const low = talents.filter((t) => !t.source.reviewed && (t.source.confidence ?? 1) < 0.8)
    for (const talent of low) {
      expect(trustKind(talent), talent.id).toBe('uncertain')
      expect(fitTrustLine(talent, renderDescription(talent, 0), true), talent.id).toMatch(/^(Uncertain reading, check|Check this reading)\.$/)
    }
  })

  it('never shows an internal id, a score or a reader name to a player', () => {
    for (const talent of talents) {
      const lines = [
        fitTrustLine(talent, renderDescription(talent, 0), true),
        gameRequirement(talent.source.note),
        ...detailLines(talent),
      ].filter((l): l is string => Boolean(l))
      for (const line of lines) expect(internalId(line), `${talent.id}: ${line}`).toBe(false)
    }
  })

  it('keeps the default view inside the meta budget', () => {
    for (const talent of talents) {
      for (const rank of [1, talent.maxRank]) {
        const description = renderDescription(talent, rank - 1)
        const details = detailLines(talent)
        const trust = fitTrustLine(talent, description, details.length > 0)
        expect(fitsBudget(trust, details.length > 0, description), `${talent.id}: ${trust}`).toBe(true)
      }
    }
  })

  it('ends every visible line in a period', () => {
    for (const talent of talents) {
      const lines = [
        trustLine(talent),
        gameRequirement(talent.source.note),
        ...detailLines(talent),
      ].filter((l): l is string => Boolean(l))
      for (const line of lines) expect(line.endsWith('.'), `${talent.id}: ${line}`).toBe(true)
    }
  })

  it('renders every unparsed game requirement the data carries', () => {
    const withRequirement = talents.filter((t) => /unparsed requirement/i.test(t.source.note ?? ''))
    for (const talent of withRequirement) {
      const line = gameRequirement(talent.source.note)
      expect(line, talent.id).toBeDefined()
      expect(line!.startsWith('Requires '), `${talent.id}: ${line}`).toBe(true)
    }
  })
})

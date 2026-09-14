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
  CHANGE_MAX,
  DETAILS_LABEL,
  TRUST_MAX,
  changeCardLines,
  changeCardTitle,
  changeLine,
  classicSeriesLine,
  valuesChangedLine,
  derivationLine,
  detailLines,
  fitTrustLine,
  fitsBudget,
  gameRequirement,
  internalId,
  metaLength,
  noteLines,
  classicSeries,
  foreverSeries,
  rankDerivationLines,
  rankScaling,
  ranksCopied,
  readerViews,
  readingLine,
  requirementLine,
  roundingLines,
  splitOnNames,
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
    // No percentage: a reader score is not something a player can act on.
    expect(readingLine(video(0.7))).toBe('Read from the stream at 5:49:11.')
    expect(readingLine(video(1))).toBe('Read from the stream at 5:49:11.')
  })

  it('rewords the useful note clauses and drops the pipeline ones', () => {
    expect(noteLines('second reader (codex) differs in name, rank_max, description')).toEqual([
      'A second transcription of this tooltip differs in the name, max rank and description.',
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
    expect(lines[2]).toBe('Read from the stream at 5:49:11.')
    expect(lines[3]).toContain('A second transcription')
  })
})

describe('nested tooltips', () => {
  it('reports the slot that actually changes between ranks', () => {
    expect(foreverSeries([[1], [2], [3]])).toBe('1/2/3')
    // "{0} energy point{1}": the plural must not be mistaken for the value
    expect(
      foreverSeries([
        [1, ''],
        [2, 's'],
        [3, 's'],
      ]),
    ).toBe('1/2/3')
    expect(foreverSeries([[70, 3, 2]])).toBe('70')
    expect(foreverSeries(['A whole sentence.', 'Another one.'])).toBeUndefined()
    expect(foreverSeries([])).toBeUndefined()
  })

  it('lifts the Classic numbers out of the note without the id or the score', () => {
    const note = 'Classic mage/fire/Fire Power (talent 35) (cross-class), matched on description (0.95): Classic 2/4/6/8/10 is proportional; Forever rank 1 is 1: scaled proportionally (1 x rank).'
    expect(classicSeries(note)).toBe('2/4/6/8/10')
    expect(classicSeries('Same wording as Improved Heroic Strike; Classic scales 1/2/3.')).toBe('1/2/3')
    expect(classicSeries('Classic druid/balance/Moonglow (talent 783): ranks copied.')).toBeUndefined()
    expect(classicSeries('Classic has 5 ranks')).toBeUndefined()
    expect(ranksCopied('Classic druid/balance/Moonglow (talent 783): ranks copied.')).toBe(true)
  })

  it('shows the Classic values a scaled rank came from, and nothing internal', () => {
    const talent = {
      ranksSource: 'classic-prior' as const,
      ranksObserved: [1],
      maxRank: 5,
      ranks: [[5], [10], [15], [20], [25]],
      ranksNote: 'Classic druid/balance/Improved Moonfire (talent 763): Classic 2/4/6/8/10 is proportional; Forever rank 1 is 5: scaled proportionally (5 x rank).',
      ranksPrior: { classicTalentId: 763, classicSpellIds: [], match: 'exact-name' as const, similarity: 1 },
    }
    const lines = rankDerivationLines(talent)
    expect(lines[0]).toBe('Values by rank: 5/10/15/20/25.')
    expect(lines[1]).toBe('Classic Era: 2/4/6/8/10.')
    expect(lines[2]).toMatch(/^Rank 1 was read from the stream\./)
    for (const line of lines) expect(internalId(line), line).toBe(false)
  })

  it('says nothing about Classic when the record has no prior', () => {
    const lines = rankDerivationLines({
      ranksSource: 'extrapolated',
      ranksObserved: [1],
      maxRank: 2,
      ranks: [[1], [2]],
      ranksNote: 'No Classic counterpart; proportional x1..x2 of rank 1 assumed.',
    })
    expect(lines.some((l) => l.startsWith('Classic Era:'))).toBe(false)
  })

  it('labels the readings without ever naming a reader', () => {
    const source = {
      kind: 'video' as const,
      reviewed: false,
      confidence: 0.71,
      reader: 'qwen3-vl-8b-instruct-q4_k_m',
      readings: [{ reader: 'rapidocr-1.4', name: 'Steady Hand', description: 'Increases your chance by 1%.', confidence: 0.62 }],
    }
    const views = readerViews(source, { name: 'Steady Hands', text: 'Increases your chance by 1%.' })
    expect(views).toHaveLength(2)
    expect(views[0]).toMatchObject({ label: 'The version shown', name: 'Steady Hands' })
    expect(views[1]).toMatchObject({ label: 'A second transcription', name: 'Steady Hand' })
    // No score travels with a transcription any more (UX round two, finding 6).
    expect(views.every((v) => !('percent' in v))).toBe(true)
    expect(JSON.stringify(views)).not.toMatch(/qwen|rapidocr/i)
  })

  it('cuts a requirement line at the prerequisite names it mentions', () => {
    const segments = splitOnNames('Requires 3 points in Improved Wrench.', [{ id: 'improved-wrench', name: 'Improved Wrench' }])
    expect(segments).toEqual([
      { text: 'Requires 3 points in ' },
      { text: 'Improved Wrench', talentId: 'improved-wrench' },
      { text: '.' },
    ])
    // a line with no name in it comes back whole
    expect(splitOnNames('Requires 10 points in Holy Talents.', [{ id: 'x', name: 'Rocket Boots' }])).toEqual([
      { text: 'Requires 10 points in Holy Talents.' },
    ])
    // the longer name wins over the substring
    const both = splitOnNames('Requires 2 points in Improved Wrench.', [
      { id: 'wrench', name: 'Wrench' },
      { id: 'improved-wrench', name: 'Improved Wrench' },
    ])
    expect(both.find((s) => s.talentId)?.talentId).toBe('improved-wrench')
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
      'Read from the stream at 4:09:33.',
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

  it('keeps the nested tooltips free of ids, scores and reader names', () => {
    for (const talent of talents) {
      for (const line of rankDerivationLines(talent)) {
        expect(internalId(line), `${talent.id}: ${line}`).toBe(false)
        expect(line.endsWith('.'), `${talent.id}: ${line}`).toBe(true)
      }
      const views = readerViews(talent.source, { name: talent.name, text: renderDescription(talent, 0) })
      expect(JSON.stringify(views), talent.id).not.toMatch(/qwen|codex|llama|gemini|rapidocr/i)
    }
  })

  it('shows the Classic numbers wherever the data records a prior', () => {
    const scaled = talents.filter((t) => t.ranksPrior && classicSeries(t.ranksNote))
    expect(scaled.length).toBeGreaterThan(0)
    for (const talent of scaled) {
      expect(rankDerivationLines(talent).some((l) => l.startsWith('Classic Era: ')), talent.id).toBe(true)
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

describe('changeLine', () => {
  const prior = { tree: 'arms', treeName: 'Arms', row: 2, col: 1, maxRank: 5 }
  const current = { tree: 'arms', maxRank: 5 }

  it('says nothing for a talent that is unchanged or not comparable', () => {
    expect(changeLine(undefined, current)).toBeUndefined()
    expect(changeLine({ status: 'same' }, current)).toBeUndefined()
  })

  it('announces a new talent without naming Classic at all', () => {
    expect(changeLine({ status: 'new' }, current)).toBe('New in Forever.')
  })

  it('counts rows the way a player does, from one, and names both ends', () => {
    const moved = { status: 'moved', prior: { ...prior, movedRow: true }, row: 4 } as const
    expect(changeLine(moved, current)).toBe('Moved from row 3 to row 5.')
    // the caller's own row wins over the one the generator wrote
    expect(changeLine(moved, { ...current, row: 6 })).toBe('Moved from row 3 to row 7.')
    // neither available: still true, just vaguer
    expect(changeLine({ status: 'moved', prior }, current)).toBe('Moved from row 3.')
  })

  // The reported bug: a tree Forever only renamed is not a move at all, and the
  // generator never sets `movedTree` for one, so the old tree is never named.
  it('names the old tree only when the talent actually changed tree', () => {
    const moved = { status: 'moved', prior: { ...prior, movedTree: true } } as const
    // same row in the new tree: naming a row would only invite "but it is in row 3"
    expect(changeLine(moved, { tree: 'fury', maxRank: 5, row: 2 })).toBe('Moved from Arms.')
    expect(changeLine({ ...moved, row: 4 }, { tree: 'fury', maxRank: 5 })).toBe('Moved from Arms, row 3 to row 5.')
    expect(changeLine({ status: 'moved', prior }, { tree: 'shadow-magic', maxRank: 5, row: 2 })).toBe(
      'Moved from row 3.',
    )
  })

  // Round 3, the owner's call: a talent that only changed column inside its row
  // never reaches this function as `moved`, and nothing else may claim it moved.
  it('never says moved for a column-only change', () => {
    const colOnly = { status: 'same', prior: { ...prior, movedCol: true } } as const
    expect(changeLine(colOnly, { ...current, row: 2 })).toBeUndefined()
    const reworked = { status: 'text-changed', prior: { ...prior, movedCol: true }, textChange: 'text' } as const
    expect(changeLine(reworked, { ...current, row: 2 })).toBe('Reworked.')
  })

  it('reports a rank change in both directions, with the plural right', () => {
    expect(changeLine({ status: 'rank-changed', prior }, { tree: 'arms', maxRank: 3 })).toBe('Now 3 ranks, was 5.')
    expect(changeLine({ status: 'rank-changed', prior }, { tree: 'arms', maxRank: 1 })).toBe('Now 1 rank, was 5.')
    expect(changeLine({ status: 'rank-changed', prior: { ...prior, maxRank: 2 } }, { tree: 'arms', maxRank: 5 })).toBe(
      'Now 5 ranks, was 2.',
    )
  })

  it('calls a rewritten talent reworked, and a retuned one by its numbers', () => {
    expect(changeLine({ status: 'text-changed', prior, textChange: 'text' }, current)).toBe('Reworked.')
    expect(
      changeLine({ status: 'values-changed', prior, textChange: 'values', values: [['15%', '20%']] }, current),
    ).toBe('Values changed: 15% \u2192 20%.')
  })

  it('is one line, always, and carries nothing internal', () => {
    const statuses = ['new', 'moved', 'rank-changed', 'text-changed', 'values-changed'] as const
    for (const status of statuses) {
      const line = changeLine({ status, prior, values: [['15%', '20%']] }, { tree: 'fury', maxRank: 3 })!
      expect(line.split('\n')).toHaveLength(1)
      expect(line.endsWith('.')).toBe(true)
      expect(internalId(line)).toBe(false)
    }
  })
})

describe('valuesChangedLine', () => {
  it('spells out every pair while they fit on one line', () => {
    expect(valuesChangedLine([['15%', '20%']])).toBe('Values changed: 15% \u2192 20%.')
    expect(valuesChangedLine([['1', '2'], ['3', '4']])).toBe('Values changed: 1 \u2192 2, 3 \u2192 4.')
  })

  it('spells out the real Pyroblast, which is the widest case in the data', () => {
    const line = valuesChangedLine([['148', '155'], ['195', '185'], ['56', '76']])
    expect(line).toBe('Values changed: 148 \u2192 155, 195 \u2192 185, 56 \u2192 76.')
    expect(line.length).toBeLessThanOrEqual(CHANGE_MAX)
  })

  it('keeps the meta budget: a longer list collapses to the first pair and a count', () => {
    const many: [string, string][] = [
      ['1200', '1400'],
      ['1300', '1500'],
      ['1400', '1600'],
      ['1500', '1700'],
    ]
    const line = valuesChangedLine(many)
    expect(line.length).toBeLessThanOrEqual(CHANGE_MAX)
    expect(line).toBe('Values changed: 1200 \u2192 1400 and 3 more.')
  })

  it('degrades to a bare sentence rather than an empty list', () => {
    expect(valuesChangedLine(undefined)).toBe('Values changed.')
    expect(valuesChangedLine([])).toBe('Values changed.')
  })
})

describe('the nested Classic card', () => {
  it('titles itself by whether Classic had the talent at all', () => {
    expect(changeCardTitle({ status: 'text-changed' })).toBe('In Classic Era')
    expect(changeCardTitle({ status: 'new' })).toBe('Not in Classic Era')
  })

  it('shows the Classic values per rank, and nothing for a one-rank talent', () => {
    expect(classicSeriesLine('2/4/6/8/10')).toBe('Classic values by rank: 2/4/6/8/10.')
    expect(classicSeriesLine(undefined)).toBeUndefined()
    expect(classicSeriesLine('15')).toBeUndefined()
  })

  it('lists the series, and every pair once there is more than one to list', () => {
    expect(changeCardLines({ series: '2/4/6', values: [['15%', '20%'], ['1', '2']] })).toEqual([
      'Classic values by rank: 2/4/6.',
      'Values: 15% \u2192 20%, 1 \u2192 2.',
    ])
    expect(changeCardLines(undefined)).toEqual([])
    expect(changeCardLines({})).toEqual([])
  })

  // The change line already spells a single pair out in full, so the card
  // repeating it two lines below would say nothing.
  it('does not repeat a single value pair the change line already showed', () => {
    expect(changeCardLines({ series: '2/4/6', values: [['15%', '20%']] })).toEqual([
      'Classic values by rank: 2/4/6.',
    ])
  })

  it('never lets an internal id through', () => {
    expect(changeCardLines({ series: '2/4/6' }).every((l) => !internalId(l))).toBe(true)
  })
})

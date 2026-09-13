/// <reference types="node" />
/**
 * The rules of `#/spells`, tested against the real files rather than against a
 * fixture: the page's whole job is to describe a coverage record honestly, and
 * a hand-written fixture would let the honest wording drift away from the data
 * it is supposed to describe.
 *
 * `docs/handover/2026-09-13-spells-data.md` section 5 numbers the rules; the
 * cases below name the numbers they cover.
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import spellsIndexJson from '../data/spells-index.json'
import { parseSpells } from '../data/spells.zod'
import type { Spell, SpellData, SpellTooltip } from '../data/schema.spells'
import {
  absentLine,
  cardCountLine,
  cardGapLine,
  coverageLine,
  hasText,
  initials,
  isNew,
  kindLabel,
  levelLine,
  NEW_CAVEAT,
  overviewCards,
  playerNotes,
  rankLabel,
  ranksLine,
  SEARCH_GROUP,
  spellGroups,
  spellTrustLine,
  spellTrustLines,
  tooltipFacts,
  tooltipRankLine,
  tooltipReadLine,
  type SpellsIndex,
} from './spellsModel'

const here = fileURLToPath(new URL('.', import.meta.url))
const dir = join(here, '../../../data/spells')
const index = spellsIndexJson as SpellsIndex

function load(id: string): SpellData {
  return parseSpells(JSON.parse(readFileSync(join(dir, `${id}.json`), 'utf8')), id)
}

const druid = load('druid')
const hunter = load('hunter')
const warlock = load('warlock')
const paladin = load('paladin')

/** Every spell of every class, for the corpus-wide assertions. */
const all: Spell[] = index.classes.flatMap((c) => load(c.id).spells)

describe('the overview', () => {
  it('has one card per class with a spellbook, in class order', () => {
    const cards = overviewCards(index)
    expect(cards).toHaveLength(8)
    expect(cards.map((c) => c.className)).toEqual([...cards.map((c) => c.className)].sort())
    expect(cards.map((c) => c.id)).not.toContain('priest')
    expect(cards.find((c) => c.id === 'shaman')!.href).toBe('#/spells/shaman')
  })

  it('counts entries and full texts, and says "none" rather than "0"', () => {
    const cards = overviewCards(index)
    expect(cardCountLine(cards.find((c) => c.id === 'druid')!)).toBe('41 entries seen, 27 with full text')
    expect(cardCountLine(cards.find((c) => c.id === 'warlock')!)).toBe('10 entries seen, none with full text')
    expect(cardCountLine({ entries: 1, withText: 1 })).toBe('1 entry seen, 1 with full text')
  })

  it('names the pages nobody opened, and says nothing when they all were', () => {
    const cards = overviewCards(index)
    expect(cardGapLine(cards.find((c) => c.id === 'rogue')!)).toBe('Assassination, Combat and Subtlety never opened')
    expect(cardGapLine(cards.find((c) => c.id === 'druid')!)).toBe('General never opened')
    expect(cardGapLine(cards.find((c) => c.id === 'hunter')!)).toBeUndefined()
  })

  it('says in one line that priest was never on screen', () => {
    expect(absentLine(index)).toBe('Priest never appeared in the footage, so there is no priest page.')
    expect(absentLine({ ...index, absent: [] })).toBeUndefined()
    expect(
      absentLine({
        ...index,
        absent: [
          { id: 'priest', className: 'Priest' },
          { id: 'mage', className: 'Mage' },
        ],
      }),
    ).toBe('Priest and Mage never appeared in the footage, so they have no page here.')
  })
})

describe('the coverage line (rule 1)', () => {
  it('names the tabs that were read and the pages that were not', () => {
    expect(coverageLine(druid)).toBe(
      'Spells seen on stream: 41 entries across Balance, Feral Combat, Restoration; 27 with full text. The General page was not shown.',
    )
  })

  it('drops the second sentence when every tab was opened', () => {
    expect(coverageLine(hunter)).toBe(
      'Spells seen on stream: 63 entries across General, Beast Mastery, Marksmanship, Pet, Survival; 36 with full text.',
    )
  })

  it('lists several missing pages, and handles a class with one tab and no text', () => {
    expect(coverageLine(warlock)).toBe(
      'Spells seen on stream: 10 entries on the General page; none with full text. The Affliction, Demonology and Destruction pages were not shown.',
    )
  })

  it('states the level bound and what a rank means', () => {
    expect(levelLine(druid)).toBe('The character was level 38, so nothing learned later is here.')
    expect(ranksLine(druid)).toBe("A rank is the one the book showed, not the spell's full range.")
    expect(ranksLine(hunter)).toBe('The book was showing every rank, so a row can list several.')
  })
})

describe('grouping (rules 5 and 8)', () => {
  it('groups by tab in spellbook order and keeps the file order inside', () => {
    const groups = spellGroups(druid)
    expect(groups.map((g) => g.name)).toEqual(['Balance', 'Feral Combat', 'Restoration'])
    const balance = groups[0]!.spells.map((s) => s.name)
    expect(balance).toEqual([...balance].sort((a, b) => a.localeCompare(b)))
    expect(groups.reduce((n, g) => n + g.spells.length, 0)).toBe(druid.spells.length)
  })

  it('puts the rows that were only seen in a search in their own group, last', () => {
    const groups = spellGroups(paladin)
    const last = groups[groups.length - 1]!
    expect(last.id).toBe(SEARCH_GROUP)
    expect(last.name).toBe('Seen only in a search')
    expect(last.spells.map((s) => s.id)).toContain('blessing-of-might')
    expect(last.spells.every((s) => s.tab === undefined)).toBe(true)
  })

  it('drops a tab that was opened and turned out to be empty', () => {
    const empty: SpellData = { ...druid, spells: druid.spells.filter((s) => s.tab !== 'balance') }
    expect(spellGroups(empty).map((g) => g.id)).toEqual(['feral-combat', 'restoration'])
  })
})

describe('a row', () => {
  it('lists the ranks that were on screen and never writes a range (rule 3)', () => {
    const blessing = paladin.spells.find((s) => s.id === 'blessing-of-might')!
    expect(blessing.ranksSeen).toEqual([1, 2, 3, 4])
    expect(rankLabel(blessing)).toBe('Ranks 1, 2, 3, 4')
    expect(rankLabel({ ...blessing, ranksSeen: [4] })).toBe('Rank 4')
    expect(rankLabel({ ...blessing, ranksSeen: undefined })).toBeUndefined()
    for (const spell of all) expect(rankLabel(spell) ?? '').not.toMatch(/\d-\d/)
  })

  it('marks a name the Classic list does not have, and nothing else', () => {
    const news = all.filter(isNew)
    expect(news).toHaveLength(16)
    expect(news.map((s) => s.name)).toContain('Holy Strike')
    expect(news.every((s) => (s.tags ?? []).includes('new'))).toBe(true)
    expect(all.filter((s) => s.classic.status === 'changed')).toHaveLength(0)
  })

  it('says what kind of entry it is, except for a plain active spell', () => {
    expect(kindLabel('active')).toBeUndefined()
    expect(kindLabel('passive')).toBe('Passive')
    expect(kindLabel('racial')).toBe('Racial')
    expect(kindLabel('racial-passive')).toBe('Racial, passive')
  })

  it('falls back to initials when a row has no icon crop', () => {
    expect(initials('Call of the Ancestors')).toBe('CO')
    expect(initials('Shapeshift')).toBe('Sh')
  })

  it('knows which rows have a full text at all', () => {
    expect(all.filter(hasText)).toHaveLength(108)
    expect(hasText({ ...all[0]!, tooltips: undefined })).toBe(false)
  })
})

describe('a full text', () => {
  const withRank = all.find((s) => (s.tooltips ?? []).some((t) => t.rank !== undefined))!
  const tooltip = (s: Spell): SpellTooltip => s.tooltips![0]!

  it('renders the tooltip header as the game prints it', () => {
    const stoneclaw = load('shaman').spells.find((s) => (s.tooltips ?? []).some((t) => t.tools))
    const facts = tooltipFacts(tooltip(stoneclaw ?? withRank))
    expect(facts.map((f) => f.label)).toEqual([...new Set(facts.map((f) => f.label))])
    expect(facts.every((f) => f.value.length > 0)).toBe(true)
  })

  it('never lets an unanchored tooltip read as rank 1 (rule 4)', () => {
    expect(tooltipRankLine({ description: 'x', rank: 4, source: { kind: 'video', reviewed: false } })).toBe(
      'Rank 4, as the row next to it read.',
    )
    expect(tooltipRankLine({ description: 'x', source: { kind: 'video', reviewed: false } })).toBe(
      'One rank; which one was not on screen.',
    )
  })

  it('says when it was read, with no reader name and no "100%"', () => {
    const line = tooltipReadLine(tooltip(withRank))!
    expect(line).toMatch(/^Read from the stream at \d:\d\d:\d\d/)
    expect(line).not.toMatch(/100%|Qwen|confidence 1/)
  })
})

describe('trust', () => {
  it('states the source once for the page, and counts the shaky readings', () => {
    expect(spellTrustLines(druid.spells)).toEqual([
      'Read from BlizzCon 2026 footage; not yet reviewed.',
      '1 of 41 entries is uncertain and marked below.',
    ])
    expect(spellTrustLines(hunter.spells)).toEqual(['Read from BlizzCon 2026 footage; not yet reviewed.'])
    expect(spellTrustLines([])).toEqual([])
  })

  it("uses the talent tooltip's own words on a shaky row, and nothing on a firm one", () => {
    const shaky = all.filter((s) => spellTrustLine(s) !== undefined)
    expect(shaky).toHaveLength(10)
    expect(spellTrustLine(shaky[0]!)).toBe('Check this reading.')
    const firm = all.find((s) => s.source.confidence === 1)!
    expect(spellTrustLine(firm)).toBeUndefined()
  })

  it('states the New caveat once, in player words', () => {
    expect(NEW_CAVEAT).toMatch(/written from memory/)
    expect(NEW_CAVEAT).not.toMatch(/prior|baseline|\.json/i)
  })

  it('keeps the notes a player can use and drops the ones written for the pipeline', () => {
    for (const cls of index.classes) {
      const notes = playerNotes(load(cls.id).notes)
      // Today exactly one note per class is written in player words.
      expect(notes.length, `${cls.id} kept too much`).toBe(1)
      for (const note of notes) {
        expect(note, `${cls.id}: ${note}`).not.toMatch(
          /pipeline|\.py|\.json|coverage\.|ranksSeen|source note|crop|VLM|reader|confidence|codex|stage \d/i,
        )
      }
    }
    expect(playerNotes(undefined)).toEqual([])
    expect(playerNotes(['Anything the data lead writes in plain words stays.'])).toHaveLength(1)
  })
})

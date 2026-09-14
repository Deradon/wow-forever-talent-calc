/// <reference types="node" />
/**
 * The rules of `#/spells`, tested against synthetic spellbooks.
 *
 * These cases used to read the real files in `data/spells/`, on the argument
 * that the page's whole job is to describe a coverage record honestly and a
 * fixture would let the wording drift away from the data. That argument was
 * wrong about the cost: the sentences under test are rules about *shapes* -
 * one tab or several, a gap or none, an opened tab that turned out empty - and
 * pinning them to whichever shapes `data/spells/` happens to hold today means
 * every extraction round breaks tests that have nothing to do with the round.
 * It did, when the corpus grew to 410 rows and every class gained the tabs it
 * was missing: six cases failed while the sentences they guard were fine.
 *
 * So the wording cases build the shape they need, and the corpus keeps exactly
 * one case - the smoke test at the bottom - which asserts structure only
 * (the files parse through the Zod mirror, every filed entry sits in a tab that
 * coverage admits was seen) and never a count.
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
import type { Spell, SpellData, SpellSource, SpellTooltip } from '../data/schema.spells'
import { needsReview } from './trust'
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
  type IndexClass,
  type SpellsIndex,
} from './spellsModel'

// --- fixtures --------------------------------------------------------------
//
// Small synthetic spellbooks. They go through `parseSpells`, so a fixture that
// stopped being a legal spell file fails here rather than testing a shape the
// app can never receive.

function source(over: Partial<SpellSource> = {}): SpellSource {
  return { kind: 'video', video: 'BC26', t: 12345, confidence: 1, reviewed: false, ...over }
}

function spell(id: string, over: Partial<Spell> = {}): Spell {
  return {
    id,
    name: id.replace(/(^|-)([a-z])/g, (_, sep: string, c: string) => `${sep ? ' ' : ''}${c.toUpperCase()}`),
    kind: 'active',
    classic: { status: 'unknown' },
    source: source(),
    ...over,
  }
}

function tooltip(over: Partial<SpellTooltip> = {}): SpellTooltip {
  return { description: 'Does a thing.', source: source(), ...over }
}

/**
 * A spellbook file. `tabs` is given as `[id, order]` pairs so a case can put a
 * tab out of file order and still say what order the spellbook shows it in;
 * `coverage` is filled in from the tabs unless a case overrides it.
 */
function book(over: {
  tabs?: [string, number][]
  tabsMissing?: string[]
  spells?: Spell[]
  observedLevel?: number
  showAllSpellRanks?: SpellData['coverage']['showAllSpellRanks']
  notes?: string[]
}): SpellData {
  const tabs = (over.tabs ?? []).map(([id, order]) => ({
    id,
    name: id.replace(/(^|-)([a-z])/g, (_, sep: string, c: string) => `${sep ? ' ' : ''}${c.toUpperCase()}`),
    order,
  }))
  return parseSpells(
    {
      schemaVersion: 1,
      class: 'testclass',
      className: 'Test Class',
      dataSource: 'video',
      generatedAt: '2026-09-14T00:00:00Z',
      observedLevel: over.observedLevel ?? 38,
      tabs,
      spells: over.spells ?? [],
      coverage: {
        pagesSeen: tabs.map((t) => t.name),
        tabsSeen: tabs.map((t) => t.id),
        tabsMissing: over.tabsMissing ?? [],
        states: 1,
        entriesRead: (over.spells ?? []).length,
        tooltipsRead: (over.spells ?? []).reduce((n, s) => n + (s.tooltips ?? []).length, 0),
        tooltipsUnmatched: 0,
        showAllSpellRanks: over.showAllSpellRanks ?? 'off',
        observedLevel: over.observedLevel ?? 38,
        windows: ['03:25:40'],
      },
      complete: false,
      ...(over.notes ? { notes: over.notes } : {}),
    },
    'fixture',
  )
}

/** One row of the generated overview index. */
function indexClass(id: string, over: Partial<IndexClass> = {}): IndexClass {
  return {
    id,
    className: id.replace(/^./, (c) => c.toUpperCase()),
    observedLevel: 38,
    entries: 10,
    withText: 4,
    tooltips: 5,
    new: 1,
    searchOnly: 0,
    tabs: [{ id: 'general', name: 'General', spells: 10 }],
    tabsMissing: [],
    showAllSpellRanks: 'off',
    complete: false,
    ...over,
  }
}

function makeIndex(classes: IndexClass[], absent: SpellsIndex['absent'] = []): SpellsIndex {
  return { prior: 'classic-era', priorVerified: false, classes, absent }
}

describe('the overview', () => {
  it('has one card per class with a spellbook, in class order', () => {
    const index = makeIndex([indexClass('shaman'), indexClass('druid'), indexClass('mage')])
    const cards = overviewCards(index)
    expect(cards.map((c) => c.id)).toEqual(['druid', 'mage', 'shaman'])
    expect(cards.find((c) => c.id === 'shaman')!.href).toBe('#/spells/shaman')
    // A class with no file at all gets no card; it is named by `absentLine`.
    expect(cards.map((c) => c.id)).not.toContain('priest')
  })

  it('counts entries and full texts, and says "none" rather than "0"', () => {
    const cards = overviewCards(
      makeIndex([indexClass('druid', { entries: 40, withText: 27 }), indexClass('warlock', { entries: 10, withText: 0 })]),
    )
    expect(cardCountLine(cards.find((c) => c.id === 'druid')!)).toBe('40 entries seen, 27 with full text')
    expect(cardCountLine(cards.find((c) => c.id === 'warlock')!)).toBe('10 entries seen, none with full text')
    expect(cardCountLine({ entries: 1, withText: 1 })).toBe('1 entry seen, 1 with full text')
  })

  it('names the pages nobody opened, and says nothing when they all were', () => {
    const cards = overviewCards(
      makeIndex([
        indexClass('rogue', { tabsMissing: ['assassination', 'combat', 'subtlety'] }),
        indexClass('druid', { tabsMissing: ['general'] }),
        indexClass('hunter', { tabsMissing: [] }),
      ]),
    )
    expect(cardGapLine(cards.find((c) => c.id === 'rogue')!)).toBe('Assassination, Combat and Subtlety never opened')
    expect(cardGapLine(cards.find((c) => c.id === 'druid')!)).toBe('General never opened')
    expect(cardGapLine(cards.find((c) => c.id === 'hunter')!)).toBeUndefined()
  })

  it('says in one line which classes were never on screen', () => {
    const index = makeIndex([indexClass('druid')], [{ id: 'priest', className: 'Priest' }])
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
  it('names the tabs that were read and the page that was not', () => {
    const data = book({
      tabs: [
        ['balance', 1],
        ['feral-combat', 2],
        ['restoration', 3],
      ],
      tabsMissing: ['general'],
      spells: [
        spell('moonfire', { tab: 'balance', tooltips: [tooltip()] }),
        spell('claw', { tab: 'feral-combat' }),
        spell('healing-touch', { tab: 'restoration', tooltips: [tooltip()] }),
      ],
    })
    expect(coverageLine(data)).toBe(
      'Spells seen on stream: 3 entries across Balance, Feral Combat, Restoration; 2 with full text. The General page was not shown.',
    )
  })

  it('drops the second sentence when every tab was opened', () => {
    const data = book({
      tabs: [
        ['general', 0],
        ['beast-mastery', 1],
        ['marksmanship', 2],
      ],
      spells: [spell('aspect-of-the-hawk', { tab: 'general', tooltips: [tooltip()] }), spell('mend-pet', { tab: 'beast-mastery' })],
    })
    expect(coverageLine(data)).toBe(
      'Spells seen on stream: 2 entries across General, Beast Mastery, Marksmanship; 1 with full text.',
    )
  })

  it('lists several missing pages, and handles a class with one tab and no text', () => {
    const data = book({
      tabs: [['general', 0]],
      tabsMissing: ['affliction', 'demonology', 'destruction'],
      spells: [spell('shadow-bolt', { tab: 'general' }), spell('corruption', { tab: 'general' })],
    })
    expect(coverageLine(data)).toBe(
      'Spells seen on stream: 2 entries on the General page; none with full text. The Affliction, Demonology and Destruction pages were not shown.',
    )
  })

  it('counts one entry as an entry', () => {
    const data = book({ tabs: [['general', 0]], spells: [spell('shadow-bolt', { tab: 'general', tooltips: [tooltip()] })] })
    expect(coverageLine(data)).toBe('Spells seen on stream: 1 entry on the General page; 1 with full text.')
  })

  it('states the level bound and what a rank means', () => {
    expect(levelLine(book({ observedLevel: 38 }))).toBe('The character was level 38, so nothing learned later is here.')
    expect(ranksLine(book({ showAllSpellRanks: 'off' }))).toBe(
      "A rank is the one the book showed, not the spell's full range.",
    )
    expect(ranksLine(book({ showAllSpellRanks: 'not observed' }))).toBe(
      "A rank is the one the book showed, not the spell's full range.",
    )
    expect(ranksLine(book({ showAllSpellRanks: 'on' }))).toBe('The book was showing every rank, so a row can list several.')
  })
})

describe('grouping (rules 5 and 8)', () => {
  /** A General tab plus three trees, deliberately out of file order. */
  const druidish = book({
    tabs: [
      ['restoration', 3],
      ['general', 0],
      ['balance', 1],
      ['feral-combat', 2],
    ],
    spells: [
      spell('regrowth', { tab: 'restoration' }),
      spell('moonfire', { tab: 'balance' }),
      spell('bear-form', { tab: 'feral-combat' }),
      spell('aquatic-form', { tab: 'feral-combat' }),
      spell('healing-touch', { tab: 'restoration' }),
      spell('wrath', { tab: 'general' }),
    ],
  })

  it('groups by tab in spellbook order, General first, and keeps the file order inside', () => {
    const groups = spellGroups(druidish)
    expect(groups.map((g) => g.name)).toEqual(['General', 'Balance', 'Feral Combat', 'Restoration'])
    // Inside a group the file's own order survives - it is the page's order,
    // and re-sorting here would quietly claim the book was alphabetical.
    expect(groups.find((g) => g.id === 'feral-combat')!.spells.map((s) => s.id)).toEqual(['bear-form', 'aquatic-form'])
    expect(groups.find((g) => g.id === 'restoration')!.spells.map((s) => s.id)).toEqual(['regrowth', 'healing-touch'])
    expect(groups.reduce((n, g) => n + g.spells.length, 0)).toBe(druidish.spells.length)
  })

  it('puts the rows that were only seen in a search in their own group, last', () => {
    const data = book({
      tabs: [
        ['general', 0],
        ['holy', 1],
      ],
      spells: [
        spell('holy-light', { tab: 'holy' }),
        spell('blessing-of-might'),
        spell('seal-of-the-crusader', { tab: 'not-a-tab' }),
      ],
    })
    const groups = spellGroups(data)
    const last = groups[groups.length - 1]!
    expect(last.id).toBe(SEARCH_GROUP)
    expect(last.name).toBe('Seen only in a search')
    // A row with no tab, and a row filed under a tab the file never declared,
    // both land here rather than inventing a group.
    expect(last.spells.map((s) => s.id)).toEqual(['blessing-of-might', 'seal-of-the-crusader'])
  })

  it('drops a tab that was opened and turned out to be empty', () => {
    const empty: SpellData = { ...druidish, spells: druidish.spells.filter((s) => s.tab !== 'balance' && s.tab !== 'general') }
    expect(spellGroups(empty).map((g) => g.id)).toEqual(['feral-combat', 'restoration'])
    expect(spellGroups(book({ tabs: [['general', 0]] }))).toEqual([])
  })
})

describe('a row', () => {
  it('lists the ranks that were on screen and never writes a range (rule 3)', () => {
    const blessing = spell('blessing-of-might', { ranksSeen: [4, 1, 3, 2] })
    expect(rankLabel(blessing)).toBe('Ranks 1, 2, 3, 4')
    expect(rankLabel({ ...blessing, ranksSeen: [4] })).toBe('Rank 4')
    expect(rankLabel({ ...blessing, ranksSeen: undefined })).toBeUndefined()
    expect(rankLabel(blessing)).not.toMatch(/\d-\d/)
  })

  it('marks a name the Classic list does not have, and nothing else', () => {
    expect(isNew(spell('holy-strike', { classic: { status: 'new' } }))).toBe(true)
    expect(isNew(spell('holy-light', { classic: { status: 'unknown' } }))).toBe(false)
    expect(isNew(spell('holy-light', { classic: { status: 'same', classicName: 'Holy Light' } }))).toBe(false)
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
    expect(hasText(spell('moonfire', { tooltips: [tooltip()] }))).toBe(true)
    expect(hasText(spell('moonfire'))).toBe(false)
    expect(hasText({ ...spell('moonfire'), tooltips: [] })).toBe(false)
  })
})

describe('a full text', () => {
  it('renders the tooltip header as the game prints it', () => {
    const facts = tooltipFacts(
      tooltip({
        cost: '75 Mana',
        range: '30 yd range',
        castTime: 'Instant cast',
        cooldown: '10 sec cooldown',
        tools: 'Earth Totem',
        requires: ['Level 20', 'Melee Weapon'],
      }),
    )
    expect(facts.map((f) => f.label)).toEqual(['Cost', 'Range', 'Cast', 'Cooldown', 'Tools', 'Requires', 'Requires'])
    expect(facts.map((f) => f.value)).toEqual([
      '75 Mana',
      '30 yd range',
      'Instant cast',
      '10 sec cooldown',
      'Earth Totem',
      'Level 20',
      'Melee Weapon',
    ])
    expect(tooltipFacts(tooltip())).toEqual([])
  })

  it('never lets an unanchored tooltip read as rank 1 (rule 4)', () => {
    expect(tooltipRankLine(tooltip({ rank: 4 }))).toBe('Rank 4, as the row next to it read.')
    expect(tooltipRankLine(tooltip())).toBe('One rank; which one was not on screen.')
  })

  it('says when it was read, with no reader name and no "100%"', () => {
    const line = tooltipReadLine(tooltip({ source: source({ t: 12345, reader: 'a-reader', confidence: 1 }) }))!
    expect(line).toMatch(/^Read from the stream at \d:\d\d:\d\d/)
    expect(line).not.toMatch(/100%|Qwen|confidence 1|a-reader/)
  })
})

describe('trust', () => {
  it('states the source once for the page, and counts the shaky readings', () => {
    const spells = [
      spell('one'),
      spell('two'),
      spell('three', { source: source({ confidence: 0.5 }) }),
      spell('four', { source: source({ confidence: 0.5 }) }),
    ]
    expect(spellTrustLines(spells)).toEqual([
      'Read from BlizzCon 2026 footage.',
      'None of the 4 entries has been checked by hand yet; they are as read.',
      '2 of 4 entries are uncertain and marked below.',
    ])
    // One shaky row says "is", and a page with none drops the line entirely.
    expect(spellTrustLines(spells.slice(0, 3))[2]).toBe('1 of 3 entries is uncertain and marked below.')
    expect(spellTrustLines(spells.slice(0, 2))).toEqual([
      'Read from BlizzCon 2026 footage.',
      'None of the 2 entries has been checked by hand yet; they are as read.',
    ])
    expect(spellTrustLines([])).toEqual([])
  })

  it("uses the talent tooltip's own words on a shaky row, and nothing on a firm one", () => {
    const shaky = spell('shaky', { source: source({ confidence: 0.4 }) })
    expect(needsReview(shaky)).toBe(true)
    expect(spellTrustLine(shaky)).toBe('Check this reading.')
    expect(spellTrustLine(spell('firm', { source: source({ confidence: 1 }) }))).toBeUndefined()
    // A row somebody checked is firm however it was read.
    expect(spellTrustLine(spell('checked', { source: source({ confidence: 0.4, reviewed: true }) }))).toBeUndefined()
  })

  it('states the New caveat once, in player words', () => {
    expect(NEW_CAVEAT).toMatch(/written from memory/)
    expect(NEW_CAVEAT).not.toMatch(/prior|baseline|\.json/i)
  })

  it('keeps the notes a player can use and drops the ones written for the pipeline', () => {
    expect(playerNotes(undefined)).toEqual([])
    expect(playerNotes(['Anything the data lead writes in plain words stays.'])).toHaveLength(1)
    expect(
      playerNotes([
        'Read by Qwen at stage 11.',
        'Talent 1234 was matched to this row.',
        'The book was open at r4c3@08-mage-14970.',
        'Rank ranges are anticipated, similarity (0.62).',
        'The demo character was a level 38 tauren.',
      ]),
    ).toEqual(['The demo character was a level 38 tauren.'])
  })
})

// --- the corpus ------------------------------------------------------------

describe('the real spellbooks', () => {
  /**
   * The one case that reads `data/spells/`. Structure only: that the files the
   * overview index advertises exist, parse through the Zod mirror the app
   * parses them with, and are internally consistent - every filed entry sits in
   * a tab the coverage record admits was seen, and no tab is both seen and
   * missing. Counts, tab lists and wording belong to the fixtures above, so an
   * extraction round never fails this file.
   */
  it('parse, and file every entry under a tab coverage admits was seen', () => {
    const dir = join(fileURLToPath(new URL('.', import.meta.url)), '../../../data/spells')
    const index = spellsIndexJson as SpellsIndex
    expect(index.classes.length).toBeGreaterThan(0)

    for (const cls of index.classes) {
      const data = parseSpells(JSON.parse(readFileSync(join(dir, `${cls.id}.json`), 'utf8')), cls.id)
      const seen = new Set(data.coverage.tabsSeen)

      for (const tab of data.tabs) {
        expect(seen, `${cls.id}: tab ${tab.id} is not in tabsSeen`).toContain(tab.id)
      }
      for (const missing of data.coverage.tabsMissing) {
        expect(seen, `${cls.id}: tab ${missing} is both seen and missing`).not.toContain(missing)
      }
      for (const entry of data.spells) {
        // No tab at all is legal - rule 8's search-only rows. A tab that
        // coverage never saw is not.
        if (entry.tab !== undefined) {
          expect(seen, `${cls.id}: ${entry.id} is filed under unseen tab ${entry.tab}`).toContain(entry.tab)
        }
      }
      // Every group the page would render holds something, and together they
      // hold every entry - no row can fall out of the page.
      const groups = spellGroups(data)
      expect(groups.every((g) => g.spells.length > 0)).toBe(true)
      expect(groups.reduce((n, g) => n + g.spells.length, 0), `${cls.id}: rows lost in grouping`).toBe(data.spells.length)
    }
  })
})

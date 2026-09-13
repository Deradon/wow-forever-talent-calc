/**
 * Types for `data/spells/<class>.json`, the spellbook files.
 *
 * Hand-written mirror of `data/schema/spell.schema.json` and section 5 of
 * `docs/handover/2026-09-13-spells-data.md`, the same arrangement
 * `schema.races.ts` has for races: these types are what the UI programs
 * against, `spells.zod.ts` is the runtime mirror that parses the files, and a
 * compile-time assertion there fails `tsc -b` if the two drift apart.
 *
 * The shape to keep in mind while reading them: a file is a **coverage
 * record**, not a spell list. `tabs` holds the tabs that were opened,
 * `coverage.tabsMissing` the ones that were not, and a spell without `tab` was
 * read from a search page. Nothing here claims to be the game's full spellbook.
 */
import type { Source } from './schema'

/** A spellbook source also records which piece of the window it came from. */
export interface SpellSource extends Source {
  panel?: 'spell-list' | 'tooltip' | 'page-head'
}

export interface SpellTab {
  id: string
  name: string
  order: number
  /** Matching talent tree in `data/talents/<class>.json`, when the tab is one. */
  tree?: string
}

/**
 * One hover tooltip, verbatim. `rank` is present only when the box could be
 * tied to a list row on a page that was read (23 of 112), so its absence means
 * "one rank, which one is not known" - never "rank 1".
 */
export interface SpellTooltip {
  rank?: number
  cost?: string
  range?: string
  castTime?: string
  cooldown?: string
  tools?: string
  requires?: string[]
  description: string
  footer?: string
  source: SpellSource
}

/**
 * Name-level only. `new` means the name is missing from a Classic Era list
 * written from memory; `unknown` means the name exists there and nothing at all
 * is claimed about the text. There is no `same` and no `changed` in the data
 * today.
 */
export interface SpellClassic {
  status: 'new' | 'changed' | 'same' | 'unknown'
  classicName?: string
  classicText?: string
  note?: string
}

export interface Spell {
  id: string
  name: string
  kind: 'active' | 'passive' | 'racial' | 'racial-passive'
  /** Absent when the row was only ever seen on a search-results page. */
  tab?: string
  /**
   * The `Rank N` labels that were **on screen**, not the spell's rank range.
   * With "Show all spell ranks" off this is the single highest rank the demo
   * character knew.
   */
  ranksSeen?: number[]
  icon?: string
  iconSource?: 'classic' | 'crop' | 'datamined' | 'manual'
  iconCrop?: string
  tooltips?: SpellTooltip[]
  classic: SpellClassic
  tags?: string[]
  source: SpellSource
}

export interface SpellCoverage {
  /** Every page heading seen, tab names and search headings alike. */
  pagesSeen: string[]
  tabsSeen: string[]
  /** Tabs that were never opened. Their spells are absent, not missing. */
  tabsMissing: string[]
  states: number
  entriesRead: number
  tooltipsRead: number
  tooltipsUnmatched: number
  showAllSpellRanks: 'on' | 'off' | 'not observed'
  observedLevel: number
  /** Stream times of the page states, `HH:MM:SS`. */
  windows: string[]
}

export interface SpellData {
  schemaVersion: 1
  class: string
  className: string
  dataSource: 'video' | 'datamined' | 'mixed' | 'manual'
  generatedAt: string
  /** Level of the demo character. The lists stop here. */
  observedLevel: number
  tabs: SpellTab[]
  spells: Spell[]
  coverage: SpellCoverage
  complete: boolean
  notes?: string[]
}

/**
 * Types for `data/races/*.json` and `data/races/matrix.json`.
 *
 * Hand-written mirror of `docs/DATA-SCHEMA-RACES.md` sections 4 and 5, the same
 * arrangement `schema.ts` has for `data/talents/`: these types are what the UI
 * programs against, `races.zod.ts` is the runtime mirror that parses the files,
 * and a compile-time assertion there fails `tsc -b` if the two drift apart.
 */
import type { Source } from './schema'

export type Faction = 'alliance' | 'horde' | 'neutral'

/** `neutral` is a race shown in both columns of the picker, never a variant. */
export type VariantFaction = 'alliance' | 'horde'

export type ClassicStatus = 'new' | 'changed' | 'same' | 'unknown'

export interface RaceVariant {
  id: string
  name: string
  faction: VariantFaction
  /** This variant's own class bar, which is not the race's union. */
  classes: string[]
  lore?: string
  loreComplete?: boolean
}

/**
 * How the trait compares to Classic Era. `classicText` is a paraphrase written
 * from memory (`data/prior/classic-era/racials.json`, `verified: false`), so
 * every renderer of it has to mark it as unverified - see `racesModel.ts`.
 */
export interface RaceClassic {
  status: ClassicStatus
  classicName?: string
  classicText?: string
  note?: string
}

export interface RaceTrait {
  id: string
  name: string
  kind: 'active' | 'passive'
  /** Row position in the race box. Traits render in this order, never by name. */
  order: number
  /** Present iff the race has variants; which variants show this trait. */
  variants?: string[]
  /** Absent for a trait known only by name; `source.note` then says why. */
  description?: string
  icon?: string
  iconSource?: 'classic' | 'crop' | 'datamined' | 'manual'
  iconCrop?: string
  classic: RaceClassic
  tags?: string[]
  source: Source
}

export interface RaceData {
  schemaVersion: 1
  race: string
  raceName: string
  faction: Faction
  dataSource: 'video' | 'datamined' | 'mixed' | 'manual'
  generatedAt: string
  variants?: RaceVariant[]
  /** Union over the variants. **Empty means unknown**, never "no classes". */
  classes: string[]
  classesSource?: Source
  lore?: string
  loreComplete?: boolean
  loreSource?: Source
  traits: RaceTrait[]
  complete: boolean
  notes?: string[]
}

export interface MatrixRace {
  race: string
  raceName: string
  faction: Faction
  classes: string[]
  byVariant?: Record<string, string[]>
  /** `false` = the class bar was never read; render as unknown, not as none. */
  observed: boolean
  reportedElsewhere?: string[]
  agreement?: string
  disagreement?: string
}

export interface RaceMatrix {
  schemaVersion: 1
  dataSource: 'video' | 'datamined' | 'mixed' | 'manual'
  generatedAt: string
  /** Class-bar order, left to right. The matrix columns follow it. */
  classes: string[]
  races: MatrixRace[]
  notes?: string[]
}

/** Display name for a faction, including the both-columns case. */
export function factionName(faction: Faction): string {
  if (faction === 'alliance') return 'Alliance'
  if (faction === 'horde') return 'Horde'
  return 'Alliance and Horde'
}

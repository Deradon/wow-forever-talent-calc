/**
 * The model behind `#/changes/<class>` (brief `docs/briefs/ui-improvements.md`,
 * idea 13; a talents-only down payment on `13_changes` in
 * `docs/briefs/beyond-talents.md`).
 *
 * Pure: it takes the class file, the generated diff entries and the removed
 * list, and returns six ordered sections of rows ready to print. No DOM, no
 * React, no import of the generated JSON - `ChangesPage` supplies all three, so
 * the whole page model is testable against a fixture.
 *
 * Sections follow the generator's own precedence (worst news first), and a
 * talent appears in exactly one of them: its headline status. A `moved` talent
 * whose wording also changed says so in its detail line rather than being
 * listed twice, because a player counting "how much changed" must not be able
 * to count the same talent twice.
 */
import type { ClassData } from '../data/schema'
import type { Change, ClassicText, RemovedTalent, ValuePair } from './classicDiff'
import { changeLine, valuesChangedLine } from './tooltipText'

export type SectionId = 'new' | 'moved' | 'rank-changed' | 'text-changed' | 'values-changed' | 'gone'

export interface ChangeRow {
  id: string
  name: string
  /** Where it sits now - for `gone`, where it sat in Classic Era. */
  treeName: string
  /** 0-based, printed 1-based, the way the tier gutter counts. */
  row: number
  maxRank: number
  /** The one-line "what changed", the same sentence the tooltip prints. */
  detail?: string
  /** `values-changed`: every pair, not just the one the tooltip line fits. */
  values?: ValuePair[]
  /** True when `classic-text.json` has a word diff for this talent. */
  hasDiff: boolean
  /** Gone talents have no Forever cell and no deep link. */
  gone: boolean
  /** Lower-cased name plus detail, which is what the filter box matches. */
  haystack: string
}

export interface ChangeSection {
  id: SectionId
  title: string
  blurb: string
  rows: ChangeRow[]
}

export interface ChangesModel {
  classId: string
  className: string
  sections: ChangeSection[]
  /** Rows across all six sections. */
  total: number
}

const HEADINGS: { id: SectionId; title: string; blurb: string }[] = [
  { id: 'new', title: 'New in Forever', blurb: 'No Classic Era talent of this name in the class.' },
  {
    id: 'moved',
    title: 'Moved',
    blurb:
      'A different tree or a different row - the two things a player has to plan around. A reshuffled column inside the same row is not a move.',
  },
  { id: 'rank-changed', title: 'Rank count changed', blurb: 'Same talent, a different number of ranks to fill.' },
  {
    id: 'text-changed',
    title: 'Reworked',
    blurb: 'The wording changed beyond its numbers. Both sentences are below: dropped words struck on the Classic line, added words marked on the Forever one.',
  },
  { id: 'values-changed', title: 'Values changed', blurb: 'The same sentence with different numbers.' },
  { id: 'gone', title: 'Gone from Classic', blurb: 'Classic Era talents with no counterpart in Forever.' },
]

/**
 * One class, six sections. `changes` is the generated map (absent talent =
 * unchanged) and `removed` the generated list of Classic talents with no
 * counterpart; `hasDiff` says whether `classic-text.json` carries a word diff,
 * which the page uses to decide whether a row can be expanded at all.
 */
export function changesModel(
  cls: ClassData,
  changes: Record<string, Change>,
  removed: RemovedTalent[],
  hasDiff: (talentId: string) => boolean = () => false,
): ChangesModel {
  const rows = new Map<SectionId, ChangeRow[]>(HEADINGS.map((h) => [h.id, []]))

  for (const tree of cls.trees) {
    for (const talent of [...tree.talents].sort((a, b) => a.row - b.row || a.col - b.col)) {
      const change = changes[talent.id]
      if (!change || change.status === 'same') continue
      const bucket = rows.get(change.status as SectionId)
      if (!bucket) continue
      const detail = detailFor(change, tree.name, talent.maxRank, talent.row)
      bucket.push({
        id: talent.id,
        name: talent.name,
        treeName: tree.name,
        row: talent.row,
        maxRank: talent.maxRank,
        detail,
        values: change.status === 'values-changed' ? change.values : undefined,
        hasDiff: hasDiff(talent.id),
        gone: false,
        haystack: `${talent.name} ${tree.name} ${detail ?? ''}`.toLowerCase(),
      })
    }
  }

  const gone = rows.get('gone')!
  for (const t of [...removed].sort((a, b) => a.treeName.localeCompare(b.treeName) || a.row - b.row || a.col - b.col)) {
    const detail = `Was ${t.treeName}, row ${t.row + 1}${t.maxRank ? ` - ${ranks(t.maxRank)}` : ''}.`
    gone.push({
      id: t.id,
      name: t.name,
      treeName: t.treeName,
      row: t.row,
      maxRank: t.maxRank,
      detail,
      hasDiff: false,
      gone: true,
      haystack: `${t.name} ${t.treeName} ${detail}`.toLowerCase(),
    })
  }

  const sections = HEADINGS.map((h) => ({ ...h, rows: rows.get(h.id)! }))
  return {
    classId: cls.class,
    className: cls.className,
    sections,
    total: sections.reduce((n, s) => n + s.rows.length, 0),
  }
}

/**
 * The line under a row. The five Forever sections reuse `changeLine`, so the
 * page and the tooltip can never disagree about what changed; the position is
 * appended because a list without the cell is unreadable, and a secondary
 * description change is named rather than silently dropped.
 */
function detailFor(change: Change, treeName: string, maxRank: number, row: number): string | undefined {
  const line = changeLine(change, { tree: treeName, maxRank, row })
  const where = `${treeName}, row ${row + 1}`
  switch (change.status) {
    case 'new':
      return `${where} - ${ranks(maxRank)}.`
    case 'values-changed':
      return `${valuesChangedLine(change.values)} ${where}.`
    case 'text-changed':
      return `${where}.`
    case 'rank-changed':
      return `${line ?? ''} ${where}.`.trim()
    case 'moved':
      // A move can also have carried a rewrite or new numbers. The headline
      // stays "moved" (one row, one section), but the rest is still true.
      // The line already names both rows, so only the tree is left to say.
      return [line, alsoLine(change), `Now in ${treeName}.`].filter(Boolean).join(' ')
    default:
      return line
  }
}

function alsoLine(change: Change): string | undefined {
  if (change.textChange === 'text') return 'Also reworked.'
  if (change.textChange === 'values') return `Also: ${lower(valuesChangedLine(change.values))}`
  return undefined
}

function lower(s: string): string {
  return s.charAt(0).toLowerCase() + s.slice(1)
}

function ranks(n: number): string {
  return `${n} rank${n === 1 ? '' : 's'}`
}

/** Case-insensitive substring filter; empty query keeps everything. */
export function filterModel(model: ChangesModel, query: string): ChangesModel {
  const q = query.trim().toLowerCase()
  if (q === '') return model
  const sections = model.sections.map((s) => ({ ...s, rows: s.rows.filter((r) => r.haystack.includes(q)) }))
  return { ...model, sections, total: sections.reduce((n, s) => n + s.rows.length, 0) }
}

/** The word diff as one interleaved run, with a plain-text fallback. */
export function diffRuns(text: ClassicText | undefined): [string, string][] {
  if (!text) return []
  if (text.diff.length > 0) return text.diff.map(([op, run]) => [op, run] as [string, string])
  return text.text ? [['=', text.text]] : []
}

export interface DiffLines {
  /** The Classic Era sentence: kept words plus the ones Forever dropped. */
  classic: [string, string][]
  /** The Forever sentence: kept words plus the ones Forever added. */
  forever: [string, string][]
}

/**
 * The same ops, split into the two sentences they were made from.
 *
 * One interleaved run is unreadable at the length these descriptions run to -
 * Defiance came out as "Increases ~~the~~ all threat generated ~~by your
 * attacks by 3%~~ ~~while~~ in Defensive ~~Stance.~~ stance by an additional 5%
 * while a shield is equipped", and `#/changes/warrior` has 25 of them (UX
 * review round two, finding 7). Neither sentence can be read without mentally
 * filtering every other word, so each is given its own line and the diff
 * becomes emphasis inside it rather than the structure of it.
 *
 * Nothing is recomputed: `compactDiff` already keeps the ops, and a `-` run
 * belongs to the Classic line, a `+` run to the Forever line, a `=` run to
 * both. A talent with no diff (no Classic counterpart) yields one Forever line.
 */
export function diffLines(text: ClassicText | undefined): DiffLines {
  const runs = diffRuns(text)
  return {
    classic: runs.filter(([op]) => op !== '+'),
    forever: runs.filter(([op]) => op !== '-'),
  }
}

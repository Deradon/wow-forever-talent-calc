/**
 * Player-facing text for the talent tooltip. Pure string helpers, no React and
 * no DOM: everything here is unit tested (tooltipText.test.ts) against the real
 * class files as well as fixtures.
 *
 * The rules come from docs/reviews/2026-09-13-text-quality.md ("Proposed style
 * guide: player-facing meta text"):
 *
 * - the tooltip carries at most ONE amber trust line, chosen by
 *   confidence/ranksSource, and it is shorter than the description;
 * - derivation, rounding, confidence, timestamp and `source.note` live behind a
 *   "Details" disclosure;
 * - Classic talent ids, similarity scores, reader names, crop paths, `{0}` slot
 *   labels and the raw `ranksSource` enum never reach a player. `internalId()`
 *   is the last line of defence and is asserted over the whole corpus in tests;
 * - every visible line ends in a period, requirement lines included, and no
 *   requirement line names an internal id.
 */
import type { Rank, Source, Talent } from '../data/schema'
import type { Verdict } from '../rules'
import { highestObserved, internalId, readingLine, trustLine, withPeriod } from './trust'
import type { RankFacts, ReadFacts } from './trust'

/**
 * The trust primitives moved to `trust.ts` so that the changes list and the
 * races pages can state trust in the same words without pulling this whole
 * file in. They are re-exported here because this module is where every caller
 * and every test already looks for them.
 */
export {
  highestObserved,
  internalId,
  readingLine,
  trustKind,
  trustLine,
  withPeriod,
  type RankFacts,
  type ReadFacts,
  type TrustKind,
} from './trust'

/** Label of the disclosure that holds everything except the trust line. */
export const DETAILS_LABEL = 'Details'

/** Style-guide cap for the amber line (roughly one line at 300 px). */
export const TRUST_MAX = 60

/** Characters of meta text the default (collapsed) view spends. */
export function metaLength(trust: string | undefined, hasDetails: boolean): number {
  return (trust ? trust.length : 0) + (hasDetails ? DETAILS_LABEL.length : 0)
}

/** The budget: meta must stay shorter than the description it comments on. */
export function fitsBudget(trust: string | undefined, hasDetails: boolean, description: string): boolean {
  return metaLength(trust, hasDetails) < description.length
}

/** The longest trust line that fits the budget; the short variant otherwise. */
export function fitTrustLine(
  facts: RankFacts & ReadFacts,
  description: string,
  hasDetails: boolean,
): string | undefined {
  const full = trustLine(facts)
  if (!full) return undefined
  if (fitsBudget(full, hasDetails, description)) return full
  return trustLine(facts, { short: true })
}

// --- requirement lines -----------------------------------------------------

export interface RequirementContext {
  treeName: string
  /** `rules.pointsPerRow * talent.row`, i.e. the points the row needs. */
  rowPoints: number
  /** `rules.maxPoints`. */
  maxPoints: number
  /** `rules.pointsPerPage[tree.page]`, when the class file sets one. */
  pageBudget?: number
  /** Resolved `requires` entries, names already looked up in the tree. */
  prereqs?: { name: string; rank: number }[]
}

/**
 * Red line under the description when the click would not work. Always a full
 * sentence; never names a page id, a tree id or a talent id.
 */
export function requirementLine(verdict: Verdict, ctx: RequirementContext): string | undefined {
  if (verdict.ok) return undefined
  switch (verdict.reason) {
    case 'row-locked':
      return withPeriod(`Requires ${ctx.rowPoints} points in ${ctx.treeName} Talents`)
    case 'prereq': {
      const parts = (ctx.prereqs ?? []).map((p) => `${p.rank} point${p.rank === 1 ? '' : 's'} in ${p.name}`)
      return parts.length > 0 ? withPeriod(`Requires ${joinAnd(parts)}`) : 'Requires another talent first.'
    }
    case 'page-full':
      return ctx.pageBudget !== undefined
        ? `No points left on this tab (${ctx.pageBudget} of ${ctx.pageBudget} spent).`
        : 'No points left on this tab.'
    case 'no-points':
      return `No talent points left (${ctx.maxPoints} of ${ctx.maxPoints} spent).`
    case 'maxed':
      return 'Already at maximum rank.'
    default:
      return undefined
  }
}

/**
 * A game requirement the reader could not fit into the schema - stances, forms,
 * shields, a level - hides inside `source.note` as an `unparsed requirement:`
 * clause. Rendered as a requirement line; dropped when it carries an id.
 */
export function gameRequirement(note: string | undefined): string | undefined {
  for (const clause of noteClauses(note)) {
    const text = clause.replace(/^unparsed requirement:\s*/i, '').trim()
    if (!/^Requires\b/.test(text)) continue
    if (internalId(text)) continue
    return withPeriod(text)
  }
  return undefined
}

// --- details ---------------------------------------------------------------

export type Scaling = 'copied' | 'proportional' | 'table'

/** How the rank values relate to rank 1; read off the numbers, not the note. */
export function rankScaling(ranks: Rank[] | undefined): Scaling {
  if (!ranks || ranks.length < 2) return 'copied'
  const first = ranks[0]
  if (!Array.isArray(first)) return 'table'
  let copied = true
  let proportional = true
  let scales = false
  for (let i = 1; i < ranks.length; i++) {
    const row = ranks[i]
    if (!Array.isArray(row) || row.length !== first.length) return 'table'
    for (let j = 0; j < first.length; j++) {
      const a = first[j]
      const b = row[j]
      if (a !== b) copied = false
      if (typeof a !== 'number' || typeof b !== 'number') {
        if (a !== b) proportional = false
        continue
      }
      if (b === a) continue
      scales = true
      if (Math.abs(b - a * (i + 1)) > 1e-6) proportional = false
    }
  }
  if (copied) return 'copied'
  return proportional && scales ? 'proportional' : 'table'
}

/** "rank 2" / "ranks 2-5", with the verb the sentence needs. */
function rankRange(lo: number, hi: number): { subject: string; verb: string } {
  return lo === hi ? { subject: `Rank ${lo}`, verb: 'is' } : { subject: `Ranks ${lo}-${hi}`, verb: 'are' }
}

/** Where the higher ranks come from, in words a player can check. */
export function derivationLine(facts: RankFacts): string | undefined {
  const observed = highestObserved(facts.ranksObserved)
  if (facts.maxRank <= observed) return undefined
  const lo = observed + 1
  const { subject, verb } = rankRange(lo, facts.maxRank)
  const read = `Rank ${observed} was read from the stream.`
  if (facts.ranksSource === 'manual') {
    return `${read} ${subject} ${verb} not known yet; the data repeats the rank ${observed} text there.`
  }
  const scaling = rankScaling(facts.ranks)
  if (facts.ranksSource === 'classic-prior') {
    return scaling === 'proportional'
      ? `${read} ${subject} ${verb} rank ${observed} multiplied by the rank, the way the matching Classic Era talent scales.`
      : `${read} ${subject} ${verb} taken from the matching Classic Era talent.`
  }
  return scaling === 'proportional'
    ? `${read} ${subject} ${verb} rank ${observed} multiplied by the rank. No Classic Era talent matched, so this is a guess.`
    : `${read} ${subject} ${verb} estimated without a Classic Era talent to match, so this is a guess.`
}

/** The rounding caveat, reworded from the pipeline's `Rounding:` clause. */
export function roundingLines(ranksNote: string | undefined): string[] {
  if (!ranksNote) return []
  const tail = /Rounding:([\s\S]*)$/.exec(ranksNote)
  if (!tail) return []
  const out: string[] = []
  for (const m of tail[1]!.matchAll(/rank (\d+) ([\d.]+) may read ([\d.]+)/g)) {
    out.push(`Rank ${m[1]} may read ${m[3]} in game; the value shown is the unrounded ${m[2]}.`)
  }
  return out
}

/**
 * `source.note` in player words. Clauses that only make sense to the pipeline
 * (frame ids, arrow scores, reader names) are dropped, not reworded.
 */
export function noteLines(note: string | undefined): string[] {
  const out: string[] = []
  for (const clause of noteClauses(note)) {
    const line = noteClauseLine(clause)
    if (line && !internalId(line) && !out.includes(line)) out.push(line)
  }
  return out
}

function noteClauseLine(clause: string): string | undefined {
  const differs = /^second reader\b.*\bdiffers in (.+)$/i.exec(clause)
  if (differs) return `A second reading of this tooltip differs in the ${fieldList(differs[1]!)}.`
  if (/^text may not be rank 1$/i.test(clause)) return 'The captured tooltip may not be rank 1.'
  if (/^every crop of this cell shows rank .*points already spent/i.test(clause)) {
    return 'Every capture of this cell already had points spent in it.'
  }
  if (/^(same-row )?prerequisite (from tree arrow|arrow)/i.test(clause)) {
    return 'The prerequisite comes from the arrows drawn in the tree, not from the tooltip text.'
  }
  return undefined
}

function fieldList(raw: string): string {
  const names = raw
    .split(/,\s*/)
    .map((f) => f.trim().replace(/^rank_max$/i, 'max rank').replace(/^maxRank$/, 'max rank'))
    .filter(Boolean)
  return joinAnd(names)
}

/** Everything the derivation block shows, in reading order. */
export function detailLines(talent: Pick<Talent, 'ranksSource' | 'ranksObserved' | 'maxRank' | 'ranks' | 'ranksNote' | 'source'>): string[] {
  const lines = [
    derivationLine(talent),
    ...roundingLines(talent.ranksNote),
    readingLine(talent.source),
    talent.source.reviewed ? 'Checked by a reviewer.' : undefined,
    ...noteLines(talent.source.note),
  ]
  return lines.filter((l): l is string => Boolean(l) && !internalId(l!))
}

// --- nested tooltips -------------------------------------------------------
//
// The nested tooltips are the mouse-reachable replacement for the old `Details`
// disclosure: hovering a term in an open tooltip opens a second, smaller one.
// Everything they render goes through the same `internalId` guard, so a Classic
// talent id or a reader model name still cannot reach a player.

/**
 * The numbers a rank series shows, e.g. `"1/2/3"`. Picks the slot that actually
 * changes between ranks, so `"Reduces the cost by {0} energy point{1}"` reports
 * the cost and not the plural `s`. Undefined when the ranks are whole sentences.
 */
export function foreverSeries(ranks: Rank[] | undefined): string | undefined {
  if (!ranks || ranks.length === 0) return undefined
  const rows = ranks.filter(Array.isArray) as (number | string)[][]
  if (rows.length !== ranks.length) return undefined
  const width = Math.min(...rows.map((r) => r.length))
  let fallback: number | undefined
  for (let j = 0; j < width; j++) {
    const column = rows.map((r) => r[j])
    if (!column.every((v) => typeof v === 'number')) continue
    if (fallback === undefined) fallback = j
    if (new Set(column).size > 1) return column.join('/')
  }
  if (fallback === undefined) return undefined
  const slot = fallback
  return rows.map((r) => r[slot]).join('/')
}

/**
 * The Classic Era numbers the pipeline scaled from, lifted out of `ranksNote`.
 * The note also carries the Classic talent id and the similarity score, which
 * is why only the digit series is taken and never the sentence around it.
 */
export function classicSeries(ranksNote: string | undefined): string | undefined {
  if (!ranksNote) return undefined
  const number = String.raw`\d+(?:\.\d+)?`
  const m = new RegExp(String.raw`\bClassic (?:scales )?(${number}(?:\/${number})+)`).exec(ranksNote)
  return m ? m[1] : undefined
}

/** True when the note says the Classic values were taken over unchanged. */
export function ranksCopied(ranksNote: string | undefined): boolean {
  return ranksNote !== undefined && /\branks copied\b/i.test(ranksNote)
}

/**
 * What the nested tooltip behind the rank numbers says: the values this talent
 * shows per rank, the Classic Era values they were scaled from when the record
 * carries a `ranksPrior` match, and the derivation in the same words the
 * derivation block uses.
 */
export function rankDerivationLines(
  talent: Pick<Talent, 'ranksSource' | 'ranksObserved' | 'maxRank' | 'ranks' | 'ranksNote' | 'ranksPrior'>,
): string[] {
  const mine = foreverSeries(talent.ranks)
  const prior = talent.ranksPrior
    ? (classicSeries(talent.ranksNote) ?? (ranksCopied(talent.ranksNote) ? mine : undefined))
    : undefined
  const lines = [
    mine && talent.maxRank > 1 ? `Values by rank: ${mine}.` : undefined,
    prior ? `Classic Era: ${prior}.` : undefined,
    derivationLine(talent),
    ...roundingLines(talent.ranksNote),
  ]
  return lines.filter((l): l is string => Boolean(l) && !internalId(l!))
}

/** One reader's take on a tooltip. Never carries the reader's model name. */
export interface ReaderView {
  label: string
  name?: string
  text?: string
  /** Whole percent, omitted when the record does not record one. */
  percent?: number
}

const READING_LABELS = ['The reading in use', 'A second reading', 'A third reading']

/**
 * Both (or all) readings of a tooltip, for the nested tooltip behind the
 * uncertain marker. The first entry is what the calculator shows; the rest come
 * from `source.readings`. Reader ids stay on `#/review/<class>`: a player gets
 * "a second reading", not "rapidocr-1.4".
 */
export function readerViews(source: Source, current: { name: string; text: string }): ReaderView[] {
  const label = (i: number) => READING_LABELS[i] ?? `Reading ${i + 1}`
  const views: ReaderView[] = [
    { label: label(0), name: current.name, text: current.text, percent: percent(source.confidence) },
  ]
  for (const [i, r] of (source.readings ?? []).entries()) {
    views.push({ label: label(i + 1), name: r.name, text: r.description, percent: percent(r.confidence) })
  }
  return views.map((v) => ({ ...v, text: v.text && !internalId(v.text) ? v.text : undefined }))
}

function percent(confidence: number | undefined): number | undefined {
  return confidence === undefined ? undefined : Math.round(confidence * 100)
}

/** A requirement line cut at the talent names it mentions, so they can be terms. */
export interface NameSegment {
  text: string
  /** Set when this segment is exactly a talent name the tooltip can nest. */
  talentId?: string
}

/**
 * Splits a rendered line on the prerequisite names it contains. Longest name
 * first, so "Improved Wrench" wins over a hypothetical "Wrench"; names that do
 * not occur are simply not found and the line comes back in one piece.
 */
export function splitOnNames(line: string, names: { id: string; name: string }[]): NameSegment[] {
  const wanted = names.filter((n) => n.name).sort((a, b) => b.name.length - a.name.length)
  const out: NameSegment[] = []
  let rest = line
  while (rest.length > 0) {
    let at = -1
    let hit: { id: string; name: string } | undefined
    for (const n of wanted) {
      const i = rest.indexOf(n.name)
      if (i === -1) continue
      if (at === -1 || i < at || (i === at && n.name.length > (hit?.name.length ?? 0))) {
        at = i
        hit = n
      }
    }
    if (at === -1 || !hit) break
    if (at > 0) out.push({ text: rest.slice(0, at) })
    out.push({ text: hit.name, talentId: hit.id })
    rest = rest.slice(at + hit.name.length)
  }
  if (rest.length > 0) out.push({ text: rest })
  return out
}

// --- what changed against Classic Era --------------------------------------

/** A Classic number and what it became: `["15%", "20%"]`. */
export type ValuePair = [string, string]

/** A talent's standing against the Classic prior; mirrors src/ui/classicDiff.ts. */
export interface ChangeFacts {
  status: 'new' | 'moved' | 'rank-changed' | 'text-changed' | 'values-changed' | 'same'
  prior?: {
    tree: string
    treeName: string
    row: number
    col: number
    maxRank: number
    /** Set only when the talent really changed tree (renames are not moves). */
    movedTree?: boolean
    /** Set when the row changed. A move is a change of tree or row, never of column alone. */
    movedRow?: boolean
    /**
     * Set when only the column inside the same row changed. Recorded for the
     * review route; the player-facing line deliberately says nothing about it.
     */
    movedCol?: boolean
  }
  textChange?: 'text' | 'values'
  values?: ValuePair[]
  /**
   * The Forever row, 0-based, written by the generator for `moved` entries only
   * so that the line can say where the talent went without the caller having to
   * look the talent up. `current.row` overrides it when a caller does pass one.
   */
  row?: number
}

/**
 * The change line's own budget, the same idea as `TRUST_MAX`: one line at
 * 300 px. A talent whose every number moved (Pyroblast changed three) would
 * otherwise turn the one-line rule into a paragraph, so the enumeration
 * collapses to its first pair plus a count.
 */
export const CHANGE_MAX = 60

/**
 * The single "what changed" line (brief idea 3). Exactly one line, always, so
 * it fits the tooltip's line budget instead of being appended to it.
 *
 * Precedence is worst news first - new > moved > rank-changed > text-changed >
 * values-changed - because the player gets one sentence and it should be the
 * largest true claim. Everything the losing categories would have said is still
 * on the record, which is what the nested card behind this line shows.
 *
 * A tree Forever merely renamed (Shadow -> Shadow Magic) is **not** a move: the
 * generator matches trees before it compares cells, and only a genuine change
 * of tree sets `prior.movedTree`. Rows are stored 0-based and spoken 1-based,
 * the way the tier gutter counts.
 *
 * Neither is a different **column** inside the same row: the row is what gates
 * a talent (five points per tier), the column is ordering, and Forever
 * reshuffled the order in most trees. The generator never gives such a talent
 * the `moved` status, so this function only ever has to name a tree or a row -
 * and it names the new row too, because "Moved from row 5" alone was read as
 * "this talent changed" by a player who was looking straight at row 5.
 */
export function changeLine(
  change: ChangeFacts | undefined,
  current: { tree: string; maxRank: number; row?: number },
): string | undefined {
  if (!change || change.status === 'same') return undefined
  if (change.status === 'new') return 'New in Forever.'
  const prior = change.prior
  if (!prior) return undefined
  switch (change.status) {
    case 'moved':
      return movedLine(prior, current.row ?? change.row)
    case 'rank-changed':
      return `Now ${ranksWord(current.maxRank)}, was ${prior.maxRank}.`
    case 'text-changed':
      return 'Reworked.'
    case 'values-changed':
      return valuesChangedLine(change.values)
    default:
      return undefined
  }
}

/**
 * The `moved` line. Four shapes, and every one of them is only reachable for a
 * talent whose tree or row really changed:
 *
 *   same tree, other row   `Moved from row 3 to row 5.`
 *   other tree, same row   `Moved from Arms.`
 *   other tree, other row  `Moved from Arms, row 3 to row 5.`
 *   row unknown            `Moved from row 3.` (the caller did not pass a row)
 *
 * `current` is the Forever row, 0-based like the stored one. It comes from the
 * caller or, failing that, from `change.row` in the generated diff; it stays
 * optional so a caller that has neither still gets a true, if vaguer, sentence.
 */
function movedLine(prior: NonNullable<ChangeFacts['prior']>, current: number | undefined): string {
  const from = prior.movedTree ? `Moved from ${prior.treeName}` : 'Moved from row ' + (prior.row + 1)
  if (current === undefined || current === prior.row) return `${from}.`
  const rows = prior.movedTree
    ? `, row ${prior.row + 1} to row ${current + 1}`
    : ` to row ${current + 1}`
  return `${from}${rows}.`
}

/** `Values changed: 15% -> 20%.`, collapsed when it would run past one line. */
export function valuesChangedLine(values: ValuePair[] | undefined): string {
  const pairs = (values ?? []).filter((v) => v?.length === 2)
  if (pairs.length === 0) return 'Values changed.'
  const full = `Values changed: ${pairs.map(valuePair).join(', ')}.`
  if (full.length <= CHANGE_MAX) return full
  const rest = pairs.length - 1
  return rest > 0 ? `Values changed: ${valuePair(pairs[0]!)} and ${rest} more.` : `Values changed: ${valuePair(pairs[0]!)}.`
}

function valuePair([was, now]: ValuePair): string {
  return `${was} \u2192 ${now}`
}

/** The heading of the nested card behind the change line. */
export function changeCardTitle(change: ChangeFacts | undefined): string {
  return change?.status === 'new' ? 'Not in Classic Era' : 'In Classic Era'
}

/** `Classic values by rank: 2/4/6/8/10.` - omitted for a one-rank talent. */
export function classicSeriesLine(series: string | undefined): string | undefined {
  if (!series || !series.includes('/')) return undefined
  const line = `Classic values by rank: ${series}.`
  return internalId(line) ? undefined : line
}

/**
 * The lines under the struck-and-marked Classic sentence: the Classic per-rank
 * values, and the full list of value pairs when there is more than one.
 *
 * A single pair is left out on purpose - `valuesChangedLine` always spells one
 * pair out in full, so repeating it in the card two lines below says nothing.
 * Several pairs can collapse to "and 3 more" up there, and then the card is the
 * only place a player can read them all.
 */
export function changeCardLines(
  classic: { series?: string; values?: ValuePair[] } | undefined,
): string[] {
  if (!classic) return []
  const lines: (string | undefined)[] = [classicSeriesLine(classic.series)]
  const pairs = (classic.values ?? []).filter((v) => v?.length === 2)
  if (pairs.length > 1) lines.push(`Values: ${pairs.map(valuePair).join(', ')}.`)
  return lines.filter((l): l is string => Boolean(l) && !internalId(l!))
}

function ranksWord(n: number): string {
  return `${n} rank${n === 1 ? '' : 's'}`
}

// --- small helpers ---------------------------------------------------------

function joinAnd(parts: string[]): string {
  if (parts.length <= 1) return parts[0] ?? ''
  return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`
}

function noteClauses(note: string | undefined): string[] {
  if (!note) return []
  return note
    .split(';')
    .map((c) => c.trim())
    .filter(Boolean)
}

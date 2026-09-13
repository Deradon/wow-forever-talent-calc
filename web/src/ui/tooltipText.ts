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
import { REVIEW_THRESHOLD, streamStamp } from './review'

/** Label of the disclosure that holds everything except the trust line. */
export const DETAILS_LABEL = 'Details'

/** Style-guide cap for the amber line (roughly one line at 300 px). */
export const TRUST_MAX = 60

export type TrustKind = 'uncertain' | 'observed-only' | 'estimated'

export interface RankFacts {
  ranksSource: Talent['ranksSource']
  ranksObserved: number[]
  maxRank: number
  ranks?: Rank[]
  ranksNote?: string
}

/**
 * The reading facts live under `talent.source`, so they are nested here too:
 * a flat `confidence` would make a whole `Talent` structurally assignable
 * while silently reading `undefined`.
 */
export interface ReadFacts {
  source: { confidence?: number; reviewed?: boolean }
}

/** Highest rank actually read from the stream; 1 when nothing is recorded. */
export function highestObserved(ranksObserved: number[]): number {
  return ranksObserved.length > 0 ? Math.max(...ranksObserved) : 1
}

/**
 * Which single trust line applies, worst news first: a shaky reading beats an
 * estimated rank, because it questions the text the player is looking at (see
 * the `warrior/enrage` example in the text-quality review, section 3).
 */
export function trustKind(facts: RankFacts & ReadFacts): TrustKind | undefined {
  const { confidence, reviewed } = facts.source
  if (!reviewed && confidence !== undefined && confidence < REVIEW_THRESHOLD) return 'uncertain'
  const observed = highestObserved(facts.ranksObserved)
  if (facts.maxRank <= observed) return undefined
  return facts.ranksSource === 'manual' ? 'observed-only' : 'estimated'
}

/** The amber line, in full or in the short variant used when space is tight. */
export function trustLine(facts: RankFacts & ReadFacts, opts: { short?: boolean } = {}): string | undefined {
  const kind = trustKind(facts)
  if (!kind) return undefined
  const observed = highestObserved(facts.ranksObserved)
  if (kind === 'uncertain') return opts.short ? 'Check this reading.' : 'Uncertain reading, check.'
  if (kind === 'observed-only') return opts.short ? `Rank ${observed} only.` : `Only rank ${observed} is known.`
  const lo = observed + 1
  const hi = facts.maxRank
  if (opts.short) return 'Estimated ranks.'
  return lo === hi ? `Rank ${lo} estimated.` : `Ranks ${lo}-${hi} estimated.`
}

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

/** One line for when and how well the tooltip was read. Never says "100%". */
export function readingLine(source: Source): string | undefined {
  if (source.kind === 'video') {
    const pct = source.confidence !== undefined && source.confidence < 1 ? `, ${Math.round(source.confidence * 100)}% confidence` : ''
    return `Read from the stream at ${streamStamp(source.t ?? 0)}${pct}.`
  }
  if (source.kind === 'datamined') return source.build ? `Datamined from build ${source.build}.` : 'Datamined from the client.'
  return 'Entered by hand.'
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

/** Everything the Details disclosure shows, in reading order. */
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

// --- guards ----------------------------------------------------------------

const INTERNAL = [
  /\btalent \d+\b/i, // Classic talent ids
  /\bstage \d+\b/i, // pipeline stage numbers
  /\br\d+c\d+\b/i, // grid coordinates
  /@\S*\d/, // frame references (r4c3@08-mage-14970)
  /\bsimilarity\b|\(0\.\d+\)/, // match scores
  /\b(codex|qwen|gpt|llama|gemini)\b/i, // reader model names
  /\{\d+\}/, // raw slot labels
  /needs manual ranks|no alignable slots|copies of rank/i,
  /\bcross-class\b/i,
  /\bpage (primary|secondary)\b/i,
  /classic-prior|extrapolated|ranksSource/i,
  /\bconfidence 0\.\d+/i,
  /data\/review\/|\.png\b|\.jpg\b/i,
  /\bconfidence 100%/i,
]

/** True when a string carries something that belongs on the review route only. */
export function internalId(text: string): boolean {
  return INTERNAL.some((re) => re.test(text))
}

// --- small helpers ---------------------------------------------------------

export function withPeriod(text: string): string {
  const trimmed = text.trim()
  return /[.!?]$/.test(trimmed) ? trimmed : `${trimmed}.`
}

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

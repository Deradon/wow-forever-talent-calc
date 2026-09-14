/**
 * The trust primitives: the one amber line, the reading line, the guard that
 * keeps pipeline internals away from players, and the full stop rule.
 *
 * They live in their own module rather than in `tooltipText.ts` because three
 * pages need them and only one needs the rest of that file. The talent tooltip
 * (`tooltipText.ts`), the changes list and the races pages all state trust the
 * same way, and they do it by calling the same functions - a second wording of
 * "uncertain reading" is exactly the divergence the text-quality review warns
 * about. `tooltipText.ts` re-exports everything here, so its callers and its
 * tests are unchanged.
 *
 * Rules: `docs/reviews/2026-09-13-text-quality.md`, "Proposed style guide:
 * player-facing meta text".
 */
import type { Rank, Source, Talent } from '../data/schema'

/**
 * Review-queue threshold from DATA-SCHEMA.md section 4.5. It lives here rather
 * than in `review.ts` so that this module imports nothing: a page that only
 * wants the trust line must not drag the review route's filtering in with it.
 * `review.ts` re-exports both of these.
 */
export const REVIEW_THRESHOLD = 0.8

/**
 * The four sentences the site is allowed to say about where its data comes
 * from. They are constants and not inline strings because round two found six
 * different wordings of the same claim across the landing page, the class
 * pages, the footer, the tooltips and the race and spell pages, three of them
 * carrying pipeline vocabulary (UX review round two, findings 5 and 6).
 */
export const SOURCE_LINE = 'Read from BlizzCon 2026 footage.'
export const RANKS_LINE =
  'Only the first rank of each talent was on screen; ranks above that are estimated from Classic Era.'
export const TWO_READINGS_LINE = 'Two transcriptions disagree; the one shown is the more likely.'
export const ONE_READING_LINE = 'Only one transcription was recorded.'

export interface ReviewFacts {
  total: number
  reviewed: number
}

/**
 * "57 of 469 talents have been checked by hand; the rest are as read."
 *
 * The number comes from the build-time index (`src/data/facts.json`), so a
 * page can never say "unreviewed" about a dataset that is partly reviewed, and
 * the sentence follows the data without anyone remembering to edit it.
 */
export function checkedLine(facts: ReviewFacts, noun: string): string {
  const { total, reviewed } = facts
  if (total === 0) return ''
  if (reviewed === 0) return `None of the ${total} ${noun} has been checked by hand yet; they are as read.`
  if (reviewed >= total) return `All ${total} ${noun} have been checked by hand.`
  return `${reviewed} of ${total} ${noun} have been checked by hand; the rest are as read.`
}

/** `h:mm:ss` into the stream for a `source.t` value. */
export function streamStamp(t: number): string {
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const sec = Math.floor(t % 60)
  return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

/** True when a record is unreviewed and was read below the threshold. */
export function needsReview(t: { source?: { confidence?: number; reviewed?: boolean } }): boolean {
  const s = t.source
  if (!s || s.reviewed) return false
  return s.confidence !== undefined && s.confidence < REVIEW_THRESHOLD
}

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

/**
 * One line for when a record was read. It carries no percentage: the stream
 * timestamp is a fact a player can check, a confidence score is a number out of
 * the reader's internals, and the amber trust line above it already says in
 * words when a reading is shaky (UX review round two, finding 6).
 */
export function readingLine(source: Source): string | undefined {
  if (source.kind === 'video') {
    return `Read from the stream at ${streamStamp(source.t ?? 0)}.`
  }
  if (source.kind === 'datamined') return source.build ? `Datamined from build ${source.build}.` : 'Datamined from the client.'
  return 'Entered by hand.'
}

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
  // Pipeline vocabulary that reached players in round two (finding 6).
  /\bvision model\b/i,
  /\brank-0\b/i,
  /\bextracted\b/i,
  /\banticipated\b/i,
  /\bthe reading in use\b|\ba (second|third) reading\b|\b\d+ readings\b/i,
  /\b\d{1,3}% confidence\b/i,
  // Dataset-level caveats the data files carry for the owner. The page states
  // the same fact from `facts.json` instead, with the number in it, so a file
  // that still says "nothing here is reviewed" cannot contradict it
  // (UX review round two, findings 5 and 16).
  /nothing here is reviewed|\bnot yet reviewed\b|\bunreviewed\b/i,
  /\bdemo build \d{4}-\d{2}-\d{2}\b/i,
  // Was `spellsModel.PIPELINE_WORDS`; one list, one guard.
  /pipeline\/|coverage\.|source note|ranksSeen|\.py\b|\.json\b|the reader|hand-labelled|half-drawn|fade-in|\bframe crops?\b|\bcrops?\b|this file/i,
]

/**
 * The `notes[]` a data file carries, minus anything written for the data owner
 * rather than for a player. Every dataset under `data/` is the pipeline's file
 * and its notes are the pipeline's prose - mage's is "Extracted from BlizzCon
 * 2026 stream footage (rank-0 tooltips only); ranks 2+ are anticipated", every
 * race and spell file's is "BlizzCon demo build 2026-09-12, read from stream
 * video; nothing here is reviewed" - so the pages state `RANKS_LINE` and
 * `checkedLine()` themselves and print only the notes that pass this guard.
 */
export function playerNotes(notes: string[] | undefined): string[] {
  return (notes ?? []).filter((n) => !internalId(n))
}

/**
 * The two or three lines a whole dataset page states once at the top: where it
 * came from, how much of it has been checked, and how much of it is shaky.
 *
 * One function for the races page and the spellbook page, which had two
 * line-for-line identical copies that both claimed "Read from BlizzCon 2026
 * footage" whatever `source.kind` said (code review K-25).
 */
export function datasetTrustLines(records: { source: Source }[], noun: { one: string; many: string }): string[] {
  const total = records.length
  if (total === 0) return []
  const kinds = new Set(records.map((r) => r.source.kind))
  const source =
    kinds.size === 1 && kinds.has('video')
      ? SOURCE_LINE
      : kinds.size === 1 && kinds.has('datamined')
        ? 'Read from the game client.'
        : kinds.size === 1 && kinds.has('manual')
          ? 'Entered by hand.'
          : 'Read from BlizzCon 2026 footage and from the game client.'
  const word = total === 1 ? noun.one : noun.many
  const lines = [source, checkedLine({ total, reviewed: records.filter((r) => r.source.reviewed).length }, word)]
  const shaky = records.filter((r) => needsReview(r)).length
  if (shaky > 0) lines.push(`${shaky} of ${total} ${word} ${shaky === 1 ? 'is' : 'are'} uncertain and marked below.`)
  return lines.filter(Boolean)
}

/** True when a string carries something that belongs on the review route only. */
export function internalId(text: string): boolean {
  return INTERNAL.some((re) => re.test(text))
}

export function withPeriod(text: string): string {
  const trimmed = text.trim()
  return /[.!?]$/.test(trimmed) ? trimmed : `${trimmed}.`
}

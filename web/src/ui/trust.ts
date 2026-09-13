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

/** One line for when and how well a record was read. Never says "100%". */
export function readingLine(source: Source): string | undefined {
  if (source.kind === 'video') {
    const pct =
      source.confidence !== undefined && source.confidence < 1
        ? `, ${Math.round(source.confidence * 100)}% confidence`
        : ''
    return `Read from the stream at ${streamStamp(source.t ?? 0)}${pct}.`
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
]

/** True when a string carries something that belongs on the review route only. */
export function internalId(text: string): boolean {
  return INTERNAL.some((re) => re.test(text))
}

export function withPeriod(text: string): string {
  const trimmed = text.trim()
  return /[.!?]$/.test(trimmed) ? trimmed : `${trimmed}.`
}

/**
 * Write-back for the review route: turn a row on `#/review/<class>` into the
 * text of an override entry for `data/overrides/<class>.json`.
 *
 * The route itself stays read-only (`docs/DATA-SCHEMA.md` section 7) - a static
 * page cannot write to the repository, and the schema deliberately keeps the
 * audit trail (`reason`, `by`, `at`) in the file. What it can do is stop the
 * reviewer from retyping the id, the tree, the name and a 200-character
 * description by hand, which is where the transcription errors come from.
 *
 * Everything here is pure and unit tested in `overrideEntry.test.ts`, which
 * checks the emitted shape against `data/schema/class.schema.json` and against
 * the key order of the pipeline's canonical serializer
 * (`pipeline/validate.py`, `KEY_ORDER`).
 *
 * Two deliberate deviations from "prefilled and ready":
 *
 * - `by` is required with `minLength: 1`, so an empty string would not
 *   validate. It is emitted as the placeholder `TODO`, like `reason`, so both
 *   fields a human has to write are one `grep TODO` away.
 * - `reviewed: true` is not a key of an override entry
 *   (`additionalProperties: false`), and applying any override already sets
 *   `source.reviewed: true`. The intent is stated where the schema allows it,
 *   in `set.source.reviewed`, so the entry says out loud what promoting it
 *   will do.
 */
import type { ReviewRow } from './review'
import { SITE_URL } from './site'

/** What a human still has to replace before the entry is worth committing. */
export const TODO = 'TODO'

export interface OverrideEntry {
  /** Talent id as `data/extracted/<class>.json` has it (pre-rename). */
  talent: string
  tree: string
  /** Shallow merge over the extracted talent; `source` merges shallowly too. */
  set: {
    name: string
    description: string
    source: { reviewed: true }
  }
  reason: string
  by: string
  at: string
}

export interface OverrideOptions {
  /** RFC 3339, injected so the tests and the copied text are reproducible. */
  at?: string
  by?: string
}

function rfc3339(date = new Date()): string {
  return `${date.toISOString().slice(0, 19)}Z`
}

/**
 * One entry, prefilled with what the record says today so the reviewer edits in
 * place rather than retyping. An accepted-as-read record needs an entry too -
 * that is the only way to reach `source.reviewed: true` (section 7) - so the
 * `set` block is never empty of the two fields a reading can get wrong.
 */
export function buildOverrideEntry(row: ReviewRow, opts: OverrideOptions = {}): OverrideEntry {
  const { talent, tree } = row
  const crop = talent.source.kind === 'video' ? talent.source.crop : undefined
  return {
    talent: talent.id,
    tree: tree.id,
    set: {
      name: talent.name,
      description: talent.description,
      source: { reviewed: true },
    },
    reason: crop ? `${TODO}: what was wrong; checked against ${crop}` : `${TODO}: what was wrong; checked on the review route`,
    by: opts.by?.trim() || TODO,
    at: opts.at ?? rfc3339(),
  }
}

// --- canonical serialization ------------------------------------------------

const INLINE_MAX = 100

/**
 * The pipeline's serializer, in TypeScript: `pipeline/validate.py` `_dump`.
 * Two spaces per level, arrays of scalars inline while they fit in 100
 * characters, everything else one item per line. `validate.py --check` compares
 * the overrides file byte for byte against this output (rule R12), so text that
 * is pasted in this shape does not have to be reformatted afterwards.
 *
 * Key order is the insertion order of the objects built above, which is the
 * `KEY_ORDER["override"]` / `KEY_ORDER["talent"]` / `KEY_ORDER["source"]` order
 * the serializer applies; `overrideEntry.test.ts` asserts that it still is.
 */
export function canonicalDump(value: unknown, indent = 0): string {
  const pad = ' '.repeat(indent)
  if (Array.isArray(value)) {
    if (value.length === 0) return '[]'
    if (!value.some((v) => v !== null && typeof v === 'object' && !Array.isArray(v))) {
      const inline = `[${value.map((v) => canonicalDump(v, indent)).join(', ')}]`
      if (inline.length <= INLINE_MAX && !inline.includes('\n')) return inline
    }
    return `[\n${value.map((v) => `${pad}  ${canonicalDump(v, indent + 2)}`).join(',\n')}\n${pad}]`
  }
  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.length === 0) return '{}'
    const items = entries.map(([k, v]) => `${pad}  ${JSON.stringify(k)}: ${canonicalDump(v, indent + 2)}`)
    return `{\n${items.join(',\n')}\n${pad}}`
  }
  return JSON.stringify(value)
}

/** Indent of an entry inside the `"overrides": [ ... ]` array of the file. */
const ENTRY_INDENT = 4

/** One entry, indented exactly as it sits in the file, ready to paste. */
export function overrideEntryText(entry: OverrideEntry): string {
  return ' '.repeat(ENTRY_INDENT) + canonicalDump(entry, ENTRY_INDENT)
}

/**
 * Several entries, comma-separated at the same indent: the array *elements*,
 * not a bracketed array, because every class already has an
 * `data/overrides/<class>.json` with an `overrides` array to paste them into
 * and a second pair of brackets there would be a syntax error.
 */
export function overrideEntriesText(entries: OverrideEntry[]): string {
  return entries.map(overrideEntryText).join(',\n')
}

// --- reporting a wrong reading ---------------------------------------------

/**
 * A GitHub issue form prefills its fields from query parameters named after the
 * `id` of each element in the form YAML ("the id is the canonical identifier
 * for the field in URL query parameter prefills" - GitHub's form schema docs),
 * plus the reserved `template` and `labels`. The ids here are the ones in
 * `.github/ISSUE_TEMPLATE/wrong-reading.yml`; keep the two in step.
 */
export function wrongReadingUrl(row: ReviewRow, classId: string, repoUrl: string): string {
  const params = new URLSearchParams({
    template: 'wrong-reading.yml',
    labels: 'data,wrong-reading',
    class: classId,
    record: `${row.tree.id}/${row.talent.id}`,
    shown: `${row.talent.name} - ${row.talent.description}`,
    link: `${SITE_URL}#/${classId}?sel=${row.talent.id}`,
  })
  return `${repoUrl}/issues/new?${params.toString()}`
}

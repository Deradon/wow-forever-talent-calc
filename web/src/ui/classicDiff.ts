/**
 * What changed against Classic Era: the read side of the two files
 * `scripts/gen-data-index.mjs` generates by diffing `data/talents/*` against
 * `data/prior/classic-era/talents.json` (brief `docs/briefs/ui-improvements.md`,
 * idea 3; round 2 in `docs/handover/2026-09-13-classic-diff-v2.md`).
 *
 *   `classic-diff.json`  statuses, the Classic cell, the value pairs the change
 *                        line prints, and the removed list. Ships on the class
 *                        route.
 *   `classic-text.json`  the Classic rank-1 sentence, its per-rank values and
 *                        the word diff. Fetched with a dynamic `import()` the
 *                        first time a player opens a "what changed" card, so a
 *                        player who never opens one never pays for it.
 *
 * The generated diff lists only the talents that actually changed. A class that
 * has a diff therefore reports `same` for every talent it does not mention; a
 * class that has none (the tinker example) reports `undefined` everywhere, so
 * an example class never claims that all of its talents are new.
 */
import diff from '../data/classic-diff.json'

export type ChangeStatus = 'new' | 'moved' | 'rank-changed' | 'text-changed' | 'values-changed' | 'same'

/** Which kind of description change a talent has, whatever its headline status. */
export type TextChange = 'text' | 'values'

/** `["15%", "20%"]`: what one number said in Classic and says in Forever. */
export type ValuePair = [string, string]

export interface PriorCell {
  tree: string
  treeName: string
  row: number
  col: number
  maxRank: number
  /**
   * Set only when the talent really changed tree. `tree` stays the Classic id
   * ("shadow"), which is *not* the current one ("shadow-magic") when Forever
   * merely renamed the tree - so never compare `tree` with a Forever tree id;
   * ask this flag instead.
   */
  movedTree?: boolean
}

export interface Change {
  status: ChangeStatus
  prior?: PriorCell
  textChange?: TextChange
  values?: ValuePair[]
}

/** The op letters the generated word diff uses. */
export type DiffOpLetter = '=' | '-' | '+'

export interface ClassicText {
  text: string
  series?: string
  diff: [DiffOpLetter, string][]
  values?: ValuePair[]
}

interface ClassDiff {
  counts: Record<string, number>
  talents: Record<string, Change>
  removed: (PriorCell & { id: string; name: string })[]
}

const CLASSES = diff.classes as unknown as Record<string, ClassDiff>

/** The statuses that mean "this talent is not what it was in Classic". */
const CHANGED: ChangeStatus[] = ['new', 'moved', 'rank-changed', 'text-changed', 'values-changed']

/** True when this class was compared against Classic at all. */
export function hasClassicDiff(classId: string): boolean {
  return classId in CLASSES
}

/** Number of talents in the class that are new, moved, re-ranked or reworded. */
export function changedCount(classId: string): number {
  const c = CLASSES[classId]?.counts
  if (!c) return 0
  return CHANGED.reduce((n, key) => n + (c[key] ?? 0), 0)
}

/** Classic talents with no counterpart in Forever - for a later `#/changes`. */
export function removedTalents(classId: string): (PriorCell & { id: string; name: string })[] {
  return CLASSES[classId]?.removed ?? []
}

/**
 * How this talent stands against Classic. `undefined` means "not comparable"
 * (no prior for this class), which is different from `same`.
 */
export function changeOf(classId: string, talentId: string): Change | undefined {
  const cls = CLASSES[classId]
  if (!cls) return undefined
  const entry = cls.talents[talentId]
  if (!entry) return { status: 'same' }
  return entry
}

// --- the lazily fetched Classic text ---------------------------------------

type TextIndex = Record<string, Record<string, ClassicText>>

let loaded: TextIndex | undefined
let loading: Promise<TextIndex> | undefined

/** Already-fetched Classic text, for a synchronous first render after the first card. */
export function classicTextSync(classId: string, talentId: string): ClassicText | undefined {
  return loaded?.[classId]?.[talentId]
}

/**
 * Fetches `classic-text.json` once and keeps it. Callers are tooltip cards, so
 * a failed fetch must degrade to "no card", never to a broken tooltip.
 */
export async function loadClassicText(classId: string, talentId: string): Promise<ClassicText | undefined> {
  if (!loaded) {
    loading ??= import('../data/classic-text.json').then((m) => (m.default ?? m) as unknown as TextIndex)
    try {
      loaded = await loading
    } catch {
      loading = undefined
      return undefined
    }
  }
  return loaded[classId]?.[talentId]
}

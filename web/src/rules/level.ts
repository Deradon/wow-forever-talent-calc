import type { Rules } from '../data/schema'

/** `requiredLevel(n) = n === 0 ? 1 : firstPointLevel - 1 + n` (DATA-SCHEMA.md 4.1). */
export function requiredLevel(total: number, rules: Pick<Rules, 'firstPointLevel'>): number {
  return total <= 0 ? 1 : rules.firstPointLevel - 1 + total
}

/** The inclusive range the level control offers: the first point to max level. */
export function levelRange(rules: Pick<Rules, 'firstPointLevel' | 'maxLevel'>): { min: number; max: number } {
  const min = Math.max(1, rules.firstPointLevel)
  return { min, max: Math.max(min, rules.maxLevel) }
}

/**
 * How many talent points a character has at `level` (brief idea 10). The exact
 * inverse of `requiredLevel`: one point at `firstPointLevel` and one per level
 * after it, never below zero and never above the class budget.
 *
 * Deliberately *not* a per-talent statement. The order in which a build was
 * spent is not tracked - the URL carries a set of ranks, not a history - so the
 * honest thing to say is how many of the points a build spends are available at
 * a given level, which is what `pointsAtLevel` feeds.
 */
export function pointsAtLevel(level: number, rules: Pick<Rules, 'firstPointLevel' | 'maxPoints'>): number {
  if (!Number.isFinite(level)) return 0
  const earned = Math.floor(level) - rules.firstPointLevel + 1
  return Math.min(Math.max(earned, 0), rules.maxPoints)
}

/** How a build stands at one level: `N of your M spent points`. */
export interface LevelStanding {
  level: number
  /** Points the character has at that level, capped at the class budget. */
  available: number
  /** Points the build spends. */
  spent: number
  /** Of the spent points, how many are affordable at that level. */
  affordable: number
  /** Spent points the character cannot have yet; 0 once the level is enough. */
  beyond: number
}

export function standingAtLevel(
  level: number,
  spent: number,
  rules: Pick<Rules, 'firstPointLevel' | 'maxPoints'>,
): LevelStanding {
  const available = pointsAtLevel(level, rules)
  const affordable = Math.min(available, Math.max(spent, 0))
  return { level, available, spent: Math.max(spent, 0), affordable, beyond: Math.max(spent, 0) - affordable }
}

/** The sentence the summary column prints. One tense, no build history implied. */
export function levelLine(standing: LevelStanding): string {
  const { level, available, spent, affordable, beyond } = standing
  if (spent === 0) return `At level ${level} you have ${available} talent point${available === 1 ? '' : 's'}.`
  if (beyond === 0) return `At level ${level} you have all ${spent} of your ${spent} spent points.`
  return `At level ${level} you have ${affordable} of your ${spent} spent points - ${beyond} too many.`
}

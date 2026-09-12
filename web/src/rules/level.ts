import type { Rules } from '../data/schema'

/** `requiredLevel(n) = n === 0 ? 1 : firstPointLevel - 1 + n` (DATA-SCHEMA.md 4.1). */
export function requiredLevel(total: number, rules: Pick<Rules, 'firstPointLevel'>): number {
  return total <= 0 ? 1 : rules.firstPointLevel - 1 + total
}

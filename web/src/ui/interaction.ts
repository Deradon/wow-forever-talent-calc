import type { Talent } from '../data/schema'
import type { Verdict } from '../rules'

/** Search matches a talent name or its description, case-insensitively. */
export function matchesTalent(talent: Pick<Talent, 'name' | 'description'>, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return talent.name.toLowerCase().includes(q) || talent.description.toLowerCase().includes(q)
}

/**
 * One line saying why a click did nothing, in the player's vocabulary. Every
 * blocked interaction used to fail silently (usability review 4); the rules
 * layer already computes the `Verdict`, this turns it into a sentence.
 */
export function blockedMessage(name: string, verdict: Verdict, action: 'add' | 'remove'): string {
  if (verdict.ok) return ''
  switch (verdict.reason) {
    case 'maxed':
      return `${name} is already at its maximum rank.`
    case 'no-points':
      return `No talent points left. Refund one before spending it on ${name}.`
    case 'page-full':
      return `No points left on this page (${verdict.detail ?? 'budget reached'}).`
    case 'row-locked':
      return `${name} needs ${verdict.detail ?? 'more points in this tree'}.`
    case 'prereq':
      return action === 'add'
        ? `${name} requires ${verdict.detail ?? 'another talent first'}.`
        : `Refunding ${name} would break ${verdict.detail ?? 'another talent'}.`
    case 'would-orphan':
      return `Refunding ${name} would orphan ${verdict.detail ?? 'a talent below it'}.`
    case 'not-spent':
      return `No points spent in ${name}.`
    default:
      return `${name} cannot be changed.`
  }
}

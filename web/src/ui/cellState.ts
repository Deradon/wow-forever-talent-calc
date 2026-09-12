import type { Verdict } from '../rules'

export type CellState = 'available' | 'partial' | 'maxed' | 'locked'

/** The four visual states of a talent cell (brief section 6). */
export function cellState(rank: number, maxRank: number, addVerdict: Verdict): CellState {
  if (rank >= maxRank) return 'maxed'
  if (rank > 0) return 'partial'
  if (addVerdict.ok) return 'available'
  if (addVerdict.reason === 'row-locked' || addVerdict.reason === 'prereq') return 'locked'
  return 'available' // out of points: keep the colour, just not addable
}

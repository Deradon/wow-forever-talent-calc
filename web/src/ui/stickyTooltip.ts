/**
 * The rules that decide when a hover tooltip is allowed to take the pointer.
 *
 * A tooltip is wider than the 12 px grid gap, so an interactive one always
 * covers a neighbouring cell - and an interactive tooltip that appears under a
 * cursor on its way somewhere else makes that cell unclickable. Work package A2
 * measured exactly that and reverted the whole idea
 * (`docs/handover/2026-09-13-fix-a2-interaction.md`, "A1's requests", item 1).
 *
 * So the layer only becomes interactive after the player has shown intent twice:
 *
 * 1. **Dwell.** The pointer rested on the cell for `CELL_DWELL_MS`. Clicking
 *    briskly along a row never dwells, so a brisk session never changes.
 * 2. **Approach.** After leaving the cell, consecutive pointer moves land inside
 *    the tooltip box, each a plausible hand-sized step. A cursor that teleports
 *    onto the tooltip in a single jump - which is what a script and only a
 *    script does - never counts, so the cell underneath keeps the click.
 *
 * Both are pure predicates here, so they can be unit tested; TalentCell owns the
 * timers and the DOM.
 */

/** How long the pointer must rest on a cell before its tooltip may go sticky. */
export const CELL_DWELL_MS = 250

/** Consecutive in-box moves needed before the layer takes the pointer. */
export const APPROACH_TICKS = 2

/**
 * Longest single pointer step (px) that still counts as an approach. A hand
 * moving 1000 px/s produces steps well under this; one jump from a cell centre
 * to its neighbour is at least 56 px (44 px cell + 12 px gap) and does not.
 */
export const APPROACH_MAX_STEP = 40

export interface Point {
  x: number
  y: number
}

export interface Box {
  left: number
  top: number
  right: number
  bottom: number
}

/** Inside the box, with an optional tolerance for the sub-pixel edge. */
export function pointInside(p: Point, box: Box, pad = 0): boolean {
  return p.x >= box.left - pad && p.x <= box.right + pad && p.y >= box.top - pad && p.y <= box.bottom + pad
}

/** A step a hand could have made: neither a stand-still nor a teleport. */
export function isApproachStep(step: number, max = APPROACH_MAX_STEP): boolean {
  return Number.isFinite(step) && step > 0 && step <= max
}

/** Distance between two pointer samples; `Infinity` when there is no previous one. */
export function stepLength(from: Point | null, to: Point): number {
  return from === null ? Infinity : Math.hypot(to.x - from.x, to.y - from.y)
}

// --- one tooltip at a time -------------------------------------------------

let owner: { id: string; close: () => void } | undefined

/**
 * Opening a tooltip closes whichever one was open, so hovering another cell
 * always wins over a sticky tooltip that is still hanging around.
 */
export function claimTooltip(id: string, close: () => void): void {
  if (owner && owner.id !== id) owner.close()
  owner = { id, close }
}

export function releaseTooltip(id: string): void {
  if (owner?.id === id) owner = undefined
}

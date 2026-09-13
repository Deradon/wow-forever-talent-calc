/**
 * Crop lookup for the races pages, the races counterpart of `iconCrop.ts`.
 *
 * Racial icons exist only as 36 px PNG crops (stage 9's icon matcher runs on
 * talents), so `iconCrop` is rendered directly and there is no icon name to
 * fall back on - the fallback is the trait's initials, as in the talent grid.
 * The trait row crop behind `source.crop` is the evidence the Details line
 * links at.
 *
 * Backed by the generated `raceCrops.ts`: one static `?url` import per crop the
 * races routes reference, so the URLs land in the races chunk instead of
 * pulling in the 971-entry review registry (`crops.ts`).
 */
import { raceCropUrls } from './raceCrops'

/** URL for a repo-relative crop path, or undefined when the file is not shipped. */
export function raceCropUrl(repoPath: string | undefined): string | undefined {
  if (!repoPath) return undefined
  return raceCropUrls[repoPath.replace(/^\.?\//, '')]
}

export function raceCropCount(): number {
  return Object.keys(raceCropUrls).length
}

/**
 * The race's own crest for the matrix rows. Stage 12 cuts trait icons and the
 * whole panel, not the portrait ring, so there is no crest crop today and every
 * row falls back to the race's initials - the same fallback `ClassIcon` uses
 * when `web/public/icons/` is missing. The lookup is here so that dropping a
 * `_crest.png` beside the panel crop is all it takes to light the column up.
 */
export function raceCrestUrl(raceId: string): string | undefined {
  for (const name of ['_crest.png', '_portrait.png']) {
    const url = raceCropUrl(`data/review/races/${raceId}/${name}`)
    if (url) return url
  }
  return undefined
}

/**
 * Crop-icon lookup for the calculator. Backed by iconCrops.ts, which
 * scripts/gen-data-index.mjs regenerates with one static `?url` import per
 * talent whose `iconSource` is `"crop"` - 73 entries instead of the 971 in
 * crops.ts, which is review-only and code-split away from the class route.
 */
import { iconCropUrls } from './iconCrops'

/** URL for a talent's `iconCrop` path, or undefined when the file is not shipped. */
export function iconCropUrl(repoPath: string | undefined): string | undefined {
  if (!repoPath) return undefined
  return iconCropUrls[repoPath.replace(/^\.?\//, '')]
}

export function iconCropCount(): number {
  return Object.keys(iconCropUrls).length
}

/**
 * Crop lookup for the spell pages, the spellbook counterpart of `raceCrop.ts`.
 *
 * `data/review/spells/` is 765 files and 14 MB - half again as much as the rest
 * of `data/review/` put together - so a single registry the way `raceCrops.ts`
 * does it would put the URLs of every class's spellbook into whichever chunk
 * touched it. Instead `scripts/gen-data-index.mjs` writes one module per class
 * under `spellCrops/spells-<class>.ts`, and the glob below is **lazy**: each
 * module becomes its own chunk, and opening `#/spells/mage` downloads the
 * mage's crop URLs and nobody else's. The overview at `#/spells` renders no
 * crop and loads none.
 *
 * `crops.ts`, the review route's registry of everything under `data/review/`,
 * excludes this directory for the same reason.
 */
type CropModule = { spellCropUrls: Record<string, string> }

const modules = import.meta.glob('./spellCrops/*.ts') as Record<string, () => Promise<CropModule>>

/** Path -> URL for one class; `spellCropUrl` reads it. */
export type SpellCrops = Record<string, string>

const EMPTY: SpellCrops = {}

const cache = new Map<string, Promise<SpellCrops>>()

/** The crop URLs of one class, fetched with that class's chunk. */
export function loadSpellCrops(classId: string): Promise<SpellCrops> {
  let p = cache.get(classId)
  if (!p) {
    const load = modules[`./spellCrops/spells-${classId}.ts`]
    p = load ? load().then((m) => m.spellCropUrls) : Promise.resolve(EMPTY)
    cache.set(classId, p)
  }
  return p
}

/** URL for a repo-relative crop path, or undefined when the file is not shipped. */
export function spellCropUrl(crops: SpellCrops, repoPath: string | undefined): string | undefined {
  if (!repoPath) return undefined
  return crops[repoPath.replace(/^\.?\//, '')]
}

/** The class ids that have a crop module at all; the tests walk it. */
export function spellCropClasses(): string[] {
  return Object.keys(modules)
    .map((p) => p.slice(p.lastIndexOf('/') + 1).replace(/^spells-/, '').replace(/\.ts$/, ''))
    .sort()
}

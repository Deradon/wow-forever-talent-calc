/**
 * Race data loading, the races half of `load.ts`.
 *
 * `data/races/<race>.json` is globbed lazily, so `#/races/<race>` fetches one
 * race chunk and nothing else - the same deal `#/<class>` gets. The overview at
 * `#/races` loads no race file at all: it runs off `races-index.json`, which
 * `scripts/gen-data-index.mjs` writes at build time.
 *
 * `matrix.json` sits in the same folder and is *not* a race; it is excluded
 * here and consumed by the index generator instead, so nothing in the browser
 * ever fetches it.
 */
import type { RaceData } from './schema.races'

type Loader = () => Promise<unknown>

const files = import.meta.glob(['../../../data/races/*.json', '!../../../data/races/matrix.json'], {
  import: 'default',
}) as Record<string, Loader>

function stem(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1).replace(/\.json$/, '')
}

// The negative glob above keeps matrix.json out; without it vite emits a chunk
// for a file nothing ever imports.
const registry = new Map<string, Loader>(Object.entries(files).map(([path, load]) => [stem(path), load]))

export function listRaces(): string[] {
  return [...registry.keys()].sort()
}

export function hasRace(id: string): boolean {
  return registry.has(id)
}

/**
 * Production ships no validator (performance review P-3): the race files are
 * checked at build time by `validateRaces.test.ts` and in CI by
 * `pipeline/validate_races.py`, so re-parsing them in every visitor's browser
 * would only cost bundle size. In dev the zod mirror still runs, and the
 * dynamic import is dead code once `import.meta.env.DEV` folds to `false`.
 */
async function validated(raw: unknown, label: string): Promise<RaceData> {
  if (import.meta.env.DEV) {
    const { parseRace } = await import('./races.zod')
    return parseRace(raw, label)
  }
  return raw as RaceData
}

const cache = new Map<string, Promise<RaceData>>()

export function loadRace(id: string): Promise<RaceData> {
  const load = registry.get(id)
  if (!load) return Promise.reject(new Error(`Unknown race "${id}"`))
  let p = cache.get(id)
  if (!p) {
    p = load().then((raw) => validated(raw, `races/${id}.json`))
    cache.set(id, p)
  }
  return p
}

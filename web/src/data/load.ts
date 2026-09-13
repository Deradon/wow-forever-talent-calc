/**
 * Class data loading. Canonical classes come from data/talents/*.json (lazy,
 * one chunk per class). While no real class exists, the example classes from
 * data/examples/*.json and web/tests/fixtures/*.json are included when
 * VITE_INCLUDE_EXAMPLES=1 (set by .env.development and .env.e2e).
 * Precedence per class id: talents > examples > fixtures.
 */
import type { ClassData } from './schema'

type Loader = () => Promise<unknown>

const canonical = import.meta.glob('../../../data/talents/*.json', { import: 'default' }) as Record<string, Loader>
const examples = import.meta.glob('../../../data/examples/*.json', { import: 'default' }) as Record<string, Loader>
const fixtures = import.meta.glob('../../tests/fixtures/*.json', { import: 'default' }) as Record<string, Loader>

export const includeExamples: boolean = import.meta.env.VITE_INCLUDE_EXAMPLES === '1'

export type ClassOrigin = 'talents' | 'examples' | 'fixtures'

export interface ClassEntry {
  id: string
  origin: ClassOrigin
  load: Loader
}

function stem(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1).replace(/\.json$/, '')
}

function collect(): Map<string, ClassEntry> {
  const map = new Map<string, ClassEntry>()
  const sources: [ClassOrigin, Record<string, Loader>][] = [['talents', canonical]]
  if (includeExamples) sources.push(['examples', examples], ['fixtures', fixtures])
  for (const [origin, files] of sources) {
    for (const [path, load] of Object.entries(files)) {
      const id = stem(path)
      if (!map.has(id)) map.set(id, { id, origin, load })
    }
  }
  return map
}

const registry = collect()

export function listClasses(): ClassEntry[] {
  return [...registry.values()].sort((a, b) => a.id.localeCompare(b.id))
}

export function hasClass(id: string): boolean {
  return registry.has(id)
}

/**
 * Production ships no validator: the class files are validated at build time by
 * validateData.test.ts and `validate-data` in CI, so re-checking them in every
 * visitor's browser only cost ~25 kB gzip (performance review P-3). In dev the
 * zod mirror still runs, and the dynamic import is dead code once
 * `import.meta.env.DEV` folds to `false`, so zod is dropped from the bundle.
 */
async function validated(raw: unknown, label: string): Promise<ClassData> {
  if (import.meta.env.DEV) {
    const { parseClass } = await import('./schema.zod')
    return parseClass(raw, label)
  }
  return raw as ClassData
}

const cache = new Map<string, Promise<ClassData>>()

export function loadClass(id: string): Promise<ClassData> {
  const entry = registry.get(id)
  if (!entry) return Promise.reject(new Error(`Unknown class "${id}"`))
  let p = cache.get(id)
  if (!p) {
    p = entry.load().then((raw) => validated(raw, `${entry.origin}/${id}.json`))
    cache.set(id, p)
  }
  return p
}

export function displayName(id: string): string {
  return id.replace(/(^|-)([a-z])/g, (_, sep: string, c: string) => `${sep ? ' ' : ''}${c.toUpperCase()}`)
}

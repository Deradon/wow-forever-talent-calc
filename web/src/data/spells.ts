/**
 * Spellbook data loading, the spells half of `load.ts` and `races.ts`.
 *
 * `data/spells/<class>.json` is globbed lazily, so `#/spells/<class>` fetches
 * one class file and nothing else. The overview at `#/spells` loads none of
 * them: it runs off `spells-index.json`, which `scripts/gen-data-index.mjs`
 * writes at build time.
 *
 * Eight files, not nine: priest was never on screen, so it has no file, and
 * `hasSpells('priest')` is false rather than an empty page.
 */
import type { SpellData } from './schema.spells'

type Loader = () => Promise<unknown>

const files = import.meta.glob('../../../data/spells/*.json', { import: 'default' }) as Record<string, Loader>

function stem(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1).replace(/\.json$/, '')
}

const registry = new Map<string, Loader>(Object.entries(files).map(([path, load]) => [stem(path), load]))

export function listSpellClasses(): string[] {
  return [...registry.keys()].sort()
}

export function hasSpells(id: string): boolean {
  return registry.has(id)
}

/**
 * Production ships no validator (performance review P-3): the files are checked
 * at build time by `validateSpells.test.ts` and in CI by
 * `pipeline/validate_spells.py`. In dev the zod mirror still runs, and the
 * dynamic import is dead code once `import.meta.env.DEV` folds to `false`.
 */
async function validated(raw: unknown, label: string): Promise<SpellData> {
  if (import.meta.env.DEV) {
    const { parseSpells } = await import('./spells.zod')
    return parseSpells(raw, label)
  }
  return raw as SpellData
}

const cache = new Map<string, Promise<SpellData>>()

export function loadSpells(id: string): Promise<SpellData> {
  const load = registry.get(id)
  if (!load) return Promise.reject(new Error(`No spellbook for "${id}"`))
  let p = cache.get(id)
  if (!p) {
    p = load().then((raw) => validated(raw, `spells/${id}.json`))
    cache.set(id, p)
  }
  return p
}

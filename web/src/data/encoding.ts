/**
 * Encoding versions (data/encoding/v<N>.json) and migrations
 * (data/encoding/migrations/v<A>-v<B>.json), see DATA-SCHEMA.md section 8.
 *
 * All versions are shipped (they are small). Real files under data/ are
 * globbed eagerly; the fixture copies under web/tests/fixtures/encoding are
 * merged in only when VITE_INCLUDE_EXAMPLES is set (dev default) and never
 * override a real file of the same version.
 */
import type { ClassData } from './schema'
import { defaultTreeOrder, rowMajor } from '../rules/points'

export interface EncodingClass {
  trees: string[]
  order: Record<string, string[]>
}

export interface EncodingFile {
  version: number
  createdAt?: string
  note?: string
  classes: Record<string, EncodingClass>
}

export interface MigrationClass {
  renamed?: Record<string, string>
  removed?: string[]
  moved?: Record<string, { from: string; to: string }>
}

export interface MigrationFile {
  from: number
  to: number
  classes: Record<string, MigrationClass>
}

export interface EncodingRegistry {
  versions: Record<number, EncodingFile>
  migrations: MigrationFile[]
}

/** The talent order of one class in one version: tree ids and per-tree talent ids. */
export interface ClassOrder {
  trees: string[]
  order: Record<string, string[]>
}

export function emptyRegistry(): EncodingRegistry {
  return { versions: {}, migrations: [] }
}

export function buildRegistry(files: EncodingFile[], migrations: MigrationFile[]): EncodingRegistry {
  const versions: Record<number, EncodingFile> = {}
  for (const f of files) versions[f.version] ??= f
  return { versions, migrations: [...migrations].sort((a, b) => a.from - b.from) }
}

/**
 * Order for `(classId, version)`. Falls back to the class file's own order
 * (pages flattened, talents row-major) for the class's current dataVersion
 * when the encoding file does not list the class, so example classes and
 * not-yet-published classes still get links.
 */
export function orderFor(registry: EncodingRegistry, cls: ClassData, version: number): ClassOrder | undefined {
  const entry = registry.versions[version]?.classes[cls.class]
  if (entry) return { trees: entry.trees, order: entry.order }
  if (version === cls.dataVersion) return derivedOrder(cls)
  return undefined
}

export function derivedOrder(cls: ClassData): ClassOrder {
  const trees = defaultTreeOrder(cls)
  const order: Record<string, string[]> = {}
  for (const tree of cls.trees) order[tree.id] = rowMajor(tree)
  return { trees, order }
}

/** Migration chain `from -> from+1 -> ... -> to`, or undefined when a step is missing. */
export function migrationChain(registry: EncodingRegistry, from: number, to: number): MigrationFile[] | undefined {
  const chain: MigrationFile[] = []
  let v = from
  while (v < to) {
    const step = registry.migrations.find((m) => m.from === v && m.to > v)
    if (!step || step.to > to) return undefined
    chain.push(step)
    v = step.to
  }
  return chain
}

// --- loading -----------------------------------------------------------------

const real = import.meta.glob('../../../data/encoding/v*.json', { eager: true, import: 'default' }) as Record<string, EncodingFile>
const realMigrations = import.meta.glob('../../../data/encoding/migrations/*.json', { eager: true, import: 'default' }) as Record<string, MigrationFile>
const fixtures = import.meta.glob('../../tests/fixtures/encoding/v*.json', { eager: true, import: 'default' }) as Record<string, EncodingFile>

export const includeExamples: boolean = import.meta.env.VITE_INCLUDE_EXAMPLES === '1'

let cached: EncodingRegistry | undefined

export function loadRegistry(): EncodingRegistry {
  if (cached) return cached
  const files = [...Object.values(real), ...(includeExamples ? Object.values(fixtures) : [])]
  cached = buildRegistry(files, Object.values(realMigrations))
  return cached
}

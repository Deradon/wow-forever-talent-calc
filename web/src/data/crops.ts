/**
 * Frame crops under data/review/<class>/<tree>/*.png, keyed by their
 * repo-relative path as the class files spell it (`iconCrop`, `source.crop`).
 *
 * The glob is eager: it yields URL strings only (the PNGs themselves are
 * emitted as assets and fetched by the browser on demand), so nine classes
 * add roughly 60 kB of paths to the bundle instead of hundreds of tiny
 * chunks. vite.config.ts keeps these files out of base64 inlining.
 */
const files = import.meta.glob('../../../data/review/*/*/*.png', {
  query: '?url',
  import: 'default',
  eager: true,
}) as Record<string, string>

const byPath = new Map<string, string>()
for (const [key, url] of Object.entries(files)) byPath.set(key.replace(/^(\.\.\/)+/, ''), url)

/** URL for a repo-relative crop path (`data/review/paladin/holy/x.icon.png`), or undefined when the file is not shipped. */
export function cropUrl(repoPath: string | undefined): string | undefined {
  if (!repoPath) return undefined
  return byPath.get(repoPath.replace(/^\.?\//, ''))
}

export function cropCount(): number {
  return byPath.size
}

/**
 * Every frame crop under data/review/<class>/<tree>/*.png, keyed by its
 * repo-relative path as the class files spell it (`iconCrop`, `source.crop`).
 *
 * The spellbook crops match the same shape (data/review/spells/<class>/*.png)
 * and are excluded: they are 765 files and 14 MB, the review route does not
 * show them, and the spell pages get them one class at a time through
 * `spellCrop.ts`.
 *
 * Review-only: one path->URL pair per talent and race crop, tens of kB of the
 * bundle. The single importer
 * is ReviewPage, which App.tsx loads with React.lazy, so this whole registry
 * now lands in the review chunk instead of every visitor's first load
 * (performance review P-2). The calculator's own 73 crop icons come from the
 * generated iconCrops.ts instead.
 *
 * The glob is eager: it yields URL strings only (the PNGs themselves are
 * emitted as assets and fetched by the browser on demand).
 * vite.config.ts keeps these files out of base64 inlining.
 */
import { iconCropUrls } from './iconCrops'

const files = import.meta.glob(['../../../data/review/*/*/*.png', '!../../../data/review/spells/**'], {
  query: '?url',
  import: 'default',
  eager: true,
}) as Record<string, string>

const byPath = new Map<string, string>(Object.entries(iconCropUrls))
for (const [key, url] of Object.entries(files)) byPath.set(key.replace(/^(\.\.\/)+/, ''), url)

/** URL for a repo-relative crop path (`data/review/paladin/holy/x.icon.png`), or undefined when the file is not shipped. */
export function cropUrl(repoPath: string | undefined): string | undefined {
  if (!repoPath) return undefined
  return byPath.get(repoPath.replace(/^\.?\//, ''))
}

export function cropCount(): number {
  return byPath.size
}

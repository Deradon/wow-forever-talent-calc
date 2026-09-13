/// <reference types="node" />
/**
 * Every crop a canonical class file points at (iconCrop, source.crop) must be
 * resolvable through the glob registry, so the UI never silently shows
 * initials for a talent whose crop exists in the repo.
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { cropCount, cropUrl } from './crops'
import { parseClass } from './schema.zod'

const here = fileURLToPath(new URL('.', import.meta.url))
const dir = join(here, '../../../data/talents')
const files = existsSync(dir) ? readdirSync(dir).filter((f) => f.endsWith('.json')) : []

describe('crops', () => {
  it('returns undefined for unknown or empty paths', () => {
    expect(cropUrl(undefined)).toBeUndefined()
    expect(cropUrl('data/review/nope/nope/nope.png')).toBeUndefined()
  })

  it('accepts a leading ./ or /', () => {
    if (cropCount() === 0) return
    const [cls] = files
    if (!cls) return
    const data = parseClass(JSON.parse(readFileSync(join(dir, cls), 'utf8')))
    const crop = data.trees[0]?.talents[0]?.source.crop
    if (!crop) return
    expect(cropUrl(`./${crop}`)).toBe(cropUrl(crop))
    expect(cropUrl(`/${crop}`)).toBe(cropUrl(crop))
  })

  for (const file of files) {
    it(`${file}: every iconCrop and source.crop is shipped`, () => {
      const cls = parseClass(JSON.parse(readFileSync(join(dir, file), 'utf8')), file)
      for (const tree of cls.trees) {
        for (const t of tree.talents) {
          if (t.iconSource === 'crop') expect(cropUrl(t.iconCrop), `${t.id} iconCrop ${t.iconCrop}`).toBeDefined()
          if (t.source.crop) expect(cropUrl(t.source.crop), `${t.id} source.crop ${t.source.crop}`).toBeDefined()
        }
      }
    })
  }
})

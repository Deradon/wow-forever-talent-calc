/**
 * Generates src/data/classic-index.json from data/prior/classic-era/talents.json.
 *
 * The import flow (brief "UI and UX improvements", idea 9) decodes a Wowhead
 * Classic build string against the Classic tab order: one digit per talent,
 * per tab, row-major. Only the tab order and the talent *names* are needed for
 * that - the mapping into Forever is by name - so this strips the 500 kB prior
 * down to ~12 kB that can be fetched on demand.
 *
 * Run by hand from web/:  npm run gen
 * src/data/classicIndex.test.ts generates into a temporary directory and
 * compares, so a stale commit fails the unit suite.
 */
import { existsSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const PRIOR = resolve(here, '../../data/prior/classic-era/talents.json')
const OUT = resolve(here, '../src/data/classic-index.json')

/** @returns {{classes: Record<string, {className: string, trees: {id: string, name: string, talents: [string, number][]}[]}>}} */
export function buildIndex(prior) {
  const classes = {}
  for (const classId of Object.keys(prior.classes).sort()) {
    const cls = prior.classes[classId]
    const trees = [...cls.trees]
      .sort((a, b) => a.order - b.order)
      .map((tree) => ({
        id: tree.id,
        name: tree.name,
        // Row-major, which is the digit order of a Wowhead tab segment.
        talents: [...tree.talents]
          .sort((a, b) => a.row - b.row || a.col - b.col)
          .map((t) => [t.name, t.maxRank]),
      }))
    classes[classId] = { className: cls.className, trees }
  }
  return { source: 'data/prior/classic-era/talents.json', classes }
}

/**
 * `root` defaults to `web/`. `src/data/classicIndex.test.ts` passes a temporary
 * directory so that it compares a fresh generation against the committed file
 * instead of against a file it has just rewritten.
 */
export function generate(root = resolve(here, '..')) {
  const prior = JSON.parse(readFileSync(PRIOR, 'utf8'))
  const index = buildIndex(prior)
  const text = JSON.stringify(index, null, 1) + '\n'
  const out = join(root, 'src/data/classic-index.json')
  let before = ''
  try {
    before = readFileSync(out, 'utf8')
  } catch {
    /* first run */
  }
  if (before !== text) {
    mkdirSync(dirname(out), { recursive: true })
    const tmp = `${out}.tmp-${process.pid}`
    try {
      writeFileSync(tmp, text)
      renameSync(tmp, out)
    } finally {
      if (existsSync(tmp)) rmSync(tmp)
    }
  }
  return { text, changed: before !== text }
}

export function priorPath() {
  return PRIOR
}
export function outPath() {
  return OUT
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { changed } = generate()
  console.log(changed ? `wrote ${OUT}` : `${OUT} already current`)
}

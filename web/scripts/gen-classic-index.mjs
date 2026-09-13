/**
 * Generates src/data/classic-index.json from data/prior/classic-era/talents.json.
 *
 * The import flow (brief "UI and UX improvements", idea 9) decodes a Wowhead
 * Classic build string against the Classic tab order: one digit per talent,
 * per tab, row-major. Only the tab order and the talent *names* are needed for
 * that - the mapping into Forever is by name - so this strips the 500 kB prior
 * down to ~12 kB that can be fetched on demand.
 *
 * Run by hand from web/:  node scripts/gen-classic-index.mjs
 * src/data/classicIndex.test.ts regenerates and compares, so a stale commit
 * fails the unit suite.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

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

export function generate() {
  const prior = JSON.parse(readFileSync(PRIOR, 'utf8'))
  const index = buildIndex(prior)
  const text = JSON.stringify(index, null, 1) + '\n'
  let before = ''
  try {
    before = readFileSync(OUT, 'utf8')
  } catch {
    /* first run */
  }
  if (before !== text) writeFileSync(OUT, text)
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

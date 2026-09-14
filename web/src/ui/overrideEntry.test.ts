/// <reference types="node" />
/**
 * The copied text is only worth a button if it validates. These tests check the
 * emitted entry against the two things that judge it in the pipeline:
 *
 * - `data/schema/class.schema.json`, from which `pipeline/validate.py` builds
 *   the overrides schema (section 6.2): entry keys, `set` keys and
 *   `set.source` keys all have to exist there, the required fields have to be
 *   present and non-empty, and `at` has to match the `rfc3339` pattern.
 * - `KEY_ORDER` in `pipeline/validate.py`, which decides the byte-identical
 *   canonical form (rule R12). The order is read out of the file so a change
 *   there fails here rather than in a reviewer's terminal.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { Talent, Tree } from '../data/schema'
import type { ReviewRow } from './review'
import { buildOverrideEntry, canonicalDump, overrideEntriesText, overrideEntryText, wrongReadingUrl } from './overrideEntry'

const here = fileURLToPath(new URL('.', import.meta.url))
const schema = JSON.parse(readFileSync(`${here}../../../data/schema/class.schema.json`, 'utf8')) as {
  $defs: Record<string, { properties?: Record<string, unknown>; pattern?: string }>
}
const validatePy = readFileSync(`${here}../../../pipeline/validate.py`, 'utf8')

/** `KEY_ORDER["<name>"] = [...]` out of pipeline/validate.py. */
function keyOrder(name: string): string[] {
  const at = validatePy.indexOf(`    "${name}": [`)
  expect(at, `KEY_ORDER[${name}] in pipeline/validate.py`).toBeGreaterThan(-1)
  const body = validatePy.slice(at + name.length + 8, validatePy.indexOf('],', at))
  return [...body.matchAll(/"([^"]+)"/g)].map((m) => m[1]!)
}

/** Entry keys the overrides schema allows; `docs/DATA-SCHEMA.md` section 6.2. */
const ENTRY_KEYS = ['talent', 'tree', 'set', 'unset', 'rename', 'delete', 'add', 'reason', 'by', 'at']

const talent: Talent = {
  id: 'improved-rend',
  name: 'Improved Rend',
  row: 1,
  col: 2,
  maxRank: 3,
  icon: 'ability_gouge',
  iconSource: 'classic',
  description: 'Increases the damage of your Rend ability by {0}%.',
  ranks: [[15], [25], [35]],
  ranksObserved: [1],
  ranksSource: 'extrapolated',
  source: {
    kind: 'video',
    video: 'DxtVEhjyROU',
    t: 14472,
    frame: 868320,
    crop: 'data/review/warrior/arms/improved-rend.png',
    confidence: 0.62,
    reader: 'qwen3-vl-8b',
    reviewed: false,
  },
}
const tree = { id: 'arms', name: 'Arms', order: 0, rows: 7, cols: 4, talents: [talent] } as unknown as Tree
const row: ReviewRow = { tree, talent, confidence: 0.62, group: 0 }
const at = '2026-09-14T09:00:00Z'

describe('buildOverrideEntry', () => {
  it('addresses the record by tree and pre-rename id', () => {
    const entry = buildOverrideEntry(row, { at })
    expect(entry.talent).toBe('improved-rend')
    expect(entry.tree).toBe('arms')
  })

  it('prefills set with the current name and description so the reviewer edits in place', () => {
    const entry = buildOverrideEntry(row, { at })
    expect(entry.set.name).toBe(talent.name)
    expect(entry.set.description).toBe(talent.description)
    expect(entry.set.source.reviewed).toBe(true)
  })

  it('leaves reason and by as TODO, and names the crop that has to be checked', () => {
    const entry = buildOverrideEntry(row, { at })
    expect(entry.by).toBe('TODO')
    expect(entry.reason).toContain('TODO')
    expect(entry.reason).toContain('data/review/warrior/arms/improved-rend.png')
    expect(buildOverrideEntry(row, { at, by: ' deradon ' }).by).toBe('deradon')
  })

  it('stamps an RFC 3339 time that matches the schema pattern', () => {
    const pattern = new RegExp(schema.$defs.rfc3339!.pattern!)
    expect(pattern.test(buildOverrideEntry(row, { at }).at)).toBe(true)
    expect(pattern.test(buildOverrideEntry(row).at)).toBe(true)
  })

  it('falls back to a crop-free reason for a non-video source', () => {
    const manual = { ...talent, source: { kind: 'manual', reviewed: false } } as Talent
    expect(buildOverrideEntry({ ...row, talent: manual }, { at }).reason).toContain('on the review route')
  })
})

describe('the emitted shape against data/schema/class.schema.json', () => {
  const entry = buildOverrideEntry(row, { at })

  it('uses only keys the overrides schema declares (additionalProperties: false)', () => {
    for (const key of Object.keys(entry)) expect(ENTRY_KEYS).toContain(key)
  })

  it('carries every required field, non-empty', () => {
    for (const key of ['talent', 'tree', 'reason', 'by', 'at'] as const) expect(entry[key].length).toBeGreaterThan(0)
    // anyOf: an entry has to do one of set/unset/rename/delete/add.
    expect(entry.set).toBeTruthy()
  })

  it('sets only real talent fields, and only real source fields', () => {
    const talentProps = Object.keys(schema.$defs.talent!.properties!)
    const sourceProps = Object.keys(schema.$defs.source!.properties!)
    for (const key of Object.keys(entry.set)) expect(talentProps).toContain(key)
    for (const key of Object.keys(entry.set.source)) expect(sourceProps).toContain(key)
  })

  it('matches the talentId and treeId patterns', () => {
    expect(new RegExp(schema.$defs.talentId!.pattern!).test(entry.talent)).toBe(true)
    expect(new RegExp(schema.$defs.treeId!.pattern!).test(entry.tree)).toBe(true)
  })

  it('does not set iconCrop or ranksPrior, which the talent if/then rules forbid without their partner field', () => {
    expect(entry.set).not.toHaveProperty('iconCrop')
    expect(entry.set).not.toHaveProperty('ranksPrior')
  })
})

describe('canonical form', () => {
  it('emits keys in the pipeline serializer order', () => {
    const entry = buildOverrideEntry(row, { at })
    const order = keyOrder('override').filter((k) => k in entry)
    expect(Object.keys(entry)).toEqual(order)
    expect(Object.keys(entry.set)).toEqual(keyOrder('talent').filter((k) => k in entry.set))
    expect(Object.keys(entry.set.source)).toEqual(keyOrder('source').filter((k) => k in entry.set.source))
  })

  it('formats like pipeline/validate.py _dump: two spaces a level, short scalar arrays inline', () => {
    expect(canonicalDump({ a: 1, b: [1, 2, 3] })).toBe('{\n  "a": 1,\n  "b": [1, 2, 3]\n}')
    expect(canonicalDump({ a: [] })).toBe('{\n  "a": []\n}')
    expect(canonicalDump({ a: {} })).toBe('{\n  "a": {}\n}')
    expect(canonicalDump([{ a: 1 }])).toBe('[\n  {\n    "a": 1\n  }\n]')
    // 30 numbers do not fit in 100 characters, so the array breaks
    expect(canonicalDump(Array.from({ length: 30 }, (_, i) => i))).toContain('\n')
  })

  it('indents one entry to its place inside the overrides array', () => {
    const text = overrideEntryText(buildOverrideEntry(row, { at }))
    expect(text.startsWith('    {\n      "talent": "improved-rend",')).toBe(true)
    expect(text.endsWith('\n    }')).toBe(true)
    expect(JSON.parse(text)).toMatchObject({ talent: 'improved-rend', tree: 'arms' })
  })

  it('emits several entries as array elements, parseable once wrapped in brackets', () => {
    const entries = [buildOverrideEntry(row, { at }), buildOverrideEntry({ ...row, talent: { ...talent, id: 'mortal-strike' } }, { at })]
    const text = overrideEntriesText(entries)
    expect(text).not.toMatch(/^\s*\[/)
    const parsed = JSON.parse(`[${text}]`) as { talent: string }[]
    expect(parsed.map((e) => e.talent)).toEqual(['improved-rend', 'mortal-strike'])
  })

  it('pastes into a real overrides file and still parses', () => {
    const file = readFileSync(`${here}../../../data/overrides/warrior.json`, 'utf8')
    const pasted = file.replace('  "overrides": [\n', `  "overrides": [\n${overrideEntryText(buildOverrideEntry(row, { at }))},\n`)
    const doc = JSON.parse(pasted) as { overrides: { talent: string }[] }
    expect(doc.overrides[0]!.talent).toBe('improved-rend')
  })
})

describe('wrongReadingUrl', () => {
  const url = new URL(wrongReadingUrl(row, 'warrior', 'https://github.com/o/r'))

  it('points at the issue form and prefills the fields by their form id', () => {
    expect(url.origin + url.pathname).toBe('https://github.com/o/r/issues/new')
    expect(url.searchParams.get('template')).toBe('wrong-reading.yml')
    expect(url.searchParams.get('class')).toBe('warrior')
    expect(url.searchParams.get('record')).toBe('arms/improved-rend')
    expect(url.searchParams.get('shown')).toContain('Improved Rend')
  })

  it('links back at the published site with the talent pinned, not at localhost', () => {
    const link = url.searchParams.get('link')!
    expect(link).toBe('https://deradon.github.io/wow-forever-talent-calc/#/warrior?sel=improved-rend')
  })

  it('uses only field ids the issue form declares', () => {
    const form = readFileSync(`${here}../../../.github/ISSUE_TEMPLATE/wrong-reading.yml`, 'utf8')
    const ids = [...form.matchAll(/^\s{4}id:\s*(\S+)/gm)].map((m) => m[1]!)
    for (const key of url.searchParams.keys()) {
      if (key === 'template' || key === 'labels') continue
      expect(ids).toContain(key)
    }
  })
})

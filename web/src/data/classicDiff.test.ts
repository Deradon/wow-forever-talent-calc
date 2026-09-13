/**
 * The Classic Era diff: the classification rules, the exclusive name matching
 * behind them, and the generated src/data/classic-diff.json that ships them.
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import {
  buildClassicDiff,
  cellBase,
  classifyTalent,
  compareDescriptions,
  diffClass,
  expected,
  matchTrees,
  maskNumbers,
  normalizeName,
  normalizeText,
  rankSeries,
} from '../../scripts/gen-data-index.mjs'
import { compactDiff } from '../../scripts/diffWords.mjs'
import { changeOf, changedCount, hasClassicDiff, removedTalents } from '../ui/classicDiff'
import { diffWords } from '../ui/review'
import diff from './classic-diff.json'
import classicText from './classic-text.json'

const here = fileURLToPath(new URL('.', import.meta.url))

const cell = (
  over: Partial<{
    tree: string
    treeName: string
    row: number
    col: number
    maxRank: number
    text: string
    sameTree: boolean
  }> = {},
) => ({
  tree: 'arms',
  treeName: 'Arms',
  row: 2,
  col: 1,
  maxRank: 5,
  text: 'Increases your chance to hit by 1%.',
  ...over,
})

describe('normalizeName', () => {
  it('ignores case, apostrophes and punctuation', () => {
    expect(normalizeName("Nature's Grasp")).toBe('natures grasp')
    expect(normalizeName('Nature’s  Grasp')).toBe('natures grasp')
    expect(normalizeName('One-Handed Weapon Specialization')).toBe('one handed weapon specialization')
    expect(normalizeName('  Enrage ')).toBe('enrage')
  })

  it('never collapses two different talents onto one key', () => {
    expect(normalizeName('Improved Wrath')).not.toBe(normalizeName('Improved Wrench'))
  })
})

describe('classifyTalent', () => {
  it('calls a talent with no Classic counterpart new, and carries no prior', () => {
    const entry = classifyTalent(cell(), undefined)
    expect(entry).toEqual({ status: 'new' })
  })

  it('calls an identical cell unchanged', () => {
    expect(classifyTalent(cell(), cell()).status).toBe('same')
  })

  it('reports a move for a different row, and records where it went', () => {
    const entry = classifyTalent(cell(), cell({ row: 4 }))
    expect(entry.status).toBe('moved')
    expect(entry.prior?.movedRow).toBe(true)
    expect(entry.row).toBe(cell().row)
  })

  // Round 3, the owner's call: rows gate points, columns are ordering, and Forever
  // reshuffled the order in most trees. A column-only change is not news.
  it('does not report a move when only the column changed', () => {
    const entry = classifyTalent(cell(), cell({ col: 3 }))
    expect(entry.status).toBe('same')
    expect(entry.prior?.movedCol).toBe(true)
    expect(entry.prior?.movedRow).toBeUndefined()
    expect(entry).not.toHaveProperty('row')
    // the losing categories still decide the status, and the old cell stays on record
    expect(classifyTalent(cell({ col: 3, maxRank: 3 }), cell({ maxRank: 5 })).status).toBe('rank-changed')
    expect(classifyTalent(cell({ col: 3 }), cell()).prior?.col).toBe(cell().col)
  })

  it('reports a move for a different tree, and says so on the entry', () => {
    const entry = classifyTalent(cell(), cell({ tree: 'fury', treeName: 'Fury', sameTree: false }))
    expect(entry.status).toBe('moved')
    expect(entry.prior?.movedTree).toBe(true)
  })

  // The bug this round exists to fix: Forever renamed priest Shadow to Shadow
  // Magic, and round 1 called every talent in it "Moved from Shadow, row 7".
  it('does not call a renamed tree a move, and never sets movedTree for one', () => {
    const entry = classifyTalent(
      cell({ tree: 'shadow-magic' }),
      cell({ tree: 'shadow', treeName: 'Shadow', sameTree: true }),
    )
    expect(entry.status).toBe('same')
    expect(entry.prior?.movedTree).toBeUndefined()
  })

  it('reports a rank change only when the cell itself did not move', () => {
    expect(classifyTalent(cell({ maxRank: 3 }), cell({ maxRank: 5 })).status).toBe('rank-changed')
    // Both at once: the cell is what the player is looking at, so the move wins,
    // and the prior still carries the old rank count for anyone who wants it.
    const both = classifyTalent(cell({ row: 4, maxRank: 3 }), cell({ maxRank: 5 }))
    expect(both.status).toBe('moved')
    expect(both.prior?.maxRank).toBe(5)
  })

  it('keeps the Classic cell on every matched entry', () => {
    const { text, ...expectedCell } = cell()
    void text
    expect(classifyTalent(cell({ row: 4 }), cell()).prior).toEqual({ ...expectedCell, movedRow: true })
  })

  it('reports a rewrite when the words moved, with the word diff attached', () => {
    const entry = classifyTalent(
      cell({ text: 'Increases your chance to dodge by 1%.' }),
      cell({ text: 'Increases your chance to hit by 1%.' }),
    )
    expect(entry.status).toBe('text-changed')
    expect(entry.textChange).toBe('text')
    expect(entry.classic?.text).toBe('Increases your chance to hit by 1%.')
    expect(entry.classic?.diff).toEqual(
      expect.arrayContaining([
        ['-', 'hit'],
        ['+', 'dodge'],
      ]),
    )
  })

  it('reports a value change when only the numbers moved, old -> new per slot', () => {
    const entry = classifyTalent(
      cell({ text: 'Increases your chance to hit by 20%.' }),
      cell({ text: 'Increases your chance to hit by 15%.' }),
    )
    expect(entry.status).toBe('values-changed')
    expect(entry.textChange).toBe('values')
    expect(entry.values).toEqual([['15%', '20%']])
  })

  it('forgives whitespace, punctuation, case and unit spelling', () => {
    const entry = classifyTalent(
      cell({ text: 'Stuns  the target for 3 seconds' }),
      cell({ text: 'Stuns the target for 3 sec.' }),
    )
    expect(entry.status).toBe('same')
    expect(entry.textChange).toBeUndefined()
  })

  it('ranks a move above a rewrite: the cell is what the player is looking at', () => {
    const entry = classifyTalent(
      cell({ row: 4, text: 'Something else entirely.' }),
      cell({ text: 'Increases your chance to hit by 1%.' }),
    )
    expect(entry.status).toBe('moved')
    // ...and the rewrite is still on the record, so the card can show it.
    expect(entry.textChange).toBe('text')
  })
})

describe('normalizeText and maskNumbers', () => {
  it('folds case, punctuation, whitespace and unit spellings onto one form', () => {
    expect(normalizeText('Lasts 15 seconds.')).toBe(normalizeText('lasts 15 sec'))
    expect(normalizeText('Increases  range by 5 yards')).toBe(normalizeText('Increases range by 5 yd.'))
    expect(normalizeText('every 3 minutes')).toBe(normalizeText('every 3 min'))
  })

  it('keeps the digits of a decimal together', () => {
    expect(normalizeText('deals 1.5 damage.')).toBe('deals 1.5 damage')
  })

  it('masks numbers with their percent sign, in order', () => {
    expect(maskNumbers('by 15% and 2.5 for 30 sec')).toEqual({
      masked: 'by # and # for # sec',
      values: ['15%', '2.5', '30'],
    })
  })
})

describe('compareDescriptions', () => {
  it('says nothing when the two sentences claim the same thing', () => {
    expect(compareDescriptions('Stuns for 3 sec.', 'Stuns for 3 seconds')).toBeUndefined()
  })

  it('separates a value change from a rewrite', () => {
    expect(compareDescriptions('Hits for 15%.', 'Hits for 20%.')?.kind).toBe('values')
    expect(compareDescriptions('Hits for 15%.', 'Heals for 15%.')?.kind).toBe('text')
  })

  it('lists every number that moved and no number that did not', () => {
    const out = compareDescriptions('deals 148 to 195 damage over 12 sec', 'deals 155 to 195 damage over 12 sec')
    expect(out).toMatchObject({ kind: 'values', values: [['148', '155']] })
  })
})

describe('matchTrees', () => {
  const tree = (id: string, name: string, names: string[]) => ({
    id,
    name,
    talents: names.map((n) => ({ name: n })),
  })

  it('matches on the id first', () => {
    const map = matchTrees([tree('arms', 'Arms', ['A'])], [tree('arms', 'Arms', ['A'])])
    expect(map.get('arms')).toBe('arms')
  })

  it('follows a renamed tree by name', () => {
    const map = matchTrees(
      [tree('elemental-combat', 'Elemental Combat', ['X'])],
      [tree('elemental', 'Elemental Combat', ['X'])],
    )
    expect(map.get('elemental')).toBe('elemental-combat')
  })

  it('follows a renamed tree by the majority of its talents when the name moved too', () => {
    const map = matchTrees(
      [tree('shadow-magic', 'Shadow Magic', ['Blackout', 'Silence', 'Darkness', 'Shadowform'])],
      [tree('shadow', 'Shadow', ['Blackout', 'Silence', 'Darkness'])],
    )
    expect(map.get('shadow')).toBe('shadow-magic')
  })

  it('does not let a tree that traded one talent steal its neighbour identity', () => {
    const map = matchTrees(
      [tree('balance', 'Balance', ['Insect Swarm', 'Moonfury', 'Moonkin Form'])],
      [tree('restoration', 'Restoration', ['Insect Swarm', 'Tranquility', 'Nature Focus'])],
    )
    expect(map.get('restoration')).toBeUndefined()
  })
})

describe('cellBase', () => {
  it('reads a 1-based prior as 1-based', () => {
    expect(cellBase([{ row: 1, col: 1 }, { row: 4, col: 2 }])).toEqual({ row: 1, col: 1 })
  })

  it('leaves a 0-based set alone, and does not rebase a merely sparse one', () => {
    expect(cellBase([{ row: 0, col: 2 }, { row: 3, col: 3 }])).toEqual({ row: 0, col: 0 })
    expect(cellBase([{ row: 2, col: 2 }])).toEqual({ row: 0, col: 0 })
  })
})

describe('rankSeries', () => {
  it('reports the slot that actually changes between ranks', () => {
    expect(rankSeries([[2], [4], [6]])).toBe('2/4/6')
    expect(rankSeries([[10, 1], [10, 2]])).toBe('1/2')
  })

  it('says nothing for whole-sentence ranks or a single rank', () => {
    expect(rankSeries(['a', 'b'])).toBeUndefined()
    expect(rankSeries([[5]])).toBeUndefined()
  })
})

describe('diffClass', () => {
  const forever = {
    trees: [
      {
        id: 'arms',
        name: 'Arms',
        talents: [
          { id: 'stayed', name: 'Stayed', row: 0, col: 0, maxRank: 3, description: 'Same words.', ranks: [[]] },
          { id: 'slid-down', name: 'Slid Down', row: 3, col: 1, maxRank: 2, description: 'Same words.', ranks: [[]] },
          { id: 'fewer-ranks', name: 'Fewer Ranks', row: 1, col: 2, maxRank: 3, description: 'Same words.', ranks: [[]] },
          { id: 'brand-new', name: 'Brand New', row: 4, col: 0, maxRank: 1, description: 'Same words.', ranks: [[]] },
          { id: 'reworded', name: 'Reworded', row: 2, col: 0, maxRank: 1, description: 'Heals for {0}.', ranks: [[5]] },
          { id: 'retuned', name: 'Retuned', row: 2, col: 1, maxRank: 1, description: 'Hits for {0}%.', ranks: [[20]] },
        ],
      },
      {
        id: 'fury',
        name: 'Fury',
        talents: [
          { id: 'changed-tree', name: 'Changed Tree', row: 0, col: 1, maxRank: 5, description: 'Same words.', ranks: [[]] },
        ],
      },
    ],
  }
  const prior = {
    trees: [
      {
        id: 'arms',
        name: 'Arms',
        talents: [
          { id: 'stayed', name: 'Stayed', row: 0, col: 0, maxRank: 3, ranks: ['Same words.'] },
          { id: 'slid-down', name: 'Slid Down', row: 1, col: 1, maxRank: 2, ranks: ['Same words.'] },
          { id: 'fewer-ranks', name: 'Fewer Ranks', row: 1, col: 2, maxRank: 5, ranks: ['Same words.'] },
          { id: 'reworded', name: 'Reworded', row: 2, col: 0, maxRank: 1, ranks: ['Hits for 5.'] },
          { id: 'retuned', name: 'Retuned', row: 2, col: 1, maxRank: 1, ranks: ['Hits for 15%.'] },
          { id: 'changed-tree', name: 'Changed Tree', row: 0, col: 1, maxRank: 5, ranks: ['Same words.'] },
          { id: 'gone', name: 'Gone', row: 6, col: 1, maxRank: 1, ranks: ['Same words.'] },
        ],
      },
    ],
  }
  const result = diffClass(forever, prior)

  it('classifies every talent and counts them', () => {
    expect(result.counts).toEqual({
      new: 1,
      moved: 2,
      'rank-changed': 1,
      'text-changed': 1,
      'values-changed': 1,
      same: 1,
      removed: 1,
    })
  })

  it('omits unchanged talents from the file, so a missing entry means "same"', () => {
    expect(Object.keys(result.talents).sort()).toEqual([
      'brand-new',
      'changed-tree',
      'fewer-ranks',
      'retuned',
      'reworded',
      'slid-down',
    ])
  })

  it('follows a talent that changed tree instead of calling it new and removed', () => {
    expect(result.talents['changed-tree']).toEqual({
      status: 'moved',
      prior: { tree: 'arms', treeName: 'Arms', row: 0, col: 1, maxRank: 5, movedTree: true },
    })
    expect(result.removed.map((r) => r.name)).toEqual(['Gone'])
  })

  it('splits the bulky half off: the sentence and its diff go to the text index', () => {
    expect(result.talents['reworded']).not.toHaveProperty('classic')
    expect(result.text!['reworded']!.text).toBe('Hits for 5.')
    expect(result.text!['retuned']).toMatchObject({ values: [['15%', '20%']] })
    expect(result.text!['stayed']).toBeUndefined()
  })

  it('lists the Classic talents with no counterpart, with their old cell', () => {
    expect(result.removed[0]).toMatchObject({ id: 'gone', name: 'Gone', tree: 'arms', row: 6, maxRank: 1 })
  })

  it('matches exclusively: one Classic talent cannot back two Forever talents', () => {
    const twice = diffClass(
      { trees: [{ id: 'arms', name: 'Arms', talents: [
        { id: 'a', name: 'Twin', row: 0, col: 0, maxRank: 1 },
        { id: 'b', name: 'Twin', row: 1, col: 0, maxRank: 1 },
      ] }] },
      { trees: [{ id: 'arms', name: 'Arms', talents: [{ id: 't', name: 'Twin', row: 0, col: 0, maxRank: 1 }] }] },
    )
    expect(twice.counts.new).toBe(1)
    expect(twice.counts.same).toBe(1)
    expect(twice.removed).toEqual([])
  })

  it('prefers the counterpart in the same tree when a name occurs twice', () => {
    const shared = diffClass(
      { trees: [{ id: 'fury', name: 'Fury', talents: [{ id: 'x', name: 'Cleave', row: 2, col: 2, maxRank: 1 }] }] },
      {
        trees: [
          { id: 'arms', name: 'Arms', talents: [{ id: 'a', name: 'Cleave', row: 0, col: 0, maxRank: 1 }] },
          { id: 'fury', name: 'Fury', talents: [{ id: 'f', name: 'Cleave', row: 2, col: 2, maxRank: 1 }] },
        ],
      },
    )
    expect(shared.counts.same).toBe(1)
    expect(shared.removed.map((r) => r.tree)).toEqual(['arms'])
  })

  // Round 2's headline: a renamed tree must not turn a whole tree into moves.
  it('maps a renamed tree, so a talent that stayed put is not a move', () => {
    const renamed = diffClass(
      {
        trees: [
          {
            id: 'shadow-magic',
            name: 'Shadow Magic',
            talents: [
              { id: 'shadowform', name: 'Shadowform', row: 6, col: 1, maxRank: 1, description: 'Assume Shadowform.', ranks: [[]] },
              { id: 'silence', name: 'Silence', row: 4, col: 0, maxRank: 1, description: 'Silences.', ranks: [[]] },
              { id: 'mind-flay', name: 'Mind Flay', row: 5, col: 2, maxRank: 1, description: 'Flays.', ranks: [[]] },
            ],
          },
        ],
      },
      {
        trees: [
          {
            id: 'shadow',
            name: 'Shadow',
            talents: [
              { id: 'shadowform', name: 'Shadowform', row: 6, col: 1, maxRank: 1, ranks: ['Assume a Shadowform.'] },
              { id: 'silence', name: 'Silence', row: 4, col: 0, maxRank: 1, ranks: ['Silences.'] },
              { id: 'mind-flay', name: 'Mind Flay', row: 2, col: 2, maxRank: 1, ranks: ['Flays.'] },
            ],
          },
        ],
      },
    )
    expect(renamed.counts.moved).toBe(1)
    expect(renamed.talents['shadowform']!.status).toBe('text-changed')
    expect(renamed.talents['silence']).toBeUndefined()
    // The one that really did move says so, and does not blame the tree.
    expect(renamed.talents['mind-flay']).toEqual({
      status: 'moved',
      row: 5,
      prior: { tree: 'shadow', treeName: 'Shadow', row: 2, col: 2, maxRank: 1, movedRow: true },
    })
  })
})

describe('buildClassicDiff', () => {
  it('skips classes with no Classic counterpart rather than calling them all new', () => {
    const out = buildClassicDiff(
      [{ id: 'tinker', data: { trees: [{ id: 't', name: 'T', talents: [{ id: 'a', name: 'A', row: 0, col: 0, maxRank: 1 }] }] } }],
      { classes: {} },
    )
    expect(out.classes).toEqual({})
    expect(out.totals.new).toBe(0)
  })
})

describe('the generated classic-diff.json', () => {
  it('is up to date, and so is the lazily fetched text index', () => {
    expect(readFileSync(join(here, 'classic-diff.json'), 'utf8')).toBe(expected().classicDiff)
    expect(readFileSync(join(here, 'classic-text.json'), 'utf8')).toBe(expected().classicText)
  })

  it('covers all nine Classic classes and no example class', () => {
    expect(Object.keys(diff.classes).sort()).toEqual([
      'druid', 'hunter', 'mage', 'paladin', 'priest', 'rogue', 'shaman', 'warlock', 'warrior',
    ])
    expect(hasClassicDiff('tinker')).toBe(false)
  })

  it('totals match the per-class counts', () => {
    const keys = ['new', 'moved', 'rank-changed', 'text-changed', 'values-changed', 'same', 'removed'] as const
    const sum = (key: (typeof keys)[number]) =>
      Object.values(diff.classes).reduce((n, c) => n + (c.counts as Record<string, number>)[key]!, 0)
    for (const key of keys) {
      expect((diff.totals as Record<string, number>)[key]).toBe(sum(key))
    }
    // Every one of the 469 talents lands in exactly one status.
    const totals = diff.totals as Record<string, number>
    expect(keys.filter((k) => k !== 'removed').reduce((n, k) => n + totals[k]!, 0)).toBe(469)
  })

  // The owner's report: priest Shadowform reads "Moved from Shadow, row 7"
  // although it never left row 7 of the Shadow tree. Forever renamed the tree
  // and reworked the wording; neither is a move.
  it('does not call Shadowform moved, and knows its wording changed', () => {
    const entry = diff.classes.priest.talents['shadowform'] as { status: string; textChange?: string }
    expect(entry.status).toBe('text-changed')
    expect(entry.textChange).toBe('text')
  })

  // Eight talents genuinely changed tree. Pinned by name, because the previous
  // round reported forty-one: the thirty-three extra were the two renames.
  it('reports exactly the eight talents that really changed tree', () => {
    const crossTree: string[] = []
    for (const [classId, cls] of Object.entries(diff.classes)) {
      for (const [id, entry] of Object.entries(cls.talents)) {
        if ((entry as { prior?: { movedTree?: boolean } }).prior?.movedTree) crossTree.push(`${classId}/${id}`)
      }
    }
    expect(crossTree.sort()).toEqual([
      'druid/insect-swarm',
      'druid/natural-shapeshifter',
      'rogue/improved-gouge',
      'rogue/improved-eviscerate',
      'shaman/earths-grasp',
      'warrior/improved-slam',
      'warrior/improved-thunder-clap',
      'warrior/iron-will',
    ].sort())
  })

  // The two trees Forever renamed. Round 1 called every talent in them moved;
  // the ones that kept their cell must now be same, reworded or re-ranked.
  it('leaves the renamed trees to their real changes', () => {
    const stayed = [
      ['priest', 'shadow-affinity'],
      ['priest', 'mind-flay'],
      ['priest', 'silence'],
      ['priest', 'darkness'],
      ['priest', 'shadowform'],
      ['shaman', 'convection'],
      ['shaman', 'concussion'],
    ] as const
    const talents = (classId: string) =>
      (diff.classes as unknown as Record<string, { talents: Record<string, { status: string }> }>)[classId]!.talents
    for (const [classId, id] of stayed) {
      expect(talents(classId)[id]?.status ?? 'same', id).not.toBe('moved')
    }
  })

  it('gives every listed entry the prior cell it needs, and new talents none', () => {
    for (const cls of Object.values(diff.classes)) {
      for (const [id, entry] of Object.entries(cls.talents)) {
        // `same` is normally left out; the one exception is a column-only move,
        // which is not news to a player but keeps its Classic cell on record.
        if (entry.status === 'same') {
          expect((entry as { prior?: { movedCol?: boolean } }).prior?.movedCol, id).toBe(true)
          continue
        }
        if (entry.status === 'new') expect(entry).not.toHaveProperty('prior')
        else expect(entry, id).toHaveProperty('prior')
      }
    }
  })
})

describe('changeOf', () => {
  it('reads the talents the brief names for Warrior', () => {
    expect(changeOf('warrior', 'bloodthrill')?.status).toBe('new')
    expect(changeOf('warrior', 'weaponmaster')?.status).toBe('new')
    expect(removedTalents('warrior').map((t) => t.name)).toEqual(
      expect.arrayContaining(['Axe Specialization', 'Mace Specialization', 'Sword Specialization', 'Polearm Specialization']),
    )
  })

  it('reports "same" for a talent the file does not mention, in a class it knows', () => {
    expect(changeOf('warrior', 'a-talent-that-does-not-exist')).toEqual({ status: 'same' })
  })

  it('reports nothing at all for a class with no Classic prior', () => {
    expect(changeOf('tinker', 'improved-wrench')).toBeUndefined()
  })

  it('counts the changed talents for the toggle tooltip', () => {
    const w = diff.classes.warrior.counts as Record<string, number>
    const changed = ['new', 'moved', 'rank-changed', 'text-changed', 'values-changed']
    expect(changedCount('warrior')).toBe(changed.reduce((n, k) => n + w[k]!, 0))
    expect(changedCount('tinker')).toBe(0)
  })
})

/**
 * `scripts/diffWords.mjs` is a second copy of `diffWords` from
 * src/ui/review.ts, because the build script cannot import TypeScript and
 * importing the script from app code costs every first load a rolldown-runtime
 * chunk (see the note at the top of diffWords.mjs). This is the guard that the
 * copies cannot drift: same words in, same runs out.
 */
describe('the build script word diff matches the app one', () => {
  const LETTER = { same: '=', del: '-', add: '+' } as const
  const pairs: [string, string][] = [
    ['', ''],
    ['same words here', 'same words here'],
    ['Increases your chance to hit by 1%.', 'Increases your chance to dodge by 2%.'],
    ['a b c d e', 'e d c b a'],
    ['one', 'one two three'],
    ['one two three', 'one'],
    [
      'Assume a Shadowform, increasing your Shadow damage by 15% and reducing Physical damage done to you by 15%.',
      'Assume Shadowform, increasing your Shadow damage by 10%, reducing the Mana cost of all Shadow spells by 50%.',
    ],
  ]

  it.each(pairs)('agrees on %j vs %j', (a, b) => {
    expect(compactDiff(a, b)).toEqual(diffWords(a, b).map((op) => [LETTER[op.type], op.text]))
  })

  // A stored diff is only trustworthy if it still contains the sentence it
  // claims to describe: the `=` and `-` runs must rebuild the Classic text, and
  // the `=` and `+` runs the Forever one.
  it('rebuilds every stored Classic sentence out of its own diff', () => {
    const index = classicText as unknown as Record<string, Record<string, { text: string; diff: [string, string][] }>>
    let checked = 0
    for (const [classId, talents] of Object.entries(index)) {
      for (const [id, entry] of Object.entries(talents)) {
        const join = (ops: string[]) =>
          entry.diff
            .filter(([op]) => ops.includes(op!))
            .map(([, text]) => text)
            .join(' ')
        expect(join(['=', '-']), `${classId}/${id}`).toBe(entry.text.split(/\s+/).filter(Boolean).join(' '))
        checked++
      }
    }
    expect(checked).toBeGreaterThan(200)
  })

  it('every entry the diff flags as reworded has a sentence in the text index', () => {
    const index = classicText as unknown as Record<string, Record<string, unknown>>
    for (const [classId, cls] of Object.entries(diff.classes)) {
      for (const [id, entry] of Object.entries(cls.talents)) {
        if (!(entry as { textChange?: string }).textChange) continue
        expect(index[classId]?.[id], `${classId}/${id}`).toBeDefined()
      }
    }
  })
})

import { describe, expect, it } from 'vitest'
import { makeClass } from '../rules/fixture'
import type { Change, ClassicText, RemovedTalent } from './classicDiff'
import { changesModel, diffLines, filterModel, type SectionId } from './changesModel'

const cls = makeClass()

function model(changes: Record<string, Change>, removed: RemovedTalent[] = [], hasDiff: (id: string) => boolean = () => false) {
  return changesModel(cls, changes, removed, hasDiff)
}

function section(m: ReturnType<typeof model>, id: SectionId) {
  return m.sections.find((s) => s.id === id)!
}

const priorCell = { tree: 'alpha', treeName: 'Alpha', row: 0, col: 0, maxRank: 5 }

describe('the #/changes model', () => {
  it('is empty when nothing changed, and keeps the six sections anyway', () => {
    const m = model({})
    expect(m.total).toBe(0)
    expect(m.sections.map((s) => s.id)).toEqual([
      'new',
      'moved',
      'rank-changed',
      'text-changed',
      'values-changed',
      'gone',
    ])
    expect(m.className).toBe('Test Class')
  })

  it('ignores talents the generator calls `same` - including a column-only move', () => {
    const m = model({ 'a-one': { status: 'same', prior: { ...priorCell, col: 2, movedCol: true } } })
    expect(m.total).toBe(0)
  })

  it('files each talent under its headline status, exactly once', () => {
    const m = model({
      'a-one': { status: 'new' },
      'a-two': { status: 'moved', prior: { ...priorCell, row: 3, movedRow: true }, row: 0, textChange: 'text' },
      'b-one': { status: 'rank-changed', prior: { ...priorCell, maxRank: 5 } },
      'b-two': { status: 'text-changed', prior: priorCell, textChange: 'text' },
      'c-one': { status: 'values-changed', prior: priorCell, textChange: 'values', values: [['15%', '12%']] },
    })
    expect(m.total).toBe(5)
    expect(section(m, 'new').rows.map((r) => r.id)).toEqual(['a-one'])
    expect(section(m, 'moved').rows.map((r) => r.id)).toEqual(['a-two'])
    expect(section(m, 'rank-changed').rows.map((r) => r.id)).toEqual(['b-one'])
    expect(section(m, 'text-changed').rows.map((r) => r.id)).toEqual(['b-two'])
    expect(section(m, 'values-changed').rows.map((r) => r.id)).toEqual(['c-one'])
    // A talent that both moved and was reworked is counted once, not twice.
    expect(m.sections.flatMap((s) => s.rows).filter((r) => r.id === 'a-two')).toHaveLength(1)
  })

  it('prints the same sentence the tooltip prints, plus where the talent sits', () => {
    const m = model({
      'a-one': { status: 'new' },
      'a-two': { status: 'moved', prior: { ...priorCell, row: 3, movedRow: true }, row: 0 },
      'b-one': { status: 'rank-changed', prior: { ...priorCell, maxRank: 5 } },
      'c-one': { status: 'values-changed', prior: priorCell, textChange: 'values', values: [['15%', '12%']] },
    })
    expect(section(m, 'new').rows[0]!.detail).toBe('Alpha, row 1 - 5 ranks.')
    expect(section(m, 'moved').rows[0]!.detail).toBe('Moved from row 4 to row 1. Now in Alpha.')
    expect(section(m, 'rank-changed').rows[0]!.detail).toBe('Now 3 ranks, was 5. Alpha, row 2.')
    expect(section(m, 'values-changed').rows[0]!.detail).toBe('Values changed: 15% → 12%. Alpha, row 3.')
  })

  it('names a description change that a move would otherwise hide', () => {
    const moved = (textChange: 'text' | 'values', values?: [string, string][]): Change => ({
      status: 'moved',
      prior: { ...priorCell, row: 3, movedRow: true },
      row: 0,
      textChange,
      values,
    })
    expect(model({ 'a-one': moved('text') }).sections[1]!.rows[0]!.detail).toContain('Also reworked.')
    expect(model({ 'a-one': moved('values', [['2', '3']]) }).sections[1]!.rows[0]!.detail).toContain(
      'Also: values changed: 2 → 3.',
    )
  })

  it('lists the Classic talents that are gone, with the cell they sat in', () => {
    const removed: RemovedTalent[] = [
      { id: 'axe-specialization', name: 'Axe Specialization', tree: 'arms', treeName: 'Arms', row: 4, col: 0, maxRank: 5 },
    ]
    const gone = section(model({}, removed), 'gone')
    expect(gone.rows).toHaveLength(1)
    expect(gone.rows[0]).toMatchObject({ name: 'Axe Specialization', gone: true, detail: 'Was Arms, row 5 - 5 ranks.' })
  })

  it('orders each section by row then column, the way the tree reads', () => {
    const m = model({
      'c-two': { status: 'new' },
      'a-two': { status: 'new' },
      'b-one': { status: 'new' },
    })
    expect(section(m, 'new').rows.map((r) => r.id)).toEqual(['a-two', 'b-one', 'c-two'])
  })

  it('reports whether a word diff exists, so a row knows if it can show one', () => {
    const m = model({ 'b-two': { status: 'text-changed', prior: priorCell, textChange: 'text' } }, [], (id) => id === 'b-two')
    expect(section(m, 'text-changed').rows[0]!.hasDiff).toBe(true)
  })
})

describe('the filter box', () => {
  const m = model(
    {
      'a-one': { status: 'new' },
      'b-two': { status: 'text-changed', prior: priorCell, textChange: 'text' },
    },
    [{ id: 'gone-one', name: 'Gone One', tree: 'arms', treeName: 'Arms', row: 0, col: 0, maxRank: 1 }],
  )

  it('keeps everything for an empty query', () => {
    expect(filterModel(m, '   ').total).toBe(3)
  })

  it('matches the name, case-insensitively', () => {
    expect(filterModel(m, 'A-ONE').total).toBe(1)
    expect(filterModel(m, 'gone one').sections.find((s) => s.id === 'gone')!.rows).toHaveLength(1)
  })

  it('matches the detail line as well as the name', () => {
    expect(filterModel(m, 'alpha').total).toBe(2)
    expect(filterModel(m, 'nothing here').total).toBe(0)
  })
})

describe('diffLines (UX review round two, finding 7)', () => {
  const defiance: ClassicText = {
    text: 'Increases the threat generated by your attacks by 3% while in Defensive Stance.',
    diff: [
      ['=', 'Increases'],
      ['-', 'the'],
      ['+', 'all'],
      ['=', 'threat generated'],
      ['-', 'by your attacks by 3%'],
      ['-', 'while'],
      ['=', 'in Defensive'],
      ['-', 'Stance.'],
      ['+', 'stance by an additional 5% while a shield is equipped.'],
    ],
  }

  it('splits one interleaved run into the two sentences it was made from', () => {
    const { classic, forever } = diffLines(defiance)
    expect(classic.map(([, run]) => run).join(' ')).toBe(
      'Increases the threat generated by your attacks by 3% while in Defensive Stance.',
    )
    expect(forever.map(([, run]) => run).join(' ')).toBe(
      'Increases all threat generated in Defensive stance by an additional 5% while a shield is equipped.',
    )
    // Each line carries only its own side's marks.
    expect(classic.some(([op]) => op === '+')).toBe(false)
    expect(forever.some(([op]) => op === '-')).toBe(false)
  })

  it('degrades to a single sentence when there is no diff, and to nothing when there is no text', () => {
    expect(diffLines({ text: 'Only Forever has this.', diff: [] } as ClassicText)).toEqual({
      classic: [['=', 'Only Forever has this.']],
      forever: [['=', 'Only Forever has this.']],
    })
    expect(diffLines(undefined)).toEqual({ classic: [], forever: [] })
    expect(diffLines({ text: '', diff: [] } as ClassicText)).toEqual({ classic: [], forever: [] })
  })
})

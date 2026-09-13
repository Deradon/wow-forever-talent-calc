import { expect, test, type Locator, type Page } from '@playwright/test'

/**
 * Same-row prerequisite arrows in a real layout. Forever lets a talent require
 * another one in its own row (priest Improved Mind Flay requires Mind Flay), so
 * `web/tests/fixtures/fixture-arrows.json` puts one of each case next to a
 * Classic vertical arrow: `flay` in the middle of row 1 with `echo` left of it,
 * `improved-flay` right of it and `distant-flay` two cells right, plus
 * `deep-flay` straight below.
 *
 * The unit test src/ui/arrows.test.ts owns the exact numbers; this one checks
 * what only a browser can: that the numbers land where the cells actually are.
 */

/** The polyline's own points, in viewport coordinates (scale and all). */
async function pointsOf(arrow: Locator): Promise<{ x: number; y: number }[]> {
  return arrow.evaluate((el) => {
    const m = (el as SVGGraphicsElement).getScreenCTM()!
    return (el.getAttribute('points') ?? '')
      .split(' ')
      .map((p) => p.split(',').map(Number))
      .map(([x, y]) => ({ x: m.a * x! + m.c * y! + m.e, y: m.b * x! + m.d * y! + m.f }))
  })
}

async function rectOf(page: Page, testId: string) {
  return page.getByTestId(testId).evaluate((el) => {
    const r = el.getBoundingClientRect()
    return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, cx: r.left + r.width / 2, cy: r.top + r.height / 2 }
  })
}

function arrow(page: Page, key: string): Locator {
  return page.locator(`[data-testid="tree-sideways"] polyline[data-arrow="${key}"]`)
}

test.beforeEach(async ({ page }) => {
  await page.goto('/#/fixture-arrows')
  await expect(page.getByTestId('talent-flay')).toBeVisible()
})

test('a same-row prerequisite draws a horizontal arrow in both directions', async ({ page }) => {
  await expect(page.locator('[data-testid="tree-sideways"] polyline[data-arrow-kind="horizontal"]')).toHaveCount(3)
  await expect(page.locator('[data-testid="tree-sideways"] polyline[data-arrow-kind="vertical"]')).toHaveCount(1)

  const source = await rectOf(page, 'talent-flay')

  for (const [key, targetId, dir] of [
    ['flay->improved-flay', 'talent-improved-flay', 'right'],
    ['flay->distant-flay', 'talent-distant-flay', 'right'],
    ['flay->echo', 'talent-echo', 'left'],
  ] as const) {
    const points = await pointsOf(arrow(page, key))
    expect(points, `${key} is a straight line`).toHaveLength(2)
    const [start, end] = points as [{ x: number; y: number }, { x: number; y: number }]
    const target = await rectOf(page, targetId)

    // Along the row's centre line, from just outside the prerequisite.
    expect(Math.abs(start.y - end.y), `${key} is level`).toBeLessThan(0.5)
    expect(Math.abs(start.y - source.cy), `${key} runs through the row centre`).toBeLessThan(1.5)
    expect(Math.abs(start.y - target.cy)).toBeLessThan(1.5)

    if (dir === 'right') {
      expect(end.x, `${key} points rightwards`).toBeGreaterThan(start.x)
      expect(start.x).toBeGreaterThanOrEqual(source.right)
      // The head stops in the gutter: past the source, short of the target.
      expect(end.x).toBeLessThan(target.left)
      expect(target.left - end.x).toBeLessThan(12)
    } else {
      expect(end.x, `${key} points leftwards`).toBeLessThan(start.x)
      expect(start.x).toBeLessThanOrEqual(source.left)
      expect(end.x).toBeGreaterThan(target.right)
      expect(end.x - target.right).toBeLessThan(12)
    }
  }
})

test('horizontal arrows keep off the tier gutter and out of the row gap', async ({ page }) => {
  const gutter = await page
    .getByTestId('tiers-sideways')
    .evaluate((el) => { const r = el.getBoundingClientRect(); return { right: r.right } })
  const row1 = await rectOf(page, 'talent-flay')
  const row2 = await rectOf(page, 'talent-deep-flay')
  const gap = { top: row1.bottom, bottom: row2.top }
  expect(gap.bottom).toBeGreaterThan(gap.top) // the 12px gutter the vertical arrow crosses

  for (const key of ['flay->improved-flay', 'flay->distant-flay', 'flay->echo']) {
    for (const p of await pointsOf(arrow(page, key))) {
      expect(p.x, `${key} stays right of the tier gutter`).toBeGreaterThan(gutter.right)
      // Inside the row's own band, so it never shares a pixel with a vertical
      // arrow crossing the gap between the rows.
      expect(p.y).toBeGreaterThan(row1.top)
      expect(p.y).toBeLessThan(row1.bottom)
    }
  }

  // The vertical arrow, by contrast, lives in exactly that gap.
  const vertical = await pointsOf(arrow(page, 'flay->deep-flay'))
  expect(vertical[0]!.y).toBeGreaterThanOrEqual(gap.top)
  expect(vertical[1]!.y).toBeLessThanOrEqual(gap.bottom)
  expect(Math.abs(vertical[0]!.x - row1.cx)).toBeLessThan(1.5)
})

test('a horizontal arrow turns gold exactly when its prerequisite is paid for', async ({ page }) => {
  const keys = ['flay->improved-flay', 'flay->distant-flay', 'flay->echo', 'flay->deep-flay']
  for (const key of keys) await expect(arrow(page, key)).toHaveAttribute('data-satisfied', 'false')
  await expect(arrow(page, 'flay->echo')).toHaveAttribute('stroke-dasharray', '4 4')

  // Open row 1, then pay the prerequisite off: 3 of 3 ranks in `flay`.
  await page.getByTestId('talent-warm-up').click({ modifiers: ['Shift'] })
  await page.getByTestId('talent-flay').click({ modifiers: ['Shift'] })
  await expect(page.getByTestId('talent-flay')).toHaveAttribute('data-rank', '3')

  for (const key of keys) {
    await expect(arrow(page, key)).toHaveAttribute('data-satisfied', 'true')
    await expect(arrow(page, key)).toHaveAttribute('stroke', '#ffd100')
  }
  // And the talent to the left of the prerequisite is now addable.
  await expect(page.getByTestId('talent-echo')).toHaveAttribute('data-addable', 'true')

  // Refunding the prerequisite below rank 3 is blocked while a dependent holds
  // points, whichever side of it the dependent sits on.
  await page.getByTestId('talent-echo').click()
  await page.getByTestId('talent-flay').click({ button: 'right' })
  await expect(page.getByTestId('talent-flay')).toHaveAttribute('data-rank', '3')
})

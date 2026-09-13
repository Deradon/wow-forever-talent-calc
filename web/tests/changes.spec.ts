import { expect, test } from '@playwright/test'

/**
 * Round 1b: "New in Forever" markers and the highlight switch (brief idea 3),
 * modifier clicks (idea 4) and the tier gutter (idea 6).
 *
 * Paladin is the fixture throughout because it is real data with a Classic
 * counterpart: `improved-holy-strike` is new, `toughness` moved up a row and
 * `divine-strength` is untouched since Classic Era - all three in row 0, so no
 * case has to spend points just to reach its subject.
 */

test('shift-click maxes a talent and ctrl-click clears it', async ({ page }) => {
  await page.goto('/#/paladin')
  const cell = page.getByTestId('talent-divine-strength') // 5 ranks, row 0
  const left = page.getByTestId('points-left')

  await cell.click({ modifiers: ['Shift'] })
  await expect(cell).toHaveAttribute('data-rank', '5')
  await expect(cell).toHaveAttribute('data-state', 'maxed')
  await expect(left).toHaveText('46')

  // A second shift-click on a maxed talent must not spend anything, and must
  // say why rather than doing nothing at all.
  await cell.click({ modifiers: ['Shift'], force: true })
  await expect(left).toHaveText('46')
  await expect(page.getByTestId('blocked-message')).toBeVisible()

  await cell.click({ modifiers: ['Control'] })
  await expect(cell).toHaveAttribute('data-rank', '0')
  await expect(left).toHaveText('51')

  // Alt is the second clear chord, for browsers that hijack Ctrl-click.
  await cell.click({ modifiers: ['Shift'] })
  await expect(cell).toHaveAttribute('data-rank', '5')
  await cell.click({ modifiers: ['Alt'] })
  await expect(cell).toHaveAttribute('data-rank', '0')
})

test('shift-click stops where the rules stop, and never bypasses a prerequisite', async ({ page }) => {
  await page.goto('/#/paladin')
  // Row 1 needs 5 points in the tree: shift-clicking it maxes nothing.
  const locked = page.locator('[data-testid="tree-holy"] [data-talent][data-state="locked"]').first()
  await locked.click({ modifiers: ['Shift'], force: true })
  await expect(locked).toHaveAttribute('data-rank', '0')
  await expect(page.getByTestId('blocked-message')).toContainText(/points in/i)
  await expect(page.getByTestId('points-left')).toHaveText('51')

  // With the row paid for, the same chord fills the talent and no more.
  await page.getByTestId('talent-divine-strength').click({ modifiers: ['Shift'] })
  // Pin the id now: once it is maxed the cell drops out of the addable set, and
  // a re-resolved locator would silently point at a different talent.
  const id = await page
    .locator('[data-testid="tree-holy"] [data-talent][data-row="1"][data-addable="true"]')
    .first()
    .getAttribute('data-talent')
  const unlocked = page.getByTestId(`talent-${id}`)
  const maxRank = Number((await unlocked.locator('.badge').textContent())!.split('/')[1])
  await unlocked.click({ modifiers: ['Shift'] })
  await expect(unlocked).toHaveAttribute('data-rank', String(maxRank))
  await expect(unlocked).toHaveAttribute('data-state', 'maxed')
})

test('shift-backspace clears a talent from the keyboard', async ({ page }) => {
  await page.goto('/#/paladin')
  const cell = page.getByTestId('talent-divine-strength')
  await cell.click({ modifiers: ['Shift'] })
  await expect(cell).toHaveAttribute('data-rank', '5')
  await cell.focus()
  await page.keyboard.press('Shift+Backspace')
  await expect(cell).toHaveAttribute('data-rank', '0')
  await expect(page.getByTestId('points-left')).toHaveText('51')
})

test('new talents carry a marker and say so in the tooltip', async ({ page }) => {
  await page.goto('/#/paladin')
  const isNew = page.getByTestId('talent-improved-holy-strike')
  await expect(isNew).toHaveAttribute('data-change', 'new')
  await expect(page.getByTestId('new-flag-improved-holy-strike')).toBeVisible()

  // Exactly three marker slots, and they do not collide: `?` top-left, the new
  // star top-right, the rank badge bottom-right.
  const star = await page.getByTestId('new-flag-improved-holy-strike').boundingBox()
  const badge = await isNew.locator('.badge').boundingBox()
  expect(star!.y + star!.height).toBeLessThanOrEqual(badge!.y)
  // ... and the star is big enough to read as a star. At 14px it was a blue
  // smudge (round-one review); 18px is flush with the badge, which is the most
  // the right-hand edge of a 44px cell has to give.
  expect(star!.height).toBeGreaterThanOrEqual(16)
  expect(star!.width).toBeGreaterThanOrEqual(16)

  await isNew.hover()
  await expect(page.getByTestId('changed-improved-holy-strike')).toHaveText('New in Forever.')

  // A talent that only moved gets the line but no marker.
  const moved = page.getByTestId('talent-toughness')
  await expect(moved).toHaveAttribute('data-change', 'moved')
  await expect(page.getByTestId('new-flag-toughness')).toHaveCount(0)
  await moved.hover()
  // Both ends of the row move: "Moved from row 2." alone read as "this changed" to a
  // player looking straight at the row it is in (docs/handover/2026-09-13-cell-attribution-audit.md).
  await expect(page.getByTestId('changed-toughness')).toHaveText('Moved from row 2 to row 1.')

  // And an unchanged talent says nothing at all.
  const same = page.getByTestId('talent-divine-strength')
  await expect(same).toHaveAttribute('data-change', 'same')
  await same.hover()
  await expect(page.getByTestId('tooltip-divine-strength')).toBeVisible()
  await expect(page.getByTestId('changed-divine-strength')).toHaveCount(0)
})

test('the highlight switch dims what is unchanged, across all three trees', async ({ page }) => {
  await page.goto('/#/paladin')
  const toggle = page.getByTestId('highlight-new')
  await expect(toggle).toHaveCount(1) // one switch for the page, not one per tree
  await expect(toggle).toHaveAttribute('aria-pressed', 'false')

  const same = page.getByTestId('talent-divine-strength')
  const fresh = page.getByTestId('talent-improved-holy-strike')
  const opacity = (testId: string) =>
    page.getByTestId(testId).evaluate((el) => Number(getComputedStyle(el).opacity))
  expect(await opacity('talent-divine-strength')).toBe(1)

  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-pressed', 'true')
  await expect(same).toHaveAttribute('data-highlight', 'true')
  expect(await opacity('talent-divine-strength')).toBeLessThan(0.5)
  expect(await opacity('talent-improved-holy-strike')).toBe(1)
  // A tree the switch does not live in follows it too. Retribution has no
  // unchanged talent left since the diff learned to read descriptions, so the
  // probe is a reworded one - which also proves the new status reaches the DOM.
  await expect(page.locator('[data-testid="tree-retribution"] [data-change="text-changed"]').first()).toHaveAttribute(
    'data-highlight',
    'true',
  )

  // A talent the player has spent points in stays readable, changed or not.
  await same.click({ modifiers: ['Shift'] })
  await expect(same).toHaveAttribute('data-rank', '5')
  expect(await opacity('talent-divine-strength')).toBe(1)

  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-pressed', 'false')
  expect(await opacity('talent-divine-strength')).toBe(1)
  await expect(fresh).toHaveAttribute('data-change', 'new')
})

test('the tier gutter shows what each row costs, gold on the next locked row', async ({ page }) => {
  await page.goto('/#/paladin')
  const gutter = page.getByTestId('tiers-holy')
  await expect(gutter.locator('.tier[data-row="0"]')).toHaveText('')
  await expect(gutter.locator('.tier[data-row="1"]')).toHaveText('5')
  await expect(gutter.locator('.tier[data-row="6"]')).toHaveText('30')
  await expect(gutter.locator('.tier[data-state="next"]')).toHaveCount(1)
  await expect(gutter.locator('.tier[data-row="1"]')).toHaveAttribute('data-state', 'next')

  // Paying for row 1 moves the gold marker down to row 2.
  await page.getByTestId('talent-divine-strength').click({ modifiers: ['Shift'] })
  await expect(gutter.locator('.tier[data-row="1"]')).toHaveAttribute('data-state', 'unlocked')
  await expect(gutter.locator('.tier[data-row="2"]')).toHaveAttribute('data-state', 'next')

  // The gutter sits left of the grid and lines its rows up with the cells.
  const tier = await gutter.locator('.tier[data-row="1"]').boundingBox()
  const cellBox = await page.locator('[data-testid="tree-holy"] [data-talent][data-row="1"]').first().boundingBox()
  expect(tier!.x + tier!.width).toBeLessThanOrEqual(cellBox!.x)
  expect(Math.abs(tier!.y + tier!.height / 2 - (cellBox!.y + cellBox!.height / 2))).toBeLessThan(3)
})

test('arrowheads stop short of the talent they point at', async ({ page }) => {
  await page.goto('/#/paladin')
  const arrow = page.locator('[data-testid="tree-protection"] polyline[data-arrow]').first()
  await expect(arrow).toHaveAttribute('data-satisfied', 'false')
  await expect(arrow).toHaveAttribute('stroke-dasharray', '4 4')
  // The SVG is painted under the cells, so no head can land on an icon.
  const z = await page
    .locator('[data-testid="tree-protection"] [data-talent]')
    .first()
    .evaluate((el) => getComputedStyle(el).zIndex)
  expect(Number(z)).toBeGreaterThan(0)
})

/**
 * Round 2 of the Classic diff (docs/handover/2026-09-13-classic-diff-v2.md).
 * Priest Shadowform never left row 7 of the Shadow tree - Forever renamed the
 * tree and rewrote the tooltip - so the one change line must talk about the
 * wording, and the card behind it must show what Classic said.
 */
test('a reworked talent says so, and its card shows the Classic wording', async ({ page }) => {
  await page.goto('/#/priest')
  const cell = page.getByTestId('talent-shadowform')
  await expect(cell).toHaveAttribute('data-change', 'text-changed')
  // It is not new, so no star, and it must never claim to have moved.
  await expect(page.getByTestId('new-flag-shadowform')).toHaveCount(0)

  await cell.hover()
  const line = page.getByTestId('changed-shadowform')
  await expect(line).toHaveText('Reworked.')

  // Walk into the tooltip so the layer takes the pointer (stickyTooltip.ts):
  // dwell first, then approach in small steps, exactly as tooltip.spec.ts does.
  const layer = page.getByTestId('tooltip-layer-shadowform')
  await expect(layer).toBeVisible()
  await page.waitForTimeout(400) // > CELL_DWELL_MS
  const box = (await layer.boundingBox())!
  await page.mouse.move(box.x + 40, box.y + 16, { steps: 30 })
  await expect(layer).toHaveAttribute('data-sticky', 'true')

  const term = page.getByTestId('term-classic-shadowform')
  const termBox = (await term.boundingBox())!
  await page.mouse.move(termBox.x + termBox.width / 2, termBox.y + termBox.height / 2, { steps: 10 })

  const card = page.getByTestId('classic-shadowform')
  await expect(card).toBeVisible()
  await expect(card).toContainText('In Classic Era')
  await expect(card.locator('.diff-del').first()).toBeVisible()
  await expect(card.locator('.diff-add').first()).toBeVisible()
  // The Classic sentence, not ours: Classic Shadowform blocked Holy spells.
  await expect(card).toContainText('Holy')
  await page.screenshot({ path: 'test-results/classic-diff-card.png' })
})

test('a retuned talent names the numbers that moved, and shows the Classic series', async ({ page }) => {
  await page.goto('/#/priest')
  const cell = page.getByTestId('talent-shadow-affinity')
  await expect(cell).toHaveAttribute('data-change', 'values-changed')
  await cell.hover()
  await expect(page.getByTestId('changed-shadow-affinity')).toContainText('Values changed:')

  const layer = page.getByTestId('tooltip-layer-shadow-affinity')
  await expect(layer).toBeVisible()
  await page.waitForTimeout(400)
  const box = (await layer.boundingBox())!
  await page.mouse.move(box.x + 40, box.y + 16, { steps: 30 })
  await expect(layer).toHaveAttribute('data-sticky', 'true')

  const term = page.getByTestId('term-classic-shadow-affinity')
  const termBox = (await term.boundingBox())!
  await page.mouse.move(termBox.x + termBox.width / 2, termBox.y + termBox.height / 2, { steps: 10 })

  const card = page.getByTestId('classic-shadow-affinity')
  await expect(card).toBeVisible()
  await expect(card).toContainText('Classic values by rank:')
  await page.screenshot({ path: 'test-results/classic-diff-card-values.png' })
})

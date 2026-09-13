import { expect, test } from '@playwright/test'

/**
 * Work package A2: keyboard, touch, blocked-action feedback, the zero-points
 * state and search. One case per finding the reviews said had no coverage.
 */

test('keyboard: Enter adds, Backspace refunds, arrows move within one tab stop', async ({ page }) => {
  await page.goto('/#/paladin')
  const cell = page.getByTestId('talent-improved-holy-strike')
  await cell.focus()

  await page.keyboard.press('Enter')
  await expect(cell).toHaveAttribute('data-rank', '1')
  await page.keyboard.press('Space')
  await expect(cell).toHaveAttribute('data-rank', '2')

  // a11y review A-1: the handler used to be swallowed by floating-ui's own onKeyDown
  await page.keyboard.press('Backspace')
  await expect(cell).toHaveAttribute('data-rank', '1')
  await page.keyboard.press('Delete')
  await expect(cell).toHaveAttribute('data-rank', '0')
  await expect(page.getByTestId('points-left')).toHaveText('51')

  // the tree is a single tab stop, and arrows move inside it (A-7)
  const grid = page.locator('[data-testid="tree-holy"] .tree-grid')
  await expect(grid).toHaveAttribute('role', 'grid')
  expect(await grid.locator('[data-talent][tabindex="0"]').count()).toBe(1)

  const before = await cell.getAttribute('data-talent')
  await page.keyboard.press('ArrowRight')
  const afterRight = await page.evaluate(() => document.activeElement?.getAttribute('data-talent'))
  expect(afterRight).not.toBe(before)
  await page.keyboard.press('ArrowDown')
  const afterDown = await page.evaluate(() => document.activeElement?.getAttribute('data-talent'))
  expect(afterDown).not.toBe(afterRight)
  expect(await grid.locator('[data-talent][tabindex="0"]').count()).toBe(1)
})

test('blocked actions say why instead of failing silently', async ({ page }) => {
  await page.goto('/#/paladin')

  // clicking a locked talent
  const locked = page.locator('[data-talent][data-state="locked"]').first()
  const lockedName = await locked.getAttribute('data-talent')
  // force: the cell is aria-disabled (a11y review A-5), which Playwright treats
  // as not enabled - a real user can still click it, and must be told why.
  await locked.click({ force: true })
  const message = page.getByTestId('blocked-message')
  await expect(message).toBeVisible()
  await expect(message).toContainText(/points in/i)
  await expect(page.getByTestId('points-left')).toHaveText('51')
  await expect(page.locator(`[data-talent="${lockedName}"]`)).toHaveAttribute('data-rank', '0')

  // refunding something nothing is spent in
  await page.locator('[data-talent][data-addable="true"]').first().click()
  await expect(message).toHaveCount(0)
  const empty = page.locator('[data-talent][data-rank="0"][data-removable="false"]').first()
  await empty.click({ button: 'right', force: true })
  await expect(page.getByTestId('blocked-message')).toContainText('No points spent in')
})

test('a refund that would orphan a talent is refused by name', async ({ page }) => {
  await page.goto('/#/paladin')
  const holy = page.locator('[data-testid="tree-holy"]')

  // 5 points in row 0 unlock row 1; the row-1 point then pins them there.
  for (let guard = 0; guard < 20; guard++) {
    if (Number(await page.getByTestId('tree-points-holy').textContent()) >= 5) break
    await holy.locator('[data-talent][data-row="0"][data-addable="true"]').first().click()
  }
  const below = holy.locator('[data-talent][data-row="1"][data-addable="true"]').first()
  await below.click()
  await expect(below).toHaveAttribute('data-rank', '1')

  const spentAbove = holy.locator('[data-talent][data-row="0"]:not([data-rank="0"])').first()
  const id = await spentAbove.getAttribute('data-talent')
  const rank = await spentAbove.getAttribute('data-rank')
  await spentAbove.click({ button: 'right', force: true })

  await expect(page.getByTestId('blocked-message')).toContainText('would orphan')
  await expect(page.locator(`[data-talent="${id}"]`)).toHaveAttribute('data-rank', rank!)
})

test('with no points left the tree stops looking clickable and says so', async ({ page }) => {
  await page.goto('/#/paladin')
  for (let guard = 0; guard < 200; guard++) {
    const left = Number(await page.getByTestId('points-left').textContent())
    if (left === 0) break
    const addable = page.locator('[data-talent][data-addable="true"]').first()
    if ((await addable.count()) === 0) break
    await addable.click()
  }
  await expect(page.getByTestId('points-left')).toHaveText('0')
  await expect(page.getByTestId('no-points-left')).toBeVisible()

  // a rank-0 cell that is still "available" must now be flagged unaddable
  const stuck = page.locator('[data-talent][data-state="available"][data-addable="false"][data-rank="0"]').first()
  await expect(stuck).toHaveCount(1)
  const opacity = await stuck.evaluate((el) => getComputedStyle(el).borderColor)
  expect(opacity).not.toBe('rgb(30, 255, 0)') // no longer the full-strength green

  const id = await stuck.getAttribute('data-talent')
  await stuck.hover()
  await expect(page.getByTestId(`no-points-${id}`)).toContainText('No talent points left')
  await stuck.click({ force: true })
  await expect(page.getByTestId('blocked-message')).toContainText('No talent points left')
})

test('search filters the trees, lists names and jumps to a talent', async ({ page }) => {
  await page.goto('/#/paladin')
  const box = page.getByTestId('talent-search')
  await expect(box).toBeVisible()

  // `/` focuses it from anywhere on the page
  await page.locator('body').click()
  await page.keyboard.press('/')
  await expect(box).toBeFocused()

  const name = await page.locator('[data-talent]').first().getAttribute('aria-label')
  const word = name!.split(',')[0]!.split(' ')[0]!
  await box.fill(word)

  await expect(page.getByTestId('search-count')).toContainText(/match/)
  const results = page.getByTestId('search-results')
  await expect(results).toContainText(word)
  await expect(page.locator('[data-talent][data-match="true"]').first()).toBeVisible()
  expect(await page.locator('[data-talent][data-match="false"]').count()).toBeGreaterThan(0)

  const result = results.locator('button').first()
  const target = (await result.getAttribute('data-testid'))!.replace('search-result-', '')
  await result.click()
  await expect(page.locator(`[data-talent="${target}"]`)).toBeFocused()

  await box.fill('')
  await expect(page.locator('[data-talent][data-match]')).toHaveCount(0)
})

test('the page has a main landmark, a skip link and a live status region', async ({ page }) => {
  await page.goto('/#/paladin')
  await expect(page.locator('main#main')).toHaveCount(1)

  await page.keyboard.press('Tab')
  await expect(page.locator('.skip-link')).toBeFocused()

  const live = page.getByTestId('live-status')
  await expect(live).toHaveAttribute('aria-live', 'polite')
  await expect(live).toContainText('51 points left')
  await page.locator('[data-talent][data-addable="true"]').first().click()
  await expect(live).toContainText('50 points left')

  // the tooltip is now announced with the cell, and the id actually resolves (A-4)
  const cell = page.locator('[data-talent]').first()
  await cell.hover()
  await expect(cell).toHaveAttribute('aria-describedby', /.+/)
  const described = await cell.getAttribute('aria-describedby')
  await expect(page.locator(`#${described}`)).toHaveAttribute('role', 'tooltip')
  await expect(page.locator('[role="tooltip"]')).toHaveCount(1)
})

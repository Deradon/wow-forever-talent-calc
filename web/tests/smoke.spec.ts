import { expect, test, type Page } from '@playwright/test'

/**
 * Open the example class, spend points until the pool is empty or nothing is
 * addable, copy the link, reload it, and assert the same build.
 */

async function snapshot(page: Page): Promise<Record<string, string>> {
  const cells = page.locator('[data-talent]')
  const out: Record<string, string> = {}
  for (const cell of await cells.all()) {
    const id = await cell.getAttribute('data-talent')
    out[id!] = (await cell.getAttribute('data-rank')) ?? '0'
  }
  return out
}

async function spendEverything(page: Page): Promise<number> {
  let clicks = 0
  for (let guard = 0; guard < 200; guard++) {
    const left = Number(await page.getByTestId('points-left').textContent())
    if (left === 0) break
    const addable = page.locator('[data-talent][data-addable="true"]').first()
    if ((await addable.count()) === 0) break
    await addable.click()
    clicks++
  }
  return clicks
}

test('spend points on the example class, copy link, reload, same build', async ({ page }) => {
  await page.goto('/#/')
  await page.getByTestId('class-tinker').click()
  await expect(page.getByTestId('points-left')).toHaveText('51')
  await expect(page.getByTestId('required-level')).toHaveText('1')

  // primary page
  const primaryClicks = await spendEverything(page)
  expect(primaryClicks).toBeGreaterThan(0)
  // secondary page (the example class has two pages)
  await page.getByTestId('page-secondary').click()
  const secondaryClicks = await spendEverything(page)
  const total = primaryClicks + secondaryClicks
  await expect(page.getByTestId('points-left')).toHaveText(String(51 - total))
  await expect(page.getByTestId('required-level')).toHaveText(String(9 + total))

  // nothing is addable any more on either page
  await expect(page.locator('[data-talent][data-addable="true"]')).toHaveCount(0)
  await page.getByTestId('page-primary').click()
  await expect(page.locator('[data-talent][data-addable="true"]')).toHaveCount(0)
  const before = await snapshot(page)

  // copy link
  await page.getByTestId('copy-link').click()
  await expect(page.getByTestId('copy-link')).toHaveText('Copied!')
  let link = await page.evaluate(() => navigator.clipboard.readText()).catch(() => '')
  if (!link) link = (await page.getByTestId('copy-link').getAttribute('data-link')) ?? ''
  expect(link).toContain('#/tinker?v=')
  expect(link).toContain('&t=')
  expect(link).toBe(page.url())

  // reload the link in a fresh navigation
  await page.goto('about:blank')
  await page.goto(link)
  await expect(page.getByTestId('points-left')).toHaveText(String(51 - total))
  await expect(page.getByTestId('notices')).toHaveCount(0)
  expect(await snapshot(page)).toEqual(before)
  await page.getByTestId('page-secondary').click()
  await expect(page.locator('[data-talent][data-addable="true"]')).toHaveCount(0)
})

test('tooltip shows current and next rank plus the anticipated-ranks caveat', async ({ page }) => {
  await page.goto('/#/tinker')
  const wrench = page.getByTestId('talent-improved-wrench')
  await wrench.click()
  await wrench.hover()
  const tip = page.getByTestId('tooltip-improved-wrench')
  await expect(tip).toContainText('Rank 1/3')
  await expect(tip).toContainText('by 1 energy point.')
  await expect(tip).toContainText('Next rank:')
  await expect(tip).toContainText('by 2 energy points.')
  // Copy owned by work package A1 (Tooltip.tsx); this asserts the meaning, not the wording.
  await expect(tip).toContainText('Ranks 2-3 estimated.')
  await expect(tip).toContainText('3:38:30')
})

test('right click refunds, locked talents explain their requirement', async ({ page }) => {
  await page.goto('/#/tinker')
  const wrench = page.getByTestId('talent-improved-wrench')
  await wrench.click()
  await expect(wrench).toHaveAttribute('data-rank', '1')
  await wrench.click({ button: 'right' })
  await expect(wrench).toHaveAttribute('data-rank', '0')

  const boots = page.getByTestId('talent-rocket-boots')
  await expect(boots).toHaveAttribute('data-state', 'locked')
  await boots.hover()
  await expect(page.getByTestId('tooltip-rocket-boots')).toContainText('Requires 10 points in Gadgetry Talents')
})

test('an invalid link is adjusted and says so', async ({ page }) => {
  await page.goto('/#/tinker?v=1&t=0010')
  await expect(page.getByTestId('notices')).toContainText('did not fit the current trees')
  await expect(page.getByTestId('points-left')).toHaveText('51')
})

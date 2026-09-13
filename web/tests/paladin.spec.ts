import { expect, test } from '@playwright/test'

/** M2 checks against the first real class file, data/talents/paladin.json. */

test('class picker lists Paladin with trees, counts and the data note', async ({ page }) => {
  await page.goto('/#/')
  await expect(page).toHaveTitle('WoW Forever Talent Calculator')
  const card = page.getByTestId('class-paladin')
  await expect(card).toContainText('Paladin')
  await expect(page.locator('a[href="https://github.com/Deradon/wow-forever-talent-calc"]').first()).toBeVisible()
  await expect(page.locator('footer')).toContainText('Not affiliated')
})

test('crop icons render in the cells and the title carries per-tree points', async ({ page }) => {
  await page.goto('/#/paladin')
  await expect(page).toHaveTitle('Paladin 0/0/0 - WoW Forever Talent Calculator')
  const crops = page.locator('[data-talent][data-icon="crop"]')
  await expect(crops.first()).toBeVisible()
  // 12 of Paladin's 52 talents fall back to a frame crop; the other 40 matched
  // a Classic icon file. Both must render, neither may fall back to initials.
  expect(await crops.count()).toBeGreaterThan(5)
  expect(await page.locator('[data-talent][data-icon="file"]').count()).toBeGreaterThan(30)
  await expect(page.locator('[data-talent][data-icon="initials"]')).toHaveCount(0)
  // the images actually decoded
  await page.waitForFunction(() =>
    Array.from(document.querySelectorAll<HTMLImageElement>('[data-icon="crop"] img')).every((i) => i.complete),
  )
  const widths = await crops.locator('img').evaluateAll((imgs) => imgs.map((i) => (i as HTMLImageElement).naturalWidth))
  expect(widths.length).toBe(await crops.count())
  for (const w of widths) expect(w).toBeGreaterThan(0)

  const first = page.locator('[data-talent][data-addable="true"]').first()
  await first.click()
  await expect(page).toHaveTitle(/^Paladin (1\/0\/0|0\/1\/0|0\/0\/1) - /)
})

test('manual-rank talents say higher ranks are unknown', async ({ page }) => {
  await page.goto('/#/paladin')
  const redoubt = page.getByTestId('talent-redoubt')
  await redoubt.click()
  await redoubt.hover()
  const tip = page.getByTestId('tooltip-redoubt')
  await expect(tip).toContainText('Rank 1/5')
  await expect(tip).toContainText('Next rank:')
  // Copy owned by work package A1 (Tooltip.tsx); this asserts the meaning, not the wording.
  await expect(tip).toContainText('Not known yet.')
  await expect(tip).toContainText('Only rank 1 is known.')
  await expect(tip).not.toContainText('anticipated (manual)')
})

test('review route lists every talent, worst reading first, with crops and two tooltips', async ({ page }) => {
  await page.goto('/#/review/paladin')
  await expect(page).toHaveTitle('Review Paladin - WoW Forever Talent Calculator')
  await expect(page.getByTestId('review-stats')).toContainText('52 talents')
  const rows = page.locator('[data-testid^="review-"][data-group]')
  await expect(rows).toHaveCount(52)
  await expect(rows.first()).toHaveAttribute('data-group', 'queue')
  await expect(rows.first()).toContainText('70%')
  await expect(rows.last()).toContainText('100%')
  const first = rows.first()
  await expect(first.locator('img.review-frame')).toBeVisible()
  // The icon column is an `img` for crop icons and a placeholder for matched
  // ones until work package A1 renders `icons/<icon>.jpg` there (usability 13).
  await expect(first.locator('img.review-icon, .review-icon.review-missing')).toHaveCount(1)
  await expect(first.locator('.tooltip')).toHaveCount(2)
  await expect(first.locator('.tooltip').first()).toContainText('Rank 1/')
  const frameWidth = await first.locator('img.review-frame').evaluate((i) => (i as HTMLImageElement).naturalWidth)
  expect(frameWidth).toBeGreaterThan(0)
})

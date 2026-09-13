import { expect, test } from '@playwright/test'

/** M2 checks against the first real class file, data/talents/paladin.json. */

test('class picker lists Paladin with trees, counts and the data note', async ({ page }) => {
  await page.goto('/#/')
  await expect(page).toHaveTitle('WoW Forever Talent Calculator')
  const card = page.getByTestId('class-paladin')
  await expect(card).toContainText('Paladin')
  await expect(page.getByTestId('class-paladin-trees')).toContainText('Holy')
  await expect(page.getByTestId('class-paladin-trees')).toContainText('Retribution')
  await expect(page.getByTestId('class-paladin-talents')).toHaveText(/\d+ talents/)
  await expect(page.locator('a[href="https://github.com/Deradon/wow-forever-talent-calc"]').first()).toBeVisible()
  await expect(page.locator('footer')).toContainText('Not affiliated')
})

test('crop icons render in the cells and the title carries per-tree points', async ({ page }) => {
  await page.goto('/#/paladin')
  await expect(page).toHaveTitle('Paladin 0/0/0 - WoW Forever Talent Calculator')
  const crops = page.locator('[data-talent][data-icon="crop"]')
  await expect(crops.first()).toBeVisible()
  expect(await crops.count()).toBeGreaterThan(40)
  await expect(page.locator('[data-talent][data-icon="initials"]')).toHaveCount(0)
  // the images actually decoded
  await page.waitForFunction(() =>
    Array.from(document.querySelectorAll<HTMLImageElement>('[data-icon="crop"] img')).every((i) => i.complete),
  )
  const widths = await crops.locator('img').evaluateAll((imgs) => imgs.map((i) => (i as HTMLImageElement).naturalWidth))
  expect(widths.length).toBeGreaterThan(40)
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
  await expect(tip).toContainText('Higher ranks unknown')
  await expect(tip).toContainText('Ranks 2+ unknown')
  await expect(tip).not.toContainText('anticipated (manual)')
})

test('review route lists every talent, worst reading first, with crops and two tooltips', async ({ page }) => {
  await page.goto('/#/review/paladin')
  await expect(page).toHaveTitle('Review Paladin - WoW Forever Talent Calculator')
  await expect(page.getByTestId('review-stats')).toContainText('45 talents')
  const rows = page.locator('[data-testid^="review-"][data-group]')
  await expect(rows).toHaveCount(45)
  await expect(rows.first()).toHaveAttribute('data-group', 'queue')
  await expect(rows.first()).toContainText('70%')
  await expect(rows.last()).toContainText('100%')
  const first = rows.first()
  await expect(first.locator('img.review-frame')).toBeVisible()
  await expect(first.locator('img.review-icon')).toBeVisible()
  await expect(first.locator('.tooltip')).toHaveCount(2)
  await expect(first.locator('.tooltip').first()).toContainText('Rank 1/')
  const frameWidth = await first.locator('img.review-frame').evaluate((i) => (i as HTMLImageElement).naturalWidth)
  expect(frameWidth).toBeGreaterThan(0)
})

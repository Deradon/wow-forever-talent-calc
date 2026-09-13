import { devices, expect, test } from '@playwright/test'

/**
 * The touch path (a11y review A-2/A-3). A mobile viewport with hasTouch, not a
 * layout check: on a coarse pointer useHover never fires and there is no right
 * click, so without this a tap spent a point blind and nothing could be undone.
 */
test.use({ ...devices['Pixel 7'] })

test('a tap opens the tooltip and its +/- controls add and refund', async ({ page }) => {
  await page.goto('/#/paladin')
  const cell = page.getByTestId('talent-improved-holy-strike')

  // a11y review A-2: a tap used to spend a point and show no tooltip at all
  await cell.tap()
  await expect(page.getByTestId('tooltip-improved-holy-strike')).toBeVisible()
  await expect(cell).toHaveAttribute('data-rank', '0')

  await page.getByTestId('touch-add-improved-holy-strike').tap()
  await expect(cell).toHaveAttribute('data-rank', '1')
  await page.getByTestId('touch-add-improved-holy-strike').tap()
  await expect(cell).toHaveAttribute('data-rank', '2')

  // A-3: refunding was right-click only, so touch had no way back
  await page.getByTestId('touch-remove-improved-holy-strike').tap()
  await expect(cell).toHaveAttribute('data-rank', '1')
  await expect(page.getByTestId('points-left')).toHaveText('50')
})

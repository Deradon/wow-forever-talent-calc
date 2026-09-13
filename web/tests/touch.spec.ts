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

test('a tap opens the nested tooltips that replaced the Details disclosure', async ({ page }) => {
  await page.goto('/#/tinker')
  const cell = page.getByTestId('talent-steady-hands')

  await cell.tap()
  await expect(page.getByTestId('tooltip-steady-hands')).toBeVisible()
  await expect(cell).toHaveAttribute('data-rank', '0')

  // +/- still work, so the touch path from A2 is untouched
  await page.getByTestId('touch-add-steady-hands').tap()
  await expect(cell).toHaveAttribute('data-rank', '1')
  await page.getByTestId('touch-remove-steady-hands').tap()
  await expect(cell).toHaveAttribute('data-rank', '0')

  // the old <details> is gone; the term opens the same lines one level deeper
  await page.getByTestId('term-derivation-steady-hands').tap()
  await expect(page.getByTestId('nest-term-derivation-steady-hands')).toContainText('read from the stream')
  await expect(cell).toHaveAttribute('data-rank', '0') // the tap never reached the cell

  // and the uncertain marker opens both readings
  await page.getByTestId('term-reading-steady-hands').tap()
  await expect(page.getByTestId('nest-term-reading-steady-hands')).toContainText('A second reading')
})

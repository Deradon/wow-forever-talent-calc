import { expect, test } from '@playwright/test'

/**
 * Round 2 of the UI brief: the `#/changes` page (idea 13) with its `sel=` deep
 * links (idea 12), the level control (idea 10), the shortcut overlay (idea 14),
 * the print stylesheet (idea 15) and embed mode (idea 16).
 *
 * Paladin is the fixture again: real data with a Classic counterpart, and every
 * section of the changes page is non-empty for it.
 */

test.describe('the #/changes page', () => {
  test('lists every class, then one class section by section', async ({ page }) => {
    await page.goto('/#/changes')
    await expect(page.getByTestId('changes-overview')).toBeVisible()
    await expect(page.getByTestId('changes-row-paladin')).toBeVisible()

    await page.getByTestId('changes-link-paladin').click()
    await expect(page.getByTestId('changes-class-title')).toHaveText('Paladin vs Classic Era')

    // Six sections, each with the count the generator wrote.
    for (const [section, count] of [
      ['new', '21'],
      ['moved', '11'],
      ['rank-changed', '1'],
      ['text-changed', '13'],
      ['values-changed', '3'],
      ['gone', '13'],
    ] as const) {
      await expect(page.getByTestId(`changes-section-${section}`)).toBeVisible()
      await expect(page.getByTestId(`changes-count-${section}`)).toHaveText(count)
    }

    // A new talent, a move that names both ends, a value change, and a Classic
    // talent that is gone - one assertion per kind of claim the page makes.
    await expect(page.getByTestId('changes-item-improved-holy-strike')).toBeVisible()
    await expect(page.getByTestId('changes-item-healing-light')).toContainText('Moved from row')
    await expect(page.getByTestId('changes-item-holy-shield')).toContainText('→')
    await expect(page.getByTestId('changes-gone-consecration')).toBeVisible()

    // The word diff arrives with the lazily fetched classic-text chunk.
    const diff = page.getByTestId('changes-diff-illumination')
    await expect(diff).toBeVisible()
    await expect(diff.locator('.diff-del, .diff-add').first()).toBeVisible()
  })

  test('the filter box narrows every section at once', async ({ page }) => {
    await page.goto('/#/changes/paladin')
    await expect(page.getByTestId('changes-item-improved-holy-strike')).toBeVisible()

    await page.getByTestId('changes-filter').fill('redoubt')
    await expect(page.getByTestId('changes-count-text-changed')).toHaveText('1')
    await expect(page.getByTestId('changes-count-new')).toHaveText('0')
    await expect(page.getByTestId('changes-section-new')).toBeHidden()
    await expect(page.getByTestId('changes-item-redoubt')).toBeVisible()

    await page.getByTestId('changes-filter').fill('zzzz')
    await expect(page.getByTestId('changes-no-match')).toBeVisible()
  })

  test('a row is a deep link that opens the talent pinned on the class page', async ({ page }) => {
    await page.goto('/#/changes/paladin')
    await page.getByTestId('changes-deeplink-improved-holy-strike').click()

    await expect(page).toHaveURL(/#\/paladin\?sel=improved-holy-strike$/)
    const cell = page.getByTestId('talent-improved-holy-strike')
    await expect(cell).toHaveAttribute('data-selected', 'true')

    // Pinned means sticky: the card took the pointer, so its nested terms are
    // reachable with a mouse without the dwell-and-approach dance.
    const layer = page.getByTestId('tooltip-layer-improved-holy-strike')
    await expect(layer).toBeVisible()
    await expect(layer).toHaveAttribute('data-sticky', 'true')
    await expect(layer).toContainText('New in Forever')

    // Dismissing it takes `sel=` out of the hash, or a reload would pin it again.
    await page.keyboard.press('Escape')
    await expect(layer).toBeHidden()
    await expect(page).toHaveURL(/#\/paladin$/)
  })

  test('the class header and the landing page both point at it', async ({ page }) => {
    await page.goto('/#/paladin')
    await page.getByTestId('changes-link').click()
    await expect(page).toHaveURL(/#\/changes\/paladin$/)

    await page.goto('/#/')
    await page.getByTestId('landing-changes-link').click()
    await expect(page.getByTestId('changes-overview')).toBeVisible()
  })
})

test.describe('the keyboard shortcut overlay', () => {
  test('opens on ?, traps focus and closes on Escape', async ({ page }) => {
    await page.goto('/#/paladin')
    await expect(page.getByTestId('shortcuts-dialog')).toBeHidden()

    await page.keyboard.press('?')
    const dialog = page.getByTestId('shortcuts-dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog).toHaveAttribute('aria-modal', 'true')
    // Every shortcut round 1 shipped has a line here.
    for (const key of ['/', 'd', 'Shift', 'Ctrl', 'Esc', 'Arrows']) {
      await expect(dialog.getByText(key, { exact: true }).first()).toBeVisible()
    }

    // Focus starts inside and Tab cannot leave it.
    await expect(page.getByTestId('shortcuts-close')).toBeFocused()
    for (let i = 0; i < 4; i++) await page.keyboard.press('Tab')
    expect(await dialog.evaluate((el) => el.contains(document.activeElement))).toBe(true)

    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
  })

  test('the ? button in the site header opens the same dialog', async ({ page }) => {
    await page.goto('/#/')
    await page.getByTestId('shortcuts-open').click()
    await expect(page.getByTestId('shortcuts-dialog')).toBeVisible()
    await page.getByTestId('shortcuts-close').click()
    await expect(page.getByTestId('shortcuts-dialog')).toBeHidden()
    // Focus goes back where it came from, or the page loses the reader's place.
    await expect(page.getByTestId('shortcuts-open')).toBeFocused()
  })

  test('typing ? into the search box does not open it', async ({ page }) => {
    await page.goto('/#/paladin')
    await page.getByTestId('talent-search').fill('?')
    await expect(page.getByTestId('shortcuts-dialog')).toBeHidden()
  })
})

test.describe('embed mode', () => {
  test('shows the trees, a points line and a way out - and nothing else', async ({ page }) => {
    await page.goto('/#/paladin?embed=1')
    await expect(page.getByTestId('embed-shell')).toBeVisible()
    await expect(page.locator('[data-talent]').first()).toBeVisible()

    await expect(page.getByTestId('embed-bar')).toContainText('Paladin')
    await expect(page.getByTestId('embed-points')).toContainText('0 of 51 points')
    await expect(page.getByTestId('embed-open')).toHaveAttribute('href', /#\/paladin$/)

    // The chrome is gone: no site header, no footer, no summary column.
    await expect(page.getByTestId('build-summary')).toHaveCount(0)
    await expect(page.getByTestId('class-switcher')).toHaveCount(0)
    await expect(page.getByTestId('shortcuts-open')).toHaveCount(0)
    await expect(page.locator('footer')).toHaveCount(0)
  })

  test('still spends points, and keeps embed=1 across an edit', async ({ page }) => {
    await page.goto('/#/paladin?embed=1')
    await page.getByTestId('talent-divine-strength').click()
    await expect(page.getByTestId('talent-divine-strength')).toHaveAttribute('data-rank', '1')
    await expect(page.getByTestId('embed-points')).toContainText('1 of 51 points')
    await expect(page).toHaveURL(/embed=1/)
  })
})

test.describe('the level control and the print view', () => {
  test('says how many of the spent points a character of that level has', async ({ page }) => {
    await page.goto('/#/paladin')
    await page.getByTestId('talent-divine-strength').click({ modifiers: ['Shift'] }) // 5 points

    const line = page.getByTestId('level-line')
    await expect(page.getByTestId('level-value')).toHaveText('60')
    await expect(line).toHaveText('At level 60 you have all 5 of your 5 spent points.')

    await page.getByTestId('level-slider').fill('12')
    await expect(page.getByTestId('level-value')).toHaveText('12')
    await expect(line).toHaveText('At level 12 you have 3 of your 5 spent points - 2 too many.')
  })

  test('the print button is there and the print stylesheet hides the controls', async ({ page }) => {
    await page.goto('/#/paladin')
    await expect(page.getByTestId('print-build')).toBeVisible()

    await page.emulateMedia({ media: 'print' })
    await expect(page.getByTestId('talent-divine-strength')).toBeVisible()
    await expect(page.getByTestId('summary-trees').or(page.getByTestId('summary-empty')).first()).toBeAttached()
    await expect(page.getByTestId('reset-all')).toBeHidden()
    await expect(page.getByTestId('talent-search')).toBeHidden()
    await expect(page.locator('footer')).toBeHidden()
    await page.emulateMedia({ media: 'screen' })
  })
})

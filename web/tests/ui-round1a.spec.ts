import { expect, test, type Page } from '@playwright/test'

/**
 * UI round 1a (docs/briefs/ui-improvements.md ideas 1, 2, 5, 7, 8, 9):
 * the summary column and its exports, the class switcher, undo/redo, the
 * localStorage "Continue" card and the import flow.
 */

async function clipboard(page: Page): Promise<string> {
  return page.evaluate(() => navigator.clipboard.readText()).catch(() => '')
}

test.describe('build summary column', () => {
  test('lists spent talents by tree and exports a Discord-ready text block', async ({ page }) => {
    await page.goto('/#/tinker')
    await expect(page.getByTestId('summary-empty')).toContainText('No points spent yet')

    const wrench = page.getByTestId('talent-improved-wrench')
    await wrench.click()
    await wrench.click()

    await expect(page.getByTestId('summary-trees')).toBeVisible()
    const row = page.getByTestId('summary-talent-improved-wrench')
    await expect(row).toContainText('2/3')
    await expect(page.getByTestId('summary-title')).toContainText('level')

    await page.getByTestId('copy-text').click()
    await expect(page.getByTestId('copy-text')).toHaveText('Copied!')
    const text = await clipboard(page)
    expect(text).toContain('WoW Forever')
    expect(text).toMatch(/^Tinker \d+(\/\d+)+ \(level \d+\) - WoW Forever$/m)
    expect(text).toMatch(/^.+ \(2\): .*Improved Wrench 2\/3/m)
    expect(text).toContain('#/tinker?v=')
    // Plain text, so it survives a paste anywhere.
    expect(text).not.toMatch(/[*_`]/)
  })

  test('copies the bare build code, which the import box accepts', async ({ page }) => {
    await page.goto('/#/tinker')
    await page.getByTestId('talent-improved-wrench').click()
    await page.getByTestId('copy-code').click()
    const code = await clipboard(page)
    expect(code).toMatch(/^[0-9-]+$/)
    expect(page.url()).toContain(`&t=${code}`)
  })

  test('a summary row jumps to its cell', async ({ page }) => {
    await page.goto('/#/tinker')
    await page.getByTestId('talent-improved-wrench').click()
    await page.getByTestId('summary-talent-improved-wrench').click()
    await expect(page.getByTestId('talent-improved-wrench')).toBeFocused()
  })
})

test.describe('class switcher', () => {
  test('navigates to another class with an empty build, and Back restores the old one', async ({ page }) => {
    await page.goto('/#/paladin')
    const addable = page.locator('[data-talent][data-addable="true"]')
    await addable.first().click()
    await addable.first().click()
    await expect(page.getByTestId('points-left')).toHaveText('49')
    const spentUrl = page.url()
    expect(spentUrl).toContain('&t=')

    await expect(page.getByTestId('class-chip-paladin')).toHaveAttribute('aria-current', 'page')
    await page.getByTestId('class-chip-mage').click()

    await expect(page.locator('h1')).toHaveText('Mage')
    await expect(page.getByTestId('points-left')).toHaveText('51')
    expect(page.url()).not.toContain('&t=')
    await expect(page.getByTestId('class-chip-mage')).toHaveAttribute('aria-current', 'page')

    // The guard the brief asks for: the build you left is one Back away.
    await page.goBack()
    await expect(page.getByTestId('points-left')).toHaveText('49')
  })

  test('every chip is keyboard reachable and names its class', async ({ page }) => {
    await page.goto('/#/paladin')
    // The class route is a lazy chunk, so wait for it before counting.
    await expect(page.getByTestId('class-switcher')).toBeVisible()
    const chips = page.getByTestId('class-switcher').locator('a')
    expect(await chips.count()).toBeGreaterThanOrEqual(9)
    await expect(page.getByTestId('class-chip-warrior')).toHaveAttribute('href', '#/warrior')
    await page.getByTestId('class-chip-warrior').focus()
    await expect(page.getByTestId('class-chip-warrior')).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.locator('h1')).toHaveText('Warrior')
  })
})

test.describe('undo and redo', () => {
  test('Ctrl+Z walks back, Ctrl+Shift+Z and Ctrl+Y walk forward', async ({ page }) => {
    await page.goto('/#/paladin')
    const addable = page.locator('[data-talent][data-addable="true"]')
    await addable.first().click()
    await addable.first().click()
    await expect(page.getByTestId('points-left')).toHaveText('49')

    await page.keyboard.press('Control+z')
    await expect(page.getByTestId('points-left')).toHaveText('50')
    await page.keyboard.press('Control+z')
    await expect(page.getByTestId('points-left')).toHaveText('51')
    await expect(page.getByTestId('undo')).toBeDisabled()

    await page.keyboard.press('Control+Shift+z')
    await expect(page.getByTestId('points-left')).toHaveText('50')
    await page.keyboard.press('Control+y')
    await expect(page.getByTestId('points-left')).toHaveText('49')
    // The hash follows the stack, so the link is always the build on screen.
    expect(page.url()).toContain('&t=')
  })

  test('the buttons in the summary column do the same', async ({ page }) => {
    await page.goto('/#/paladin')
    await expect(page.getByTestId('undo')).toBeDisabled()
    await page.locator('[data-talent][data-addable="true"]').first().click()
    await page.getByTestId('undo').click()
    await expect(page.getByTestId('points-left')).toHaveText('51')
    await page.getByTestId('redo').click()
    await expect(page.getByTestId('points-left')).toHaveText('50')
  })

  test('Reset is undoable, from the button and from Ctrl+Z', async ({ page }) => {
    await page.goto('/#/paladin')
    const addable = page.locator('[data-talent][data-addable="true"]')
    await addable.first().click()
    await addable.first().click()
    await page.getByTestId('reset-all').click()
    await expect(page.getByTestId('points-left')).toHaveText('51')

    await expect(page.getByTestId('reset-undo')).toBeVisible()
    await page.getByTestId('reset-undo').click()
    await expect(page.getByTestId('points-left')).toHaveText('49')

    await page.getByTestId('reset-all').click()
    await expect(page.getByTestId('points-left')).toHaveText('51')
    await page.keyboard.press('Control+z')
    await expect(page.getByTestId('points-left')).toHaveText('49')
  })

  test('an editing session costs exactly one browser-history entry', async ({ page }) => {
    await page.goto('/#/')
    await page.getByTestId('class-paladin').click()
    for (let i = 0; i < 5; i++) await page.locator('[data-talent][data-addable="true"]').first().click()
    await expect(page.getByTestId('points-left')).toHaveText('46')

    // One Back leaves the edits; a second one leaves the class page entirely.
    await page.goBack()
    await expect(page.getByTestId('points-left')).toHaveText('51')
    await page.goBack()
    await expect(page.getByTestId('class-list')).toBeVisible()
  })
})

test.describe('import', () => {
  test('imports one of our own build codes', async ({ page }) => {
    await page.goto('/#/paladin')
    await page.locator('[data-talent][data-addable="true"]').first().click()
    const code = new URL(page.url()).hash.split('&t=')[1]!

    await page.goto('/#/paladin')
    await page.getByTestId('open-import').click()
    await page.getByTestId('import-input').fill(code)
    await page.getByTestId('import-check').click()
    await expect(page.getByTestId('import-report')).toContainText('build code')
    await page.getByTestId('import-apply').click()
    await expect(page.getByTestId('points-left')).toHaveText('50')
    expect(page.url()).toContain(`&t=${code}`)
  })

  test('imports a link to this site, including one for another class', async ({ page }) => {
    await page.goto('/#/paladin')
    await page.getByTestId('open-import').click()
    await page.getByTestId('import-input').fill('https://example.test/x/#/mage?v=1&t=5')
    await page.getByTestId('import-check').click()
    await expect(page.getByTestId('import-report')).toContainText('mage')
    await page.getByTestId('import-apply').click()
    await expect(page.locator('h1')).toHaveText('Mage')
  })

  test('imports a real Wowhead Classic string and reports what did not fit', async ({ page }) => {
    await page.goto('/#/warrior')
    await page.getByTestId('open-import').click()
    // Wowhead's own label for this string is Spec[17/34/0], Fury Warrior DPS.
    await page.getByTestId('import-input').fill('https://www.wowhead.com/classic/talent-calc/warrior/30305001302-05050005525010051')
    await page.getByTestId('import-check').click()

    const report = page.getByTestId('import-report')
    await expect(report).toContainText('of 51 points placed')
    await expect(report).toContainText('not in Forever')
    await expect(page.getByTestId('import-unplaced')).toContainText('Tactical Mastery')

    await page.getByTestId('import-apply').click()
    await expect(page.getByTestId('import-box')).toHaveCount(0)
    await expect(page.getByTestId('summary-trees')).toBeVisible()
    const left = Number(await page.getByTestId('points-left').textContent())
    expect(left).toBeGreaterThan(0)
    expect(left).toBeLessThan(51)
    // Whatever it placed is a build the rules accept, so nothing was adjusted.
    await expect(page.getByTestId('notices')).toHaveCount(0)
  })

  test('explains what it cannot read', async ({ page }) => {
    await page.goto('/#/warrior')
    await page.getByTestId('open-import').click()
    await page.getByTestId('import-input').fill('https://example.com/builds/42')
    await page.getByTestId('import-check').click()
    await expect(page.getByTestId('import-error')).toContainText('not a build link')

    await page.getByTestId('import-input').fill('https://www.wowhead.com/classic/talent-calc/mage/25002')
    await page.getByTestId('import-check').click()
    await expect(page.getByTestId('import-error')).toContainText('Open mage first')
  })
})

test('the landing page offers the last build, and forgets it on request', async ({ page }) => {
  await page.goto('/#/paladin')
  await page.locator('[data-talent][data-addable="true"]').first().click()
  await expect(page.getByTestId('points-left')).toHaveText('50')

  await page.goto('/#/')
  const card = page.getByTestId('continue-card')
  await expect(card).toContainText('Continue: Paladin')

  // The URL always wins: a bare class hash still shows an empty build.
  await page.goto('/#/paladin')
  await expect(page.getByTestId('points-left')).toHaveText('51')
  await expect(page.getByTestId('continue-line')).toContainText('Continue: Paladin')

  await page.goto('/#/')
  await page.getByTestId('continue-forget').click()
  await expect(page.getByTestId('continue-card')).toHaveCount(0)
  await page.reload()
  await expect(page.getByTestId('continue-card')).toHaveCount(0)
})

test('the wide desktop layout grows the cells and keeps the tree panels level', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 })
  await page.goto('/#/paladin')
  await expect(page.getByTestId('build-summary')).toBeVisible()

  const cell = await page.locator('[data-talent]').first().evaluate((el) => el.getBoundingClientRect().width)
  expect(cell).toBeGreaterThanOrEqual(55)

  const heights = await page
    .locator('.tree-columns > section')
    .evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().height)))
  expect(new Set(heights).size, `panel heights: ${heights.join(', ')}`).toBe(1)

  // The summary sits beside the trees, not under them.
  const summary = (await page.getByTestId('build-summary').boundingBox())!
  const trees = (await page.locator('.tree-columns').boundingBox())!
  expect(summary.x).toBeGreaterThan(trees.x + trees.width - 40)

  await page.setViewportSize({ width: 1500, height: 900 })
  const midCell = await page.locator('[data-talent]').first().evaluate((el) => el.getBoundingClientRect().width)
  expect(midCell).toBeGreaterThanOrEqual(49)
  expect(midCell).toBeLessThan(56)
})

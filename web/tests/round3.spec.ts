import { expect, test } from '@playwright/test'

/**
 * Round 3, work package E of `docs/reviews/2026-09-14-consolidated.md`: the
 * malformed-link notice (E1), the print view (E2), the import dialog (E3/E4),
 * the review wording (E4/E5), the two-line Classic diff (E6) and the agreement
 * between the change markers and the highlight rings (E7).
 */

test.describe('a link that does not fit the current trees', () => {
  // The exact string from UX review round two, finding 1: it stacked three
  // developer bars of encoding positions, talent slugs and rule reasons.
  const BAD = '/#/warrior?v=1&t=5553253055532530555325305553'

  test('says one sentence, with no internal id in it', async ({ page }) => {
    await page.goto(BAD)
    const notices = page.getByTestId('notices')
    await expect(notices).toBeVisible()
    // One bar, not three.
    await expect(notices.locator('.notice')).toHaveCount(1)

    const text = (await page.getByTestId('notice-message').textContent()) ?? ''
    expect(text).toContain('This link did not fit the current trees')
    expect(text).toContain('The build below is what fits.')
    for (const leak of ['arms #', 'prereq', 'Clamped', 'anger-management', 'improved-tactical-mastery']) {
      expect(text, `leaked "${leak}"`).not.toContain(leak)
    }
    // No title repeated verbatim inside its own body.
    expect(text.match(/This link/g)).toHaveLength(1)

    // The build is still a legal one and the trees render.
    await expect(page.getByTestId('tree-arms')).toBeVisible()
    await page.getByTestId('notices').getByRole('button', { name: 'Dismiss notice' }).click()
    await expect(page.getByTestId('notices')).toHaveCount(0)
  })

  test('puts the ids and the reasons on the console instead', async ({ page }) => {
    const logged: string[] = []
    page.on('console', (m) => logged.push(m.text()))
    await page.goto(BAD)
    await expect(page.getByTestId('notices')).toBeVisible()
    const line = logged.find((l) => l.startsWith('[build link]'))
    expect(line, 'the detail must reach the console').toBeDefined()
    expect(line).toContain('arms #')
  })

  test('garbage in the build string gets the friendly unreadable sentence', async ({ page }) => {
    await page.goto('/#/warrior?v=1&t=not-a-build')
    await expect(page.getByTestId('notice-message')).toHaveText(
      'This link could not be read; showing an empty build.',
    )
    await expect(page.getByTestId('points-left')).toHaveText('51')
  })
})

test.describe('the import dialog', () => {
  const WOWHEAD = 'https://www.wowhead.com/classic/talent-calc/embed/warrior/0503--550340510553151'

  test('is a modal, wider than the summary column, and closes on Escape', async ({ page }) => {
    // 1600x1000, the width the review drove: there the summary column is the
    // 320 px strip the import panel used to live in.
    await page.setViewportSize({ width: 1600, height: 1000 })
    await page.goto('/#/warrior')
    const summary = (await page.getByTestId('build-summary').boundingBox())!
    expect(summary.width).toBeLessThan(400)

    await page.getByTestId('open-import').click()
    const dialog = page.getByTestId('import-dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog).toHaveAttribute('role', 'dialog')
    await expect(dialog).toHaveAttribute('aria-modal', 'true')

    const box = (await dialog.boundingBox())!
    expect(box.width, 'the one prose screen must not be the narrowest column').toBeGreaterThan(summary.width)
    expect(box.width).toBeGreaterThan(560)
    // A pasted Wowhead URL used to wrap over three lines in a ~280 px textarea.
    const field = (await page.getByTestId('import-input').boundingBox())!
    expect(field.width).toBeGreaterThan(500)

    await page.keyboard.press('Escape')
    await expect(page.getByTestId('import-dialog')).toHaveCount(0)
  })

  test('reports one line per talent, with the real numbers and no truncation', async ({ page }) => {
    await page.goto('/#/warrior')
    await page.getByTestId('open-import').click()
    await page.getByTestId('import-input').fill(WOWHEAD)
    await page.getByTestId('import-check').click()

    const report = page.getByTestId('import-report')
    await expect(report).toContainText('of 51 points placed')
    const rows = await page.getByTestId('import-unplaced').locator('li').allTextContents()
    expect(rows.length).toBeGreaterThan(3)

    // One row per talent: no name appears twice.
    const names = rows.map((r) => r.split(':')[0]!.trim())
    expect(new Set(names).size, `duplicate rows: ${names.join(' | ')}`).toBe(names.length)

    // "and N more" only when the list really is cut short - it is not here.
    expect(rows.some((r) => /^and \d+ more$/.test(r))).toBe(false)

    // "fewer ranks in Forever" read as "this talent is gone"; the rows now say
    // what happened and with which numbers.
    expect(rows.join(' ')).not.toContain('fewer ranks in Forever')
    for (const row of rows) {
      expect(row).toMatch(/(points? lost, not in Forever\.|placed \d+ of \d+ points?, )/)
    }

    await page.getByTestId('import-apply').click()
    await expect(page.getByTestId('import-dialog')).toHaveCount(0)
    await expect(page.getByTestId('summary-trees')).toBeVisible()
  })
})

test.describe('the print view', () => {
  test('prints black on white, with no stars and a legible build link', async ({ page }) => {
    await page.goto('/#/warrior?v=1&t=5230000000000000000000000005-53')
    await expect(page.getByTestId('tree-arms')).toBeVisible()
    await page.emulateMedia({ media: 'print' })

    const rgb = (s: string) => (s.match(/\d+/g) ?? []).slice(0, 3).map(Number)
    const isLight = (s: string) => rgb(s).every((v) => v > 200)
    const isDark = (s: string) => rgb(s).every((v) => v < 120)

    // The three tree panels were three large black rectangles on a white page.
    for (const tree of ['arms', 'fury', 'protection']) {
      const grid = page.locator(`[data-testid="tree-${tree}"] .tree-grid`)
      const bg = await grid.evaluate((el) => getComputedStyle(el).backgroundColor)
      expect(isLight(bg), `${tree} grid background ${bg}`).toBe(true)
      const image = await grid.evaluate((el) => getComputedStyle(el).backgroundImage)
      expect(image).toBe('none')
    }

    // Everything that printed in pale gold or light grey is ink now.
    for (const id of ['points-left', 'required-level', 'tree-counts', 'summary-title']) {
      const colour = await page.getByTestId(id).evaluate((el) => getComputedStyle(el).color)
      expect(isDark(colour), `${id} printed ${colour}`).toBe(true)
    }

    // No change markers at all - neither has a legend on paper - and the build
    // URL is at body size rather than 9 px.
    await expect(page.locator('.new-flag').first()).toBeHidden()
    await expect(page.locator('.changed-flag').first()).toBeHidden()
    const link = await page.locator('.summary-head').evaluate((el) => {
      const s = getComputedStyle(el, '::after')
      return { size: s.fontSize, colour: s.color, content: s.content }
    })
    expect(link.content).toContain('#/warrior')
    expect(parseFloat(link.size)).toBeGreaterThanOrEqual(10)
    expect(isDark(link.colour)).toBe(true)

    // The summary is full width in two columns, not one narrow strip.
    const columns = await page.getByTestId('summary-trees').evaluate((el) => getComputedStyle(el).columnCount)
    expect(columns).toBe('2')

    await page.emulateMedia({ media: 'screen' })
  })
})

test.describe('the review wording is one fact from the build index', () => {
  test('no player page calls the whole dataset unreviewed', async ({ page }) => {
    for (const route of ['/#/', '/#/paladin', '/#/changes', '/#/races/dwarf', '/#/spells/mage', '/#/about']) {
      await page.goto(route)
      await expect(page.locator('#main')).toBeVisible()
      const text = (await page.locator('body').innerText()).toLowerCase()
      expect(text, `${route} still says "unreviewed"`).not.toContain('unreviewed')
      expect(text, `${route} still says "not yet reviewed"`).not.toContain('not yet reviewed')
      expect(text, `${route} still says "nothing here is reviewed"`).not.toContain('nothing here is reviewed')
      for (const word of ['vision model', 'rank-0', 'frame crops', '% confidence', 'readings)']) {
        expect(text, `${route} still says "${word}"`).not.toContain(word)
      }
    }
  })

  test('the landing page and the footer count the checked talents', async ({ page }) => {
    await page.goto('/#/')
    const caveat = page.getByTestId('landing-caveat')
    await expect(caveat).toContainText(/\d+ of \d+ talents have been checked by hand/)
    await expect(page.locator('footer')).toContainText(/\d+ of \d+ talents have been checked by hand/)
  })

  test('a class page states the rank caveat in a player’s words', async ({ page }) => {
    await page.goto('/#/paladin')
    await expect(page.getByTestId('class-ranks-line')).toHaveText(
      'Only the first rank of each talent was on screen; ranks above that are estimated from Classic Era.',
    )
  })
})

test.describe('the Classic diff is two sentences, never one interleaved run', () => {
  test('#/changes/<class> labels both lines and keeps each side’s marks to itself', async ({ page }) => {
    await page.goto('/#/changes/warrior')
    const section = page.getByTestId('changes-section-text-changed')
    await expect(section).toBeVisible()

    const first = section.locator('[data-testid^="changes-diff-"]').first()
    const classic = first.locator('.classic-line-classic')
    const forever = first.locator('.classic-line-forever')
    await expect(classic).toBeVisible()
    await expect(forever).toBeVisible()
    await expect(classic).toContainText('Classic Era')
    await expect(forever).toContainText('Forever')

    // The Classic line carries no "added" run and the Forever line no "dropped" one.
    await expect(classic.locator('.diff-add')).toHaveCount(0)
    await expect(forever.locator('.diff-del')).toHaveCount(0)
    // Both carry at least one mark between them, or there would be no diff.
    expect(
      (await classic.locator('.diff-del').count()) + (await forever.locator('.diff-add').count()),
    ).toBeGreaterThan(0)
  })

  test('the nested tooltip card draws the same two lines', async ({ page }) => {
    // Same walk into the sticky layer as tests/changes.spec.ts.
    await page.goto('/#/priest')
    const cell = page.getByTestId('talent-shadowform')
    await expect(cell).toHaveAttribute('data-change', 'text-changed')
    await cell.hover()

    const layer = page.getByTestId('tooltip-layer-shadowform')
    await expect(layer).toBeVisible()
    await page.waitForTimeout(400)
    const box = (await layer.boundingBox())!
    await page.mouse.move(box.x + 40, box.y + 16, { steps: 30 })
    await expect(layer).toHaveAttribute('data-sticky', 'true')

    const term = page.getByTestId('term-classic-shadowform')
    const termBox = (await term.boundingBox())!
    await page.mouse.move(termBox.x + termBox.width / 2, termBox.y + termBox.height / 2, { steps: 10 })

    const card = page.getByTestId('classic-shadowform')
    await expect(card).toBeVisible()
    const classic = card.locator('.classic-line-classic')
    const forever = card.locator('.classic-line-forever')
    await expect(classic).toContainText('Classic Era')
    await expect(forever).toContainText('Forever')
    await expect(classic.locator('.diff-add')).toHaveCount(0)
    await expect(forever.locator('.diff-del')).toHaveCount(0)
    // The Classic sentence, not ours: Classic Shadowform blocked Holy spells.
    await expect(classic).toContainText('Holy')
  })
})

test.describe('markers and highlight rings say the same thing', () => {
  test('a star means new, a diamond means reworked, and the rings match', async ({ page }) => {
    await page.goto('/#/paladin')
    await page.getByTestId('highlight-new').click()

    const shadow = (sel: string) => page.locator(sel).first().evaluate((el) => getComputedStyle(el).boxShadow)

    // New: blue star, blue ring.
    const newCell = page.locator('[data-change="new"]').first()
    await expect(newCell.locator('.new-flag')).toBeVisible()
    await expect(newCell.locator('.changed-flag')).toHaveCount(0)
    expect(await shadow('[data-change="new"]')).toContain('rgb(78, 163, 255)')

    // Reworked: amber diamond, amber ring, and never a star.
    const reworked = page.locator('[data-change="text-changed"]').first()
    await expect(reworked.locator('.changed-flag')).toBeVisible()
    await expect(reworked.locator('.new-flag')).toHaveCount(0)
    expect(await shadow('[data-change="text-changed"]')).toContain('rgb(232, 163, 61)')

    // Moved: a ring of its own and no corner marker at all.
    const moved = page.locator('[data-change="moved"]').first()
    await expect(moved.locator('.new-flag')).toHaveCount(0)
    await expect(moved.locator('.changed-flag')).toHaveCount(0)

    // Unchanged: no marker, and dimmed rather than ringed.
    const same = page.locator('[data-change="same"]').first()
    await expect(same.locator('.new-flag')).toHaveCount(0)
    await expect(same.locator('.changed-flag')).toHaveCount(0)

    // Three slots, still no collision, now with the diamond in the star's slot.
    const diamond = (await reworked.locator('.changed-flag').boundingBox())!
    const badge = (await reworked.locator('.badge').boundingBox())!
    expect(diamond.y + diamond.height).toBeLessThanOrEqual(badge.y)
    expect(diamond.height).toBeGreaterThanOrEqual(16)

    // The legend explains both of them.
    await expect(page.getByTestId('badge-legend')).toContainText('= new in Forever')
    await expect(page.getByTestId('badge-legend')).toContainText('= reworked in Forever')
  })
})

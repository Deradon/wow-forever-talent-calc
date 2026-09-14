import { expect, test, type Locator, type Page } from '@playwright/test'

/**
 * Crusader Kings style sticky, nested tooltips.
 *
 * Work package A2 reverted an always-interactive tooltip layer because it
 * covered the neighbouring cell and two suites started failing on intercepted
 * clicks. The layer is now transparent until the player has both dwelled on the
 * cell and walked into the tooltip, so these cases guard the two halves against
 * each other: the sticky path must work, and the brisk path must not trigger it.
 */

const DWELL = 400 // > CELL_DWELL_MS (250) in src/ui/stickyTooltip.ts

/** Walk the pointer into an open tooltip the way a hand does: in small steps. */
async function approach(page: Page, layer: Locator): Promise<void> {
  const box = await layer.boundingBox()
  if (!box) throw new Error('the tooltip layer has no box')
  await page.mouse.move(box.x + 40, box.y + 16, { steps: 30 })
}

/** Hover a cell, wait out the dwell, then walk into its tooltip. */
async function makeSticky(page: Page, talentId: string): Promise<Locator> {
  await page.getByTestId(`talent-${talentId}`).hover()
  const layer = page.getByTestId(`tooltip-layer-${talentId}`)
  await expect(layer).toBeVisible()
  await page.waitForTimeout(DWELL)
  await approach(page, layer)
  await expect(layer).toHaveAttribute('data-sticky', 'true')
  return layer
}

/** Hover a term inside an already sticky tooltip and wait for its nested card. */
async function openNested(page: Page, termTestId: string): Promise<Locator> {
  const term = page.getByTestId(termTestId)
  const box = await term.boundingBox()
  if (!box) throw new Error(`${termTestId} has no box`)
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 })
  const nest = page.getByTestId(`nest-${termTestId}`)
  await expect(nest).toBeVisible()
  return nest
}

test('a tooltip goes sticky when the pointer walks into it, and the derivation is readable', async ({ page }) => {
  await page.goto('/#/tinker')
  const layer = await makeSticky(page, 'improved-wrench')

  // the trust line is the term: hovering it opens the derivation one level deeper
  const nest = await openNested(page, 'term-derivation-improved-wrench')
  await expect(nest).toContainText('Rank 1 was read from the stream')
  await expect(nest).toContainText('3:38:30')

  // and the rank numbers carry the Classic Era values they were scaled from
  await expect(page.getByTestId('term-ranks-improved-wrench')).toBeVisible()

  // Escape closes the whole chain and the layer is gone with it
  await page.keyboard.press('Escape')
  await expect(layer).toHaveCount(0)
})

test('the rank term shows the Classic values, and only one nested tooltip is open at a time', async ({ page }) => {
  await page.goto('/#/tinker')
  await makeSticky(page, 'improved-wrench')

  const ranks = await openNested(page, 'term-ranks-improved-wrench')
  await expect(ranks).toContainText('Values by rank: 1/2/3.')
  await expect(ranks).toContainText('Classic Era: 1/2/3.')

  await openNested(page, 'term-derivation-improved-wrench')
  await expect(page.getByTestId('nest-term-ranks-improved-wrench')).toHaveCount(0)
})

test('the neighbour under a sticky tooltip is clickable again as soon as it closes', async ({ page }) => {
  await page.goto('/#/tinker')
  const wrench = page.getByTestId('talent-improved-wrench')
  const neighbour = page.getByTestId('talent-steady-hands') // row 0, col 2: right under the tooltip

  const layer = await makeSticky(page, 'improved-wrench')
  const tip = (await layer.boundingBox())!
  const cell = (await neighbour.boundingBox())!
  expect(tip.x).toBeLessThan(cell.x + cell.width) // it really does cover it
  expect(tip.x + tip.width).toBeGreaterThan(cell.x)

  // leaving the tooltip closes it; nothing has to be clicked to get the grid back
  await page.mouse.move(tip.x + tip.width + 120, tip.y + 220, { steps: 20 })
  await expect(layer).toHaveCount(0)

  await neighbour.click()
  await expect(neighbour).toHaveAttribute('data-rank', '1')
  await expect(wrench).toHaveAttribute('data-rank', '0')
})

test('a brisk click sequence across a row never makes a tooltip sticky', async ({ page }) => {
  await page.goto('/#/tinker')
  const wrench = page.getByTestId('talent-improved-wrench')
  const hands = page.getByTestId('talent-steady-hands')

  for (let i = 0; i < 3; i++) {
    await wrench.click()
    await hands.click()
    // the layer may well be open - it must never have taken the pointer
    await expect(page.locator('.tooltip-layer[data-sticky="true"]')).toHaveCount(0)
  }
  await expect(wrench).toHaveAttribute('data-rank', '3')
  await expect(hands).toHaveAttribute('data-rank', '3')
  await expect(page.getByTestId('points-left')).toHaveText('45')
})

test('a prerequisite name opens that talent’s own card', async ({ page }) => {
  await page.goto('/#/paladin')
  // 10 points into Protection without touching Redoubt: the row is unlocked, so
  // what still blocks Shield Specialization is the prerequisite, by name.
  const spend = async (talent: string, times: number) => {
    for (let i = 0; i < times; i++) await page.getByTestId(`talent-${talent}`).click()
  }
  await spend('toughness', 5)
  await spend('precision', 3)
  await spend('guardians-favor', 2)
  await expect(page.getByTestId('tree-points-protection')).toHaveText('10')

  const target = page.getByTestId('talent-shield-specialization')
  await expect(target).toHaveAttribute('data-addable', 'false')

  await makeSticky(page, 'shield-specialization')
  await expect(page.getByTestId('tooltip-shield-specialization')).toContainText('Requires 5 points in Redoubt')

  const card = await openNested(page, 'term-prereq-redoubt')
  await expect(card).toContainText('Redoubt')
  await expect(card).toContainText('Rank 0/5')
  // one level deep only: the nested card carries no terms of its own
  await expect(card.locator('.tip-term')).toHaveCount(0)
})

test('the uncertain marker shows both readings and the captured crop', async ({ page }) => {
  await page.goto('/#/tinker')
  await makeSticky(page, 'steady-hands')

  const nest = await openNested(page, 'term-reading-steady-hands')
  await expect(nest).toContainText('The version shown')
  await expect(nest).toContainText('A second transcription')
  await expect(nest).toContainText('Steady Hand')
  await expect(nest).not.toContainText(/qwen|rapidocr/i)

  const crop = nest.locator('img.reading-crop')
  await expect(crop).toBeVisible()
  await expect
    .poll(async () => crop.evaluate((i) => (i as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0)
})

test('`d` opens the derivation in place, without a pointer', async ({ page }) => {
  await page.goto('/#/tinker')
  const cell = page.getByTestId('talent-improved-wrench')
  await cell.focus() // keyboard only: the tooltip opens on focus and stays transparent

  const block = page.getByTestId('derivation-improved-wrench')
  await expect(block).toHaveCount(0)
  await page.keyboard.press('d')
  await expect(block).toBeVisible()
  await expect(block).toContainText('Rank 1 was read from the stream')
  await page.keyboard.press('d')
  await expect(block).toHaveCount(0)

  // and it is still announced while collapsed, because aria-describedby
  // flattens the whole tooltip subtree
  const described = await cell.getAttribute('aria-describedby')
  await expect(page.locator(`#${described}`)).toContainText('Rank 1 was read from the stream')
})

test('tooltips prefer the placements that cover fewer cells', async ({ page }) => {
  // last rows open upwards, so they do not run off the grid or over the header
  await page.goto('/#/tinker')
  const deep = page.getByTestId('talent-overclock') // row 6 of 7
  await deep.hover()
  const deepLayer = page.getByTestId('tooltip-layer-overclock')
  await expect(deepLayer).toBeVisible()
  const cellBox = (await deep.boundingBox())!
  const tipBox = (await deepLayer.boundingBox())!
  expect(tipBox.y).toBeLessThan(cellBox.y)
  expect(tipBox.y + tipBox.height).toBeLessThan(cellBox.y + cellBox.height + 40)

  // the last column opens to the left, so it covers the gutter and not the row
  await page.goto('/#/paladin')
  const edge = page.getByTestId('talent-crusade') // Retribution, col 3 of 4
  await edge.hover()
  const edgeLayer = page.getByTestId('tooltip-layer-crusade')
  await expect(edgeLayer).toBeVisible()
  const edgeCell = (await edge.boundingBox())!
  const edgeTip = (await edgeLayer.boundingBox())!
  expect(edgeTip.x + edgeTip.width).toBeLessThanOrEqual(edgeCell.x + 1)
})

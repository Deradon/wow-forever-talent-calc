import { expect, test } from '@playwright/test'

/**
 * Phase 2b's web half: `#/races` (the race/class matrix) and `#/races/<race>`
 * (the traits), spec in `docs/handover/2026-09-13-races-data.md` section 5.
 *
 * Dwarf is the fixture for a plain race - four traits, one of each verdict
 * except `unknown`, and Shaman is a combination Classic Era did not allow.
 * Skyborne is the fixture for variants, because it is the only race that has
 * any and the two variants disagree about Mage and Shaman.
 */

test('the matrix marks the combinations Classic Era did not allow', async ({ page }) => {
  await page.goto('/#/races')
  await expect(page.getByTestId('races-table')).toBeVisible()

  // Dwarf Shaman is new; Dwarf Warrior is not; Dwarf Druid is not playable.
  await expect(page.getByTestId('races-cell-dwarf-shaman')).toHaveAttribute('data-state', 'new')
  await expect(page.getByTestId('races-cell-dwarf-warrior')).toHaveAttribute('data-state', 'playable')
  await expect(page.getByTestId('races-cell-dwarf-druid')).toHaveAttribute('data-state', 'no')
  // Night Elf gained nothing, so no cell in its row may claim otherwise.
  await expect(page.locator('[data-testid^="races-cell-night-elf-"][data-state="new"]')).toHaveCount(0)

  // A cell is the way into that class's calculator.
  await page.getByTestId('races-cell-dwarf-shaman').getByRole('link').click()
  await expect(page).toHaveURL(/#\/shaman$/)
  await expect(page.locator('[data-talent]').first()).toBeVisible()
})

test('the two Skyborne variants are separate rows on their own faction side', async ({ page }) => {
  await page.goto('/#/races')
  const high = page.getByTestId('races-row-skyborne:high-order')
  const wind = page.getByTestId('races-row-skyborne:windshaper')
  await expect(high).toBeVisible()
  await expect(wind).toBeVisible()
  await expect(high).toContainText('High Order Skyborne')
  await expect(high).toContainText('Alliance')
  await expect(wind).toContainText('Horde')

  // The whole reason they are two rows: High Order has Mage, Windshaper has
  // Shaman, and neither has the other's.
  await expect(page.getByTestId('races-cell-skyborne:high-order-mage')).toHaveAttribute('data-state', 'new')
  await expect(page.getByTestId('races-cell-skyborne:high-order-shaman')).toHaveAttribute('data-state', 'no')
  await expect(page.getByTestId('races-cell-skyborne:windshaper-shaman')).toHaveAttribute('data-state', 'new')
  await expect(page.getByTestId('races-cell-skyborne:windshaper-mage')).toHaveAttribute('data-state', 'no')
})

test('a race page shows its traits, their verdicts and the source once', async ({ page }) => {
  await page.goto('/#/races')
  await page.getByTestId('races-link-dwarf').click()
  await expect(page).toHaveURL(/#\/races\/dwarf$/)

  await expect(page.getByTestId('race-title')).toHaveText('Dwarf')
  await expect(page.getByTestId('race-faction')).toHaveText('Alliance')
  await expect(page.getByTestId('race-classes')).toContainText('Shaman')

  // Four traits in box order, each with an icon crop and a vs-Classic chip.
  const traits = page.locator('[data-testid^="trait-"][data-kind]')
  await expect(traits).toHaveCount(4)
  await expect(page.getByTestId('trait-stoneform')).toContainText('Immunity to Bleeds')
  await expect(page.getByTestId('trait-chip-stoneform')).toHaveText('Changed')
  await expect(page.getByTestId('trait-chip-mace-specialization')).toHaveText('New')
  await expect(page.getByTestId('trait-chip-find-treasure')).toHaveText('Same')
  await expect(page.getByTestId('trait-stoneform').locator('img.races-trait-icon')).toBeVisible()

  // The provenance is stated once for the page, not on every card.
  await expect(page.getByTestId('race-trust')).toContainText('Read from the stream')
  await expect(page.getByTestId('race-trust')).toContainText('checked by a reviewer')
  await expect(page.locator('.races-trust-line')).toHaveCount(0)

  // The Classic side is nested and labelled unverified, never shown as game text.
  const classic = page.getByTestId('trait-classic-stoneform')
  await expect(classic.locator('.races-classic-text')).toBeHidden()
  await expect(classic).toContainText('unverified')
  await classic.locator('summary').click()
  await expect(classic.locator('.races-classic-text')).toContainText('increases armor by 10%')
  await expect(classic).not.toContainText('data/prior')

  // The timestamp and the frame live behind Details.
  const details = page.getByTestId('trait-details-stoneform')
  await details.locator('summary').click()
  await expect(details).toContainText(/Read from the stream at \d:\d\d:\d\d\./)
  await expect(page.getByTestId('trait-crop-stoneform')).toHaveAttribute('href', /\.png$/)

  // A new trait has no Classic sentence to show, only the reason it counts as
  // new - which comes from the same unverified prior and says so.
  const isNew = page.getByTestId('trait-classic-mace-specialization')
  await expect(isNew).toContainText('Not in Classic Era')
  await expect(isNew).toContainText('unverified')
  await isNew.locator('summary').click()
  await expect(isNew.locator('.races-classic-text')).toHaveCount(0)
  await expect(isNew).toContainText('No Classic Era racial called Mace Specialization')
})

test('the variant tabs swap the traits, the classes and the lore', async ({ page }) => {
  await page.goto('/#/races/skyborne')
  // Alliance is the default.
  await expect(page.getByTestId('race-title')).toHaveText('High Order Skyborne')
  await expect(page.getByTestId('race-variant-high-order')).toHaveAttribute('data-active', 'true')
  await expect(page.getByTestId('race-classes')).toContainText('Mage')
  await expect(page.getByTestId('race-classes')).not.toContainText('Shaman')
  await expect(page.getByTestId('trait-read-ley-line')).toBeVisible()
  await expect(page.getByTestId('trait-skysight')).toHaveCount(0)

  await page.getByTestId('race-variant-windshaper').click()
  await expect(page).toHaveURL(/#\/races\/skyborne\?variant=windshaper$/)
  await expect(page.getByTestId('race-title')).toHaveText('Windshaper Skyborne')
  await expect(page.getByTestId('race-faction')).toHaveText('Horde')
  await expect(page.getByTestId('race-classes')).toContainText('Shaman')
  await expect(page.getByTestId('race-classes')).not.toContainText('Mage')
  // Windshaper-only, High-Order-only and shared, in that order of evidence.
  await expect(page.getByTestId('trait-skysight')).toBeVisible()
  await expect(page.getByTestId('trait-read-ley-line')).toHaveCount(0)
  await expect(page.getByTestId('trait-walk-on-air')).toBeVisible()

  // Variant lore, not the race's - Skyborne has none of its own.
  const lore = page.getByTestId('race-lore')
  await lore.locator('summary').click()
  await expect(lore).toContainText('Windshapers')

  // The deep link stands on its own, and nonsense falls back rather than
  // emptying the page.
  await page.goto('/#/races/skyborne?variant=windshaper')
  await expect(page.getByTestId('race-title')).toHaveText('Windshaper Skyborne')
  await page.goto('/#/races/skyborne?variant=nope')
  await expect(page.getByTestId('race-title')).toHaveText('High Order Skyborne')
})

test('races is reachable from the header and the landing page, and costs the calculator nothing', async ({ page }) => {
  const scripts: string[] = []
  page.on('request', (r) => {
    if (r.resourceType() === 'script') scripts.push(new URL(r.url()).pathname)
  })

  await page.goto('/#/')
  await expect(page.getByTestId('landing-races-link')).toBeVisible()
  await page.waitForTimeout(300)
  // The landing page still fetches the entry chunk and nothing else: the races
  // index rides in the races chunk, not in everyone's first load.
  expect(scripts.filter((p) => /RacesPage/.test(p))).toHaveLength(0)

  await page.getByTestId('landing-races-link').click()
  await expect(page.getByTestId('races-matrix')).toBeVisible()

  await page.goto('/#/paladin')
  await expect(page.locator('[data-talent]').first()).toBeVisible()
  await page.getByTestId('nav-races').click()
  await expect(page).toHaveURL(/#\/races$/)
  await expect(page.getByTestId('races-table')).toBeVisible()

  // An unknown race says so instead of rendering an empty page.
  await page.goto('/#/races/murloc')
  await expect(page.getByTestId('races-error')).toContainText('Unknown race')
})

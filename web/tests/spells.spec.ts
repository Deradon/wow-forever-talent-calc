import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/** Counts read from the build-time index, so a data correction does not fail a wording test. */
interface SpellCard {
  id: string
  entries: number
  withText: number
  new: number
}
const index = JSON.parse(
  readFileSync(fileURLToPath(new URL('../src/data/spells-index.json', import.meta.url)), 'utf8'),
) as { classes: SpellCard[] }
const card = (id: string) => index.classes.find((c) => c.id === id)!

/**
 * Phase 2d's web half: `#/spells` (what each class's spellbook showed) and
 * `#/spells/<class>` (the entries and the full tooltips), spec in
 * `docs/handover/2026-09-13-spells-data.md` section 5.
 *
 * Mage is the fixture for a class page: four tabs, and more tooltips than rows
 * with text - some spells were hovered twice, which is why the card counts rows
 * with text rather than tooltips. The entry counts come from
 * `src/data/spells-index.json` rather than being typed in, because the spell
 * data is still being corrected and a stale number here fails for a reason that
 * has nothing to do with the sentence under test. Warlock and rogue are the fixtures for a gap - one tab open,
 * three never - and priest for a class the stream never showed at all.
 */

test('the overview cards say what was seen and what was never opened', async ({ page }) => {
  await page.goto('/#/spells')
  await expect(page.getByTestId('spells-cards')).toBeVisible()
  await expect(page.locator('li.spells-card')).toHaveCount(8)

  await expect(page.getByTestId('spells-card-counts-mage')).toHaveText(
    `${card('mage').entries} entries seen, ${card('mage').withText} with full text`,
  )
  await expect(page.getByTestId('spells-card-gap-rogue')).toHaveText('Assassination, Combat and Subtlety never opened')
  await expect(page.getByTestId('spells-card-gap-hunter')).toHaveCount(0)
  await expect(page.getByTestId('spells-card-new-shaman')).toHaveText(`${card('shaman').new} new`)

  // The class the footage never showed is named, not silently missing.
  await expect(page.getByTestId('spells-absent')).toHaveText(
    'Priest never appeared in the footage, so there is no priest page.',
  )
  await expect(page.getByTestId('spells-card-priest')).toHaveCount(0)

  await page.getByTestId('spells-card-mage').getByRole('link').first().click()
  await expect(page).toHaveURL(/#\/spells\/mage$/)
  await expect(page.getByTestId('spells-title')).toHaveText('Mage')
})

test('a class page leads with the coverage record and groups the list by tab', async ({ page }) => {
  await page.goto('/#/spells/druid')
  await expect(page.getByTestId('spells-coverage')).toHaveText(
    `Spells seen on stream: ${card('druid').entries} entries across Balance, Feral Combat, Restoration; ${card('druid').withText} with full text. The General page was not shown.`,
  )
  // One sentence with a number in it, not the word "unreviewed" (E4/E5).
  await expect(page.getByTestId('spells-trust')).toContainText('Read from BlizzCon 2026 footage.')
  await expect(page.getByTestId('spells-trust')).toContainText('has been checked by hand yet')
  await expect(page.getByTestId('spells-trust')).not.toContainText('not yet reviewed')

  // The groups are the spellbook's tabs, in the spellbook's order.
  const groups = page.locator('[data-testid^="spells-group-"]')
  await expect(groups).toHaveCount(3)
  await expect(groups.first()).toContainText('Balance')
  await expect(page.getByTestId('spells-group-restoration')).toContainText('Restoration')

  // A row: icon crop, name, the rank that was on screen.
  const healingTouch = page.getByTestId('spell-healing-touch')
  await expect(healingTouch.locator('img.spells-icon')).toBeVisible()
  await expect(healingTouch).toContainText('Healing Touch')
  await expect(healingTouch.locator('.spells-rank')).toContainText('Rank')

  // Every row read below the review threshold carries the tooltip's amber
  // line, and no other row does. Which rows those are is read from the data,
  // because the spell readings are still being corrected.
  const druid = JSON.parse(
    readFileSync(fileURLToPath(new URL('../../data/spells/druid.json', import.meta.url)), 'utf8'),
  ) as { spells: { id: string; source: { confidence?: number; reviewed?: boolean } }[] }
  const shaky = druid.spells.filter((s) => !s.source.reviewed && (s.source.confidence ?? 1) < 0.8)
  await expect(page.locator('.spells-trust-line')).toHaveCount(shaky.length)
  for (const row of shaky) {
    await expect(page.getByTestId(`spell-${row.id}`).locator('.spells-trust-line')).toHaveText('Check this reading.')
  }

  // The calculator is one click away from the spellbook.
  await page.getByTestId('spells-talents-link').click()
  await expect(page).toHaveURL(/#\/druid$/)
  await expect(page.locator('[data-talent]').first()).toBeVisible()
})

test('the full text opens under the row, and a row without one shows nothing extra', async ({ page }) => {
  await page.goto('/#/spells/mage')

  const arcaneExplosion = page.getByTestId('spell-arcane-explosion')
  const text = page.getByTestId('spell-text-arcane-explosion')
  await expect(text.locator('.spells-tooltip-text')).toBeHidden()
  await text.locator('summary').click()
  await expect(text.locator('.spells-tooltip-text').first()).toContainText('explosion of arcane magic')
  await expect(text).toContainText('250 Mana')
  // Rule 4: a hover that could not be tied to a row must not read as rank 1.
  await expect(text).toContainText('One rank; which one was not on screen.')
  await expect(arcaneExplosion.getByTestId('spell-frame-link').first()).toBeVisible()

  // Rule 7: the New chip, with its caveat stated once at the top of the page.
  await expect(page.getByTestId('spell-new-arcane-blast')).toHaveText('New')
  await expect(page.getByTestId('spells-new-caveat')).toContainText('written from memory')
  await expect(page.locator('[data-testid^="spell-new-"]')).toHaveCount(card('mage').new)

  // A row nobody hovered carries no disclosure at all - no "no text" line.
  const plain = page.getByTestId('spell-polymorph')
  await expect(plain).toBeVisible()
  await expect(plain.locator('details')).toHaveCount(0)
})

test('the class the stream never showed says so instead of 404ing', async ({ page }) => {
  await page.goto('/#/spells/priest')
  await expect(page.getByTestId('spells-error')).toContainText('never on screen')
  await page.getByRole('link', { name: 'All classes' }).click()
  await expect(page.getByTestId('spells-cards')).toBeVisible()
})

test('the spell pages carry no pipeline words, and no other route loads their crops', async ({ page }) => {
  const scripts: string[] = []
  page.on('request', (r) => {
    if (r.resourceType() === 'script') scripts.push(new URL(r.url()).pathname)
  })

  // The overview runs off the generated index: no class file, no crop module.
  await page.goto('/#/spells')
  await expect(page.getByTestId('spells-cards')).toBeVisible()
  await page.waitForTimeout(300)
  expect(scripts.filter((p) => /spells-[a-z]+-[^/]+\.js$/.test(p))).toHaveLength(0)

  await page.goto('/#/spells/mage')
  await expect(page.getByTestId('spells-title')).toHaveText('Mage')
  await page.waitForTimeout(300)
  // Exactly one class's crop URLs, never the whole 14 MB spellbook registry.
  const cropChunks = scripts.filter((p) => /spells-[a-z]+-[^/]+\.js$/.test(p))
  expect(cropChunks, `crop chunks: ${cropChunks.join(', ')}`).toHaveLength(1)
  expect(cropChunks[0]).toMatch(/spells-mage-/)

  // Wording rules (docs/reviews/2026-09-13-text-quality.md): nothing about how
  // the data was made reaches the page.
  for (const hash of ['#/spells', '#/spells/mage']) {
    await page.goto(`/${hash}`)
    await page.waitForTimeout(200)
    const body = (await page.locator('main').innerText()).toLowerCase()
    for (const word of ['vlm', 'reader', 'confidence', 'codex', 'stage ', 'pipeline', '.json', '.py']) {
      expect(body, `${hash} says "${word}"`).not.toContain(word)
    }
  }
})

test('the header and the landing page lead to the spells overview', async ({ page }) => {
  await page.goto('/#/')
  await expect(page.getByTestId('landing-spells-link')).toBeVisible()
  await page.getByTestId('nav-spells').click()
  await expect(page).toHaveURL(/#\/spells$/)
  await expect(page.getByTestId('spells-cards')).toBeVisible()
})

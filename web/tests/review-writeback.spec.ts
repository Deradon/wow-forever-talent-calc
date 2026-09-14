import { expect, test } from '@playwright/test'

/**
 * The write-back half of `#/review/<class>`: the per-row "Copy override"
 * button, the "Copy all flagged" button and the prefilled issue link. The
 * clipboard is readable here because `playwright.config.ts` grants
 * clipboard-read / clipboard-write to the context.
 *
 * The example class `tinker` is used deliberately: it ships with the repo as a
 * fixture, so the ids and the confidences these assertions rely on do not move
 * when a real class is re-exported.
 */

const TALENT = 'improved-wrench'

test('copy override puts one schema-shaped entry on the clipboard', async ({ page }) => {
  await page.goto(`/#/review/tinker`)
  const button = page.getByTestId(`copy-override-${TALENT}`)
  await expect(button).toHaveText('Copy override')
  await button.click()
  await expect(button).toHaveText('Copied!')

  const text = await page.evaluate(() => navigator.clipboard.readText())
  // Indented to its place inside the "overrides": [ ... ] array of the file.
  expect(text.startsWith('    {')).toBe(true)
  const entry = JSON.parse(text) as Record<string, unknown>
  expect(entry).toMatchObject({
    talent: TALENT,
    tree: 'gadgetry',
    set: { name: 'Improved Wrench', source: { reviewed: true } },
    by: 'TODO',
  })
  expect(String(entry.reason)).toContain('TODO')
  // RFC 3339, as the schema's `at` requires.
  expect(String(entry.at)).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/)
  // Only keys section 6.2 allows.
  for (const key of Object.keys(entry)) {
    expect(['talent', 'tree', 'set', 'unset', 'rename', 'delete', 'add', 'reason', 'by', 'at']).toContain(key)
  }
  // The description is prefilled from the record, so the reviewer edits in place.
  const set = entry.set as { description: string }
  expect(set.description).toContain('Wrench Strike')
})

test('copy all flagged follows the filter and yields the array elements', async ({ page }) => {
  await page.goto(`/#/review/tinker`)
  const all = page.getByTestId('copy-all-overrides')
  const total = Number((await all.textContent())!.match(/\((\d+)\)/)![1])
  expect(total).toBeGreaterThan(1)

  // Narrow to the review queue first: "flagged" is whatever the filter shows.
  await page.getByRole('button', { name: /^queue \(/ }).click()
  const queued = Number((await all.textContent())!.match(/\((\d+)\)/)![1])
  expect(queued).toBeGreaterThan(0)
  expect(queued).toBeLessThan(total)

  await all.click()
  await expect(all).toHaveText('Copied!')
  const text = await page.evaluate(() => navigator.clipboard.readText())
  // Elements, not a bracketed array: they go inside the array the file has.
  expect(text.trim().startsWith('[')).toBe(false)
  const entries = JSON.parse(`[${text}]`) as { talent: string }[]
  expect(entries).toHaveLength(queued)
  for (const entry of entries) expect(entry.talent.length).toBeGreaterThan(0)
})

test('the review page says where to paste and links the report form', async ({ page }) => {
  await page.goto(`/#/review/tinker`)
  await expect(page.getByText('data/overrides/tinker.json').first()).toBeVisible()

  const report = page.getByTestId(`report-${TALENT}`)
  const href = new URL((await report.getAttribute('href'))!)
  expect(href.pathname).toBe('/Deradon/wow-forever-talent-calc/issues/new')
  expect(href.searchParams.get('template')).toBe('wrong-reading.yml')
  expect(href.searchParams.get('class')).toBe('tinker')
  expect(href.searchParams.get('record')).toBe(`gadgetry/${TALENT}`)
})

test('the about page is reachable from the footer and states the caveats', async ({ page }) => {
  await page.goto('/#/')
  await page.getByTestId('footer-about').click()
  await expect(page).toHaveURL(/#\/about$/)
  const main = page.locator('#main')
  await expect(main).toContainText('not endorsed')
  await expect(main).toContainText('first rank')
  await expect(page.getByTestId('about-changes-link')).toBeVisible()
  await expect(page.getByTestId('about-issues-link')).toBeVisible()
  await expect(page.getByTestId('about-repo-link')).toBeVisible()
  // Player-facing: no pipeline vocabulary on this page.
  const text = (await main.textContent())!.toLowerCase()
  for (const word of ['pipeline', 'stage ', 'override', 'confidence', 'qwen', 'ocr', 'json']) {
    expect(text).not.toContain(word)
  }
})

import { expect, test } from '@playwright/test'

/**
 * Performance review P-1/P-2: the landing page used to import all nine class
 * chunks to print a few hundred bytes of text, and every first load carried the
 * registry of all 971 review crops. Both are now build-time artefacts.
 */

test('the landing page loads no class chunk and no review code', async ({ page }) => {
  const scripts: string[] = []
  page.on('request', (r) => {
    if (r.resourceType() === 'script') scripts.push(new URL(r.url()).pathname)
  })

  await page.goto('/#/')
  await expect(page.getByTestId('class-list')).toBeVisible()
  await expect(page.getByTestId('class-paladin')).toContainText('Paladin')
  await page.waitForTimeout(500)

  const classChunks = scripts.filter((p) => /\/(paladin|priest|druid|mage|rogue|shaman|warlock|warrior|hunter)-[^/]+\.js$/.test(p))
  expect(classChunks, `class chunks fetched: ${classChunks.join(', ')}`).toHaveLength(0)
  expect(scripts.filter((p) => p.includes('ReviewPage'))).toHaveLength(0)
  expect(scripts).toHaveLength(1) // the entry chunk only
})

test('the class route still loads exactly one class chunk, and review stays split', async ({ page }) => {
  const scripts: string[] = []
  page.on('request', (r) => {
    if (r.resourceType() === 'script') scripts.push(new URL(r.url()).pathname)
  })
  await page.goto('/#/paladin')
  await expect(page.locator('[data-talent]').first()).toBeVisible()
  await page.waitForTimeout(300)
  expect(scripts.filter((p) => /paladin-[^/]+\.js$/.test(p))).toHaveLength(1)
  expect(scripts.filter((p) => p.includes('ReviewPage'))).toHaveLength(0)

  await page.goto('/#/review/paladin')
  await expect(page.getByTestId('review-stats')).toBeVisible()
  expect(scripts.filter((p) => p.includes('ReviewPage'))).toHaveLength(1)
})

test('robots.txt and sitemap.xml are served, and index.html carries OG tags', async ({ page, baseURL }) => {
  const robots = await page.request.get(`${baseURL}/robots.txt`)
  expect(robots.status()).toBe(200)
  expect(await robots.text()).toContain('Sitemap:')

  const sitemap = await page.request.get(`${baseURL}/sitemap.xml`)
  expect(sitemap.status()).toBe(200)
  expect(await sitemap.text()).toContain('<urlset')

  await page.goto('/#/')
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute('content', /Talent Calculator/)
  await expect(page.locator('meta[property="og:description"]')).toHaveAttribute('content', /.{40,}/)
  await expect(page.locator('meta[name="twitter:card"]')).toHaveCount(1)
  await expect(page.locator('link[rel="canonical"]')).toHaveCount(1)
})

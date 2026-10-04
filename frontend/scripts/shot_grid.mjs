import { chromium } from 'playwright'

const BASE = process.env.BASE ?? 'http://localhost:5173'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
await page.goto(BASE, { waitUntil: 'networkidle' })
const audits = await page.evaluate(() =>
  fetch('/api/v1/audits').then((r) => r.json()),
)
await page.goto(`${BASE}/audits/${audits[0].id}`, { waitUntil: 'networkidle' })
await page.getByRole('button', { name: /transactions/i }).first().click()
await page.waitForTimeout(1200)
// exercise the search filter for the second shot
await page.screenshot({ path: 'scripts/shots/07-grid-top.png' })
await page.getByPlaceholder(/search narration/i).fill('UPI')
await page.waitForTimeout(600)
await page.screenshot({ path: 'scripts/shots/08-grid-filtered.png' })
await browser.close()
console.log('done')

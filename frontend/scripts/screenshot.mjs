// Headless smoke check: renders key screens and fails on any console/page error.
import { chromium } from 'playwright'

const BASE = process.env.BASE ?? 'http://localhost:5173'
const errors = []

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
page.on('console', (m) => {
  if (m.type() === 'error') errors.push('[console] ' + m.text())
})
page.on('pageerror', (e) => errors.push('[pageerror] ' + (e?.message ?? e)))

// 1) Dashboard
await page.goto(BASE, { waitUntil: 'networkidle' })
await page.waitForTimeout(500)
await page.screenshot({ path: 'scripts/shots/01-dashboard.png' })
console.log('captured dashboard')

// 2) New-audit dialog
await page
  .getByRole('button', { name: /new audit/i })
  .first()
  .click()
await page.waitForTimeout(400)
await page.screenshot({ path: 'scripts/shots/02-new-audit.png' })
console.log('captured new-audit dialog')
await page.keyboard.press('Escape')
await page.waitForTimeout(200)

// 3) Audit detail (first audit from the API)
const audits = await page.evaluate(async () => {
  const r = await fetch('/api/v1/audits')
  return r.json()
})
if (Array.isArray(audits) && audits.length) {
  await page.goto(`${BASE}/audits/${audits[0].id}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(400)
  await page.screenshot({ path: 'scripts/shots/03-audit-detail.png' })
  console.log('captured audit detail for', audits[0].id)
} else {
  console.log('no audits found to screenshot detail')
}

await browser.close()

console.log(`\nCONSOLE/PAGE ERRORS: ${errors.length}`)
for (const e of errors) console.log(' -', e)
process.exit(errors.length ? 1 : 0)

import { chromium } from 'playwright'

const BASE = process.env.BASE ?? 'http://localhost:5173'
const errors = []
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
page.on('console', (m) => {
  if (m.type() === 'error') errors.push('[console] ' + m.text())
})
page.on('pageerror', (e) => errors.push('[pageerror] ' + (e?.message ?? e)))

await page.goto(BASE, { waitUntil: 'networkidle' })
const audits = await page.evaluate(() =>
  fetch('/api/v1/audits').then((r) => r.json()),
)
const id = audits[0].id

await page.goto(`${BASE}/audits/${id}`, { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)
await page.screenshot({ path: 'scripts/shots/05-doc-ready.png' })

await page.getByRole('button', { name: /transactions/i }).first().click()
await page.waitForTimeout(1500)
await page.screenshot({ path: 'scripts/shots/06-transactions.png', fullPage: true })

const txns = await page.evaluate(
  (aid) => fetch(`/api/v1/audits/${aid}/transactions`).then((r) => r.json()),
  id,
)
console.log('transactions:', txns.length)
await browser.close()
console.log('errors:', errors.length)
for (const e of errors) console.log(' -', e)
process.exit(errors.length ? 1 : 0)

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
await page.getByRole('button', { name: /report/i }).first().click()
await page.waitForTimeout(600)
await page.getByRole('button', { name: /generate report/i }).click()
await page.waitForSelector('text=Money in', { timeout: 30000 })
await page.waitForTimeout(800)
await page.screenshot({ path: 'scripts/shots/09-report.png', fullPage: true })

const gen = await page.evaluate(
  (aid) =>
    fetch(`/api/v1/audits/${aid}/generate`, { method: 'POST' }).then((r) =>
      r.json(),
    ),
  id,
)
console.log('net:', gen.reconciliation.net, 'txns:', gen.reconciliation.txn_count)
console.log('accounts:', gen.reconciliation.accounts.length)
await browser.close()
console.log('errors:', errors.length)
for (const e of errors) console.log(' -', e)
process.exit(errors.length ? 1 : 0)

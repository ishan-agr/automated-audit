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
const a = audits.find((x) => x.subject_name === 'UPI Export Test') ?? audits[0]

await page.goto(`${BASE}/audits/${a.id}`, { waitUntil: 'networkidle' })
await page.waitForTimeout(800)
await page.screenshot({ path: 'scripts/shots/12-csv-doc.png' })

await page.getByRole('button', { name: /transactions/i }).first().click()
await page.waitForTimeout(800)
await page.screenshot({ path: 'scripts/shots/13-csv-txns.png' })

await page.getByRole('button', { name: /report/i }).first().click()
await page.waitForTimeout(600)
await page.getByRole('button', { name: /generate report/i }).click()
await page.waitForSelector('text=Money in', { timeout: 30000 })
await page.waitForTimeout(600)
await page.screenshot({ path: 'scripts/shots/14-report-export.png', fullPage: true })

// real download through the proxy
const [download] = await Promise.all([
  page.waitForEvent('download'),
  page.getByRole('button', { name: /^CSV$/ }).click(),
])
const fname = download.suggestedFilename()
await download.saveAs(`scripts/shots/${fname}`)
console.log('downloaded:', fname)

await browser.close()
console.log('errors:', errors.length)
for (const e of errors) console.log(' -', e)
process.exit(errors.length ? 1 : 0)

// End-to-end Slice 2 smoke: upload the Axis PDF via the UI, extract, structure,
// and view the transaction grid. Fails on any console/page error.
import { chromium } from 'playwright'

const BASE = process.env.BASE ?? 'http://localhost:5173'
const PDF =
  process.env.PDF ??
  'D:/automated-audit/automated-audit/AcctStatement_XXX7229_02082026.pdf'

const errors = []
const log = (...a) => console.log(...a)

async function api(page, path) {
  return page.evaluate((p) => fetch(p).then((r) => r.json()), path)
}

async function waitFor(page, fn, { timeout = 60000, label = 'condition' } = {}) {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    if (await fn()) return
    await page.waitForTimeout(1000)
  }
  throw new Error(`timeout waiting for ${label}`)
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
page.on('console', (m) => {
  if (m.type() === 'error') errors.push('[console] ' + m.text())
})
page.on('pageerror', (e) => errors.push('[pageerror] ' + (e?.message ?? e)))

// resolve the first audit
await page.goto(BASE, { waitUntil: 'networkidle' })
const audits = await api(page, '/api/v1/audits')
const auditId = audits[0].id
log('using audit', auditId)

// Documents tab
await page.goto(`${BASE}/audits/${auditId}`, { waitUntil: 'networkidle' })
await page.waitForTimeout(500)

// pick file + bank + kind, then upload
await page.setInputFiles('input[type=file]', PDF)
await page.waitForTimeout(300)
await page.locator('select').first().selectOption('AXIS')
await page.locator('select').nth(1).selectOption('BANK_STATEMENT')
await page.getByRole('button', { name: /^upload$/i }).click()
log('uploaded; waiting for extraction…')

await waitFor(
  page,
  async () => {
    const docs = await api(page, `/api/v1/audits/${auditId}/documents`)
    const d = docs[docs.length - 1]
    log('  doc status:', d?.status, d?.pages_extracted, '/', d?.pages_total)
    return d && (d.status === 'EXTRACTED' || d.status === 'READY')
  },
  { timeout: 90000, label: 'EXTRACTED' },
)
await page.waitForTimeout(2000)
await page.screenshot({ path: 'scripts/shots/04-doc-extracted.png' })
log('captured doc-extracted')

// Structure (Docling — can take a while)
const structureBtn = page.getByRole('button', { name: /^structure$/i })
if (await structureBtn.count()) {
  await structureBtn.first().click()
  log('clicked Structure; waiting for transactions (Docling)…')
  await waitFor(
    page,
    async () => {
      const txns = await api(page, `/api/v1/audits/${auditId}/transactions`)
      return Array.isArray(txns) && txns.length > 0
    },
    { timeout: 300000, label: 'transactions' },
  )
  await page.waitForTimeout(2500)
  await page.screenshot({ path: 'scripts/shots/05-doc-ready.png' })
  log('captured doc-ready')
} else {
  log('no Structure button (already structured?)')
}

// Transactions tab
await page.getByRole('button', { name: /transactions/i }).first().click()
await page.waitForTimeout(1500)
await page.screenshot({ path: 'scripts/shots/06-transactions.png', fullPage: true })

const txns = await api(page, `/api/v1/audits/${auditId}/transactions`)
log(`transactions in grid: ${txns.length}`)

await browser.close()
log(`\nCONSOLE/PAGE ERRORS: ${errors.length}`)
for (const e of errors) log(' -', e)
process.exit(errors.length ? 1 : 0)

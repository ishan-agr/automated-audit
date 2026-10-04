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

// seed a graph: DEBIT transactions -> SUM -> OUTPUT "Total spend"
const graph = {
  name: 'Monthly spend',
  nodes: [
    { id: 'g1', kind: 'TXN_GROUP', config: { selector: { direction: 'DEBIT' } }, ui: { x: 40, y: 110 } },
    { id: 'a1', kind: 'AGGREGATE', config: { fn: 'SUM' }, ui: { x: 340, y: 110 } },
    { id: 'o1', kind: 'OUTPUT', config: { label: 'Total spend', format: 'MONEY' }, ui: { x: 640, y: 110 } },
  ],
  edges: [
    { source: 'g1', target: 'a1', target_port: 'in' },
    { source: 'a1', target: 'o1', target_port: 'in' },
  ],
}
const put = await page.evaluate(
  async ([aid, g]) => {
    const r = await fetch(`/api/v1/audits/${aid}/report`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(g),
    })
    return { status: r.status, body: await r.json() }
  },
  [id, graph],
)
console.log('PUT /report:', put.status, 'nodes:', put.body.nodes?.length)

// open the Report tab — canvas should hydrate the saved graph
await page.goto(`${BASE}/audits/${id}`, { waitUntil: 'networkidle' })
await page.getByRole('button', { name: /report/i }).first().click()
await page.waitForTimeout(1200)
await page.screenshot({ path: 'scripts/shots/10-canvas.png' })
console.log('nodes rendered:', await page.locator('.react-flow__node').count())
console.log('edges rendered:', await page.locator('.react-flow__edge').count())

// generate and check the OUTPUT value
await page.getByRole('button', { name: /generate report/i }).click()
await page.waitForSelector('text=Total spend', { timeout: 30000 })
await page.waitForTimeout(800)
await page.screenshot({ path: 'scripts/shots/11-canvas-generated.png', fullPage: true })

const gen = await page.evaluate(
  (aid) =>
    fetch(`/api/v1/audits/${aid}/generate`, { method: 'POST' }).then((r) =>
      r.json(),
    ),
  id,
)
console.log('outputs:', JSON.stringify(gen.outputs))

// palette add-node check
await page.getByRole('button', { name: /^Constant$/ }).click()
await page.waitForTimeout(400)
console.log('nodes after add:', await page.locator('.react-flow__node').count())

await browser.close()
console.log('errors:', errors.length)
for (const e of errors) console.log(' -', e)
process.exit(errors.length ? 1 : 0)

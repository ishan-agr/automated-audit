import { AlertTriangle, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import type { OutputLine, Reconciliation } from '@/lib/api/types'
import { money, toNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

export function ReconciliationView({
  recon,
  outputs,
  warnings,
}: {
  recon: Reconciliation
  outputs: OutputLine[]
  warnings: string[]
}) {
  const net = toNumber(recon.net)
  return (
    <div className="flex flex-col gap-5">
      {/* headline stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <Stat label="Net">
          <span className={net >= 0 ? 'text-success' : 'text-destructive'}>
            {net >= 0 ? '+' : '−'}
            {money(Math.abs(net))}
          </span>
        </Stat>
        <Stat label="Money in">{money(recon.total_credit)}</Stat>
        <Stat label="Money out">{money(recon.total_debit)}</Stat>
        <Stat label="Transactions">{recon.txn_count}</Stat>
        <Stat label="Coverage">
          {recon.coverage_pct != null ? `${recon.coverage_pct}%` : '—'}
        </Stat>
        <Stat label="Internal transfers">
          {money(recon.internal_transfer_total)}
        </Stat>
        <Stat label="Duplicates removed">{recon.dedup_removed}</Stat>
        <Stat label="Low-confidence">{recon.flagged_low_confidence}</Stat>
      </div>

      {/* card-graph outputs */}
      {outputs.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">
            Report outputs
          </h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {outputs.map((o) => (
              <Card key={o.node_id}>
                <CardContent className="py-4">
                  <p className="text-xs text-muted-foreground">{o.label}</p>
                  <p className="mt-1 text-lg font-semibold tabular-nums">
                    {formatOutput(o)}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* per-account reconciliation */}
      {recon.accounts.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">
            Accounts
          </h3>
          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-card text-muted-foreground">
                  <tr>
                    <Th>Account</Th>
                    <Th right>Opening</Th>
                    <Th right>Closing (stated)</Th>
                    <Th right>Closing (computed)</Th>
                    <Th right>Net</Th>
                    <Th right>Txns</Th>
                    <Th>Continuity</Th>
                  </tr>
                </thead>
                <tbody>
                  {recon.accounts.map((a) => (
                    <tr
                      key={a.account || 'unknown'}
                      className="border-b border-border/60 last:border-0"
                    >
                      <Td>
                        <span className="font-mono text-xs">
                          {a.account || '—'}
                        </span>
                      </Td>
                      <Td right>{money(a.opening)}</Td>
                      <Td right>{money(a.closing_stated)}</Td>
                      <Td
                        right
                        className={cn(
                          a.closing_stated != null &&
                            toNumber(a.closing_stated) !==
                              toNumber(a.closing_computed) &&
                            'text-warning',
                        )}
                      >
                        {money(a.closing_computed)}
                      </Td>
                      <Td right>{money(a.net)}</Td>
                      <Td right>{a.txn_count}</Td>
                      <Td>
                        {a.continuity_ok ? (
                          <Badge tone="success">balanced</Badge>
                        ) : (
                          <Badge tone="warning">
                            {a.breaks.length} break
                            {a.breaks.length === 1 ? '' : 's'}
                          </Badge>
                        )}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* gaps */}
      {recon.gaps.length > 0 && (
        <Callout tone="warning" icon={<TriangleAlert className="size-4" />}>
          <p className="font-medium">Coverage gaps</p>
          <ul className="mt-1 list-inside list-disc text-sm">
            {recon.gaps.map((g, i) => (
              <li key={i}>
                {g.account || 'account'}: {g.start} → {g.end}
              </li>
            ))}
          </ul>
        </Callout>
      )}

      {/* warnings */}
      {warnings.length > 0 && (
        <Callout tone="danger" icon={<AlertTriangle className="size-4" />}>
          <p className="font-medium">Warnings</p>
          <ul className="mt-1 list-inside list-disc text-sm">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </Callout>
      )}
    </div>
  )
}

function formatOutput(o: OutputLine): string {
  if (o.value == null) return '—'
  if (o.format === 'MONEY' || o.format === 'CURRENCY') return money(o.value)
  if (o.format === 'PERCENT') return `${o.value}%`
  return String(o.value)
}

function Callout({
  tone,
  icon,
  children,
}: {
  tone: 'warning' | 'danger'
  icon: ReactNode
  children: ReactNode
}) {
  return (
    <div
      className={cn(
        'flex gap-3 rounded-lg border p-4 text-sm',
        tone === 'warning'
          ? 'border-warning/40 bg-warning/10 text-warning'
          : 'border-destructive/40 bg-destructive/10 text-destructive',
      )}
    >
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div className="text-foreground">{children}</div>
    </div>
  )
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Card>
      <CardContent className="py-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="mt-1 text-lg font-semibold tabular-nums">{children}</p>
      </CardContent>
    </Card>
  )
}

function Th({
  children,
  right,
}: {
  children: ReactNode
  right?: boolean
}) {
  return (
    <th
      className={cn(
        'px-4 py-2.5 font-medium',
        right ? 'text-right' : 'text-left',
      )}
    >
      {children}
    </th>
  )
}

function Td({
  children,
  right,
  className,
}: {
  children: ReactNode
  right?: boolean
  className?: string
}) {
  return (
    <td
      className={cn(
        'px-4 py-2.5 tabular-nums',
        right ? 'text-right' : 'text-left',
        className,
      )}
    >
      {children}
    </td>
  )
}

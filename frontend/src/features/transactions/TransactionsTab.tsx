import {
  type SortingState,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ArrowUpDown, Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { useTransactions } from '@/lib/api/hooks'
import type { Transaction } from '@/lib/api/types'
import { fmtDate, money, toNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

const col = createColumnHelper<Transaction>()

const columns = [
  col.accessor((r) => r.tran_date ?? '', {
    id: 'tran_date',
    header: 'Date',
    cell: (c) => (
      <span className="whitespace-nowrap text-muted-foreground">
        {fmtDate(c.row.original.tran_date)}
      </span>
    ),
  }),
  col.accessor('narration_raw', {
    header: 'Narration',
    enableSorting: false,
    cell: (c) => {
      const t = c.row.original
      return (
        <div className="max-w-[26rem]">
          <p className="truncate" title={t.narration_raw}>
            {t.counterparty_name || t.narration_raw || '—'}
          </p>
          {t.counterparty_name && (
            <p className="truncate text-xs text-muted-foreground" title={t.narration_raw}>
              {t.narration_raw}
            </p>
          )}
        </div>
      )
    },
  }),
  col.accessor('channel', {
    header: 'Channel',
    cell: (c) =>
      c.getValue() ? (
        <Badge tone="muted">{c.getValue()}</Badge>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  }),
  col.accessor('direction', {
    header: 'Type',
    cell: (c) => (
      <Badge tone={c.getValue() === 'CREDIT' ? 'success' : 'default'}>
        {c.getValue() === 'CREDIT' ? 'Credit' : 'Debit'}
      </Badge>
    ),
  }),
  col.accessor((r) => toNumber(r.amount), {
    id: 'amount',
    header: 'Amount',
    cell: (c) => {
      const t = c.row.original
      return (
        <span
          className={cn(
            'whitespace-nowrap font-medium tabular-nums',
            t.direction === 'CREDIT' ? 'text-success' : 'text-foreground',
          )}
        >
          {t.direction === 'CREDIT' ? '+' : '−'}
          {money(t.amount)}
        </span>
      )
    },
  }),
  col.accessor((r) => toNumber(r.balance), {
    id: 'balance',
    header: 'Balance',
    cell: (c) => (
      <span className="whitespace-nowrap tabular-nums text-muted-foreground">
        {c.row.original.balance != null ? money(c.row.original.balance) : '—'}
      </span>
    ),
  }),
  col.accessor('source_account', {
    header: 'Account',
    cell: (c) => (
      <span className="whitespace-nowrap font-mono text-xs text-muted-foreground">
        {c.getValue() || '—'}
      </span>
    ),
  }),
]

export function TransactionsTab({ auditId }: { auditId: string }) {
  const { data: txns, isLoading } = useTransactions(auditId)
  const [search, setSearch] = useState('')
  const [direction, setDirection] = useState('ALL')
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'tran_date', desc: false },
  ])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (txns ?? []).filter((t) => {
      if (direction !== 'ALL' && t.direction !== direction) return false
      if (!q) return true
      return (
        t.narration_raw.toLowerCase().includes(q) ||
        (t.counterparty_name ?? '').toLowerCase().includes(q) ||
        (t.ref_id ?? '').toLowerCase().includes(q) ||
        (t.source_account ?? '').toLowerCase().includes(q)
      )
    })
  }, [txns, search, direction])

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Loading transactions…
      </div>
    )
  }

  if (!txns || txns.length === 0) {
    return (
      <Card className="border-dashed">
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          No transactions yet. Upload a document, then run{' '}
          <span className="font-medium text-foreground">Structure</span> on it
          from the Documents tab.
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[16rem]">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-8"
            placeholder="Search narration, counterparty, ref, account…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="w-40">
          <Select
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
          >
            <option value="ALL">All types</option>
            <option value="DEBIT">Debit only</option>
            <option value="CREDIT">Credit only</option>
          </Select>
        </div>
        <span className="text-sm text-muted-foreground">
          {filtered.length} of {txns.length}
        </span>
      </div>

      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-card">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => {
                    const sortable = h.column.getCanSort()
                    const sorted = h.column.getIsSorted()
                    return (
                      <th
                        key={h.id}
                        className={cn(
                          'px-4 py-2.5 text-left font-medium text-muted-foreground',
                          sortable && 'cursor-pointer select-none',
                        )}
                        onClick={h.column.getToggleSortingHandler()}
                      >
                        <span className="inline-flex items-center gap-1">
                          {flexRender(
                            h.column.columnDef.header,
                            h.getContext(),
                          )}
                          {sortable &&
                            (sorted === 'asc' ? (
                              <ArrowUp className="size-3.5" />
                            ) : sorted === 'desc' ? (
                              <ArrowDown className="size-3.5" />
                            ) : (
                              <ArrowUpDown className="size-3.5 opacity-40" />
                            ))}
                        </span>
                      </th>
                    )
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-border/60 last:border-0 hover:bg-accent/40"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-2.5 align-top">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

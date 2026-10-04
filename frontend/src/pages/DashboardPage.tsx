import { FileWarning, Plus, ScrollText } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { StatusBadge } from '@/components/status-badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { CreateAuditDialog } from '@/features/audits/CreateAuditDialog'
import type { Audit } from '@/lib/api'
import { useAudits } from '@/lib/api/hooks'
import { fmtDate, fmtDateTime } from '@/lib/format'

export function DashboardPage() {
  const [creating, setCreating] = useState(false)
  const { data: audits, isLoading, isError, error } = useAudits()

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Audits</h1>
          <p className="text-sm text-muted-foreground">
            Each audit ingests one or more statements and produces a reconciled,
            range-aware report.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus /> New audit
        </Button>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Loading audits…
        </div>
      )}

      {isError && (
        <Card className="border-destructive/40">
          <CardContent className="flex items-center gap-3 py-6 text-sm">
            <FileWarning className="size-5 text-destructive" />
            <div>
              <p className="font-medium text-destructive">
                Couldn’t reach the backend.
              </p>
              <p className="text-muted-foreground">
                {(error as Error)?.message}. Is the API running on{' '}
                <code className="rounded bg-muted px-1">:8000</code>?
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {audits && audits.length === 0 && (
        <EmptyState onCreate={() => setCreating(true)} />
      )}

      {audits && audits.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {audits.map((a) => (
            <AuditCard key={a.id} audit={a} />
          ))}
        </div>
      )}

      <CreateAuditDialog open={creating} onOpenChange={setCreating} />
    </div>
  )
}

function AuditCard({ audit }: { audit: Audit }) {
  const range =
    audit.range_from && audit.range_to
      ? `${fmtDate(audit.range_from)} → ${fmtDate(audit.range_to)}`
      : 'No range set'
  return (
    <Link to={`/audits/${audit.id}`}>
      <Card className="h-full transition-colors hover:border-primary/50">
        <CardHeader className="flex-row items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="truncate">{audit.subject_name}</CardTitle>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              {audit.id}
            </p>
          </div>
          <StatusBadge status={audit.status} />
        </CardHeader>
        <CardContent className="flex flex-col gap-1 text-sm text-muted-foreground">
          <span>{range}</span>
          <span className="text-xs">
            Created {fmtDateTime(audit.created_at)}
          </span>
        </CardContent>
      </Card>
    </Link>
  )
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
        <span className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <ScrollText className="size-6" />
        </span>
        <div>
          <p className="font-medium">No audits yet</p>
          <p className="text-sm text-muted-foreground">
            Create your first audit to start ingesting statements.
          </p>
        </div>
        <Button onClick={onCreate}>
          <Plus /> New audit
        </Button>
      </CardContent>
    </Card>
  )
}

import { ArrowLeft, FileWarning } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { StatusBadge } from '@/components/status-badge'
import { Card, CardContent } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { DocumentsTab } from '@/features/documents/DocumentsTab'
import { ReportTab } from '@/features/report/ReportTab'
import { TransactionsTab } from '@/features/transactions/TransactionsTab'
import { useAudit } from '@/lib/api/hooks'
import { fmtDate, fmtDateTime } from '@/lib/format'

export function AuditDetailPage() {
  const { auditId } = useParams<{ auditId: string }>()
  const { data: audit, isLoading, isError, error } = useAudit(auditId)
  const [tab, setTab] = useState('documents')

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Loading audit…
      </div>
    )
  }

  if (isError || !audit) {
    return (
      <Card className="border-destructive/40">
        <CardContent className="flex items-center gap-3 py-6 text-sm">
          <FileWarning className="size-5 text-destructive" />
          <div>
            <p className="font-medium text-destructive">Audit not found</p>
            <p className="text-muted-foreground">{(error as Error)?.message}</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const range =
    audit.range_from && audit.range_to
      ? `${fmtDate(audit.range_from)} → ${fmtDate(audit.range_to)}`
      : 'No range set'

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          to="/"
          className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> All audits
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">
            {audit.subject_name}
          </h1>
          <StatusBadge status={audit.status} />
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
          <span className="font-mono text-xs">{audit.id}</span>
          <span>{range}</span>
          {audit.subject_email && <span>{audit.subject_email}</span>}
          {audit.subject_phone && <span>{audit.subject_phone}</span>}
          <span className="text-xs">
            Updated {fmtDateTime(audit.updated_at)}
          </span>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="transactions">Transactions</TabsTrigger>
          <TabsTrigger value="report">Report</TabsTrigger>
        </TabsList>

        <TabsContent value="documents" className="mt-4">
          <DocumentsTab auditId={audit.id} />
        </TabsContent>
        <TabsContent value="transactions" className="mt-4">
          <TransactionsTab auditId={audit.id} />
        </TabsContent>
        <TabsContent value="report" className="mt-4">
          <ReportTab audit={audit} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

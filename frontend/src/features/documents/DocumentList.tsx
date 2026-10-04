import { FileText, KeyRound, Sparkles } from 'lucide-react'

import { StatusBadge } from '@/components/status-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { ApiError } from '@/lib/api'
import { useStructureDocument } from '@/lib/api/hooks'
import type { AuditDocument } from '@/lib/api/types'
import { fmtDateTime } from '@/lib/format'

const KIND_LABEL: Record<string, string> = {
  BANK_STATEMENT: 'Bank statement',
  UPI_EXPORT: 'UPI export',
  UNKNOWN: 'Document',
}

export function DocumentList({
  auditId,
  docs,
  onUnlock,
}: {
  auditId: string
  docs: AuditDocument[]
  onUnlock: (doc: AuditDocument) => void
}) {
  const structure = useStructureDocument(auditId)

  return (
    <div className="flex flex-col gap-3">
      {docs.map((doc) => {
        const structuring = structure.isPending && structure.variables === doc.id
        return (
          <Card key={doc.id}>
            <CardContent className="flex flex-wrap items-center gap-4 py-4">
              <span className="flex size-9 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                <FileText className="size-4" />
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium">{doc.filename}</span>
                  {doc.bank !== 'UNKNOWN' && (
                    <Badge tone="outline">{doc.bank}</Badge>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {KIND_LABEL[doc.doc_kind] ?? doc.doc_kind} · added{' '}
                  {fmtDateTime(doc.created_at)}
                  {doc.unlocked_with_saved_credential && ' · unlocked with saved password'}
                </p>
                {doc.status === 'FAILED' && doc.error_message && (
                  <p className="mt-1 text-xs text-destructive">
                    {doc.error_message}
                  </p>
                )}
              </div>

              <div className="flex items-center gap-3">
                {doc.status === 'PROCESSING' && (
                  <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Spinner className="size-3.5" />
                    {doc.pages_total
                      ? `${doc.pages_extracted ?? 0}/${doc.pages_total} pages`
                      : 'extracting…'}
                  </span>
                )}
                {doc.status === 'READY' && doc.page_count != null && (
                  <span className="text-xs text-muted-foreground">
                    {doc.page_count} pages
                  </span>
                )}

                <StatusBadge status={doc.status} />

                {doc.status === 'LOCKED' && (
                  <Button size="sm" variant="outline" onClick={() => onUnlock(doc)}>
                    <KeyRound /> Unlock
                  </Button>
                )}

                {doc.status === 'EXTRACTED' && (
                  <Button
                    size="sm"
                    onClick={() => structure.mutate(doc.id)}
                    disabled={structuring}
                  >
                    {structuring ? <Spinner /> : <Sparkles />}
                    {structuring ? 'Structuring…' : 'Structure'}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        )
      })}

      {structure.isError && (
        <p className="text-sm text-destructive">
          {structure.error instanceof ApiError
            ? structure.error.message
            : 'Structuring failed.'}
        </p>
      )}
    </div>
  )
}

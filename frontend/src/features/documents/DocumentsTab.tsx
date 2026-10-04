import { useState } from 'react'

import { Card, CardContent } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import type { AuditDocument } from '@/lib/api/types'
import { useDocuments } from '@/lib/api/hooks'

import { DocumentList } from './DocumentList'
import { UnlockDialog } from './UnlockDialog'
import { UploadPanel } from './UploadPanel'

export function DocumentsTab({ auditId }: { auditId: string }) {
  const { data: docs, isLoading } = useDocuments(auditId)
  const [unlockDoc, setUnlockDoc] = useState<AuditDocument | null>(null)

  return (
    <div className="flex flex-col gap-4">
      <UploadPanel auditId={auditId} />

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Loading documents…
        </div>
      )}

      {docs && docs.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No documents yet. Upload a bank statement or UPI export to begin.
          </CardContent>
        </Card>
      )}

      {docs && docs.length > 0 && (
        <DocumentList auditId={auditId} docs={docs} onUnlock={setUnlockDoc} />
      )}

      <UnlockDialog
        auditId={auditId}
        doc={unlockDoc}
        onOpenChange={(o) => !o && setUnlockDoc(null)}
      />
    </div>
  )
}

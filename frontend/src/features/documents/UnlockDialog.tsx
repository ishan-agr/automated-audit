import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'
import { ApiError } from '@/lib/api'
import { useUnlockDocument } from '@/lib/api/hooks'
import type { AuditDocument } from '@/lib/api/types'

export function UnlockDialog({
  auditId,
  doc,
  onOpenChange,
}: {
  auditId: string
  doc: AuditDocument | null
  onOpenChange: (open: boolean) => void
}) {
  const unlock = useUnlockDocument(auditId)
  const [password, setPassword] = useState('')
  const [save, setSave] = useState(false)

  const close = () => {
    setPassword('')
    setSave(false)
    unlock.reset()
    onOpenChange(false)
  }

  const submit = async () => {
    if (!doc || !password) return
    await unlock.mutateAsync({
      docId: doc.id,
      input: { password, save_credential: save },
    })
    close()
  }

  return (
    <Dialog open={Boolean(doc)} onOpenChange={(o) => (o ? undefined : close())}>
      <DialogContent onClose={close}>
        <DialogHeader>
          <DialogTitle>Unlock document</DialogTitle>
          <DialogDescription>
            <span className="font-medium text-foreground">{doc?.filename}</span>{' '}
            is password-protected. Enter the statement password to extract it.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label>Password</Label>
            <Input
              autoFocus
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submit()}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <Checkbox
              checked={save}
              onChange={(e) => setSave(e.target.checked)}
            />
            Remember this password for {doc?.bank ?? 'this bank'}
          </label>

          {unlock.isError && (
            <p className="text-sm text-destructive">
              {unlock.error instanceof ApiError &&
              unlock.error.status === 422
                ? 'That password did not unlock the document.'
                : unlock.error instanceof ApiError
                  ? unlock.error.message
                  : 'Unlock failed.'}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!password || unlock.isPending}>
            {unlock.isPending && <Spinner />}
            Unlock
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

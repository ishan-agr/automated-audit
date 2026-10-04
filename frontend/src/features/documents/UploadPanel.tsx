import { FileUp, Upload, X } from 'lucide-react'
import { useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { ApiError } from '@/lib/api'
import { useUploadDocument } from '@/lib/api/hooks'
import type { Bank } from '@/lib/api/types'
import { cn } from '@/lib/utils'

const BANKS: Bank[] = ['UNKNOWN', 'AXIS', 'HDFC', 'ICICI', 'SBI', 'KOTAK']
const KINDS = [
  { value: 'UNKNOWN', label: 'Unknown' },
  { value: 'BANK_STATEMENT', label: 'Bank statement' },
  { value: 'UPI_EXPORT', label: 'UPI export' },
]

export function UploadPanel({ auditId }: { auditId: string }) {
  const upload = useUploadDocument(auditId)
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [bank, setBank] = useState<Bank>('UNKNOWN')
  const [docKind, setDocKind] = useState('UNKNOWN')
  const [password, setPassword] = useState('')
  const [saveCredential, setSaveCredential] = useState(false)
  const [dragging, setDragging] = useState(false)

  const reset = () => {
    setFile(null)
    setPassword('')
    setSaveCredential(false)
    upload.reset()
    if (inputRef.current) inputRef.current.value = ''
  }

  const submit = async () => {
    if (!file) return
    await upload.mutateAsync({
      file,
      bank,
      doc_kind: docKind,
      password: password || undefined,
      save_credential: saveCredential,
    })
    reset()
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-4 py-5">
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            const f = e.dataTransfer.files?.[0]
            if (f) setFile(f)
          }}
          onClick={() => inputRef.current?.click()}
          className={cn(
            'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-8 text-center transition-colors',
            dragging
              ? 'border-primary bg-primary/5'
              : 'border-border hover:border-primary/50',
          )}
        >
          <span className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <FileUp className="size-5" />
          </span>
          {file ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium">{file.name}</span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  reset()
                }}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Remove file"
              >
                <X className="size-4" />
              </button>
            </div>
          ) : (
            <div className="text-sm">
              <span className="font-medium text-foreground">
                Drop a statement here
              </span>{' '}
              <span className="text-muted-foreground">
                or click to browse — PDF, CSV, XLSX
              </span>
            </div>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.csv,.xls,.xlsx"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label>Bank</Label>
            <Select value={bank} onChange={(e) => setBank(e.target.value as Bank)}>
              {BANKS.map((b) => (
                <option key={b} value={b}>
                  {b === 'UNKNOWN' ? 'Unknown / other' : b}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Document type</Label>
            <Select
              value={docKind}
              onChange={(e) => setDocKind(e.target.value)}
            >
              {KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </Select>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Password (for locked PDFs)</Label>
          <Input
            type="password"
            placeholder="optional — auto-derived from name + DOB when possible"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {password && (
            <label className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
              <Checkbox
                checked={saveCredential}
                onChange={(e) => setSaveCredential(e.target.checked)}
              />
              Remember this password for {bank === 'UNKNOWN' ? 'this bank' : bank}
            </label>
          )}
        </div>

        {upload.isError && (
          <p className="text-sm text-destructive">
            {upload.error instanceof ApiError
              ? upload.error.message
              : 'Upload failed.'}
          </p>
        )}

        <div className="flex justify-end">
          <Button onClick={submit} disabled={!file || upload.isPending}>
            {upload.isPending ? <Spinner /> : <Upload />}
            Upload
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

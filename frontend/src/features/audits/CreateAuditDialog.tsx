import { zodResolver } from '@hookform/resolvers/zod'
import type { ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
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
import { useCreateAudit } from '@/lib/api/hooks'

const schema = z.object({
  subject_name: z.string().trim().min(1, 'Name is required').max(255),
  subject_email: z.string().trim().optional(),
  subject_phone: z.string().trim().optional(),
  subject_dob: z.string().trim().optional(),
})

type FormValues = z.infer<typeof schema>

export function CreateAuditDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const createAudit = useCreateAudit()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      subject_name: '',
      subject_email: '',
      subject_phone: '',
      subject_dob: '',
    },
  })

  const close = () => {
    reset()
    createAudit.reset()
    onOpenChange(false)
  }

  const onSubmit = handleSubmit(async (values) => {
    const audit = await createAudit.mutateAsync({
      subject_name: values.subject_name,
      subject_email: values.subject_email || null,
      subject_phone: values.subject_phone || null,
      subject_dob: values.subject_dob || null,
    })
    close()
    navigate(`/audits/${audit.id}`)
  })

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? onOpenChange(o) : close())}>
      <DialogContent onClose={close}>
        <DialogHeader>
          <DialogTitle>New audit</DialogTitle>
          <DialogDescription>
            Only a name is required. Date of birth helps derive bank statement
            passwords automatically.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <Field
            label="Subject name"
            required
            error={errors.subject_name?.message}
          >
            <Input
              autoFocus
              placeholder="e.g. Priya Sharma"
              {...register('subject_name')}
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Email">
              <Input
                type="email"
                placeholder="optional"
                {...register('subject_email')}
              />
            </Field>
            <Field label="Phone">
              <Input placeholder="optional" {...register('subject_phone')} />
            </Field>
          </div>

          <Field label="Date of birth">
            <Input type="date" {...register('subject_dob')} />
          </Field>

          {createAudit.isError && (
            <p className="text-sm text-destructive">
              {createAudit.error instanceof ApiError
                ? createAudit.error.message
                : 'Failed to create audit.'}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={close}>
              Cancel
            </Button>
            <Button type="submit" disabled={createAudit.isPending}>
              {createAudit.isPending && <Spinner />}
              Create audit
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function Field({
  label,
  required,
  error,
  children,
}: {
  label: string
  required?: boolean
  error?: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>
        {label}
        {required && <span className="ml-0.5 text-destructive">*</span>}
      </Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}

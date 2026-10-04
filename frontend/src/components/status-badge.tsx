import { Badge, type BadgeProps } from '@/components/ui/badge'

type Tone = NonNullable<BadgeProps['tone']>

const TONES: Record<string, Tone> = {
  // audit
  DRAFT: 'muted',
  EXTRACTING: 'info',
  EXTRACTED: 'info',
  GENERATED: 'success',
  // document
  PENDING: 'muted',
  LOCKED: 'warning',
  PROCESSING: 'info',
  PARSED: 'info',
  READY: 'success',
  // shared
  FAILED: 'danger',
  // password
  NOT_REQUIRED: 'muted',
  UNLOCKED: 'success',
}

export function StatusBadge({ status }: { status: string }) {
  const tone = TONES[status] ?? 'outline'
  return <Badge tone={tone}>{status.replace(/_/g, ' ').toLowerCase()}</Badge>
}

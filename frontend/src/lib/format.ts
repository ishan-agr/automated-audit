import { format, parseISO } from 'date-fns'

/** Coerce a Decimal-as-string (or number/null) into a number for display math. */
export function toNumber(v: string | number | null | undefined): number {
  if (v == null || v === '') return 0
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : 0
}

const INR = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
})

/** Format a money value (string|number) as INR. */
export function money(v: string | number | null | undefined): string {
  if (v == null || v === '') return '—'
  return INR.format(toNumber(v))
}

/** Format an ISO date (YYYY-MM-DD or full ISO) as e.g. "02 Aug 2026". */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return format(parseISO(iso), 'dd MMM yyyy')
  } catch {
    return iso
  }
}

/** Format an ISO datetime as "02 Aug 2026, 14:25". */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return format(parseISO(iso), 'dd MMM yyyy, HH:mm')
  } catch {
    return iso
  }
}

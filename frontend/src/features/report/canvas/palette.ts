import type { NodeKind } from '@/lib/api/types'

export interface PortDef {
  id: string
  label: string
}

export interface KindMeta {
  label: string
  hint: string
  accent: string // hsl/oklch color for the node header dot + handles
  inputs: PortDef[]
  hasOutput: boolean
  defaultConfig: Record<string, unknown>
}

export const KIND_META: Record<NodeKind, KindMeta> = {
  TXN_GROUP: {
    label: 'Transactions',
    hint: 'Filter the transaction pool',
    accent: 'oklch(0.62 0.19 274)',
    inputs: [],
    hasOutput: true,
    defaultConfig: { selector: {} },
  },
  AGGREGATE: {
    label: 'Aggregate',
    hint: 'Reduce a group to a number',
    accent: 'oklch(0.7 0.16 155)',
    inputs: [{ id: 'in', label: 'transactions' }],
    hasOutput: true,
    defaultConfig: { fn: 'SUM' },
  },
  OPERATION: {
    label: 'Operation',
    hint: 'Math on two numbers',
    accent: 'oklch(0.78 0.15 80)',
    inputs: [
      { id: 'a', label: 'a' },
      { id: 'b', label: 'b' },
    ],
    hasOutput: true,
    defaultConfig: { op: 'ADD' },
  },
  CONSTANT: {
    label: 'Constant',
    hint: 'A fixed number',
    accent: 'oklch(0.68 0.01 285)',
    inputs: [],
    hasOutput: true,
    defaultConfig: { value: 0 },
  },
  RECONCILE: {
    label: 'Reconcile field',
    hint: 'A value from reconciliation',
    accent: 'oklch(0.7 0.13 235)',
    inputs: [],
    hasOutput: true,
    defaultConfig: { field: 'net' },
  },
  OUTPUT: {
    label: 'Output',
    hint: 'A line in the report',
    accent: 'oklch(0.72 0.18 15)',
    inputs: [{ id: 'in', label: 'value' }],
    hasOutput: false,
    defaultConfig: { label: 'Result', format: 'NUMBER' },
  },
}

export const KIND_ORDER: NodeKind[] = [
  'TXN_GROUP',
  'AGGREGATE',
  'OPERATION',
  'CONSTANT',
  'RECONCILE',
  'OUTPUT',
]

export const AGG_FNS = ['SUM', 'COUNT', 'AVG', 'MIN', 'MAX', 'NET']
export const OPS = ['ADD', 'SUB', 'MUL', 'DIV', 'PCT']
export const RECON_FIELDS = [
  'net',
  'total_debit',
  'total_credit',
  'txn_count',
  'internal_transfer_total',
  'coverage_pct',
  'dedup_removed',
]
export const SELECTOR_KEYS = [
  'NAME',
  'CHANNEL',
  'ACCOUNT_NO',
  'UPI_ID',
  'REF_ID',
  'LABEL',
]
export const SELECTOR_OPS = ['EQ', 'CONTAINS', 'IN', 'REGEX']
export const OUTPUT_FORMATS = ['NUMBER', 'MONEY', 'PERCENT']

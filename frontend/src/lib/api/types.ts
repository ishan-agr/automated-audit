/*
  TypeScript mirrors of the backend Pydantic schemas (app schemas.py / routes.py).
  Money fields are serialized by Pydantic v2 as strings to preserve Decimal
  precision — keep them as strings and coerce only at display time (see money()).
*/

export type Bank = 'AXIS' | 'HDFC' | 'ICICI' | 'SBI' | 'KOTAK' | 'UNKNOWN'

export type AuditStatus =
  | 'DRAFT'
  | 'EXTRACTING'
  | 'EXTRACTED'
  | 'GENERATED'
  | 'FAILED'

export type DocStatus =
  | 'PENDING'
  | 'LOCKED'
  | 'PROCESSING'
  | 'EXTRACTED'
  | 'PARSED'
  | 'READY'
  | 'FAILED'

export type PasswordStatus = 'NOT_REQUIRED' | 'LOCKED' | 'UNLOCKED'

export type Direction = 'DEBIT' | 'CREDIT'

export type ParseSource = 'REGEX' | 'SLM' | 'MANUAL'

// ---- audits ---------------------------------------------------------------

export interface Audit {
  id: string
  subject_name: string
  subject_email: string | null
  subject_phone: string | null
  status: AuditStatus
  range_from: string | null // ISO date (YYYY-MM-DD)
  range_to: string | null
  created_at: string
  updated_at: string
}

export interface AuditCreate {
  subject_name: string
  subject_email?: string | null
  subject_phone?: string | null
  subject_dob?: string | null // ISO date; used for password derivation
}

export interface RangeUpdate {
  range_from: string
  range_to: string
}

// ---- documents ------------------------------------------------------------

export interface AuditDocument {
  id: string
  audit_id: string
  file_id: string
  filename: string
  doc_kind: string
  bank: string
  status: DocStatus
  is_encrypted: boolean
  password_status: PasswordStatus
  unlocked_with_saved_credential: boolean
  page_count: number | null
  pages_extracted: number | null
  pages_total: number | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface UploadDocumentInput {
  file: File
  bank?: Bank
  doc_kind?: string
  password?: string
  save_credential?: boolean
}

export interface UnlockInput {
  password: string
  save_credential?: boolean
  label?: string
}

// ---- transactions ---------------------------------------------------------

export interface Transaction {
  id: string
  document_id: string
  page_num: number | null
  tran_date: string | null
  narration_raw: string
  direction: Direction
  amount: string
  balance: string | null
  channel: string | null
  txn_subtype: string | null
  ref_id: string | null
  counterparty_name: string | null
  source_account: string | null
  identifiers: Record<string, string>
  user_label: string | null
  confidence: number
  parse_source: ParseSource
  is_internal_transfer: boolean
  created_at: string
}

// ---- report graph ---------------------------------------------------------

export type NodeKind =
  | 'TXN_GROUP'
  | 'AGGREGATE'
  | 'OPERATION'
  | 'CONSTANT'
  | 'RECONCILE'
  | 'OUTPUT'

export interface GraphNode {
  id: string
  kind: NodeKind
  config: Record<string, unknown>
  ui: Record<string, unknown>
}

export interface GraphEdge {
  source: string
  target: string
  target_port: string
}

export interface ReportGraph {
  report_id: string | null
  name: string | null
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// ---- generate / reconciliation --------------------------------------------

export interface ContinuityBreak {
  at_date: string | null
  expected: string | null
  found: string | null
}

export interface AccountRecon {
  account: string
  opening: string | null
  closing_stated: string | null
  closing_computed: string | null
  sum_debit: string | null
  sum_credit: string | null
  net: string | null
  txn_count: number
  continuity_ok: boolean
  breaks: ContinuityBreak[]
}

export interface Gap {
  account: string
  start: string
  end: string
}

export interface Reconciliation {
  total_debit: string | null
  total_credit: string | null
  net: string | null
  txn_count: number
  dedup_removed: number
  internal_transfer_total: string | null
  coverage_pct: number | null
  flagged_low_confidence: number
  gaps: Gap[]
  accounts: AccountRecon[]
}

export interface OutputLine {
  node_id: string
  label: string
  format: string
  value: string | number | null
}

export interface GenerateResult {
  audit_id: string
  range: { from: string | null; to: string | null }
  reconciliation: Reconciliation
  outputs: OutputLine[]
  warnings: string[]
}

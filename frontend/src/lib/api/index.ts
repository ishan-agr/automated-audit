import { API_BASE, request } from './http'
import type {
  Audit,
  AuditCreate,
  AuditDocument,
  GenerateResult,
  RangeUpdate,
  ReportGraph,
  Transaction,
  UnlockInput,
  UploadDocumentInput,
} from './types'

export * from './types'
export { ApiError } from './http'

// ---- audits ---------------------------------------------------------------

export const audits = {
  list: (params?: { limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.limit != null) q.set('limit', String(params.limit))
    if (params?.offset != null) q.set('offset', String(params.offset))
    const qs = q.toString()
    return request<Audit[]>(`/audits${qs ? `?${qs}` : ''}`)
  },
  get: (id: string) => request<Audit>(`/audits/${id}`),
  create: (payload: AuditCreate) =>
    request<Audit>('/audits', { method: 'POST', body: payload }),
  updateRange: (id: string, payload: RangeUpdate) =>
    request<Audit>(`/audits/${id}/range`, { method: 'PATCH', body: payload }),
}

// ---- documents ------------------------------------------------------------

export const documents = {
  list: (auditId: string) =>
    request<AuditDocument[]>(`/audits/${auditId}/documents`),
  get: (auditId: string, docId: string) =>
    request<AuditDocument>(`/audits/${auditId}/documents/${docId}`),
  upload: (auditId: string, input: UploadDocumentInput) => {
    const fd = new FormData()
    fd.set('file', input.file)
    if (input.bank) fd.set('bank', input.bank)
    if (input.doc_kind) fd.set('doc_kind', input.doc_kind)
    if (input.password) fd.set('password', input.password)
    fd.set('save_credential', String(input.save_credential ?? false))
    return request<AuditDocument>(`/audits/${auditId}/documents`, {
      method: 'POST',
      body: fd,
      form: true,
    })
  },
  unlock: (auditId: string, docId: string, input: UnlockInput) =>
    request<AuditDocument>(`/audits/${auditId}/documents/${docId}/unlock`, {
      method: 'POST',
      body: input,
    }),
}

// ---- transactions ---------------------------------------------------------

export const transactions = {
  list: (auditId: string) =>
    request<Transaction[]>(`/audits/${auditId}/transactions`),
  structure: (auditId: string, docId: string) =>
    request<unknown>(`/audits/${auditId}/documents/${docId}/structure`, {
      method: 'POST',
    }),
}

// ---- report + generate -----------------------------------------------------

export const report = {
  get: (auditId: string) => request<ReportGraph>(`/audits/${auditId}/report`),
  save: (auditId: string, graph: Omit<ReportGraph, 'report_id'>) =>
    request<ReportGraph>(`/audits/${auditId}/report`, {
      method: 'PUT',
      body: graph,
    }),
  generate: (auditId: string, range?: { range_from?: string; range_to?: string }) =>
    request<GenerateResult>(`/audits/${auditId}/generate`, {
      method: 'POST',
      body: range ?? {},
    }),
  // Direct download URL (Content-Disposition triggers the save). `format`:
  // 'json' = reconciliation + outputs, 'csv' = flat transactions.
  exportHref: (
    auditId: string,
    format: 'json' | 'csv',
    range?: { range_from?: string; range_to?: string },
  ) => {
    const q = new URLSearchParams({ format })
    if (range?.range_from && range?.range_to) {
      q.set('range_from', range.range_from)
      q.set('range_to', range.range_to)
    }
    return `${API_BASE}/audits/${auditId}/export?${q.toString()}`
  },
}

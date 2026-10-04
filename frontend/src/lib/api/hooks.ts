import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { audits, documents, report, transactions } from './index'
import type {
  AuditCreate,
  RangeUpdate,
  ReportGraph,
  UnlockInput,
  UploadDocumentInput,
} from './types'

export const qk = {
  audits: ['audits'] as const,
  audit: (id: string) => ['audits', id] as const,
  documents: (auditId: string) => ['audits', auditId, 'documents'] as const,
  transactions: (auditId: string) =>
    ['audits', auditId, 'transactions'] as const,
  report: (auditId: string) => ['audits', auditId, 'report'] as const,
  generate: (auditId: string) => ['audits', auditId, 'generate'] as const,
}

// ---- audits ---------------------------------------------------------------

export function useAudits() {
  return useQuery({ queryKey: qk.audits, queryFn: () => audits.list() })
}

export function useAudit(id: string | undefined) {
  return useQuery({
    queryKey: qk.audit(id ?? ''),
    queryFn: () => audits.get(id as string),
    enabled: Boolean(id),
  })
}

export function useCreateAudit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: AuditCreate) => audits.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.audits }),
  })
}

export function useUpdateRange(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: RangeUpdate) => audits.updateRange(id, payload),
    onSuccess: (audit) => {
      qc.setQueryData(qk.audit(id), audit)
      qc.invalidateQueries({ queryKey: qk.audits })
    },
  })
}

// ---- documents ------------------------------------------------------------

export function useDocuments(auditId: string) {
  return useQuery({
    queryKey: qk.documents(auditId),
    queryFn: () => documents.list(auditId),
    // Poll while any document is still extracting.
    refetchInterval: (query) => {
      const docs = query.state.data
      const busy = docs?.some((d) => d.status === 'PROCESSING')
      return busy ? 1500 : false
    },
  })
}

export function useUploadDocument(auditId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: UploadDocumentInput) =>
      documents.upload(auditId, input),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: qk.documents(auditId) }),
  })
}

export function useUnlockDocument(auditId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ docId, input }: { docId: string; input: UnlockInput }) =>
      documents.unlock(auditId, docId, input),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: qk.documents(auditId) }),
  })
}

export function useStructureDocument(auditId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (docId: string) => transactions.structure(auditId, docId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.documents(auditId) })
      qc.invalidateQueries({ queryKey: qk.transactions(auditId) })
    },
  })
}

// ---- transactions ---------------------------------------------------------

export function useTransactions(auditId: string) {
  return useQuery({
    queryKey: qk.transactions(auditId),
    queryFn: () => transactions.list(auditId),
  })
}

// ---- report + generate -----------------------------------------------------

export function useReport(auditId: string) {
  return useQuery({
    queryKey: qk.report(auditId),
    queryFn: () => report.get(auditId),
  })
}

export function useSaveReport(auditId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (graph: Omit<ReportGraph, 'report_id'>) =>
      report.save(auditId, graph),
    onSuccess: (data) => qc.setQueryData(qk.report(auditId), data),
  })
}

export function useGenerate(auditId: string) {
  return useMutation({
    mutationFn: (range?: { range_from?: string; range_to?: string }) =>
      report.generate(auditId, range),
  })
}

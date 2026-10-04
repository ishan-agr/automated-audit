import { ReactFlowProvider } from '@xyflow/react'

import type { Audit } from '@/lib/api/types'

import { ReportCanvas } from './canvas/ReportCanvas'

export function ReportTab({ audit }: { audit: Audit }) {
  return (
    <ReactFlowProvider>
      <ReportCanvas audit={audit} />
    </ReactFlowProvider>
  )
}

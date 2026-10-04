import { createContext, useContext } from 'react'

export interface CanvasApi {
  updateConfig: (nodeId: string, patch: Record<string, unknown>) => void
  updateSelector: (nodeId: string, patch: Record<string, unknown>) => void
  removeNode: (nodeId: string) => void
}

export const CanvasContext = createContext<CanvasApi | null>(null)

export function useCanvas(): CanvasApi {
  const ctx = useContext(CanvasContext)
  if (!ctx) throw new Error('useCanvas must be used inside CanvasContext')
  return ctx
}

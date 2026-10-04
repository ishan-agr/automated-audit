import {
  Background,
  Controls,
  type Connection,
  type Edge,
  type Node,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Download, Play, Plus, Save } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'
import { ApiError, report as reportApi } from '@/lib/api'
import {
  useGenerate,
  useReport,
  useSaveReport,
  useUpdateRange,
} from '@/lib/api/hooks'
import type { Audit, NodeKind, ReportGraph } from '@/lib/api/types'

import { ReconciliationView } from '../ReconciliationView'
import { CanvasContext } from './CanvasContext'
import { type CardData, CardNode } from './CardNode'
import { KIND_META, KIND_ORDER } from './palette'

const nodeTypes = { card: CardNode }

type FlowNode = Node<CardData>

function graphToFlow(graph: ReportGraph): { nodes: FlowNode[]; edges: Edge[] } {
  const nodes: FlowNode[] = graph.nodes.map((n, i) => {
    const ui = (n.ui ?? {}) as { x?: number; y?: number }
    return {
      id: n.id,
      type: 'card',
      position: { x: ui.x ?? 80 + (i % 4) * 270, y: ui.y ?? 60 + Math.floor(i / 4) * 210 },
      data: { kind: n.kind, config: n.config ?? {} },
    }
  })
  const edges: Edge[] = graph.edges.map((e, i) => ({
    id: `e${i}-${e.source}-${e.target}-${e.target_port}`,
    source: e.source,
    target: e.target,
    targetHandle: e.target_port,
  }))
  return { nodes, edges }
}

function flowToGraph(nodes: FlowNode[], edges: Edge[]): Omit<ReportGraph, 'report_id'> {
  return {
    name: null,
    nodes: nodes.map((n) => ({
      id: n.id,
      kind: n.data.kind,
      config: n.data.config,
      ui: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
    })),
    edges: edges.map((e) => ({
      source: e.source,
      target: e.target,
      target_port: e.targetHandle ?? 'in',
    })),
  }
}

export function ReportCanvas({ audit }: { audit: Audit }) {
  const report = useReport(audit.id)
  const saveReport = useSaveReport(audit.id)
  const gen = useGenerate(audit.id)
  const updateRange = useUpdateRange(audit.id)

  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [loaded, setLoaded] = useState(false)

  const [from, setFrom] = useState(audit.range_from ?? '')
  const [to, setTo] = useState(audit.range_to ?? '')
  const [error, setError] = useState<string | null>(null)

  // hydrate the canvas from the saved graph once
  useEffect(() => {
    if (report.data && !loaded) {
      const { nodes: n, edges: e } = graphToFlow(report.data)
      setNodes(n)
      setEdges(e)
      setLoaded(true)
    }
  }, [report.data, loaded, setNodes, setEdges])

  const updateConfig = useCallback(
    (id: string, patch: Record<string, unknown>) =>
      setNodes((ns) =>
        ns.map((n) =>
          n.id === id
            ? { ...n, data: { ...n.data, config: { ...n.data.config, ...patch } } }
            : n,
        ),
      ),
    [setNodes],
  )

  const updateSelector = useCallback(
    (id: string, patch: Record<string, unknown>) =>
      setNodes((ns) =>
        ns.map((n) => {
          if (n.id !== id) return n
          const selector = {
            ...((n.data.config.selector as Record<string, unknown>) ?? {}),
            ...patch,
          }
          return { ...n, data: { ...n.data, config: { ...n.data.config, selector } } }
        }),
      ),
    [setNodes],
  )

  const removeNode = useCallback(
    (id: string) => {
      setNodes((ns) => ns.filter((n) => n.id !== id))
      setEdges((es) => es.filter((e) => e.source !== id && e.target !== id))
    },
    [setNodes, setEdges],
  )

  const addNode = useCallback(
    (kind: NodeKind) => {
      const id = `${kind}-${crypto.randomUUID().slice(0, 8)}`
      setNodes((ns) => [
        ...ns,
        {
          id,
          type: 'card',
          position: { x: 120 + (ns.length % 4) * 60, y: 80 + (ns.length % 6) * 40 },
          data: {
            kind,
            config: structuredClone(KIND_META[kind].defaultConfig),
          },
        },
      ])
    },
    [setNodes],
  )

  const onConnect = useCallback(
    (c: Connection) => setEdges((es) => addEdge(c, es)),
    [setEdges],
  )

  const isValidConnection = useCallback(
    (c: Connection | Edge) => c.source !== c.target,
    [],
  )

  const save = async () => {
    setError(null)
    try {
      await saveReport.mutateAsync(flowToGraph(nodes, edges))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Save failed')
    }
  }

  const generate = async () => {
    setError(null)
    if ((from && !to) || (!from && to)) {
      setError('Set both dates, or leave both empty for all transactions.')
      return
    }
    if (from && to && to < from) {
      setError('End date must be on or after the start date.')
      return
    }
    try {
      await saveReport.mutateAsync(flowToGraph(nodes, edges))
      if (from && to) await updateRange.mutateAsync({ range_from: from, range_to: to })
      await gen.mutateAsync(from && to ? { range_from: from, range_to: to } : undefined)
    } catch (e) {
      setError(e instanceof ApiError ? `invalid graph: ${e.message}` : 'Generate failed')
    }
  }

  const download = (format: 'json' | 'csv') => {
    const range = from && to ? { range_from: from, range_to: to } : undefined
    const href = reportApi.exportHref(audit.id, format, range)
    const a = document.createElement('a')
    a.href = href
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    a.remove()
  }

  const busy = gen.isPending || saveReport.isPending || updateRange.isPending

  return (
    <CanvasContext.Provider value={{ updateConfig, updateSelector, removeNode }}>
      <div className="flex flex-col gap-4">
        {/* palette */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">Add card:</span>
          {KIND_ORDER.map((kind) => (
            <Button
              key={kind}
              size="sm"
              variant="outline"
              onClick={() => addNode(kind)}
              title={KIND_META[kind].hint}
            >
              <Plus />
              {KIND_META[kind].label}
            </Button>
          ))}
          <div className="ml-auto">
            <Button size="sm" variant="secondary" onClick={save} disabled={busy}>
              {saveReport.isPending ? <Spinner /> : <Save />}
              Save
            </Button>
          </div>
        </div>

        {/* canvas */}
        <Card className="overflow-hidden p-0">
          <div className="h-[460px] w-full">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              isValidConnection={isValidConnection}
              nodeTypes={nodeTypes}
              fitView
              proOptions={{ hideAttribution: true }}
              defaultEdgeOptions={{ animated: true }}
            >
              <Background gap={16} color="oklch(0.27 0.008 285)" />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
        </Card>

        {/* range + generate */}
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1.5">
            <Label>From</Label>
            <Input
              type="date"
              className="w-40"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>To</Label>
            <Input
              type="date"
              className="w-40"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </div>
          <Button onClick={generate} disabled={busy}>
            {busy ? <Spinner /> : <Play />}
            Generate report
          </Button>
          <div className="ml-auto flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => download('csv')}>
              <Download /> CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => download('json')}>
              <Download /> JSON
            </Button>
          </div>
          {error && <p className="w-full text-sm text-destructive">{error}</p>}
        </div>

        {/* result */}
        {gen.data ? (
          <ReconciliationView
            recon={gen.data.reconciliation}
            outputs={gen.data.outputs}
            warnings={gen.data.warnings}
          />
        ) : (
          <Card className="border-dashed">
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              Wire up cards (or just hit Generate) to see the reconciled report.
            </CardContent>
          </Card>
        )}
      </div>
    </CanvasContext.Provider>
  )
}

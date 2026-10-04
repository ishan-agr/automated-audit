import { Handle, type NodeProps, Position } from '@xyflow/react'
import { X } from 'lucide-react'

import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import type { NodeKind } from '@/lib/api/types'
import { cn } from '@/lib/utils'

import { useCanvas } from './CanvasContext'
import {
  AGG_FNS,
  KIND_META,
  OPS,
  OUTPUT_FORMATS,
  RECON_FIELDS,
  SELECTOR_KEYS,
  SELECTOR_OPS,
} from './palette'

export interface CardData extends Record<string, unknown> {
  kind: NodeKind
  config: Record<string, unknown>
}

const fieldCls =
  'nodrag h-7 w-full rounded-md border border-input bg-background px-2 text-xs'

export function CardNode({ id, data, selected }: NodeProps) {
  const { kind, config } = data as CardData
  const meta = KIND_META[kind]
  const { updateConfig, updateSelector, removeNode } = useCanvas()

  return (
    <div
      className={cn(
        'w-60 rounded-xl border bg-card shadow-md transition-colors',
        selected ? 'border-primary' : 'border-border',
      )}
    >
      {/* input handles */}
      {meta.inputs.map((port, i) => (
        <Handle
          key={port.id}
          type="target"
          position={Position.Left}
          id={port.id}
          style={{
            top: 44 + i * 22,
            width: 10,
            height: 10,
            background: meta.accent,
          }}
        />
      ))}
      {meta.hasOutput && (
        <Handle
          type="source"
          position={Position.Right}
          style={{ top: 44, width: 10, height: 10, background: meta.accent }}
        />
      )}

      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <span
            className="size-2.5 rounded-full"
            style={{ background: meta.accent }}
          />
          <span className="text-xs font-semibold">{meta.label}</span>
        </div>
        <button
          className="nodrag text-muted-foreground hover:text-destructive"
          onClick={() => removeNode(id)}
          aria-label="Delete node"
        >
          <X className="size-3.5" />
        </button>
      </div>

      <div className="flex flex-col gap-2 p-3">
        {meta.inputs.length > 0 && (
          <div className="flex flex-col gap-0.5 text-[10px] text-muted-foreground">
            {meta.inputs.map((p) => (
              <span key={p.id}>◦ {p.label}</span>
            ))}
          </div>
        )}

        {kind === 'TXN_GROUP' && (
          <TxnGroupEditor
            config={config}
            onSelector={(patch) => updateSelector(id, patch)}
          />
        )}

        {kind === 'AGGREGATE' && (
          <LabeledSelect
            label="Function"
            value={String(config.fn ?? 'SUM')}
            options={AGG_FNS}
            onChange={(v) => updateConfig(id, { fn: v })}
          />
        )}

        {kind === 'OPERATION' && (
          <>
            <LabeledSelect
              label="Operator"
              value={String(config.op ?? 'ADD')}
              options={OPS}
              onChange={(v) => updateConfig(id, { op: v })}
            />
            <label className="text-[10px] text-muted-foreground">
              Constant (if only input “a” is wired)
              <input
                className={fieldCls}
                type="number"
                value={
                  config.constant == null ? '' : String(config.constant)
                }
                onChange={(e) =>
                  updateConfig(id, {
                    constant: e.target.value === '' ? null : Number(e.target.value),
                  })
                }
              />
            </label>
          </>
        )}

        {kind === 'CONSTANT' && (
          <label className="text-[10px] text-muted-foreground">
            Value
            <input
              className={fieldCls}
              type="number"
              value={String(config.value ?? 0)}
              onChange={(e) => updateConfig(id, { value: Number(e.target.value) })}
            />
          </label>
        )}

        {kind === 'RECONCILE' && (
          <LabeledSelect
            label="Field"
            value={String(config.field ?? 'net')}
            options={RECON_FIELDS}
            onChange={(v) => updateConfig(id, { field: v })}
          />
        )}

        {kind === 'OUTPUT' && (
          <>
            <label className="text-[10px] text-muted-foreground">
              Label
              <Input
                className={cn(fieldCls, 'nodrag')}
                value={String(config.label ?? '')}
                onChange={(e) => updateConfig(id, { label: e.target.value })}
              />
            </label>
            <LabeledSelect
              label="Format"
              value={String(config.format ?? 'NUMBER')}
              options={OUTPUT_FORMATS}
              onChange={(v) => updateConfig(id, { format: v })}
            />
          </>
        )}
      </div>
    </div>
  )
}

function TxnGroupEditor({
  config,
  onSelector,
}: {
  config: Record<string, unknown>
  onSelector: (patch: Record<string, unknown>) => void
}) {
  const sel = (config.selector as Record<string, unknown>) ?? {}
  return (
    <div className="flex flex-col gap-2">
      <LabeledSelect
        label="Direction"
        value={String(sel.direction ?? '')}
        options={['', 'DEBIT', 'CREDIT']}
        labels={{ '': 'Any' }}
        onChange={(v) => onSelector({ direction: v || undefined })}
      />
      <div className="grid grid-cols-[1fr_1fr] gap-1.5">
        <LabeledSelect
          label="Match field"
          value={String(sel.key ?? '')}
          options={['', ...SELECTOR_KEYS]}
          labels={{ '': 'None' }}
          onChange={(v) => onSelector({ key: v || undefined })}
        />
        <LabeledSelect
          label="Op"
          value={String(sel.op ?? 'CONTAINS')}
          options={SELECTOR_OPS}
          onChange={(v) => onSelector({ op: v })}
        />
      </div>
      {sel.key ? (
        <label className="text-[10px] text-muted-foreground">
          Value
          <input
            className={fieldCls}
            value={String(sel.value ?? '')}
            onChange={(e) => onSelector({ value: e.target.value })}
          />
        </label>
      ) : null}
      <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
        <Checkbox
          className="nodrag size-3.5"
          checked={Boolean(sel.exclude_internal_transfers)}
          onChange={(e) =>
            onSelector({ exclude_internal_transfers: e.target.checked })
          }
        />
        Exclude internal transfers
      </label>
    </div>
  )
}

function LabeledSelect({
  label,
  value,
  options,
  labels,
  onChange,
}: {
  label: string
  value: string
  options: string[]
  labels?: Record<string, string>
  onChange: (v: string) => void
}) {
  return (
    <label className="text-[10px] text-muted-foreground">
      {label}
      <Select
        className="nodrag h-7 text-xs"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {labels?.[o] ?? o.toLowerCase()}
          </option>
        ))}
      </Select>
    </label>
  )
}

# Tech Stack — modular, sleek, dynamic UI

The signature surface is a **card canvas**: users drop transaction *cards* and wire
them with math operators into a report. That is a **node-graph editor**, which
dictates the frontend core. The rest is chosen to stay modular, typed, and light.

## Frontend

| Concern | Choice | Why |
|---------|--------|-----|
| Framework | **React 18 + TypeScript + Vite** | Fast HMR, typed, matches the existing magoneai FE; huge ecosystem for the pieces below. |
| **Node/card canvas** | **React Flow (`@xyflow/react`)** | Purpose-built for draggable nodes + typed connection handles + edges — exactly the card→operator→output graph. Custom node types render each card kind; connection validation enforces port types on the client, the server re-validates. |
| Styling | **Tailwind CSS** + **shadcn/ui** (Radix primitives) | "Sleek + modular": copy-in components you own, accessible, themeable via CSS vars; no heavyweight component-library lock-in. |
| Server state | **TanStack Query** | Caching, background refetch, mutations for audits/documents/transactions; pairs with the SSE progress stream. |
| Client state | **Zustand** | Minimal store for canvas/editor UI state (selection, dragging, unsaved graph); avoids Redux boilerplate. |
| Data grid | **TanStack Table** (+ virtualization) | Thousands of transactions, server-side paging/filter/sort, column pinning for date/amount/balance. |
| Forms + validation | **React Hook Form + Zod** | The initiation form (name required), selector builder, manual transaction edits; Zod schemas shared with API types. |
| Charts | **Recharts** (or **visx** for custom) | Report visualisations (spend by merchant, inflow/outflow). |
| Drag/drop (non-canvas) | **dnd-kit** | Dragging transactions into cards, reordering outputs. |
| Live progress | **SSE (EventSource)** | Push per-page extraction progress + status/re-eval events (`GET /audits/{id}/events`). Simpler than WebSockets for one-way progress. |
| Money/dates | **dinero.js** + **date-fns** | Decimal-safe money display; month-wise range math. |
| Export | server-rendered PDF/CSV | Report export lives in the backend for deterministic output. |

**Canvas UX notes:** each node is a custom React Flow node — `TXN_GROUP` shows its
selector + live count/preview rows, `AGGREGATE`/`OPERATION` show their computed
scalar inline, `OUTPUT` shows the formatted report line. An operator palette
(+ − × ÷ %) drops `OPERATION` nodes; edges carry typed data (TxnSet vs scalar) and
invalid connections are refused with a hint. Autosave the graph (debounced `PUT
/report`) and re-evaluate on change.

## Backend

| Concern | Choice | Why |
|---------|--------|-----|
| API | **FastAPI (Python 3.11+)** + **Pydantic v2** | Matches magoneai; async; typed schemas mirror the FE Zod types. |
| Workflow orchestration | **Temporal** | Reused from the KB engine — retry isolation, heartbeats, resume, worker isolation for heavy extraction. |
| DB / ORM | **PostgreSQL + SQLModel/SQLAlchemy** | Relational core + **JSONB** for flexible `identifiers`, `DocumentMeta.kv`, and node `config`/`ui`. GIN index on identifiers. |
| Migrations | **Alembic** | Same as the reference codebase. |
| Object storage | **S3 / MinIO** | Source PDFs + per-page text blobs (reuses `payload_offload` / `page_store` patterns). |
| Extraction (PDF) | **Docling + DocLayout-YOLO + TableFormer** via the ported **converter pool** | Reused wholesale; job pooling + paged multi-page baked in. |
| Extraction (CSV/XLSX) | **pandas + openpyxl** (+ **DuckDB** for large files) | UPI-app spreadsheet exports parse directly to rows — no layout model, no OCR; cheapest reliable path. |
| Local SLM (**optional toggle**) | **Ollama / llama.cpp** serving **Qwen3-4B GGUF** behind a `NarrationStructurer` interface | Default **off**; deterministic parsing ships v1. When on, adds grammar-constrained "better parse" for flagged rows; swappable to vLLM on a bigger box. |
| Auth | reuse magoneai org/user scoping | keep columns; run single-org locally. |

## Infra / dev

| Concern | Choice |
|---------|--------|
| Local orchestration | **docker-compose**: `postgres`, `temporal` (+ UI), `minio`, `ollama`, `api`, `audit-worker`, `frontend` |
| Package mgmt | **uv** (Python) · **pnpm** (JS) |
| Quality gates | ruff + pyright/mypy + pytest (BE); eslint + tsc + vitest + Playwright (FE) |
| Observability | structured logging (reuse `core/logging`); Temporal UI for workflow state; extraction-confidence metrics |

## Why this is "modular"
- **Extraction, structuring (SLM), and report evaluation are three independent,
  swappable modules** behind interfaces — you can replace the SLM, add a bank
  profile, or change the compute engine without touching the others.
- **The report is data (a graph), not code** — new node/operator kinds are enum +
  config additions, no schema migration for each new report shape.
- **FE and BE share types** (Zod ↔ Pydantic) so the card/graph contract is
  enforced on both sides.
- **The canvas is the only heavy FE dependency**; everything else is small,
  own-your-code (shadcn) or headless (TanStack), keeping the bundle sleek.

## Minimal dependency manifest (indicative)
```
frontend:  react react-dom @xyflow/react @tanstack/react-query @tanstack/react-table
           zustand react-hook-form zod tailwindcss (+shadcn/ui) recharts dnd-kit
           date-fns dinero.js
backend:   fastapi pydantic sqlmodel alembic temporalio docling
           (ported converter pool) boto3/minio httpx  + ollama/llama-cpp client
```

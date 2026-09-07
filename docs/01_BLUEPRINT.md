# Development Blueprint

A phased roadmap to build the automated month-wise expense-audit system. Each
phase is independently shippable and ends with a demoable capability. Phases are
ordered by dependency; the extraction spine (P1–P2) must precede the report
engine (P3), which precedes the dynamic UI polish (P4).

---

## Target architecture (one diagram)

```
┌────────────────────────── Frontend (React + Vite) ──────────────────────────┐
│  Audit wizard │ Document dropzone + live progress │ Transaction grid │       │
│  Card canvas (React Flow: TXN_GROUP · AGGREGATE · OPERATION · OUTPUT nodes)  │
└───────────────▲───────────────────────────────────────────────▲─────────────┘
                │ REST /api/v1 + SSE /events                     │
┌───────────────┴───────────────── Backend (FastAPI) ───────────┴─────────────┐
│  Audit svc │ Document svc │ Transaction svc │ Report compute engine (DAG)    │
└───────┬───────────────────────────┬──────────────────────────┬──────────────┘
        │ dispatch                   │ read/write               │ pure eval
        ▼                            ▼                          ▼
┌─────────────── Temporal ───────────────┐   ┌── Postgres ──┐   (in-process,
│ AuditExtractionWorkflow (per document) │   │ audits       │    memoised)
│  precount→extract→parse→structure→     │   │ documents    │
│  persist→reconcile                     │   │ transactions │
│  [dedicated task queue: audit-extract] │   │ report graph │
└───┬───────────────┬───────────────┬────┘   └──────────────┘
    ▼               ▼               ▼
 Converter pool  Local SLM      Object store (S3/MinIO)
 (Docling+YOLO   (llama.cpp,    page blobs + source PDFs
  +TableFormer)  Qwen3-4B GGUF)
```

## Repo layout (proposed)

```
automated-audit/
  backend/
    audit/            # Audit + lifecycle (models, repo, service, routes)
    documents/        # upload (streamed), doc registry — mirrors KB routes
    extraction/       # AuditExtractionWorkflow + activities
      bank_profiles/  # per-bank column maps + narration regex (axis.py, hdfc.py…)
      converter_pool.py   # imported/adapted from be/knowledge/extract_pool.py
      parse_transactions.py
      structure_narration.py   # regex-first + SLM-assist
      reconcile.py
    transactions/     # ExtractedTransaction model, query/filter, manual edits
    report/           # AuditNode/Edge model + DAG compute engine + evaluate API
    slm/              # NarrationStructurer interface + llama.cpp/Ollama client
    core/             # config, logging, db, auth (reuse magoneai patterns)
    temporal/         # worker.py (audit-extraction queue), config
  frontend/           # Vite + React + TS (see 04_TECH_STACK.md)
  docs/               # these design docs
  infra/              # docker-compose (postgres, temporal, minio, ollama)
```

---

## Phase 0 — Foundations (½–1 week)
**Goal:** repo, infra, and a walking skeleton.
- Scaffold `backend/` (FastAPI) + `frontend/` (Vite) + `infra/docker-compose`
  (Postgres, Temporal, MinIO, Ollama).
- Port `core/` (config, logging, db/SQLModel session, auth) from magoneai patterns.
- CI: lint (ruff), type (mypy/pyright), test (pytest), FE (eslint/tsc/vitest).
- **Exit:** `GET /health` green; empty audit table migrated; one Temporal worker boots.

## Phase 1 — Audit lifecycle + document ingest spine ✅ built
**Goal:** create an audit, upload a PDF, watch it extract page-by-page.
- [x] `Audit` model + `AUD-…` id value object (ULID→base32).
- [x] Initiation API (`subject_name` required) + `AuditDocument` **streamed upload**
  (`SpooledTemporaryFile` + streamed SHA-256 dedupe) + LocalFileStore.
- [x] **Password gate wired in** (§2.0): detect → resolve candidates (typed / saved
  / derived from the audit's own name+DOB) → unlock → `LOCKED` doc + `/unlock`
  endpoint. Opt-in encrypted credential reuse across a bank's statements.
- [x] Paged extraction with per-page `ExtractedPage` rows + `pages_extracted/total`
  progress, behind an **`Extractor` interface**; **bounded job pool** (job pooling).
- [x] Tests: 32 passing (unlock, derivation, credential round-trips, pool bounds,
  full ingest API); verified on the real 8-page Axis PDF (8/8 pages).
- **Deferred to P5 (behind the same interfaces):** the **Docling+Temporal** adapter
  replaces the pypdf baseline `Extractor`; a **format router** adds the CSV/XLSX
  `tabular_parse` path; **SSE** replaces poll for progress. (pypdf baseline +
  polling suffice to build P2/P3 now.)
- **Exit (met):** upload the Axis PDF → 8 pages extract, page text persisted;
  encrypted PDFs unlock via typed/saved/derived passwords.

## Phase 2 — Transaction structuring, deterministic core (1.5–2 weeks) ⟵ the core value
**Goal:** PDF + CSV sources become clean, queryable `ExtractedTransaction` rows —
**no LLM required**.
- `source_profiles/`: `axis.py` (PDF column map + `OPENING BALANCE` seed + multi-
  line Particulars folding) and CSV profiles (GPay/PhonePe/Paytm/bank export).
- `parse_transactions_activity` (table-grid + line-oriented fallback for PDF; direct
  row map for CSV) + **balance reconciliation** confidence signal.
- `structure_narration`: **deterministic** UPI/NEFT/IMPS parser → `identifiers` enum
  map (baseline, always on). SLM stays behind the `structurer_slm.enabled` toggle
  (**default off**) via the `NarrationStructurer` interface — wire the interface now,
  ship the regex impl; the SLM impl lands in Phase 5.
- `ExtractedTransaction` + `DocumentMeta` persistence (idempotent upsert); low-
  confidence rows flagged for manual review.
- Transaction query/filter API + a basic grid in the FE (with manual-edit path).
- **Exit:** every row (PDF + CSV) is structured with counterparty name/UPI-ref/bank,
  direction, amount, balance, account; reconciliation flags mismatches; manual edit
  works — all deterministic, SLM toggle off.

## Phase 2.5 — Audit generation = reconcile pre-pass (½ week)
**Goal:** the innate reconciled report over multiple merged sources.
- `reconcile_pass()`: cross-source **de-dup** (overlap), **coverage/gap** detection
  vs the window, **balance continuity** chaining, **own-transfer netting** (§2.6 of
  the LLD).
- `POST /audits/{id}/generate` returns `{reconciliation, outputs}`; `PATCH /range`
  triggers it.
- **Exit:** upload two overlapping months across two accounts → one reconciled
  report with correct dedup, coverage %, and transfer netting; change the range →
  it regenerates from cache.

## Phase 3 — Report compute engine + card graph (2 weeks)
**Goal:** user builds a report from cards + math ops; changing the date range
regenerates it instantly.
- `ReportDefinition` + `AuditNode` + `AuditEdge` schema; save-time acyclicity +
  port-type validation.
- DAG evaluator (TXN_GROUP → AGGREGATE → OPERATION → RECONCILE → OUTPUT) on top of
  the reconciled view, Decimal math, provenance, memoisation by
  `(report_version, range, txn_maxid)`.
- `PATCH /range` and "add source" both route through `generate` (reconcile + eval).
- Report export (PDF/CSV/JSON).
- **Exit:** a "monthly personal audit" graph (e.g. total UPI spend by merchant,
  net inflow, savings rate) evaluates over the cache; moving the date range
  re-generates with no re-extraction.

## Phase 4 — Dynamic UI: the card canvas (2 weeks, overlaps P3)
**Goal:** the sleek node-editor experience.
- React Flow canvas: draggable cards, typed connection handles, an inline
  operator palette (+ − × ÷ %), live per-node value preview.
- Selector builder (pick IdentifierKey + matcher), transaction naming/grouping UI.
- Document dropzone with per-page progress; audit dashboard; range picker with
  "regenerate" affordance; DocumentMeta (misc kv/freeform) panel.
- **Exit:** end-to-end demo: initiate → upload → design report on canvas →
  change range → export.

## Phase 5 — Enhancements, hardening & scale (1–2 weeks, ongoing)
- **SLM "better parse" toggle**: implement `SlmStructurer` (llama.cpp/Ollama +
  Qwen3-4B + GBNF grammar, pooled) behind `structurer_slm.enabled`; A/B it against
  the deterministic baseline on flagged rows — see `03_SLM_RESEARCH.md`.
- **Auto-categorization** (deferred here per decision): tag each txn
  (food/fuel/transfer/…) filling `user_label`/a `category` field, user-editable;
  best done by the SLM once the toggle exists.
- Worker-replica scaling on `audit-extraction`; load test multi-page + multi-source.
- Add source profiles (HDFC/SBI/ICICI PDFs; more UPI CSV shapes).
- Optional LoRA fine-tune of the SLM *only if* field-level errors demand it.
- Observability (per-activity metrics, extraction/reconciliation dashboards),
  report-template library, audit export polish.

---

## Milestones & rough timeline
| Milestone | Phases | ~Weeks (cumulative) |
|-----------|--------|---------------------|
| M1 — extract PDF + CSV sources live | P0–P1 | ~2.5 |
| M2 — structured transactions (deterministic) | P2 | ~4.5 |
| M2.5 — reconciled report over merged sources | P2.5 | ~5 |
| M3 — report from cards, range-reactive | P3 | ~7 |
| M4 — full dynamic-UI demo | P4 | ~9 |
| M5 — SLM toggle, auto-categorize, scale | P5 | ~10.5+ |

## Key risks & mitigations
| Risk | Mitigation |
|------|-----------|
| Statement/export layouts vary across banks & apps | Source-profile registry + line-oriented fallback + reconciliation as a correctness oracle; start with Axis PDF + one UPI CSV, add profiles behind the same interface |
| SLM JSON drift / hallucinated fields (only if toggle on) | Deterministic parser is the baseline, so v1 doesn't depend on the SLM at all; when enabled, **constrained decoding (GBNF grammar)** guarantees schema-valid output and it only runs on already-flagged rows |
| PDFium not thread-safe → crashes | Keep converter pool at 1/process; scale via replicas (already proven in the KB engine) |
| 8GB local VRAM limits model size | Qwen3-4B GGUF Q4_K_M fits; abstraction lets a bigger box run Qwen3-8B/vLLM later |
| Scanned / image statements | Router's vision-OCR path already exists; opt-in per doc |
| Confidential data (financial) | Fully local extraction + local SLM = no data leaves the box; mask/redact in exports |

## Definition of done (v1)
Initiate an audit (name required, `AUD-…` id) → add **multiple mixed-format sources**
(bank PDFs + UPI CSV/XLSX) → watch extraction → get identifier-tagged, nameable
transactions → the **date range generates the innate reconciled report** (dedup,
coverage, balance continuity, transfer netting) → optionally design a card+operation
layer on the canvas → change the range or add a source and see the reconciled report
regenerate from cache without re-extraction → export the audit. All **deterministic**;
the local **SLM stays an off-by-default toggle** for better parsing.

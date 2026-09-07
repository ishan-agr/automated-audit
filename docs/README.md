# Automated Audit System — Design Docs

An automated, **month-wise audit system for personal expenses**. Input is bank
statements / UPI-app exports (PDF, tabular or free-form). The system runs an
**audit-by-audit procedure**: initiate → attach documents + date range → extract
→ generate a **user-defined audit report** built from connectable *cards* and
math operations, all computed over cached extracted transactions.

## Reference material used to design this

| Reference | What we took from it |
|-----------|----------------------|
| `automated-audit/AcctStatement_XXX7229_02082026.pdf` | Axis Bank statement — header + transaction-table layout; the **narration grammar** (`UPI/P2M/<ref>/<counterparty>/UPI/<bank>`) that yields the name / UPI-id / acc-no identifiers |
| `D:\magoneai_v2\be\knowledge` | The static-KB extraction pipeline we **reuse**: Temporal workflow + Docling + DocLayout-YOLO page router + TableFormer + **converter pool** (job pooling) + **paged multi-page** extraction + heartbeats + S3 payload offload |

## Documents

1. **[01_BLUEPRINT.md](01_BLUEPRINT.md)** — phased development roadmap, milestones, repo layout, risks.
2. **[02_LLD.md](02_LLD.md)** — low-level design: domain model, DB schema, extraction pipeline, the card/operation compute engine, APIs, sequence flows.
3. **[03_SLM_RESEARCH.md](03_SLM_RESEARCH.md)** — which small/quantized LLM to run locally for narration→JSON structuring (HF-sourced, quantization-aware, per hardware tier).
4. **[04_TECH_STACK.md](04_TECH_STACK.md)** — modular, sleek tech stack for the dynamic card-canvas UI + backend.

## The one-paragraph mental model

An **Audit** owns **multiple Sources** (bank statement PDFs *and* UPI-app CSV/XLSX
exports — mixed formats) and a **DateRange**. Each source triggers a Temporal
**extraction workflow** that reuses the magoneai KB engine (PDF) or a light tabular
parser (CSV/XLSX) and emits **ExtractedTransaction** rows into a durable, immutable
cache. The **date range is the trigger** that *generates the audit* — and the
audit's innate output is a **reconciled report**: a pre-pass merges/de-dupes the
sources, checks coverage of the window, chains balances, and nets own-account
transfers, then the user's optional **card graph** (Cards keyed by an *identifier
enum* — NAME / UPI_ID / ACCOUNT_NO / LABEL / … wired by basic math ops + − × ÷ %)
computes on top. Changing the range or adding a source only re-generates from the
cache — it **never re-extracts**. Transaction structuring is deterministic by
default; a local **SLM is an opt-in toggle** for better parsing of messy rows.

## Decisions locked (v1)
- **Local, single-user** deployment.
- **Multiple sources per audit, mixed formats (PDF + CSV/XLSX), merged & reconciled.**
- **Reconciled report = the audit** (not a separate feature/API); the date range triggers it.
- **SLM = optional "better parse" toggle**, default off; deterministic parsing ships v1.
- **Auto-categorization deferred to Phase 5**; v1 is manual naming/grouping.

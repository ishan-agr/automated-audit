# Low-Level Design (LLD)

> Scope: the complete v1 design — domain model, DB schema, extraction pipeline
> (reusing the magoneai KB engine), the card/operation compute engine, the audit
> lifecycle state machine, and the REST/stream API surface.

---

## 1. Domain model

```
Audit ──1─┬─* AuditDocument ──1─* ExtractedTransaction
          │                └─1─* DocumentMeta   (key/value + free-string misc)
          ├─1─1 DateRange   (mutable; from,to)
          └─1─1 ReportDefinition ──1─* AuditNode ──*─* AuditEdge
                                                       (nodes: TXN_GROUP | AGGREGATE
                                                        | OPERATION | CONSTANT | OUTPUT)
```

### 1.1 Audit
The unit of work. Created by the initiation form.

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` PK | Human handle **`AUD-<base32 ULID suffix>`** (e.g. `AUD-7F3K9Q`). This is the "uid as enum": short, unique, monotonic, URL-safe. |
| `subject_name` | `str` **required** | The person being audited. Only compulsory field. |
| `subject_email` | `str?` | optional |
| `subject_phone` | `str?` | optional |
| `status` | `enum` | see §4 state machine |
| `range_from` / `range_to` | `date?` | mutable audit window (month-wise default = calendar month) |
| `report_definition_id` | `str?` | active report graph |
| `created_at/updated_at` | `tz datetime` | |

> **UID-as-enum**: `AuditId` is modelled as a value object with a checksum so it
> can be referenced everywhere (URLs, exports, card selectors) as a stable enum
> handle. Generation: `ULID → Crockford base32 → last 6 chars → "AUD-" prefix`,
> collision-checked on insert.

### 1.2 AuditDocument
Mirrors `KBDocument` from the KB engine (so we inherit paged-extraction progress
fields verbatim).

| Field | Type | Notes |
|-------|------|-------|
| `id` | PK | |
| `audit_id` | FK | |
| `file_id` | str | dedupe by SHA-256 (reuse FileService) |
| `filename` | str | |
| `doc_kind` | enum | `BANK_STATEMENT` \| `UPI_EXPORT` \| `UNKNOWN` (classified) |
| `bank_hint` | str? | `AXIS` \| `HDFC` \| `SBI` \| `ICICI` \| `GPAY` \| `PHONEPE` \| `PAYTM` … (drives the parser profile) |
| `status` | enum | `PENDING→PROCESSING→EXTRACTED→PARSED→READY` \| `FAILED` |
| `page_count` | int? | precount via pypdf |
| `pages_extracted` / `pages_total` | int? | progress (reused verbatim) |
| `workflow_id` | str? | Temporal id for cancel/resume |
| `stmt_period_from/to` | date? | parsed from header — used to sanity-check the audit range |

### 1.3 ExtractedTransaction — the durable extraction cache
**This is the pivotal table.** It is written once by extraction and is *immutable
source data*; every report is a pure function of these rows filtered by date. This
is what makes "change the date range → regenerate audit **without re-extracting**"
cheap and correct.

| Field | Type | Notes |
|-------|------|-------|
| `id` | PK | |
| `audit_id` | FK, indexed | |
| `document_id` | FK | provenance |
| `page_num`, `row_index` | int | citation back to the source page |
| `tran_date` | date, indexed | primary date used for range filtering |
| `value_date` | date? | |
| `narration_raw` | text | verbatim particulars (multi-line folded) |
| `direction` | enum | `DEBIT` \| `CREDIT` |
| `amount` | `Decimal(18,2)` | always positive; sign implied by `direction` |
| `balance` | `Decimal(18,2)?` | running balance (used for reconciliation) |
| `channel` | enum | `UPI` \| `NEFT` \| `IMPS` \| `RTGS` \| `POS` \| `ATM` \| `CHEQUE` \| `CHARGE` \| `INTEREST` \| `OTHER` |
| `txn_subtype` | enum? | `P2M` \| `P2A` \| `SELF` (from UPI narration) |
| `ref_id` | str? | UPI ref / UTR / cheque no |
| **identifiers** | `JSONB` | the **enum-keyed** identity map (see §1.4) |
| `counterparty_name` | str? | denormalised from identifiers for fast filter |
| `user_label` | str? | user-assigned name for grouping (see §5.4) |
| `confidence` | float | parse confidence; low → flagged for review |
| `parse_source` | enum | `REGEX` \| `SLM` \| `MANUAL` — provenance of the structuring |
| `raw_json` | JSONB | full extractor/SLM output for audit trail |

Indexes: `(audit_id, tran_date)`, `(audit_id, counterparty_name)`,
GIN on `identifiers`, `(audit_id, user_label)`.

### 1.4 The identifier enum (grouping key)
Requirement: *"transactions … identifiable by an enum (name, upi id, acc no, as
user wants)"*. Modelled as an open enum `IdentifierKey` and a per-transaction
`identifiers` JSONB:

```jsonc
IdentifierKey = NAME | UPI_ID | ACCOUNT_NO | REF_ID | COUNTERPARTY_BANK
              | CHANNEL | LABEL   // extensible

// example row.identifiers, parsed from
// "UPI/P2M/645702960479/Google India Digital/UPI/AXIS BANK"
{
  "NAME": "Google India Digital",
  "UPI_ID": "645702960479",          // UPI ref acts as the UPI identifier here
  "COUNTERPARTY_BANK": "AXIS BANK",
  "CHANNEL": "UPI",
  "REF_ID": "645702960479"
}
```
Cards select transactions by *(IdentifierKey, matcher)*. "As user wants" = the UI
lets the user pick which key to group/identify by, per card.

### 1.5 DocumentMeta — miscellaneous key/value + free string
Requirement: *"all miscellaneous details available respective to that document in
key-value / or free string format"*. Two columns cover both shapes:

| Field | Type | Notes |
|-------|------|-------|
| `document_id` | FK | |
| `kv` | JSONB | structured header facts: `{account_no, ifsc, micr, customer_id, scheme, currency, opening_balance, closing_balance, period_from, period_to, holder_name, pan_masked, …}` |
| `freeform` | text | anything not confidently keyed — preserved verbatim so nothing is lost |

Parsed from the statement header block (page 1 of the Axis sample):
`ISHAN AGRAWAL … Customer ID … IFSC Code: UTIB0005016 … Statement of Axis Account
No: 924010023017229 for the period (From: 01-04-2026 To: 02-08-2026)`.

### 1.6 ReportDefinition + AuditNode + AuditEdge — the workflow graph
Requirement: *"the person can decide the audit report's format and calculations …
like a workflow … custom cards … connect multiple cards with mathematical
operations in between them."* This is a **directed acyclic compute graph**.

`ReportDefinition`: `{id, audit_id, name, version, canvas: {...}, is_active}`
(versioned so editing never corrupts a generated report; regeneration always
targets the active version).

`AuditNode`:
| Field | Type | Notes |
|-------|------|-------|
| `id` | PK | |
| `report_id` | FK | |
| `kind` | enum | `TXN_GROUP` \| `AGGREGATE` \| `OPERATION` \| `CONSTANT` \| `RECONCILE` \| `OUTPUT` |
| `config` | JSONB | kind-specific (below) |
| `ui` | JSONB | `{x, y, w, h, color, title}` — canvas placement |

Node configs:
- **TXN_GROUP** (a "card" holding transactions): `{ selector: Selector }` where
  `Selector = { all?: bool, key?: IdentifierKey, op: EQ|CONTAINS|IN|REGEX,
  value|values, direction?, channel?, date_scope?: INHERIT|CUSTOM }`. Produces a
  **transaction set** (and, for display, its rows).
- **AGGREGATE**: `{ input: nodeId, fn: SUM|COUNT|AVG|MIN|MAX|NET, field: amount }`
  → scalar. `NET = SUM(credit) − SUM(debit)`.
- **OPERATION**: `{ op: ADD|SUB|MUL|DIV|PCT, inputs: [nodeId, nodeId | constant] }`
  → scalar. This is the "math operation between cards". Predefined + basic per the
  requirement; the enum is the single extension point for future ops.
- **CONSTANT**: `{ value: number }`.
- **OUTPUT**: `{ input: nodeId, label, format: CURRENCY|NUMBER|PERCENT }` → a line
  on the final report.

`AuditEdge`: `{id, report_id, source_node, target_node, target_port}`. Edges
encode data flow; the evaluator ignores UI and reads edges. **Acyclicity** is
enforced on save (reject a cycle with the offending path).

---

## 2. Extraction pipeline (reuses the magoneai KB engine)

We fork the KB `DocumentIngestionWorkflow` into an **`AuditExtractionWorkflow`**.
A **format router** at the head picks the path by file type; both converge on the
same `parse_transactions → structure → persist → reconcile` tail:

- **PDF** (bank statements, PDF UPI exports) → the reused KB layout path
  (converter pool + DocLayout-YOLO router + TableFormer, paged). Everything up to
  "clean per-page text + tables" is reused **unchanged**; only the
  chunk→embed→index tail is replaced.
- **CSV / XLSX** (spreadsheet UPI exports — GPay/PhonePe/Paytm/bank CSV) → a
  lightweight **tabular path** (adapting magoneai's `static_kb` tabular route):
  read rows directly with pandas/openpyxl (or DuckDB for large files), **no layout
  model, no OCR**. Rows map straight into `parse_transactions` via a per-source
  column profile. Much cheaper and more reliable than PDF for the same data.

```
                                   ┌── PDF ──▶ extract_document_activity ──┐
Upload ─▶ format router ──────────┤          (REUSED: converter pool,      ├─▶ parse_transactions ─▶ structure_narration ─▶ persist
          (by mime/ext)            │           YOLO router, TableFormer,    │   (NEW: deterministic    (OPTIONAL toggle:    (NEW)
                                   │           paged, heartbeat, S3)        │    table/row parser        SLM better-parse)
                                   └── CSV/XLSX ▶ tabular_parse_activity ───┘    per source profile,
                                              (NEW: pandas/openpyxl/DuckDB,       + balance recon)
                                               no layout model, no OCR)

(Per-source extraction stops at `persist`. The cross-source reconcile pre-pass is
NOT here — it runs at AUDIT GENERATION time, triggered by the date range / an added
source, over the whole cache; see §2.6 and §3.)

### 2.0 Password-protected PDFs — the unlock gate (runs first) ✅ built
Statement PDFs are frequently encrypted, and **different documents in one audit
carry different passwords** because **each bank uses its own password format**. So
the very first step of the PDF path (before Docling/pdfium ever see the bytes) is
an unlock gate. *(Implemented: `backend/app/extraction/pdf_password.py`,
`backend/app/bank_profiles/passwords.py`, `backend/app/credentials/`.)*

**Flow at upload:**
```
bytes ─▶ is_encrypted? ──no──▶ extract as-is
             │yes
             ▼
   build ordered candidates ──▶ unlock_pdf ──ok──▶ un-encrypted bytes ─▶ extract
   (§ priority below)              │fail
                                   ▼
                          doc.status = LOCKED, ask the user for a password
                          (then retry with the typed password prepended)
```

**Candidate priority** (`credentials.service.build_candidates`, first hit wins;
`""` is always tried first for owner-only locks):
1. **Typed for this upload** — most specific.
2. **Saved literal for this bank** — the opt-in convenience ("remember my HDFC
   password").
3. **Derived** from the bank's known format(s) + saved personal inputs
   (`bank_profiles.passwords.candidates_for_bank`).

**Store-against-the-bank (opt-in, encrypted).** `BankCredential` (scope = audit or
user) holds **either** a literal password **or** the personal inputs to derive one
(name/DOB/PAN/customer-id…), as **Fernet ciphertext** (`core.crypto`, key
`AUDIT_SECRET_KEY`). Never plaintext, never on the document row. Gated by
`allow_credential_storage`. This is what makes "different banks have different
password formats, entered once" work: the next statement from that bank unlocks
with no retyping.

**Bank password formats are data, not authority.** The registry models formats as
composable segments (e.g. `FIRST4_UPPER(name) + DDMM(dob)` → `ISHA1008`) so the UI
can show a hint and derive candidates; every format is flagged `verify=true`
(common-but-not-guaranteed) and is only ever a *candidate*. Some banks (SBI
e-statements) use a user-chosen password with **no** derivable format — the literal
path covers them. Output of the gate is always an **un-encrypted** PDF, so the rest
of the pipeline is unchanged.

**Doc model fields** (`documents.models.AuditDocument`): `is_encrypted`,
`password_status` (`NOT_REQUIRED|LOCKED|UNLOCKED`), `unlocked_with_saved_credential`
(UX signal), and a `LOCKED` doc status so an audit with an un-unlocked source is
visibly blocked rather than silently failed. **The original encrypted bytes are
what we SHA-256 for dedupe** (so re-uploading the same locked file is still caught);
the decrypted bytes are transient input to the extractor.
```

### 2.1 Reused as-is (from `be/knowledge/`)
- **`extract_pool.py`** — the process-level Docling **converter pool** (job
  pooling). `KB_MAX_CONCURRENT_EXTRACTS=1` per process (PDFium is not
  thread-safe); scale with worker replicas. Pre-warmed at startup.
- **Paged multi-page extraction** — `kb_document_pages` per-page state,
  `KB_EXTRACT_BATCH_SIZE=10` with overlap=1, resume from `max(extracted)+1`,
  synthetic rows for blank pages, `pages_extracted/pages_total` progress.
- **DocLayout-YOLO router** — per-page: digital-text → pdfium fast path;
  scanned/figure-dominant → vision LLM OCR; table → TableFormer (cells from the
  digital text layer). Bank statements are almost always digital-text → the fast,
  cheap path dominates.
- **Heartbeat pump** (`pumping`) over blocking converts + pool waits.
- **S3 payload offload** for inter-activity data.
- **Worker isolation** — a dedicated Temporal task queue
  (`audit-extraction`), separate from the API, so heavy extraction can't starve
  request handling. Scale `docker compose up --scale audit-worker=N`.

### 2.2 New activity: `parse_transactions_activity` (deterministic)
Input: per-page text + TableFormer cell grid. Output: raw transaction rows.

- **Bank-profile registry**: a small table of column maps + narration regexes
  keyed by `bank_hint`. The Axis profile: columns
  `[Tran Date, Chq No, Particulars, Debit, Credit, Balance, Init.Br]`; the
  `OPENING BALANCE` seed row; multi-line **Particulars folding** (a row's
  narration spans 2-3 physical lines until the next date-prefixed line — fold
  them, mirroring the KB chunker's `_fold_short_text`).
- **Two extraction modes**, auto-selected: (a) *table-grid* when TableFormer
  returns a clean grid; (b) *line-oriented* fallback that reconstructs rows from
  the pdfium text layer using the date anchor + amount/balance column geometry
  (needed because many statements render the table without ruled cells).
- **Reconciliation is computed here**: `balance[i] − balance[i-1]` must equal
  `+credit` or `−debit`; mismatches set `confidence` low and raise a flag. This
  is a *free, deterministic* correctness signal unique to financial docs.

### 2.3 New activity: `structure_narration_activity` (deterministic core, SLM is an opt-in toggle)
Turns `narration_raw` into `{channel, txn_subtype, identifiers, counterparty_*}`.

- **Deterministic parser is the baseline (always on).** UPI/NEFT/IMPS narration is
  highly structured; a rules/regex parser handles the ~90-95% that match
  `UPI/(P2M|P2A)/<ref>/<name>/<...>/<bank>`, `NEFT/<utr>/<name>/<bank>/…`, etc.
  `parse_source=REGEX`, `confidence≈0.99`, **$0 cost, no model**. This is enough to
  ship v1 end-to-end without any LLM.
- **SLM is an optional "better parse" toggle** — `structurer_slm.enabled`
  (default **off**, per the same pattern as the KB engine's
  `vision_enrichment.enabled`). **When off**, rows the deterministic parser can't
  confidently resolve are simply left with low `confidence` and **flagged for
  manual review** (the user fixes them in the grid). **When on**, those same
  low-confidence/messy rows are routed to the local SLM (see `03_SLM_RESEARCH.md`)
  with **JSON-Schema-constrained decoding** (GBNF grammar) so output is always
  schema-valid; `parse_source=SLM`. The SLM never sees the rows the regex already
  nailed, so cost/latency stay minimal and the toggle is purely additive accuracy.
- **Interface, not a dependency:** a `NarrationStructurer` port with two impls —
  `RegexStructurer` (default) and `SlmStructurer` (toggle). The pipeline, DB, and
  UI are identical either way; the toggle only swaps in the SLM fallback stage.
- **SLM job pooling** (only relevant when the toggle is on): a bounded async worker
  (semaphore = N, default 4) in front of a single llama.cpp/Ollama server, batched
  — mirrors the converter-pool philosophy (one heavy resource, leased per unit of
  work, heartbeat-safe).

### 2.4 New activity: `persist_transactions_activity`
Idempotent upsert (deterministic point id = `hash(document_id, page, row)`) so
retries overwrite in place. Writes `ExtractedTransaction` + `DocumentMeta`, flips
document `status→READY`, updates counts.

### 2.5 Adding documents later (extend an audit)
Requirement: *"after the audit is generated further documents can be added to
extend the audit and for this date range customization is necessary."* New docs
run the same workflow and append `ExtractedTransaction` rows tagged with the same
`audit_id`. Because the report is a pure function over `(audit_id, date range)`,
extending = "more rows exist" + "widen the range to include them" → the UI
**requires** confirming/adjusting `range_from/range_to` after an add, then
re-evaluates. No re-extraction of existing docs.

### 2.6 The reconciled report **is** the audit (multi-source, range-driven)
Reconciliation is **not a separate feature or API** — it is the innate output of
an audit. The system is audit-by-audit: **one audit trigger** ingests **any number
of data sources** (bank statement PDFs, UPI-app CSV/XLSX exports, … — extensible),
normalises them into one `ExtractedTransaction` stream, and the **date range is
the trigger** that (re)generates the audit's canonical artifact: a **reconciled
report** over that window.

So there is exactly one core loop, and everything hangs off it:

```
sources (n, mixed formats) ─▶ ExtractedTransaction cache ─┐
                                                          ├─▶ GENERATE AUDIT(range)
date range (set / changed) ───────────────────────────────┘        │
                                                                    ▼
                              reconcile pre-pass  →  report DAG  →  reconciled report
                              (dedup, coverage,     (user's cards   (summary + outputs,
                               continuity, netting)  + math ops)     one artifact)
```

§2.2 reconciles **within one statement**; this step reconciles **across all
sources** in the window. It is a **pre-pass of audit generation**, not a bolt-on:
generation always runs it first, then evaluates the report graph on the reconciled
view (§3). It is pure over the cache, so it re-runs on every range edit or added
source — same "regenerate, never re-extract" contract. Implemented as
`reconcile_pass()` inside the generate step (in-process; for a large window it can
be an activity on the `audit-extraction` queue, but it is conceptually part of
"generate the audit", not an independent job).

**Account identity.** Every `ExtractedTransaction` carries `source_account`
(the account no. from `DocumentMeta.kv`) and `source_period_from/to`. A multi-
account audit **partitions by account**; reconciliation and continuity checks run
per account, then roll up.

1. **Overlap de-duplication.** Consecutive/overlapping statements repeat rows.
   Dedup key = `(source_account, tran_date, amount, direction, ref_id | balance,
   narration_hash)`. Duplicates are collapsed to one canonical row (earliest
   `document_id` wins); the loser is kept with `superseded_by` set so the source
   is auditable. Prevents double-counting when two statements cover the same day.

2. **Coverage & gap detection over the required range.** From each doc's
   `source_period_from/to` we build the set of covered intervals **per account**,
   intersect with the audit `[range_from, range_to]`, and compute:
   `coverage% = covered_days / window_days`, plus the list of **uncovered
   sub-ranges** (missing months) and **overlap sub-ranges**. A window that isn't
   fully covered flags the audit `INCOMPLETE` (a warning, not a hard error) so a
   report is never silently computed over a month with no statement behind it.

3. **Cross-statement balance continuity (chained reconciliation).** For each
   account, sort statements by period; assert
   `closing_balance(stmt_n) == opening_balance(stmt_{n+1})`. Combined with the
   intra-statement delta check (§2.2), this gives an unbroken balance chain across
   the whole window: `opening(first) + Σcredit − Σdebit == closing(last)`. Any
   break localises the bad statement/day and flags it.

4. **Own-transfer detection (don't double-count).** In a multi-account audit, a
   `DEBIT` in account A often mirrors a `CREDIT` in account B (moving your own
   money). Match on `amount` + `tran_date ± window` + counterparty resolving to
   the audit subject / another audited account (name or acc-no in `identifiers`).
   Matched pairs are tagged `is_internal_transfer=true` so the default
   "net spend"/"expense" cards **exclude** them; they remain visible and can be
   opted back in per card.

5. **Reconciliation as a first-class output.** `AuditReconciliation` snapshot
   (per account + rolled up): `opening`, `closing_stated`, `closing_computed`,
   `Σdebit`, `Σcredit`, `net`, `txn_count`, `dedup_removed`, `coverage%`,
   `gaps[]`, `internal_transfer_total`, `flagged[]` (low-confidence / continuity
   breaks). Surfaced both as an API resource (§5.6) and as a **`RECONCILE`
   report node** the user can drop on the canvas (§3).

> Net effect: point 1 keeps totals honest across overlaps, point 2 tells the user
> their date range is actually backed by statements, points 3–4 are the two
> financial-correctness oracles (balance chain + transfer netting), and point 5
> makes all of it inspectable and wireable into the report.

---

## 3. Audit generation = reconcile pre-pass + report DAG

`generate_audit(range)` is the single operation the date range triggers. It first
runs the reconcile pre-pass (§2.6) to produce the canonical reconciled view + a
reconciliation summary, then evaluates the user's `AuditNode`/`AuditEdge` DAG on
that view. It returns **one artifact**: `{ reconciliation, outputs }`.

```
generate_audit(audit_id, date_from, date_to):
  raw  = SELECT * FROM extracted_transaction
         WHERE audit_id = audit_id
           AND tran_date BETWEEN date_from AND date_to      # the ONLY place range enters
  recon, txns = reconcile_pass(raw)      # §2.6: dedup, coverage, continuity,
                                         # transfer-netting → canonical view + summary
  graph = topo_sort(nodes, edges)        # reject cycles at save time
  memo = {}
  for node in graph:
    memo[node] = eval_node(node, memo, txns, recon)
  return { reconciliation: recon,        # innate audit output, always present
           outputs: [memo[n] for n in nodes if n.kind == OUTPUT] }
```

If the user has drawn no report graph yet, the audit still generates — it returns
the `reconciliation` summary alone (the default reconciled report). The card graph
*adds* custom calculations on top; it is never a prerequisite for reconciliation.

- `eval_node(TXN_GROUP)` → filter `txns` by the selector → a `TxnSet`.
- `eval_node(AGGREGATE)` → reduce a `TxnSet` to a scalar.
- `eval_node(OPERATION)` → apply the math op to scalar inputs (Decimal, banker's
  rounding; DIV-by-zero → `null` + node warning).
- `eval_node(RECONCILE)` → expose fields from the pre-pass `recon` result
  (opening/closing, Σdebit/Σcredit, coverage%, gaps, internal-transfer total) as a
  pinnable card. This node only *surfaces* the reconciliation on the canvas; the
  reconciliation itself always runs, with or without the node.
- `eval_node(OUTPUT)` → formatted report line.

Properties this buys us:
- **Date-range change = pure re-eval** over the cache. p50 well under 100 ms for a
  few-thousand-row month; cacheable by `(report_version, from, to, txn_maxid)`.
- **Deterministic & explainable**: every OUTPUT can emit its provenance
  (contributing transaction ids) → drill-down + trustworthy audit trail.
- **Report definitions are reusable templates**: a "monthly personal audit"
  graph can be cloned across audits/months.

---

## 4. Audit lifecycle state machine

```
DRAFT ──add sources (n, mixed) + range──▶ EXTRACTING ──all sources READY──▶ EXTRACTED
  ▲                                           │ (per-source Temporal workflows)
  │                                           ▼
  └───────────────────────────────────────  FAILED (a source hard-fails; retry per source)

EXTRACTED ──generate(range)──▶ GENERATED  ──edit range / add source / edit cards──▶ (re-generate, stays GENERATED)
                              (reconciled report = reconciliation summary + card outputs)
```
- **Multi-source from initiation**: an audit accepts any number of sources of any
  supported format (bank PDF, UPI CSV/XLSX, …); they extract **independently** (one
  workflow each) so one bad file doesn't block the audit.
- **`generate(range)` is the core transition** — it runs the reconcile pre-pass +
  report DAG and yields the reconciled report. The date range is what triggers it.
- Range edits, added sources, and card edits never leave `GENERATED` — they
  **re-generate** (reconcile + eval over the cache), never re-extract.

---

## 5. API surface (FastAPI)

Base: `/api/v1`. All mutating routes are org/user-scoped (reuse existing auth).

### 5.1 Audit lifecycle
| Method | Path | Body / notes |
|--------|------|--------------|
| `POST` | `/audits` | `{subject_name*, subject_email?, subject_phone?}` → `{id: "AUD-…"}` |
| `GET` | `/audits/{id}` | full audit incl. status, range, doc summaries |
| `PATCH` | `/audits/{id}/range` | `{from, to}` → **triggers audit generation** (reconcile pre-pass + report), returns the reconciled report; never re-extracts |
| `GET` | `/audits` | list/paginate |

### 5.2 Documents (streamed upload, mirrors KB route)
| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/audits/{id}/documents` | streamed `SpooledTemporaryFile` upload (reused), dispatches `AuditExtractionWorkflow`, returns `202` |
| `GET` | `/audits/{id}/documents` | list with `pages_extracted/pages_total` progress |
| `DELETE` | `/audits/{id}/documents/{docId}` | cascades transaction cleanup |
| `GET` | `/audits/{id}/documents/{docId}/meta` | DocumentMeta (kv + freeform) |

### 5.3 Transactions
| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/audits/{id}/transactions` | filter by date/channel/identifier/label/account; `view=deduped\|raw` toggles overlap-duplicate rows; server-side paging for the data grid |
| `PATCH` | `/audits/{id}/transactions/{txnId}` | `{user_label?, identifiers?, direction?}` — manual correction; sets `parse_source=MANUAL` |
| `POST` | `/audits/{id}/transactions/label` | bulk name/group by a selector |

### 5.4 Audit generation & report graph
The reconciled report is the audit's core output; `generate` always includes the
reconciliation summary, whether or not a card graph exists.
| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/audits/{id}/generate` | `{from?, to?}` (defaults to audit range) → **the reconciled report**: `{reconciliation, outputs}`. This is the one call the range change / added source triggers. |
| `GET/PUT` | `/audits/{id}/report` | load/save the card+edge graph (validated: acyclic, ports typed). Optional layer *on top of* reconciliation. |
| `POST` | `/audits/{id}/report/clone-template` | instantiate a saved template graph |
| `GET` | `/audits/{id}/export` | PDF/CSV/JSON of the generated reconciled audit |

### 5.5 Progress stream
`GET /audits/{id}/events` — SSE. Emits per-doc extraction progress
(`pages_extracted/pages_total`), status transitions, and re-eval completions, so
the UI shows a live loader exactly like the KB `list_documents` polling but push-based.

> **No separate reconciliation endpoint.** Reconciliation is produced by
> `POST /audits/{id}/generate` (and returned inside `PATCH /range`), because it is
> the audit's innate output, not an independent resource. The only related
> addition is a view toggle on the transactions list: `GET
> /audits/{id}/transactions?view=deduped|raw` controls whether overlap-duplicate
> (superseded) rows are shown.

---

## 6. Optimization / job pooling / multi-page (requirement callout)

| Concern | Mechanism (inherited or new) |
|---------|------------------------------|
| **Job pooling** | Docling **converter pool** (`extract_pool.py`, size=1/process, leased per batch → fair interleaving); **SLM pool** (bounded semaphore in front of one llama.cpp server, batched) |
| **Multi-page** | Paged extraction with `kb_document_pages` state, batch size + overlap, resume, blank-page synthetic rows, per-page progress |
| **Throughput scaling** | Worker **replicas** on the `audit-extraction` task queue (never raise the in-process converter count) |
| **Memory bounds** | one model set (shared) + `batch_size × render ceiling`; render downscale cap for pathological pages |
| **Cost** | regex-first structuring (SLM only on the messy tail); local SLM = no per-token API cost |
| **Re-eval cost** | pure DAG eval over cached rows, memoised by `(report_version, range, txn_maxid)` |
| **Reliability** | Temporal retry isolation per activity, heartbeats, idempotent upserts, per-doc failure isolation |

---

## 7. Resolved decisions (confirmed with product owner)
1. **Deployment — local, single-user.** Runs on this machine; org/project columns
   kept but a single local org. No hosted multi-tenant concerns in v1.
2. **Sources — multiple, mixed-format, merged per audit.** Bank statement PDFs +
   UPI-app CSV/XLSX exports (extensible). One audit reconciles across all of them;
   accounts partitioned, cross-account transfers netted (§2.6).
3. **SLM — optional toggle, default OFF.** Deterministic parsing ships v1; the SLM
   (`structurer_slm.enabled`, Qwen3-4B local, §2.3) is an additive "better parse"
   fallback for messy rows only. `NarrationStructurer` interface keeps it swappable.
4. **Auto-categorization — deferred to Phase 5.** v1 is manual naming/grouping via
   `user_label`; auto-categorization later fills the same field behind a toggle.
5. **"Month-wise" default range** — auto-seed range to the sources' own
   `period_from/to`, then let the user narrow to a calendar month. Default: yes.
6. **Vision/OCR** — sources are digital-text; router's vision path available but
   the pdfium fast path dominates. Default: vision opt-in.

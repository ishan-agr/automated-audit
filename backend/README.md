# Automated Audit — Backend

FastAPI + Temporal + Postgres backend for the month-wise expense-audit system.
See `../docs/` for the blueprint, LLD, SLM research, and tech stack.

## Status

**Phase 1 complete** — audit lifecycle + document-ingest spine with the
password gate wired in, running end-to-end (verified on the real 8-page Axis
reference PDF: upload → 8/8 pages extracted). Extraction runs on a **pypdf paged
baseline** behind an `Extractor` interface; the Docling + Temporal adapter (reusing
the magoneai KB engine) slots in later without changing the pipeline.

```
app/
  core/            config (env), crypto (Fernet secret box), db (SQLModel session)
  files/           hashing (streamed sha256), storage (LocalFileStore → S3 later)
  bank_profiles/   passwords.py — per-bank password-format registry + derivation
  extraction/      pdf_password.py (unlock gate), base.py (Extractor protocol),
                   pypdf_extractor.py (paged baseline), page_store.py (ExtractedPage),
                   pool.py (bounded job pool), pipeline.py (unlock→extract→persist)
  credentials/     service.py (candidate assembly + encrypted store/resolve),
                   models.py (BankCredential — opt-in, encrypted at rest)
  documents/       models.py, schemas.py, service.py (upload/unlock), routes.py
  audit/           models.py, ids.py (AUD-XXXXXX), schemas.py, service.py, routes.py
  main.py          FastAPI app factory
tests/             unlock, bank derivation, credential round-trips, pool bounds,
                   full ingest API (plain/encrypted/locked→unlock/dedupe/multi-pw)
```

## API (v1)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/audits` | create audit (`subject_name` required) → `AUD-XXXXXX` |
| GET | `/api/v1/audits` · `/{id}` | list / fetch |
| PATCH | `/api/v1/audits/{id}/range` | set date range (will trigger generate in P2.5) |
| POST | `/api/v1/audits/{id}/documents` | streamed upload → dedupe → password gate → extract |
| POST | `/api/v1/audits/{id}/documents/{doc}/unlock` | supply a password for a LOCKED doc (opt-in save) |
| GET | `/api/v1/audits/{id}/documents` · `/{doc}` | list / fetch with `pages_extracted/total` |

Run locally: `.venv\Scripts\python.exe -m uvicorn app.main:app --reload` then open `/docs`.

## The password gate (why it exists)

Bank/UPI statement PDFs are often encrypted, and **different documents in one
audit have different passwords** because **each bank uses its own password
format**. The gate:

1. detects encryption (`is_encrypted`),
2. assembles ordered candidate passwords — *typed for this upload* → *saved
   literal for this bank* → *derived from the bank's known format(s) + saved
   personal inputs* (`credentials.service.build_candidates`),
3. unlocks and returns an **un-encrypted** byte stream so Docling/pdfium never
   deal with encryption (`extraction.pdf_password.unlock_pdf`),
4. if nothing works, raises `PdfPasswordRequired` so the API can ask the user.

**Storing a password against a bank is opt-in and encrypted at rest** (Fernet via
`AUDIT_SECRET_KEY`). You can save either a literal password or the personal inputs
(name/DOB/PAN…) to *derive* it next time — different banks, different formats,
entered once. Nothing is stored unless the user opts in and
`AUDIT_ALLOW_CREDENTIAL_STORAGE` is on.

> Bank format templates are **common-but-not-authoritative** (labelled
> `verify=true`) and are offered as *candidates*; the always-reliable path is a
> typed/saved literal password. SBI e-statements use a user-chosen password and
> have no derivable format by design.

## Setup

```powershell
cd backend
uv venv --python 3.13 .venv
uv pip install -e ".[dev]"

# generate a persistent key for at-rest credential encryption:
.venv\Scripts\python.exe -c "from app.core.crypto import generate_key; print(generate_key())"
# then set it (PowerShell):  $env:AUDIT_SECRET_KEY = "<key>"
```

## Run tests / lint

```powershell
# PowerShell:  .\.venv\Scripts\Activate.ps1     (cmd.exe: .venv\Scripts\activate.bat)
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check app tests
```

## Config (env, prefix `AUDIT_`)

| Var | Default | Purpose |
|-----|---------|---------|
| `AUDIT_SECRET_KEY` | *(ephemeral dev key)* | Fernet key for encrypting stored credentials. Set it in real use. |
| `AUDIT_ALLOW_CREDENTIAL_STORAGE` | `true` | Global switch: if false, no password is ever persisted. |
| `AUDIT_DATABASE_URL` | `sqlite:///./automated_audit.db` | DB (Postgres in real deployments). |

# TRACE Platform — Codebase Structure

## Overview

This document defines the Python application codebase structure for the TRACE platform.
It separates application code (this repo) from infrastructure provisioning (managed in a separate infra repo).

---

## Repository Layout

```
trace-document-ai/
│
├── src/
│   └── trace_ai/                    # Main package
│       ├── __init__.py
│       ├── config.py                # Centralised settings — loaded from .env
│       ├── pipeline.py              # Main entry point — orchestrates all stages
│       │
│       ├── common/
│       │   ├── __init__.py
│       │   ├── gcs_client.py
│       │   └── logging_client.py
│       │
│       ├── ingestion/
│       │   ├── __init__.py
│       │   └── upload_handler.py
│       │
│       ├── extraction/
│       │   ├── __init__.py
│       │   ├── document_ai_client.py
│       │   ├── dlp_client.py
│       │   └── extraction_models.py
│       │
│       ├── intelligence/
│       │   ├── __init__.py
│       │   ├── gemini_client.py
│       │   ├── rag_client.py
│       │   ├── embeddings_client.py
│       │   └── prompts/
│       │       ├── company_information.txt
│       │       ├── pricing_extraction.txt
│       │       ├── merchant_details.txt
│       │       ├── processing_details.txt
│       │       ├── processor_info.txt
│       │       ├── owners_officers.txt
│       │       ├── banking_information.txt
│       │       └── llm_judge.txt
│       │
│       ├── normalization/
│       │   ├── __init__.py
│       │   ├── schema.py
│       │   └── normalizer.py
│       │
│       ├── validation/
│       │   ├── __init__.py
│       │   ├── llm_judge_client.py
│       │   ├── confidence_scorer.py
│       │   └── validation_models.py
│       │
│       ├── delivery/
│       │   ├── __init__.py
│       │   ├── gcs_writer.py
│       │   ├── storage_backend.py
│       │   ├── firestore_client.py
│       │   └── bigquery_client.py
│       │
│       ├── review_app/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── queue.py
│       │   │   └── review.py
│       │   └── templates/
│       │       ├── queue.html
│       │       └── review.html
│       │
│       └── knowledge_base/
│           ├── __init__.py
│           └── kb_indexer.py
│
├── tests/
│   ├── __init__.py
│   ├── ingestion/
│   ├── extraction/
│   ├── intelligence/
│   ├── normalization/
│   ├── validation/
│   └── delivery/
│
├── scripts/
│   └── create_index.py              # One-time Vector Search index provisioning
│
├── docs/
│   └── requirement/                 # All requirement and design documents
│
├── .env.example
├── .gitignore
├── Dockerfile
└── pyproject.toml
```

---

## Module Responsibilities

### `config.py` (package root)

Centralised settings loaded from `.env` via `python-dotenv`. Used by every module via `from trace_ai.config import config`.

---

### `pipeline.py` (package root)

Thin orchestrator that wires all 7 pipeline stages in sequence. Entry point for contract processing.

```
Stage 1 → extraction/document_ai_client.py   (OCR)
Stage 2 → extraction/dlp_client.py           (PII masking)
Stage 3 → intelligence/rag_client.py         (RAG context)
Stage 4 → intelligence/gemini_client.py      (LLM extraction)
Stage 5 → normalization/normalizer.py        (schema mapping)
Stage 6 → validation/llm_judge_client.py     (quality scoring)
Stage 7 → delivery/gcs_writer.py             (output)
        → delivery/storage_backend.py       (audit — every stage, routes to Firestore or BigQuery)
```

---

### `common/`

Shared utilities used across all modules.

| File | Responsibility |
|------|----------------|
| `gcs_client.py` | Shared helper for GCS upload, download, upload_json, list_blobs across all zones. |
| `logging_client.py` | Structured JSON logging wrapper emitting to Cloud Logging with consistent fields — stage, contract_id, severity. |

GCP Services used: `GCS`, `Cloud Logging`

---

### `ingestion/`

Handles contract file validation and upload to GCS Raw Zone. Called separately before the pipeline.

| File | Responsibility |
|------|----------------|
| `upload_handler.py` | Validates file type (PDF only), size (≤50MB). Uploads to `gs://<GCS_BUCKET>/<GCS_RAW_PREFIX>/contracts/`. Returns contract_id and GCS URI. |

GCP Services used: `Google Cloud Storage`

---

### `extraction/`

Calls Document AI and Cloud DLP to extract and sanitize contract content.

| File | Responsibility |
|------|----------------|
| `document_ai_client.py` | Submits PDF to Document AI Form Parser with `enable_native_pdf_parsing=True`. Handles both digital and scanned PDFs. Returns full text, key-value pairs, and tables. |
| `dlp_client.py` | Calls Cloud DLP to detect and mask PII (SSN, DOB, routing numbers, etc.) before passing to Gemini. |
| `extraction_models.py` | Pydantic models for OCR output — ExtractionResult, KeyValuePair, ExtractedTable. |

GCP Services used: `Document AI`, `Cloud DLP`

---

### `intelligence/`

Calls Vertex AI Gemini with RAG-grounded context to extract contract intelligence.

| File | Responsibility |
|------|----------------|
| `gemini_client.py` | Runs all 7 extraction prompts against masked contract text + RAG context. Returns raw extracted dict. |
| `rag_client.py` | Embeds contract text, queries Vector Search, fetches matching chunks from GCS KB bucket. |
| `embeddings_client.py` | Calls Vertex AI Embeddings API (text-embedding-004). Used by rag_client.py and kb_indexer.py. |

Prompt files (all in `prompts/`):

| File | Extracts |
|------|----------|
| `company_information.txt` | Legal name, address, contacts, HIC admin |
| `pricing_extraction.txt` | Billing model, card rates, recurring fees, Amex details |
| `merchant_details.txt` | Business type, ownership, tax ID, PCI compliance |
| `processing_details.txt` | Transaction method percentages, signature, website |
| `processor_info.txt` | MID, atlas token, sales rep, SDR, affiliate ID |
| `owners_officers.txt` | All owners/officers with PII fields (DOB, SSN last 4, DL last 4) |
| `banking_information.txt` | Bank name, routing number, account details |
| `llm_judge.txt` | Quality scoring prompt used by validation/llm_judge_client.py |

GCP Services used: `Vertex AI Gemini`, `Vertex AI Vector Search`, `Vertex AI Embeddings API`

---

### `normalization/`

Maps raw Gemini output into the canonical ContractRecord schema.

| File | Responsibility |
|------|----------------|
| `schema.py` | Full Pydantic schema — ContractRecord, ProcessorInfo, CompanyInformation, MerchantDetails, CreditCardPricing, ProcessingDetails, OwnerOfficer, BankingInformation, and all supporting models. |
| `normalizer.py` | Maps raw Gemini JSON dict to ContractRecord. Handles BillingModel, SettlementType, FeeFrequency coercion and missing field defaults. |

GCP Services used: None (pure Python logic)

---

### `validation/`

Validates extraction quality using a secondary Gemini call and routes based on confidence score.

| File | Responsibility |
|------|----------------|
| `llm_judge_client.py` | Submits masked contract text + extracted JSON to Gemini using llm_judge.txt prompt. Returns ValidationResult with per-section scores. |
| `confidence_scorer.py` | Applies threshold logic: ≥0.85 → Approved, 0.60–0.85 → Review Required, <0.60 → Rejected. |
| `validation_models.py` | Pydantic models — ValidationResult, FieldScores. |

GCP Services used: `Vertex AI Gemini`

---

### `delivery/`

Writes approved contract JSON to GCS and records all audit/state events to the configured operational store.

| File | Responsibility |
|------|----------------|
| `gcs_writer.py` | Serializes ContractRecord to JSON and writes to `gs://<GCS_BUCKET>/<GCS_CURATED_PREFIX>/contracts/`. |
| `storage_backend.py` | Factory — re-exports the correct backend functions based on `STORAGE_BACKEND` env var. |
| `firestore_client.py` | Firestore implementation — upsert_contract, write_audit_event, get_contract, get_pending_review, update_review_decision. |
| `bigquery_client.py` | BigQuery implementation — same 5-function interface as firestore_client.py. Uses MERGE for upserts, streaming insert for audit events. |

GCP Services used: `GCS Curated Zone`, `Firestore` or `BigQuery` (configured via `STORAGE_BACKEND`)

---

### `review_app/`

FastAPI + Jinja2 web application for human-in-the-loop (HITL) contract review. Deployed on Cloud Run.

| File | Responsibility |
|------|----------------|
| `main.py` | FastAPI app entry point. Mounts queue and review routers. Root `/` redirects to `/queue`. |
| `routes/queue.py` | `GET /queue` — fetches Review Required contracts via storage_backend, renders queue.html. |
| `routes/review.py` | `GET /review/{id}` — renders contract detail. `POST /review/{id}` — records approve/reject decision, writes to GCS if approved. |
| `templates/queue.html` | Reviewer queue UI — lists pending contracts with confidence score badges. |
| `templates/review.html` | Contract detail UI — all sections displayed, approve/reject form at bottom. |

GCP Services used: `Firestore` or `BigQuery` (via storage_backend), `GCS Curated Zone`

---

### `knowledge_base/`

Indexes reference documents into Vertex AI Vector Search for RAG grounding.

| File | Responsibility |
|------|----------------|
| `kb_indexer.py` | Reads documents from `gs://<GCS_BUCKET>/<GCS_KB_PREFIX>/documents/`. Chunks (500 chars, 50 overlap), embeds, stores chunks to `gs://<GCS_BUCKET>/<GCS_KB_PREFIX>/chunks/`, upserts vectors to Vector Search in batches of 100. |

GCP Services used: `GCS KB Bucket`, `Vertex AI Embeddings API`, `Vertex AI Vector Search`

---

### `scripts/`

Standalone one-time maintenance scripts. Not part of the application package.

| File | Responsibility |
|------|----------------|
| `create_index.py` | Creates and deploys Vertex AI Vector Search index and endpoint. Run once before kb_indexer. Prints index/endpoint IDs to add to .env. |

---

## Application vs Infrastructure Split

### Application Code (This Repo)

Everything under `src/trace_ai/` — Python modules implementing business logic via GCP service APIs.

### Infrastructure Repo (Separate)

| Component | Tool | Why Infra |
|---|---|---|
| GCS bucket creation (single bucket with raw / processing / curated / kb prefixes) | Terraform | Resource provisioning |
| Eventarc trigger configuration | Terraform | GCP event binding |
| Document AI processor creation | Terraform | One-time GCP resource |
| Vertex AI Vector Search index creation | Terraform | Index provisioning |
| Cloud Run service deployment | Terraform + Dockerfile | Service deployment config |
| Firestore database + collection setup | Terraform | DB provisioning |
| IAM roles & service account bindings | Terraform | Security configuration |
| VPC Service Controls perimeter | Terraform | Network security |
| Cloud KMS key creation (CMEK) | Terraform | Encryption key management |
| Cloud Monitoring alert policies | Terraform | Observability configuration |

---

## Key Dependencies (pyproject.toml)

```
google-cloud-storage==2.18.2
google-cloud-documentai==2.31.0
google-cloud-dlp==3.22.0
google-cloud-aiplatform==1.71.1   # Vector Search + Embeddings
google-genai>=1.0.0               # Gemini (gemini_client, llm_judge_client)
google-cloud-firestore==2.19.0
google-cloud-bigquery==3.27.0
google-cloud-logging==3.11.3
fastapi==0.115.6
uvicorn==0.32.1
jinja2==3.1.4
python-multipart==0.0.20
pydantic==2.10.3
python-dotenv==1.0.1
```

---

## Environment Variables (.env)

```bash
# GCP
GCP_PROJECT_ID=
GCP_REGION=

# GCS — single bucket, all data separated by prefix
GCS_BUCKET=
GCS_RAW_PREFIX=raw
GCS_PROCESSING_PREFIX=processing
GCS_CURATED_PREFIX=curated
GCS_KB_PREFIX=kb

# Document AI
DOCUMENT_AI_FORM_PROCESSOR_ID=
DOCUMENT_AI_LOCATION=us

# Vertex AI
VERTEX_GEMINI_MODEL=gemini-1.5-pro
VERTEX_EMBEDDING_MODEL=text-embedding-004
VERTEX_VECTOR_SEARCH_INDEX_ID=
VERTEX_VECTOR_SEARCH_ENDPOINT_ID=
VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID=trace-kb-deployed

# Storage backend: "firestore" or "bigquery"
STORAGE_BACKEND=firestore

# Firestore (used when STORAGE_BACKEND=firestore)
FIRESTORE_COLLECTION_CONTRACTS=contracts
FIRESTORE_COLLECTION_AUDIT=audit_events

# BigQuery (used when STORAGE_BACKEND=bigquery)
BIGQUERY_DATASET=trace_contracts

# Validation
CONFIDENCE_THRESHOLD_APPROVE=0.85
CONFIDENCE_THRESHOLD_REVIEW=0.60
```

---

## Data Flow Through Codebase

```
ingestion/upload_handler.py          (separate — uploads PDF to GCS raw)
        ↓
pipeline.py starts from GCS URI
        ↓
extraction/document_ai_client.py  →  extraction/dlp_client.py
        ↓
intelligence/rag_client.py  +  intelligence/gemini_client.py  (7 prompts)
        ↓
normalization/normalizer.py  (maps to normalization/schema.py → ContractRecord)
        ↓
validation/llm_judge_client.py  →  validation/confidence_scorer.py
        ↓
    ┌───────────────────────────────┐
    │  score ≥ 0.85 (Approved)      │──→  delivery/gcs_writer.py
    │  score 0.60–0.85 (Review)     │──→  review_app/routes/queue.py
    │  score < 0.60 (Rejected)      │──→  logged, manual intervention
    └───────────────────────────────┘
        ↓ (all paths)
    delivery/storage_backend.py    (audit event written at every stage — Firestore or BigQuery)
```

---

## Run Commands

```bash
# Install package in editable mode
pip install -e .

# Create Vector Search index (one-time, ~30-60 min)
python scripts/create_index.py

# Upload RAG seed documents to GCS KB bucket under documents/ then index
python -m trace_ai.knowledge_base.kb_indexer

# Upload a contract PDF and process it
python -m trace_ai.pipeline --local-pdf /path/to/contract.pdf

# Process a PDF already in GCS
python -m trace_ai.pipeline --gcs-uri gs://<GCS_BUCKET>/raw/contracts/CNT-XXX/contract.pdf --contract-id CNT-XXX

# Start HITL review app
uvicorn trace_ai.review_app.main:app --reload --port 8080
```

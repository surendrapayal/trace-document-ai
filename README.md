# TRACE — Contract Intelligence Platform

AI-powered pipeline for automated extraction, normalization, and validation of merchant processing contracts using GCP.

---

## Overview

TRACE ingests contract PDFs, extracts structured data using Document AI + Vertex AI Gemini, validates extraction quality with an LLM-as-a-Judge, and routes contracts to either auto-approval or a human review queue.

**Pipeline stages:**
```
Upload PDF → Document AI OCR → Cloud DLP (PII masking) → RAG context (Vector Search)
  → Gemini extraction (7 prompts) → Normalize (Pydantic) → LLM Judge → Route
      ├── score ≥ 0.85  → Approved   → GCS Curated Zone → Webhook (if enabled)
      ├── score 0.60–0.85 → Review Required → FastAPI review app → Webhook on approval
      └── score < 0.60  → Rejected   → logged, manual intervention
```

---

## Prerequisites

- Python 3.13+
- GCP project with the following APIs enabled:
  - Cloud Storage
  - Document AI
  - Cloud DLP
  - Vertex AI
  - Firestore (if using `STORAGE_BACKEND=firestore`)
  - BigQuery (if using `STORAGE_BACKEND=bigquery`)
- [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) configured:
  ```bash
  gcloud auth application-default login
  ```
- Document AI Form Parser processor created manually in GCP console

---

## Setup

**1. Clone the repository**
```bash
git clone <repo-url>
cd trace-document-ai
```

**2. Create and activate a virtual environment**
```bash
# Create
python3.13 -m venv .venv

# Activate — macOS/Linux
source .venv/bin/activate

# Activate — Windows
.venv\Scripts\activate
```

Verify the correct Python is active:
```bash
python --version   # should print Python 3.13.x
```

**3. Install the package and all dependencies**
```bash
pip install --upgrade pip
pip install -e .
```

This installs all dependencies from `pyproject.toml` and registers the `trace-pipeline` CLI entry point.

**4. Configure environment**
```bash
cp .env.example .env
# Fill in all values in .env
```

Key values to fill in before proceeding:
- `GCP_PROJECT_ID`, `GCP_REGION`
- `GCS_BUCKET`
- `DOCUMENT_AI_FORM_PROCESSOR_ID`
- `STORAGE_BACKEND` (`firestore` or `bigquery`)

**5. Authenticate with GCP**
```bash
gcloud auth application-default login
gcloud config set project <GCP_PROJECT_ID>
```

**6. Create GCS bucket** (or via Terraform in infra repo)
```bash
gcloud storage buckets create gs://<GCS_BUCKET> --location=<GCP_REGION>
```

All data is stored inside this single bucket under separate prefixes:
```
gs://<GCS_BUCKET>/
    raw/contracts/<contract_id>/<file>.pdf
    processing/
    curated/contracts/<contract_id>/output.json
    kb/documents/
    kb/chunks/
```

**7. (BigQuery only) Create dataset and tables**

Skip this step if using `STORAGE_BACKEND=firestore`.
```bash
python scripts/create_bq_tables.py
```

**8. Create Vector Search index** (one-time, ~30–60 min)
```bash
python scripts/create_index.py
```
Copy the printed index ID, endpoint ID, and deployed index ID into your `.env`.

**9. Upload RAG seed documents and index them**

Upload the 4 Heartland knowledge base documents from `docs/requirement/RAG_KNOWLEDGE_BASE.md`
to your GCS KB bucket under the `documents/` prefix, then run:
```bash
python -m trace_ai.knowledge_base.kb_indexer
```

---

## Running the Pipeline

**Process a local PDF (upload + process in one command):**
```bash
python -m trace_ai.pipeline --local-pdf /path/to/contract.pdf
```

**Process a PDF already in GCS:**
```bash
python -m trace_ai.pipeline --gcs-uri gs://<GCS_RAW_BUCKET>/contracts/CNT-XXX/contract.pdf --contract-id CNT-XXX
```

**Via CLI entry point (after `pip install -e .`):**
```bash
trace-pipeline --local-pdf /path/to/contract.pdf
```

**Upload only (without processing):**
```python
from trace_ai.ingestion.upload_handler import upload_contract
result = upload_contract("/path/to/contract.pdf")
print(result)  # {"contract_id": "CNT-...", "gcs_uri": "gs://...", "file_size_bytes": ...}
```

---

## Running Individual Stages

Each stage can be run independently using `--stage`. Every stage writes its output to `--output` (JSON file) or prints to stdout if omitted, and reads its dependencies from `--input` / `--rag-input` / `--masked-text-input` / `--judge-input`.

**Stage 0 — Ingestion (upload only, no `--stage` flag):**
```bash
# Upload a single PDF — prints contract_id and GCS URI
python -m trace_ai.pipeline --stage ingest --local-pdf docs/contract/your_contract.pdf

# Upload all PDFs in a folder
python -m trace_ai.pipeline --stage ingest --local-pdf docs/contract/

# Save output to a file
python -m trace_ai.pipeline --stage ingest --local-pdf docs/contract/your_contract.pdf --output s0_ingest.json
python -m trace_ai.pipeline --stage ingest --local-pdf docs/contract/ --output s0_ingest.json

# Or upload + run full pipeline in one command
python -m trace_ai.pipeline --local-pdf docs/contract/your_contract.pdf
```

```bash
# Stage 1 — OCR
python -m trace_ai.pipeline --stage ocr \
  --gcs-uri gs://<GCS_RAW_BUCKET>/contracts/CNT-XXX/contract.pdf \
  --contract-id CNT-XXX --output s1_ocr.json

# Stage 2 — DLP masking
python -m trace_ai.pipeline --stage dlp \
  --contract-id CNT-XXX --input s1_ocr.json --output s2_dlp.json

# Stage 3 — RAG retrieval
python -m trace_ai.pipeline --stage rag \
  --contract-id CNT-XXX --input s2_dlp.json --output s3_rag.json

# Stage 4 — Gemini extraction
python -m trace_ai.pipeline --stage extract \
  --contract-id CNT-XXX --input s2_dlp.json --rag-input s3_rag.json --output s4_extract.json

# Stage 5 — Normalization
python -m trace_ai.pipeline --stage normalize \
  --contract-id CNT-XXX --input s4_extract.json --output s5_normalize.json

# Stage 6 — LLM Judge
python -m trace_ai.pipeline --stage judge \
  --contract-id CNT-XXX --input s5_normalize.json --masked-text-input s2_dlp.json --output s6_judge.json

# Stage 7 — Delivery
python -m trace_ai.pipeline --stage deliver \
  --contract-id CNT-XXX --input s5_normalize.json --judge-input s6_judge.json
```

| Flag | Required for |
|---|---|
| `--stage` | Any individual stage run |
| `--gcs-uri` / `--local-pdf` | `ocr` stage only |
| `--input` | All stages except `ocr` |
| `--rag-input` | `extract` stage (RAG stage output) |
| `--masked-text-input` | `judge` stage (DLP stage output) |
| `--judge-input` | `deliver` stage (judge stage output) |
| `--output` | Optional on all stages — prints to stdout if omitted |

---

## Review App

Start the HITL review app for contracts routed to `Review Required`:
```bash
uvicorn trace_ai.review_app.main:app --reload --port 8080
```

Open [http://localhost:8080/queue](http://localhost:8080/queue) to see pending contracts.

**How it works**:
- `queue.html` and `review.html` are static Jinja2 templates in the repo -- never generated at runtime
- A contract appears in the queue only when Stage 7 writes it with `extraction_status = "Review Required"` (LLM Judge score 0.60--0.85)
- Reviewer opens `/queue` → clicks a contract → reviews all extracted fields → submits Approve or Reject
- Approved contracts are written to GCS curated zone and the decision is recorded in Firestore/BigQuery

---

## Third Party Integration

### Webhook (push)

TRACE pushes the approved `ContractRecord` JSON to a third party endpoint on every approval -- both auto-approval (pipeline) and human approval (review app).

```bash
# Enable in .env
WEBHOOK_ENABLED=true
WEBHOOK_URL=https://your-third-party.com/api/contracts
WEBHOOK_SECRET=your-bearer-token
```

- Disabled by default (`WEBHOOK_ENABLED=false`) -- implementation is in place
- 3 retries with exponential backoff (2s, 4s, 8s)
- Failure is logged as ERROR but never fails the pipeline
- **Testing locally**: set `WEBHOOK_URL=https://webhook.site/<your-id>` to inspect payloads in real time

### REST API (pull)

Third party systems can pull contract data on demand. Start the review app and use:

```bash
# Fetch a single contract
curl -H "X-API-Key: your-key" http://localhost:8080/api/v1/contracts/CNT-A3F9B2C1D4E5

# List contracts pending review
curl -H "X-API-Key: your-key" "http://localhost:8080/api/v1/contracts?status=Review Required"
```

| Endpoint | Description |
|---|---|
| `GET /api/v1/contracts/{contract_id}` | Fetch a single contract by ID |
| `GET /api/v1/contracts?status=Review Required` | List all contracts pending human review |

- Auth via `X-API-Key` header. Set `REST_API_KEY` in `.env`. Leave empty to disable auth (dev only).
- Interactive Swagger docs at [http://localhost:8080/docs](http://localhost:8080/docs)

---

## Knowledge Base

Re-index KB documents after adding new reference material to GCS:
```bash
python -m trace_ai.knowledge_base.kb_indexer
```

---

## Project Structure

```
trace-document-ai/
├── src/trace_ai/
│   ├── config.py               # All settings loaded from .env
│   ├── pipeline.py             # Main entry point
│   ├── common/                 # GCS client, logging
│   ├── ingestion/              # PDF upload to GCS raw zone
│   ├── extraction/             # Document AI OCR + Cloud DLP
│   ├── intelligence/           # Gemini extraction + RAG + embeddings
│   │   └── prompts/            # 7 extraction prompts + llm_judge.txt
│   ├── normalization/          # Pydantic ContractRecord schema + mapper
│   ├── validation/             # LLM judge + confidence scorer
│   ├── delivery/               # GCS writer + storage backend (Firestore or BigQuery) + webhook
│   ├── review_app/             # FastAPI + Jinja2 HITL review UI + REST API (/api/v1/contracts)
│   └── knowledge_base/         # Vector Search indexer
├── scripts/
│   └── create_index.py         # One-time Vector Search provisioning
├── tests/
├── docs/requirement/           # All design and requirement documents
├── .env.example
├── pyproject.toml
└── Dockerfile
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Orchestration | Python `pipeline.py` | Direct, debuggable -- no Cloud Workflows overhead for POC |
| LLM | Vertex AI Gemini 1.5 Pro | Best-in-class extraction, native GCP, JSON mode |
| RAG | Vertex AI Vector Search | Native GCP, no extra infra, integrates with Embeddings API |
| Operational store | Firestore (default) or BigQuery | Configurable via `STORAGE_BACKEND` -- Firestore for production, BigQuery for POC |
| PII masking | Cloud DLP | Masks SSN, DOB, routing numbers before any LLM call |
| Review UI | FastAPI + Jinja2 | Working UI with zero frontend build tooling |
| Third party push | Webhook (`httpx`, disabled by default) | Fire-and-forget with retry -- failure never blocks pipeline |
| Third party pull | REST API (`/api/v1/contracts`) | Standard pull pattern, secured with API key |

See `docs/requirement/` for full architecture, schema, and requirement documents.

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|---|---|
| `GCP_PROJECT_ID` | GCP project ID |
| `GCP_REGION` | GCP region e.g. `us-central1` |
| `DOCUMENT_AI_FORM_PROCESSOR_ID` | Form Parser processor ID from GCP console |
| `VERTEX_GEMINI_MODEL` | Default: `gemini-1.5-pro` |
| `VERTEX_VECTOR_SEARCH_INDEX_ID` | From `scripts/create_index.py` output |
| `VERTEX_VECTOR_SEARCH_ENDPOINT_ID` | From `scripts/create_index.py` output |
| `VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID` | From `scripts/create_index.py` output — default: `trace-kb-deployed` |
| `STORAGE_BACKEND` | `firestore` or `bigquery` — default: `firestore` |
| `FIRESTORE_COLLECTION_CONTRACTS` | Firestore collection name (when `STORAGE_BACKEND=firestore`) |
| `BIGQUERY_DATASET` | BigQuery dataset name (when `STORAGE_BACKEND=bigquery`) |
| `CONFIDENCE_THRESHOLD_APPROVE` | Default: `0.85` |
| `CONFIDENCE_THRESHOLD_REVIEW` | Default: `0.60` |
| `WEBHOOK_ENABLED` | `true` to push approved contracts to third party -- default: `false` |
| `WEBHOOK_URL` | Third party endpoint URL |
| `WEBHOOK_SECRET` | Bearer token sent in `Authorization` header |
| `WEBHOOK_TIMEOUT_SECONDS` | Per-request timeout -- default: `10` |
| `REST_API_KEY` | API key for `X-API-Key` header on `/api/v1/*` -- leave empty to disable auth |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` -- default: `INFO` |
| `LOG_TO_FILE` | `true` to write logs to a rotating file locally -- default: `false` |
| `LOG_FILE_PATH` | Log file path -- default: `logs/trace_ai.log` |

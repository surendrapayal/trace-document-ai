# TRACE — Contract Intelligence Platform

AI-powered pipeline for automated extraction, normalization, and validation of merchant processing contracts using GCP.

---

## Overview

TRACE ingests contract PDFs, extracts structured data using Document AI + Vertex AI Gemini, validates extraction quality with an LLM-as-a-Judge, and routes contracts to either auto-approval or a human review queue.

**Pipeline stages:**
```
Upload PDF → Document AI OCR → Cloud DLP (PII masking) → RAG context (Vector Search)
  → Gemini extraction (7 prompts) → Normalize (Pydantic) → LLM Judge → Route
      ├── score ≥ 0.85  → Approved   → GCS Curated Zone
      ├── score 0.60–0.85 → Review Required → FastAPI review app
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
  - Cloud Logging
- [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) configured:
  ```bash
  gcloud auth application-default login
  ```
- Document AI processor created manually in GCP console (OCR + Form Parser)

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
- `GCS_RAW_BUCKET`, `GCS_PROCESSING_BUCKET`, `GCS_CURATED_BUCKET`, `GCS_KB_BUCKET`
- `DOCUMENT_AI_PROCESSOR_ID`
- `STORAGE_BACKEND` (`firestore` or `bigquery`)

**5. Authenticate with GCP**
```bash
gcloud auth application-default login
gcloud config set project <GCP_PROJECT_ID>
```

**6. Create GCS buckets** (or via Terraform in infra repo)
```bash
gcloud storage buckets create gs://<GCS_RAW_BUCKET> --location=<GCP_REGION>
gcloud storage buckets create gs://<GCS_PROCESSING_BUCKET> --location=<GCP_REGION>
gcloud storage buckets create gs://<GCS_CURATED_BUCKET> --location=<GCP_REGION>
gcloud storage buckets create gs://<GCS_KB_BUCKET> --location=<GCP_REGION>
```

**7. (BigQuery only) Create dataset and tables**

Skip this step if using `STORAGE_BACKEND=firestore`.
```bash
bq mk --dataset <GCP_PROJECT_ID>:<BIGQUERY_DATASET>
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

## Review App

Start the HITL review app for contracts routed to `Review Required`:
```bash
uvicorn trace_ai.review_app.main:app --reload --port 8080
```

Open [http://localhost:8080/queue](http://localhost:8080/queue) to see pending contracts.

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
│   ├── delivery/               # GCS writer + storage backend (Firestore or BigQuery)
│   ├── review_app/             # FastAPI + Jinja2 HITL review UI
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
| Orchestration | Python `pipeline.py` | Direct, debuggable — no Cloud Workflows overhead for POC |
| LLM | Vertex AI Gemini 1.5 Pro | Best-in-class extraction, native GCP, JSON mode |
| RAG | Vertex AI Vector Search | Native GCP, no extra infra, integrates with Embeddings API |
| Operational store | Firestore (default) or BigQuery | Configurable via `STORAGE_BACKEND` — Firestore for production, BigQuery for POC |
| PII masking | Cloud DLP | Masks SSN, DOB, routing numbers before any LLM call |
| Review UI | FastAPI + Jinja2 | Working UI with zero frontend build tooling |

See `docs/requirement/` for full architecture, schema, and requirement documents.

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|---|---|
| `GCP_PROJECT_ID` | GCP project ID |
| `GCP_REGION` | GCP region e.g. `us-central1` |
| `DOCUMENT_AI_PROCESSOR_ID` | Processor ID from GCP console |
| `VERTEX_GEMINI_MODEL` | Default: `gemini-1.5-pro` |
| `VERTEX_VECTOR_SEARCH_INDEX_ID` | From `scripts/create_index.py` output |
| `VERTEX_VECTOR_SEARCH_ENDPOINT_ID` | From `scripts/create_index.py` output |
| `VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID` | From `scripts/create_index.py` output — default: `trace-kb-deployed` |
| `STORAGE_BACKEND` | `firestore` or `bigquery` — default: `firestore` |
| `FIRESTORE_COLLECTION_CONTRACTS` | Firestore collection name (when `STORAGE_BACKEND=firestore`) |
| `BIGQUERY_DATASET` | BigQuery dataset name (when `STORAGE_BACKEND=bigquery`) |
| `CONFIDENCE_THRESHOLD_APPROVE` | Default: `0.85` |
| `CONFIDENCE_THRESHOLD_REVIEW` | Default: `0.60` |

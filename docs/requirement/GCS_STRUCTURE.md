# TRACE Platform — GCS Bucket Structure

All pipeline data lives in a **single GCS bucket** (`GCS_BUCKET`) separated into four logical zones by prefix. There are no separate buckets — only one bucket with different folder prefixes acting as zones.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GCS_BUCKET` | _(required)_ | The single GCS bucket name. All zones live inside this bucket. e.g. `my-trace-ai-bucket` |
| `GCS_RAW_PREFIX` | `raw` | Prefix for the raw landing zone — uploaded PDFs land here |
| `GCS_PROCESSING_PREFIX` | `processing` | Prefix for OCR and DLP intermediate artifacts — not currently written by the pipeline (reserved for future use) |
| `GCS_CURATED_PREFIX` | `curated` | Prefix for final validated JSON outputs — written only for Approved contracts |
| `GCS_KB_PREFIX` | `kb` | Prefix for knowledge base documents and vector chunks used by RAG |

---

## Full Bucket Layout

```
gs://<GCS_BUCKET>/
│
├── raw/
│   └── contracts/
│       └── <contract_id>/
│           └── <filename>.pdf          ← uploaded by upload_handler.py (Stage 0)
│
├── processing/                         ← reserved prefix, not written by current pipeline
│
├── curated/
│   └── contracts/
│       └── <contract_id>/
│           └── output.json             ← written by gcs_writer.py (Stage 7, Approved only)
│
└── kb/
    ├── documents/
    │   └── <document_name>.txt         ← seed KB docs uploaded manually before indexing
    └── chunks/
        └── <chunk_id>.txt              ← text chunks written by kb_indexer.py
```

---

## Zone-by-Zone Explanation

### `raw/` — Landing Zone

**Env var**: `GCS_RAW_PREFIX` (default: `raw`)

**Written by**: `ingestion/upload_handler.py` (Stage 0)

**Path pattern**: `gs://<GCS_BUCKET>/raw/contracts/<contract_id>/<filename>.pdf`

**What lands here**: The original unmodified PDF uploaded by the user. This is the source of truth for the contract. Document AI reads the PDF directly from this path.

**Example**:
```
gs://my-trace-ai-bucket/raw/contracts/CNT-a1b2c3d4e5f6/CHETSHOESLLC.pdf
```

The `contract_id` subfolder isolates each contract so multiple files for the same contract can coexist without collision. The `source_pdf_uri` field on `ContractRecord` stores this exact GCS URI.

---

### `processing/` — Intermediate Zone

**Env var**: `GCS_PROCESSING_PREFIX` (default: `processing`)

**Written by**: Not currently written by the pipeline — reserved prefix.

**Purpose**: Intended for storing OCR artifacts (raw Document AI output) and DLP intermediate results between stages. Currently the pipeline passes these in-memory between stages rather than writing to GCS. This prefix is defined in `.env` for future use if intermediate persistence is needed (e.g. for debugging, resumable pipelines, or audit requirements).

---

### `curated/` — Output Zone

**Env var**: `GCS_CURATED_PREFIX` (default: `curated`)

**Written by**: `delivery/gcs_writer.py` (Stage 7) and `review_app/routes/review.py` (human approval)

**Path pattern**: `gs://<GCS_BUCKET>/curated/contracts/<contract_id>/output.json`

**What lands here**: The final validated `ContractRecord` serialized as JSON. Only written for contracts with `extraction_status = Approved` — either auto-approved by the pipeline (score ≥ 0.85) or manually approved via the review app.

**Example**:
```
gs://my-trace-ai-bucket/curated/contracts/CNT-a1b2c3d4e5f6/output.json
```

The `curated_gcs_uri` field in Firestore/BigQuery stores this path so downstream consumers can fetch the output directly.

**Who reads it**: Business consumers via direct GCS access, or via the REST API (`GET /api/v1/contracts/{id}`) which reads from Firestore/BigQuery (not GCS directly).

---

### `kb/` — Knowledge Base Zone

**Env var**: `GCS_KB_PREFIX` (default: `kb`)

**Written by**:
- `kb/documents/` — uploaded manually before running `kb_indexer.py`
- `kb/chunks/` — written by `knowledge_base/kb_indexer.py`

**Read by**: `intelligence/rag_client.py` (Stage 3) — fetches chunk text files by chunk ID returned from Vector Search

#### `kb/documents/`

**Path pattern**: `gs://<GCS_BUCKET>/kb/documents/<document_name>.txt`

Seed reference documents for the knowledge base — Heartland fee schedules, processing guides, compliance playbooks. These are plain text files uploaded once before indexing. See `docs/requirement/RAG_KNOWLEDGE_BASE.md` for the list of documents.

#### `kb/chunks/`

**Path pattern**: `gs://<GCS_BUCKET>/kb/chunks/<chunk_id>.txt`

Text chunks produced by `kb_indexer.py`. Each document is split into 500-character chunks with 50-character overlap. Each chunk is stored as a separate `.txt` file named by its chunk ID. When Vector Search returns the top-5 nearest neighbor IDs for a contract query, `rag_client.py` downloads the corresponding chunk files from this prefix and concatenates them as `rag_context` for Gemini.

---

## How a Contract Moves Through the Zones

```
User uploads PDF
        │
        ▼
gs://<GCS_BUCKET>/raw/contracts/<contract_id>/<file>.pdf
        │
        │  Stage 1: Document AI reads PDF bytes from raw/
        │  Stage 2: DLP masks text in memory
        │  Stage 3: RAG reads chunks from kb/chunks/
        │  Stage 4: Gemini extracts from masked text + RAG context
        │  Stage 5: Normalizer builds ContractRecord
        │  Stage 6: LLM Judge scores extraction
        │
        ▼
  score ≥ 0.85 (Approved)
        │
        ▼
gs://<GCS_BUCKET>/curated/contracts/<contract_id>/output.json
```

Contracts that are `Review Required` or `Rejected` are written to Firestore/BigQuery only — no file is written to `curated/` until a human reviewer approves them via the review app.

---

## What Is NOT Stored in GCS

| Data | Where it lives |
|---|---|
| Contract metadata, status, scores | Firestore (`contracts` collection) or BigQuery (`contracts` table) |
| Audit events per pipeline stage | Firestore (`audit_events` collection) or BigQuery (`audit_events` table) |
| Vector embeddings | Vertex AI Vector Search index (not GCS) |
| OCR text, masked text, RAG context | In-memory only — passed between pipeline stages, never written to disk or GCS |

# TRACE Platform — GCS Bucket Structure

All pipeline data lives in a **single GCS bucket** (`GCS_BUCKET`) separated into four logical zones by prefix. There are no separate buckets — only one bucket with different folder prefixes acting as zones.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GCS_BUCKET` | _(required)_ | The single GCS bucket name. All zones live inside this bucket. e.g. `my-trace-ai-bucket` |
| `GCS_LANDING_PREFIX` | `landing` | Prefix for the landing zone — users drop PDFs here to trigger the pipeline via REST API |
| `GCS_RAW_PREFIX` | `raw` | Prefix for the raw zone — PDFs are moved here from landing before processing begins |
| `GCS_PROCESSING_PREFIX` | `processing` | Prefix for OCR and DLP intermediate artifacts |
| `GCS_CURATED_PREFIX` | `curated` | Prefix for final validated JSON outputs — written only for Approved contracts |
| `GCS_KB_PREFIX` | `kb` | Prefix for knowledge base documents and vector chunks used by RAG |

---

## Full Bucket Layout

```
gs://<GCS_BUCKET>/
│
├── landing/
│   └── <filename>.pdf                  ← user drops PDFs here; consumed by POST /api/v1/pipeline/trigger
│
├── raw/
│   └── contracts/
│       └── <contract_id>/
│           └── <filename>.pdf          ← moved from landing/ by upload_contract_from_gcs() (Stage 0)
│
├── processing/
│   └── contracts/
│       └── <contract_id>/
│           ├── ocr.json                ← written by document_ai_client.py (Stage 1)
│           └── masked.json             ← written by dlp_client.py (Stage 2)
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

### `landing/` — Inbox Zone

**Env var**: `GCS_LANDING_PREFIX` (default: `landing`)

**Written by**: Users / external systems — drop PDFs here manually or via `gsutil`/GCS client

**Path pattern**: `gs://<GCS_BUCKET>/landing/<filename>.pdf`

**What lands here**: Raw PDFs waiting to be picked up by the pipeline trigger. This is the inbox — files sit here until `POST /api/v1/pipeline/trigger` is called.

**Lifecycle**: When the trigger endpoint is called, each PDF in `landing/` is:
1. Downloaded to compute SHA256 hash and check for duplicates
2. Moved (copy + delete) to `raw/contracts/<contract_id>/<filename>.pdf`
3. Deleted from `landing/` — clean inbox pattern

If a file is a duplicate (same hash already processed), it is skipped and remains in `landing/` — it is not deleted. The trigger response includes a `skipped` list with the reason.

**Example**:
```
gs://my-trace-ai-bucket/landing/CHETSHOESLLC.pdf
```

---

### `raw/` — Raw Zone

**Env var**: `GCS_RAW_PREFIX` (default: `raw`)

**Written by**: `ingestion/upload_handler.py` — `upload_contract_from_gcs()` moves PDFs from `landing/` here; `upload_contract()` uploads local PDFs directly here

**Path pattern**: `gs://<GCS_BUCKET>/raw/contracts/<contract_id>/<filename>.pdf`

**What lands here**: The original unmodified PDF. This is the durable source of truth for the contract. Document AI reads the PDF directly from this path.

**Example**:
```
gs://my-trace-ai-bucket/raw/contracts/CNT-a1b2c3d4e5f6/CHETSHOESLLC.pdf
```

The `contract_id` subfolder isolates each contract so multiple files for the same contract can coexist without collision. The `source_pdf_uri` field on `ContractRecord` stores this exact GCS URI.

---

### `processing/` — Intermediate Zone

**Env var**: `GCS_PROCESSING_PREFIX` (default: `processing`)

**Written by**: `extraction/document_ai_client.py` (Stage 1) and `extraction/dlp_client.py` (Stage 2)

**Path patterns**:
```
gs://<GCS_BUCKET>/processing/contracts/<contract_id>/ocr.json
gs://<GCS_BUCKET>/processing/contracts/<contract_id>/masked.json
```

**What lands here**:

| File | Written by | Contents |
|---|---|---|
| `ocr.json` | `process_document_cached()` after Stage 1 | `full_text`, `key_value_pairs`, `tables`, `page_count` from Document AI |
| `masked.json` | `mask_pii_cached()` after Stage 2 | `masked_text`, `pii_types` after Cloud DLP masking |

**Skip-if-exists (cache) behaviour**: Before calling Document AI or Cloud DLP, the pipeline checks whether the output file already exists in GCS. If it does, the API call is skipped entirely and the cached result is loaded from GCS instead. This means:
- Re-running the pipeline for the same `contract_id` never calls Document AI or DLP again — no repeated API cost
- If the pipeline fails at Stage 3 or later, you can restart and Stages 1 and 2 are free
- The `cache_hit` flag is recorded in the audit event (`document_ai_complete` / `dlp_complete`) so you can see in the audit trail whether the API was called or the cache was used

**Example**:
```
gs://my-trace-ai-bucket/processing/contracts/CNT-a1b2c3d4e5f6/ocr.json
gs://my-trace-ai-bucket/processing/contracts/CNT-a1b2c3d4e5f6/masked.json
```

**Compliance value**: `masked.json` proves that PII was removed before any LLM call. The file exists as a durable artifact showing exactly what text Gemini received — with all PII replaced by mask characters.

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
User drops PDF into landing/
        │
        ▼
POST /api/v1/pipeline/trigger
        │
        ▼
gs://<GCS_BUCKET>/landing/<file>.pdf  →  move_blob()  →  gs://<GCS_BUCKET>/raw/contracts/<contract_id>/<file>.pdf
(deleted from landing/)                                   (contract_id auto-generated)
        │
        │  Stage 1: Document AI reads PDF bytes from raw/
        │           writes ocr.json to processing/
        │  Stage 2: DLP masks text, writes masked.json to processing/
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
| OCR text, masked text, RAG context | `processing/` in GCS (ocr.json, masked.json) for OCR and DLP. RAG context is in-memory only. |

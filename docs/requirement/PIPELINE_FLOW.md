# TRACE Pipeline Flow

Detailed stage-by-stage reference for the contract processing pipeline defined in `pipeline.py`.

---

## Overview

```
Local PDF / GCS URI
        │
        ▼
[Stage 0] Ingestion          upload_handler.py       → GCS raw zone
        │
        ▼
[Stage 1] Document AI OCR    document_ai_client.py   → ExtractionResult       CLI: --stage ocr
        │
        ▼
[Stage 2] DLP PII Masking    dlp_client.py           → masked_text, pii_types[]  CLI: --stage dlp
        │
        ▼
[Stage 3] RAG Retrieval      rag_client.py           → rag_context (string)   CLI: --stage rag
        │
        ▼
[Stage 4] Gemini Extraction  gemini_client.py        → raw_extracted (dict, 7 sections)  CLI: --stage extract
        │
        ▼
[Stage 5] Normalization      normalizer.py           → ContractRecord (Pydantic)  CLI: --stage normalize
        │
        ▼
[Stage 6] LLM Judge          llm_judge_client.py     → ValidationResult + extraction_status  CLI: --stage judge
        │
        ▼
[Stage 7] Delivery           gcs_writer.py + storage_backend.py               CLI: --stage deliver
              ├── Approved         → GCS curated zone + upsert_contract
              ├── Review Required  → upsert_contract (review queue)
              └── Rejected         → upsert_contract (logged)
```

Each stage from 1–7 can be run individually via `--stage`. See [Running Individual Stages](#running-individual-stages).

---

## Running Individual Stages

Pass `--stage <name>` to run a single stage. Each stage serializes its output to `--output` (JSON file) or stdout if omitted, and reads prior stage outputs via input flags.

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

**Input/output flag reference**:

| Stage | `--input` reads | Extra input flag | `--output` writes |
|---|---|---|---|
| `ocr` | — | `--gcs-uri` or `--local-pdf` | `full_text`, `key_value_pairs`, `tables`, `page_count` |
| `dlp` | OCR output | — | `masked_text`, `pii_types` |
| `rag` | DLP output | — | `rag_context` |
| `extract` | DLP output | `--rag-input` (RAG output) | 7-section extraction dict |
| `normalize` | extract output | — | full `ContractRecord` as JSON |
| `judge` | normalize output | `--masked-text-input` (DLP output) | `overall_confidence`, `verdict`, `field_scores`, `issues`, `critical_failures` |
| `deliver` | normalize output | `--judge-input` (judge output) | `contract_id`, `extraction_status`, `confidence_score`, `curated_gcs_uri`, `issues` |

`--output` is optional on every stage — omit it to print to stdout.

---

## Stage 0 — Ingestion

**Module**: `ingestion/upload_handler.py`  
**Triggered when**: `--local-pdf` flag is passed to `pipeline.py`; skipped when `--gcs-uri` is used directly.

**What it does**:
- Validates file exists, has `.pdf` extension, and is ≤ 50 MB
- Generates `contract_id` as `CNT-<12-char hex>` if not provided
- Uploads to `gs://<GCS_RAW_BUCKET>/contracts/<contract_id>/<filename>`

**Input**: local file path, optional `contract_id`  
**Output**: `{ contract_id, gcs_uri, file_size_bytes }`

---

## Stage 1 — Document AI OCR

**Module**: `extraction/document_ai_client.py`  
**GCP service**: Cloud Document AI (Form Parser processor)

**What it does**:
- Downloads the PDF bytes from GCS raw zone
- Submits to Document AI via `ProcessRequest` with `RawDocument(mime_type="application/pdf")`
- Extracts three things from the `Document` response:
  - `full_text` — the complete OCR'd text of the entire document (`document.text`)
  - `key_value_pairs` — form fields from each page (`page.form_fields`), each with `key`, `value`, and `confidence` score
  - `tables` — structured tables from each page (`page.tables`), with `headers` and `rows`

**Input**: `gcs_uri: str`, `contract_id: str`  
**Output**: `ExtractionResult`

```
ExtractionResult
├── full_text: str          # raw OCR text, all pages concatenated
├── key_value_pairs: list[KeyValuePair]
│   └── { key, value, confidence: float }
├── tables: list[ExtractedTable]
│   └── { headers: list[str], rows: list[list[str]] }
└── page_count: int
```

**Note**: Only `full_text` is passed to subsequent stages. `key_value_pairs` and `tables` are captured in the model but not forwarded — Gemini reads the raw text directly.

---

## Stage 2 — DLP PII Masking

**Module**: `extraction/dlp_client.py`  
**GCP service**: Cloud DLP (`projects/<id>/locations/global`)

**What it does**:
- Sends `full_text` to DLP `deidentify_content` — masks all matched PII spans
- Runs a second `inspect_content` call on the original text to collect the set of detected PII type names
- Returns the masked text and the list of detected type names

**PII types scanned** (hardcoded, applied when no inspect template is set):
`PERSON_NAME`, `DATE_OF_BIRTH`, `US_SOCIAL_SECURITY_NUMBER`, `US_DRIVERS_LICENSE_NUMBER`, `PHONE_NUMBER`, `EMAIL_ADDRESS`, `STREET_ADDRESS`, `US_BANK_ROUTING_MICR`, `FINANCIAL_ACCOUNT_NUMBER`

**Configuration** (all via env vars / `config.py`):

| Variable | Default | Description |
|---|---|---|
| `DLP_ENABLED` | `true` | Set to `false` to skip PII masking entirely — original text is passed through unchanged |
| `DLP_LOCATION` | `global` | DLP API location. `global` works everywhere; use a specific region (e.g. `us-central1`) for data residency requirements |
| `DLP_INSPECT_TEMPLATE_NAME` | `""` (inline) | Full resource name of a stored GCP inspect template. When set, overrides inline `info_types` and `min_likelihood` |
| `DLP_DEIDENTIFY_TEMPLATE_NAME` | `""` (inline) | Full resource name of a stored GCP deidentify template. When set, overrides inline `CharacterMaskConfig` |
| `DLP_MASK_CHARACTER` | `*` | Character used to replace masked spans |
| `DLP_NUMBER_TO_MASK` | `0` | Number of characters to mask; `0` masks the entire matched span |
| `DLP_MIN_LIKELIHOOD` | `LIKELY` | Minimum match confidence: `POSSIBLE_REGION`, `LIKELY`, `VERY_LIKELY` |

**Template vs inline behaviour**:
- If `DLP_INSPECT_TEMPLATE_NAME` is set, `inspect_config` is passed as `None` and `inspect_template_name` is used instead — the stored template controls info types and likelihood
- If `DLP_DEIDENTIFY_TEMPLATE_NAME` is set, `deidentify_config` is passed as `None` and `deidentify_template_name` is used instead — the stored template controls masking transformation
- Both can be set independently; mixing (e.g. stored inspect + inline deidentify) is supported
- Stored templates are managed in the GCP console or via the DLP API under `projects/<id>/locations/global/inspectTemplates/<id>` and `.../deidentifyTemplates/<id>`

**Input**: `full_text: str` from Stage 1  
**Output**: `(masked_text: str, pii_types: list[str])`

`masked_text` is what all downstream stages (RAG, Gemini, LLM Judge) receive — no raw PII ever reaches an LLM call.

---

## Stage 3 — RAG Context Retrieval

**Module**: `intelligence/rag_client.py`  
**GCP services**: Vertex AI Embeddings (`VERTEX_AI_LOCATION`), Vertex AI Vector Search (`VERTEX_VECTOR_SEARCH_LOCATION`)

**What it does**:
1. Takes the first 2000 characters of `masked_text` as the query
2. Embeds it using `embeddings_client.embed_single()` → `list[float]` (768 dimensions by default)
3. Queries the Vector Search index endpoint (`VERTEX_VECTOR_SEARCH_ENDPOINT_ID`) for `top_k=5` nearest neighbors
4. For each neighbor ID returned, downloads the corresponding chunk from `gs://<GCS_KB_BUCKET>/chunks/<id>.txt`
5. Joins all chunks with `\n\n---\n\n` as the separator

**Input**: `masked_text: str`  
**Output**: `rag_context: str` — concatenated KB text chunks, or `""` if no neighbors found

**KB structure**: The knowledge base bucket holds reference documents (Heartland processing rules, fee schedules, compliance requirements) pre-chunked and indexed by `kb_indexer.py`. These are plain text files, not PDFs.

---

## Stage 4 — Gemini Extraction

**Module**: `intelligence/gemini_client.py`  
**GCP service**: Vertex AI Gemini (`VERTEX_GEMINI_MODEL`, default `gemini-1.5-pro`)

**What it does**:
- Runs 7 sequential prompt calls, one per contract section
- Each prompt file is loaded from `intelligence/prompts/` and formatted with `{contract_text}` and `{rag_context}` placeholders
- Every call uses `GenerationConfig(temperature=0.0, response_mime_type="application/json")` — Gemini is forced to return valid JSON
- The raw response has any markdown code fences stripped before `json.loads()`

**The 7 prompts and their output keys**:

| Prompt file | Output key | What it extracts |
|---|---|---|
| `processor_info.txt` | `processor_info` | Processor name, sales rep, MID, Atlas token, affiliate ID |
| `company_information.txt` | `company_information` | Legal name, DBA, address, contacts, HIC admin |
| `merchant_details.txt` | `merchant_details` | Business type, ownership, tax ID, terminals, PCI status |
| `pricing_extraction.txt` | `credit_card_pricing` | Card rates, fees, billing model, Amex details, settlement type |
| `processing_details.txt` | `processing_details` | Card-present %, keyed %, B2B %, future delivery %, website flag |
| `owners_officers.txt` | `owners_officers` | List of owners/officers with ownership %, DOB, SSN last 4 |
| `banking_information.txt` | `banking_information` | Bank name, routing/account numbers, funding option |

**Input**: `masked_text: str`, `rag_context: str`  
**Output**: `raw_extracted: dict` with the 7 keys above

---

## Stage 5 — Normalization

**Module**: `normalization/normalizer.py`  
**Schema**: `normalization/schema.py`

**What it does**:
- Receives `raw_extracted` dict from Stage 4 plus `contract_id`
- Constructs a fully-typed `ContractRecord` Pydantic model
- Applies coercion logic for three enum fields that Gemini returns as free-text strings:

| Field | Coercion logic |
|---|---|
| `BillingModel` | Matches `"interchange plus"` / `"ic++"` → `IC++`; `"flat"` → `Flat Rate`; `"tiered"` → `Tiered`; else `Unknown` |
| `SettlementType` | Matches `"5 bps"` → `Monthly 5 bps`; `"0 bps"` → `Monthly 0 bps`; `"daily"` → `Daily`; else `Unknown` |
| `FeeFrequency` | Matches `"annual"` → `Annually`; `"occurrence"` / `"per "` → `Per Occurrence`; `"one"` / `"one-time"` → `One-Time`; default `Monthly` |

- `owners_officers` is a list — each item becomes an `OwnerOfficer` model
- `credit_card_pricing.card_rates` is a list — each item becomes a `CardPricingRate` model
- `confidence_score` and `extraction_status` are set to defaults (`0.0`, `"Pending"`) here; Stage 6 overwrites them
- `extracted_at` is set to `datetime.now(timezone.utc).isoformat()`

**Input**: `raw_extracted: dict`  
**Output**: `ContractRecord` (Pydantic model, all fields typed and validated)

---

## Stage 6 — LLM Judge Validation

**Modules**: `validation/llm_judge_client.py`, `validation/confidence_scorer.py`  
**GCP service**: Vertex AI Gemini (same model as Stage 4)

### LLM Judge call

**What it does**:
- Loads `intelligence/prompts/llm_judge.txt` and formats it with two inputs:
  - `{contract_text}` — the `masked_text` from Stage 2 (the source of truth)
  - `{extracted_json}` — `contract_record.model_dump_json()` from Stage 5 (what was extracted)
- Sends both to Gemini with `temperature=0.0, response_mime_type="application/json"`
- Gemini reads the original contract text and the extracted JSON side-by-side and scores how faithfully the extraction represents the source

**This is the LLM-as-a-Judge pattern**: a second independent Gemini call evaluates the first extraction, not a rule-based validator.

**Judge output parsed into `ValidationResult`**:

```
ValidationResult
├── overall_confidence: float       # 0.0–1.0
├── verdict: str                    # "Approved" / "Review Required" / "Rejected"
├── field_scores: FieldScores
│   ├── company_information: float
│   ├── merchant_details: float
│   ├── credit_card_pricing: float
│   ├── processing_details: float
│   ├── processor_info: float
│   ├── owners_officers: float
│   └── banking_information: float
├── issues: list[str]               # non-critical discrepancies
└── critical_failures: list[str]    # fields that failed completely
```

### Confidence routing (`confidence_scorer.py`)

| Score | Status | Action |
|---|---|---|
| `≥ CONFIDENCE_THRESHOLD_APPROVE` (default 0.85) | `Approved` | Written to GCS curated zone |
| `≥ CONFIDENCE_THRESHOLD_REVIEW` (default 0.60) | `Review Required` | Held in review queue |
| `< CONFIDENCE_THRESHOLD_REVIEW` | `Rejected` | Logged, manual intervention |

`contract_record.confidence_score` and `contract_record.extraction_status` are updated with the judge's results before delivery.

---

## Stage 7 — Delivery

**Modules**: `delivery/gcs_writer.py`, `delivery/storage_backend.py`

### GCS write (Approved only)

- Serializes `ContractRecord` to JSON via `model_dump_json(indent=2)`
- Writes to `gs://<GCS_CURATED_BUCKET>/contracts/<contract_id>/output.json`
- Returns the `curated_gcs_uri`

### Operational store (all statuses)

`upsert_contract(contract_record, curated_uri)` is called for every contract regardless of status. Backend is selected by `STORAGE_BACKEND`:

| Backend | Mechanism |
|---|---|
| `firestore` | `document.set(data, merge=True)` on `contracts/<contract_id>` |
| `bigquery` | `MERGE` statement on `contracts` table keyed by `contract_id` |

### Audit trail

`write_audit_event()` is called at every stage transition throughout the pipeline. Each event records `contract_id`, `stage`, `event`, `timestamp`, and optional metadata. These accumulate in Firestore (`audit_events` collection) or BigQuery (`audit_events` table).

---

## Data Flow Summary

```
PDF bytes
  └─[Document AI]──► full_text (raw OCR)
                          │
                    [Cloud DLP]──► masked_text  ──────────────────────────────┐
                                       │                                       │
                               [Embeddings API]                                │
                                       │                                       │
                               [Vector Search]──► top-5 chunk IDs             │
                                       │                                       │
                               [GCS KB bucket]──► rag_context                 │
                                       │                                       │
                               [Gemini × 7]──► raw_extracted dict             │
                                       │                                       │
                               [Normalizer]──► ContractRecord                 │
                                       │                                       │
                               [Gemini Judge]◄──────────────────────────────┘
                               (masked_text + extracted_json)
                                       │
                               [Confidence Router]──► extraction_status
                                       │
                               [GCS / Firestore / BigQuery]
```

---

## Audit Events Reference

| Stage | Event |
|---|---|
| `extraction` | `document_ai_started`, `document_ai_complete` |
| `extraction` | `dlp_started`, `dlp_complete` |
| `intelligence` | `rag_query_started`, `rag_query_complete` |
| `intelligence` | `gemini_extraction_started`, `gemini_extraction_complete` |
| `normalization` | `normalization_started`, `normalization_complete` |
| `validation` | `llm_judge_started`, `llm_judge_complete` |
| `delivery` | `written_to_curated`, `routed_to_review_queue`, `rejected` |

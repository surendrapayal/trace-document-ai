# TRACE Pipeline Flow

Detailed stage-by-stage reference for the contract processing pipeline defined in `pipeline.py`.

---

## Overview

```
GCS landing/ zone  (user drops PDFs here)
        │
        ▼
[Stage 0] Ingestion          upload_handler.py       → GCS raw zone  (via REST trigger or CLI)
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
              ├── Approved         → GCS curated zone + upsert_contract + Webhook (if enabled)
              ├── Review Required  → upsert_contract (review queue)
              └── Rejected         → upsert_contract (logged)
```

Each stage from 1–7 can be run individually via `--stage`. See [Running Individual Stages](#running-individual-stages).

---

## Running the Pipeline

**Trigger pipeline via REST API (recommended — landing zone pattern):**
```bash
# 1. Drop PDF(s) into GCS landing zone
gsutil cp /path/to/contract.pdf gs://<GCS_BUCKET>/landing/

# 2. Call trigger endpoint — scans landing/, moves PDFs to raw/, starts pipeline
curl -X POST http://localhost:8080/api/v1/pipeline/trigger \
  -H "X-API-Key: your-key"

# 3. Poll for result using contract_id from trigger response
curl -H "X-API-Key: your-key" http://localhost:8080/api/v1/contracts/CNT-A1B2C3D4E5F6
```

**Process a local PDF directly (CLI):**
```bash
python -m trace_ai.pipeline --local-pdf /path/to/contract.pdf
```

**Process all PDFs in a local folder:**
```bash
python -m trace_ai.pipeline --local-pdf /path/to/folder/
```

**Process a PDF already in GCS:**
```bash
python -m trace_ai.pipeline --gcs-uri gs://<GCS_BUCKET>/raw/contracts/CNT-XXX/contract.pdf --contract-id CNT-XXX
```

**Process all PDFs under a GCS prefix:**
```bash
python -m trace_ai.pipeline --gcs-uri gs://<GCS_BUCKET>/raw/contracts/
```

**Via CLI entry point (after `pip install -e .`):**
```bash
trace-pipeline --local-pdf /path/to/contract.pdf
```

---

## Running Individual Stages

Pass `--stage <name>` to run a single stage. Each stage serializes its output to `--output` (JSON file) or stdout if omitted, and reads prior stage outputs via input flags.

**Stage 0 — Ingestion** — use `--stage ingest` with `--local-pdf` or `--gcs-uri`. Accepts a single file or a folder:

```bash
# Upload a single local PDF
python -m trace_ai.pipeline --stage ingest --local-pdf docs/contract/your_contract.pdf

# Upload all PDFs in a local folder
python -m trace_ai.pipeline --stage ingest --local-pdf docs/contract/

# Move a single PDF from GCS landing/ to raw/
python -m trace_ai.pipeline --stage ingest --gcs-uri gs://<GCS_BUCKET>/landing/contract.pdf

# Move all PDFs in GCS landing/ to raw/
python -m trace_ai.pipeline --stage ingest --gcs-uri gs://<GCS_BUCKET>/landing/

# Save output to file
python -m trace_ai.pipeline --stage ingest --local-pdf docs/contract/your_contract.pdf --output s0_ingest.json
python -m trace_ai.pipeline --stage ingest --gcs-uri gs://<GCS_BUCKET>/landing/contract.pdf --output s0_ingest.json
```

**Single file output**: `{ contract_id, gcs_uri, file_size_bytes, file_hash }`  
**Folder output**: `{ uploaded: [ { contract_id, gcs_uri, file_size_bytes, file_hash }, ... ], failed: [...], total: N }`

- `--local-pdf` uploads from local disk directly to `raw/` via `upload_contract()`
- `--gcs-uri` moves from `landing/` to `raw/` via `upload_contract_from_gcs()` — same function used by the REST trigger endpoint

```bash
# Stage 1 — OCR (use gcs_uri and contract_id from Stage 0 output above)
python -m trace_ai.pipeline --stage ocr \
  --gcs-uri gs://<GCS_BUCKET>/raw/contracts/CNT-XXX/contract.pdf \
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
| `ingest` | — | `--local-pdf` or `--gcs-uri` | `contract_id`, `gcs_uri`, `file_size_bytes`, `file_hash` |
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
**Triggered by**: `POST /api/v1/pipeline/trigger` (landing zone pattern), `--local-pdf` CLI flag, or `--gcs-uri` CLI flag pointing at `landing/`.

**Two ingestion paths**:

| Path | Function | Source |
|---|---|---|
| Landing zone (REST trigger or CLI `--gcs-uri`) | `upload_contract_from_gcs(landing_blob)` | PDF already in `gs://<bucket>/landing/` |
| Local file (CLI `--local-pdf`) | `upload_contract(local_path)` | PDF on local disk |

**`upload_contract_from_gcs()` — landing zone path**:
- Downloads PDF bytes from `landing/` to compute SHA256 hash
- Checks for duplicates via `get_contract_by_hash()` when `DUPLICATE_CHECK_ENABLED=true`
- Generates `contract_id` as `CNT-<12-char hex>`
- Moves blob: copies to `raw/contracts/<contract_id>/<filename>.pdf`, then deletes from `landing/`
- Returns `{ contract_id, gcs_uri, file_size_bytes, file_hash }`
- If duplicate detected: raises `ValueError`, blob is NOT deleted from `landing/`

**`upload_contract()` — local file path**:
- Validates file exists, has `.pdf` extension, and is ≤ 50 MB
- Computes SHA256 `file_hash` of the PDF bytes
- When `DUPLICATE_CHECK_ENABLED=true` — queries `get_contract_by_hash()` and raises `ValueError` if the file was already processed
- Generates `contract_id` as `CNT-<12-char hex>` if not provided
- Uploads to `gs://<GCS_BUCKET>/<GCS_RAW_PREFIX>/contracts/<contract_id>/<filename>`

**Folder support** (CLI only): `--local-pdf folder/` uploads all `*.pdf` files sequentially. Each file runs independently — failures are captured per-file and the batch continues.

**Duplicate behaviour**:

| `DUPLICATE_CHECK_ENABLED` | Duplicate file | Behaviour |
|---|---|---|
| `true` (default) | Same file re-submitted | Raises `ValueError` with existing `contract_id` — upload blocked, file stays in `landing/` |
| `false` | Same file re-submitted | Proceeds — new `contract_id` generated, file reprocessed |

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
**GCP services**: Vertex AI Embeddings (`VERTEX_EMBEDDING_LOCATION`), Vertex AI Vector Search (`VERTEX_VECTOR_SEARCH_LOCATION`)

**What it does**:
1. Takes the first 2000 characters of `masked_text` as the query
2. Embeds it using `embeddings_client.embed_single()` → `list[float]` (768 dimensions by default)
3. Queries the Vector Search index endpoint (`VERTEX_VECTOR_SEARCH_ENDPOINT_ID`) for `top_k=5` nearest neighbors
4. For each neighbor ID returned, downloads the corresponding chunk from `gs://<GCS_BUCKET>/<GCS_KB_PREFIX>/chunks/<id>.txt`
5. Joins all chunks with `\n\n---\n\n` as the separator

**Input**: `masked_text: str`  
**Output**: `rag_context: str` — concatenated KB text chunks, or `""` if no neighbors found

**KB structure**: The knowledge base bucket holds reference documents pre-chunked and indexed by `kb_indexer.py`. Stored under `gs://<GCS_BUCKET>/<GCS_KB_PREFIX>/documents/` and `gs://<GCS_BUCKET>/<GCS_KB_PREFIX>/chunks/`. These are plain text files, not PDFs.

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

The two thresholds divide the 0.0–1.0 score range into three zones:

```
0.0 ──────────────────────────────────────────────────────── 1.0

│←────── Rejected ──────→│←── Review Required ──→│←─ Approved ─→│
0.0                    REVIEW                  APPROVE          1.0
                       (0.60)                  (0.85)
```

| Score range | `extraction_status` | Action |
|---|---|---|
| `≥ CONFIDENCE_THRESHOLD_APPROVE` (default `0.85`) | `Approved` | Written directly to GCS curated zone — no human review needed |
| `≥ CONFIDENCE_THRESHOLD_REVIEW` and `< APPROVE` (default `0.60–0.85`) | `Review Required` | Written to Firestore/BigQuery — appears in `/queue` for human review |
| `< CONFIDENCE_THRESHOLD_REVIEW` (default `< 0.60`) | `Rejected` | Logged only — too low quality even for human review to salvage reliably |

`contract_record.confidence_score` and `contract_record.extraction_status` are updated with the judge's results before delivery. `contract_record.field_scores` and `contract_record.judge_issues` are also stamped here and persisted to Firestore/BigQuery — making them available to `review.html` when a contract is loaded for human review.

---

### What `overall_confidence` means

The score is not rule-based. It is Gemini's own assessment of how faithfully the
extracted JSON represents the source contract text. A score of `0.91` means Gemini
is 91% confident the extraction is accurate. The judge scores all 7 sections
independently via `field_scores` and derives `overall_confidence` from those.

**What causes the score to drop:**

| Issue | Impact |
|---|---|
| Missing required field (`bank_name`, `merchant_legal_name`) | Large drop |
| Wrong billing model (`Flat Rate` extracted as `IC++`) | Large drop |
| Wrong fee amounts or missing fees from the recurring fees table | Moderate drop |
| Owner/officer section incomplete or missing an owner | Moderate drop |
| Minor formatting differences (`0.910%` vs `0.91%`) | Small or no drop |
| PII fields null because DLP masked them | No drop — judge knows DLP masking is expected |
| `$0.00` fees missing (waived fees not extracted) | Moderate drop |

---

### Best Practice Threshold Values

There is no universal answer — it depends on risk tolerance and review capacity.

| Scenario | `APPROVE` | `REVIEW` | Reasoning |
|---|---|---|---|
| Development / POC | `1.0` | `0.0` | Forces every contract into review queue — lets you manually verify all extractions and calibrate |
| High-trust production (default) | `0.85` | `0.60` | Good balance — auto-approves clean extractions, catches genuinely bad ones |
| High-volume, lower-risk | `0.80` | `0.55` | Approves more automatically, smaller review queue |
| Regulated / financial compliance | `0.90` | `0.70` | Stricter — fewer auto-approvals, larger review queue |
| Zero tolerance for errors | `0.95` | `0.80` | Almost everything goes to human review |

**Practical guidance:**

- Start with `CONFIDENCE_THRESHOLD_APPROVE=1.0` and `CONFIDENCE_THRESHOLD_REVIEW=0.0` during
  development — every contract hits the review queue so you can see all extractions and calibrate
- After processing 20–30 real contracts, look at the score distribution. If most contracts
  score 0.88–0.95, set `APPROVE=0.85` to auto-approve the bulk and only review edge cases
- Never set `REVIEW` below `0.50` in production — below that, the extraction is so poor
  that human review is unlikely to salvage it reliably
- The gap between `REVIEW` and `APPROVE` (the review band) should be wide enough to catch
  genuinely ambiguous cases — a gap of `0.20–0.25` is typical
- Threshold changes are **not retroactive** — existing records in Firestore/BigQuery keep
  their current `extraction_status`. Only newly processed contracts use the new thresholds

**For Heartland contracts specifically** — the 4 KB documents are well-structured and
Heartland contracts follow a fixed 4-page format, so scores tend to cluster high
(`0.85–0.95`) for clean digital PDFs. The defaults of `0.85` / `0.60` are appropriate
for production once the KB is properly indexed.

---

## Stage 7 — Delivery

**Modules**: `delivery/gcs_writer.py`, `delivery/storage_backend.py`, `delivery/webhook_client.py`

### GCS write (Approved only)

- Serializes `ContractRecord` to JSON via `model_dump_json(indent=2)`
- Writes to `gs://<GCS_BUCKET>/<GCS_CURATED_PREFIX>/contracts/<contract_id>/output.json`
- Returns the `curated_gcs_uri`

### Webhook push (Approved only, if enabled)

After GCS write, `webhook_client.send(contract_record)` is called when `WEBHOOK_ENABLED=true`. This pushes the full `ContractRecord` JSON to the configured third party endpoint.

- Disabled by default (`WEBHOOK_ENABLED=false`)
- 3 retries with exponential backoff: 2s, 4s, 8s
- Auth via `Authorization: Bearer <WEBHOOK_SECRET>` header (optional)
- Failure is logged as ERROR but **never fails the pipeline** — the contract is already approved and stored
- Also triggered after human review approval via the review app

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

## Review App — Human Review Flow

**Modules**: `review_app/routes/queue.py`, `review_app/routes/review.py`, `review_app/routes/decisions.py`
**Templates**: `review_app/templates/queue.html`, `review_app/templates/review.html`, `review_app/templates/decisions.html`
**GCP services**: Firestore or BigQuery (via `storage_backend`), GCS Curated Zone

**Start the review app**:
```bash
uvicorn trace_ai.review_app.main:app --reload --port 8080
```

**How templates work**:
- `queue.html` and `review.html` are static Jinja2 template files — they are never generated, they exist permanently in the repo under `review_app/templates/`
- Jinja2 renders them at request time by injecting live contract data fetched from Firestore/BigQuery
- No HTML files are written to disk — the rendered HTML is returned directly in the HTTP response

**When a contract appears in the queue**:
A contract appears in `/queue` only when Stage 7 delivery writes it to the operational store with `extraction_status = "Review Required"` — i.e. LLM Judge score was between 0.60 and 0.85.

| Score | Status | Review App |
|---|---|---|
| ≥ 0.85 | Approved | Written directly to GCS — never enters review queue |
| 0.60–0.85 | Review Required | Written to Firestore/BigQuery — appears in `/queue` |
| < 0.60 | Rejected | Logged only — does not appear in `/queue` |

**Request flow**:

```
Browser: GET /queue
        │
        ▼
queue.py → get_pending_review()        ← Firestore/BigQuery: all extraction_status="Review Required"
        │
        ▼
Jinja2 renders queue.html              ← injects contracts list
        │
        ▼
Browser: click contract → GET /review/CNT-XXX
        │
        ▼
review.py → get_contract("CNT-XXX")    ← Firestore/BigQuery: single contract by ID
        │
        ▼
Jinja2 renders review.html             ← injects full contract detail
        │
        ▼
Reviewer submits → POST /review/CNT-XXX
        │
        ├── update_review_decision()   ← writes decision + audit event to Firestore/BigQuery
        ├── if Approved → gcs_writer.write()  ← writes output.json to GCS curated zone
        ├── if Approved → webhook_client.send()  ← pushes to third party (if WEBHOOK_ENABLED=true)
        └── redirect → GET /queue

Browser: GET /approved
        │
        ▼
decisions.py → list_contracts("Approved")  ← Firestore/BigQuery: all extraction_status="Approved"
        │
        ▼
Jinja2 renders decisions.html          ← injects contracts list with reviewer, notes, reviewed_at

Browser: GET /rejected
        │
        ▼
decisions.py → list_contracts("Rejected")  ← Firestore/BigQuery: all extraction_status="Rejected"
        │
        ▼
Jinja2 renders decisions.html          ← injects contracts list with reviewer, notes, reviewed_at
```

---

## Third Party Integration

Two mechanisms are available for third party systems to consume approved contract data.

### Webhook (push)

TRACE pushes the approved `ContractRecord` JSON to the third party endpoint immediately on approval — both from the pipeline (auto-approval) and from the review app (human approval).

**Trigger**: `extraction_status = Approved` (auto or human review)  
**Module**: `delivery/webhook_client.py`  
**Method**: `POST` to `WEBHOOK_URL` with `Content-Type: application/json`

```
POST <WEBHOOK_URL>
Authorization: Bearer <WEBHOOK_SECRET>
Content-Type: application/json

{ ...full ContractRecord JSON... }
```

**Retry behaviour**: 3 attempts, exponential backoff (2s → 4s → 8s). All attempts logged. Failure never affects the pipeline.

**Environment variables**:

| Variable | Default | Description |
|---|---|---|
| `WEBHOOK_ENABLED` | `false` | Set to `true` to activate |
| `WEBHOOK_URL` | `""` | Full URL of the third party endpoint |
| `WEBHOOK_SECRET` | `""` | Sent as `Authorization: Bearer <token>`. Leave empty to skip auth |
| `WEBHOOK_TIMEOUT_SECONDS` | `10` | Per-request timeout in seconds |

**Testing locally**: Set `WEBHOOK_URL=https://webhook.site/<your-unique-id>` — every POST will appear on webhook.site in real time with full headers and body. No third party needed.

### REST API (pull)

Third party systems can pull contract data on demand via the REST API endpoints on the review app.

**Base URL**: `http://localhost:8080/api/v1` (local) or your deployed app URL  
**Auth**: `X-API-Key: <REST_API_KEY>` header. Leave `REST_API_KEY` empty to disable auth (dev only).

| Endpoint | Description |
|---|---|
| `GET /api/v1/contracts/{contract_id}` | Fetch a single contract by ID |
| `GET /api/v1/contracts?status=Review Required` | List all contracts pending human review |

**Example**:
```bash
# Fetch a single contract
curl -H "X-API-Key: your-key" http://localhost:8080/api/v1/contracts/CNT-A3F9B2C1D4E5

# List contracts pending review
curl -H "X-API-Key: your-key" "http://localhost:8080/api/v1/contracts?status=Review Required"
```

**Interactive docs**: FastAPI auto-generates Swagger UI at `http://localhost:8080/docs`

---

## Pipeline Resume — Checkpointing & Retry

The pipeline is fully resumable. On failure, re-triggering the same `contract_id` automatically skips completed stages and resumes from the failed one.

### How it works

After each stage completes, `run()` writes the stage output as a JSON checkpoint to GCS:

```
gs://<bucket>/processing/contracts/CNT-XXX/
    s1_ocr.json        ← written after OCR completes
    s2_dlp.json        ← written after DLP completes
    s3_rag.json        ← written after RAG completes
    s4_extract.json    ← written after Gemini extraction completes
    s5_normalize.json  ← written after normalization completes
    s6_judge.json      ← written after LLM Judge completes
```

On retry, `run()` checks each checkpoint in order. If the file exists, the stage is skipped and its output is loaded from GCS. If it doesn't exist, the stage runs and its output is saved.

Stage 7 (Delivery) is intentionally not checkpointed — it always re-runs to ensure the final contract state is written correctly.

### Pipeline status

`pipeline_status` is tracked in Firestore/BigQuery alongside the contract record:

| Status | Meaning |
|---|---|
| `running` | Pipeline is currently executing |
| `completed` | All 7 stages finished successfully |
| `dead_letter` | All retries exhausted — manual intervention required |

On entry, `run()` checks `pipeline_status`:
- `completed` → skips immediately, returns early
- `dead_letter` → skips immediately, logs ERROR, returns early
- anything else → sets to `running` and proceeds

### Retry with exponential backoff

Each stage is wrapped in `_with_retry()`. On transient failure, the stage is retried up to `PIPELINE_MAX_RETRIES` times (default: 3) with exponential backoff:

| Attempt | Wait |
|---|---|
| 1 | 2s |
| 2 | 4s |
| 3 | 8s |

If all attempts fail, the exception propagates, `pipeline_status` is set to `dead_letter`, and a `pipeline.dead_lettered` audit event is written.

### Forcing a full re-run

To reprocess a contract from scratch (e.g. after fixing extraction logic), delete the checkpoints from GCS:

```bash
gsutil -m rm gs://<bucket>/processing/contracts/CNT-XXX/s*.json
```

Then re-trigger. The `pipeline_status` guard will also need to be cleared — either delete the contract record or set `pipeline_status` to `null` in Firestore/BigQuery.

### Configuration

| Variable | Default | Description |
|---|---|---|
| `PIPELINE_MAX_RETRIES` | `3` | Max attempts per stage before dead-lettering. Set to `1` to disable retries. |

---

## Audit Events Reference

| Stage | Event | `details` fields |
|---|---|---|
| `extraction` | `document_ai_started` | — |
| `extraction` | `document_ai_complete` | `page_count`, `cache_hit` |
| `extraction` | `dlp_started` | — |
| `extraction` | `dlp_complete` | `pii_types`, `cache_hit` |
| `intelligence` | `rag_query_started` | — |
| `intelligence` | `rag_query_complete` | — |
| `intelligence` | `gemini_extraction_started` | — |
| `intelligence` | `gemini_extraction_complete` | — |
| `normalization` | `normalization_started` | — |
| `normalization` | `normalization_complete` | — |
| `validation` | `llm_judge_started` | — |
| `validation` | `llm_judge_complete` | `confidence_score`, `verdict`, `issues`, `critical_failures` |
| `delivery` | `written_to_curated` | `gcs_uri` |
| `delivery` | `routed_to_review_queue` | — |
| `delivery` | `rejected` | — |
| `delivery` | `webhook_delivered`, `webhook_failed` | (when `WEBHOOK_ENABLED=true`) |
| `pipeline` | `dead_lettered` | `error` |

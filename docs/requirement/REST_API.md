# TRACE REST API Reference

Full reference for all HTTP endpoints exposed by the TRACE Review App.

**Start the app:**
```bash
uvicorn trace_ai.review_app.main:app --reload --port 8080
```

**Base URL**: `http://localhost:8080`

**Interactive Swagger UI**: [http://localhost:8080/docs](http://localhost:8080/docs)

---

## Authentication

Authentication is controlled by `REST_API_KEY` in `.env`.

| `REST_API_KEY` value | Behaviour |
|---|---|
| Empty (default) | No auth required -- all requests pass through freely |
| Set to any string | Every `/api/v1/*` request must include `X-API-Key: <value>` header |

```bash
# With auth enabled
curl -H "X-API-Key: your-secret-key" http://localhost:8080/api/v1/contracts/CNT-A3F9B2C1D4E5

# With auth disabled (REST_API_KEY= empty)
curl http://localhost:8080/api/v1/contracts/CNT-A3F9B2C1D4E5
```

**Auth error response** (when key is wrong or missing):
```json
{
  "detail": "Invalid or missing API key"
}
```
HTTP status: `401 Unauthorized`

---

## Endpoints

### 1. GET /

Redirects to `/queue`.

```bash
curl -L http://localhost:8080/
```

**Response**: `302 Redirect` to `/queue`

---

### 2. GET /queue

Returns the HTML review queue page listing all contracts with `extraction_status = "Review Required"`.

**Response**: HTML page (Jinja2 rendered `queue.html`)

```bash
curl http://localhost:8080/queue
```

- Contracts are sorted by `extracted_at` descending (most recent first)
- Only contracts with `extraction_status = "Review Required"` appear
- Intended for browser use -- not a JSON API

---

### 3. GET /review/{contract_id}

Returns the HTML review detail page for a single contract.

**Path parameter**: `contract_id` -- e.g. `CNT-A3F9B2C1D4E5`

**Response**: HTML page (Jinja2 rendered `review.html`)

```bash
curl http://localhost:8080/review/CNT-A3F9B2C1D4E5
```

**Error responses**:

| Status | Condition |
|---|---|
| `404 Not Found` | Contract ID does not exist in Firestore/BigQuery |

```json
{ "detail": "Contract not found" }
```

---

### 4. POST /review/{contract_id}

Submits a human review decision (Approve or Reject) for a contract.

**Path parameter**: `contract_id` -- e.g. `CNT-A3F9B2C1D4E5`

**Request body**: `application/x-www-form-urlencoded`

| Field | Required | Description |
|---|---|---|
| `reviewer` | Yes | Name or ID of the reviewer |
| `decision` | Yes | Must be `Approved` or `Rejected` |
| `notes` | No | Optional review notes (default: empty string) |

```bash
# Approve
curl -X POST http://localhost:8080/review/CNT-A3F9B2C1D4E5 \
  -d "reviewer=John Smith&decision=Approved&notes=All fields verified"

# Reject
curl -X POST http://localhost:8080/review/CNT-A3F9B2C1D4E5 \
  -d "reviewer=John Smith&decision=Rejected&notes=Pricing section incomplete"
```

**What happens on Approved**:
1. `update_review_decision()` writes decision + audit event to Firestore/BigQuery
2. `gcs_writer.write()` writes `output.json` to GCS curated zone
3. `webhook_client.send()` pushes `ContractRecord` JSON to third party (if `WEBHOOK_ENABLED=true`)
4. Redirects to `/queue`

**What happens on Rejected**:
1. `update_review_decision()` writes decision + audit event to Firestore/BigQuery
2. Redirects to `/queue`

**Error responses**:

| Status | Condition |
|---|---|
| `400 Bad Request` | `decision` is not `Approved` or `Rejected` |
| `404 Not Found` | Contract ID does not exist |

```json
{ "detail": "Decision must be Approved or Rejected" }
{ "detail": "Contract not found" }
```

**Response on success**: `303 Redirect` to `/queue`

---

### 5. GET /approved

Returns the HTML page listing all contracts with `extraction_status = "Approved"`.

**Response**: HTML page (Jinja2 rendered `decisions.html`)

```bash
curl http://localhost:8080/approved
```

- Contracts are sorted by `reviewed_at` descending (most recently reviewed first)
- Shows reviewer name, review notes, reviewed_at timestamp for each contract
- Includes both auto-approved (pipeline) and human-approved (review app) contracts
- Intended for browser use -- not a JSON API

---

### 6. GET /rejected

Returns the HTML page listing all contracts with `extraction_status = "Rejected"`.

**Response**: HTML page (Jinja2 rendered `decisions.html`)

```bash
curl http://localhost:8080/rejected
```

- Contracts are sorted by `reviewed_at` descending
- Shows reviewer name, review notes, reviewed_at timestamp for each contract
- Intended for browser use -- not a JSON API

---

### 7. GET /api/v1/contracts/{contract_id}

Fetches a single contract record by ID as JSON.

**Path parameter**: `contract_id` -- e.g. `CNT-A3F9B2C1D4E5`

**Headers**:
- `X-API-Key` -- required only when `REST_API_KEY` is set in `.env`

```bash
# Auth disabled (default)
curl http://localhost:8080/api/v1/contracts/CNT-A3F9B2C1D4E5

# Auth enabled
curl -H "X-API-Key: your-secret-key" \
  http://localhost:8080/api/v1/contracts/CNT-A3F9B2C1D4E5
```

**Response** `200 OK`:
```json
{
  "contract_id": "CNT-A3F9B2C1D4E5",
  "extraction_status": "Approved",
  "confidence_score": 0.95,
  "extracted_at": "2024-01-15T10:30:00+00:00",
  "file_hash": "a3f9b2c1d4e5...",
  "processor_info": {
    "processor_name": "Heartland Payment Systems",
    "sales_rep_name": "Jane Doe",
    "mid": "123456789"
  },
  "company_information": {
    "merchant_legal_name": "Chet Shoes LLC",
    "dba_name": "Chet's Shoe Store",
    "address": "123 Main St",
    "city_state_zip": "Springfield, IL 62701"
  },
  "merchant_details": { "..." },
  "credit_card_pricing": { "..." },
  "processing_details": { "..." },
  "owners_officers": [ { "..." } ],
  "banking_information": { "..." }
}
```

**Error responses**:

| Status | Condition |
|---|---|
| `401 Unauthorized` | Invalid or missing API key (when auth is enabled) |
| `404 Not Found` | Contract ID does not exist |

```json
{ "detail": "Contract CNT-A3F9B2C1D4E5 not found" }
```

---

### 8. GET /api/v1/contracts?status=...

Lists all contracts with a given `extraction_status`.

**Query parameter**: `status` -- currently only `Review Required` is supported for listing

**Headers**:
- `X-API-Key` -- required only when `REST_API_KEY` is set in `.env`

```bash
# Auth disabled (default)
curl "http://localhost:8080/api/v1/contracts?status=Review Required"

# Auth enabled
curl -H "X-API-Key: your-secret-key" \
  "http://localhost:8080/api/v1/contracts?status=Review Required"

# URL-encoded (use either form)
curl "http://localhost:8080/api/v1/contracts?status=Review%20Required"
```

**Response** `200 OK`:
```json
{
  "contracts": [
    {
      "contract_id": "CNT-A3F9B2C1D4E5",
      "extraction_status": "Review Required",
      "confidence_score": 0.72,
      "extracted_at": "2024-01-15T10:30:00+00:00",
      "company_information": { "merchant_legal_name": "Chet Shoes LLC" },
      "..."
    }
  ],
  "count": 1
}
```

**Error responses**:

| Status | Condition |
|---|---|
| `400 Bad Request` | `status` value is not a valid `ExtractionStatus` |
| `400 Bad Request` | `status` is not `Review Required` (only listing supported) |
| `401 Unauthorized` | Invalid or missing API key (when auth is enabled) |

```json
{ "detail": "Invalid status. Must be one of: ['Pending', 'Approved', 'Review Required', 'Rejected']" }
{ "detail": "Only status='Review Required' is supported for listing. Fetch individual contracts by ID." }
```

---

### 9. POST /api/v1/pipeline/trigger

Scans the GCS `landing/` zone for PDF files, moves each one to `raw/`, and starts the full pipeline for each contract as a background task. Returns `202 Accepted` immediately.

**Request body**: Optional JSON.

| Field | Type | Required | Description |
|---|---|---|---|
| `files` | `list[str]` | No | Filenames to process (e.g. `["contract_a.pdf"]`). Omit to process all PDFs in `landing/`. |

**Headers**:
- `X-API-Key` -- required only when `REST_API_KEY` is set in `.env`

```bash
# Scan all PDFs in landing/ (no body needed)
curl -X POST http://localhost:8080/api/v1/pipeline/trigger \
  -H "X-API-Key: your-secret-key"

# Trigger a single specific PDF
curl -X POST http://localhost:8080/api/v1/pipeline/trigger \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"files": ["contract_a.pdf"]}'

# Trigger multiple specific PDFs
curl -X POST http://localhost:8080/api/v1/pipeline/trigger \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"files": ["contract_a.pdf", "contract_b.pdf"]}'
```

`files` contains filenames only -- not full GCS paths. The `landing/` prefix is resolved internally.

**What happens**:
1. Lists all `.pdf` files under `gs://<GCS_BUCKET>/landing/`
2. If `files` is provided, filters to only those filenames; unmatched names go directly to `skipped[]`
3. For each matched PDF: downloads bytes to compute SHA256 hash, checks for duplicates, moves blob to `raw/contracts/<CNT-XXX>/`, deletes from `landing/`
4. Fires `pipeline.run()` for each contract as a FastAPI `BackgroundTask`
5. Returns `202` immediately with the list of accepted and skipped contracts

**Response** `202 Accepted` -- PDFs found:
```json
{
  "accepted": [
    {
      "contract_id": "CNT-A1B2C3D4E5F6",
      "gcs_uri": "gs://my-bucket/raw/contracts/CNT-A1B2C3D4E5F6/contract.pdf"
    }
  ],
  "skipped": [],
  "count": 1,
  "messages": [
    "Poll GET /api/v1/contracts/CNT-A1B2C3D4E5F6 for status."
  ]
}
```

**Response** `202 Accepted` -- no PDFs in landing (or none matched):
```json
{
  "accepted": [],
  "skipped": [],
  "count": 0,
  "messages": []
}
```

**Response** `202 Accepted` -- multiple PDFs accepted:
```json
{
  "accepted": [
    {"contract_id": "CNT-A1B2C3D4E5F6", "gcs_uri": "gs://..."},
    {"contract_id": "CNT-B2C3D4E5F6A1", "gcs_uri": "gs://..."}
  ],
  "skipped": [],
  "count": 2,
  "messages": [
    "Poll GET /api/v1/contracts/CNT-A1B2C3D4E5F6 for status.",
    "Poll GET /api/v1/contracts/CNT-B2C3D4E5F6A1 for status."
  ]
}
```

**Response** `202 Accepted` -- with skipped files:
```json
{
  "accepted": [{"contract_id": "CNT-A1B2C3D4E5F6", "gcs_uri": "gs://..."}],
  "skipped": [
    {"blob": "landing/duplicate.pdf", "reason": "Duplicate contract detected -- already processed as CNT-XXXX"},
    {"blob": "landing/missing.pdf", "reason": "Not found in landing zone"}
  ],
  "count": 1,
  "messages": [
    "Poll GET /api/v1/contracts/CNT-A1B2C3D4E5F6 for status."
  ]
}
```

**Skipped files** are not deleted from `landing/` -- they remain for manual inspection.

**Poll for result** after triggering:
```bash
curl -H "X-API-Key: your-key" http://localhost:8080/api/v1/contracts/CNT-A1B2C3D4E5F6
# extraction_status will be "Pending" while running, then "Approved" / "Review Required" / "Rejected"
```

**Error responses**:

| Status | Condition |
|---|---|
| `401 Unauthorized` | Invalid or missing API key (when auth is enabled) |

---

## Endpoint Summary

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | No | Redirect to `/queue` |
| `GET` | `/queue` | No | HTML review queue -- pending contracts (browser) |
| `GET` | `/review/{contract_id}` | No | HTML review detail page (browser) |
| `POST` | `/review/{contract_id}` | No | Submit Approve/Reject decision |
| `GET` | `/approved` | No | HTML list of all approved contracts (browser) |
| `GET` | `/rejected` | No | HTML list of all rejected contracts (browser) |
| `POST` | `/api/v1/pipeline/trigger` | Optional | Scan `landing/` zone, move PDFs to `raw/`, start pipeline per contract |
| `GET` | `/api/v1/contracts/{contract_id}` | Optional | Fetch single contract as JSON |
| `GET` | `/api/v1/contracts?status=...` | Optional | List contracts by status as JSON |
| `GET` | `/api/v1/contracts/status/stats` | Optional | Breakdown of contracts by status |

"Auth: Optional" means auth is enforced only when `REST_API_KEY` is set in `.env`. Default is no auth.

---

## Testing with Postman

1. Start the app: `uvicorn trace_ai.review_app.main:app --reload --port 8080`
2. Import the base URL `http://localhost:8080`
3. For JSON endpoints (`/api/v1/*`), set `Accept: application/json` header
4. If `REST_API_KEY` is set, add `X-API-Key: <value>` header to all `/api/v1/*` requests
5. For `POST /review/{contract_id}`, set body type to `form-data` with fields `reviewer`, `decision`, `notes`

## Testing Webhook

To test outbound webhook delivery locally:

1. Go to [https://webhook.site](https://webhook.site) and copy your unique URL
2. Set in `.env`:
   ```
   WEBHOOK_ENABLED=true
   WEBHOOK_URL=https://webhook.site/your-unique-id
   ```
3. Run the pipeline or approve a contract via the review app
4. The full `ContractRecord` JSON payload will appear on webhook.site in real time

To test retry behaviour, use a Postman Mock Server configured to return `500` -- TRACE will retry 3 times with 2s, 4s, 8s backoff and log each attempt.

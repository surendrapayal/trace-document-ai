# Technical Design Document (TDD)
# Data Access Review Request (DARR)
# Contract Intelligence & Pricing Extraction Platform

**Version:** 1.0
**Project:** Contract Intelligence Platform (TRACE)
**Architecture Foundation:** Contract Processing AI Platform
**Product Owner:**

---

## 1. Executive Summary

The Contract Intelligence Platform is a GCP-native AI solution designed to automate the extraction, interpretation, normalization, and validation of merchant processing contracts and related commercial documents.

The platform ingests contract documents, extracts structured commercial and pricing information, normalizes processor-specific terminology into a canonical contract schema, validates extraction quality using Retrieval Augmented Generation (RAG) and LLM-based review, and generates standardized JSON output files for downstream consumption.

The platform's responsibility ends when the validated JSON artifact is generated and stored in the approved output location.

No downstream warehousing, analytics, reporting, or BigQuery ingestion is performed by this platform.

---

## 2. Business Purpose

Merchant processing contracts contain critical commercial information including:

- Pricing programs
- Fee schedules
- Billing models
- Contract terms
- Renewal terms
- Termination clauses
- Service fees
- Special provisions
- Processor-specific language

Today, contract interpretation requires significant manual review and domain expertise.

The platform automates:

- Contract ingestion
- OCR extraction
- Contract metadata extraction
- Pricing schedule extraction
- Clause identification
- Contract normalization
- Quality validation
- JSON record generation

Expected business benefits include:

- Reduced manual contract review effort
- Faster onboarding workflows
- Improved contract visibility
- Improved pricing intelligence
- Consistent contract interpretation
- Structured contract metadata for downstream use

---

## 3. Scope

### In Scope

The platform is responsible for:

- Contract document ingestion
- OCR processing
- Entity extraction
- Commercial term extraction
- Pricing extraction
- Contract normalization
- Confidence scoring
- Human review workflows
- Audit logging
- JSON generation
- JSON storage

### Out of Scope

The platform does not perform:

- Data warehousing
- BigQuery ingestion
- Data transformation within BigQuery
- Reporting
- BI dashboards
- User-facing analytics
- Contract management workflows

The platform boundary ends with creation of the validated JSON output.

---

## 4. Solution Architecture

**Reference Architecture (GCP)**

The solution follows a five-stage architecture:

```
Ingest → Extract → Intelligence → Normalize → Validate → JSON Output
```

| Stage | GCP Components |
|-------|---------------|
| 1 - Ingest | Cloud Storage (GCS), trace_ai.ingestion (upload_handler) |
| 2 - Extract | Document AI (OCR + Form Parser), Cloud DLP |
| 3 - Intelligence | Vertex AI Gemini, Vertex AI Vector Search (RAG), Vertex AI Embeddings API |
| 4 - Normalize & Validate | Pydantic ContractRecord, Vertex AI Gemini (LLM-as-a-Judge) |
| 5 - Deliver | storage_backend (Firestore or BigQuery), Cloud Run (FastAPI Review App), GCS Curated Zone |

---

## 5. Architecture Components

### 5.1 Ingest Layer

**GCP Services**
- Google Cloud Storage (GCS)

**Application Code**
- `trace_ai.ingestion.upload_handler` — validates PDF, uploads to GCS Raw Zone, returns GCS URI
- `trace_ai.pipeline` — Python orchestrator, starts from GCS URI, wires all 7 stages

**Supported Input Documents**
- Merchant processing agreements (PDF)
- Amendments
- Addenda
- Pricing schedules
- Rate cards
- Processor agreements
- Contract exhibits

**Workflow**
```
Contract PDF → trace_ai.ingestion.upload_handler → GCS Raw Zone → trace_ai.pipeline (GCS URI)
```

### 5.2 Extraction Layer

**Google Cloud Document AI**

Purpose:
- OCR
- Table extraction
- Key-value extraction (Form Parser processor)

Extracted Content:
- Document text
- Pricing tables
- Fee schedules
- Contract metadata

**Google Cloud DLP (Data Loss Prevention)**

Purpose:
- Entity extraction
- PII detection and de-identification

Extracted Entities:
- Processor names
- Merchant identifiers
- Contract references
- Commercial terms
- Pricing references

**PII Handling**

Any detected sensitive information is flagged and masked by Cloud DLP prior to Vertex AI LLM processing.

### 5.3 Intelligence Layer

**Vertex AI Gemini (LLM Gateway)**

Primary functions:
- Clause extraction
- Pricing interpretation
- Fee classification
- Contract understanding

**Vertex AI Vector Search (RAG)**

Provides contextual grounding using:
- Processor playbooks
- Contract templates
- Pricing references
- Fee dictionaries
- Business terminology mappings

**Extraction Prompts (7 total)**

Each section is extracted by a dedicated prompt in `intelligence/prompts/`:
- company_information.txt
- pricing_extraction.txt
- merchant_details.txt
- processing_details.txt
- processor_info.txt
- owners_officers.txt
- banking_information.txt

---

## 6. Canonical Contract Schema

All contract documents are normalized into a common Pydantic schema — `ContractRecord` — defined in `normalization/schema.py`.

| Section | Model | Key Fields |
|---------|-------|------------|
| Identity | `ProcessorInfo` | processor_brand, rep_name, rep_role, mid, atlas_token, referred_by |
| Company | `CompanyInformation` | legal_name, legal_address, dba_name, primary_contact, HIC admin |
| Merchant | `MerchantDetails` | business_type, ownership_type, tax_id, PCI compliance |
| Pricing | `CreditCardPricing` | billing_model, card_rates, recurring_fees, Amex details |
| Processing | `ProcessingDetails` | card_swiped_pct, face_to_face_pct, website flag |
| Owners | `List[OwnerOfficer]` | name, title, ownership_pct, DOB, SSN last 4, DL last 4 |
| Banking | `BankingInformation` | funding_option, accounts[bank_name, routing_number, account_number_masked] |
| Validation | (ContractRecord fields) | confidence_score, extraction_status, reviewed_by |

Billing models supported: `IC++`, `Flat Rate`, `Tiered`, `Unknown`

See `docs/requirement/CONTRACT_SCHEMA.md` for full Pydantic definition and example extracted JSON.

---

## 7. Validation Layer

**Vertex AI LLM Evaluation (LLM-as-a-Judge)**

A secondary Gemini model is used to validate extracted content.

**Validation Checks**
- Extraction completeness
- Clause fidelity
- Pricing accuracy
- Schema adherence
- Contract consistency

**Confidence Outcomes**
- Approved
- Review Required
- Rejected

**Confidence Thresholds**

| Score | Outcome |
|-------|---------|
| ≥ 0.85 | Approved — written to GCS Curated Zone automatically |
| 0.60 – 0.85 | Review Required — routed to FastAPI review app queue |
| < 0.60 | Rejected — logged, manual intervention required |

**Human Review Workflow**

Low-confidence outputs are routed to the FastAPI review app (Cloud Run) via the configured operational store (`storage_backend`).

Reviewer actions:
- Approve — writes output to GCS Curated Zone
- Reject — logged in audit_events table/collection

All reviewer decisions are logged and auditable.

---

## 8. Delivery Layer

**Purpose**

The delivery layer generates standardized machine-readable contract outputs.

**Output Format:** JSON

**Example Output**

```json
{
  "contract_id": "CNT-12345",
  "merchant_name": "ABC Merchant",
  "processor": "Worldpay",
  "effective_date": "2026-01-01",
  "billing_model": "IC++",
  "pricing_schedule": {
    "discount_rate": "2.30%"
  },
  "fees": [
    {
      "fee_name": "Authorization Fee",
      "amount": "0.05"
    }
  ],
  "confidence_score": 0.97
}
```

**Platform Boundary**

The platform lifecycle ends after:

```
Validated Contract → JSON Serialization → Approved Output Storage (GCS)
```

No downstream processing is performed by this platform.

---

## 9. End-to-End Data Flow

**Step 1: Contract Upload**
```
Contract PDF → GCS Landing Bucket
```

**Step 2: OCR Extraction**
```
Document AI (Form Parser / OCR Processor) → Structured Content
```

**Step 3: Entity Recognition**
```
Cloud DLP → Contract Metadata
```

**Step 4: Contract Intelligence**
```
Vertex AI Gemini + Vertex AI Vector Search RAG → Canonical Contract Representation
```

**Step 5: Validation**
```
Vertex AI LLM Evaluation (LLM-as-a-Judge) → Confidence Scoring
```

**Step 6: Publishing**
```
Validated Contract Record → JSON Generation → GCS Output Bucket
```

---

## 10. Data Inventory

| Dataset | Classification |
|---------|---------------|
| Contract PDFs | Confidential |
| Amendments | Confidential |
| Processor Agreements | Confidential |
| Pricing Schedules | Confidential |
| Fee Schedules | Confidential |
| OCR Content | Confidential |
| Contract Metadata | Confidential |
| Extracted Clauses | Confidential |
| Audit Records | Internal |
| Confidence Scores | Internal |
| JSON Outputs | Confidential |

---

## 11. Sensitive Data Assessment

The platform may process:

**Merchant Information**
- Merchant Name
- Merchant Address
- Business Contact Information
- Merchant Identifiers

**Commercial Information**
- Pricing schedules
- Fee arrangements
- Contract dates
- Renewal terms
- Commercial clauses

**Confidential Business Information**
- Negotiated pricing
- Service agreements
- Commercial Commitments
- Processor-specific terms

**Explicitly Excluded**

The solution is not designed to process:
- Payment card numbers
- Cardholder data
- Authentication credentials
- PCI transaction data

---

## 12. Storage Locations

**Google Cloud Storage (GCS)**

Raw Zone — Stores:
- Original contracts
- Amendments
- Supporting documents

Processing Zone — Stores:
- Document AI OCR outputs
- Intermediate extraction artifacts
- Validation artifacts

Curated Zone — Stores:
- Final JSON outputs

**Vertex AI Vector Search** — Stores:
- Vector embeddings
- Contract knowledge base
- Processor reference material
- RAG documents

**Operational Store — Firestore or BigQuery (via `STORAGE_BACKEND`)** — Stores:
- Audit metadata
- Workflow status
- Confidence scores
- Human review records

---

## 13. Access Model

**Platform Administrators**

Access:
- Infrastructure configuration
- Service management
- Security administration

**Data Scientists**

Access:
- Extraction outputs
- Model evaluation data
- Validation results

**Contract Review Analysts**

Access:
- Review queue at `GET /queue` (FastAPI review app on Cloud Run)
- Contract detail view at `GET /review/{contract_id}`
- Approve / Reject decisions via `POST /review/{contract_id}`

**Business Consumers**

Access:
- Approved JSON outputs only

---

## 14. Security Controls

**Authentication**
- Google Workspace SSO / Identity Platform
- Identity and Access Management (IAM) with Role-Based Access Control

**Encryption at Rest**
- GCS encryption (Google-managed or CMEK)
- Firestore encryption (when `STORAGE_BACKEND=firestore`)
- BigQuery encryption (when `STORAGE_BACKEND=bigquery`)
- Vertex AI Vector Search encryption

**Encryption in Transit**
- TLS 1.2 or higher

**Monitoring**
- Cloud Monitoring
- Cloud Audit Logs
- Cloud Logging (application audit logs)

**Auditing**

All platform activities are logged and retained according to enterprise policy via Cloud Audit Logs.

---

## 15. Human-in-the-Loop Controls

Records below confidence thresholds are routed for manual review via the FastAPI review app deployed on Cloud Run.

Review workflow:

```
Low Confidence Output → storage_backend (status=Review Required) → FastAPI /queue → Approve / Reject → Audit Record (storage_backend)
```

All reviewer decisions are retained for governance and model improvement.

---

## 16. Technology Decision — Configurable Operational Storage (Firestore or BigQuery)

### Decision Summary

The TRACE platform supports both Google Firestore and BigQuery as the operational data store, configurable via the `STORAGE_BACKEND` environment variable. No code changes are required to switch backends.

### Configuration

```
STORAGE_BACKEND=firestore   # default — real-time, transactional
STORAGE_BACKEND=bigquery    # POC / environments without Firestore access
```

The `delivery/storage_backend.py` factory re-exports the correct implementation (`firestore_client.py` or `bigquery_client.py`) based on this value. Both expose the same 5-function interface: `upsert_contract`, `write_audit_event`, `get_contract`, `get_pending_review`, `update_review_decision`.

### Comparison

| Criteria | Firestore | BigQuery | Winner |
|---|---|---|---|
| Write latency | ~1–10ms (real-time) | Seconds (streaming insert) | Firestore |
| Read by contract ID | Instant key-value lookup | Full or partition scan | Firestore |
| Live workflow state tracking | Native — real-time document updates | Not designed for this | Firestore |
| HITL review queue management | Supported — live document listeners | Not transactional | Firestore |
| Concurrent reviewer updates | ACID transactions per document | No row-level transactions | Firestore |
| Schema flexibility | Schemaless — adapts as fields evolve | Strict schema, ALTER TABLE needed | Firestore |
| Analytical / historical queries | Limited | Excellent — SQL at scale | BigQuery |
| Cost at operational volume | Very low — per read/write | Query-billed — cost grows with scans | Firestore |
| GCP access requirements | Requires Firestore database provisioning | Available in most GCP projects | BigQuery |

### When to Use Each

**Firestore** (`STORAGE_BACKEND=firestore`) — recommended for production:
- Sub-10ms latency for pipeline audit events
- ACID transactions for concurrent HITL reviewer access
- Document model fits ContractRecord structure natively

**BigQuery** (`STORAGE_BACKEND=bigquery`) — recommended for POC / restricted environments:
- Firestore database provisioning not available
- Higher latency (~1–2s per lookup) is acceptable
- Analytical queries across all contracts are needed

### Recommended Future State

```
Firestore (operational)  →  Pub/Sub  →  BigQuery (analytical)
     |                                        |
 Live state, HITL queue              Historical reporting,
 Workflow tracking                   Model evaluation,
 Per-contract audit                  Compliance queries
```

---

## 17. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Poor scan quality | Document AI confidence thresholds and HITL manual review |
| Non-standard contract formats | Vertex AI Vector Search RAG grounding and canonical normalization |
| Hallucinated contract terms | LLM-as-a-Judge secondary Gemini validation |
| Missing section extraction | Per-section field scores in ValidationResult — critical fields block approval |
| Incorrect pricing extraction | Human review workflow via FastAPI review app |
| Schema inconsistencies | Pydantic ContractRecord validation at normalization stage |
| Unauthorized access | IAM RBAC and Google Workspace SSO controls |

---

## 17. Data Access Review Request

Approval is requested for controlled access to the following data and services.

**Data Sources**
- Merchant contracts
- Processor agreements
- Contract amendments
- Pricing schedules
- Fee schedules
- Contract exhibits

**GCP Services**
- Google Cloud Storage (GCS)
- Google Cloud Document AI
- Google Cloud DLP
- Vertex AI Gemini (gemini-1.5-pro)
- Vertex AI Vector Search
- Vertex AI Embeddings API (text-embedding-004)
- Google Firestore (when `STORAGE_BACKEND=firestore`)
- Google BigQuery (when `STORAGE_BACKEND=bigquery`)
- Cloud Run
- Cloud Monitoring & Logging
- Cloud Audit Logs

**Generated Data**
- Extracted contract metadata
- Canonical contract records
- Validation results
- Audit metadata
- JSON output artifacts

**Business Justification**

Access is required to support automated contract ingestion, extraction, normalization, validation, and publication of standardized contract records. The platform enables consistent interpretation of processor agreements and creation of structured JSON outputs for downstream consumption.

**System Boundary:** The platform's responsibility ends after successful generation and storage of validated JSON output files in GCS. Any downstream ingestion, storage, transformation, reporting, or analytics functions are outside the scope of this request and managed by separate systems and teams.

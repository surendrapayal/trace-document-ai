# Technical Design Document (TDD)
# Data Access Review Request (DARR)
# Contract Intelligence & Pricing Extraction Platform

**Version:** 1.0
**Project:** Contract Intelligence Platform (TRACE)
**Architecture Foundation:** Contract Processing AI Platform
**Product Owner:**

---

## 1. Executive Summary

The Contract Intelligence Platform is an AWS-native AI solution designed to automate the extraction, interpretation, normalization, and validation of merchant processing contracts and related commercial documents.

The platform ingests contract documents, extracts structured commercial and pricing information, normalizes processor-specific terminology into a canonical contract schema, validates extraction quality using Retrieval Augmented Generation (RAG) and LLM-based review, and generates standardized JSON output files for downstream consumption.

The platform's responsibility ends when the validated JSON artifact is generated and stored in the approved output location.

No downstream warehousing, analytics, reporting, or Snowflake ingestion is performed by this platform.

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
- Snowflake ingestion
- Data transformation within Snowflake
- Reporting
- BI dashboards
- User-facing analytics
- Contract management workflows

The platform boundary ends with creation of the validated JSON output.

---

## 4. Solution Architecture

**Reference Architecture (Worldpay)**

The solution follows a five-stage architecture:

```
Ingest → Extract → Intelligence → Normalize → Validate → JSON Output
```

| Stage | Components |
|-------|-----------|
| 1 - Ingest | Acquirer Invoices (S3), Raw Landing Bucket |
| 2 - Extract | Textract OCR Tables, Comprehend Entities - PII |
| 3 - Intelligence | LLM Gateway - NEURONSDK, OpenSearch Vector RAG, SageMaker Classify - Score |
| 4 - Reconcile | Published Visa / MC (S3), Delta & Padding Engine, LLM-as-a-Judge |
| 5 - Deliver | DynamoDB Results - Audit, Streamlit Review App, JSON file output |

---

## 5. Architecture Components

### 5.1 Ingest Layer

**AWS Services**
- Amazon S3
- Amazon EventBridge
- AWS Step Functions

**Supported Input Documents**
- Merchant processing agreements
- Amendments
- Addenda
- Pricing schedules
- Rate cards
- Processor agreements
- Contract exhibits

**Workflow**
```
Contract Uploaded → S3 Landing Bucket → Event Trigger → Processing Workflow
```

### 5.2 Extraction Layer

**Amazon Textract**

Purpose:
- OCR
- Table extraction
- Key-value extraction

Extracted Content:
- Document text
- Pricing tables
- Fee schedules
- Contract metadata

**Amazon Comprehend**

Purpose:
- Entity extraction
- PII detection

Extracted Entities:
- Processor names
- Merchant identifiers
- Contract references
- Commercial terms
- Pricing references

**PII Handling**

Any detected sensitive information is flagged prior to LLM processing.

### 5.3 Intelligence Layer

**LLM Gateway (NEURONSDK)**

Primary functions:
- Clause extraction
- Pricing interpretation
- Fee classification
- Contract understanding

**OpenSearch Vector RAG**

Provides contextual grounding using:
- Processor playbooks
- Contract templates
- Pricing references
- Fee dictionaries
- Business terminology mappings

**Guardrails**

Provides:
- Grounding validation
- Hallucination mitigation
- Content validation
- Output consistency controls

---

## 6. Canonical Contract Schema

All contract documents are normalized into a common schema.

Example:

```json
{
  "contract_id": "",
  "merchant_name": "",
  "processor": "",
  "effective_date": "",
  "expiration_date": "",
  "term_months": 0,
  "billing_model": "",
  "pricing_schedule": {},
  "fees": [],
  "renewal_terms": {},
  "termination_terms": {},
  "special_clauses": [],
  "confidence_score": 0.0
}
```

This schema provides consistency across all processor contract formats.

---

## 7. Validation Layer

**LLM-as-a-Judge**

A secondary model is used to validate extracted content.

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

**Human Review Workflow**

Low-confidence outputs are routed to designated reviewers for validation.

Reviewer actions:
- Approve
- Modify
- Reject

All reviewer actions are logged and auditable.

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
Validated Contract → JSON Serialization → Approved Output Storage
```

No downstream processing is performed by this platform.

---

## 9. End-to-End Data Flow

**Step 1: Contract Upload**
```
Contract PDF → S3 Landing Bucket
```

**Step 2: OCR Extraction**
```
Textract → Structured Content
```

**Step 3: Entity Recognition**
```
Comprehend → Contract Metadata
```

**Step 4: Contract Intelligence**
```
LLM Gateway + OpenSearch RAG → Canonical Contract Representation
```

**Step 5: Validation**
```
LLM-as-a-Judge → Confidence Scoring
```

**Step 6: Publishing**
```
Validated Contract Record → JSON Generation → Output Location
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

**Amazon S3**

Raw Zone — Stores:
- Original contracts
- Amendments
- Supporting documents

Processing Zone — Stores:
- OCR outputs
- Intermediate extraction artifacts
- Validation artifacts

Curated Zone — Stores:
- Final JSON outputs

**Amazon OpenSearch** — Stores:
- Vector embeddings
- Contract knowledge base
- Processor reference material
- RAG documents

**Amazon DynamoDB** — Stores:
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
- Review queues
- Validation workflows
- Human-in-the-loop interface

**Business Consumers**

Access:
- Approved JSON outputs only

---

## 14. Security Controls

**Authentication**
- Enterprise SSO
- Role-Based Access Control (RBAC)

**Encryption at Rest**
- Amazon S3 encryption
- DynamoDB encryption
- OpenSearch encryption

**Encryption in Transit**
- TLS 1.2 or higher

**Monitoring**
- CloudWatch
- CloudTrail
- Application audit logs

**Auditing**

All platform activities are logged and retained according to enterprise policy.

---

## 15. Human-in-the-Loop Controls

Records below confidence thresholds are routed for manual review.

Review workflow:

```
Low Confidence Output → Reviewer Queue → Approve / Modify / Reject → Audit Record
```

All reviewer decisions are retained for governance and model improvement.

---

## 16. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Poor scan quality | OCR confidence thresholds and manual review |
| Non-standard contract formats | RAG grounding and canonical normalization |
| Hallucinated contract terms | Guardrails and LLM-as-a-Judge |
| Missing clause extraction | Completeness validation checks |
| Incorrect pricing extraction | Human review workflow |
| Schema inconsistencies | JSON schema validation |
| Unauthorized access | RBAC and SSO controls |

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

**AWS Services**
- Amazon S3
- Amazon EventBridge
- AWS Step Functions
- Amazon Textract
- Amazon Comprehend
- Amazon OpenSearch
- Amazon DynamoDB

**Generated Data**
- Extracted contract metadata
- Canonical contract records
- Validation results
- Audit metadata
- JSON output artifacts

**Business Justification**

Access is required to support automated contract ingestion, extraction, normalization, validation, and publication of standardized contract records. The platform enables consistent interpretation of processor agreements and creation of structured JSON outputs for downstream consumption.

**System Boundary:** The platform's responsibility ends after successful generation and storage of validated JSON output files. Any downstream ingestion, storage, transformation, reporting, or analytics functions are outside the scope of this request and managed by separate systems and teams.

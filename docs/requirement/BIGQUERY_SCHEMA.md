# TRACE — BigQuery Schema Reference

This document describes the two BigQuery tables used when `STORAGE_BACKEND=bigquery`.

Dataset: `BIGQUERY_DATASET` (configured in `.env`, default: `trace_contracts`)

Created by: `scripts/create_bq_tables.py`

---

## Tables Overview

| Table | Purpose | Write Pattern |
|---|---|---|
| `contracts` | One row per contract — full ContractRecord + status | MERGE (upsert by `contract_id`) |
| `audit_events` | Append-only event log — one row per pipeline stage event | INSERT (streaming) |

---

## Table 1: `contracts`

One row per contract. Written and updated by `delivery/bigquery_client.upsert_contract()`.

Clustered on `extraction_status` for efficient queue queries.

### Schema

| Column | BQ Type | Mode | Source | Description |
|---|---|---|---|---|
| `contract_id` | STRING | REQUIRED | `ContractRecord.contract_id` | Auto-generated ID e.g. `CNT-20240101-abc123` |
| `processor_info` | JSON | NULLABLE | `ContractRecord.processor_info` | See ProcessorInfo fields below |
| `company_information` | JSON | NULLABLE | `ContractRecord.company_information` | See CompanyInformation fields below |
| `merchant_details` | JSON | NULLABLE | `ContractRecord.merchant_details` | See MerchantDetails fields below |
| `credit_card_pricing` | JSON | NULLABLE | `ContractRecord.credit_card_pricing` | See CreditCardPricing fields below |
| `processing_details` | JSON | NULLABLE | `ContractRecord.processing_details` | See ProcessingDetails fields below |
| `owners_officers` | JSON | NULLABLE | `ContractRecord.owners_officers` | JSON array — see OwnerOfficer fields below |
| `banking_information` | JSON | NULLABLE | `ContractRecord.banking_information` | See BankingInformation fields below |
| `confidence_score` | FLOAT64 | NULLABLE | `ContractRecord.confidence_score` | LLM Judge score — 0.0 to 1.0 |
| `extraction_status` | STRING | NULLABLE | `ContractRecord.extraction_status` | `Approved`, `Review Required`, `Rejected`, `Pending` |
| `field_scores` | JSON | NULLABLE | `ContractRecord.field_scores` | Per-section LLM Judge scores e.g. `{"credit_card_pricing": 0.54, ...}` |
| `judge_issues` | JSON | NULLABLE | `ContractRecord.judge_issues` | List of specific issues flagged by LLM Judge |
| `source_pdf_uri` | STRING | NULLABLE | `ContractRecord.source_pdf_uri` | GCS URI of the raw input PDF |
| `page_count` | INT64 | NULLABLE | `ContractRecord.page_count` | Number of pages in the PDF (from OCR stage) |
| `file_hash` | STRING | NULLABLE | `ContractRecord.file_hash` | SHA256 hash of the original PDF bytes — used for duplicate detection |
| `extracted_at` | STRING | NULLABLE | `ContractRecord.extracted_at` | ISO 8601 UTC timestamp |
| `reviewed_by` | STRING | NULLABLE | `ContractRecord.reviewed_by` | Reviewer name (set after HITL review) |
| `review_notes` | STRING | NULLABLE | `ContractRecord.review_notes` | Reviewer notes (set after HITL review) |
| `reviewed_at` | STRING | NULLABLE | Set by `update_review_decision()` | ISO 8601 UTC — time of HITL decision |
| `curated_gcs_uri` | STRING | NULLABLE | Set by `upsert_contract()` | GCS URI of final JSON output e.g. `gs://trace-curated/contracts/CNT-xxx/output.json` |
| `updated_at` | STRING | NULLABLE | Set by `upsert_contract()` | ISO 8601 UTC — last upsert time |

---

### JSON Column Structures

All nested Pydantic models are serialised to JSON strings by `bigquery_client.py` using `json.dumps()`.
Use `JSON_VALUE()` or `JSON_QUERY()` in SQL to extract fields.

---

#### `processor_info` — ProcessorInfo

```json
{
  "processor_name": "Heartland Payment Systems",
  "sales_rep_name": "Jane Smith",
  "sales_rep_role": "Sales Representative",
  "sales_rep_phone": "555-000-0000",
  "mid": "123456789",
  "atlas_token": "ATL-XXXXX",
  "sdr_name": "John Doe",
  "affiliate_id": "AFF-001",
  "generated_on": "2024-01-15"
}
```

| Field | Type | Description |
|---|---|---|
| `processor_name` | string | Required — processor company name |
| `sales_rep_name` | string\|null | Sales representative name |
| `sales_rep_role` | string\|null | Role title |
| `sales_rep_phone` | string\|null | Contact phone |
| `mid` | string\|null | Merchant ID |
| `atlas_token` | string\|null | Atlas system token |
| `sdr_name` | string\|null | SDR name |
| `affiliate_id` | string\|null | Affiliate identifier |
| `generated_on` | string\|null | Contract generation date |

---

#### `company_information` — CompanyInformation

```json
{
  "legal_name": "Chet Shoes LLC",
  "legal_address": "8870 Rendova St NE, Circle Pines, MN 55014",
  "legal_phone": "(763) 253-1079",
  "dba_name": "Chet's Shoes",
  "dba_address": null,
  "dba_phone": null,
  "contact_email": "info@chetshoes.com",
  "website": "www.chetshoes.com",
  "primary_contact_name": "Chester Brown",
  "primary_contact_phone": "555-111-3333",
  "secondary_contact_phone": null,
  "after_hours_emergency_phone": null,
  "authorized_to_purchase": null,
  "hic_admin_name": "Admin User",
  "hic_admin_email": "admin@heartland.us"
}
```

| Field | Type | Description |
|---|---|---|
| `legal_name` | string | Required — legal business name |
| `legal_address` | string\|null | Full legal address |
| `legal_phone` | string\|null | Phone in legal block |
| `dba_name` | string\|null | Doing business as name |
| `dba_address` | string\|null | Physical DBA address |
| `dba_phone` | string\|null | Phone listed next to DBA |
| `contact_email` | string\|null | Main business email |
| `website` | string\|null | Business website |
| `primary_contact_name` | string\|null | Primary contact |
| `primary_contact_phone` | string\|null | Primary contact phone |
| `secondary_contact_phone` | string\|null | Secondary phone under primary |
| `after_hours_emergency_phone` | string\|null | After hours/emergency phone |
| `authorized_to_purchase` | string\|null | Yes or No |
| `hic_admin_name` | string\|null | HIC admin name |
| `hic_admin_email` | string\|null | HIC admin email |

---

#### `merchant_details` — MerchantDetails

```json
{
  "business_type": "Retail",
  "ownership_type": "LLC",
  "tax_id": "XX-XXXXXXX",
  "services": "Card Present",
  "card_acceptance": "Visa, Mastercard, Discover, Amex",
  "statement_type": "Online",
  "new_existing_business": "Existing",
  "length_in_business": "5 years",
  "number_of_terminals": 2,
  "deposit_method": "ACH",
  "dispute_letter_mailing": "Yes",
  "dispute_letter_electronic": "No",
  "pci_compliant": true
}
```

| Field | Type | Description |
|---|---|---|
| `business_type` | string\|null | e.g. Retail, Restaurant, Non-Profit |
| `ownership_type` | string\|null | e.g. LLC, Sole Proprietor, Corporation |
| `tax_id` | string\|null | EIN / Tax ID (may be masked by DLP) |
| `services` | string\|null | Services offered |
| `card_acceptance` | string\|null | Card brands accepted |
| `statement_type` | string\|null | Online or Paper |
| `new_existing_business` | string\|null | New or Existing |
| `length_in_business` | string\|null | Years in business |
| `number_of_terminals` | integer\|null | Terminal count |
| `deposit_method` | string\|null | ACH or Check |
| `dispute_letter_mailing` | string\|null | Mailing preference |
| `dispute_letter_electronic` | string\|null | Electronic preference |
| `pci_compliant` | boolean\|null | PCI compliance status |

---

#### `credit_card_pricing` — CreditCardPricing

```json
{
  "annual_volume": "500000",
  "avg_ticket": "75.00",
  "network": "Visa/MC/Discover",
  "interchange_calculation": "Interchange Plus",
  "settlement_type": "Monthly 5 bps",
  "billing_model": "IC++",
  "card_rates": [
    {
      "card_type": "Visa Credit",
      "discount_rate_cp": "0.20%",
      "discount_rate_cnp": "0.25%",
      "trans_fee_cp": "0.10",
      "trans_fee_cnp": "0.15",
      "non_emv_assessment_fee": "0.20%"
    }
  ],
  "amex_details": {
    "annual_volume": "50000",
    "average_ticket": "80.00",
    "amex_program": "OptBlue",
    "amex_merchant_number": "AMEX-XXXXX",
    "opt_out_of_marketing": false,
    "arc_iata_number": null
  },
  "recurring_fees": [
    { "fee_name": "Monthly Service Fee", "amount": "9.95", "frequency": "Monthly" },
    { "fee_name": "PCI Compliance Fee", "amount": "99.00", "frequency": "Annually" }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `annual_volume` | string\|null | Estimated annual processing volume |
| `avg_ticket` | string\|null | Average transaction amount |
| `network` | string\|null | Card networks |
| `interchange_calculation` | string\|null | Interchange calculation method |
| `settlement_type` | string\|null | `Monthly 5 bps`, `Monthly 0 bps`, `Daily`, `Unknown` |
| `billing_model` | string | `IC++`, `Flat Rate`, `Tiered`, `Unknown` |
| `card_rates` | array | List of CardPricingRate objects (see below) |
| `amex_details` | object\|null | Amex-specific fields (see below) |
| `recurring_fees` | array | List of RecurringFee objects (see below) |

**CardPricingRate fields:**

| Field | Type | Description |
|---|---|---|
| `card_type` | string | e.g. Visa Credit, MC Debit, Discover |
| `discount_rate_cp` | string\|null | Card present discount rate |
| `discount_rate_cnp` | string\|null | Card not present discount rate |
| `discount_rate` | string\|null | Single rate (IC++ contracts) |
| `discount_per_item` | string\|null | Per item discount |
| `trans_fee_cp` | string\|null | Card present transaction fee |
| `trans_fee_cnp` | string\|null | Card not present transaction fee |
| `trans_fee_dial` | string\|null | Dial transaction fee |
| `trans_fee_ip` | string\|null | IP transaction fee |
| `non_emv_assessment_fee` | string\|null | Non-EMV assessment fee |

**AmexDetails fields:**

| Field | Type | Description |
|---|---|---|
| `annual_volume` | string\|null | Amex annual volume |
| `average_ticket` | string\|null | Amex average ticket |
| `amex_program` | string\|null | e.g. OptBlue, Direct |
| `amex_merchant_number` | string\|null | Amex merchant number |
| `opt_out_of_marketing` | boolean\|null | Marketing opt-out flag |
| `arc_iata_number` | string\|null | ARC/IATA number |

**RecurringFee fields:**

| Field | Type | Description |
|---|---|---|
| `fee_name` | string | Fee name |
| `amount` | string\|null | Fee amount |
| `frequency` | string | `Monthly`, `Annually`, `Per Occurrence`, `One-Time` |

---

#### `processing_details` — ProcessingDetails

```json
{
  "card_swiped_pct": "80%",
  "keyed_with_imprint_pct": "10%",
  "b2b_consumer_pct": "100%",
  "face_to_face_pct": "90%",
  "inbound_telephone_pct": "5%",
  "future_delivery_volume_pct": "0%",
  "signature_obtained": "Yes",
  "consumer_charged": "No",
  "credit_card_via_website": false
}
```

| Field | Type | Description |
|---|---|---|
| `card_swiped_pct` | string\|null | % of card-swiped transactions |
| `keyed_with_imprint_pct` | string\|null | % of keyed with imprint |
| `b2b_consumer_pct` | string\|null | % B2B vs consumer |
| `face_to_face_pct` | string\|null | % face-to-face transactions |
| `inbound_telephone_pct` | string\|null | % inbound telephone orders |
| `future_delivery_volume_pct` | string\|null | % future delivery volume |
| `signature_obtained` | string\|null | Signature obtained flag |
| `consumer_charged` | string\|null | Consumer charged flag |
| `credit_card_via_website` | boolean\|null | Accepts cards via website |

---

#### `owners_officers` — List[OwnerOfficer]

JSON array — one object per owner or officer.

```json
[
  {
    "name": "Chester Brown",
    "title": "Owner",
    "ownership_pct": "100%",
    "address": "456 Oak Ave",
    "city_state_zip": "Springfield, IL 62701",
    "email": "chester@chetshoes.com",
    "home_phone": "555-222-3333",
    "cell_phone": "555-444-5555",
    "dob": "[MASKED]",
    "ssn_last4": "[MASKED]",
    "drivers_license_last4": "[MASKED]",
    "length_at_address": "10 years",
    "citizenship": "US"
  }
]
```

| Field | Type | Description |
|---|---|---|
| `name` | string | Required — owner/officer full name |
| `title` | string\|null | Title e.g. Owner, President, CEO |
| `ownership_pct` | string\|null | Ownership percentage |
| `address` | string\|null | Home address |
| `city_state_zip` | string\|null | City, state, ZIP |
| `email` | string\|null | Personal email |
| `home_phone` | string\|null | Home phone |
| `cell_phone` | string\|null | Cell phone |
| `dob` | string\|null | Date of birth — masked by Cloud DLP |
| `ssn_last4` | string\|null | SSN last 4 digits — masked by Cloud DLP |
| `drivers_license_last4` | string\|null | DL last 4 digits — masked by Cloud DLP |
| `length_at_address` | string\|null | Years at address |
| `citizenship` | string\|null | Citizenship |

---

#### `banking_information` — BankingInformation

```json
{
  "funding_option": "Standard",
  "accounts": [
    {
      "bank_name": "First National Bank",
      "name_on_account": "Chet Shoes LLC",
      "bank_address": "789 Bank St, Springfield, IL 62701",
      "bank_phone": "555-666-7777",
      "product_services": "Card/Gift",
      "transfer_method": "Both",
      "routing_number": "[MASKED]",
      "account_number_masked": "[MASKED]",
      "account_type": "Checking"
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `funding_option` | string\|null | e.g. Standard, Extended, Next Day |
| `accounts` | array | List of BankingAccount objects (see below) |

**BankingAccount fields:**

| Field | Type | Description |
|---|---|---|
| `bank_name` | string | Required — bank name |
| `name_on_account` | string\|null | Account holder name |
| `bank_address` | string\|null | Bank address |
| `bank_phone` | string\|null | Bank phone |
| `product_services` | string\|null | Account product/services |
| `transfer_method` | string\|null | e.g. Both, Debit Only, Credit Only |
| `routing_number` | string\|null | Routing number — masked by Cloud DLP |
| `account_number_masked` | string\|null | Masked account number — masked by Cloud DLP |
| `account_type` | string\|null | Checking or Savings |

---

## Table 2: `audit_events`

Append-only event log. One row written per pipeline stage via `delivery/bigquery_client.write_audit_event()`.

### Schema

| Column | BQ Type | Mode | Description |
|---|---|---|---|
| `contract_id` | STRING | REQUIRED | Contract this event belongs to |
| `stage` | STRING | REQUIRED | Pipeline stage — see values below |
| `event` | STRING | REQUIRED | Event name — see values below |
| `details` | JSON | NULLABLE | Stage-specific metadata |
| `timestamp` | STRING | REQUIRED | ISO 8601 UTC timestamp |

### Stage and Event Values

| `stage` | `event` | `details` fields |
|---|---|---|
| `extraction` | `document_ai_started` | — |
| `extraction` | `document_ai_complete` | `page_count`, `cache_hit` |
| `extraction` | `dlp_started` | — |
| `extraction` | `dlp_complete` | `pii_types` (list of detected PII type names), `cache_hit` |
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
| `review` | `human_review_decision` | `reviewer`, `decision`, `notes` |

### Example Row

```json
{
  "contract_id": "CNT-20240115-abc123",
  "stage": "validation",
  "event": "llm_judge_complete",
  "details": {
    "confidence_score": 0.91,
    "verdict": "Approved",
    "issues": [],
    "critical_failures": []
  },
  "timestamp": "2024-01-15T14:32:10.123456+00:00"
}
```

---

## Sample Queries

**Get all contracts pending review:**
```sql
SELECT
  contract_id,
  JSON_VALUE(company_information, '$.legal_name') AS merchant_name,
  confidence_score,
  extraction_status,
  extracted_at
FROM `<project>.<dataset>.contracts`
WHERE extraction_status = 'Review Required'
ORDER BY extracted_at DESC;
```

**Get full pipeline audit trail for a contract:**
```sql
SELECT stage, event, details, timestamp
FROM `<project>.<dataset>.audit_events`
WHERE contract_id = 'CNT-20240115-abc123'
ORDER BY timestamp ASC;
```

**Get all approved contracts with merchant name and billing model:**
```sql
SELECT
  contract_id,
  JSON_VALUE(company_information, '$.legal_name') AS merchant_name,
  JSON_VALUE(credit_card_pricing, '$.billing_model')       AS billing_model,
  JSON_VALUE(credit_card_pricing, '$.annual_volume')       AS annual_volume,
  confidence_score,
  curated_gcs_uri
FROM `<project>.<dataset>.contracts`
WHERE extraction_status = 'Approved'
ORDER BY extracted_at DESC;
```

**Get all contracts reviewed by a specific analyst:**
```sql
SELECT
  contract_id,
  JSON_VALUE(company_information, '$.legal_name') AS merchant_name,
  reviewed_by,
  extraction_status,
  review_notes,
  reviewed_at
FROM `<project>.<dataset>.contracts`
WHERE reviewed_by = '<reviewer_name>'
ORDER BY reviewed_at DESC;
```

**Count contracts by status:**
```sql
SELECT extraction_status, COUNT(*) AS total
FROM `<project>.<dataset>.contracts`
GROUP BY extraction_status
ORDER BY total DESC;
```

**Get PII types detected per contract:**
```sql
SELECT
  contract_id,
  JSON_VALUE(details, '$.pii_types') AS pii_types,
  timestamp
FROM `<project>.<dataset>.audit_events`
WHERE event = 'dlp_complete'
ORDER BY timestamp DESC;
```

---

## Design Notes

- Nested Pydantic models are stored as `JSON` columns rather than flattened columns. This avoids schema migrations when the `ContractRecord` schema evolves and keeps the table structure simple.
- Use `JSON_VALUE(column, '$.field')` to extract a scalar from a JSON column.
- Use `JSON_QUERY(column, '$.field')` to extract a nested object or array.
- `audit_events` is append-only — never updated, only inserted via streaming. Do not run DML UPDATE/DELETE on this table.
- `contracts` is upserted via MERGE on `contract_id` — safe to re-run the pipeline for the same contract.
- PII fields (`dob`, `ssn_last4`, `drivers_license_last4`, `routing_number`, `account_number_masked`) are masked by Cloud DLP before reaching BigQuery.

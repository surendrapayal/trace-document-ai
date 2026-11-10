# TRACE Platform — Document Request Template

**Project:** Contract Intelligence Platform (TRACE)
**Requested By:** Platform Engineering Team
**Date:**
**Required By:**

---

## Purpose

The TRACE platform automates the extraction, interpretation, and normalization of merchant
processing contracts using AI. To build and validate the platform, we need the following
documents and information from the business team.

This request is split into two phases:
- **Phase 1 — POC** : Minimum needed to start building and validating the pipeline
- **Phase 2 — Production** : Full set needed before go-live

---

## Phase 1 — POC Requirements

> Target: Unblock development within the first 2 weeks.

### 1.1 Sample Contract Documents

We need sample merchant processing contracts to build and test the AI extraction pipeline.

| # | What We Need | Format | Quantity | Notes |
|---|---|---|---|---|
| 1 | Merchant processing agreements | PDF | 3–5 | Can be anonymized or synthetic |
| 2 | Contracts from at least 2 different processors | PDF | 2+ | e.g. Worldpay, TSYS, Fiserv |
| 3 | At least one pricing schedule document | PDF | 1 | Standalone or embedded in contract |
| 4 | At least one contract with a fee schedule | PDF | 1 | Any format |

**Anonymization:** If real contracts contain sensitive merchant data, please anonymize or
redact merchant names, addresses, and identifiers before sharing. The contract structure
and pricing data should remain intact.

**Provided By:** ___________________________
**Date Provided:** ___________________________

---

### 1.2 Core Field List (Canonical Schema)

We need to know which fields to extract from every contract. Please fill in the table below
or attach an existing field specification document.

| # | Field Name | Description | Example Value | Mandatory? |
|---|---|---|---|---|
| 1 | Contract ID | Unique contract reference | CNT-12345 | Yes |
| 2 | Merchant Name | Legal name of the merchant | ABC Retail Ltd | Yes |
| 3 | Processor Name | Payment processor name | Worldpay | Yes |
| 4 | Effective Date | Contract start date | 2026-01-01 | Yes |
| 5 | Expiration Date | Contract end date | 2028-01-01 | No |
| 6 | Billing Model | Pricing model type | IC++, Flat Rate, Tiered | Yes |
| 7 | Pricing Schedule | Rate and fee structure | discount_rate: 2.30% | Yes |
| 8 | Fees | List of named fees and amounts | Authorization Fee: $0.05 | Yes |
| 9 | Renewal Terms | Auto-renewal conditions | Auto-renews 30 days before expiry | No |
| 10 | Termination Clauses | Early termination conditions | 90-day notice required | No |
| 11 | _(add more rows as needed)_ | | | |

**Additional fields not listed above:**

```
(Please list any additional fields the business requires extracted)




```

**Provided By:** ___________________________
**Date Provided:** ___________________________

---

### 1.3 RAG Reference Material (Draft Acceptable)

The AI uses reference documents to ground its extraction and avoid hallucination.
Draft or partial documents are acceptable for POC.

| # | What We Need | Format | Notes |
|---|---|---|---|
| 1 | Processor playbook (at least 1) | PDF / Word / Text | How a specific processor structures their contracts |
| 2 | Fee name glossary | Excel / Word / Text | Maps processor fee names to standard names e.g. "Auth Fee" = "Authorization Fee" |
| 3 | Pricing model descriptions | Word / Text | Brief description of IC++, flat rate, tiered pricing |

**Provided By:** ___________________________
**Date Provided:** ___________________________

---

## Phase 2 — Production Requirements

> Target: Complete before go-live. Can be gathered in parallel with POC development.

### 2.1 Complete Contract Coverage

| # | What We Need | Notes |
|---|---|---|
| 1 | Contracts from ALL supported processors | One sample per processor format |
| 2 | Edge case contracts | Unusual formats, missing fields, multi-page pricing tables |
| 3 | Contract amendments and addenda samples | To validate amendment handling |
| 4 | Rate cards and pricing exhibits | Standalone pricing documents |

**Provided By:** ___________________________
**Date Provided:** ___________________________

---

### 2.2 Complete Canonical Schema

| # | What We Need | Notes |
|---|---|---|
| 1 | Full finalized field list | All fields, not just core 10 |
| 2 | Data type per field | String, date, float, list, boolean |
| 3 | Validation rules per field | e.g. effective_date must not be in the past |
| 4 | Accepted enum values | e.g. billing_model: IC++, Flat Rate, Tiered, Interchange |
| 5 | Schema versioning approach | How changes are managed without breaking existing records |

**Provided By:** ___________________________
**Date Provided:** ___________________________

---

### 2.3 Complete RAG Knowledge Base

| # | What We Need | Notes |
|---|---|---|
| 1 | Processor playbooks for ALL processors | One per processor |
| 2 | Complete fee dictionary | All known fee name mappings |
| 3 | Pricing program reference guides | All pricing models in use |
| 4 | Standard contract clause templates | All clause types the platform should recognize |
| 5 | KB ownership & update process | Who maintains these documents and how often |

**Provided By:** ___________________________
**Date Provided:** ___________________________

---

### 2.4 Validation & Confidence Rules

| # | What We Need | Notes |
|---|---|---|
| 1 | Confidence threshold for auto-approval | e.g. score ≥ 0.85 = approved without human review |
| 2 | Confidence threshold for human review | e.g. score 0.60–0.85 = route to analyst |
| 3 | Confidence threshold for rejection | e.g. score < 0.60 = reject and re-process |
| 4 | Field importance weights | Which fields are critical vs low priority for scoring |
| 5 | Definition of extraction completeness | Minimum fields required for a contract to be approved |

**Business Sign-Off Required:** ___________________________
**Date Signed Off:** ___________________________

---

### 2.5 Human Review Workflow Rules

| # | What We Need | Notes |
|---|---|---|
| 1 | Reviewer role assignments | Which analyst reviews which processor or contract type |
| 2 | Review SLA | How long a contract can sit in the review queue before escalation |
| 3 | Escalation rules | What happens when SLA is breached or reviewer rejects a contract |
| 4 | Maximum retry count | How many times a rejected contract is re-processed before manual intervention |
| 5 | Audit retention period | How long reviewer decisions must be retained |

**Provided By:** ___________________________
**Date Provided:** ___________________________

---

### 2.6 Access & Security

| # | What We Need | Notes |
|---|---|---|
| 1 | List of users per role | Platform Admin, Data Scientist, Contract Analyst, Business Consumer |
| 2 | Google Workspace domain | For SSO configuration |
| 3 | Data residency requirements | Which GCP region must data be stored in |
| 4 | Data retention policy | How long contracts, audit records, and JSON outputs are kept |
| 5 | Encryption key ownership | Who owns and manages CMEK keys |
| 6 | Any regulatory / compliance requirements | PCI-DSS, GDPR, SOC2 etc. |

**Provided By:** ___________________________
**Date Provided:** ___________________________

---

### 2.7 Operational & Integration Details

| # | What We Need | Notes |
|---|---|---|
| 1 | Contract upload mechanism | Manual upload, SFTP drop, API push, or another system |
| 2 | Expected contract volume | Contracts per day, peak volume |
| 3 | Downstream system details | Which systems consume the JSON output and how |
| 4 | Notification requirements | Who gets alerted when a contract is processed or fails |
| 5 | Disaster recovery requirements | RTO (recovery time) and RPO (recovery point) targets |

**Provided By:** ___________________________
**Date Provided:** ___________________________

---

## Checklist Summary

### Phase 1 — POC (Complete to unblock development)

- [ ] 1.1 — Sample contract PDFs (3–5, at least 2 processors)
- [ ] 1.2 — Core field list (8–10 fields minimum)
- [ ] 1.3 — RAG reference material (1–2 draft documents)

### Phase 2 — Production (Complete before go-live)

- [ ] 2.1 — Complete contract coverage (all processors + edge cases)
- [ ] 2.2 — Finalized canonical schema (all fields + validation rules)
- [ ] 2.3 — Complete RAG knowledge base (all processors + fee dictionary)
- [ ] 2.4 — Confidence & validation rules (business signed off)
- [ ] 2.5 — HITL workflow rules (SLA, escalation, retry)
- [ ] 2.6 — Access & security details (IAM, SSO, data residency)
- [ ] 2.7 — Operational & integration details (volume, upstream, downstream)

---

## How to Submit

| Method | Details |
|---|---|
| Documents | Share via _(shared drive / email / Confluence link)_ |
| Field list | Fill in Section 1.2 table above or attach spreadsheet |
| Questions | Contact _(platform team contact)_ |

---

## Notes & Assumptions

```
(Business team to fill in any constraints, assumptions, or clarifications here)




```

---

**Document Version:** 1.0
**Last Updated:**
**Next Review:**

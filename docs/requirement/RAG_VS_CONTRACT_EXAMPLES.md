# TRACE Platform — RAG Knowledge Base vs Contract Processing Examples

---

## Side-by-Side Comparison

```
RAG Knowledge Base                        Contract Processing
──────────────────────────────────────    ──────────────────────────────────────
Generic domain knowledge                  Specific merchant contract
Loaded ONCE, reused for ALL contracts     Processed ONCE per contract upload
Helps LLM understand the language         The actual document to extract from
Written by your internal team             Provided by merchant / processor
────────────────────────────────────────────────────────────────────────────────
```

---

## Example 1 — Fee Dictionary (RAG Knowledge Base)

This is a reference document your team creates and loads into Vector Search.
It teaches the LLM that different processors use different names for the same fee.

**Filename:** `rag/fee_dictionary.txt`

```
FEE NAME DICTIONARY — CANONICAL MAPPINGS
=========================================

AUTHORIZATION FEES
------------------
Canonical Name : Authorization Fee
Also known as  : Auth Fee, Txn Auth Fee, Authorization Charge,
                 Per Auth Fee, Transaction Authorization Fee,
                 Auth Transaction Fee
Processors     : Worldpay uses "Auth Fee"
                 TSYS uses "Authorization Charge"
                 Fiserv uses "Per Auth Fee"
Unit           : Per transaction (USD)
Typical range  : $0.03 – $0.10

MONTHLY SERVICE FEE
-------------------
Canonical Name : Monthly Service Fee
Also known as  : Monthly Maintenance Fee, Account Maintenance Fee,
                 Monthly Account Fee, Service Charge
Processors     : Worldpay uses "Monthly Maintenance Fee"
                 TSYS uses "Account Maintenance Fee"
Unit           : Per month (USD)
Typical range  : $5.00 – $25.00

CHARGEBACK FEE
--------------
Canonical Name : Chargeback Fee
Also known as  : Dispute Fee, Retrieval Fee, Chargeback Processing Fee,
                 Dispute Processing Fee
Processors     : Worldpay uses "Dispute Fee"
                 TSYS uses "Chargeback Processing Fee"
Unit           : Per chargeback (USD)
Typical range  : $15.00 – $35.00

BATCH SETTLEMENT FEE
--------------------
Canonical Name : Batch Settlement Fee
Also known as  : Batch Fee, Daily Settlement Fee, Batch Close Fee,
                 Settlement Processing Fee
Unit           : Per batch (USD)
Typical range  : $0.10 – $0.30
```

---

## Example 2 — Processor Playbook (RAG Knowledge Base)

This teaches the LLM how a specific processor structures their contracts.

**Filename:** `rag/worldpay_playbook.txt`

```
WORLDPAY CONTRACT PLAYBOOK
===========================

DOCUMENT STRUCTURE
------------------
Worldpay contracts typically follow this structure:
  Section 1  : Merchant Information
  Section 2  : Processing Terms
  Section 3  : Pricing Schedule (most important)
  Section 4  : Fee Schedule
  Section 5  : Special Provisions
  Exhibit A  : Rate Card
  Exhibit B  : Equipment Schedule (if applicable)

PRICING MODEL TERMINOLOGY
--------------------------
Worldpay uses the following terms for billing models:
  "Interchange Plus Plus (IC++)" = Interchange + Worldpay markup + per-transaction fee
  "Flat Rate"                    = Single blended rate for all card types
  "Tiered"                       = Qualified / Mid-qualified / Non-qualified rates

The "Discount Rate" in Worldpay contracts refers to the
Worldpay markup ONLY — it does not include interchange.
Total merchant cost = Interchange + Discount Rate + Auth Fee.

EFFECTIVE DATE
--------------
Worldpay states the effective date in two places:
  1. Cover page — "Agreement Date" (signing date, NOT the effective date)
  2. Section 2.1 — "Processing Commencement Date" (this is the true effective date)
Always use "Processing Commencement Date" as effective_date in the schema.

RENEWAL TERMS
-------------
Standard Worldpay renewal clause is in Section 6.2.
Auto-renews for 1-year terms unless written notice given 30 days before expiry.
Look for the phrase "automatically renew for successive one-year terms".

TERMINATION
-----------
Early termination fee is in Section 7.1.
Worldpay calls it "Early Termination Fee (ETF)".
Typical ETF = $295 flat or remaining months x monthly minimum.
```

---

## Example 3 — Pricing Model Guide (RAG Knowledge Base)

This teaches the LLM what pricing models mean so it can classify them correctly.

**Filename:** `rag/pricing_models.txt`

```
PRICING MODEL REFERENCE GUIDE
==============================

IC++ (INTERCHANGE PLUS PLUS)
-----------------------------
Definition : Merchant pays actual interchange cost set by card networks
             (Visa/Mastercard) PLUS a fixed processor markup PLUS a
             per-transaction fee.
Structure  :
  Total Cost = Interchange Rate + Processor Markup + Per-Transaction Fee
  Example   : 1.80% interchange + 0.30% markup + $0.10 per transaction

How to identify in a contract:
  - Look for the phrase "Interchange Plus" or "Cost Plus"
  - Pricing schedule will show markup % separately from interchange
  - Will reference Visa/MC interchange tables

Canonical value : "IC++"

─────────────────────────────────────────────────────────

FLAT RATE
---------
Definition : Single blended percentage rate applied to all transactions
             regardless of card type.
Structure  :
  Total Cost = Flat Rate % + Per-Transaction Fee (sometimes)
  Example   : 2.75% on all transactions

How to identify in a contract:
  - Single rate applies to Visa, Mastercard, Amex equally
  - No reference to interchange tables
  - Often seen in small merchant contracts

Canonical value : "Flat Rate"

─────────────────────────────────────────────────────────

TIERED
------
Definition : Transactions are bucketed into tiers — Qualified,
             Mid-Qualified, Non-Qualified — each with a different rate.
Structure  :
  Qualified rate     : Lowest — standard consumer debit/credit cards
  Mid-Qualified rate : Medium — rewards cards, manually keyed transactions
  Non-Qualified rate : Highest — corporate cards, international cards

How to identify in a contract:
  - Look for "Qualified", "Mid-Qual", "Non-Qual" rate columns
  - Three distinct rate rows in the pricing schedule table

Canonical value : "Tiered"
```

---

## Example 4 — Sample Contract PDF Content (Contract Processing)

This is what a real merchant contract looks like — this goes through the
**pipeline** (Document AI → DLP → Gemini), NOT into the RAG index.

**Filename:** `contracts/raw/CNT-12345-worldpay-abc-merchant.pdf`

```
════════════════════════════════════════════════════════
        WORLDPAY MERCHANT PROCESSING AGREEMENT
════════════════════════════════════════════════════════

Agreement Date: December 1, 2025

MERCHANT INFORMATION
────────────────────
Merchant Legal Name : ABC Retail Ltd
Merchant Address    : 123 High Street, London, EC1A 1BB
Business Type       : Retail — General Merchandise
Merchant ID         : WP-987654321

SECTION 2 — PROCESSING TERMS
──────────────────────────────
Processing Commencement Date : January 1, 2026
Agreement Term               : 36 months
Billing Model                : Interchange Plus Plus (IC++)

SECTION 3 — PRICING SCHEDULE
──────────────────────────────
Pricing Model    : IC++
Worldpay Markup  : 0.25%
Auth Fee         : $0.08 per transaction
Monthly Minimum  : $25.00

SECTION 4 — FEE SCHEDULE
──────────────────────────
Monthly Maintenance Fee  : $10.00 per month
Batch Fee                : $0.15 per batch
Dispute Fee              : $25.00 per dispute
PCI Compliance Fee       : $9.95 per month
Annual Fee               : $99.00 per year

SECTION 6.2 — RENEWAL TERMS
─────────────────────────────
This Agreement shall automatically renew for successive one-year
terms unless either party provides written notice of non-renewal
no less than thirty (30) days prior to the expiration of the
then-current term.

SECTION 7.1 — EARLY TERMINATION
─────────────────────────────────
In the event Merchant terminates this Agreement prior to the
expiration of the initial term, Merchant shall pay an Early
Termination Fee (ETF) of $295.00.

EXHIBIT A — RATE CARD
──────────────────────
Visa Credit (Consumer)      : Interchange + 0.25% + $0.08
Visa Debit                  : Interchange + 0.25% + $0.08
Mastercard Credit           : Interchange + 0.25% + $0.08
Mastercard Debit            : Interchange + 0.25% + $0.08
American Express            : Interchange + 0.35% + $0.10

════════════════════════════════════════════════════════
Merchant Signature: ___________________  Date: _________
Worldpay Signature: ___________________  Date: _________
════════════════════════════════════════════════════════
```

---

## How They Work Together in the Pipeline

```
STEP 1 — Contract uploaded to GCS
  └── contracts/raw/CNT-12345-worldpay-abc-merchant.pdf

STEP 2 — Document AI extracts raw text from the PDF
  └── "Auth Fee : $0.08 per transaction"
      "Dispute Fee : $25.00 per dispute"
      "Billing Model : Interchange Plus Plus (IC++)"

STEP 3 — Gemini receives:
  ├── Extracted contract text (from Document AI)       ← the CONTRACT
  └── RAG context chunks (from Vector Search)          ← the KNOWLEDGE BASE
      e.g. "Worldpay uses 'Auth Fee' = Authorization Fee"
           "IC++ means Interchange + markup + per-txn fee"
           "Use Processing Commencement Date as effective_date"

STEP 4 — Gemini extracts using combined context:
  └── Maps "Auth Fee" → "Authorization Fee"     (using fee dictionary)
      Maps "IC++"     → billing_model: "IC++"   (using pricing guide)
      Uses "Processing Commencement Date"        (using Worldpay playbook)

STEP 5 — Normalizer maps to canonical schema:
  └── {
        "contract_id"      : "CNT-12345",
        "merchant_name"    : "ABC Retail Ltd",
        "processor"        : "Worldpay",
        "effective_date"   : "2026-01-01",
        "billing_model"    : "IC++",
        "pricing_schedule" : { "markup_rate": "0.25%" },
        "fees": [
          { "fee_name": "Authorization Fee", "amount": "0.08" },
          { "fee_name": "Monthly Service Fee", "amount": "10.00" },
          { "fee_name": "Chargeback Fee", "amount": "25.00" },
          { "fee_name": "Batch Settlement Fee", "amount": "0.15" }
        ],
        "renewal_terms"    : { "auto_renew": true, "notice_days": 30 },
        "termination_terms": { "etf_amount": "295.00" },
        "confidence_score" : 0.96
      }
```

---

## Summary

| | RAG Knowledge Base | Contract Processing |
|---|---|---|
| Example files | `fee_dictionary.txt`, `worldpay_playbook.txt`, `pricing_models.txt` | `CNT-12345-worldpay-abc-merchant.pdf` |
| Created by | Your internal team | Merchant / Processor |
| Loaded into | Vertex AI Vector Search | Document AI pipeline |
| Used | Once, grounding every extraction | Once, per contract |
| Contains | Generic domain knowledge | Specific merchant data |
| Changes | When processors change terms | Every new contract |

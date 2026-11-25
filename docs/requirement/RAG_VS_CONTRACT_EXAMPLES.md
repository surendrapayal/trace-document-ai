# TRACE Platform — RAG Knowledge Base vs Contract Processing Examples

---

## The Core Distinction

There are two completely different types of documents in TRACE:

```
RAG Knowledge Base Documents              Contract Documents
──────────────────────────────────────    ──────────────────────────────────────
Plain .txt reference files                Merchant PDF contracts
Written by your team                      Provided by merchants / processors
Loaded ONCE into Vector Search            Processed ONCE per upload
Reused as grounding for ALL contracts     Each contract processed independently
Teach Gemini HOW to read contracts        The actual document to extract FROM
Stored in gs://<bucket>/kb/documents/     Stored in gs://<bucket>/raw/contracts/
Never go through Document AI              Go through full 7-stage pipeline
────────────────────────────────────────────────────────────────────────────────
```

The KB documents are not contracts. They are reference material — like a training
manual that tells Gemini what Heartland-specific terms mean and how to interpret them.

---

## Why This Matters — The Problem Without RAG

Consider this line from a Heartland IC++ contract:

```
Discount Rate: 0.910%
```

Without RAG, Gemini sees a percentage and has to guess:
- Is this the total rate the merchant pays?
- Is this a markup on top of interchange?
- Should this go in discount_rate_cp or discount_rate_cnp?

With RAG, the relevant chunk from `heartland_pricing_models.txt` is injected:

```
IC++ CONTRACT IDENTIFICATION
  - Single "Discount Rate" column (not split CP/CNP)
  - Interchange Calculation field = "Interchange Plus"
  - Discount rates are LOW (e.g. 0.910%) — this is the MARKUP only, not total cost
  - Total merchant cost = Interchange (set by Visa/MC) + Discount Rate + Trans Fee
```

Now Gemini knows exactly what 0.910% means and where to put it.

---

## Side-by-Side: RAG Knowledge Base vs Contract

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

## Example 1 — IC++ Contract (Chet Shoes LLC)

### What the contract text looks like (after Document AI OCR)

```
MID: 650000011273417          atlas Token: 4685796
Sales Rep: Lukas Turner       Role: isRM - Inbound and Market
SDR: Julia Wallis

COMPANY INFORMATION
-------------------
Merchant Legal Name : Chet Shoes LLC
Address             : 8870 Rendova St NE, Circle Pines, MN 55014
Phone               : (763) 253-1079
Website             : http://chetsshoes.com
Primary Contact     : Emily Dehmer  (612) 655-6313

CREDIT CARD PRICING
-------------------
Annual Volume : $800,000.00   Avg Ticket : $193.00   Network : Exchange
Interchange Calculation : Interchange Plus   Settlement Type : Monthly 5 bps

Type          Discount Rate   Trans Fee Dial   Trans Fee IP   Non-EMV Assessment Fee
Visa          0.910%          $0.2100          $0.2100        1.000%
Mastercard    0.910%          $0.2100          $0.2100        1.000%
Discover/JCB  0.910%          $0.2100          $0.2100        1.000%
Amex-AXP      0.910%          $0.2100          $0.2100        1.000%

RECURRING FEES
--------------
Minimum Discount Fee          $255.00    Monthly
Service/Mandate Fee           $33.50     Monthly
Annual Fee                    $0.00      Annually
Chargeback Fee                $25.00     Per Occurrence
Voice Authorization Fee       $0.65      Per Occurrence
Application Processing Fee    $0.00      One-Time
PCI Non-Compliance Fee        $125.00    Monthly
Payments Manager+ Discount    0.30%      Per Occurrence
Payments Manager+ Txn Fee     $0.20      Per Occurrence
```

### RAG chunks retrieved for this contract (top 5 from Vector Search)

The first 2000 chars of the masked contract text are embedded and queried against
Vector Search. The 5 most relevant KB chunks are returned. For this IC++ contract,
the retrieved chunks would be from:

**Chunk 1** — from `heartland_pricing_models.txt`:
```
IC++ (INTERCHANGE PLUS)
Heartland label : "Interchange Plus" in Interchange Calculation field
Settlement Type : "Monthly 5 bps"
How it works    : Merchant pays actual Visa/MC interchange cost
                  PLUS Heartland markup (the Discount Rate shown)
                  PLUS per-transaction fee
Identification  :
  ✓ Single "Discount Rate" column in pricing table
  ✓ Interchange Calculation = "Interchange Plus"
  ✓ Low discount rate (typically 0.5% – 1.5%)
```

**Chunk 2** — from `heartland_playbook.txt`:
```
PRICING TABLE COLUMNS
  Discount Rate : For IC++ contracts — shows as single "Discount Rate" column
  Trans Fee Dial : Transaction fee for dial-up terminal
  Trans Fee IP   : Transaction fee for IP terminal
  Non-EMV Assessment Fee : Fee for non-chip card transactions
```

**Chunk 3** — from `heartland_fee_dictionary.txt`:
```
Minimum Discount Fee    | Minimum Discount Fee  | Monthly minimum processing charge
Service/Mandate Fee     | Service Fee           | Monthly account maintenance fee
Payments Manager+ Disc  | PM+ Discount Rate     | Additional rate for PM+ channel
Payments Manager+ Txn   | PM+ Transaction Fee   | Additional per-txn for PM+ channel
```

**Chunk 4** — from `heartland_playbook.txt`:
```
RECURRING FEES TABLE
Standard Heartland recurring fees appear in this fixed order:
  1. Minimum Discount Fee    — monthly minimum processing fee
  2. Service/Mandate Fee     — monthly service fee
  ...
  8. Payments Manager+ Discount Rate
  9. Payments Manager+ Txn Fee
A fee of $0.00 means it is waived — still extract it with amount $0.00.
```

**Chunk 5** — from `heartland_playbook.txt`:
```
HEADER FIELDS
  "MID"         = Merchant ID — unique identifier assigned by Heartland
  "atlas Token" = Internal Heartland system token
  "SDR"         = Sales Development Representative name
```

### What Gemini extracts using contract text + RAG context

```json
{
  "processor_info": {
    "processor_name": "Heartland",
    "sales_rep_name": "Lukas Turner",
    "sales_rep_role": "isRM - Inbound and Market",
    "mid": "650000011273417",
    "atlas_token": "4685796",
    "sdr_name": "Julia Wallis"
  },
  "credit_card_pricing": {
    "annual_volume": "$800,000.00",
    "avg_ticket": "$193.00",
    "network": "Exchange",
    "interchange_calculation": "Interchange Plus",
    "settlement_type": "Monthly 5 bps",
    "billing_model": "IC++",
    "card_rates": [
      {
        "card_type": "Visa",
        "discount_rate_cp": "0.910%",
        "trans_fee_dial": "$0.2100",
        "trans_fee_ip": "$0.2100",
        "non_emv_assessment_fee": "1.000%"
      }
    ],
    "recurring_fees": [
      { "fee_name": "Minimum Discount Fee", "amount": "$255.00", "frequency": "Monthly" },
      { "fee_name": "Service/Mandate Fee",  "amount": "$33.50",  "frequency": "Monthly" },
      { "fee_name": "Annual Fee",           "amount": "$0.00",   "frequency": "Annually" },
      { "fee_name": "Chargeback Fee",       "amount": "$25.00",  "frequency": "Per Occurrence" },
      { "fee_name": "PCI Non-Compliance Fee","amount": "$125.00","frequency": "Monthly" }
    ]
  }
}
```

**What RAG enabled here:**
- `billing_model: "IC++"` — Gemini knew "Interchange Plus" maps to "IC++" from the pricing models chunk
- `discount_rate_cp: "0.910%"` — Gemini knew the single Discount Rate column in IC++ goes to `discount_rate_cp`, not `discount_rate_cnp`
- `$0.00` fees were still extracted — Gemini knew from the playbook chunk that $0.00 = waived, not missing
- `atlas_token` was correctly identified — Gemini knew "atlas Token" is an internal Heartland field from the header chunk

---

## Example 2 — Flat Rate Contract (Fitchburg Historical Society)

### What the contract text looks like (after Document AI OCR)

```
Sales Rep: Sterling Jackson    Role: TM
Affiliate ID: FSBFMAS          atlas Token: 4802548

COMPANY INFORMATION
-------------------
Merchant Legal Name : Fitchburg Historical Society
Address             : 781 Main Street, Fitchburg, MA 01420
HIC Admin           : Susan Navarre  director@fitchburghistoricalsociety.com

CREDIT CARD PRICING
-------------------
Annual Volume : $15,000.00   Avg Ticket : $25.00   Network : Exchange
Interchange Calculation : Flat Rate   Settlement Type : Monthly 0 bps

Type          Discount CP   Discount CNP   Trans Fee CP   Trans Fee CNP   Non-EMV
Visa          2.600%        2.900%         $0.1000        $0.3000         1.000%
Mastercard    2.600%        2.900%         $0.1000        $0.3000         1.000%
Discover/JCB  2.600%        2.900%         $0.1000        $0.3000         1.000%
Amex-AXP      2.600%        2.900%         $0.1000        $0.3000         1.000%

MERCHANT DETAILS
----------------
Business Type    : Private
Ownership Type   : Tax Exempt
Tax ID           : 04-6060118
New/Existing     : Switching to Heartland
Length           : > 15 years
```

### RAG chunks retrieved for this contract

For this Flat Rate contract, Vector Search returns different chunks because the
contract text mentions "Flat Rate" and "Tax Exempt" — different semantic content
pulls different chunks from the KB.

**Chunk 1** — from `heartland_pricing_models.txt`:
```
FLAT RATE
Heartland label : "Flat Rate" in Interchange Calculation field
Settlement Type : "Monthly 0 bps"
How it works    : Merchant pays a single fixed rate regardless of card type
                  Rate is split into Card Present (CP) and Card Not Present (CNP)
Identification  :
  ✓ Two discount columns: "Discount CP" and "Discount CNP"
  ✓ Higher discount rates (typically 2.5% – 3.5%)
```

**Chunk 2** — from `heartland_playbook.txt`:
```
PRICING TABLE COLUMNS
  Discount CP  : For Flat Rate — Card Present discount rate
  Discount CNP : For Flat Rate — Card Not Present discount rate
  Trans Fee CP : Transaction fee Card Present
  Trans Fee CNP: Transaction fee Card Not Present
```

**Chunk 3** — from `heartland_merchant_types.txt`:
```
OWNERSHIP TYPES
  Tax Exempt : Non-profit / charitable organization (has EIN starting with 04-, 84- etc.)

NEW/EXISTING BUSINESS VALUES
  "Switching to Heartland" : Merchant currently processes with another provider
```

### What RAG enabled here (vs IC++ contract)

- `billing_model: "Flat Rate"` — Gemini knew "Flat Rate" in the Interchange Calculation field maps to the Flat Rate billing model
- `discount_rate_cp: "2.600%"` and `discount_rate_cnp: "2.900%"` — Gemini knew the two-column layout means CP and CNP rates, not a single markup
- `ownership_type: "Tax Exempt"` — Gemini knew this is a valid Heartland ownership type for non-profits
- `new_existing_business: "Switching to Heartland"` — Gemini knew this exact phrase is a valid enum value

**Key difference from IC++ extraction:**
The same Gemini model, the same prompt template, but different RAG chunks were
retrieved — because the contract text was semantically different. Vector Search
automatically surfaced the Flat Rate chunks for this contract and the IC++ chunks
for Chet Shoes LLC. This is the power of semantic retrieval.

---

## How They Work Together in the Pipeline

```
STEP 1 — Contract PDF uploaded to GCS raw zone
  └── gs://<bucket>/raw/contracts/CNT-XXX/contract.pdf

STEP 2 — Document AI extracts raw text (Stage 1)
  └── full_text: "Interchange Calculation: Interchange Plus  Settlement: Monthly 5 bps
                  Discount Rate: 0.910%  Trans Fee IP: $0.2100 ..."

STEP 3 — Cloud DLP masks PII (Stage 2)
  └── masked_text: same text but SSN, DOB, routing numbers replaced with [MASKED]

STEP 4 — RAG retrieval (Stage 3)
  ├── embed first 2000 chars of masked_text → 768-dim query vector
  ├── Vector Search finds 5 nearest KB chunk vectors
  ├── fetch 5 chunk .txt files from gs://<bucket>/kb/chunks/
  └── rag_context = joined chunk texts

STEP 5 — Gemini extraction (Stage 4) — 7 prompts, each receives:
  ├── {contract_text} = masked_text          ← the contract being processed
  └── {rag_context}   = 5 KB chunks          ← the grounding reference material

  Gemini reads both together and extracts structured JSON for each section.

STEP 6 — Normalizer maps to ContractRecord (Stage 5)
  └── raw Gemini dict → typed Pydantic ContractRecord

STEP 7 — LLM Judge scores extraction quality (Stage 6)
  └── also receives rag_context — uses KB rules to validate extraction accuracy

STEP 8 — Delivery (Stage 7)
  └── routes to GCS curated / review queue / rejected based on confidence score
```

---

## Summary

| | RAG Knowledge Base | Contract Documents |
|---|---|---|
| File type | `.txt` plain text | `.pdf` merchant contracts |
| Created by | Your team (developer / analyst) | Merchants / processors |
| Stored in GCS | `kb/documents/` | `raw/contracts/` |
| Loaded into | Vertex AI Vector Search | Document AI pipeline |
| Used | Once indexed, grounding every extraction | Once per contract upload |
| Contains | Heartland domain rules, fee names, pricing model definitions | Specific merchant data, rates, owner info |
| Changes when | Heartland changes contract format or you add new processors | Every new merchant contract |
| Volume | 4 documents (~16–20 chunks total) | One per merchant onboarding |
| Retrieved per contract | Top 5 most relevant chunks via semantic search | N/A — full text extracted by Document AI |

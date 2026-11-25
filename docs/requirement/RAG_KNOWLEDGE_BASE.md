# TRACE Platform — RAG Knowledge Base
# Derived from: CHETSHOESLLC.pdf, FITCHBURG HISTORICAL SOCIETY.pdf
# Version: 1.0 (POC Seed)

---

## Why RAG Exists in TRACE

Gemini is a general-purpose LLM. It has no built-in knowledge of Heartland-specific
contract structure, fee names, pricing models, or field layouts. Without domain context,
Gemini would guess or hallucinate — for example:

- It would not know that "Interchange Plus" in the pricing bar means billing_model = "IC++"
- It would not know that a 0.910% discount rate in an IC++ contract is the markup only, not the total cost
- It would not know that "Monthly 5 bps" is the settlement type for IC++ contracts
- It would not know the fixed order of the 9 recurring fees in the Heartland fee table
- It would not know that "atlas Token" is an internal Heartland system identifier

RAG solves this by injecting Heartland-specific reference documents directly into every
Gemini prompt as grounding context. Gemini then extracts against known rules, not guesses.

---

## What RAG Is — Plain English

RAG stands for Retrieval-Augmented Generation.

Instead of asking Gemini to extract from the contract text alone, we first retrieve
relevant reference material from a knowledge base and inject it alongside the contract
text in the prompt. Gemini reads both together and uses the reference material to
interpret the contract correctly.

```
Without RAG:
  Gemini sees: "Discount Rate: 0.910%"
  Gemini guesses: some kind of rate, unclear meaning

With RAG:
  Gemini sees: "Discount Rate: 0.910%"
            + "IC++ contracts show a single Discount Rate column — this is the
               Heartland markup only, not the total cost. Total = Interchange + markup + txn fee."
  Gemini extracts: discount_rate_cp = "0.910%" correctly mapped to IC++ billing model
```

---

## The 4 Knowledge Base Documents

These are plain `.txt` files written manually by the developer / business analyst.
They encode domain expertise about Heartland contracts into text form.
They are uploaded once to GCS and indexed into Vertex AI Vector Search.

### Who creates them?
You (the developer or business analyst) write them based on your knowledge of
Heartland contracts. They are not auto-generated. Think of them as structured
reference notes that a human expert would use to train a new analyst.

### Where are they stored?
```
gs://<GCS_BUCKET>/kb/documents/heartland_playbook.txt
gs://<GCS_BUCKET>/kb/documents/heartland_fee_dictionary.txt
gs://<GCS_BUCKET>/kb/documents/heartland_pricing_models.txt
gs://<GCS_BUCKET>/kb/documents/heartland_merchant_types.txt
```

### When are they loaded?
Once, before any contract is processed. After uploading to GCS, run:
```bash
python -m trace_ai.knowledge_base.kb_indexer
```
This chunks, embeds, and indexes all 4 documents into Vector Search.

---

## File 1 — heartland_playbook.txt

```
HEARTLAND PAYMENT SYSTEMS — CONTRACT PLAYBOOK
==============================================

DOCUMENT STRUCTURE
------------------
Heartland contracts follow this fixed 4-page structure:
  Page 1 : Application header + Company Information + Credit Card Pricing
  Page 2 : Merchant Details (compliance questions)
  Page 3 : Processing Details + Owner/Officers/Contacts + Banking Information
  Page 4 : Terms and Conditions (signatures)

HEADER FIELDS
-------------
The application header contains processor-assigned identifiers:
  "MID"         = Merchant ID — unique identifier assigned by Heartland
                  e.g. MID: 650000011273417
  "atlas Token" = Internal Heartland system token
                  e.g. atlas Token: 4685796
  "SDR"         = Sales Development Representative name
  "Affiliate ID"= Partner/affiliate identifier (not always present)
                  e.g. Affiliate ID: FSBFMAS

SALES REP ROLES
---------------
  "isRM - Inbound and Market" = Inbound sales representative
  "TM"                        = Territory Manager

SALES REP CONTACT
-----------------
  sales_rep_phone : Phone number listed next to the sales rep name in the header
  sdr_name        : SDR field — Sales Development Representative, separate from sales rep

COMPANY INFORMATION SECTION
----------------------------
Contains two address blocks:
  Block 1 (top)  : Primary business address (DBA address)
  Block 2 (Legal): Legal registered address — use this as merchant_address
                   if different from primary

Primary contact = "Primary" field — authorized decision maker
HIC Admin       = Heartland portal admin contact

CREDIT CARD PRICING SECTION
-----------------------------
The pricing summary bar shows 5 key values left to right:
  Column 1 : Annual Volume     — projected annual processing volume
  Column 2 : Avg Ticket        — average transaction amount
  Column 3 : Network           — always "Exchange" for Heartland
  Column 4 : Interchange Calculation — this is the BILLING MODEL
             "Interchange Plus" = IC++ billing model
             "Flat Rate"        = Flat Rate billing model
  Column 5 : Settlement Type   — "Monthly 5 bps" or "Monthly 0 bps"

PRICING TABLE COLUMNS
---------------------
The card rate table has these columns:
  Type              : Card type (Visa, Mastercard, Discover/JCB, Amex-AXP)
  Discount Rate     : For IC++ contracts — shows as single "Discount Rate" column
  Discount CP       : For Flat Rate — Card Present discount rate
  Discount CNP      : For Flat Rate — Card Not Present discount rate
  Discount Per Item : Per-item discount (usually blank)
  Trans Fee Dial    : Transaction fee for dial-up terminal
  Trans Fee IP      : Transaction fee for IP terminal
  Trans Fee CP      : Transaction fee Card Present
  Trans Fee CNP     : Transaction fee Card Not Present
  Non-EMV Assessment Fee : Fee for non-chip card transactions

IC++ CONTRACT IDENTIFICATION
-----------------------------
  - Single "Discount Rate" column (not split CP/CNP)
  - Interchange Calculation field = "Interchange Plus"
  - Settlement Type = "Monthly 5 bps"
  - Discount rates are LOW (e.g. 0.910%) — this is the MARKUP only, not total cost
  - Total merchant cost = Interchange (set by Visa/MC) + Discount Rate + Trans Fee

FLAT RATE CONTRACT IDENTIFICATION
----------------------------------
  - Two discount columns: "Discount CP" and "Discount CNP"
  - Interchange Calculation field = "Flat Rate"
  - Settlement Type = "Monthly 0 bps"
  - Discount rates are HIGHER (e.g. 2.600% CP, 2.900% CNP) — this IS the total rate
  - No interchange passthrough — merchant pays fixed rate regardless of card type

RECURRING FEES TABLE
--------------------
Standard Heartland recurring fees appear in this fixed order:
  1. Minimum Discount Fee    — monthly minimum processing fee
  2. Service/Mandate Fee     — monthly service fee
  3. Annual Fee              — yearly fee
  4. Chargeback Fee          — per dispute/chargeback
  5. Voice Authorization Fee — per manual voice auth
  6. Application Processing Fee — one-time setup fee
  7. PCI Non-Compliance Fee  — monthly fee if not PCI compliant
  8. Payments Manager+ Discount Rate — additional rate for PM+ transactions
  9. Payments Manager+ Txn Fee       — additional per-txn fee for PM+ transactions

A fee of $0.00 means it is waived for this merchant — still extract it with amount $0.00.

MERCHANT DETAILS SECTION
-------------------------
Contains compliance and risk questions — all Yes/No answers.
Key fields to extract:
  Business Type             : Private / Non-Profit / Government
  Ownership Type            : LLC Corporation / Tax Exempt / Sole Proprietor / Partnership
  Tax ID                    : Federal EIN (format: XX-XXXXXXX)
  Services                  : Business category description
  New/Existing              : "Open-New to Card" / "Switching to Heartland" / "Existing"
  Length in Business        : e.g. "< 1 year", "> 15 years", "1-3 years"
  Number of Terminals       : Integer
  PCI Compliant             : Yes/No → boolean true/false
  Deposit Method            : e.g. "ACH", "Check"
  Dispute Letter Mailing    : Yes/No — whether dispute letters are sent by mail
  Dispute Letter Electronic : Yes/No — whether dispute letters are sent electronically
  Statement Type            : e.g. "Online", "Paper"
  Card Acceptance           : e.g. "Credit and Debit"

PROCESSING DETAILS SECTION
---------------------------
Shows transaction method breakdown as percentages — must sum to 100%.
  Card Swiped %       : Physical card present, chip/swipe
  Keyed w/ Imprint %  : Manually keyed with card imprint
  B2B Consumer %      : Business-to-consumer percentage
  Face to Face %      : In-person transactions
  Inbound Telephone % : Phone orders
  Future Delivery %   : Orders fulfilled in future

ADDITIONAL PROCESSING FIELDS
-----------------------------
  Signature Obtained      : Yes/No — whether merchant obtains customer signature
  Consumer Charged        : Yes/No — whether consumer is charged at time of transaction
  Credit Card via Website : Yes/No — whether merchant accepts cards through a website
                            "Yes" -> true, "No" -> false

DOCUMENT GENERATION DATE
------------------------
Found at bottom right of each page:
  "Generated On: MM/DD/YYYY HH:MM A GMT-X"
  Use this as the document_generated_date field.
  This is NOT the contract effective date.
```

---

## File 2 — heartland_fee_dictionary.txt

```
HEARTLAND FEE NAME DICTIONARY
==============================

CANONICAL MAPPINGS
------------------

Heartland Term              | Canonical Name              | Notes
----------------------------|-----------------------------|---------------------------------
Minimum Discount Fee        | Minimum Discount Fee        | Monthly minimum processing charge
Service/Mandate Fee         | Service Fee                 | Monthly account maintenance fee
Annual Fee                  | Annual Fee                  | Yearly account fee
Chargeback Fee              | Chargeback Fee              | Per dispute processing fee
Voice Authorization Fee     | Voice Authorization Fee     | Per manual authorization call
Application Processing Fee  | Application Fee             | One-time setup/onboarding fee
PCI Non-Compliance Fee      | PCI Non-Compliance Fee      | Monthly fee if PCI not maintained
Payments Manager+ Discount  | PM+ Discount Rate           | Additional rate for PM+ channel
Payments Manager+ Txn Fee   | PM+ Transaction Fee         | Additional per-txn for PM+ channel
Non-EMV Assessment Fee      | Non-EMV Assessment Fee      | Surcharge for non-chip transactions
Discount Rate               | Processor Markup Rate       | IC++ contracts — markup only
Discount CP                 | Card Present Rate           | Flat Rate contracts
Discount CNP                | Card Not Present Rate       | Flat Rate contracts
Trans Fee Dial              | Dial Transaction Fee        | Per-txn fee for dial terminal
Trans Fee IP                | IP Transaction Fee          | Per-txn fee for IP terminal
Trans Fee CP                | Card Present Transaction Fee| Flat Rate per-txn CP
Trans Fee CNP               | Card Not Present Txn Fee    | Flat Rate per-txn CNP
```

---

## File 3 — heartland_pricing_models.txt

```
HEARTLAND PRICING MODELS
=========================

IC++ (INTERCHANGE PLUS)
------------------------
Heartland label : "Interchange Plus" in Interchange Calculation field
Settlement Type : "Monthly 5 bps"
How it works    : Merchant pays actual Visa/MC interchange cost
                  PLUS Heartland markup (the Discount Rate shown)
                  PLUS per-transaction fee

Example from contract (Chet Shoes LLC):
  Discount Rate  : 0.910%  ← Heartland markup only
  Trans Fee IP   : $0.2100 ← per transaction
  Total cost     : Interchange (varies by card) + 0.910% + $0.21

Who it suits    : Higher volume merchants (e.g. $800,000/year)
                  Benefits merchants with mostly debit/basic credit cards
                  as interchange is lower for those card types

Identification  :
  ✓ Single "Discount Rate" column in pricing table
  ✓ Interchange Calculation = "Interchange Plus"
  ✓ Settlement Type = "Monthly 5 bps"
  ✓ Low discount rate (typically 0.5% – 1.5%)

─────────────────────────────────────────────────────────────

FLAT RATE
---------
Heartland label : "Flat Rate" in Interchange Calculation field
Settlement Type : "Monthly 0 bps"
How it works    : Merchant pays a single fixed rate regardless of card type
                  Rate is split into Card Present (CP) and Card Not Present (CNP)
                  No interchange passthrough — rate is all-inclusive

Example from contract (Fitchburg Historical Society):
  Discount CP    : 2.600%  ← all-in rate for in-person transactions
  Discount CNP   : 2.900%  ← all-in rate for keyed/online transactions
  Trans Fee CP   : $0.1000 ← per transaction in-person
  Trans Fee CNP  : $0.3000 ← per transaction keyed/online

Who it suits    : Lower volume merchants (e.g. $15,000/year)
                  Simpler billing — predictable cost per transaction
                  Non-profits, small businesses, seasonal merchants

Identification  :
  ✓ Two discount columns: "Discount CP" and "Discount CNP"
  ✓ Interchange Calculation = "Flat Rate"
  ✓ Settlement Type = "Monthly 0 bps"
  ✓ Higher discount rates (typically 2.5% – 3.5%)
```

---

## File 4 — heartland_merchant_types.txt

```
HEARTLAND MERCHANT TYPE REFERENCE
===================================

OWNERSHIP TYPES
---------------
LLC Corporation  : Standard limited liability company
Tax Exempt       : Non-profit / charitable organization (has EIN starting with 04-, 84- etc.)
Sole Proprietor  : Individual business owner
Partnership      : Multi-owner business
Corporation      : C-Corp or S-Corp

OWNER/OFFICER FIELDS
---------------------
Each owner or officer entry on page 3 contains:
  name                  : Full name
  title                 : e.g. "Owner", "Officer", "Director"
  ownership_pct         : Ownership percentage e.g. "100%", "33%"
  address               : Street address
  city_state_zip        : City, state, zip
  email                 : Email address
  home_phone            : Home phone number
  cell_phone            : Cell phone number
  dob                   : Date of birth — will be masked by DLP e.g. "7/31/1992"
  ssn_last4             : SSN — shown masked e.g. "***-**-6306"
  drivers_license_last4 : Driver's license — shown masked e.g. "****8113"
  length_at_address     : How long at current address e.g. "5 years"
  citizenship           : e.g. "US Citizen"

NEW/EXISTING BUSINESS VALUES
------------------------------
"Open-New to Card"       : Merchant has never accepted cards before
"Switching to Heartland" : Merchant currently processes with another provider
"Existing"               : Existing Heartland merchant adding location or product

LENGTH IN BUSINESS
------------------
Standard values seen in Heartland contracts:
  "< 1 year"
  "1-3 years"
  "3-5 years"
  "5-10 years"
  "10-15 years"
  "> 15 years"

SERVICES / BUSINESS CATEGORY
------------------------------
Free-text field — examples seen:
  "Shoes-Retail"
  "Historical Organizations"
  "Restaurants"
  "Healthcare"
  "Professional Services"
```

---

## How the KB Documents Are Processed — Full Lifecycle

### Step 1 — Upload to GCS (manual, one-time)

Upload all 4 `.txt` files to the GCS KB bucket under the `documents/` prefix:

```
gs://<GCS_BUCKET>/kb/documents/heartland_playbook.txt
gs://<GCS_BUCKET>/kb/documents/heartland_fee_dictionary.txt
gs://<GCS_BUCKET>/kb/documents/heartland_pricing_models.txt
gs://<GCS_BUCKET>/kb/documents/heartland_merchant_types.txt
```

### Step 2 — Create the Vector Search Index (one-time, ~30–60 min)

```bash
python scripts/create_index.py
```

This creates an empty Vertex AI Vector Search index configured for:
- 768 dimensions (matches `text-embedding-004` output size)
- DOT_PRODUCT_DISTANCE with UNIT_L2_NORM (optimal for text embeddings)
- STREAM_UPDATE method (allows incremental upserts from kb_indexer)

Copy the 3 printed IDs into `.env`:
```
VERTEX_VECTOR_SEARCH_INDEX_ID=...
VERTEX_VECTOR_SEARCH_ENDPOINT_ID=...
VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID=trace-kb-deployed
```

### Step 3 — Index the Documents (`kb_indexer.py`)

```bash
python -m trace_ai.knowledge_base.kb_indexer
```

What happens inside `index_all()`:

```
For each .txt file in gs://<bucket>/kb/documents/:
    │
    ├── _read_blob()
    │       └── downloads the full text of the document
    │
    ├── _chunk_text()
    │       └── splits into 500-char chunks with 50-char overlap
    │           e.g. heartland_playbook.txt (4000 chars) → ~16 chunks
    │           overlap ensures context is not lost at chunk boundaries
    │
    ├── embed(chunks, task_type="RETRIEVAL_DOCUMENT")
    │       └── calls Vertex AI Embeddings API (text-embedding-004)
    │           each chunk → list[float] of 768 dimensions
    │           task_type="RETRIEVAL_DOCUMENT" signals these are documents to be stored
    │
    └── for each chunk:
            ├── chunk_id = uuid4()
            ├── _store_chunk()
            │       └── saves chunk text to gs://<bucket>/kb/chunks/<uuid>.txt
            └── appends { datapoint_id: chunk_id, feature_vector: [768 floats] }

After all documents:
    index.upsert_datapoints(batches of 100)
        └── writes all vectors into the Vector Search index
```

After this step, the index contains one vector per chunk. Each vector's ID is a UUID
that maps back to a `.txt` file in `gs://<bucket>/kb/chunks/`.

---

## How RAG Is Used Per Contract — Stage 3

During pipeline Stage 3, `rag_client.query()` runs for every contract:

```
1. Takes first 2000 chars of masked_text as the search query
   (enough to capture merchant name, business type, pricing section header)

2. embed_single(query_text, task_type="RETRIEVAL_QUERY")
   → converts query to a 768-dim vector
   note: task_type="RETRIEVAL_QUERY" is different from "RETRIEVAL_DOCUMENT" used at index time
   — this asymmetry is intentional, text-embedding-004 is optimised for asymmetric retrieval

3. index_endpoint.find_neighbors(queries=[query_vector], num_neighbors=5)
   → Vector Search finds the 5 stored chunk vectors closest to the query vector
   → returns 5 neighbor IDs (UUIDs)

4. For each neighbor ID:
   download_bytes(bucket, "kb/chunks/<neighbor_id>.txt")
   → fetches the actual text of that chunk from GCS

5. return "\n\n---\n\n".join(chunks)
   → all 5 chunk texts joined into one string = rag_context
```

This `rag_context` string is then injected into all 7 Gemini extraction prompts
alongside the contract text. Gemini reads both together.

---

## When to Re-index

Re-run `kb_indexer.py` whenever you:
- Add a new KB document to GCS
- Update an existing KB document (edit the `.txt` file and re-upload)
- Add support for a new processor (add a new playbook document)

```bash
python -m trace_ai.knowledge_base.kb_indexer
```

`upsert_datapoints()` is idempotent — re-indexing the same document generates new
chunk UUIDs and adds them alongside the old ones. To avoid stale duplicates, delete
the old chunks from GCS and clear the index before re-indexing updated documents.

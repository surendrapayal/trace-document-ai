# TRACE Platform — Heartland RAG Knowledge Base
# Derived from: CHETSHOESLLC.pdf, FITCHBURG HISTORICAL SOCIETY.pdf
# Version: 1.0 (POC Seed)

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
  Business Type       : Private / Non-Profit / Government
  Ownership Type      : LLC Corporation / Tax Exempt / Sole Proprietor / Partnership
  Tax ID              : Federal EIN (format: XX-XXXXXXX)
  Services            : Business category description
  New/Existing        : "Open-New to Card" / "Switching to Heartland" / "Existing"
  Length in Business  : e.g. "< 1 year", "> 15 years", "1-3 years"
  Number of Terminals : Integer
  PCI Compliant       : Yes/No → boolean true/false

PROCESSING DETAILS SECTION
---------------------------
Shows transaction method breakdown as percentages — must sum to 100%.
  Card Swiped %       : Physical card present, chip/swipe
  Keyed w/ Imprint %  : Manually keyed with card imprint
  B2B Consumer %      : Business-to-consumer percentage
  Face to Face %      : In-person transactions
  Inbound Telephone % : Phone orders
  Future Delivery %   : Orders fulfilled in future

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

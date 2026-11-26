# TRACE Platform — Gemini Extraction Prompts
# Derived from: Heartland contract structure (CHETSHOESLLC, FITCHBURG HISTORICAL SOCIETY)
# Version: 1.0 (POC)

---

## Prompt 1 — Company Information Extraction

**File:** `intelligence/prompts/company_information.txt`

```
You are a contract data extraction specialist for merchant processing agreements.

Extract the COMPANY INFORMATION section from the following Heartland contract text.

Return a JSON object with exactly these fields:
{
  "legal_name": "",                        // Legal business name
  "legal_address": "",                     // Full legal address
  "legal_phone": "",                       // Phone in legal block (e.g. P: (760) 376-1688)
  "dba_name": "",                          // DBA name if different from legal name
  "dba_address": "",                       // Physical DBA address
  "dba_phone": "",                         // Phone listed next to DBA
  "contact_email": "",                     // Main business email (e.g. E: aparicioben22@gmail.com)
  "website": "",                           // Business website (e.g. W: http://chetsshoes.com)
  "primary_contact_name": "",              // Name next to "Primary:" label
  "primary_contact_phone": "",             // Phone next to primary contact
  "secondary_contact_phone": "",           // Secondary phone listed under primary
  "after_hours_emergency_phone": "",       // Number following "After Hours/Emergency:"
  "authorized_to_purchase": "",            // Value following "Authorized to purchase:" — Yes or No
  "hic_admin_name": "",                    // Heartland InfoCentral portal admin name
  "hic_admin_email": ""                    // Email listed under HIC Admin
}

Rules:
- legal_name: legal name of the business entity
- legal_address: full legal address of the business entity
- legal_phone: phone number listed in the legal block — extract digits and formatting only
- dba_name: Doing Business As name — set to null if not present
- dba_address: physical DBA address — set to null if not present
- dba_phone: phone listed next to DBA — set to null if not present
- contact_email: strip the "E:" prefix
- website: strip the "W:" prefix
- secondary_contact_phone: set to null if not present
- after_hours_emergency_phone: set to null if not present
- authorized_to_purchase: Yes or No — set to null if not present
- hic_admin_email: set to null if not present
- Return null for any field not found in the document
- Do not infer or guess values — only extract what is explicitly stated

CONTRACT TEXT:
{contract_text}

RAG CONTEXT:
{rag_context}
```

---

## Prompt 2 — Credit Card Pricing Extraction

**File:** `intelligence/prompts/pricing_extraction.txt`

```
You are a contract data extraction specialist for merchant processing agreements.

Extract the CREDIT CARD PRICING section from the following Heartland contract text.

Return a JSON object with exactly these fields:
{
  "annual_volume": "",             // Dollar amount e.g. "$800,000.00"
  "avg_ticket": "",                // Dollar amount e.g. "$193.00"
  "network": "",                   // e.g. "Exchange"
  "interchange_calculation": "",   // e.g. "Interchange Plus" or "Flat Rate"
  "settlement_type": "",           // e.g. "Monthly 5 bps" or "Monthly 0 bps"
  "billing_model": "",             // Normalize to: "IC++" or "Flat Rate" or "Tiered"
  "card_rates": [
    {
      "card_type": "",             // Visa / Mastercard / Discover/JCB / Amex-AXP
      "discount_rate_cp": "",      // Card Present rate (Flat Rate contracts)
      "discount_rate_cnp": "",     // Card Not Present rate (Flat Rate contracts)
      "discount_rate": "",         // Single rate (IC++ contracts)
      "discount_per_item": "",      // Per item discount
      "trans_fee_cp": "",          // Transaction fee Card Present
      "trans_fee_cnp": "",         // Transaction fee Card Not Present
      "trans_fee_dial": "",        // Transaction fee Dial
      "trans_fee_ip": "",          // Transaction fee IP
      "non_emv_assessment_fee": "" // Non-EMV assessment fee
    }
  ],
  "amex_details": {
    "annual_volume": "",
    "average_ticket": "",
    "amex_program": "",            // e.g. "AXP"
    "amex_merchant_number": "",
    "opt_out_of_marketing": null   // boolean
  },
  "recurring_fees": [
    {
      "fee_name": "",              // Use canonical name from fee dictionary
      "amount": "",                // Dollar amount or percentage
      "frequency": ""             // Monthly / Annually / Per Occurrence / One-Time
    }
  ]
}

Rules:
- billing_model: if interchange_calculation is "Interchange Plus" → set to "IC++"
- billing_model: if interchange_calculation is "Flat Rate" → set to "Flat Rate"
- Extract ALL rows from the recurring fees table including $0.00 fees
- For IC++ contracts: use "discount_rate" field, leave "discount_rate_cp/cnp" as null
- discount_per_item: per item discount — set to null if not present
- For Flat Rate contracts: use "discount_rate_cp" and "discount_rate_cnp", leave "discount_rate" as null
- Preserve original dollar formatting e.g. "$0.2100" not "0.21"
- Return null for any field not found — do not guess

CONTRACT TEXT:
{contract_text}

RAG CONTEXT:
{rag_context}
```

---

## Prompt 3 — Merchant Details Extraction

**File:** `intelligence/prompts/merchant_details.txt`

```
You are a contract data extraction specialist for merchant processing agreements.

Extract the MERCHANT DETAILS section from the following Heartland contract text.

Return a JSON object with exactly these fields:
{
  "business_type": "",             // e.g. "Private"
  "ownership_type": "",            // e.g. "LLC Corporation" or "Tax Exempt"
  "tax_id": "",                    // Federal EIN e.g. "84-3846372"
  "services": "",                  // Business category e.g. "Shoes-Retail"
  "card_acceptance": "",           // e.g. "All Cards Accepted"
  "statement_type": "",            // e.g. "Standard / DBA"
  "new_existing_business": "",     // e.g. "Open-New to Card" or "Switching to Heartland"
  "length_in_business": "",        // e.g. "< 1 year" or "> 15 years"
  "number_of_terminals": null,     // integer
  "deposit_method": "",            // e.g. "Standard"
  "dispute_letter_mailing": "",    // e.g. "DBA"
  "dispute_letter_electronic": "", // e.g. "Email"
  "pci_compliant": null            // boolean — true if "Yes", false if "No"
}

Rules:
- pci_compliant: "Yes" → true, "No" → false
- number_of_terminals: extract as integer
- Return null for any field not found
- Do not extract the compliance Yes/No questions — only the structured fields above

CONTRACT TEXT:
{contract_text}

RAG CONTEXT:
{rag_context}
```

---

## Prompt 4 — Processing Details Extraction

**File:** `intelligence/prompts/processing_details.txt`

```
You are a contract data extraction specialist for merchant processing agreements.

Extract the PROCESSING DETAILS section from the following Heartland contract text.

Return a JSON object with exactly these fields:
{
  "card_swiped_pct": "",           // e.g. "100%" or "50%"
  "keyed_with_imprint_pct": "",    // e.g. "50%"
  "b2b_consumer_pct": "",          // Consumer percentage
  "face_to_face_pct": "",          // e.g. "100%"
  "inbound_telephone_pct": "",     // e.g. "50%"
  "future_delivery_volume_pct": "",// e.g. "0%"
  "signature_obtained": "",        // e.g. "All Face to Face Sales"
  "consumer_charged": "",          // e.g. "At Time of Purchase"
  "credit_card_via_website": null  // boolean
}

Rules:
- credit_card_via_website: "Yes" → true, "No" → false
- Percentages should include the % symbol e.g. "100%"
- Return null for any field not found

CONTRACT TEXT:
{contract_text}

RAG CONTEXT:
{rag_context}
```

---

## Prompt 5 — Processor Info Extraction

**File:** `intelligence/prompts/processor_info.txt`

```
You are a contract data extraction specialist for merchant processing agreements.

Extract the PROCESSOR HEADER INFORMATION from the following Heartland contract text.

Return a JSON object with exactly these fields:
{
  "processor_brand": "",           // Processor company name e.g. "Heartland", "Global Payments"
  "rep_name": "",                  // Full name of the sales rep / relationship manager
  "rep_role": "",                  // Role code e.g. "SRM", "RM", "TM", "FI - RM", "isRM"
  "rep_phone": "",                 // Phone listed directly under the rep's name
  "mid": "",                       // MID value e.g. "650000011273417"
  "atlas_token": "",               // atlas Token value e.g. "4685796"
  "sdr_name": "",                  // SDR name if present
  "affiliate_id": "",              // Partner/affiliate code following "Affiliate ID:"
  "referred_by": ""               // Name following "Referred By:"
}

Rules:
- processor_brand: processor company name e.g. "Heartland", "Global Payments"
- rep_name: full name of the sales rep / relationship manager in the top right header
- rep_role: role code e.g. "SRM", "RM", "TM", "FI - RM", "isRM"
- rep_phone: phone number listed directly under the rep's name
- MID label in document is "MID:" — extract the number after it
- atlas Token label is "atlas Token:" — extract the number after it
- affiliate_id: partner/affiliate code following "Affiliate ID:" — set to null if not present
- referred_by: name following "Referred By:" — set to null if not present
- Return null for any field not found

CONTRACT TEXT:
{contract_text}

RAG CONTEXT:
{rag_context}
```

---

## Prompt 6 — LLM-as-a-Judge Validation

**File:** `intelligence/prompts/llm_judge.txt`

```
You are a quality validation specialist for extracted merchant contract data.

Review the following extracted contract JSON against the original contract text
and score the extraction quality.

Return a JSON object with exactly these fields:
{
  "overall_confidence": 0.0,       // 0.0 to 1.0
  "verdict": "",                   // "Approved" / "Review Required" / "Rejected"
  "field_scores": {
    "company_information": 0.0,
    "merchant_details": 0.0,
    "credit_card_pricing": 0.0,
    "processing_details": 0.0,
    "processor_info": 0.0
  },
  "issues": [],                    // List of specific issues found
  "critical_failures": []          // Fields that are wrong or missing that block approval
}

Scoring rules:
- 1.0 = all fields extracted correctly and completely
- 0.8 = minor fields missing or formatting differences only
- 0.6 = some important fields missing or incorrect
- 0.4 = significant fields missing or multiple errors
- 0.0 = section completely missing or entirely wrong

Verdict rules:
- overall_confidence >= 0.85 → "Approved"
- overall_confidence >= 0.60 → "Review Required"
- overall_confidence < 0.60  → "Rejected"

Critical fields (any error here = Review Required minimum):
- legal_name
- legal_address
- billing_model
- card_rates (all rows)
- recurring_fees (all rows)
- tax_id

ORIGINAL CONTRACT TEXT:
{contract_text}

EXTRACTED JSON:
{extracted_json}
```

---

## Prompt 7 — Banking Information Extraction

**File:** `intelligence/prompts/banking_information.txt`

```
You are a contract data extraction specialist for merchant processing agreements.

Extract the BANKING INFORMATION section from the following Heartland contract text.
This section is on page 3 of the contract. There may be multiple bank accounts listed.

Return a JSON object with exactly this structure:
{
  "funding_option": "",            // e.g. "Standard", "Extended", "Next Day"
  "accounts": [
    {
      "bank_name": "",             // Full bank name e.g. "GLACIER BANK"
      "name_on_account": "",       // Legal or DBA name on account
      "bank_address": "",          // Bank address e.g. "Helena, MT 59602"
      "bank_phone": "",            // Bank phone
      "product_services": "",      // e.g. "Card/Gift, PetroPay, e-Commerce"
      "transfer_method": "",       // e.g. "Both", "Debit Only", "Credit Only"
      "routing_number": "",        // Full routing number — masked by DLP
      "account_number_masked": "", // Masked account number e.g. "***********233"
      "account_type": ""           // e.g. "Checking", "Savings"
    }
  ]
}

Rules:
- funding_option: top-level funding option — set to null if not present
- accounts: one entry per bank account listed — return [] if none found
- routing_number: extract the full routing number — this will be masked by DLP
- account_number_masked: extract the masked value as shown e.g. "***********233"
- Return null for any field not found — do not guess

CONTRACT TEXT:
{contract_text}

RAG CONTEXT:
{rag_context}
```

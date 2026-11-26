# TRACE Platform — Canonical Contract Schema
# Derived from: Heartland Merchant Processing Contracts
# Contracts Analyzed: CHETSHOESLLC.pdf, FITCHBURG HISTORICAL SOCIETY.pdf
# Version: 1.0 (POC)

---

## Schema Definition (Pydantic)

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class ExtractionStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REVIEW_REQUIRED = "Review Required"
    REJECTED = "Rejected"


class BillingModel(str, Enum):
    INTERCHANGE_PLUS = "IC++"
    FLAT_RATE = "Flat Rate"
    TIERED = "Tiered"
    UNKNOWN = "Unknown"


class SettlementType(str, Enum):
    MONTHLY_5_BPS = "Monthly 5 bps"
    MONTHLY_0_BPS = "Monthly 0 bps"
    DAILY = "Daily"
    UNKNOWN = "Unknown"


class FeeFrequency(str, Enum):
    MONTHLY = "Monthly"
    ANNUALLY = "Annually"
    PER_OCCURRENCE = "Per Occurrence"
    ONE_TIME = "One-Time"


class CardPricingRate(BaseModel):
    card_type: str                          # Visa, Mastercard, Discover/JCB, Amex-AXP
    discount_rate_cp: Optional[str]         # Card Present discount rate
    discount_rate_cnp: Optional[str]        # Card Not Present discount rate
    discount_rate: Optional[str]            # Single rate (IC++ contracts)
    discount_per_item: Optional[str]        # Per item discount
    trans_fee_cp: Optional[str]             # Transaction fee Card Present
    trans_fee_cnp: Optional[str]            # Transaction fee Card Not Present
    trans_fee_dial: Optional[str]           # Transaction fee Dial
    trans_fee_ip: Optional[str]             # Transaction fee IP
    non_emv_assessment_fee: Optional[str]   # Non-EMV assessment fee


class RecurringFee(BaseModel):
    fee_name: str                           # e.g. Minimum Discount Fee
    amount: Optional[str]                   # e.g. $255.00
    frequency: FeeFrequency                 # Monthly, Annually, Per Occurrence, One-Time


class AmexDetails(BaseModel):
    annual_volume: Optional[str]
    average_ticket: Optional[str]
    amex_program: Optional[str]             # e.g. AXP
    amex_merchant_number: Optional[str]
    opt_out_of_marketing: Optional[bool]
    arc_iata_number: Optional[str]


class CompanyInformation(BaseModel):
    legal_name: str                         # e.g. Chet Shoes LLC
    legal_address: Optional[str]            # Full legal address
    legal_phone: Optional[str]              # Phone in legal block
    dba_name: Optional[str]
    dba_address: Optional[str]              # Physical DBA address
    dba_phone: Optional[str]                # Phone listed next to DBA
    contact_email: Optional[str]            # Main business email
    website: Optional[str]
    primary_contact_name: Optional[str]
    primary_contact_phone: Optional[str]
    secondary_contact_phone: Optional[str]  # Secondary phone under primary
    after_hours_emergency_phone: Optional[str]
    authorized_to_purchase: Optional[str]   # Yes / No
    hic_admin_name: Optional[str]
    hic_admin_email: Optional[str]


class MerchantDetails(BaseModel):
    business_type: Optional[str]            # e.g. Private
    ownership_type: Optional[str]           # e.g. LLC Corporation, Tax Exempt
    tax_id: Optional[str]                   # e.g. 84-3846372
    services: Optional[str]                 # e.g. Shoes-Retail, Historical Organizations
    card_acceptance: Optional[str]          # e.g. All Cards Accepted
    statement_type: Optional[str]           # e.g. Standard / DBA
    new_existing_business: Optional[str]    # e.g. Open-New to Card, Switching to Heartland
    length_in_business: Optional[str]       # e.g. < 1 year, > 15 years
    number_of_terminals: Optional[int]
    deposit_method: Optional[str]           # e.g. Standard
    dispute_letter_mailing: Optional[str]   # e.g. DBA
    dispute_letter_electronic: Optional[str]# e.g. Email
    pci_compliant: Optional[bool]


class ProcessingDetails(BaseModel):
    card_swiped_pct: Optional[str]          # e.g. 100%
    keyed_with_imprint_pct: Optional[str]
    b2b_consumer_pct: Optional[str]
    face_to_face_pct: Optional[str]
    inbound_telephone_pct: Optional[str]
    future_delivery_volume_pct: Optional[str]
    signature_obtained: Optional[str]
    consumer_charged: Optional[str]
    credit_card_via_website: Optional[bool]


class CreditCardPricing(BaseModel):
    annual_volume: Optional[str]            # e.g. $800,000.00
    avg_ticket: Optional[str]              # e.g. $193.00
    network: Optional[str]                 # e.g. Exchange
    interchange_calculation: Optional[str] # e.g. Interchange Plus, Flat Rate
    settlement_type: Optional[SettlementType]
    billing_model: BillingModel
    card_rates: List[CardPricingRate]
    amex_details: Optional[AmexDetails]
    recurring_fees: List[RecurringFee]


class OwnerOfficer(BaseModel):
    name: str                               # e.g. Emily Dehmer
    title: Optional[str]                    # e.g. Owner, Officer, Director
    ownership_pct: Optional[str]            # e.g. 33%, 100%
    address: Optional[str]                  # Street address
    city_state_zip: Optional[str]           # e.g. Saint Michael, MN 55376
    email: Optional[str]
    home_phone: Optional[str]
    cell_phone: Optional[str]
    dob: Optional[str]                      # Date of birth e.g. 7/31/1992 — PII flagged by DLP
    ssn_last4: Optional[str]                # Last 4 of SSN e.g. ***-**-6306 — PII flagged by DLP
    drivers_license_last4: Optional[str]    # Last 4 of DL — PII flagged by DLP
    length_at_address: Optional[str]        # e.g. 1-3 years, 11-15 years
    citizenship: Optional[str]              # e.g. US Citizen


class BankingAccount(BaseModel):
    bank_name: str                          # e.g. GLACIER BANK
    name_on_account: Optional[str]          # Legal or DBA name on account
    bank_address: Optional[str]             # Bank address e.g. Helena, MT 59602
    bank_phone: Optional[str]               # Bank phone
    product_services: Optional[str]         # e.g. Card/Gift, PetroPay, e-Commerce
    transfer_method: Optional[str]          # e.g. Both, Debit Only, Credit Only
    routing_number: Optional[str]           # Full routing number — masked by DLP
    account_number_masked: Optional[str]    # Masked account number e.g. ***********233
    account_type: Optional[str]             # e.g. Checking, Savings


class BankingInformation(BaseModel):
    funding_option: Optional[str]           # e.g. Standard, Extended, Next Day
    accounts: List[BankingAccount]          # One entry per bank account listed


class ProcessorInfo(BaseModel):
    processor_brand: str                    # e.g. Heartland, Global Payments
    rep_name: Optional[str]                 # e.g. Lukas Turner, Sterling Jackson
    rep_role: Optional[str]                 # e.g. SRM, RM, TM, FI - RM, isRM
    rep_phone: Optional[str]                # Phone listed directly under rep's name
    mid: Optional[str]                      # Merchant ID e.g. 650000011273417
    atlas_token: Optional[str]              # e.g. 4685796
    sdr_name: Optional[str]                 # e.g. Julia Wallis
    affiliate_id: Optional[str]             # e.g. FSBFMAS
    referred_by: Optional[str]              # e.g. Kelly Firesheets


class ContractRecord(BaseModel):
    # ── Identity ──────────────────────────────────────────────
    contract_id: str                        # System generated
    processor_info: ProcessorInfo

    # ── Company ───────────────────────────────────────────────
    company_information: CompanyInformation

    # ── Merchant ──────────────────────────────────────────────
    merchant_details: MerchantDetails

    # ── Pricing ───────────────────────────────────────────────
    credit_card_pricing: CreditCardPricing

    # ── Processing ────────────────────────────────────────────
    processing_details: ProcessingDetails

    # ── Owners ────────────────────────────────────────────────
    owners_officers: List[OwnerOfficer]     # All owners with >= 25% ownership

    # ── Banking ───────────────────────────────────────────────
    banking_information: BankingInformation

    # ── Validation ────────────────────────────────────────────
    confidence_score: float = Field(ge=0.0, le=1.0)
    extraction_status: ExtractionStatus = ExtractionStatus.PENDING
    field_scores: Optional[dict] = None    # Per-section LLM Judge scores e.g. {"credit_card_pricing": 0.54, ...}
    judge_issues: list[str] = []           # Specific issues flagged by LLM Judge
    source_pdf_uri: Optional[str]          # GCS URI of the raw input PDF
    page_count: Optional[int]              # Number of pages (from OCR stage)
    file_hash: Optional[str]               # SHA256 hash of the original PDF bytes
    extracted_at: Optional[str]
    reviewed_by: Optional[str]
    review_notes: Optional[str]
    reviewed_at: Optional[str]             # ISO timestamp of human review decision
```

---

## Example Extracted Output — Contract 1 (Chet Shoes LLC)

```json
{
  "contract_id": "CNT-20240426-CHETSHOESLLC",
  "processor_info": {
    "processor_brand": "Heartland",
    "rep_name": "Lukas Turner",
    "rep_role": "isRM",
    "rep_phone": "(405) 266-9827",
    "mid": "650000011273417",
    "atlas_token": "4685796",
    "sdr_name": "Julia Wallis",
    "affiliate_id": null,
    "referred_by": null
  },
  "company_information": {
    "legal_name": "Chet Shoes LLC",
    "legal_address": "8870 Rendova St NE, Circle Pines, MN 55014",
    "legal_phone": "(763) 253-1079",
    "dba_name": null,
    "dba_address": null,
    "dba_phone": null,
    "contact_email": null,
    "website": "http://chetsshoes.com",
    "primary_contact_name": "Emily Dehmer",
    "primary_contact_phone": "(612) 655-6313",
    "secondary_contact_phone": null,
    "after_hours_emergency_phone": null,
    "authorized_to_purchase": null,
    "hic_admin_name": null,
    "hic_admin_email": null
  },
  "merchant_details": {
    "business_type": "Private",
    "ownership_type": "LLC Corporation",
    "tax_id": "84-3846372",
    "services": "Shoes-Retail",
    "card_acceptance": "All Cards Accepted",
    "new_existing_business": "Open-New to Card",
    "length_in_business": "< 1 year",
    "number_of_terminals": 1,
    "deposit_method": "Standard",
    "pci_compliant": true
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
      },
      {
        "card_type": "Mastercard",
        "discount_rate_cp": "0.910%",
        "trans_fee_dial": "$0.2100",
        "trans_fee_ip": "$0.2100",
        "non_emv_assessment_fee": "1.000%"
      },
      {
        "card_type": "Discover/JCB",
        "discount_rate_cp": "0.910%",
        "trans_fee_dial": "$0.2100",
        "trans_fee_ip": "$0.2100",
        "non_emv_assessment_fee": "1.000%"
      },
      {
        "card_type": "Amex-AXP",
        "discount_rate_cp": "0.910%",
        "trans_fee_dial": "$0.2100",
        "trans_fee_ip": "$0.2100",
        "non_emv_assessment_fee": "1.000%"
      }
    ],
    "amex_details": {
      "annual_volume": "$120,000.00",
      "average_ticket": "$193.00",
      "amex_program": "AXP",
      "opt_out_of_marketing": false
    },
    "recurring_fees": [
      { "fee_name": "Minimum Discount Fee", "amount": "$255.00", "frequency": "Monthly" },
      { "fee_name": "Service/Mandate Fee", "amount": "$33.50", "frequency": "Monthly" },
      { "fee_name": "Annual Fee", "amount": "$0.00", "frequency": "Annually" },
      { "fee_name": "Chargeback Fee", "amount": "$25.00", "frequency": "Per Occurrence" },
      { "fee_name": "Voice Authorization Fee", "amount": "$0.65", "frequency": "Per Occurrence" },
      { "fee_name": "Application Processing Fee", "amount": "$0.00", "frequency": "One-Time" },
      { "fee_name": "PCI Non-Compliance Fee", "amount": "$125.00", "frequency": "Monthly" },
      { "fee_name": "Payments Manager+ Discount Rate", "amount": "0.30%", "frequency": "Per Occurrence" },
      { "fee_name": "Payments Manager+ Txn Fee", "amount": "$0.20", "frequency": "Per Occurrence" }
    ]
  },
  "processing_details": {
    "card_swiped_pct": "100%",
    "b2b_consumer_pct": "100%",
    "face_to_face_pct": "100%",
    "future_delivery_volume_pct": "0%",
    "signature_obtained": "All Face to Face Sales",
    "consumer_charged": "At Time of Purchase",
    "credit_card_via_website": false
  },
  "owners_officers": [
    {
      "name": "Emily Dehmer",
      "title": "Owner",
      "ownership_pct": "33%",
      "address": "105 2nd St SE",
      "city_state_zip": "Saint Michael, MN 55376",
      "email": "emilygracedehmer@gmail.com",
      "home_phone": "(612) 655-6313",
      "cell_phone": "(612) 655-6313",
      "dob": "7/31/1992",
      "ssn_last4": "***-**-6306",
      "drivers_license_last4": "****8113",
      "length_at_address": "1-3 years",
      "citizenship": "US Citizen"
    },
    {
      "name": "Katelyn Raab",
      "title": "Officer",
      "ownership_pct": "33%",
      "address": "6623 381st Street",
      "city_state_zip": "North Branch, MN 55056",
      "email": "katelyn@chetsshoes.com",
      "home_phone": "(612) 619-0187",
      "cell_phone": "(612) 619-0187",
      "dob": "6/21/1987",
      "ssn_last4": "***-**-6851",
      "drivers_license_last4": "****5025",
      "length_at_address": "1-3 years",
      "citizenship": "US Citizen"
    }
  ],
  "banking_information": {
    "funding_option": "Standard",
    "accounts": [
      {
        "bank_name": "FARMERS & MERCHANTS SAVINGS",
        "name_on_account": "Chet Shoes LLC",
        "bank_address": "Manchester, IA 52057",
        "bank_phone": "319 730-5965",
        "product_services": "Card/Gift, PetroPay, e-Commerce",
        "transfer_method": "Both",
        "routing_number": "073903244",
        "account_number_masked": "***********4698",
        "account_type": "Checking"
      }
    ]
  },
  "confidence_score": 0.95,
  "extraction_status": "Approved",
  "field_scores": {
    "company_information": 0.97,
    "merchant_details": 0.95,
    "credit_card_pricing": 0.94,
    "processing_details": 0.96,
    "processor_info": 0.98,
    "owners_officers": 0.93,
    "banking_information": 0.96
  },
  "judge_issues": [],
  "source_pdf_uri": "gs://<GCS_BUCKET>/raw/contracts/CNT-20240426-CHETSHOESLLC/contract.pdf",
  "page_count": 8,
  "file_hash": "a3f9b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1",
  "extracted_at": "2024-04-26T11:35:00Z"
}
```

---

## Example Extracted Output — Contract 2 (Fitchburg Historical Society)

```json
{
  "contract_id": "CNT-20241031-FITCHBURGHISTORICAL",
  "processor_info": {
    "processor_brand": "Heartland",
    "rep_name": "Sterling Jackson",
    "rep_role": "TM",
    "rep_phone": "(617) 697-2899",
    "mid": null,
    "atlas_token": "4802548",
    "sdr_name": null,
    "affiliate_id": "FSBFMAS",
    "referred_by": null
  },
  "company_information": {
    "legal_name": "Fitchburg Historical Society",
    "legal_address": "781 Main Street, Fitchburg, MA 01420",
    "legal_phone": "(978) 345-1157",
    "dba_name": null,
    "dba_address": null,
    "dba_phone": null,
    "contact_email": null,
    "website": null,
    "primary_contact_name": "Susan Navarre",
    "primary_contact_phone": "(978) 345-1157",
    "secondary_contact_phone": null,
    "after_hours_emergency_phone": null,
    "authorized_to_purchase": null,
    "hic_admin_name": "Susan Navarre",
    "hic_admin_email": "director@fitchburghistoricalsociety.com"
  },
  "merchant_details": {
    "business_type": "Private",
    "ownership_type": "Tax Exempt",
    "tax_id": "04-6060118",
    "services": "Historical Organizations",
    "card_acceptance": "All Cards Accepted",
    "new_existing_business": "Switching to Heartland",
    "length_in_business": "> 15 years",
    "number_of_terminals": 1,
    "deposit_method": "Standard",
    "pci_compliant": true
  },
  "credit_card_pricing": {
    "annual_volume": "$15,000.00",
    "avg_ticket": "$25.00",
    "network": "Exchange",
    "interchange_calculation": "Flat Rate",
    "settlement_type": "Monthly 0 bps",
    "billing_model": "Flat Rate",
    "card_rates": [
      {
        "card_type": "Visa",
        "discount_rate_cp": "2.600%",
        "discount_rate_cnp": "2.900%",
        "trans_fee_cp": "$0.1000",
        "trans_fee_cnp": "$0.3000",
        "non_emv_assessment_fee": "1.000%"
      },
      {
        "card_type": "Mastercard",
        "discount_rate_cp": "2.600%",
        "discount_rate_cnp": "2.900%",
        "trans_fee_cp": "$0.1000",
        "trans_fee_cnp": "$0.3000",
        "non_emv_assessment_fee": "1.000%"
      },
      {
        "card_type": "Discover/JCB",
        "discount_rate_cp": "2.600%",
        "discount_rate_cnp": "2.900%",
        "trans_fee_cp": "$0.1000",
        "trans_fee_cnp": "$0.3000",
        "non_emv_assessment_fee": "1.000%"
      },
      {
        "card_type": "Amex-AXP",
        "discount_rate_cp": "2.600%",
        "discount_rate_cnp": "2.900%",
        "trans_fee_cp": "$0.1000",
        "trans_fee_cnp": "$0.3000",
        "non_emv_assessment_fee": "1.000%"
      }
    ],
    "amex_details": {
      "annual_volume": "$2,000.00",
      "average_ticket": "$25.00",
      "amex_program": "AXP",
      "opt_out_of_marketing": false
    },
    "recurring_fees": [
      { "fee_name": "Minimum Discount Fee", "amount": "$0.00", "frequency": "Monthly" },
      { "fee_name": "Service/Mandate Fee", "amount": "$0.00", "frequency": "Monthly" },
      { "fee_name": "Annual Fee", "amount": "$0.00", "frequency": "Annually" },
      { "fee_name": "Chargeback Fee", "amount": "$25.00", "frequency": "Per Occurrence" },
      { "fee_name": "Voice Authorization Fee", "amount": "$0.65", "frequency": "Per Occurrence" },
      { "fee_name": "Application Processing Fee", "amount": "$0.00", "frequency": "One-Time" },
      { "fee_name": "PCI Non-Compliance Fee", "amount": "$125.00", "frequency": "Monthly" },
      { "fee_name": "Payments Manager+ Discount Rate", "amount": "0.30%", "frequency": "Per Occurrence" },
      { "fee_name": "Payments Manager+ Txn Fee", "amount": "$0.20", "frequency": "Per Occurrence" }
    ]
  },
  "processing_details": {
    "card_swiped_pct": "50%",
    "keyed_with_imprint_pct": "50%",
    "b2b_consumer_pct": "100%",
    "face_to_face_pct": "50%",
    "inbound_telephone_pct": "50%",
    "future_delivery_volume_pct": "0%",
    "signature_obtained": "All Face to Face Sales",
    "consumer_charged": "At Time of Purchase",
    "credit_card_via_website": false
  },
  "owners_officers": [
    {
      "name": "Susan Navarre",
      "title": "Director",
      "ownership_pct": "100%",
      "address": "507 Blanchflower Ln",
      "city_state_zip": "Leominster, MA 01453",
      "email": "director@fitchburghistoricalsociety.com",
      "home_phone": "(978) 345-1157",
      "cell_phone": "(978) 345-1157",
      "dob": "1/12/1959",
      "ssn_last4": "***-**-5784",
      "length_at_address": "11-15 years",
      "citizenship": "US Citizen"
    }
  ],
  "banking_information": {
    "funding_option": "Standard",
    "accounts": [
      {
        "bank_name": "FIDELITY CO-OP BANK",
        "name_on_account": "Fitchburg Historical Society",
        "bank_address": "Leominster, MA 01453",
        "bank_phone": "978 870-1466",
        "product_services": "Card/Gift",
        "transfer_method": "Both",
        "routing_number": "211370707",
        "account_number_masked": "***********3011",
        "account_type": "Checking"
      }
    ]
  },
  "confidence_score": 0.95,
  "extraction_status": "Approved",
  "field_scores": {
    "company_information": 0.96,
    "merchant_details": 0.94,
    "credit_card_pricing": 0.95,
    "processing_details": 0.97,
    "processor_info": 0.96,
    "owners_officers": 0.93,
    "banking_information": 0.95
  },
  "judge_issues": [],
  "source_pdf_uri": "gs://<GCS_BUCKET>/raw/contracts/CNT-20241031-FITCHBURGHISTORICAL/contract.pdf",
  "page_count": 6,
  "file_hash": "b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5",
  "extracted_at": "2024-10-31T10:32:00Z"
}
```

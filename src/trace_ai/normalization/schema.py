from pydantic import BaseModel, Field
from typing import Optional
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
    card_type: str
    discount_rate_cp: Optional[str] = None
    discount_rate_cnp: Optional[str] = None
    discount_rate: Optional[str] = None
    discount_per_item: Optional[str] = None
    trans_fee_cp: Optional[str] = None
    trans_fee_cnp: Optional[str] = None
    trans_fee_dial: Optional[str] = None
    trans_fee_ip: Optional[str] = None
    non_emv_assessment_fee: Optional[str] = None


class RecurringFee(BaseModel):
    fee_name: str
    amount: Optional[str] = None
    frequency: FeeFrequency


class AmexDetails(BaseModel):
    annual_volume: Optional[str] = None
    average_ticket: Optional[str] = None
    amex_program: Optional[str] = None
    amex_merchant_number: Optional[str] = None
    opt_out_of_marketing: Optional[bool] = None
    arc_iata_number: Optional[str] = None


class CompanyInformation(BaseModel):
    legal_name: str
    legal_address: Optional[str] = None
    legal_phone: Optional[str] = None
    dba_name: Optional[str] = None
    dba_address: Optional[str] = None
    dba_phone: Optional[str] = None
    contact_email: Optional[str] = None
    website: Optional[str] = None
    primary_contact_name: Optional[str] = None
    primary_contact_phone: Optional[str] = None
    secondary_contact_phone: Optional[str] = None
    after_hours_emergency_phone: Optional[str] = None
    authorized_to_purchase: Optional[str] = None
    hic_admin_name: Optional[str] = None
    hic_admin_email: Optional[str] = None


class MerchantDetails(BaseModel):
    business_type: Optional[str] = None
    ownership_type: Optional[str] = None
    tax_id: Optional[str] = None
    services: Optional[str] = None
    card_acceptance: Optional[str] = None
    statement_type: Optional[str] = None
    new_existing_business: Optional[str] = None
    length_in_business: Optional[str] = None
    number_of_terminals: Optional[int] = None
    deposit_method: Optional[str] = None
    dispute_letter_mailing: Optional[str] = None
    dispute_letter_electronic: Optional[str] = None
    pci_compliant: Optional[bool] = None


class ProcessingDetails(BaseModel):
    card_swiped_pct: Optional[str] = None
    keyed_with_imprint_pct: Optional[str] = None
    b2b_consumer_pct: Optional[str] = None
    face_to_face_pct: Optional[str] = None
    inbound_telephone_pct: Optional[str] = None
    future_delivery_volume_pct: Optional[str] = None
    signature_obtained: Optional[str] = None
    consumer_charged: Optional[str] = None
    credit_card_via_website: Optional[bool] = None


class CreditCardPricing(BaseModel):
    annual_volume: Optional[str] = None
    avg_ticket: Optional[str] = None
    network: Optional[str] = None
    interchange_calculation: Optional[str] = None
    settlement_type: Optional[SettlementType] = None
    billing_model: BillingModel
    card_rates: list[CardPricingRate]
    amex_details: Optional[AmexDetails] = None
    recurring_fees: list[RecurringFee]


class OwnerOfficer(BaseModel):
    name: str
    title: Optional[str] = None
    ownership_pct: Optional[str] = None
    address: Optional[str] = None
    city_state_zip: Optional[str] = None
    email: Optional[str] = None
    home_phone: Optional[str] = None
    cell_phone: Optional[str] = None
    dob: Optional[str] = None
    ssn_last4: Optional[str] = None
    drivers_license_last4: Optional[str] = None
    length_at_address: Optional[str] = None
    citizenship: Optional[str] = None


class BankingAccount(BaseModel):
    bank_name: str
    name_on_account: Optional[str] = None
    bank_address: Optional[str] = None
    bank_phone: Optional[str] = None
    product_services: Optional[str] = None
    transfer_method: Optional[str] = None
    routing_number: Optional[str] = None
    account_number_masked: Optional[str] = None
    account_type: Optional[str] = None


class BankingInformation(BaseModel):
    funding_option: Optional[str] = None
    accounts: list[BankingAccount]


class ProcessorInfo(BaseModel):
    processor_name: str
    sales_rep_name: Optional[str] = None
    sales_rep_role: Optional[str] = None
    sales_rep_phone: Optional[str] = None
    mid: Optional[str] = None
    atlas_token: Optional[str] = None
    sdr_name: Optional[str] = None
    affiliate_id: Optional[str] = None
    generated_on: Optional[str] = None


class ContractRecord(BaseModel):
    contract_id: str
    processor_info: ProcessorInfo
    company_information: CompanyInformation
    merchant_details: MerchantDetails
    credit_card_pricing: CreditCardPricing
    processing_details: ProcessingDetails
    owners_officers: list[OwnerOfficer]
    banking_information: BankingInformation
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_status: ExtractionStatus = ExtractionStatus.PENDING
    field_scores: Optional[dict] = None
    judge_issues: list[str] = []
    source_pdf_uri: Optional[str] = None
    page_count: Optional[int] = None
    file_hash: Optional[str] = None
    extracted_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[str] = None

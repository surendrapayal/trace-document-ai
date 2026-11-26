from trace_ai.normalization.schema import (
    ContractRecord, ProcessorInfo, CompanyInformation, MerchantDetails,
    CreditCardPricing, ProcessingDetails, OwnerOfficer, BankingInformation, BankingAccount,
    CardPricingRate, RecurringFee, AmexDetails, BillingModel, SettlementType, FeeFrequency,
)
from trace_ai.common.logger import log
from datetime import datetime, timezone


def _billing_model(raw: dict) -> BillingModel:
    value = (raw.get("billing_model") or raw.get("interchange_calculation") or "").lower()
    if "interchange plus" in value or "ic++" in value:
        return BillingModel.INTERCHANGE_PLUS
    if "flat rate" in value or "flat" in value:
        return BillingModel.FLAT_RATE
    if "tiered" in value:
        return BillingModel.TIERED
    return BillingModel.UNKNOWN


def _settlement_type(value: str | None) -> SettlementType | None:
    if not value:
        return None
    v = value.lower()
    if "5 bps" in v:
        return SettlementType.MONTHLY_5_BPS
    if "0 bps" in v:
        return SettlementType.MONTHLY_0_BPS
    if "daily" in v:
        return SettlementType.DAILY
    return SettlementType.UNKNOWN


def _fee_frequency(value: str | None) -> FeeFrequency:
    if not value:
        return FeeFrequency.MONTHLY
    v = value.lower()
    if "annual" in v:
        return FeeFrequency.ANNUALLY
    if "occurrence" in v or "per " in v:
        return FeeFrequency.PER_OCCURRENCE
    if "one" in v or "1-time" in v or "one-time" in v:
        return FeeFrequency.ONE_TIME
    return FeeFrequency.MONTHLY


def normalize(raw: dict, contract_id: str) -> ContractRecord:
    log("Normalizing extracted data", severity="DEBUG", sections=list(raw.keys()))

    pricing_raw = raw.get("credit_card_pricing", {})
    card_rates = [CardPricingRate(**r) for r in pricing_raw.get("card_rates", [])]
    recurring_fees = [
        RecurringFee(
            fee_name=f["fee_name"],
            amount=f.get("amount"),
            frequency=_fee_frequency(f.get("frequency")),
        )
        for f in pricing_raw.get("recurring_fees", [])
    ]
    amex_raw = pricing_raw.get("amex_details")
    amex = AmexDetails(**amex_raw) if amex_raw else None

    owners = [OwnerOfficer(**o) for o in raw.get("owners_officers", [])]
    banking_raw = raw.get("banking_information", {})
    banking = BankingInformation(
        funding_option=banking_raw.get("funding_option"),
        accounts=[BankingAccount(**a) for a in banking_raw.get("accounts", [])],
    )

    record = ContractRecord(
        contract_id=contract_id,
        processor_info=ProcessorInfo(**raw.get("processor_info", {"processor_brand": "Unknown"})),
        company_information=CompanyInformation(**raw["company_information"]),
        merchant_details=MerchantDetails(**raw.get("merchant_details", {})),
        credit_card_pricing=CreditCardPricing(
            annual_volume=pricing_raw.get("annual_volume"),
            avg_ticket=pricing_raw.get("avg_ticket"),
            network=pricing_raw.get("network"),
            interchange_calculation=pricing_raw.get("interchange_calculation"),
            settlement_type=_settlement_type(pricing_raw.get("settlement_type")),
            billing_model=_billing_model(pricing_raw),
            card_rates=card_rates,
            amex_details=amex,
            recurring_fees=recurring_fees,
        ),
        processing_details=ProcessingDetails(**raw.get("processing_details", {})),
        owners_officers=owners,
        banking_information=banking,
        extracted_at=datetime.now(timezone.utc).isoformat(),

    log("Normalization complete", billing_model=str(record.credit_card_pricing.billing_model), owners_count=len(record.owners_officers))
    return record

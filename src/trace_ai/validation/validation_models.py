from pydantic import BaseModel, Field


class FieldScores(BaseModel):
    company_information: float = Field(default=0.0, ge=0.0, le=1.0)
    merchant_details: float = Field(default=0.0, ge=0.0, le=1.0)
    credit_card_pricing: float = Field(default=0.0, ge=0.0, le=1.0)
    processing_details: float = Field(default=0.0, ge=0.0, le=1.0)
    processor_info: float = Field(default=0.0, ge=0.0, le=1.0)
    owners_officers: float = Field(default=0.0, ge=0.0, le=1.0)
    banking_information: float = Field(default=0.0, ge=0.0, le=1.0)


class ValidationResult(BaseModel):
    overall_confidence: float = Field(ge=0.0, le=1.0)
    verdict: str
    field_scores: FieldScores
    issues: list[str] = []
    critical_failures: list[str] = []

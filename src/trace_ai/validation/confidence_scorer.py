from trace_ai.config import config
from trace_ai.common.logger import log
from trace_ai.validation.validation_models import ValidationResult


def route(result: ValidationResult, contract_id: str) -> str:
    score = result.overall_confidence
    if score >= config.CONFIDENCE_THRESHOLD_APPROVE:
        status = "Approved"
    elif score >= config.CONFIDENCE_THRESHOLD_REVIEW:
        status = "Review Required"
    else:
        status = "Rejected"

    log("Confidence routing decision", confidence_score=score, extraction_status=status,
        threshold_approve=config.CONFIDENCE_THRESHOLD_APPROVE,
        threshold_review=config.CONFIDENCE_THRESHOLD_REVIEW)
    return status

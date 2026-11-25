from trace_ai.config import config
from trace_ai.common.logger import log
from trace_ai.validation.validation_models import ValidationResult
from trace_ai.normalization.schema import ExtractionStatus


def route(result: ValidationResult, contract_id: str) -> ExtractionStatus:
    score = result.overall_confidence
    if score >= config.CONFIDENCE_THRESHOLD_APPROVE:
        status = ExtractionStatus.APPROVED
    elif score >= config.CONFIDENCE_THRESHOLD_REVIEW:
        status = ExtractionStatus.REVIEW_REQUIRED
    else:
        status = ExtractionStatus.REJECTED

    log("Confidence routing decision", confidence_score=score, extraction_status=status.value,
        threshold_approve=config.CONFIDENCE_THRESHOLD_APPROVE,
        threshold_review=config.CONFIDENCE_THRESHOLD_REVIEW)
    return status

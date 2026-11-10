import json
import re
from pathlib import Path
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from trace_ai.config import config
from trace_ai.common.logging_client import log
from trace_ai.validation.validation_models import ValidationResult, FieldScores

vertexai.init(project=config.GCP_PROJECT_ID, location=config.GCP_REGION)

_PROMPT_PATH = Path(__file__).parent.parent / "intelligence" / "prompts" / "llm_judge.txt"
_JSON_CONFIG = GenerationConfig(temperature=0.0, response_mime_type="application/json")


def evaluate(contract_text: str, extracted_json: str, contract_id: str) -> ValidationResult:
    log("validation", contract_id, "Starting LLM judge evaluation")

    prompt = _PROMPT_PATH.read_text().format(
        contract_text=contract_text,
        extracted_json=extracted_json,
    )

    model = GenerativeModel(config.VERTEX_GEMINI_MODEL)
    response = model.generate_content(prompt, generation_config=_JSON_CONFIG)
    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)

    result = ValidationResult(
        overall_confidence=data["overall_confidence"],
        verdict=data["verdict"],
        field_scores=FieldScores(**data.get("field_scores", {})),
        issues=data.get("issues", []),
        critical_failures=data.get("critical_failures", []),
    )

    log("validation", contract_id, "LLM judge complete",
        verdict=result.verdict, confidence=result.overall_confidence)
    return result

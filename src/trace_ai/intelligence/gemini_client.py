import json
import re
from pathlib import Path
from google import genai
from google.genai import types
from trace_ai.config import config
from trace_ai.common.logging_client import log

_client = genai.Client(vertexai=True, project=config.GCP_PROJECT_ID, location=config.VERTEX_GEMINI_LOCATION)
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_JSON_CONFIG = types.GenerateContentConfig(
    temperature=0.0,
    response_mime_type="application/json",
)


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text()


def _call(prompt: str, contract_id: str, section: str) -> dict | list:
    response = _client.models.generate_content(
        model=config.VERTEX_GEMINI_MODEL,
        contents=prompt,
        config=_JSON_CONFIG,
    )
    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log("intelligence", contract_id, f"JSON parse error in {section}", severity="ERROR", error=str(e))
        raise


def extract_all(contract_text: str, rag_context: str, contract_id: str) -> dict:
    log("intelligence", contract_id, "Starting Gemini extraction")

    def run(prompt_file: str, section: str) -> dict | list:
        template = _load_prompt(prompt_file)
        prompt = template.replace("{contract_text}", contract_text).replace("{rag_context}", rag_context)
        result = _call(prompt, contract_id, section)
        log("intelligence", contract_id, f"Extracted {section}")
        return result

    return {
        "processor_info": run("processor_info.txt", "processor_info"),
        "company_information": run("company_information.txt", "company_information"),
        "merchant_details": run("merchant_details.txt", "merchant_details"),
        "credit_card_pricing": run("pricing_extraction.txt", "credit_card_pricing"),
        "processing_details": run("processing_details.txt", "processing_details"),
        "owners_officers": run("owners_officers.txt", "owners_officers"),
        "banking_information": run("banking_information.txt", "banking_information"),
    }

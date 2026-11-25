import time
import httpx
from trace_ai.config import config
from trace_ai.common.logger import log
from trace_ai.normalization.schema import ContractRecord

_MAX_RETRIES = 3
_BACKOFF_BASE = 2  # seconds — 2, 4, 8


def send(record: ContractRecord) -> bool:
    """
    POST ContractRecord JSON to WEBHOOK_URL.
    Returns True on success, False if all retries exhausted.
    Webhook delivery failure never raises — pipeline is not affected.
    """
    if not config.WEBHOOK_ENABLED:
        log("Webhook disabled -- skipping", severity="WARNING")
        return False

    if not config.WEBHOOK_URL:
        log("WEBHOOK_ENABLED=true but WEBHOOK_URL is not set", severity="ERROR")
        return False

    headers = {"Content-Type": "application/json"}
    if config.WEBHOOK_SECRET:
        headers["Authorization"] = f"Bearer {config.WEBHOOK_SECRET}"

    payload = record.model_dump_json()

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = httpx.post(
                config.WEBHOOK_URL,
                content=payload,
                headers=headers,
                timeout=config.WEBHOOK_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            log(
                "Webhook delivered successfully",
                contract_id=record.contract_id,
                status_code=response.status_code,
                attempt=attempt,
            )
            return True
        except httpx.HTTPStatusError as e:
            log(
                "Webhook HTTP error",
                severity="WARNING",
                contract_id=record.contract_id,
                attempt=attempt,
                status_code=e.response.status_code,
                error=str(e),
            )
        except httpx.RequestError as e:
            log(
                "Webhook request error",
                severity="WARNING",
                contract_id=record.contract_id,
                attempt=attempt,
                error=str(e),
            )

        if attempt < _MAX_RETRIES:
            wait = _BACKOFF_BASE ** attempt
            log("Webhook retrying", severity="DEBUG", attempt=attempt, wait_seconds=wait)
            time.sleep(wait)

    log(
        "Webhook delivery failed after all retries",
        severity="ERROR",
        contract_id=record.contract_id,
        max_retries=_MAX_RETRIES,
    )
    return False

import google.cloud.logging
import logging
import json

_client = google.cloud.logging.Client()
_client.setup_logging()

logger = logging.getLogger("trace_ai")


def log(stage: str, contract_id: str, message: str, severity: str = "INFO", **kwargs):
    payload = {"stage": stage, "contract_id": contract_id, "message": message, **kwargs}
    log_fn = {
        "DEBUG": logger.debug,
        "INFO": logger.info,
        "WARNING": logger.warning,
        "ERROR": logger.error,
        "CRITICAL": logger.critical,
    }.get(severity, logger.info)
    log_fn(json.dumps(payload))

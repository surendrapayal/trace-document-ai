from trace_ai.config import config

if config.STORAGE_BACKEND == "bigquery":
    from trace_ai.delivery.bigquery_client import (
        upsert_contract,
        write_audit_event,
        get_contract,
        get_contract_by_hash,
        get_pending_review,
        update_review_decision,
    )
elif config.STORAGE_BACKEND == "firestore":
    from trace_ai.delivery.firestore_client import (
        upsert_contract,
        write_audit_event,
        get_contract,
        get_contract_by_hash,
        get_pending_review,
        update_review_decision,
    )
else:
    raise ValueError(f"Invalid STORAGE_BACKEND '{config.STORAGE_BACKEND}'. Must be 'bigquery' or 'firestore'.")

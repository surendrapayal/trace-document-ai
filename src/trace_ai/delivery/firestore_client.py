from google.cloud import firestore
from trace_ai.config import config
from trace_ai.common.logging_client import log
from trace_ai.normalization.schema import ContractRecord
from datetime import datetime, timezone

_db = firestore.Client(project=config.GCP_PROJECT_ID)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_contract(record: ContractRecord, gcs_uri: str | None = None) -> None:
    doc_ref = _db.collection(config.FIRESTORE_COLLECTION_CONTRACTS).document(record.contract_id)
    data = record.model_dump()
    if gcs_uri:
        data["curated_gcs_uri"] = gcs_uri
    data["updated_at"] = _now()
    doc_ref.set(data, merge=True)
    log("delivery", record.contract_id, "Contract upserted to Firestore")


def write_audit_event(contract_id: str, stage: str, event: str, details: dict | None = None) -> None:
    _db.collection(config.FIRESTORE_COLLECTION_AUDIT).add({
        "contract_id": contract_id,
        "stage": stage,
        "event": event,
        "details": details or {},
        "timestamp": _now(),
    })
    log("delivery", contract_id, f"Audit event written: {event}", stage=stage)


def get_contract(contract_id: str) -> dict | None:
    doc = _db.collection(config.FIRESTORE_COLLECTION_CONTRACTS).document(contract_id).get()
    return doc.to_dict() if doc.exists else None


def get_pending_review() -> list[dict]:
    docs = (
        _db.collection(config.FIRESTORE_COLLECTION_CONTRACTS)
        .where("extraction_status", "==", "Review Required")
        .stream()
    )
    return [d.to_dict() for d in docs]


def update_review_decision(contract_id: str, reviewer: str, decision: str, notes: str) -> None:
    _db.collection(config.FIRESTORE_COLLECTION_CONTRACTS).document(contract_id).update({
        "extraction_status": decision,
        "reviewed_by": reviewer,
        "review_notes": notes,
        "reviewed_at": _now(),
    })
    write_audit_event(contract_id, "review", "human_review_decision", {
        "reviewer": reviewer, "decision": decision, "notes": notes,
    })
    log("delivery", contract_id, "Review decision recorded", decision=decision, reviewer=reviewer)

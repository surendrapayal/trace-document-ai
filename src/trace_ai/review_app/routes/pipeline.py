from fastapi import APIRouter, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel
from trace_ai.config import config
from trace_ai.common.logger import log
from trace_ai.common.gcs_client import list_blobs

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


class TriggerRequest(BaseModel):
    files: list[str] | None = None  # e.g. ["contract_a.pdf", "contract_b.pdf"]


def _run_pipeline(gcs_uri: str, contract_id: str, file_hash: str | None) -> None:
    from trace_ai.pipeline import run
    try:
        run(gcs_uri, contract_id, file_hash)
    except Exception as e:
        log("Background pipeline failed", severity="ERROR", contract_id=contract_id, error=str(e))


@router.post("/trigger", status_code=202)
async def trigger_pipeline(
    background_tasks: BackgroundTasks,
    body: TriggerRequest = TriggerRequest(),
    x_api_key: str | None = Header(default=None),
):
    if config.REST_API_KEY and x_api_key != config.REST_API_KEY:
        log("Unauthorized pipeline trigger attempt", severity="WARNING")
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    landing_prefix = config.GCS_LANDING_PREFIX.rstrip("/") + "/"
    all_blobs = [b for b in list_blobs(config.GCS_BUCKET, landing_prefix) if b.lower().endswith(".pdf")]

    if body.files:
        blob_map = {b.split("/")[-1]: b for b in all_blobs}
        blobs, unknown = [], []
        for name in body.files:
            if name in blob_map:
                blobs.append(blob_map[name])
            else:
                unknown.append({"blob": f"{landing_prefix}{name}", "reason": "Not found in landing zone"})
    else:
        blobs, unknown = all_blobs, []

    if not blobs:
        return {"accepted": [], "skipped": unknown, "count": 0, "message": "No PDFs found in landing zone."}

    from trace_ai.ingestion.upload_handler import upload_contract_from_gcs

    accepted, skipped = [], unknown
    for blob in blobs:
        try:
            upload_result = upload_contract_from_gcs(blob)
            background_tasks.add_task(
                _run_pipeline,
                upload_result["gcs_uri"],
                upload_result["contract_id"],
                upload_result.get("file_hash"),
            )
            accepted.append({
                "contract_id": upload_result["contract_id"],
                "gcs_uri": upload_result["gcs_uri"],
            })
            log("Contract accepted from landing zone", contract_id=upload_result["contract_id"], blob=blob)
        except Exception as e:
            log("Skipped landing blob", severity="WARNING", blob=blob, error=str(e))
            skipped.append({"blob": blob, "reason": str(e)})

    ids = [a["contract_id"] for a in accepted]
    ids_str = ids[0] if len(ids) == 1 else ", ".join(ids)
    return {
        "accepted": accepted,
        "skipped": skipped,
        "count": len(accepted),
        "message": f"{len(accepted)} pipeline(s) started. Poll GET /api/v1/contracts/{ids_str} for status.",
    }

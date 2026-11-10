import os
import uuid
from trace_ai.common.gcs_client import upload
from trace_ai.config import config
from trace_ai.common.logging_client import log

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


def upload_contract(local_path: str, contract_id: str | None = None) -> dict:
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"File not found: {local_path}")

    if not local_path.lower().endswith(".pdf"):
        raise ValueError(f"Only PDF files are supported. Got: {local_path}")

    file_size = os.path.getsize(local_path)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File exceeds 50MB limit: {file_size} bytes")

    if not contract_id:
        contract_id = f"CNT-{uuid.uuid4().hex[:12].upper()}"

    blob_name = f"contracts/{contract_id}/{os.path.basename(local_path)}"
    gcs_uri = upload(local_path, config.GCS_RAW_BUCKET, blob_name)

    log("ingestion", contract_id, "Contract uploaded to GCS raw zone", gcs_uri=gcs_uri)

    return {"contract_id": contract_id, "gcs_uri": gcs_uri, "file_size_bytes": file_size}

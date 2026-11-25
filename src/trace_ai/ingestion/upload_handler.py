import hashlib
import os
import uuid
from pathlib import Path
from trace_ai.common.gcs_client import upload
from trace_ai.config import config
from trace_ai.common.logger import log

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


def _compute_hash(local_path: str) -> str:
    h = hashlib.sha256()
    with open(local_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_contract(local_path: str, contract_id: str | None = None) -> dict:
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"File not found: {local_path}")

    if not local_path.lower().endswith(".pdf"):
        raise ValueError(f"Only PDF files are supported. Got: {local_path}")

    file_size = os.path.getsize(local_path)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File exceeds 50MB limit: {file_size} bytes")

    file_hash = _compute_hash(local_path)

    if config.DUPLICATE_CHECK_ENABLED:
        from trace_ai.delivery.storage_backend import get_contract_by_hash
        existing = get_contract_by_hash(file_hash)
        if existing:
            raise ValueError(
                f"Duplicate contract detected — already processed as {existing['contract_id']} "
                f"(status: {existing.get('extraction_status', 'unknown')}). "
                f"Set DUPLICATE_CHECK_ENABLED=false to reprocess."
            )

    if not contract_id:
        contract_id = f"CNT-{uuid.uuid4().hex[:12].upper()}"

    blob_name = f"{config.GCS_RAW_PREFIX}/contracts/{contract_id}/{os.path.basename(local_path)}"
    gcs_uri = upload(local_path, config.GCS_BUCKET, blob_name)

    log("Contract uploaded to GCS raw zone", gcs_uri=gcs_uri, file_size_bytes=file_size, file_hash=file_hash)

    return {"contract_id": contract_id, "gcs_uri": gcs_uri, "file_size_bytes": file_size, "file_hash": file_hash}


def upload_contracts_from_folder(folder_path: str) -> list[dict]:
    path = Path(folder_path)
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    pdf_files = sorted(path.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in: {folder_path}")

    results = []
    for pdf in pdf_files:
        try:
            result = upload_contract(str(pdf))
            results.append(result)
        except Exception as e:
            log(f"Failed to upload {pdf.name}", severity="ERROR", error=str(e))
            results.append({"file": pdf.name, "error": str(e)})

    return results

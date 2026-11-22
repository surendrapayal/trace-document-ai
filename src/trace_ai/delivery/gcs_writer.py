from trace_ai.common.gcs_client import upload_json
from trace_ai.config import config
from trace_ai.common.logger import log
from trace_ai.normalization.schema import ContractRecord


def write(record: ContractRecord) -> str:
    blob_name = f"{config.GCS_CURATED_PREFIX}/contracts/{record.contract_id}/output.json"
    gcs_uri = upload_json(
        record.model_dump_json(indent=2),
        config.GCS_BUCKET,
        blob_name,
    )
    log("Contract JSON written to GCS curated zone", gcs_uri=gcs_uri)
    return gcs_uri

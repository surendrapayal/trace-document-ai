from google.cloud import storage
from trace_ai.config import config
from trace_ai.common.logger import log

_client = storage.Client(project=config.GCP_PROJECT_ID)


def upload(local_path: str, bucket_name: str, blob_name: str) -> str:
    bucket = _client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local_path)
    log("GCS upload complete", severity="DEBUG", bucket=bucket_name, blob=blob_name)
    return f"gs://{bucket_name}/{blob_name}"


def download_bytes(bucket_name: str, blob_name: str) -> bytes:
    bucket = _client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    data = blob.download_as_bytes()
    log("GCS download complete", severity="DEBUG", bucket=bucket_name, blob=blob_name, size_bytes=len(data))
    return data


def upload_json(data: str, bucket_name: str, blob_name: str) -> str:
    bucket = _client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type="application/json")
    log("GCS JSON upload complete", severity="DEBUG", bucket=bucket_name, blob=blob_name)
    return f"gs://{bucket_name}/{blob_name}"


def list_blobs(bucket_name: str, prefix: str = "") -> list[str]:
    blobs = [b.name for b in _client.list_blobs(bucket_name, prefix=prefix)]
    log("GCS list blobs", severity="DEBUG", bucket=bucket_name, prefix=prefix, count=len(blobs))
    return blobs

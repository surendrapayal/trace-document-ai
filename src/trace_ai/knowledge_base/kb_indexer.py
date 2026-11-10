import uuid
from google.cloud import aiplatform, storage
from trace_ai.config import config
from trace_ai.common.logging_client import log
from trace_ai.intelligence.embeddings_client import embed

aiplatform.init(project=config.GCP_PROJECT_ID, location=config.GCP_REGION)

_CHUNK_SIZE = 500
_CHUNK_OVERLAP = 50


def _chunk_text(text: str) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        chunks.append(text[start:end].strip())
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return [c for c in chunks if c]


def _list_kb_blobs() -> list[str]:
    client = storage.Client(project=config.GCP_PROJECT_ID)
    return [b.name for b in client.list_blobs(config.GCS_KB_BUCKET, prefix="documents/")]


def _read_blob(blob_name: str) -> str:
    client = storage.Client(project=config.GCP_PROJECT_ID)
    return client.bucket(config.GCS_KB_BUCKET).blob(blob_name).download_as_text()


def _store_chunk(chunk_id: str, text: str) -> None:
    client = storage.Client(project=config.GCP_PROJECT_ID)
    client.bucket(config.GCS_KB_BUCKET).blob(f"chunks/{chunk_id}.txt").upload_from_string(text)


def index_all() -> int:
    log("knowledge_base", "kb_indexer", "Starting KB indexing")

    blob_names = _list_kb_blobs()
    if not blob_names:
        log("knowledge_base", "kb_indexer", "No documents found in KB bucket", severity="WARNING")
        return 0

    index = aiplatform.MatchingEngineIndex(index_name=config.VERTEX_VECTOR_SEARCH_INDEX_ID)

    all_datapoints = []
    total_chunks = 0

    for blob_name in blob_names:
        text = _read_blob(blob_name)
        chunks = _chunk_text(text)
        vectors = embed(chunks)

        for chunk_text, vector in zip(chunks, vectors):
            chunk_id = str(uuid.uuid4())
            _store_chunk(chunk_id, chunk_text)
            all_datapoints.append({
                "datapoint_id": chunk_id,
                "feature_vector": vector,
            })
            total_chunks += 1

        log("knowledge_base", "kb_indexer", f"Chunked {blob_name}", chunks=len(chunks))

    for i in range(0, len(all_datapoints), 100):
        batch = all_datapoints[i: i + 100]
        index.upsert_datapoints(datapoints=batch)
        log("knowledge_base", "kb_indexer", f"Upserted batch {i // 100 + 1}", count=len(batch))

    log("knowledge_base", "kb_indexer", "KB indexing complete", total_chunks=total_chunks)
    return total_chunks


if __name__ == "__main__":
    count = index_all()
    print(f"Indexed {count} chunks into Vector Search.")

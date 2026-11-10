from google.cloud import aiplatform
from trace_ai.config import config
from trace_ai.common.logging_client import log
from trace_ai.common.gcs_client import download_bytes
from trace_ai.intelligence.embeddings_client import embed_single

aiplatform.init(project=config.GCP_PROJECT_ID, location=config.GCP_REGION)


def query(contract_text: str, contract_id: str, top_k: int = 5) -> str:
    query_vector = embed_single(contract_text[:2000])

    index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
        index_endpoint_name=config.VERTEX_VECTOR_SEARCH_ENDPOINT_ID
    )

    response = index_endpoint.find_neighbors(
        deployed_index_id=config.VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID,
        queries=[query_vector],
        num_neighbors=top_k,
    )

    if not response or not response[0]:
        log("intelligence", contract_id, "RAG returned no results")
        return ""

    neighbor_ids = [neighbor.id for neighbor in response[0]]
    log("intelligence", contract_id, "RAG neighbors retrieved", neighbor_ids=neighbor_ids)

    chunks = []
    for neighbor_id in neighbor_ids:
        try:
            text = download_bytes(config.GCS_KB_BUCKET, f"chunks/{neighbor_id}.txt").decode("utf-8")
            chunks.append(text)
        except Exception:
            pass

    return "\n\n---\n\n".join(chunks)

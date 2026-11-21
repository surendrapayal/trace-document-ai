from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    GCP_PROJECT_ID: str = os.environ["GCP_PROJECT_ID"]
    GCP_REGION: str = os.environ["GCP_REGION"]

    GCS_RAW_BUCKET: str = os.environ["GCS_RAW_BUCKET"]
    GCS_PROCESSING_BUCKET: str = os.environ["GCS_PROCESSING_BUCKET"]
    GCS_CURATED_BUCKET: str = os.environ["GCS_CURATED_BUCKET"]
    GCS_KB_BUCKET: str = os.environ["GCS_KB_BUCKET"]

    DOCUMENT_AI_PROCESSOR_ID: str = os.environ["DOCUMENT_AI_PROCESSOR_ID"]
    DOCUMENT_AI_LOCATION: str = os.getenv("DOCUMENT_AI_LOCATION", "us")

    VERTEX_GEMINI_MODEL: str = os.getenv("VERTEX_GEMINI_MODEL", "gemini-1.5-pro")
    VERTEX_EMBEDDING_MODEL: str = os.getenv("VERTEX_EMBEDDING_MODEL", "text-embedding-004")
    VERTEX_VECTOR_SEARCH_INDEX_ID: str = os.environ["VERTEX_VECTOR_SEARCH_INDEX_ID"]
    VERTEX_VECTOR_SEARCH_ENDPOINT_ID: str = os.environ["VERTEX_VECTOR_SEARCH_ENDPOINT_ID"]
    VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID: str = os.getenv(
        "VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID", "trace-kb-deployed"
    )

    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "firestore")  # "firestore" or "bigquery"

    FIRESTORE_COLLECTION_CONTRACTS: str = os.getenv("FIRESTORE_COLLECTION_CONTRACTS", "contracts")
    FIRESTORE_COLLECTION_AUDIT: str = os.getenv("FIRESTORE_COLLECTION_AUDIT", "audit_events")

    BIGQUERY_DATASET: str = os.getenv("BIGQUERY_DATASET", "trace_contracts")
    BIGQUERY_TABLE_CONTRACTS: str = os.getenv("BIGQUERY_TABLE_CONTRACTS", "contracts")
    BIGQUERY_TABLE_AUDIT: str = os.getenv("BIGQUERY_TABLE_AUDIT", "audit_events")

    CONFIDENCE_THRESHOLD_APPROVE: float = float(os.getenv("CONFIDENCE_THRESHOLD_APPROVE", "0.85"))
    CONFIDENCE_THRESHOLD_REVIEW: float = float(os.getenv("CONFIDENCE_THRESHOLD_REVIEW", "0.60"))


config = Config()

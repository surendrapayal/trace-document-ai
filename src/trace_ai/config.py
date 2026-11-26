from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    GCP_PROJECT_ID: str = os.environ["GCP_PROJECT_ID"]
    GCP_REGION: str = os.environ["GCP_REGION"]

    GCS_BUCKET: str = os.environ["GCS_BUCKET"]
    GCS_LANDING_PREFIX: str = os.getenv("GCS_LANDING_PREFIX", "landing")
    GCS_RAW_PREFIX: str = os.getenv("GCS_RAW_PREFIX", "raw")
    GCS_PROCESSING_PREFIX: str = os.getenv("GCS_PROCESSING_PREFIX", "processing")
    GCS_CURATED_PREFIX: str = os.getenv("GCS_CURATED_PREFIX", "curated")
    GCS_KB_PREFIX: str = os.getenv("GCS_KB_PREFIX", "kb")

    DOCUMENT_AI_FORM_PROCESSOR_ID: str = os.environ["DOCUMENT_AI_FORM_PROCESSOR_ID"]
    DOCUMENT_AI_LOCATION: str = os.getenv("DOCUMENT_AI_LOCATION", "us")

    DLP_ENABLED: bool = os.getenv("DLP_ENABLED", "true").lower() == "true"
    DLP_LOCATION: str = os.getenv("DLP_LOCATION", "global")
    DLP_INSPECT_TEMPLATE_NAME: str = os.getenv("DLP_INSPECT_TEMPLATE_NAME", "")
    DLP_DEIDENTIFY_TEMPLATE_NAME: str = os.getenv("DLP_DEIDENTIFY_TEMPLATE_NAME", "")
    DLP_MASK_CHARACTER: str = os.getenv("DLP_MASK_CHARACTER", "*")
    DLP_NUMBER_TO_MASK: int = int(os.getenv("DLP_NUMBER_TO_MASK", "0"))
    # POSSIBLE_REGION, LIKELY, VERY_LIKELY
    DLP_MIN_LIKELIHOOD: str = os.getenv("DLP_MIN_LIKELIHOOD", "LIKELY")

    VERTEX_GEMINI_MODEL: str = os.getenv("VERTEX_GEMINI_MODEL", "gemini-1.5-pro")
    VERTEX_GEMINI_LOCATION: str = os.getenv("VERTEX_GEMINI_LOCATION", "us-central1")
    VERTEX_EMBEDDING_MODEL: str = os.getenv("VERTEX_EMBEDDING_MODEL", "text-embedding-004")
    VERTEX_EMBEDDING_LOCATION: str = os.getenv("VERTEX_EMBEDDING_LOCATION", "us-central1")
    VERTEX_EMBEDDING_DIMENSIONS: int = int(os.getenv("VERTEX_EMBEDDING_DIMENSIONS", "768"))
    VERTEX_VECTOR_SEARCH_INDEX_ID: str = os.environ["VERTEX_VECTOR_SEARCH_INDEX_ID"]
    VERTEX_VECTOR_SEARCH_ENDPOINT_ID: str = os.environ["VERTEX_VECTOR_SEARCH_ENDPOINT_ID"]
    VERTEX_VECTOR_SEARCH_LOCATION: str = os.getenv("VERTEX_VECTOR_SEARCH_LOCATION", "us-central1")
    VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID: str = os.getenv(
        "VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID", "trace-kb-deployed"
    )
    VERTEX_VECTOR_SEARCH_INDEX_DISPLAY_NAME: str = os.getenv(
        "VERTEX_VECTOR_SEARCH_INDEX_DISPLAY_NAME", "trace-kb-index"
    )
    VERTEX_VECTOR_SEARCH_ENDPOINT_DISPLAY_NAME: str = os.getenv(
        "VERTEX_VECTOR_SEARCH_ENDPOINT_DISPLAY_NAME", "trace-kb-endpoint"
    )

    # Index algorithm: "tree_ah" or "brute_force"
    VERTEX_VECTOR_SEARCH_ALGORITHM: str = os.getenv("VERTEX_VECTOR_SEARCH_ALGORITHM", "tree_ah")

    # Distance measure: "DOT_PRODUCT_DISTANCE", "SQUARED_L2_DISTANCE", "L1_DISTANCE", "COSINE_DISTANCE"
    VERTEX_VECTOR_SEARCH_DISTANCE_MEASURE: str = os.getenv(
        "VERTEX_VECTOR_SEARCH_DISTANCE_MEASURE", "DOT_PRODUCT_DISTANCE"
    )

    # Update method: "STREAM_UPDATE" or "BATCH_UPDATE"
    VERTEX_VECTOR_SEARCH_UPDATE_METHOD: str = os.getenv(
        "VERTEX_VECTOR_SEARCH_UPDATE_METHOD", "STREAM_UPDATE"
    )

    # Feature norm type: "UNIT_L2_NORM", "NONE"
    VERTEX_VECTOR_SEARCH_FEATURE_NORM_TYPE: str = os.getenv(
        "VERTEX_VECTOR_SEARCH_FEATURE_NORM_TYPE", "UNIT_L2_NORM"
    )

    # Shard size: "SHARD_SIZE_SMALL", "SHARD_SIZE_MEDIUM", "SHARD_SIZE_LARGE"
    VERTEX_VECTOR_SEARCH_SHARD_SIZE: str = os.getenv(
        "VERTEX_VECTOR_SEARCH_SHARD_SIZE", "SHARD_SIZE_MEDIUM"
    )

    # Tree-AH algorithm tuning
    VERTEX_VECTOR_SEARCH_APPROXIMATE_NEIGHBORS_COUNT: int = int(
        os.getenv("VERTEX_VECTOR_SEARCH_APPROXIMATE_NEIGHBORS_COUNT", "10")
    )
    VERTEX_VECTOR_SEARCH_LEAF_NODE_EMBEDDING_COUNT: int = int(
        os.getenv("VERTEX_VECTOR_SEARCH_LEAF_NODE_EMBEDDING_COUNT", "1000")
    )
    VERTEX_VECTOR_SEARCH_LEAF_NODES_TO_SEARCH_PERCENT: int = int(
        os.getenv("VERTEX_VECTOR_SEARCH_LEAF_NODES_TO_SEARCH_PERCENT", "1")
    )

    # Deployment sizing
    VERTEX_VECTOR_SEARCH_MIN_REPLICAS: int = int(
        os.getenv("VERTEX_VECTOR_SEARCH_MIN_REPLICAS", "1")
    )
    VERTEX_VECTOR_SEARCH_MAX_REPLICAS: int = int(
        os.getenv("VERTEX_VECTOR_SEARCH_MAX_REPLICAS", "2")
    )

    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "firestore")  # "firestore" or "bigquery"

    FIRESTORE_COLLECTION_CONTRACTS: str = os.getenv("FIRESTORE_COLLECTION_CONTRACTS", "contracts")
    FIRESTORE_COLLECTION_AUDIT: str = os.getenv("FIRESTORE_COLLECTION_AUDIT", "audit_events")

    BIGQUERY_DATASET: str = os.getenv("BIGQUERY_DATASET", "trace_contracts")
    BIGQUERY_TABLE_CONTRACTS: str = os.getenv("BIGQUERY_TABLE_CONTRACTS", "contracts")
    BIGQUERY_TABLE_AUDIT: str = os.getenv("BIGQUERY_TABLE_AUDIT", "audit_events")
    BIGQUERY_LOCATION: str = os.getenv("BIGQUERY_LOCATION", "US")

    CONFIDENCE_THRESHOLD_APPROVE: float = float(os.getenv("CONFIDENCE_THRESHOLD_APPROVE", "0.85"))
    CONFIDENCE_THRESHOLD_REVIEW: float = float(os.getenv("CONFIDENCE_THRESHOLD_REVIEW", "0.60"))

    DUPLICATE_CHECK_ENABLED: bool = os.getenv("DUPLICATE_CHECK_ENABLED", "true").lower() == "true"
    MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_BYTES", "50")) * 1024 * 1024

    WEBHOOK_ENABLED: bool = os.getenv("WEBHOOK_ENABLED", "false").lower() == "true"
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
    WEBHOOK_TIMEOUT_SECONDS: int = int(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "10"))

    REST_API_KEY: str = os.getenv("REST_API_KEY", "")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "false").lower() == "true"
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "logs/trace_ai.log")
    LOG_FILE_MAX_BYTES: int = int(os.getenv("LOG_FILE_MAX_BYTES", str(5 * 1024 * 1024)))  # 5MB
    LOG_FILE_BACKUP_COUNT: int = int(os.getenv("LOG_FILE_BACKUP_COUNT", "3"))


config = Config()

"""
One-time script to create and deploy the Vertex AI Vector Search index.
Run this ONCE before running the pipeline or kb_indexer.

Usage:
    python scripts/create_index.py

After completion, copy the printed IDs into your .env file:
    VERTEX_VECTOR_SEARCH_INDEX_ID=...
    VERTEX_VECTOR_SEARCH_ENDPOINT_ID=...

Note: Index creation takes approximately 30-60 minutes.
"""

from google.cloud import aiplatform
from trace_ai.config import config

INDEX_DISPLAY_NAME = "trace-kb-index"
ENDPOINT_DISPLAY_NAME = "trace-kb-endpoint"
DEPLOYED_INDEX_ID = "trace-kb-deployed"
DIMENSIONS = 768  # text-embedding-004 output dimension


def main():
    aiplatform.init(project=config.GCP_PROJECT_ID, location=config.GCP_REGION)

    print(f"Creating Vector Search index '{INDEX_DISPLAY_NAME}'...")
    print("This will take 30-60 minutes. Do not interrupt.")

    index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=INDEX_DISPLAY_NAME,
        dimensions=DIMENSIONS,
        approximate_neighbors_count=10,
        distance_measure_type="DOT_PRODUCT_DISTANCE",
        index_update_method="STREAM_UPDATE",
    )

    index_id = index.resource_name.split("/")[-1]
    print(f"\nIndex created: {index.resource_name}")
    print(f"Index ID: {index_id}")

    print(f"\nCreating index endpoint '{ENDPOINT_DISPLAY_NAME}'...")
    endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name=ENDPOINT_DISPLAY_NAME,
        public_endpoint_enabled=True,
    )

    endpoint_id = endpoint.resource_name.split("/")[-1]
    print(f"Endpoint created: {endpoint.resource_name}")
    print(f"Endpoint ID: {endpoint_id}")

    print(f"\nDeploying index to endpoint as '{DEPLOYED_INDEX_ID}'...")
    endpoint.deploy_index(
        index=index,
        deployed_index_id=DEPLOYED_INDEX_ID,
        display_name=DEPLOYED_INDEX_ID,
        min_replica_count=1,
        max_replica_count=2,
    )

    print("\n✓ Done. Add these to your .env file:")
    print(f"VERTEX_VECTOR_SEARCH_INDEX_ID={index_id}")
    print(f"VERTEX_VECTOR_SEARCH_ENDPOINT_ID={endpoint_id}")
    print(f"VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID={DEPLOYED_INDEX_ID}")


if __name__ == "__main__":
    main()

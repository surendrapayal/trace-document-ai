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


def main():
    aiplatform.init(project=config.GCP_PROJECT_ID, location=config.GCP_REGION)

    print(f"Creating Vector Search index '{config.VERTEX_VECTOR_SEARCH_INDEX_DISPLAY_NAME}'...")
    print("This will take 30-60 minutes. Do not interrupt.")

    index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=config.VERTEX_VECTOR_SEARCH_INDEX_DISPLAY_NAME,
        dimensions=config.VERTEX_EMBEDDING_DIMENSIONS,
        approximate_neighbors_count=10,
        distance_measure_type="DOT_PRODUCT_DISTANCE",
        index_update_method="STREAM_UPDATE",
    )

    index_id = index.resource_name.split("/")[-1]
    print(f"\nIndex created: {index.resource_name}")
    print(f"Index ID: {index_id}")

    print(f"\nCreating index endpoint '{config.VERTEX_VECTOR_SEARCH_ENDPOINT_DISPLAY_NAME}'...")
    endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name=config.VERTEX_VECTOR_SEARCH_ENDPOINT_DISPLAY_NAME,
        public_endpoint_enabled=True,
    )

    endpoint_id = endpoint.resource_name.split("/")[-1]
    print(f"Endpoint created: {endpoint.resource_name}")
    print(f"Endpoint ID: {endpoint_id}")

    print(f"\nDeploying index to endpoint as '{config.VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID}'...")
    endpoint.deploy_index(
        index=index,
        deployed_index_id=config.VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID,
        display_name=config.VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID,
        min_replica_count=1,
        max_replica_count=2,
    )

    print("\n✓ Done. Add these to your .env file:")
    print(f"VERTEX_VECTOR_SEARCH_INDEX_ID={index_id}")
    print(f"VERTEX_VECTOR_SEARCH_ENDPOINT_ID={endpoint_id}")
    print(f"VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID={config.VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID}")


if __name__ == "__main__":
    main()

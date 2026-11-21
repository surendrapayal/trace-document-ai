"""
One-time script to create and deploy the Vertex AI Vector Search index.
Run this ONCE before running the pipeline or kb_indexer.

Usage:
    python scripts/create_index.py

After completion, copy the printed IDs into your .env file:
    VERTEX_VECTOR_SEARCH_INDEX_ID=...
    VERTEX_VECTOR_SEARCH_ENDPOINT_ID=...

Note: Index creation takes approximately 30-60 minutes.

Algorithm options (VERTEX_VECTOR_SEARCH_ALGORITHM):
    tree_ah     — Approximate nearest neighbour using Tree-AH. Best for large KB + low latency.
    brute_force — Exact nearest neighbour. Only suitable for small datasets (<10K vectors).

Distance measure options (VERTEX_VECTOR_SEARCH_DISTANCE_MEASURE):
    DOT_PRODUCT_DISTANCE  — Best for normalised text embeddings (text-embedding-004). Default.
    SQUARED_L2_DISTANCE   — Euclidean distance. Good for non-normalised vectors.
    L1_DISTANCE           — Manhattan distance.
    COSINE_DISTANCE       — Cosine similarity.

Update method options (VERTEX_VECTOR_SEARCH_UPDATE_METHOD):
    STREAM_UPDATE — Incremental upserts. Required for kb_indexer.py. Default.
    BATCH_UPDATE  — Full index rebuild from GCS. Not compatible with kb_indexer.py.

Feature norm type options (VERTEX_VECTOR_SEARCH_FEATURE_NORM_TYPE):
    UNIT_L2_NORM — Normalises vectors before distance calculation. Recommended for text. Default.
    NONE         — No normalisation.

Shard size options (VERTEX_VECTOR_SEARCH_SHARD_SIZE):
    SHARD_SIZE_SMALL  — Up to 1GB of vectors.
    SHARD_SIZE_MEDIUM — Up to 10GB of vectors. Default.
    SHARD_SIZE_LARGE  — Up to 100GB of vectors.
"""

from google.cloud import aiplatform
from trace_ai.config import config


def _create_index() -> aiplatform.MatchingEngineIndex:
    common_kwargs = dict(
        display_name=config.VERTEX_VECTOR_SEARCH_INDEX_DISPLAY_NAME,
        dimensions=config.VERTEX_EMBEDDING_DIMENSIONS,
        distance_measure_type=config.VERTEX_VECTOR_SEARCH_DISTANCE_MEASURE,
        feature_norm_type=config.VERTEX_VECTOR_SEARCH_FEATURE_NORM_TYPE,
        index_update_method=config.VERTEX_VECTOR_SEARCH_UPDATE_METHOD,
        shard_size=config.VERTEX_VECTOR_SEARCH_SHARD_SIZE,
    )

    if config.VERTEX_VECTOR_SEARCH_ALGORITHM == "brute_force":
        print("Algorithm           : Brute Force (exact nearest neighbour)")
        return aiplatform.MatchingEngineIndex.create_brute_force_index(**common_kwargs)

    # Default: Tree-AH
    print("Algorithm           : Tree-AH (approximate nearest neighbour)")
    return aiplatform.MatchingEngineIndex.create_tree_ah_index(
        **common_kwargs,
        approximate_neighbors_count=config.VERTEX_VECTOR_SEARCH_APPROXIMATE_NEIGHBORS_COUNT,
        leaf_node_embedding_count=config.VERTEX_VECTOR_SEARCH_LEAF_NODE_EMBEDDING_COUNT,
        leaf_nodes_to_search_percent=config.VERTEX_VECTOR_SEARCH_LEAF_NODES_TO_SEARCH_PERCENT,
    )


def main():
    aiplatform.init(project=config.GCP_PROJECT_ID, location=config.GCP_REGION)

    print(f"\nCreating Vector Search index '{config.VERTEX_VECTOR_SEARCH_INDEX_DISPLAY_NAME}'...")
    print(f"Dimensions          : {config.VERTEX_EMBEDDING_DIMENSIONS}")
    print(f"Distance measure    : {config.VERTEX_VECTOR_SEARCH_DISTANCE_MEASURE}")
    print(f"Feature norm type   : {config.VERTEX_VECTOR_SEARCH_FEATURE_NORM_TYPE}")
    print(f"Update method       : {config.VERTEX_VECTOR_SEARCH_UPDATE_METHOD}")
    print(f"Shard size          : {config.VERTEX_VECTOR_SEARCH_SHARD_SIZE}")
    if config.VERTEX_VECTOR_SEARCH_ALGORITHM == "tree_ah":
        print(f"Approx neighbours   : {config.VERTEX_VECTOR_SEARCH_APPROXIMATE_NEIGHBORS_COUNT}")
        print(f"Leaf node emb count : {config.VERTEX_VECTOR_SEARCH_LEAF_NODE_EMBEDDING_COUNT}")
        print(f"Fraction leaf nodes : {config.VERTEX_VECTOR_SEARCH_LEAF_NODES_TO_SEARCH_PERCENT}%")
    print("\nThis will take 30-60 minutes. Do not interrupt.\n")

    index = _create_index()
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
        min_replica_count=config.VERTEX_VECTOR_SEARCH_MIN_REPLICAS,
        max_replica_count=config.VERTEX_VECTOR_SEARCH_MAX_REPLICAS,
    )

    print("\n✓ Done. Add these to your .env file:")
    print(f"VERTEX_VECTOR_SEARCH_INDEX_ID={index_id}")
    print(f"VERTEX_VECTOR_SEARCH_ENDPOINT_ID={endpoint_id}")
    print(f"VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID={config.VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID}")


if __name__ == "__main__":
    main()

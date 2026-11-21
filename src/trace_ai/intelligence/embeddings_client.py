import vertexai
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
from trace_ai.config import config


def _model() -> TextEmbeddingModel:
    vertexai.init(project=config.GCP_PROJECT_ID, location=config.VERTEX_EMBEDDING_LOCATION)
    return TextEmbeddingModel.from_pretrained(config.VERTEX_EMBEDDING_MODEL)


def embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    inputs = [TextEmbeddingInput(text=t, task_type=task_type) for t in texts]
    embeddings = _model().get_embeddings(inputs, output_dimensionality=config.VERTEX_EMBEDDING_DIMENSIONS)
    return [e.values for e in embeddings]


def embed_single(text: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
    return embed([text], task_type=task_type)[0]

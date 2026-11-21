import vertexai
from vertexai.language_models import TextEmbeddingModel
from trace_ai.config import config

vertexai.init(project=config.GCP_PROJECT_ID, location=config.VERTEX_AI_LOCATION)

_model = TextEmbeddingModel.from_pretrained(config.VERTEX_EMBEDDING_MODEL)


def embed(texts: list[str]) -> list[list[float]]:
    embeddings = _model.get_embeddings(texts)
    return [e.values for e in embeddings]


def embed_single(text: str) -> list[float]:
    return embed([text])[0]

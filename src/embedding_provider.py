from typing import List

from .config import ComfreyConfig
from .openai_compatible_client import OpenAICompatibleClient


class EmbeddingProvider:
    def __init__(self, config: ComfreyConfig):
        self.config = config
        self._local_model = None
        self._api_client = OpenAICompatibleClient(config)

    def similarity(self, text1: str, text2: str) -> float:
        embeddings = self.embed([text1, text2])
        return self._cosine_similarity(embeddings[0], embeddings[1])

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.config.enable_embedding_similarity:
            raise RuntimeError("Embedding similarity is disabled")

        provider = self.config.embedding_provider
        if provider == "local_qwen":
            if self.config.strict_paper_mode:
                raise ValueError("Paper mode uses Yunqiao/OpenAI-compatible embeddings, not local_qwen")
            return self._embed_with_sentence_transformers(texts)
        if provider in {"local", "local_sentence_transformers"}:
            return self._embed_with_sentence_transformers(texts)
        if provider == "yunqiao":
            return self._api_client.embeddings(texts)
        if provider == "openai_compatible":
            return self._api_client.embeddings(texts)

        raise ValueError(f"Unsupported embedding provider: {provider}")

    def _embed_with_sentence_transformers(self, texts: List[str]) -> List[List[float]]:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Local embedding provider requires sentence-transformers and a configured "
                "local embedding model."
            ) from exc

        if self._local_model is None:
            model_name_or_path = self.config.embedding_model_path or self.config.embedding_model_name
            self._local_model = SentenceTransformer(model_name_or_path)
        embeddings = self._local_model.encode(texts)
        return [list(vector) for vector in embeddings]

    def _cosine_similarity(self, vec1, vec2) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

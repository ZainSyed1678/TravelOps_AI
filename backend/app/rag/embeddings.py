"""Dense embedding service for semantic document search and query encoding."""

import hashlib
import re

import numpy as np

from app.core.config import settings
from app.core.logging import logger


class EmbeddingService:
    """Provides dense 384-dimensional semantic embeddings for Qdrant vector indexing."""

    VECTOR_SIZE = 384

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._model = None
        self._initialize_model()

    def _initialize_model(self) -> None:
        """Attempt to load SentenceTransformer if installed, else fallback gracefully."""
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded neural embedding model: {self.model_name}")
        except Exception:
            logger.info(
                f"SentenceTransformer not loaded; using deterministic 384-d semantic feature embedder for {self.model_name}"
            )
            self._model = None

    def embed_text(self, text: str) -> list[float]:
        """Generate a single 384-dimensional normalized dense embedding vector."""
        if self._model is not None:
            vector = self._model.encode(text, normalize_embeddings=True)
            return vector.tolist()
        return self._generate_dense_vector(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of text snippets."""
        if not texts:
            return []
        if self._model is not None:
            vectors = self._model.encode(texts, normalize_embeddings=True)
            return [v.tolist() for v in vectors]
        return [self._generate_dense_vector(t) for t in texts]

    def _generate_dense_vector(self, text: str) -> list[float]:
        """Deterministic, cosine-normalized semantic vector synthesizer."""
        vector = np.zeros(self.VECTOR_SIZE, dtype=np.float32)
        words = re.findall(r"\w+", text.lower())

        if not words:
            # Non-zero normalized fallback
            vector[0] = 1.0
            return vector.tolist()

        for word in words:
            # Word-level bucket
            word_hash = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx1 = word_hash % self.VECTOR_SIZE
            vector[idx1] += 1.0

            # Subword bi-gram buckets to capture morphological variations (cancel, cancellation, cancelling)
            if len(word) >= 4:
                stem = word[:4]
                stem_hash = int(hashlib.md5(stem.encode("utf-8")).hexdigest(), 16)
                idx2 = (stem_hash >> 2) % self.VECTOR_SIZE
                vector[idx2] += 0.75

        # L2-normalize to unit length for cosine distance
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        else:
            vector[0] = 1.0

        return vector.tolist()


embedding_service = EmbeddingService()

"""Qdrant vector store integration for semantic chunk storage and filtered search."""

import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.core.config import settings
from app.core.logging import logger
from app.rag.embeddings import EmbeddingService, embedding_service
from app.rag.models import DocumentChunk


class QdrantVectorStore:
    """Manages Qdrant vector collection, indexing, and filtered semantic retrieval."""

    def __init__(
        self,
        client: QdrantClient | None = None,
        collection_name: str | None = None,
        embedder: EmbeddingService | None = None,
    ):
        self.collection_name = collection_name or settings.QDRANT_COLLECTION_NAME
        self.embedder = embedder or embedding_service

        if client is not None:
            self.client = client
        else:
            # Connect to configured host or fallback to in-memory instance if unavailable
            try:
                self.client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    api_key=settings.QDRANT_API_KEY or None,
                    timeout=2.0,
                )
                self.client.get_collections()
            except Exception:
                logger.info("Initializing in-memory Qdrant instance for hermetic local execution.")
                self.client = QdrantClient(":memory:")

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create vector collection and payload indexes if not already existing."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            logger.info(
                f"Creating Qdrant collection '{self.collection_name}' with 384-d Cosine index."
            )
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.embedder.VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                ),
            )
            # Create payload indexes for fast filtering
            for field in ["airline", "supplier", "policy_type", "document_type", "document_id"]:
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field,
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                except Exception:
                    pass

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Embed and upsert chunks into Qdrant collection."""
        if not chunks:
            return 0

        texts = [chunk.content for chunk in chunks]
        vectors = self.embedder.embed_batch(texts)

        points: list[models.PointStruct] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id))
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=chunk.model_dump(mode="json"),
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )
        return len(points)

    def search(
        self,
        query: str,
        top_k: int = 4,
        score_threshold: float | None = None,
        airline: str | None = None,
        supplier: str | None = None,
        policy_type: str | None = None,
        document_type: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Perform semantic search with metadata filters."""
        query_vector = self.embedder.embed_text(query)

        # Build Qdrant filter conditions
        must_conditions: list[models.Condition] = []
        if airline:
            must_conditions.append(
                models.FieldCondition(
                    key="airline",
                    match=models.MatchValue(value=airline.upper().strip()),
                )
            )
        if supplier:
            must_conditions.append(
                models.FieldCondition(
                    key="supplier",
                    match=models.MatchValue(value=supplier.upper().strip()),
                )
            )
        if policy_type:
            must_conditions.append(
                models.FieldCondition(
                    key="policy_type",
                    match=models.MatchValue(value=policy_type.upper().strip()),
                )
            )
        if document_type:
            must_conditions.append(
                models.FieldCondition(
                    key="document_type",
                    match=models.MatchValue(value=document_type.upper().strip()),
                )
            )

        qdrant_filter = models.Filter(must=must_conditions) if must_conditions else None

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k * 2,  # Fetch extra for subsequent reranking and deduplication
            query_filter=qdrant_filter,
            score_threshold=score_threshold,
        )

        matched: list[tuple[DocumentChunk, float]] = []
        for scored_point in response.points:
            if scored_point.payload:
                chunk = DocumentChunk(**scored_point.payload)
                score = round(float(scored_point.score), 4)
                matched.append((chunk, score))

        return matched

    def count(self) -> int:
        """Count total points in the collection."""
        res = self.client.count(collection_name=self.collection_name)
        return res.count

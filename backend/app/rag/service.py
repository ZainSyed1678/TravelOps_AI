"""Unified RAG service integrating chunking, Qdrant retrieval, reranking, and synthesis."""

import json
import time
from pathlib import Path

from app.core.logging import logger
from app.rag.chunker import StructureAwareChunker
from app.rag.models import DocumentChunk, RAGQueryRequest, RAGQueryResponse
from app.rag.reranker import RerankerService, reranker_service
from app.rag.synthesizer import AnswerSynthesizer, synthesizer
from app.rag.vector_store import QdrantVectorStore
from ingestion.models import IngestedDocument


class RAGService:
    """Production RAG orchestration service."""

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        chunker: StructureAwareChunker | None = None,
        reranker: RerankerService | None = None,
        answer_synthesizer: AnswerSynthesizer | None = None,
    ):
        self.vector_store = vector_store or QdrantVectorStore()
        self.chunker = chunker or StructureAwareChunker()
        self.reranker = reranker or reranker_service
        self.synthesizer = answer_synthesizer or synthesizer

    def index_processed_documents(self, processed_dir: str = "data/processed") -> int:
        """Load and index all processed JSON documents into Qdrant vector store."""
        p_dir = Path(processed_dir)
        if not p_dir.exists():
            return 0

        all_chunks: list[DocumentChunk] = []

        for json_file in p_dir.glob("doc-*.json"):
            try:
                doc_data = json.loads(json_file.read_text(encoding="utf-8"))
                document = IngestedDocument(**doc_data)
                chunks = self.chunker.chunk_document(document)
                all_chunks.extend(chunks)
            except Exception as exc:
                logger.error(f"Error loading processed document {json_file.name}: {exc}")

        if all_chunks:
            indexed_count = self.vector_store.upsert_chunks(all_chunks)
            logger.info(
                f"Indexed {indexed_count} chunks into Qdrant collection '{self.vector_store.collection_name}'"
            )
            try:
                from app.caching import cache_manager

                cache_manager.invalidate_tag("rag_policy")
            except Exception:
                pass
            return indexed_count
        return 0

    def query(self, request: RAGQueryRequest) -> RAGQueryResponse:
        """Execute end-to-end RAG retrieval, reranking, and grounded synthesis."""
        start_time = time.perf_counter()

        # Check cache
        cache_key = None
        try:
            from app.caching import cache_manager

            cache_key = f"rag_query:{request.query.lower().strip()}:{request.airline}:{request.policy_type}"
            cached_res = cache_manager.get(cache_key, namespace="travelops:rag")
            if cached_res is not None:
                return RAGQueryResponse(**cached_res)
        except Exception:
            cache_key = None

        # Step 1: Semantic Vector Search in Qdrant with Metadata Filters (fetch wider candidate pool for hybrid reranker)
        retrieval_start = time.perf_counter()
        candidates = self.vector_store.search(
            query=request.query,
            top_k=max(request.top_k * 3, 10),
            score_threshold=None,
            airline=request.airline,
            supplier=request.supplier,
            policy_type=request.policy_type,
            document_type=request.document_type,
        )
        retrieval_ms = round((time.perf_counter() - retrieval_start) * 1000, 2)

        # Step 2: Hybrid Reranking and Context Deduplication
        reranked_chunks = self.reranker.rerank_and_deduplicate(
            query=request.query,
            candidates=candidates,
            top_k=request.top_k,
        )

        total_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Step 3: Grounded Synthesis with Citation Validation
        response = self.synthesizer.synthesize(
            query=request.query,
            retrieved_chunks=reranked_chunks,
            retrieval_latency_ms=retrieval_ms,
            total_latency_ms=total_ms,
        )
        try:
            from app.observability.metrics import record_rag_query

            record_rag_query("success", total_ms / 1000.0, len(response.sources))
        except Exception:
            pass

        if cache_key:
            try:
                from app.caching import cache_manager

                cache_manager.set(
                    key=cache_key,
                    value=response.model_dump(mode="json"),
                    ttl_seconds=600,
                    namespace="travelops:rag",
                    tags=["rag_policy"],
                )
            except Exception:
                pass

        return response


rag_service = RAGService()

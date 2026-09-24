"""Hybrid reranking and context deduplication service."""

import re

from app.rag.models import DocumentChunk


class RerankerService:
    """Combines semantic scores with lexical term matches and removes redundant chunks."""

    def __init__(self, semantic_weight: float = 0.65):
        self.semantic_weight = semantic_weight

    def rerank_and_deduplicate(
        self,
        query: str,
        candidates: list[tuple[DocumentChunk, float]],
        top_k: int = 4,
    ) -> list[tuple[DocumentChunk, float]]:
        """Rerank candidates using hybrid scoring and filter out semantic duplicates."""
        if not candidates:
            return []

        query_tokens = set(re.findall(r"\w+", query.lower()))

        scored_candidates: list[tuple[DocumentChunk, float]] = []

        for chunk, semantic_score in candidates:
            chunk_tokens = set(re.findall(r"\w+", chunk.content.lower()))
            overlap = len(query_tokens.intersection(chunk_tokens))
            lexical_score = overlap / max(1, len(query_tokens))

            # Hybrid score computation
            hybrid_score = (self.semantic_weight * semantic_score) + (
                (1.0 - self.semantic_weight) * lexical_score
            )
            scored_candidates.append((chunk, round(hybrid_score, 4)))

        # Sort descending by hybrid score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Context Deduplication: filter out near-identical chunks from same document
        deduplicated: list[tuple[DocumentChunk, float]] = []

        for chunk, score in scored_candidates:
            chunk_words = set(re.findall(r"\w+", chunk.content.lower()))
            is_duplicate = False

            for existing_chunk, _ in deduplicated:
                if existing_chunk.document_id == chunk.document_id:
                    existing_words = set(re.findall(r"\w+", existing_chunk.content.lower()))
                    intersection = len(chunk_words.intersection(existing_words))
                    union = len(chunk_words.union(existing_words))
                    jaccard = intersection / max(1, union)
                    if jaccard > 0.65:
                        is_duplicate = True
                        break

            if not is_duplicate:
                deduplicated.append((chunk, score))

            if len(deduplicated) >= top_k:
                break

        return deduplicated


reranker_service = RerankerService()

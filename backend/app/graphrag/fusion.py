"""GraphRAG Context Fusion module.

Synthesizes structured Knowledge Graph facts and unstructured dense vector text chunks
into a unified, reranked, and citation-ready context for grounded LLM generation.
"""

from typing import Any

from app.graphrag.models import ExtractedEntity, FusedContext, GraphFact, RetrievedChunk


class GraphRAGContextFusion:
    """Combines structured relational facts and unstructured document chunks."""

    def fuse_context(
        self,
        query: str,
        graph_facts: list[GraphFact],
        retrieved_chunks: list[RetrievedChunk],
        extracted_entities: list[ExtractedEntity],
    ) -> FusedContext:
        """Fuse and format graph facts and retrieved chunks into a prompt-ready context."""
        # 1. Score and prioritize chunks based on entity alignment
        prioritized_chunks = self._align_and_prioritize_chunks(retrieved_chunks, extracted_entities)

        # 2. Build structured prompt context
        lines: list[str] = []

        # Section A: Recognized Entities
        if extracted_entities:
            lines.append("### Recognized Travel Entities:")
            for ent in extracted_entities:
                lines.append(f"- {ent.entity_type}: {ent.value} (ID: {ent.normalized_id or ent.value})")
            lines.append("")

        # Section B: Structured Knowledge Graph Facts
        if graph_facts:
            lines.append("### Verified Knowledge Graph Structural Facts:")
            for fact in graph_facts:
                lines.append(f"- {fact.to_readable_sentence()}")
            lines.append("")

        # Section C: Unstructured Retrieved Policy & Operational Documents
        if prioritized_chunks:
            lines.append("### Retrieved Document Context & Policy Clauses:")
            for idx, chunk in enumerate(prioritized_chunks, start=1):
                doc_id = chunk.document_id
                source = chunk.source
                sec = chunk.section_title or "General"
                lines.append(f"[Source {idx}: {source} | DocID: {doc_id} | Section: {sec}]")
                lines.append(f"{chunk.content.strip()}")
                lines.append("")

        formatted_context = "\n".join(lines)

        # Convert chunks to dict representation for API serialization
        chunks_data: list[dict[str, Any]] = [
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "source": c.source,
                "section_title": c.section_title,
                "content": c.content,
                "score": c.score,
                "metadata": c.metadata,
            }
            for c in prioritized_chunks
        ]

        return FusedContext(
            graph_facts=graph_facts,
            retrieved_chunks=chunks_data,
            extracted_entities=extracted_entities,
            formatted_prompt_context=formatted_context,
        )

    def _align_and_prioritize_chunks(
        self,
        chunks: list[RetrievedChunk],
        entities: list[ExtractedEntity],
    ) -> list[RetrievedChunk]:
        """Boost chunks whose content or metadata matches recognized entity identifiers."""
        if not entities or not chunks:
            return chunks

        entity_tokens = set()
        for e in entities:
            if e.value:
                entity_tokens.add(e.value.lower())
            if e.normalized_id:
                entity_tokens.add(e.normalized_id.lower())

        scored_chunks: list[tuple[float, RetrievedChunk]] = []
        for chunk in chunks:
            boost = 0.0
            content_lower = chunk.content.lower()
            metadata_str = str(chunk.metadata).lower()

            for tok in entity_tokens:
                if tok in content_lower:
                    boost += 0.15
                if tok in metadata_str:
                    boost += 0.20

            final_score = chunk.score + boost
            # Update score on copy or original
            chunk.score = round(final_score, 4)
            scored_chunks.append((final_score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored_chunks]


context_fusion = GraphRAGContextFusion()

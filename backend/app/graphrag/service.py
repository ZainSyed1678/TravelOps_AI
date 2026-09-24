"""GraphRAG Service orchestrating entity extraction, graph retrieval, vector search, fusion, and synthesis."""

import time

from app.graphrag.entity_extractor import TravelEntityExtractor, entity_extractor
from app.graphrag.fusion import GraphRAGContextFusion, context_fusion
from app.graphrag.models import (
    GraphRAGExplanation,
    GraphRAGRequest,
    GraphRAGResponse,
)
from app.graphrag.retriever import GraphRAGRetriever
from app.graphrag.synthesizer import GraphRAGSynthesizer, graphrag_synthesizer


class GraphRAGService:
    """Production GraphRAG pipeline service combining graph and dense vector retrieval."""

    def __init__(
        self,
        extractor: TravelEntityExtractor | None = None,
        retriever: GraphRAGRetriever | None = None,
        fusion: GraphRAGContextFusion | None = None,
        synthesizer: GraphRAGSynthesizer | None = None,
    ):
        self.extractor = extractor or entity_extractor
        self.retriever = retriever or GraphRAGRetriever()
        self.fusion = fusion or context_fusion
        self.synthesizer = synthesizer or graphrag_synthesizer

    def query(self, request: GraphRAGRequest) -> GraphRAGResponse:
        """Execute end-to-end GraphRAG query with entity-guided retrieval and fusion."""
        start_time = time.perf_counter()

        # Step 1: Entity Extraction & Disambiguation
        entities = self.extractor.extract_entities(
            query=request.query,
            airline_hint=request.airline,
            flight_hint=request.flight_number,
            booking_hint=request.booking_reference,
            policy_hint=request.policy_type,
        )

        # Step 2: Knowledge Graph Traversal & Entity-Constrained Vector Search
        retrieval_start = time.perf_counter()
        graph_facts, chunks, _ = self.retriever.retrieve(
            query=request.query,
            entities=entities,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
        )
        retrieval_ms = round((time.perf_counter() - retrieval_start) * 1000, 2)

        # Step 3: Graph and Vector Context Fusion
        fused_context = self.fusion.fuse_context(
            query=request.query,
            graph_facts=graph_facts,
            retrieved_chunks=chunks,
            extracted_entities=entities,
        )

        # Step 4: Grounded Answer Synthesis with Citation Validation
        answer, citations = self.synthesizer.synthesize(
            query=request.query,
            fused_context=fused_context,
        )

        total_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return GraphRAGResponse(
            query=request.query,
            answer=answer,
            graph_facts=graph_facts,
            citations=citations,
            entities=entities,
            retrieval_latency_ms=retrieval_ms,
            total_latency_ms=total_ms,
        )

    def explain(self, request: GraphRAGRequest) -> GraphRAGExplanation:
        """Provide diagnostic explanation of entities, graph facts, and retrieved vector chunks."""
        start_time = time.perf_counter()

        # Step 1: Extract Entities
        entities = self.extractor.extract_entities(
            query=request.query,
            airline_hint=request.airline,
            flight_hint=request.flight_number,
            booking_hint=request.booking_reference,
            policy_hint=request.policy_type,
        )

        # Step 2: Retrieve Graph Facts and Vector Chunks
        retrieval_start = time.perf_counter()
        graph_facts, chunks, applied_filters = self.retriever.retrieve(
            query=request.query,
            entities=entities,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
        )
        retrieval_ms = round((time.perf_counter() - retrieval_start) * 1000, 2)

        # Step 3: Fuse Context
        fused_context = self.fusion.fuse_context(
            query=request.query,
            graph_facts=graph_facts,
            retrieved_chunks=chunks,
            extracted_entities=entities,
        )

        total_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return GraphRAGExplanation(
            query=request.query,
            extracted_entities=entities,
            graph_facts_count=len(graph_facts),
            graph_facts=graph_facts,
            vector_chunks_count=len(fused_context.retrieved_chunks),
            vector_chunks=fused_context.retrieved_chunks,
            entity_filters_applied=applied_filters,
            retrieval_latency_ms=retrieval_ms,
            total_latency_ms=total_ms,
        )


graphrag_service = GraphRAGService()

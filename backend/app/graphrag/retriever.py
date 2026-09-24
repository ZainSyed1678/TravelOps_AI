"""GraphRAG Retriever coordinating Knowledge Graph subgraph extraction with entity-constrained vector search."""

from typing import Any

from app.core.logging import logger
from app.graph.service import GraphService, graph_service
from app.graphrag.models import ExtractedEntity, GraphFact, RetrievedChunk
from app.rag.vector_store import QdrantVectorStore


class GraphRAGRetriever:
    """Retrieves structural graph facts from Neo4j/in-memory graph and dense vector chunks from Qdrant."""

    def __init__(
        self,
        graph_svc: GraphService | None = None,
        vector_store: QdrantVectorStore | None = None,
    ):
        self.graph_svc = graph_svc or graph_service
        self.vector_store = vector_store or QdrantVectorStore()

    def retrieve(
        self,
        query: str,
        entities: list[ExtractedEntity],
        top_k: int = 5,
        score_threshold: float = 0.2,
    ) -> tuple[list[GraphFact], list[RetrievedChunk], dict[str, Any]]:
        """Extract multi-hop graph facts and retrieve vector chunks with entity-guided filtering."""
        # 1. Extract structural graph facts
        graph_facts = self._extract_graph_facts(entities)

        # 2. Build entity-based vector filters
        vector_filters = self._build_vector_filters(entities)
        airline_code = vector_filters.get("airline")
        policy_type = vector_filters.get("policy_type")
        effective_threshold = score_threshold if score_threshold > 0 else None

        # 3. Retrieve dense chunks from Qdrant using entity filters
        raw_results = self.vector_store.search(
            query=query,
            top_k=top_k,
            score_threshold=effective_threshold,
            airline=airline_code,
            policy_type=policy_type,
        )

        # If strict policy_type filtering returned fewer than 2 results, relax policy_type
        if len(raw_results) < 2 and policy_type and airline_code:
            relaxed_airline_results = self.vector_store.search(
                query=query,
                top_k=top_k,
                score_threshold=effective_threshold,
                airline=airline_code,
            )
            raw_results = relaxed_airline_results

        chunks: list[RetrievedChunk] = [
            RetrievedChunk(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                source=c.source,
                content=c.content,
                score=round(score, 4),
                section_title=c.section,
                metadata=c.metadata,
            )
            for c, score in raw_results
        ]

        # If still < 2 chunks, relax airline filter completely
        if len(chunks) < 2:
            logger.info("Filtered vector retrieval yielded < 2 chunks; executing relaxed search.")
            fallback_raw = self.vector_store.search(
                query=query,
                top_k=top_k,
                score_threshold=None,
            )
            seen_ids = {c.chunk_id for c in chunks}
            for fc, score in fallback_raw:
                if fc.chunk_id not in seen_ids:
                    chunks.append(
                        RetrievedChunk(
                            chunk_id=fc.chunk_id,
                            document_id=fc.document_id,
                            source=fc.source,
                            content=fc.content,
                            score=round(score, 4),
                            section_title=fc.section,
                            metadata=fc.metadata,
                        )
                    )
                    seen_ids.add(fc.chunk_id)

        return graph_facts, chunks, vector_filters

    def _extract_graph_facts(self, entities: list[ExtractedEntity]) -> list[GraphFact]:
        """Traverse Knowledge Graph for all recognized entities."""
        facts: list[GraphFact] = []
        seen_triples = set()

        def add_fact(sub: str, sub_t: str, pred: str, obj: str, obj_t: str, props: dict[str, Any] | None = None):
            key = (sub, pred, obj)
            if key not in seen_triples and sub and obj:
                seen_triples.add(key)
                facts.append(
                    GraphFact(
                        subject=sub,
                        subject_type=sub_t,
                        predicate=pred,
                        object=obj,
                        object_type=obj_t,
                        properties=props or {},
                    )
                )

        for ent in entities:
            # Flight Subgraph Traversal
            if ent.entity_type == "FLIGHT":
                f_ctx = self.graph_svc.get_flight_context(ent.normalized_id or ent.value)
                if f_ctx:
                    f_num = f_ctx.flight_number
                    al_name = f_ctx.airline.get("name", "")
                    al_code = f_ctx.airline.get("id", "")
                    orig_code = f_ctx.origin_airport.get("id", "")
                    orig_city = f_ctx.origin_city.get("name", "")
                    dest_code = f_ctx.destination_airport.get("id", "")
                    dest_city = f_ctx.destination_city.get("name", "")
                    dest_country = f_ctx.destination_country.get("name", "")

                    if al_name or al_code:
                        add_fact(al_name or al_code, "Airline", "OPERATES", f_num, "Flight")
                    if orig_code:
                        add_fact(f_num, "Flight", "DEPARTS_FROM", orig_code, "Airport")
                        if orig_city:
                            add_fact(orig_code, "Airport", "LOCATED_IN", orig_city, "City")
                    if dest_code:
                        add_fact(f_num, "Flight", "ARRIVES_AT", dest_code, "Airport")
                        if dest_city:
                            add_fact(dest_code, "Airport", "LOCATED_IN", dest_city, "City")
                            if dest_country:
                                add_fact(dest_city, "City", "LOCATED_IN", dest_country, "Country")

                    for fare in f_ctx.fares:
                        fare_id = fare.get("id", "")
                        add_fact(f_num, "Flight", "HAS_FARE", fare_id, "Fare", fare)

                    for pol in f_ctx.policies:
                        p_id = pol.get("id", "")
                        p_title = pol.get("title", "")
                        add_fact(al_name or al_code, "Airline", "HAS_POLICY", p_title or p_id, "Policy", pol)

            # Airline Subgraph Traversal
            elif ent.entity_type == "AIRLINE":
                al_code = ent.normalized_id or ent.value
                policies = self.graph_svc.get_airline_policies(al_code)
                for item in policies:
                    p = item.get("policy", {})
                    p_id = p.get("id", "")
                    p_title = p.get("title", "")
                    add_fact(al_code, "Airline", "HAS_POLICY", p_title or p_id, "Policy", p)

            # Booking Subgraph Traversal
            elif ent.entity_type == "BOOKING_REF":
                b_ref = ent.normalized_id or ent.value
                b_ctx = self.graph_svc.get_booking_context(b_ref)
                if b_ctx:
                    f_dict = b_ctx.flight or {}
                    f_num = f_dict.get("flight_number") or ""
                    if f_num:
                        add_fact(b_ref, "Booking", "FOR_FLIGHT", f_num, "Flight", {"status": b_ctx.status})
                    al = b_ctx.airline or {}
                    if al.get("name"):
                        add_fact(al["name"], "Airline", "CARRIES_BOOKING", b_ref, "Booking")
                    for p in b_ctx.applicable_policies:
                        add_fact(b_ref, "Booking", "SUBJECT_TO_POLICY", p.get("title") or p.get("id"), "Policy", p)

        return facts

    def _build_vector_filters(self, entities: list[ExtractedEntity]) -> dict[str, Any]:
        """Construct Qdrant vector metadata filter parameters from recognized entities."""
        filters: dict[str, Any] = {}
        for ent in entities:
            if ent.entity_type == "AIRLINE":
                filters["airline"] = ent.normalized_id or ent.value
            elif ent.entity_type == "POLICY_TYPE":
                filters["policy_type"] = ent.normalized_id or ent.value
        return filters

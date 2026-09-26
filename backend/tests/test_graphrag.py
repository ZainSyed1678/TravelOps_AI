"""Comprehensive test suite for Phase 6: GraphRAG."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.graph.ingestion import sync_knowledge_graph
from app.graph.service import graph_service
from app.graphrag.entity_extractor import entity_extractor
from app.graphrag.fusion import context_fusion
from app.graphrag.models import ExtractedEntity, GraphFact, GraphRAGRequest, RetrievedChunk
from app.graphrag.retriever import GraphRAGRetriever
from app.graphrag.service import graphrag_service
from app.graphrag.synthesizer import graphrag_synthesizer
from app.main import app
from app.rag.service import rag_service


@pytest.fixture(autouse=True)
def setup_graph_and_rag():
    """Ensure both Knowledge Graph and RAG vector store are synchronized before tests."""
    sync_knowledge_graph(service=graph_service)
    rag_service.index_processed_documents()


def test_entity_extraction_flights_and_airlines():
    """Verify regex and dictionary extraction for flights, airlines, and policies."""
    # 1. Flight and airline extraction
    query = "What is the cancellation policy on flight EK505 from Mumbai to Dubai?"
    entities = entity_extractor.extract_entities(query)
    entity_map = {e.entity_type: e.normalized_id for e in entities}

    assert "FLIGHT" in entity_map
    assert entity_map["FLIGHT"] == "EK505"
    assert "AIRLINE" in entity_map
    assert entity_map["AIRLINE"] == "EK"
    assert "POLICY_TYPE" in entity_map
    assert entity_map["POLICY_TYPE"] == "CANCELLATION"

    # 2. Airline name and booking reference
    query2 = "What are the Air India fare rules for reservation BK-AI915-002?"
    entities2 = entity_extractor.extract_entities(query2)
    types2 = {e.entity_type for e in entities2}

    assert "AIRLINE" in types2
    assert "BOOKING_REF" in types2
    assert "FARE_RULES" in [e.normalized_id for e in entities2 if e.entity_type == "POLICY_TYPE"]


def test_entity_extraction_explicit_hints():
    """Verify explicit hints take precedence in entity extraction."""
    entities = entity_extractor.extract_entities(
        query="What is the baggage limit?",
        airline_hint="BA",
        flight_hint="BA142",
        booking_hint="BK-BA142-003",
        policy_hint="CANCELLATION",
    )
    ent_dict = {e.entity_type: e.normalized_id for e in entities}
    assert ent_dict["AIRLINE"] == "BA"
    assert ent_dict["FLIGHT"] == "BA142"
    assert ent_dict["BOOKING_REF"] == "BK-BA142-003"
    assert ent_dict["POLICY_TYPE"] == "CANCELLATION"


def test_graphrag_retriever_subgraph_extraction():
    """Verify GraphRAGRetriever traverses knowledge graph facts and sets vector filters."""
    retriever = GraphRAGRetriever()
    entities = [
        ExtractedEntity(entity_type="FLIGHT", value="EK505", normalized_id="EK505"),
        ExtractedEntity(entity_type="AIRLINE", value="EK", normalized_id="EK"),
        ExtractedEntity(
            entity_type="POLICY_TYPE", value="cancellation", normalized_id="CANCELLATION"
        ),
    ]

    graph_facts, chunks, filters = retriever.retrieve(
        query="cancellation rules for EK505",
        entities=entities,
        top_k=3,
    )

    assert len(graph_facts) > 0
    predicates = {f.predicate for f in graph_facts}
    assert "OPERATES" in predicates or "DEPARTS_FROM" in predicates
    assert filters.get("airline") == "EK"
    assert filters.get("policy_type") == "CANCELLATION"


def test_graphrag_context_fusion_and_scoring():
    """Verify context fusion formats prompt context and boosts entity-aligned chunks."""
    facts = [
        GraphFact(
            subject="Air India",
            subject_type="Airline",
            predicate="OPERATES",
            object="AI915",
            object_type="Flight",
        ),
        GraphFact(
            subject="AI915",
            subject_type="Flight",
            predicate="HAS_FARE",
            object="FARE-AI915-SV",
            object_type="Fare",
            properties={"fare_basis": "SV-ECON", "cancellation_fee": 4500.0, "refundable": True},
        ),
    ]

    chunks = [
        RetrievedChunk(
            chunk_id="chk-1",
            document_id="doc-json-air_india_fare_rules-9aa586b3c066",
            source="air_india_fare_rules.json",
            content="Super Value cancellation fee is INR 4500. Flex change fee is INR 0.",
            score=0.75,
            metadata={"airline": "AI"},
        ),
        RetrievedChunk(
            chunk_id="chk-2",
            document_id="doc-html-emirates_cancellation_policy-d0f0d4d70ea2",
            source="emirates_cancellation_policy.html",
            content="Emirates tickets cancelled prior to departure incur fees.",
            score=0.70,
            metadata={"airline": "EK"},
        ),
    ]

    entities = [
        ExtractedEntity(entity_type="AIRLINE", value="Air India", normalized_id="AI"),
        ExtractedEntity(entity_type="FLIGHT", value="AI915", normalized_id="AI915"),
    ]

    fused = context_fusion.fuse_context(
        query="Air India AI915 cancellation fee",
        graph_facts=facts,
        retrieved_chunks=chunks,
        extracted_entities=entities,
    )

    # Air India chunk should be boosted above Emirates chunk
    assert fused.retrieved_chunks[0]["document_id"] == "doc-json-air_india_fare_rules-9aa586b3c066"
    assert "Verified Knowledge Graph Structural Facts" in fused.formatted_prompt_context
    assert "Air India operates flight AI915" in fused.formatted_prompt_context
    assert "Retrieved Document Context & Policy Clauses" in fused.formatted_prompt_context


def test_graphrag_synthesizer_grounding():
    """Verify grounded answer synthesis extracts citations and adheres to facts."""
    facts = [
        GraphFact(
            subject="AI915",
            subject_type="Flight",
            predicate="HAS_FARE",
            object="FARE-AI915-SV",
            object_type="Fare",
            properties={"fare_basis": "SV-ECON", "cancellation_fee": 4500.0, "refundable": True},
        )
    ]
    chunks = [
        RetrievedChunk(
            chunk_id="chk-1",
            document_id="doc-json-air_india_fare_rules-9aa586b3c066",
            source="air_india_fare_rules.json",
            content="Super Value cancellation fee is INR 4500. Free full refund on carrier cancellation.",
            score=0.88,
        )
    ]
    entities = [ExtractedEntity(entity_type="FLIGHT", value="AI915", normalized_id="AI915")]

    fused = context_fusion.fuse_context("AI915 cancellation fee", facts, chunks, entities)
    answer, citations = graphrag_synthesizer.synthesize("AI915 cancellation fee", fused)

    assert "4500" in answer or "AI915" in answer
    assert len(citations) >= 1
    assert citations[0]["document_id"] == "doc-json-air_india_fare_rules-9aa586b3c066"


def test_graphrag_service_query_workflow():
    """Verify end-to-end GraphRAG query execution."""
    req = GraphRAGRequest(
        query="What is the cancellation policy and fee for Air India flight AI915?",
        flight_number="AI915",
    )
    resp = graphrag_service.query(req)

    assert resp.query == req.query
    assert len(resp.answer) > 0
    assert len(resp.graph_facts) > 0
    assert len(resp.citations) > 0
    assert resp.retrieval_latency_ms >= 0
    assert resp.total_latency_ms >= resp.retrieval_latency_ms


def test_graphrag_service_explain_workflow():
    """Verify explain diagnostic workflow returns full structural and vector breakdown."""
    req = GraphRAGRequest(
        query="What are Emirates EK505 cancellation terms and route details?",
        airline="EK",
    )
    exp = graphrag_service.explain(req)

    assert exp.query == req.query
    assert exp.graph_facts_count > 0
    assert exp.vector_chunks_count > 0
    assert "airline" in exp.entity_filters_applied
    assert exp.entity_filters_applied["airline"] == "EK"


@pytest.mark.asyncio
async def test_graphrag_api_endpoints():
    """Verify HTTP API endpoints for GraphRAG query and explain."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Query Endpoint
        res_query = await client.post(
            "/api/v1/graphrag/query",
            json={
                "query": "Tell me about British Airways flight BA142 cancellation rules",
                "airline": "BA",
                "flight_number": "BA142",
            },
        )
        assert res_query.status_code == 200
        data = res_query.json()
        assert "answer" in data
        assert len(data["answer"]) > 0
        assert len(data["graph_facts"]) > 0

        # 2. Explain Endpoint
        res_explain = await client.post(
            "/api/v1/graphrag/explain",
            json={
                "query": "What are the rules for flight EK505?",
                "flight_number": "EK505",
            },
        )
        assert res_explain.status_code == 200
        exp_data = res_explain.json()
        assert exp_data["graph_facts_count"] > 0
        assert "extracted_entities" in exp_data

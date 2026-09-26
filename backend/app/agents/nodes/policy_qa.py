"""Policy Q&A Node: Answers travel policy and fare questions using GraphRAG."""

from typing import Any

from app.agents.state import AgentState
from app.core.logging import logger
from app.graphrag.models import GraphRAGRequest
from app.graphrag.service import graphrag_service


def policy_qa_node(state: AgentState) -> dict[str, Any]:
    """Execute GraphRAG retrieval and grounded generation for policy and fare rules."""
    query = state.get("query", "")
    entities = state.get("extracted_entities", {})

    airline_hint = entities.get("AIRLINE")
    flight_hint = entities.get("FLIGHT")
    policy_hint = entities.get("POLICY_TYPE")

    logger.info(
        f"Policy QA node querying GraphRAG: '{query}' (airline={airline_hint}, flight={flight_hint})"
    )

    req = GraphRAGRequest(
        query=query,
        airline=airline_hint,
        flight_number=flight_hint,
        policy_type=policy_hint,
    )

    rag_resp = graphrag_service.query(req)

    # Format response message
    lines = [rag_resp.answer, ""]

    if rag_resp.citations:
        lines.append("### Verified Policy Citations:")
        for c in rag_resp.citations:
            sec = f" (Section: {c['section_title']})" if c.get("section_title") else ""
            lines.append(f"- **{c['source']}**{sec} `[ID: {c['document_id']}]`")

    assistant_msg = "\n".join(lines).strip()
    trace_entry = f"policy_qa: grounded answer generated with {len(rag_resp.graph_facts)} graph facts and {len(rag_resp.citations)} citations."

    return {
        "policy_response": rag_resp.model_dump(mode="json"),
        "messages": [{"role": "assistant", "content": assistant_msg}],
        "trace": [trace_entry],
    }

"""Supervisor Node: Classifies intent, extracts entities, and routes to specialist agent nodes."""

from typing import Any

from app.agents.state import AgentState
from app.core.logging import logger
from app.graphrag.entity_extractor import entity_extractor


def supervisor_node(state: AgentState) -> dict[str, Any]:
    """Orchestrator node inspecting query and determining specialized workflow."""
    query = state.get("query", "")
    q_lower = query.lower()

    # 1. Entity Extraction
    extracted_list = entity_extractor.extract_entities(query)
    entities: dict[str, Any] = {}
    for ent in extracted_list:
        entities[ent.entity_type] = ent.normalized_id or ent.value

    # 2. Workflow / Intent Classification
    workflow = "SEARCH"
    user_intent = "flight_search"

    # Disruption / Rebooking keywords
    if any(k in q_lower for k in ["rebook", "cancelled", "canceled", "delayed", "missed", "disruption", "reschedule"]):
        workflow = "DISRUPTION_REBOOKING"
        user_intent = "disruption_rebooking"
    # Hotel keywords
    elif any(k in q_lower for k in ["hotel", "hotels", "stay", "accommodation", "room", "resort"]):
        workflow = "HOTEL"
        user_intent = "hotel_search"
    # Policy / Rules keywords
    elif any(k in q_lower for k in ["policy", "refund", "baggage", "allowance", "fee", "rules", "carriage", "cancel ticket", "cancellation cost"]):
        workflow = "POLICY"
        user_intent = "policy_qa"
    # Search keywords
    else:
        workflow = "SEARCH"
        user_intent = "flight_search"

    logger.info(f"Supervisor classified intent '{user_intent}' for workflow '{workflow}'")

    trace_entry = f"supervisor: classified intent as '{user_intent}' ({workflow}) with {len(entities)} entities."

    return {
        "workflow": workflow,
        "user_intent": user_intent,
        "extracted_entities": entities,
        "trace": [trace_entry],
    }

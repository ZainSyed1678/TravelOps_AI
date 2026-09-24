"""Disruption Rebooking Node: Handles delayed/cancelled flights with Human-in-the-Loop confirmation."""

import asyncio
from datetime import date, timedelta
from typing import Any

from app.agents.hitl import hitl_manager
from app.agents.state import AgentState
from app.core.logging import logger
from app.graph.service import graph_service
from app.ml.ranker import flight_ranker
from app.providers.factory import get_flight_provider
from app.schemas.travel import FlightSearchQuery


def disruption_node(state: AgentState) -> dict[str, Any]:
    """Analyze flight disruption, search alternate options, and require human approval before rebooking."""
    entities = state.get("extracted_entities", {})

    # Identify booking reference and flight
    b_ref = entities.get("BOOKING_REF", "BK-EK505-001")
    f_num = entities.get("FLIGHT", "EK505")

    # Fetch booking lineage from Knowledge Graph
    b_ctx = graph_service.get_booking_context(b_ref)

    orig = "BOM"
    dest = "DXB"
    if b_ctx and b_ctx.origin and b_ctx.destination:
        orig = b_ctx.origin.get("id", "BOM")
        dest = b_ctx.destination.get("id", "DXB")

    logger.info(f"Processing disruption for booking {b_ref}, flight {f_num} on {orig}->{dest}")

    # Search alternate flights
    dep_date = date.today() + timedelta(days=1)
    params = FlightSearchQuery(
        origin=orig,
        destination=dest,
        departure_date=dep_date,
        adults=1,
    )

    provider = get_flight_provider()
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            search_res = pool.submit(asyncio.run, provider.search_flights(params)).result()
    except Exception:
        import nest_asyncio
        nest_asyncio.apply()
        search_res = asyncio.get_event_loop().run_until_complete(provider.search_flights(params))

    # Rank alternatives to select optimal replacement
    ranked_alts = flight_ranker.rank_flight_offers(search_res.offers)
    # Pick alternate flight that is NOT the cancelled flight
    best_alt = None
    for r in ranked_alts:
        if r.offer.flight_number != f_num:
            best_alt = r.offer
            break
    if not best_alt and ranked_alts:
        best_alt = ranked_alts[0].offer

    proposed_flight_num = best_alt.flight_number if best_alt else "EK501"
    proposed_carrier = best_alt.airline_name if best_alt else "Emirates"

    disruption_plan = {
        "booking_reference": b_ref,
        "disrupted_flight": f_num,
        "origin": orig,
        "destination": dest,
        "carrier_policy": "Full waiver of change fee under disruption policy rules.",
        "proposed_flight": {
            "flight_number": proposed_flight_num,
            "airline": proposed_carrier,
            "departure_time": best_alt.departure_time.isoformat() if best_alt else "2026-10-16T04:30:00",
            "arrival_time": best_alt.arrival_time.isoformat() if best_alt else "2026-10-16T07:00:00",
            "additional_fee": 0.0,
        },
    }

    # CRITICAL: Register pending action with Human-in-the-Loop manager to enforce safety barrier
    pending_record = hitl_manager.create_pending_action(
        action_type="REBOOK_FLIGHT",
        summary=f"Rebook booking {b_ref} onto {proposed_carrier} ({proposed_flight_num}) due to flight disruption",
        details={
            "booking_reference": b_ref,
            "original_flight": f_num,
            "new_flight": proposed_flight_num,
            "waiver_applied": True,
            "additional_amount": 0.0,
            "currency": "INR",
        },
        thread_id=state.get("thread_id"),
        risk_level="HIGH",
        financial_impact={"amount": 0.0, "currency": "INR", "waiver_applied": True},
    )
    pending_action = pending_record.model_dump(mode="json")

    lines = [
        f"🚨 **Flight Disruption Detected for Booking {b_ref} (Flight {f_num})**",
        "",
        "Under carrier disruption protection rules, you are entitled to a complimentary rebooking at **₹0 additional cost**.",
        "",
        "### Proposed Replacement Flight:",
        f"- **Flight:** {proposed_carrier} ({proposed_flight_num})",
        f"- **Route:** {orig} -> {dest}",
        f"- **Departure:** {best_alt.departure_time.strftime('%Y-%m-%d %H:%M') if best_alt else 'Next Available'}",
        "- **Fare Difference / Change Fee:** **₹0 (Waived)**",
        "",
        "> ⚠️ **SAFETY CHECKPOINT: Human-in-the-Loop Confirmation Required**",
        f"> **Action ID:** `{pending_record.action_id}`",
        f"> Please review and approve this rebooking action to finalize changes for reservation `{b_ref}`.",
    ]

    assistant_msg = "\n".join(lines)
    trace_entry = (
        f"disruption_rebooking: proposed replacement flight {proposed_flight_num} for booking {b_ref}; "
        "paused execution for human confirmation."
    )

    return {
        "disruption_plan": disruption_plan,
        "pending_action": pending_action,
        "requires_human_confirmation": True,
        "confirmation_status": "PENDING",
        "messages": [{"role": "assistant", "content": assistant_msg}],
        "trace": [trace_entry],
    }

"""Hotel Search Node: Discovers accommodations using Knowledge Graph and Hotel Providers."""

import asyncio
from datetime import date, timedelta
from typing import Any

from app.agents.state import AgentState
from app.core.logging import logger
from app.graph.service import graph_service
from app.providers.factory import get_hotel_provider
from app.schemas.travel import HotelSearchQuery


def hotel_search_node(state: AgentState) -> dict[str, Any]:
    """Search destination hotels combining Knowledge Graph proximity and live provider inventory."""
    entities = state.get("extracted_entities", {})
    query = state.get("query", "").upper()

    dest_airport = "DXB"
    if "BOM" in query or "MUMBAI" in query:
        dest_airport = "BOM"
    elif "DEL" in query or "DELHI" in query:
        dest_airport = "DEL"
    elif "LHR" in query or "LONDON" in query:
        dest_airport = "LHR"
    elif "DXB" in query or "DUBAI" in query:
        dest_airport = "DXB"
    elif entities.get("AIRPORT"):
        dest_airport = entities["AIRPORT"]

    city_map = {"DXB": "Dubai", "BOM": "Mumbai", "DEL": "Delhi", "LHR": "London"}
    dest_city = city_map.get(dest_airport, "Dubai")

    logger.info(f"Hotel search node resolving hotels near airport '{dest_airport}' ({dest_city})")

    # 1. Traversal via Knowledge Graph
    kg_hotels = graph_service.get_destination_hotels(dest_airport, limit=5)

    # 2. Query Hotel Provider
    checkin = date.today() + timedelta(days=7)
    checkout = checkin + timedelta(days=3)
    params = HotelSearchQuery(
        city=dest_city,
        check_in_date=checkin,
        check_out_date=checkout,
        guests=2,
    )

    provider = get_hotel_provider()
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            provider_res = pool.submit(asyncio.run, provider.search_hotels(params)).result()
        hotel_offers = provider_res.offers
    except Exception:
        hotel_offers = []

    # Format response message
    lines = [
        f"I found accommodations for your stay in **{dest_city} ({dest_airport})** ({checkin.isoformat()} to {checkout.isoformat()}):",
        "",
    ]

    results_data: list[dict[str, Any]] = []

    if hotel_offers:
        for idx, h in enumerate(hotel_offers[:3], start=1):
            stars = int(h.star_rating) if h.star_rating else 4
            lines.append(f"**#{idx} {h.name}** ({'★' * stars})")
            lines.append(f"- Location: {h.address}")
            lines.append(f"- Rate: **₹{h.total_price:,.0f}** total (₹{h.price_per_night:,.0f}/night)")
            lines.append("")
            results_data.append(h.model_dump(mode="json"))
    elif kg_hotels:
        for idx, h in enumerate(kg_hotels[:3], start=1):
            stars = int(h.get("star_rating", 4))
            lines.append(f"**#{idx} {h.get('name')}** ({'★' * stars})")
            lines.append(f"- Address: {h.get('address')}")
            lines.append("")
            results_data.append(h)
    else:
        lines.append("No hotels currently found matching your destination criteria.")

    assistant_msg = "\n".join(lines).strip()
    trace_entry = f"hotel_search: found {len(results_data)} hotel options for destination {dest_airport}."

    return {
        "hotel_results": results_data,
        "messages": [{"role": "assistant", "content": assistant_msg}],
        "trace": [trace_entry],
    }

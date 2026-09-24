"""Flight Search Node: Discovers provider offers and ranks them using Travel ML."""

import asyncio
from datetime import date, timedelta
from typing import Any

from app.agents.state import AgentState
from app.core.logging import logger
from app.ml.ranker import flight_ranker
from app.ml.schemas import UserPreferences
from app.providers.factory import get_flight_provider
from app.schemas.travel import FlightSearchQuery


def flight_search_node(state: AgentState) -> dict[str, Any]:
    """Execute live/mock flight search and ML ranking based on traveler preferences."""
    entities = state.get("extracted_entities", {})
    prefs_dict = state.get("preferences") or {}
    prefs = UserPreferences(**prefs_dict) if prefs_dict else UserPreferences()

    # Determine origin and destination
    origin = entities.get("AIRPORT", "BOM")
    # If multiple airports found or default
    dest = "DXB"
    query = state.get("query", "").upper()
    if "DEL" in query or "DELHI" in query:
        if origin != "DEL":
            dest = "DEL"
    if "LHR" in query or "LONDON" in query:
        dest = "LHR"
    if "DOH" in query or "DOHA" in query:
        dest = "DOH"
    if "DXB" in query or "DUBAI" in query:
        dest = "DXB"

    dep_date = date.today() + timedelta(days=7)

    params = FlightSearchQuery(
        origin=origin,
        destination=dest,
        departure_date=dep_date,
        adults=1,
        cabin_class="ECONOMY",
    )

    logger.info(f"Executing flight search: {origin} -> {dest} on {dep_date}")
    provider = get_flight_provider()

    # Execute async search synchronously in graph node
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                search_res = pool.submit(asyncio.run, provider.search_flights(params)).result()
        else:
            search_res = asyncio.run(provider.search_flights(params))
    except Exception:
        # Fallback direct call if already running loop in thread
        import nest_asyncio
        nest_asyncio.apply()
        search_res = asyncio.get_event_loop().run_until_complete(provider.search_flights(params))

    # Rank offers with ML ranker
    ranked_offers = flight_ranker.rank_flight_offers(search_res.offers, preferences=prefs)

    # Build response message
    lines = [
        f"I found {len(ranked_offers)} flight options from **{origin}** to **{dest}** on {dep_date.isoformat()}.",
        "Here are the top ranked recommendations scored by our AI engine:",
        "",
    ]

    for item in ranked_offers[:3]:
        off = item.offer
        top_reason = item.score_breakdown[0].explanation if item.score_breakdown else "Balanced price and schedule."
        lines.append(
            f"**#{item.rank} {off.airline_name} ({off.flight_number})** — Score: `{item.score}/100`"
        )
        lines.append(
            f"- Price: **₹{off.total_price:,.0f}** | Duration: {off.duration_minutes // 60}h {off.duration_minutes % 60}m | Stops: {off.stops}"
        )
        lines.append(
            f"- Schedule: Departs {off.departure_time.strftime('%H:%M')} -> Arrives {off.arrival_time.strftime('%H:%M')}"
        )
        lines.append(f"- *Why ranked here:* {top_reason}")
        lines.append("")

    lines.append("Would you like me to reserve one of these options for you?")
    assistant_msg = "\n".join(lines)

    ranked_dicts = [item.model_dump(mode="json") for item in ranked_offers]
    trace_entry = f"flight_search: searched {origin}->{dest}, retrieved {len(ranked_offers)} offers and applied ML ranking."

    return {
        "flight_results": ranked_dicts,
        "messages": [{"role": "assistant", "content": assistant_msg}],
        "trace": [trace_entry],
    }

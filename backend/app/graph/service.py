"""Neo4j Knowledge Graph service with in-memory graph fallback for hermetic execution."""

from typing import Any

import networkx as nx

from app.core.config import settings
from app.core.logging import logger
from app.graph.cypher_queries import (
    GET_AIRLINE_POLICIES,
    GET_BOOKING_CONTEXT,
    GET_DESTINATION_HOTELS,
    GET_FLIGHT_FULL_CONTEXT,
    MERGE_AIRLINE,
    MERGE_AIRPORT,
    MERGE_BOOKING,
    MERGE_CITY,
    MERGE_COUNTRY,
    MERGE_DOCUMENT,
    MERGE_FARE,
    MERGE_FLIGHT,
    MERGE_HOTEL,
    MERGE_POLICY,
    MERGE_ROUTE,
    MERGE_SUPPLIER,
    MERGE_SUPPLIER_FLIGHT,
    SCHEMA_CONSTRAINTS,
)
from app.graph.models import BookingGraphContext, FlightGraphContext


class GraphService:
    """Manages travel knowledge graph entities, Cypher executions, and graph traversals."""

    _neo4j_reachable: bool | None = None

    def __init__(self, uri: str | None = None, user: str | None = None, password: str | None = None):
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self._driver = None
        self._use_in_memory = False

        # In-memory graph fallback using NetworkX DiGraph
        self._mem_graph = nx.DiGraph()

        self._init_connection()

    def _init_connection(self) -> None:
        """Attempt connection to Neo4j; fall back to in-memory graph engine if offline."""
        if GraphService._neo4j_reachable is False:
            self._driver = None
            self._use_in_memory = True
            return

        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password), connection_timeout=1.0)
            driver.verify_connectivity()
            self._driver = driver
            GraphService._neo4j_reachable = True
            logger.info(f"Connected to Neo4j Knowledge Graph at {self.uri}")
        except Exception:
            GraphService._neo4j_reachable = False
            logger.info("Neo4j daemon not reachable; initializing in-memory NetworkX graph engine.")
            self._driver = None
            self._use_in_memory = True

    def execute_cypher(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute Cypher query against Neo4j or return empty if in fallback mode."""
        if self._driver is not None:
            try:
                with self._driver.session() as session:
                    result = session.run(query, parameters or {})
                    return [record.data() for record in result]
            except Exception as exc:
                logger.error(f"Neo4j Cypher query failed: {exc}")
                return []
        return []

    def initialize_schema(self) -> None:
        """Create uniqueness constraints and indexes in Neo4j."""
        if self._driver is not None:
            for constraint in SCHEMA_CONSTRAINTS:
                try:
                    self.execute_cypher(constraint)
                except Exception:
                    pass

    # ==========================================================================
    # Entity Upsert Methods
    # ==========================================================================

    def upsert_country(self, name: str) -> None:
        """Upsert Country entity."""
        self._mem_graph.add_node(name, label="Country", name=name)
        if self._driver:
            self.execute_cypher(MERGE_COUNTRY, {"name": name})

    def upsert_city(self, name: str, country_name: str) -> None:
        """Upsert City entity and LOCATED_IN Country relationship."""
        self.upsert_country(country_name)
        self._mem_graph.add_node(name, label="City", name=name)
        self._mem_graph.add_edge(name, country_name, rel="LOCATED_IN")
        if self._driver:
            self.execute_cypher(MERGE_CITY, {"name": name, "country_name": country_name})

    def upsert_airport(
        self,
        id: str,
        name: str,
        city_name: str,
        country_name: str,
        icao: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        timezone: str | None = None,
    ) -> None:
        """Upsert Airport entity and LOCATED_IN City relationship."""
        self.upsert_city(city_name, country_name)
        self._mem_graph.add_node(
            id,
            label="Airport",
            id=id,
            name=name,
            icao=icao,
            city=city_name,
            country=country_name,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
        )
        self._mem_graph.add_edge(id, city_name, rel="LOCATED_IN")
        if self._driver:
            self.execute_cypher(
                MERGE_AIRPORT,
                {
                    "id": id,
                    "name": name,
                    "icao": icao,
                    "city_name": city_name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": timezone,
                },
            )

    def upsert_airline(
        self,
        id: str,
        name: str,
        country: str,
        alliance: str | None = None,
        logo_url: str | None = None,
    ) -> None:
        """Upsert Airline entity."""
        self._mem_graph.add_node(
            id,
            label="Airline",
            id=id,
            name=name,
            country=country,
            alliance=alliance,
            logo_url=logo_url,
        )
        if self._driver:
            self.execute_cypher(
                MERGE_AIRLINE,
                {"id": id, "name": name, "country": country, "alliance": alliance, "logo_url": logo_url},
            )

    def upsert_route(self, origin: str, destination: str, distance_km: float = 0.0) -> None:
        """Upsert Route entity between two airports."""
        route_id = f"{origin}-{destination}"
        self._mem_graph.add_node(route_id, label="Route", id=route_id, origin=origin, destination=destination)
        self._mem_graph.add_edge(route_id, origin, rel="FROM_AIRPORT")
        self._mem_graph.add_edge(route_id, destination, rel="TO_AIRPORT")
        if self._driver:
            self.execute_cypher(MERGE_ROUTE, {"id": route_id, "origin": origin, "destination": destination, "distance_km": distance_km})

    def upsert_flight(
        self,
        flight_number: str,
        airline_code: str,
        origin_code: str,
        destination_code: str,
        departure_time: str,
        arrival_time: str,
        duration_minutes: int,
        stops: int = 0,
        aircraft_type: str | None = None,
        status: str = "SCHEDULED",
    ) -> None:
        """Upsert Flight entity and its relationships to Airline and origin/dest Airports."""
        self._mem_graph.add_node(
            flight_number,
            label="Flight",
            flight_number=flight_number,
            airline_code=airline_code,
            origin=origin_code,
            destination=destination_code,
            departure_time=departure_time,
            arrival_time=arrival_time,
            duration_minutes=duration_minutes,
            stops=stops,
            aircraft_type=aircraft_type,
            status=status,
        )
        self._mem_graph.add_edge(airline_code, flight_number, rel="OPERATES")
        self._mem_graph.add_edge(flight_number, origin_code, rel="DEPARTS_FROM")
        self._mem_graph.add_edge(flight_number, destination_code, rel="ARRIVES_AT")

        if self._driver:
            self.execute_cypher(
                MERGE_FLIGHT,
                {
                    "flight_number": flight_number,
                    "airline_code": airline_code,
                    "origin_code": origin_code,
                    "destination_code": destination_code,
                    "departure_time": departure_time,
                    "arrival_time": arrival_time,
                    "duration_minutes": duration_minutes,
                    "stops": stops,
                    "aircraft_type": aircraft_type,
                    "status": status,
                },
            )

    def upsert_hotel(self, id: str, name: str, city_name: str, address: str, star_rating: float) -> None:
        """Upsert Hotel entity and LOCATED_IN City relationship."""
        self._mem_graph.add_node(
            id,
            label="Hotel",
            id=id,
            name=name,
            address=address,
            star_rating=star_rating,
        )
        self._mem_graph.add_edge(id, city_name, rel="LOCATED_IN")
        if self._driver:
            self.execute_cypher(MERGE_HOTEL, {"id": id, "name": name, "city_name": city_name, "address": address, "star_rating": star_rating})

    def upsert_supplier(self, code: str, name: str, supplier_type: str) -> None:
        """Upsert Supplier entity."""
        self._mem_graph.add_node(code, label="Supplier", code=code, name=name, supplier_type=supplier_type)
        if self._driver:
            self.execute_cypher(MERGE_SUPPLIER, {"code": code, "name": name, "supplier_type": supplier_type})

    def link_supplier_flight(self, supplier_code: str, flight_number: str) -> None:
        """Link Supplier to Flight via PROVIDES relationship."""
        self._mem_graph.add_edge(supplier_code, flight_number, rel="PROVIDES")
        if self._driver:
            self.execute_cypher(MERGE_SUPPLIER_FLIGHT, {"supplier_code": supplier_code, "flight_number": flight_number})

    def upsert_policy(
        self,
        id: str,
        entity_type: str,
        entity_id: str,
        policy_type: str,
        title: str,
        content: str,
        version: str = "1.0",
    ) -> None:
        """Upsert Policy entity and connect to entity (e.g. Airline)."""
        self._mem_graph.add_node(
            id,
            label="Policy",
            id=id,
            entity_type=entity_type,
            entity_id=entity_id,
            policy_type=policy_type,
            title=title,
            content=content,
            version=version,
        )
        if entity_type == "AIRLINE":
            self._mem_graph.add_edge(entity_id, id, rel="HAS_POLICY")
        if self._driver:
            self.execute_cypher(
                MERGE_POLICY,
                {
                    "id": id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "policy_type": policy_type,
                    "title": title,
                    "content": content,
                    "version": version,
                },
            )

    def upsert_document(
        self,
        id: str,
        title: str,
        source: str,
        document_type: str,
        policy_id: str | None = None,
        version: str = "1.0",
    ) -> None:
        """Upsert Document entity and DESCRIBES Policy relationship."""
        self._mem_graph.add_node(
            id,
            label="Document",
            id=id,
            title=title,
            source=source,
            document_type=document_type,
            version=version,
        )
        if policy_id:
            self._mem_graph.add_edge(id, policy_id, rel="DESCRIBES")
        if self._driver:
            self.execute_cypher(
                MERGE_DOCUMENT,
                {
                    "id": id,
                    "title": title,
                    "source": source,
                    "document_type": document_type,
                    "policy_id": policy_id,
                    "version": version,
                },
            )

    def upsert_fare(
        self,
        id: str,
        fare_basis: str,
        cabin_class: str,
        refundable: bool,
        change_fee: float,
        cancellation_fee: float,
        flight_number: str | None = None,
    ) -> None:
        """Upsert Fare entity and connect to Flight."""
        self._mem_graph.add_node(
            id,
            label="Fare",
            id=id,
            fare_basis=fare_basis,
            cabin_class=cabin_class,
            refundable=refundable,
            change_fee=change_fee,
            cancellation_fee=cancellation_fee,
        )
        if flight_number:
            self._mem_graph.add_edge(flight_number, id, rel="HAS_FARE")
        if self._driver:
            self.execute_cypher(
                MERGE_FARE,
                {
                    "id": id,
                    "fare_basis": fare_basis,
                    "cabin_class": cabin_class,
                    "refundable": refundable,
                    "change_fee": change_fee,
                    "cancellation_fee": cancellation_fee,
                    "flight_number": flight_number,
                },
            )

    def upsert_booking(
        self,
        reference: str,
        flight_number: str | None = None,
        status: str = "CONFIRMED",
        total_amount: float = 0.0,
        currency: str = "INR",
    ) -> None:
        """Upsert Booking entity and FOR_FLIGHT relationship."""
        self._mem_graph.add_node(
            reference,
            label="Booking",
            reference=reference,
            status=status,
            total_amount=total_amount,
            currency=currency,
        )
        if flight_number:
            self._mem_graph.add_edge(reference, flight_number, rel="FOR_FLIGHT")
        if self._driver:
            self.execute_cypher(
                MERGE_BOOKING,
                {
                    "reference": reference,
                    "flight_number": flight_number,
                    "status": status,
                    "total_amount": total_amount,
                    "currency": currency,
                },
            )

    # ==========================================================================
    # Knowledge Graph Retrieval Methods
    # ==========================================================================

    def get_flight_context(self, flight_number: str) -> FlightGraphContext | None:
        """Traverse flight subgraph to fetch airline, airports, cities, fares, policies, and documents."""
        # Try Neo4j first if connected
        if self._driver is not None:
            records = self.execute_cypher(GET_FLIGHT_FULL_CONTEXT, {"flight_number": flight_number})
            if records:
                row = records[0]
                return FlightGraphContext(
                    flight_number=flight_number,
                    airline=row.get("al", {}),
                    origin_airport=row.get("orig", {}),
                    origin_city=row.get("ci_orig", {}),
                    destination_airport=row.get("dest", {}),
                    destination_city=row.get("ci_dest", {}),
                    destination_country=row.get("co_dest", {}),
                    fares=row.get("fares", []),
                    policies=row.get("policies", []),
                    documents=row.get("documents", []),
                )

        # In-memory graph traversal
        if not self._mem_graph.has_node(flight_number):
            return None

        f_data = self._mem_graph.nodes[flight_number]
        airline_code = f_data.get("airline_code", "")
        origin_code = f_data.get("origin", "")
        dest_code = f_data.get("destination", "")

        al_data = self._mem_graph.nodes.get(airline_code, {})
        orig_data = self._mem_graph.nodes.get(origin_code, {})
        dest_data = self._mem_graph.nodes.get(dest_code, {})

        dest_city_name = dest_data.get("city", "")
        dest_city_data = self._mem_graph.nodes.get(dest_city_name, {})
        dest_country_name = dest_data.get("country", "")
        dest_country_data = self._mem_graph.nodes.get(dest_country_name, {})

        orig_city_name = orig_data.get("city", "")
        orig_city_data = self._mem_graph.nodes.get(orig_city_name, {})

        # Find policies linked to airline
        policies = []
        documents = []
        fares = []

        if airline_code:
            for neighbor in self._mem_graph.successors(airline_code):
                edge_data = self._mem_graph.get_edge_data(airline_code, neighbor)
                if edge_data and edge_data.get("rel") == "HAS_POLICY":
                    pol_data = dict(self._mem_graph.nodes[neighbor])
                    policies.append(pol_data)
                    # Check documents describing policy
                    for pred in self._mem_graph.predecessors(neighbor):
                        pred_edge = self._mem_graph.get_edge_data(pred, neighbor)
                        if pred_edge and pred_edge.get("rel") == "DESCRIBES":
                            documents.append(dict(self._mem_graph.nodes[pred]))

        # Find fares linked to flight
        for neighbor in self._mem_graph.successors(flight_number):
            edge_data = self._mem_graph.get_edge_data(flight_number, neighbor)
            if edge_data and edge_data.get("rel") == "HAS_FARE":
                fares.append(dict(self._mem_graph.nodes[neighbor]))

        return FlightGraphContext(
            flight_number=flight_number,
            airline=al_data,
            origin_airport=orig_data,
            origin_city=orig_city_data,
            destination_airport=dest_data,
            destination_city=dest_city_data,
            destination_country=dest_country_data,
            fares=fares,
            policies=policies,
            documents=documents,
        )

    def get_airline_policies(self, airline_code: str, policy_type: str | None = None) -> list[dict[str, Any]]:
        """Retrieve policies and associated documents for an airline."""
        if self._driver is not None:
            records = self.execute_cypher(GET_AIRLINE_POLICIES, {"airline_code": airline_code})
            results = []
            for r in records:
                p = r.get("p", {})
                if policy_type is None or p.get("policy_type") == policy_type.upper():
                    results.append({"policy": p, "documents": r.get("documents", [])})
            return results

        # In-memory
        results = []
        if self._mem_graph.has_node(airline_code):
            for neighbor in self._mem_graph.successors(airline_code):
                edge = self._mem_graph.get_edge_data(airline_code, neighbor)
                if edge and edge.get("rel") == "HAS_POLICY":
                    p_data = self._mem_graph.nodes[neighbor]
                    if policy_type is None or p_data.get("policy_type") == policy_type.upper():
                        docs = [
                            self._mem_graph.nodes[pred]
                            for pred in self._mem_graph.predecessors(neighbor)
                            if self._mem_graph.get_edge_data(pred, neighbor).get("rel") == "DESCRIBES"
                        ]
                        results.append({"policy": dict(p_data), "documents": docs})
        return results

    def get_booking_context(self, booking_reference: str) -> BookingGraphContext | None:
        """Fetch booking lineage and flight/policy relationships."""
        if self._driver is not None:
            records = self.execute_cypher(GET_BOOKING_CONTEXT, {"reference": booking_reference})
            if records:
                r = records[0]
                b = r.get("b", {})
                return BookingGraphContext(
                    booking_reference=booking_reference,
                    status=b.get("status", "CONFIRMED"),
                    flight=r.get("f"),
                    airline=r.get("al"),
                    origin=r.get("orig"),
                    destination=r.get("dest"),
                    applicable_policies=r.get("policies", []),
                    policy_documents=r.get("documents", []),
                )

        if not self._mem_graph.has_node(booking_reference):
            return None

        b_data = self._mem_graph.nodes[booking_reference]
        flight_number = None
        for neighbor in self._mem_graph.successors(booking_reference):
            edge = self._mem_graph.get_edge_data(booking_reference, neighbor)
            if edge and edge.get("rel") == "FOR_FLIGHT":
                flight_number = neighbor
                break

        flight_ctx = self.get_flight_context(flight_number) if flight_number else None
        flight_node = (
            dict(self._mem_graph.nodes[flight_number])
            if flight_number and self._mem_graph.has_node(flight_number)
            else None
        )

        return BookingGraphContext(
            booking_reference=booking_reference,
            status=b_data.get("status", "CONFIRMED"),
            flight=flight_node,
            airline=flight_ctx.airline if flight_ctx else None,
            origin=flight_ctx.origin_airport if flight_ctx else None,
            destination=flight_ctx.destination_airport if flight_ctx else None,
            applicable_policies=flight_ctx.policies if flight_ctx else [],
            policy_documents=flight_ctx.documents if flight_ctx else [],
        )

    def get_destination_hotels(self, airport_code: str, limit: int = 10) -> list[dict[str, Any]]:
        """Find hotels situated in the destination city of an airport."""
        if self._driver is not None:
            records = self.execute_cypher(GET_DESTINATION_HOTELS, {"airport_code": airport_code, "limit": limit})
            return [r.get("h", {}) for r in records]

        # In-memory
        if not self._mem_graph.has_node(airport_code):
            return []
        # Find City of Airport
        city_name = None
        for neighbor in self._mem_graph.successors(airport_code):
            edge = self._mem_graph.get_edge_data(airport_code, neighbor)
            if edge and edge.get("rel") == "LOCATED_IN":
                city_name = neighbor
                break
        if not city_name:
            return []

        # Find Hotels in City
        hotels = []
        for pred in self._mem_graph.predecessors(city_name):
            edge = self._mem_graph.get_edge_data(pred, city_name)
            if edge and edge.get("rel") == "LOCATED_IN":
                node_data = self._mem_graph.nodes[pred]
                if node_data.get("label") == "Hotel":
                    hotels.append(dict(node_data))
                    if len(hotels) >= limit:
                        break
        return hotels


graph_service = GraphService()

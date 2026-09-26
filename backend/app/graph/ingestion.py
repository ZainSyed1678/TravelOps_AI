"""Knowledge Graph ingestion pipeline.

Synchronizes travel domain entities, relationships, policies, and documents
into the Neo4j Knowledge Graph (or in-memory NetworkX graph).
"""

import csv
import json
from pathlib import Path

from app.core.logging import logger
from app.graph.service import GraphService, graph_service


class GraphIngestionPipeline:
    """Pipelines raw datasets and database entities into the Neo4j Knowledge Graph."""

    def __init__(self, service: GraphService | None = None, data_dir: Path | None = None):
        self.service = service or graph_service
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        else:
            candidate_1 = Path("data/raw")
            candidate_2 = Path(__file__).resolve().parents[3] / "data" / "raw"
            self.data_dir = candidate_1 if candidate_1.exists() else candidate_2

    def run_full_sync(self) -> dict[str, int]:
        """Execute full idempotent graph ingestion from raw data files."""
        stats = {
            "airports": 0,
            "airlines": 0,
            "routes": 0,
            "flights": 0,
            "hotels": 0,
            "suppliers": 0,
            "policies": 0,
            "documents": 0,
            "fares": 0,
            "bookings": 0,
        }

        # Initialize schema constraints
        self.service.initialize_schema()

        # 1. Ingest Airports, Cities, Countries
        stats["airports"] = self._ingest_airports()

        # 2. Ingest Airlines
        stats["airlines"] = self._ingest_airlines()

        # 3. Ingest Routes and Flights
        routes_count, flights_count = self._ingest_routes_and_flights()
        stats["routes"] = routes_count
        stats["flights"] = flights_count

        # 4. Ingest Hotels
        stats["hotels"] = self._ingest_hotels()

        # 5. Ingest Suppliers & link to Flights
        stats["suppliers"] = self._ingest_suppliers()

        # 6. Ingest Policies & Documents
        pol_count, doc_count = self._ingest_policies_and_documents()
        stats["policies"] = pol_count
        stats["documents"] = doc_count

        # 7. Ingest Fares
        stats["fares"] = self._ingest_fares()

        # 8. Ingest Sample Bookings
        stats["bookings"] = self._ingest_sample_bookings()

        logger.info(f"Graph synchronization complete: {stats}")
        return stats

    def _ingest_airports(self) -> int:
        airports_file = self.data_dir / "airports.csv"
        if not airports_file.exists():
            logger.warning(f"Airports file not found at {airports_file}")
            return 0

        count = 0
        with open(airports_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.service.upsert_airport(
                    id=row["id"],
                    name=row["name"],
                    city_name=row["city"],
                    country_name=row["country"],
                    icao=row.get("icao_code"),
                    latitude=float(row["latitude"]) if row.get("latitude") else None,
                    longitude=float(row["longitude"]) if row.get("longitude") else None,
                    timezone=row.get("timezone"),
                )
                count += 1
        return count

    def _ingest_airlines(self) -> int:
        airlines_file = self.data_dir / "airlines.json"
        if not airlines_file.exists():
            logger.warning(f"Airlines file not found at {airlines_file}")
            return 0

        with open(airlines_file, encoding="utf-8") as f:
            airlines = json.load(f)

        count = 0
        for al in airlines:
            self.service.upsert_airline(
                id=al["id"],
                name=al["name"],
                country=al.get("country", ""),
                alliance=al.get("alliance"),
                logo_url=al.get("logo_url"),
            )
            count += 1
        return count

    def _ingest_routes_and_flights(self) -> tuple[int, int]:
        routes_file = self.data_dir / "flight_routes.csv"
        if not routes_file.exists():
            logger.warning(f"Flight routes file not found at {routes_file}")
            return 0, 0

        routes_count = 0
        flights_count = 0
        seen_routes = set()

        with open(routes_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                orig = row["origin"]
                dest = row["destination"]
                route_key = f"{orig}-{dest}"
                if route_key not in seen_routes:
                    self.service.upsert_route(origin=orig, destination=dest)
                    seen_routes.add(route_key)
                    routes_count += 1

                self.service.upsert_flight(
                    flight_number=row["flight_number"],
                    airline_code=row["airline_code"],
                    origin_code=orig,
                    destination_code=dest,
                    departure_time=row["departure_time"],
                    arrival_time=row["arrival_time"],
                    duration_minutes=int(row["duration_minutes"]),
                    stops=int(row.get("stops", 0)),
                    aircraft_type=row.get("aircraft_type"),
                    status="SCHEDULED",
                )
                flights_count += 1

        return routes_count, flights_count

    def _ingest_hotels(self) -> int:
        hotels_file = self.data_dir / "hotels.json"
        if not hotels_file.exists():
            logger.warning(f"Hotels file not found at {hotels_file}")
            return 0

        with open(hotels_file, encoding="utf-8") as f:
            hotels = json.load(f)

        count = 0
        for h in hotels:
            self.service.upsert_hotel(
                id=h["id"],
                name=h["name"],
                city_name=h["city"],
                address=h.get("address", ""),
                star_rating=float(h.get("star_rating", 3.0)),
            )
            count += 1
        return count

    def _ingest_suppliers(self) -> int:
        suppliers = [
            {"code": "1A", "name": "Amadeus GDS", "supplier_type": "GDS"},
            {"code": "1S", "name": "Sabre GDS", "supplier_type": "GDS"},
            {"code": "EK-NDC", "name": "Emirates NDC Direct", "supplier_type": "NDC"},
            {"code": "AI-NDC", "name": "Air India NDC Direct", "supplier_type": "NDC"},
            {"code": "HTL-BEDS", "name": "Hotelbeds Wholesale", "supplier_type": "HOTEL_BEDS"},
        ]
        for s in suppliers:
            self.service.upsert_supplier(
                code=s["code"], name=s["name"], supplier_type=s["supplier_type"]
            )

        # Link suppliers to flights
        self.service.link_supplier_flight("EK-NDC", "EK505")
        self.service.link_supplier_flight("EK-NDC", "EK501")
        self.service.link_supplier_flight("1A", "EK505")
        self.service.link_supplier_flight("AI-NDC", "AI915")
        self.service.link_supplier_flight("1A", "AI915")
        self.service.link_supplier_flight("1S", "BA142")
        self.service.link_supplier_flight("1A", "6E1451")

        return len(suppliers)

    def _ingest_policies_and_documents(self) -> tuple[int, int]:
        policies = [
            {
                "id": "EK-POL-CANC",
                "entity_type": "AIRLINE",
                "entity_id": "EK",
                "policy_type": "CANCELLATION",
                "title": "Emirates Cancellation and Refund Policy",
                "content": "Tickets cancelled prior to departure are subject to fare rules and applicable fees.",
                "version": "2024.1",
                "document_id": "doc-ek-cancellation-01",
                "document_title": "Emirates Passenger Service & Cancellation Policy",
                "source": "emirates_cancellation_policy.html",
                "doc_type": "POLICY",
            },
            {
                "id": "AI-POL-FARERULES",
                "entity_type": "AIRLINE",
                "entity_id": "AI",
                "policy_type": "CANCELLATION",
                "title": "Air India Domestic & International Fare Rules",
                "content": "Super Value change fee is INR 3500; Flex change fee is INR 0. Full refund on carrier cancellation.",
                "version": "4.0",
                "document_id": "doc-ai-fare-rules-01",
                "document_title": "Air India Fare Families & Disruption Rules",
                "source": "air_india_fare_rules.json",
                "doc_type": "FARE_RULES",
            },
            {
                "id": "GEN-POL-CARRIAGE",
                "entity_type": "AIRLINE",
                "entity_id": "BA",
                "policy_type": "CONTRACT_OF_CARRIAGE",
                "title": "Conditions of Carriage for Passengers and Baggage",
                "content": "General international carrier conditions of carriage under the Montreal Convention.",
                "version": "1.0",
                "document_id": "doc-carrier-coc-01",
                "document_title": "Carrier General Conditions of Carriage",
                "source": "carrier_contract_of_carriage.pdf",
                "doc_type": "CONTRACT_OF_CARRIAGE",
            },
        ]

        pol_count = 0
        doc_count = 0

        for item in policies:
            self.service.upsert_policy(
                id=item["id"],
                entity_type=item["entity_type"],
                entity_id=item["entity_id"],
                policy_type=item["policy_type"],
                title=item["title"],
                content=item["content"],
                version=item["version"],
            )
            pol_count += 1

            self.service.upsert_document(
                id=item["document_id"],
                title=item["document_title"],
                source=item["source"],
                document_type=item["doc_type"],
                policy_id=item["id"],
                version=item["version"],
            )
            doc_count += 1

        # Also ingest IATA NDC standalone document
        self.service.upsert_document(
            id="doc-iata-ndc-01",
            title="IATA NDC Implementation & Shopping Guide",
            source="iata_ndc_shopping_guide.html",
            document_type="NDC_SPECIFICATION",
            version="21.3",
        )
        doc_count += 1

        return pol_count, doc_count

    def _ingest_fares(self) -> int:
        fares = [
            # Air India Fares for AI915
            {
                "id": "FARE-AI915-SV",
                "fare_basis": "SV-ECON",
                "cabin_class": "ECONOMY",
                "refundable": True,
                "change_fee": 3500.0,
                "cancellation_fee": 4500.0,
                "flight_number": "AI915",
            },
            {
                "id": "FARE-AI915-FL",
                "fare_basis": "FL-FLEX",
                "cabin_class": "ECONOMY",
                "refundable": True,
                "change_fee": 0.0,
                "cancellation_fee": 2000.0,
                "flight_number": "AI915",
            },
            {
                "id": "FARE-AI915-BIZ",
                "fare_basis": "BIZ-EXEC",
                "cabin_class": "BUSINESS",
                "refundable": True,
                "change_fee": 0.0,
                "cancellation_fee": 1000.0,
                "flight_number": "AI915",
            },
            # Emirates Fares for EK505
            {
                "id": "FARE-EK505-SAV",
                "fare_basis": "EK-SAVER",
                "cabin_class": "ECONOMY",
                "refundable": True,
                "change_fee": 5000.0,
                "cancellation_fee": 7000.0,
                "flight_number": "EK505",
            },
            {
                "id": "FARE-EK505-FLX",
                "fare_basis": "EK-FLEXPLUS",
                "cabin_class": "BUSINESS",
                "refundable": True,
                "change_fee": 0.0,
                "cancellation_fee": 2500.0,
                "flight_number": "EK505",
            },
            # British Airways Fares for BA142
            {
                "id": "FARE-BA142-STD",
                "fare_basis": "BA-STANDARD",
                "cabin_class": "ECONOMY",
                "refundable": True,
                "change_fee": 4000.0,
                "cancellation_fee": 6000.0,
                "flight_number": "BA142",
            },
        ]

        for f in fares:
            self.service.upsert_fare(
                id=f["id"],
                fare_basis=f["fare_basis"],
                cabin_class=f["cabin_class"],
                refundable=f["refundable"],
                change_fee=f["change_fee"],
                cancellation_fee=f["cancellation_fee"],
                flight_number=f["flight_number"],
            )

        return len(fares)

    def _ingest_sample_bookings(self) -> int:
        bookings = [
            {
                "reference": "BK-EK505-001",
                "flight_number": "EK505",
                "status": "CONFIRMED",
                "total_amount": 28500.0,
                "currency": "INR",
            },
            {
                "reference": "BK-AI915-002",
                "flight_number": "AI915",
                "status": "CONFIRMED",
                "total_amount": 21000.0,
                "currency": "INR",
            },
            {
                "reference": "BK-BA142-003",
                "flight_number": "BA142",
                "status": "CONFIRMED",
                "total_amount": 65000.0,
                "currency": "INR",
            },
        ]

        for b in bookings:
            self.service.upsert_booking(
                reference=b["reference"],
                flight_number=b["flight_number"],
                status=b["status"],
                total_amount=b["total_amount"],
                currency=b["currency"],
            )

        return len(bookings)


def sync_knowledge_graph(service: GraphService | None = None) -> dict[str, int]:
    """Helper entry point to trigger graph sync."""
    pipeline = GraphIngestionPipeline(service=service)
    return pipeline.run_full_sync()

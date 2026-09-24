"""Unified batch ingestion runner for all travel data domains."""

from pathlib import Path

from ingestion.engine import IdempotentIngestionEngine
from ingestion.models import DocumentType, IngestionResult


class IngestionRunner:
    """Executes ingestion pipelines across all 8 travel domains."""

    def __init__(
        self,
        raw_data_dir: str = "data/raw",
        processed_dir: str = "data/processed",
        manifest_path: str = "data/processed/ingestion_manifest.json",
    ):
        self.raw_dir = Path(raw_data_dir)
        self.engine = IdempotentIngestionEngine(
            manifest_path=manifest_path,
            processed_dir=processed_dir,
        )

    def run_all(self, force: bool = False) -> list[IngestionResult]:
        """Discover and ingest all supported data files in raw directory."""
        results: list[IngestionResult] = []

        # Domain file mapping patterns
        domain_mapping = [
            ("airports.csv", DocumentType.AIRPORT_DATA, "Global Airports Directory"),
            ("airlines.json", DocumentType.AIRLINE_DATA, "Commercial Airlines Catalog"),
            ("flight_routes.csv", DocumentType.FLIGHT_ROUTE, "Flight Routes and Schedules"),
            ("hotels.json", DocumentType.HOTEL_DATA, "Hospitality Properties and Rooms"),
            (
                "emirates_cancellation_policy.html",
                DocumentType.TRAVEL_POLICY,
                "Emirates Cancellation Policy",
            ),
            ("air_india_fare_rules.json", DocumentType.FARE_RULE, "Air India Fare Rules"),
            (
                "iata_ndc_shopping_guide.html",
                DocumentType.NDC_DOCUMENTATION,
                "IATA NDC Shopping Architecture",
            ),
            (
                "amadeus_flight_offers_api.json",
                DocumentType.SUPPLIER_API_DOC,
                "Amadeus Flight Offers API Reference",
            ),
        ]

        for filename, doc_type, title in domain_mapping:
            target_path = self.raw_dir / filename
            if target_path.exists():
                res = self.engine.ingest(
                    source_path_or_url=str(target_path),
                    document_type=doc_type,
                    title=title,
                    force=force,
                )
                results.append(res)

        return results

"""Tests for Travel Data Ingestion Framework (Extractors, Pipelines, and Idempotency)."""

import json
from pathlib import Path

from ingestion.engine import IdempotentIngestionEngine
from ingestion.extractors.api_extractor import APIExtractor
from ingestion.extractors.base import BaseExtractor
from ingestion.extractors.csv_extractor import CSVExtractor
from ingestion.extractors.html_extractor import HTMLExtractor
from ingestion.extractors.json_extractor import JSONExtractor
from ingestion.extractors.pdf_extractor import PDFExtractor
from ingestion.models import DocumentType
from ingestion.pipelines.runner import IngestionRunner


def test_base_extractor_hashing():
    """Verify SHA-256 deterministic checksum calculation."""
    h1 = BaseExtractor.compute_hash("Test travel document content")
    h2 = BaseExtractor.compute_hash("Test travel document content")
    h3 = BaseExtractor.compute_hash("Different travel content")

    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64  # Standard SHA-256 hex length


def test_csv_extractor(tmp_path: Path):
    """Test CSVExtractor parses records, columns, and generates markdown summary."""
    csv_file = tmp_path / "test_airports.csv"
    csv_file.write_text(
        "id,name,city,country\nBOM,Mumbai CSMI,Mumbai,India\nDXB,Dubai International,Dubai,UAE\n",
        encoding="utf-8",
    )

    extractor = CSVExtractor()
    doc = extractor.extract(
        source_path_or_url=str(csv_file),
        document_type=DocumentType.AIRPORT_DATA,
    )

    assert doc.document_type == DocumentType.AIRPORT_DATA
    assert doc.metadata["record_count"] == 2
    assert "Columns: id, name, city, country" in doc.content
    assert doc.raw_data[0]["id"] == "BOM"
    assert doc.hash is not None


def test_json_extractor(tmp_path: Path):
    """Test JSONExtractor parses structured data and computes record counts."""
    json_file = tmp_path / "test_airlines.json"
    sample_data = [
        {"id": "EK", "name": "Emirates"},
        {"id": "AI", "name": "Air India"},
    ]
    json_file.write_text(json.dumps(sample_data), encoding="utf-8")

    extractor = JSONExtractor()
    doc = extractor.extract(
        source_path_or_url=str(json_file),
        document_type=DocumentType.AIRLINE_DATA,
    )

    assert doc.document_type == DocumentType.AIRLINE_DATA
    assert doc.metadata["record_count"] == 2
    assert "Emirates" in doc.content
    assert doc.raw_data == sample_data


def test_html_extractor(tmp_path: Path):
    """Test HTMLExtractor extracts title, headings, and strips script tags."""
    html_file = tmp_path / "test_policy.html"
    html_file.write_text(
        "<html><head><title>Airline Baggage Policy</title>"
        "<script>console.log('malicious');</script></head>"
        "<body><h1>Checked Bags</h1><p>Economy allowance is 25kg.</p></body></html>",
        encoding="utf-8",
    )

    extractor = HTMLExtractor()
    doc = extractor.extract(
        source_path_or_url=str(html_file),
        document_type=DocumentType.TRAVEL_POLICY,
    )

    assert doc.title == "Airline Baggage Policy"
    assert "Economy allowance is 25kg." in doc.content
    assert "console.log" not in doc.content
    assert "Checked Bags" in doc.metadata["headings"]


def test_pdf_extractor(tmp_path: Path):
    """Test PDFExtractor processes PDF files and records page numbers."""
    # Test on the generated PDF in data/raw
    pdf_path = Path("data/raw/carrier_contract_of_carriage.pdf")
    if pdf_path.exists():
        extractor = PDFExtractor()
        doc = extractor.extract(
            source_path_or_url=str(pdf_path),
            document_type=DocumentType.TRAVEL_POLICY,
        )
        assert doc.metadata["format"] == "pdf"
        assert doc.metadata["page_count"] >= 1
        assert "--- Page 1 ---" in doc.content


def test_api_extractor():
    """Test APIExtractor extracts structured API documents."""
    extractor = APIExtractor()
    doc = extractor.extract(
        source_path_or_url="https://api.travelops.ai/mock-feed",
        document_type=DocumentType.SUPPLIER_API_DOC,
        title="Mock Travel Gateway Feed",
    )

    assert doc.document_type == DocumentType.SUPPLIER_API_DOC
    assert doc.metadata["format"] == "api_json"
    assert doc.hash is not None


def test_idempotent_ingestion_engine_lifecycle(tmp_path: Path):
    """Test full idempotency cycle: Initial Ingest -> Duplicate Skip -> Content Change Reingest -> Force Reingest."""
    manifest_path = tmp_path / "test_manifest.json"
    processed_dir = tmp_path / "processed"
    raw_file = tmp_path / "policy.html"
    raw_file.write_text("<h1>Original Policy</h1><p>Fee is ₹5,000.</p>", encoding="utf-8")

    engine = IdempotentIngestionEngine(
        manifest_path=str(manifest_path),
        processed_dir=str(processed_dir),
    )

    # 1. Initial Ingestion
    res1 = engine.ingest(
        source_path_or_url=str(raw_file),
        document_type=DocumentType.TRAVEL_POLICY,
        title="Emirates Cancellation Policy",
    )
    assert res1.status == "INGESTED"
    processed_file = processed_dir / f"{res1.document_id}.json"
    assert processed_file.exists()

    # 2. Duplicate Ingestion (Must be SKIPPED)
    res2 = engine.ingest(
        source_path_or_url=str(raw_file),
        document_type=DocumentType.TRAVEL_POLICY,
    )
    assert res2.status == "SKIPPED"
    assert res2.document_id == res1.document_id
    assert "checksum unchanged" in res2.message

    # 3. Content Modification (Must trigger new INGESTED)
    raw_file.write_text("<h1>Updated Policy</h1><p>Fee increased to ₹6,000.</p>", encoding="utf-8")
    res3 = engine.ingest(
        source_path_or_url=str(raw_file),
        document_type=DocumentType.TRAVEL_POLICY,
    )
    assert res3.status == "INGESTED"
    assert res3.hash != res1.hash

    # 4. Force Ingestion (Must process even if unchanged)
    res4 = engine.ingest(
        source_path_or_url=str(raw_file),
        document_type=DocumentType.TRAVEL_POLICY,
        force=True,
    )
    assert res4.status == "INGESTED"


def test_ingestion_runner_batch():
    """Test IngestionRunner processes raw datasets in batch mode."""
    runner = IngestionRunner()
    results = runner.run_all(force=True)

    # Check that baseline files were discovered and processed
    assert len(results) >= 6
    doc_types = {r.document_type for r in results}
    assert DocumentType.AIRPORT_DATA in doc_types
    assert DocumentType.AIRLINE_DATA in doc_types
    assert DocumentType.FLIGHT_ROUTE in doc_types
    assert DocumentType.HOTEL_DATA in doc_types
    assert DocumentType.TRAVEL_POLICY in doc_types
    assert DocumentType.FARE_RULE in doc_types

"""Idempotent ingestion engine with content-hash tracking."""

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from ingestion.extractors.api_extractor import APIExtractor
from ingestion.extractors.base import BaseExtractor
from ingestion.extractors.csv_extractor import CSVExtractor
from ingestion.extractors.html_extractor import HTMLExtractor
from ingestion.extractors.json_extractor import JSONExtractor
from ingestion.extractors.pdf_extractor import PDFExtractor
from ingestion.models import DocumentType, IngestedDocument, IngestionManifest, IngestionResult


class IdempotentIngestionEngine:
    """Orchestrates document extraction, checksum verification, and idempotent persistence."""

    def __init__(
        self,
        manifest_path: str = "data/processed/ingestion_manifest.json",
        processed_dir: str = "data/processed",
    ):
        self.manifest_path = Path(manifest_path)
        self.processed_dir = Path(processed_dir)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = self._load_manifest()

        # Registry mapping file extensions to extractors
        self._extractors: dict[str, type[BaseExtractor]] = {
            ".csv": CSVExtractor,
            ".json": JSONExtractor,
            ".html": HTMLExtractor,
            ".htm": HTMLExtractor,
            ".pdf": PDFExtractor,
        }

    def _load_manifest(self) -> IngestionManifest:
        """Load manifest from disk or initialize fresh catalog."""
        if self.manifest_path.exists():
            try:
                data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                return IngestionManifest(**data)
            except Exception:
                pass
        return IngestionManifest()

    def _save_manifest(self) -> None:
        """Persist current manifest to disk."""
        self.manifest.last_updated = datetime.now(UTC)
        self.manifest_path.write_text(
            json.dumps(self.manifest.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    def get_extractor_for_path(self, path_or_url: str) -> BaseExtractor:
        """Resolve appropriate extractor instance based on extension or protocol."""
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return APIExtractor()

        path = Path(path_or_url)
        suffix = path.suffix.lower()
        extractor_cls = self._extractors.get(suffix)
        if not extractor_cls:
            raise ValueError(f"Unsupported file format '{suffix}' for {path_or_url}")
        return extractor_cls()

    def ingest(
        self,
        source_path_or_url: str,
        document_type: DocumentType,
        title: str | None = None,
        version: str = "1.0",
        force: bool = False,
    ) -> IngestionResult:
        """Idempotently process and persist a source document."""
        start_time = time.perf_counter()
        extractor = self.get_extractor_for_path(source_path_or_url)

        # Pre-compute hash for local files to check idempotency before full extraction
        is_local = not (
            source_path_or_url.startswith("http://") or source_path_or_url.startswith("https://")
        )
        if is_local:
            file_bytes = Path(source_path_or_url).read_bytes()
            content_hash = BaseExtractor.compute_hash(file_bytes)
            lookup_key = f"{Path(source_path_or_url).name}_{document_type.value}"

            # Idempotency check: Skip if already ingested with identical checksum
            if not force and lookup_key in self.manifest.documents:
                entry = self.manifest.documents[lookup_key]
                if entry.get("hash") == content_hash:
                    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    return IngestionResult(
                        document_id=entry.get("document_id", ""),
                        source=Path(source_path_or_url).name,
                        document_type=document_type,
                        status="SKIPPED",
                        hash=content_hash,
                        message="Document checksum unchanged; skipped re-ingestion.",
                        records_count=entry.get("records_count", 0),
                        duration_ms=duration_ms,
                    )

        # Extract document
        document: IngestedDocument = extractor.extract(
            source_path_or_url=source_path_or_url,
            document_type=document_type,
            title=title,
            version=version,
        )

        lookup_key = f"{document.source}_{document.document_type.value}"

        # Write processed JSON document
        output_file = self.processed_dir / f"{document.document_id}.json"
        output_file.write_text(
            json.dumps(document.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

        # Update manifest
        records_count = document.metadata.get("record_count", 1)
        self.manifest.documents[lookup_key] = {
            "document_id": document.document_id,
            "source": document.source,
            "document_type": document.document_type.value,
            "hash": document.hash,
            "version": document.version,
            "updated_at": document.updated_at.isoformat(),
            "records_count": records_count,
            "processed_file": str(output_file),
        }
        self._save_manifest()

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return IngestionResult(
            document_id=document.document_id,
            source=document.source,
            document_type=document.document_type,
            status="INGESTED",
            hash=document.hash,
            message=f"Successfully extracted and indexed {document_type.value}.",
            records_count=records_count,
            duration_ms=duration_ms,
        )

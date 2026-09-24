"""JSON format extractor for structured travel specifications and catalogs."""

import json
from pathlib import Path
from typing import Any

from ingestion.extractors.base import BaseExtractor
from ingestion.models import DocumentType, IngestedDocument


class JSONExtractor(BaseExtractor):
    """Extracts structured entities and catalogs from JSON files."""

    def extract(
        self,
        source_path_or_url: str,
        document_type: DocumentType = DocumentType.HOTEL_DATA,
        title: str | None = None,
        version: str = "1.0",
        **kwargs: Any,
    ) -> IngestedDocument:
        path = Path(source_path_or_url)
        content_bytes = path.read_bytes()
        file_hash = self.compute_hash(content_bytes)
        parsed_data = json.loads(content_bytes.decode("utf-8", errors="replace"))

        doc_title = title or f"{path.stem.replace('_', ' ').title()} Specification"
        doc_id = f"doc-json-{path.stem}-{file_hash[:12]}"

        # Format readable textual representation for semantic embedding
        formatted_content = json.dumps(parsed_data, indent=2)

        record_count = len(parsed_data) if isinstance(parsed_data, list) else 1

        return IngestedDocument(
            document_id=doc_id,
            source=path.name,
            source_url=str(path.resolve()),
            version=version,
            hash=file_hash,
            document_type=document_type,
            title=doc_title,
            content=formatted_content,
            metadata={
                "format": "json",
                "record_count": record_count,
                "is_list": isinstance(parsed_data, list),
            },
            raw_data=parsed_data,
        )

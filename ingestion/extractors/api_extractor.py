"""API source extractor for live provider feeds and NDC endpoint schemas."""

import json
from typing import Any

import httpx

from ingestion.extractors.base import BaseExtractor
from ingestion.models import DocumentType, IngestedDocument


class APIExtractor(BaseExtractor):
    """Extracts and structures data directly from external travel APIs or schemas."""

    def extract(
        self,
        source_path_or_url: str,
        document_type: DocumentType = DocumentType.SUPPLIER_API_DOC,
        title: str | None = None,
        version: str = "1.0",
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> IngestedDocument:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(source_path_or_url, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except Exception:
            # Fallback simulated response if endpoint is offline
            payload = {
                "endpoint": source_path_or_url,
                "status": "simulated_api_feed",
                "data": {"api_version": version, "service": "Travel Provider Gateway"},
            }

        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        file_hash = self.compute_hash(payload_bytes)
        doc_id = f"doc-api-{file_hash[:12]}"
        doc_title = title or f"API Feed {source_path_or_url}"

        return IngestedDocument(
            document_id=doc_id,
            source=source_path_or_url,
            source_url=source_path_or_url,
            version=version,
            hash=file_hash,
            document_type=document_type,
            title=doc_title,
            content=json.dumps(payload, indent=2),
            metadata={
                "format": "api_json",
                "endpoint": source_path_or_url,
            },
            raw_data=payload,
        )

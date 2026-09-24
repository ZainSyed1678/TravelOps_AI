"""PDF format extractor for airline contract-of-carriage and official fare rules."""

import io
from pathlib import Path
from typing import Any

import pypdf

from ingestion.extractors.base import BaseExtractor
from ingestion.models import DocumentType, IngestedDocument


class PDFExtractor(BaseExtractor):
    """Extracts text page-by-page from PDF files using pypdf."""

    def extract(
        self,
        source_path_or_url: str,
        document_type: DocumentType = DocumentType.TRAVEL_POLICY,
        title: str | None = None,
        version: str = "1.0",
        **kwargs: Any,
    ) -> IngestedDocument:
        path = Path(source_path_or_url)
        content_bytes = path.read_bytes()
        file_hash = self.compute_hash(content_bytes)

        reader = pypdf.PdfReader(io.BytesIO(content_bytes))
        num_pages = len(reader.pages)

        page_texts: list[str] = []
        for page_idx, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            page_texts.append(f"--- Page {page_idx} ---\n{text.strip()}")

        full_content = "\n\n".join(page_texts)
        doc_title = title or f"{path.stem.replace('_', ' ').title()} Document"
        doc_id = f"doc-pdf-{path.stem}-{file_hash[:12]}"

        return IngestedDocument(
            document_id=doc_id,
            source=path.name,
            source_url=str(path.resolve()),
            version=version,
            hash=file_hash,
            document_type=document_type,
            title=doc_title,
            content=full_content,
            metadata={
                "format": "pdf",
                "page_count": num_pages,
                "char_length": len(full_content),
            },
            raw_data={"page_count": num_pages},
        )

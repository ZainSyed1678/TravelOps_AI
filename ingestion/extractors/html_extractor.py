"""HTML format extractor for web travel policies and NDC portal documentation."""

from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from ingestion.extractors.base import BaseExtractor
from ingestion.models import DocumentType, IngestedDocument


class HTMLExtractor(BaseExtractor):
    """Parses HTML documents, strips boilerplate/scripts, and extracts semantic text."""

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

        soup = BeautifulSoup(content_bytes, "html.parser")

        # Strip scripts, styles, and navigation artifacts
        for element in soup(["script", "style", "nav", "footer"]):
            element.decompose()

        # Extract title from <title> or <h1>
        detected_title = title
        if not detected_title:
            if soup.title and soup.title.string:
                detected_title = soup.title.string.strip()
            elif soup.h1:
                detected_title = soup.h1.get_text().strip()
            else:
                detected_title = path.stem.replace("_", " ").title()

        # Extract text with line formatting
        lines = [line.strip() for line in soup.get_text().splitlines()]
        cleaned_text = "\n".join(chunk for chunk in lines if chunk)

        doc_id = f"doc-html-{path.stem}-{file_hash[:12]}"

        # Extract headings for outline metadata
        headings = [h.get_text().strip() for h in soup.find_all(["h1", "h2", "h3"])]

        return IngestedDocument(
            document_id=doc_id,
            source=path.name,
            source_url=str(path.resolve()),
            version=version,
            hash=file_hash,
            document_type=document_type,
            title=detected_title,
            content=cleaned_text,
            metadata={
                "format": "html",
                "headings": headings[:10],
                "char_length": len(cleaned_text),
            },
            raw_data={"headings": headings},
        )

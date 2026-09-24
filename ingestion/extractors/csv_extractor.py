"""CSV format extractor for tabular travel datasets."""

import csv
import io
from pathlib import Path
from typing import Any

from ingestion.extractors.base import BaseExtractor
from ingestion.models import DocumentType, IngestedDocument


class CSVExtractor(BaseExtractor):
    """Extracts tabular records from CSV files with row count and schema detection."""

    def extract(
        self,
        source_path_or_url: str,
        document_type: DocumentType = DocumentType.AIRPORT_DATA,
        title: str | None = None,
        version: str = "1.0",
        **kwargs: Any,
    ) -> IngestedDocument:
        path = Path(source_path_or_url)
        content_bytes = path.read_bytes()
        file_hash = self.compute_hash(content_bytes)
        text_content = content_bytes.decode("utf-8", errors="replace")

        reader = csv.DictReader(io.StringIO(text_content))
        rows: list[dict[str, str]] = list(reader)
        fieldnames = reader.fieldnames or []

        doc_title = title or f"{path.stem.replace('_', ' ').title()} Dataset"
        doc_id = f"doc-csv-{path.stem}-{file_hash[:12]}"

        # Render structured summary for text/RAG indexing
        summary_lines = [
            f"# {doc_title}",
            f"Source: {path.name}",
            f"Columns: {', '.join(fieldnames)}",
            f"Total Records: {len(rows)}\n",
            "## Sample Records:",
        ]
        for idx, row in enumerate(rows[:5], 1):
            row_repr = ", ".join(f"{k}: {v}" for k, v in row.items())
            summary_lines.append(f"{idx}. {row_repr}")

        return IngestedDocument(
            document_id=doc_id,
            source=path.name,
            source_url=str(path.resolve()),
            version=version,
            hash=file_hash,
            document_type=document_type,
            title=doc_title,
            content="\n".join(summary_lines),
            metadata={
                "format": "csv",
                "record_count": len(rows),
                "columns": fieldnames,
            },
            raw_data=rows,
        )

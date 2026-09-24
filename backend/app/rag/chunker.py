"""Structure-aware document chunker preserving headings, sections, and metadata."""

import re

from app.rag.models import DocumentChunk
from ingestion.models import IngestedDocument


class StructureAwareChunker:
    """Splits documents according to heading hierarchies, page breaks, and paragraphs."""

    def __init__(
        self,
        target_chunk_size: int = 500,
        chunk_overlap: int = 80,
    ):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, document: IngestedDocument) -> list[DocumentChunk]:
        """Convert IngestedDocument into structured DocumentChunks."""
        text = document.content
        chunks: list[DocumentChunk] = []

        # Detect domain metadata tags
        airline = self._extract_airline(document)
        supplier = self._extract_supplier(document)
        policy_type = self._extract_policy_type(document)
        effective_date = document.metadata.get("effective_date")

        # Check for page boundaries (common in PDF extractions)
        has_pages = "--- Page " in text
        if has_pages:
            page_blocks = re.split(r"--- Page (\d+) ---", text)
            # page_blocks is [intro, page_num1, text1, page_num2, text2, ...]
            current_page: int | None = 1
            idx = 0
            while idx < len(page_blocks):
                part = page_blocks[idx].strip()
                if part.isdigit():
                    current_page = int(part)
                    idx += 1
                    if idx < len(page_blocks):
                        page_text = page_blocks[idx].strip()
                        chunks.extend(
                            self._split_section_into_chunks(
                                text=page_text,
                                document=document,
                                page=current_page,
                                section=f"Page {current_page}",
                                airline=airline,
                                supplier=supplier,
                                policy_type=policy_type,
                                effective_date=effective_date,
                                start_index=len(chunks),
                            )
                        )
                elif part:
                    chunks.extend(
                        self._split_section_into_chunks(
                            text=part,
                            document=document,
                            page=current_page,
                            section="Header",
                            airline=airline,
                            supplier=supplier,
                            policy_type=policy_type,
                            effective_date=effective_date,
                            start_index=len(chunks),
                        )
                    )
                idx += 1
            return (
                chunks
                if chunks
                else [self._fallback_chunk(document, airline, supplier, policy_type)]
            )

        # Heading-based splitting (Markdown / HTML extracted text)
        sections = self._split_by_headings(text)
        for sec_title, sec_body in sections:
            if not sec_body.strip():
                continue
            sub_chunks = self._split_section_into_chunks(
                text=sec_body,
                document=document,
                page=None,
                section=sec_title,
                airline=airline,
                supplier=supplier,
                policy_type=policy_type,
                effective_date=effective_date,
                start_index=len(chunks),
            )
            chunks.extend(sub_chunks)

        if not chunks:
            chunks.append(self._fallback_chunk(document, airline, supplier, policy_type))

        return chunks

    def _split_by_headings(self, text: str) -> list[tuple[str, str]]:
        """Split text by Markdown headings (#, ##, ###) while preserving section titles."""
        lines = text.splitlines()
        sections: list[tuple[str, str]] = []
        current_title = "Overview"
        current_lines: list[str] = []

        for line in lines:
            line_stripped = line.strip()
            # Detect Markdown header
            if line_stripped.startswith("#") and not line_stripped.startswith("####"):
                if current_lines:
                    sections.append((current_title, "\n".join(current_lines)))
                    current_lines = []
                current_title = line_stripped.lstrip("#").strip()
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_title, "\n".join(current_lines)))

        return sections if sections else [("Overview", text)]

    def _split_section_into_chunks(
        self,
        text: str,
        document: IngestedDocument,
        page: int | None,
        section: str | None,
        airline: str | None,
        supplier: str | None,
        policy_type: str | None,
        effective_date: str | None,
        start_index: int,
    ) -> list[DocumentChunk]:
        """Split a single section into bounded chunks respecting paragraph and sentence boundaries."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[DocumentChunk] = []
        current_buffer = ""
        chunk_idx = start_index

        for para in paragraphs:
            if len(current_buffer) + len(para) <= self.target_chunk_size:
                current_buffer = f"{current_buffer}\n\n{para}".strip()
            else:
                if current_buffer:
                    chunk_id = f"{document.document_id}#c{chunk_idx}"
                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            document_id=document.document_id,
                            source=document.source,
                            content=current_buffer,
                            page=page,
                            section=section,
                            document_type=document.document_type.value,
                            airline=airline,
                            supplier=supplier,
                            policy_type=policy_type,
                            effective_date=effective_date,
                            version=document.version,
                            char_count=len(current_buffer),
                            metadata={"doc_title": document.title},
                        )
                    )
                    chunk_idx += 1
                    # Overlap with end of buffer
                    overlap_tail = (
                        current_buffer[-self.chunk_overlap :]
                        if len(current_buffer) > self.chunk_overlap
                        else ""
                    )
                    current_buffer = f"{overlap_tail}\n\n{para}".strip() if overlap_tail else para
                else:
                    current_buffer = para

        if current_buffer:
            chunk_id = f"{document.document_id}#c{chunk_idx}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    source=document.source,
                    content=current_buffer,
                    page=page,
                    section=section,
                    document_type=document.document_type.value,
                    airline=airline,
                    supplier=supplier,
                    policy_type=policy_type,
                    effective_date=effective_date,
                    version=document.version,
                    char_count=len(current_buffer),
                    metadata={"doc_title": document.title},
                )
            )

        return chunks

    def _fallback_chunk(
        self,
        document: IngestedDocument,
        airline: str | None,
        supplier: str | None,
        policy_type: str | None,
    ) -> DocumentChunk:
        return DocumentChunk(
            chunk_id=f"{document.document_id}#c0",
            document_id=document.document_id,
            source=document.source,
            content=document.content[: self.target_chunk_size],
            page=None,
            section="Full Document",
            document_type=document.document_type.value,
            airline=airline,
            supplier=supplier,
            policy_type=policy_type,
            version=document.version,
            char_count=len(document.content[: self.target_chunk_size]),
        )

    def _extract_airline(self, document: IngestedDocument) -> str | None:
        source_lower = f"{document.source} {document.title} {document.content[:500]}".lower()
        if "emirates" in source_lower or " ek" in source_lower:
            return "EK"
        if "air india" in source_lower or " ai" in source_lower:
            return "AI"
        if "indigo" in source_lower or " 6e" in source_lower:
            return "6E"
        if "british airways" in source_lower or " ba" in source_lower:
            return "BA"
        return None

    def _extract_supplier(self, document: IngestedDocument) -> str | None:
        source_lower = f"{document.source} {document.title}".lower()
        if "amadeus" in source_lower:
            return "AMADEUS"
        if "sabre" in source_lower:
            return "SABRE"
        if "ndc" in source_lower:
            return "NDC"
        return None

    def _extract_policy_type(self, document: IngestedDocument) -> str | None:
        source_lower = f"{document.source} {document.title}".lower()
        if "cancellation" in source_lower or "refund" in source_lower:
            return "CANCELLATION"
        if "baggage" in source_lower:
            return "BAGGAGE"
        if "disruption" in source_lower:
            return "DISRUPTION"
        if "fare" in source_lower:
            return "FARE_RULE"
        return None

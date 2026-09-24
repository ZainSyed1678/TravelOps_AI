"""Base extractor class and hashing utilities."""

import hashlib
from abc import ABC, abstractmethod

from ingestion.models import IngestedDocument


class BaseExtractor(ABC):
    """Abstract base extractor providing SHA-256 checksum computation and extraction contract."""

    @staticmethod
    def compute_hash(content: str | bytes) -> str:
        """Calculate standard SHA-256 hexadecimal digest for idempotency verification."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    @abstractmethod
    def extract(self, source_path_or_url: str, **kwargs) -> IngestedDocument:
        """Extract and structure data into a canonical IngestedDocument."""
        pass

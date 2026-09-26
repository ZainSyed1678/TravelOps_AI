"""Input sanitization, XSS stripping, and SQL injection defense utilities."""

import html
import re
import unicodedata

# Dangerous HTML/script patterns
HTML_TAG_PATTERN = re.compile(r"<[^>]*?>", re.IGNORECASE)
JAVASCRIPT_URI_PATTERN = re.compile(r"javascript:\s*", re.IGNORECASE)
DATA_URI_PATTERN = re.compile(r"data:\s*text/html", re.IGNORECASE)

# SQL injection probe patterns
SQL_INJECTION_PATTERNS = [
    re.compile(
        r"(\b(UNION(\s+ALL)?|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC)\b.*\b(FROM|INTO|TABLE|DATABASE)\b)",
        re.IGNORECASE,
    ),
    re.compile(r"(\bOR\b|\bAND\b)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+", re.IGNORECASE),
    re.compile(r"(--|#|/\*|\*/|;)\s*$", re.MULTILINE),
]


def normalize_unicode(text: str) -> str:
    """Normalize Unicode characters using NFKC and strip non-printable characters."""
    normalized = unicodedata.normalize("NFKC", text)
    # Strip non-printable / control characters (except newline, tab, carriage return)
    cleaned = "".join(
        ch for ch in normalized if unicodedata.category(ch)[0] != "C" or ch in ("\n", "\r", "\t")
    )
    return cleaned


def strip_html(text: str) -> str:
    """Strip HTML tags and unescape HTML entities to prevent stored and reflected XSS."""
    no_tags = HTML_TAG_PATTERN.sub("", text)
    no_js_uri = JAVASCRIPT_URI_PATTERN.sub("", no_tags)
    no_data_uri = DATA_URI_PATTERN.sub("", no_js_uri)
    return html.unescape(no_data_uri).strip()


def sanitize_input(text: str) -> str:
    """Comprehensive input sanitization pipeline."""
    if not text:
        return ""
    normalized = normalize_unicode(text)
    stripped = strip_html(normalized)
    return stripped


def check_sql_injection(text: str) -> tuple[bool, str | None]:
    """Check if input contains potential SQL injection patterns.

    Returns (is_suspicious, pattern_name).
    """
    for idx, pattern in enumerate(SQL_INJECTION_PATTERNS):
        if pattern.search(text):
            return True, f"SQL_INJECTION_PATTERN_{idx + 1}"
    return False, None

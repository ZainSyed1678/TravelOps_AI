"""Prompt injection and adversarial jailbreak detection guard for Agentic AI workflows."""

import re
from typing import ClassVar

from pydantic import BaseModel, Field

from app.security.sanitizer import sanitize_input


class InjectionInspectionResult(BaseModel):
    """Result of prompt safety and injection inspection."""

    is_safe: bool = Field(..., description="Whether prompt is safe for agent processing")
    risk_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score of injection (0.0=safe, 1.0=critical)"
    )
    risk_category: str = Field(
        ..., description="Classification category: CLEAN, JAILBREAK_ATTEMPT, SYSTEM_OVERRIDE, etc."
    )
    matched_patterns: list[str] = Field(
        default_factory=list, description="List of matched adversarial heuristic triggers"
    )
    cleaned_text: str = Field(..., description="Sanitized text with harmful delimiters neutralized")


class InjectionGuard:
    """Production guardrail detecting direct and indirect prompt injection attempts."""

    JAILBREAK_TRIGGERS: ClassVar[list[tuple[str, re.Pattern]]] = [
        (
            "DIRECT_INSTRUCTION_OVERRIDE",
            re.compile(
                r"\b(ignore|disregard|forget|bypass|override)\b.*?\b(previous|all|prior|above|system)\b.*?\b(instructions|rules|guidelines|prompts)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "JAILBREAK_PERSONA",
            re.compile(
                r"\b(you\s+are\s+now|act\s+as|pretend\s+to\s+be)\b.*?\b(dan|jailbreak|unrestricted|godmode|root|evil|anti-gpt)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "SYSTEM_PROMPT_LEAK",
            re.compile(
                r"\b(print|reveal|output|display|show|repeat)\b.*?\b(system\s+prompt|initial\s+instructions|hidden\s+rules|developer\s+mode)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "DELIMITER_HIJACK",
            re.compile(
                r"(<\|im_start\|>|<\|im_end\|>|<\|system\|>|\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>|```system|---BEGIN SYSTEM---)",
                re.IGNORECASE,
            ),
        ),
        (
            "ROLEPLAY_ESCALATION",
            re.compile(
                r"\b(developer\s+mode\s+enabled|safety\s+filters?\s+disabled|ethics\s+protocol\s+suspended)\b",
                re.IGNORECASE,
            ),
        ),
    ]

    def inspect(self, text: str) -> InjectionInspectionResult:
        """Inspect and score an incoming user prompt for injection and adversarial exploits."""
        from app.security.sanitizer import normalize_unicode

        normalized_raw = normalize_unicode(text)
        sanitized = sanitize_input(text)
        matched_triggers: list[str] = []

        for category, pattern in self.JAILBREAK_TRIGGERS:
            if pattern.search(sanitized) or pattern.search(normalized_raw):
                matched_triggers.append(category)

        if not matched_triggers:
            return InjectionInspectionResult(
                is_safe=True,
                risk_score=0.0,
                risk_category="CLEAN",
                matched_patterns=[],
                cleaned_text=sanitized,
            )

        # Calculate composite risk score
        risk_score = min(1.0, 0.4 + (0.3 * len(matched_triggers)))
        primary_category = matched_triggers[0]

        return InjectionInspectionResult(
            is_safe=False,
            risk_score=round(risk_score, 2),
            risk_category=primary_category,
            matched_patterns=matched_triggers,
            cleaned_text=sanitized,
        )


injection_guard = InjectionGuard()

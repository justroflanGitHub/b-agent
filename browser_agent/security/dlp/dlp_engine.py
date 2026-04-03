"""DLP engine — policy enforcement for data loss prevention.

Scans LLM prompts, responses, extracted data, and screenshots
for PII/sensitive data and applies configurable actions.
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .pii_detector import PIIDetector, PIIType, PIIMatch
from .redaction import DataRedactor, RedactionStrategy, TokenMap

logger = logging.getLogger(__name__)


class DLPAction(Enum):
    REDACT = "redact"        # Redact and continue
    BLOCK = "block"          # Block the action
    ALERT = "alert"          # Alert but continue
    LOG = "log"              # Log only


@dataclass
class DLPPolicy:
    """DLP policy configuration."""
    action: DLPAction = DLPAction.REDACT
    pii_types: List[PIIType] = field(default_factory=list)  # Empty = all types
    redaction_strategy: RedactionStrategy = RedactionStrategy.MASK
    confidence_threshold: float = 0.7
    scan_prompts: bool = True
    scan_responses: bool = True
    scan_extractions: bool = True
    scan_screenshots: bool = False
    block_on_detection: bool = False
    alert_on_detection: bool = True
    log_on_detection: bool = True


@dataclass
class DLPViolation:
    """Record of a PII detection event."""
    pii_type: PIIType
    field_name: Optional[str]
    confidence: float
    value_hash: str
    action_taken: DLPAction
    location: str  # "prompt", "response", "extraction", "screenshot"

    def to_dict(self) -> dict:
        return {
            "pii_type": self.pii_type.value,
            "field_name": self.field_name,
            "confidence": self.confidence,
            "value_hash": self.value_hash,
            "action_taken": self.action_taken.value,
            "location": self.location,
        }


@dataclass
class DLPResult:
    """Result of a DLP scan."""
    has_violations: bool
    action_taken: DLPAction
    violations: List[DLPViolation] = field(default_factory=list)
    redacted_content: Optional[Any] = None
    original_content_hash: str = ""
    scan_duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "has_violations": self.has_violations,
            "action_taken": self.action_taken.value,
            "violations": [v.to_dict() for v in self.violations],
            "original_content_hash": self.original_content_hash,
            "scan_duration_ms": self.scan_duration_ms,
        }


class DLPEngine:
    """Data Loss Prevention engine.

    Scans text and data for PII, applies redaction/blocking policies,
    and logs violations.
    """

    def __init__(
        self,
        detector: Optional[PIIDetector] = None,
        redactor: Optional[DataRedactor] = None,
        policy: Optional[DLPPolicy] = None,
        audit_callback=None,
    ):
        self._detector = detector or PIIDetector()
        self._redactor = redactor or DataRedactor()
        self._policy = policy or DLPPolicy()
        self._audit_callback = audit_callback

    @property
    def policy(self) -> DLPPolicy:
        return self._policy

    @policy.setter
    def policy(self, value: DLPPolicy):
        self._policy = value

    async def scan_text(self, text: str, context: str = "unknown") -> DLPResult:
        """Scan text for PII and apply policy."""
        start = time.monotonic()

        matches = self._detector.detect(text)
        # Filter by configured PII types and confidence
        filtered = self._filter_matches(matches)

        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        if not filtered:
            return DLPResult(
                has_violations=False,
                action_taken=DLPAction.LOG,
                original_content_hash=content_hash,
                scan_duration_ms=(time.monotonic() - start) * 1000,
            )

        violations = [
            DLPViolation(
                pii_type=m.pii_type,
                field_name=None,
                confidence=m.confidence,
                value_hash=hashlib.sha256(m.value.encode()).hexdigest()[:16],
                action_taken=self._policy.action,
                location=context,
            )
            for m in filtered
        ]

        action = self._determine_action(violations)
        redacted = None

        if action in (DLPAction.REDACT, DLPAction.BLOCK):
            redacted_text = self._redactor.redact_text(text, filtered)
            redacted = redacted_text.redacted_text

        # Log
        if self._policy.log_on_detection:
            logger.warning(
                "DLP: %d violation(s) in %s, action=%s types=%s",
                len(violations), context, action.value,
                [v.pii_type.value for v in violations],
            )

        # Audit callback
        if self._audit_callback:
            try:
                await self._audit_callback(violations, context)
            except Exception as e:
                logger.warning("Audit callback failed: %s", e)

        return DLPResult(
            has_violations=True,
            action_taken=action,
            violations=violations,
            redacted_content=redacted,
            original_content_hash=content_hash,
            scan_duration_ms=(time.monotonic() - start) * 1000,
        )

    async def scan_dict(self, data: Dict[str, Any], context: str = "extraction") -> DLPResult:
        """Scan dictionary for PII."""
        all_text = " ".join(str(v) for v in data.values() if isinstance(v, str))
        result = await self.scan_text(all_text, context)

        if result.has_violations and result.action_taken == DLPAction.REDACT:
            # Also redact the dict
            matches_by_field = {}
            for key, value in data.items():
                if isinstance(value, str):
                    field_matches = self._detector.detect(value)
                    filtered = self._filter_matches(field_matches)
                    if filtered:
                        matches_by_field[key] = filtered

            if matches_by_field:
                redacted = self._redactor.redact_dict(data, matches_by_field)
                result.redacted_content = redacted

        return result

    async def scan_prompt(self, prompt: str) -> DLPResult:
        """Scan LLM prompt before sending."""
        if not self._policy.scan_prompts:
            return DLPResult(has_violations=False, action_taken=DLPAction.LOG)
        return await self.scan_text(prompt, "prompt")

    async def scan_response(self, response: str) -> DLPResult:
        """Scan LLM response."""
        if not self._policy.scan_responses:
            return DLPResult(has_violations=False, action_taken=DLPAction.LOG)
        return await self.scan_text(response, "response")

    async def scan_extraction(self, data: Any) -> DLPResult:
        """Scan extracted data before returning to caller."""
        if not self._policy.scan_extractions:
            return DLPResult(has_violations=False, action_taken=DLPAction.LOG)
        if isinstance(data, dict):
            return await self.scan_dict(data, "extraction")
        return await self.scan_text(str(data), "extraction")

    def _filter_matches(self, matches: List[PIIMatch]) -> List[PIIMatch]:
        """Filter matches by PII type and confidence threshold."""
        filtered = []
        for m in matches:
            if m.confidence < self._policy.confidence_threshold:
                continue
            if self._policy.pii_types and m.pii_type not in self._policy.pii_types:
                continue
            filtered.append(m)
        return filtered

    def _determine_action(self, violations: List[DLPViolation]) -> DLPAction:
        """Determine action based on policy and violations."""
        if self._policy.block_on_detection:
            return DLPAction.BLOCK
        return self._policy.action

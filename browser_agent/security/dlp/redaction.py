"""Data redaction — mask, replace, hash, or remove PII from content.

Supports reversible tokenization for cases where PII needs to be
restored after processing (e.g., after LLM call).
"""

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RedactionStrategy(Enum):
    MASK = "mask"            # "123-45-6789" → "12*******9"
    REPLACE = "replace"      # "123-45-6789" → "[SSN]"
    HASH = "hash"            # "123-45-6789" → "[SSN:a1b2c3]"
    REMOVE = "remove"        # "my SSN is 123-45-6789" → "my SSN is "
    PARTIAL = "partial"      # "John Smith" → "J*** S***"


@dataclass
class RedactedText:
    """Result of redacting text."""
    original_hash: str
    redacted_text: str
    redaction_count: int
    redacted_types: List[str] = field(default_factory=list)
    token_map: Optional["TokenMap"] = None

    def to_dict(self) -> dict:
        return {
            "original_hash": self.original_hash,
            "redacted_text": self.redacted_text,
            "redaction_count": self.redaction_count,
            "redacted_types": self.redacted_types,
        }


class TokenMap:
    """Reversible mapping of redacted values to tokens.

    Used when PII must be restored after processing (e.g., after
    sending redacted text to an LLM, restore original values).
    """

    def __init__(self):
        self._mapping: Dict[str, str] = {}  # token → original

    def create_token(self, value: str, pii_type: str = "") -> str:
        """Create a reversible token for a value."""
        token = f"[{pii_type}:{uuid.uuid4().hex[:8]}]"
        self._mapping[token] = value
        return token

    def detokenize(self, text: str) -> str:
        """Replace tokens back with original values."""
        result = text
        for token, original in self._mapping.items():
            result = result.replace(token, original)
        return result

    def get_original(self, token: str) -> Optional[str]:
        return self._mapping.get(token)

    @property
    def size(self) -> int:
        return len(self._mapping)

    def clear(self):
        """Securely clear the mapping."""
        self._mapping.clear()


class DataRedactor:
    """Redact PII from text and data structures."""

    def __init__(
        self,
        strategy: RedactionStrategy = RedactionStrategy.MASK,
        preserve_types: Optional[List[str]] = None,
    ):
        self._strategy = strategy
        self._preserve_types = set(preserve_types or [])

    def redact_text(self, text: str, matches: list) -> RedactedText:
        """Redact PII from text given a list of PIIMatch objects.

        Processes matches in reverse order (end of string first)
        to preserve positions.
        """
        redacted_types = set()
        token_map = TokenMap() if self._strategy == RedactionStrategy.HASH else None

        result = text
        # Sort by start position descending to preserve indices
        sorted_matches = sorted(matches, key=lambda m: m.start, reverse=True)

        for match in sorted_matches:
            original = match.value
            pii_type = match.pii_type.value if hasattr(match, 'pii_type') else "unknown"
            redacted_types.add(pii_type)

            replacement = self._apply_strategy(original, pii_type, token_map)
            result = result[:match.start] + replacement + result[match.end:]

        original_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        return RedactedText(
            original_hash=original_hash,
            redacted_text=result,
            redaction_count=len(matches),
            redacted_types=list(redacted_types),
            token_map=token_map,
        )

    def redact_dict(self, data: Dict[str, Any], matches_by_field: Dict[str, list]) -> Dict[str, Any]:
        """Redact PII from dictionary values."""
        result = dict(data)
        for field_path, matches in matches_by_field.items():
            # Navigate nested dicts
            keys = field_path.split(".")
            obj = result
            for key in keys[:-1]:
                if isinstance(obj, dict) and key in obj:
                    obj = obj[key]
                else:
                    break
            else:
                last_key = keys[-1]
                if isinstance(obj, dict) and last_key in obj and isinstance(obj[last_key], str):
                    redacted = self.redact_text(obj[last_key], matches)
                    obj[last_key] = redacted.redacted_text
        return result

    def _apply_strategy(self, value: str, pii_type: str, token_map: Optional[TokenMap]) -> str:
        if self._strategy == RedactionStrategy.MASK:
            if len(value) <= 3:
                return "*" * len(value)
            return value[:2] + "*" * (len(value) - 3) + value[-1]

        elif self._strategy == RedactionStrategy.REPLACE:
            return f"[{pii_type.upper()}]"

        elif self._strategy == RedactionStrategy.HASH:
            if token_map:
                return token_map.create_token(value, pii_type)
            h = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
            return f"[{pii_type}:{h}]"

        elif self._strategy == RedactionStrategy.REMOVE:
            return ""

        elif self._strategy == RedactionStrategy.PARTIAL:
            parts = value.split()
            return " ".join(p[0] + "*" * (len(p) - 1) for p in parts) if parts else "***"

        return "*" * len(value)

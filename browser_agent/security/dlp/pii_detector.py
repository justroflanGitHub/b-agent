"""PII detection via regex patterns.

Detects common PII types in text: SSN, credit cards, emails, phones,
API keys, passwords, and more. Supports custom patterns.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class PIIType(Enum):
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    PHONE = "phone"
    EMAIL = "email"
    DATE_OF_BIRTH = "date_of_birth"
    ADDRESS = "address"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    BANK_ACCOUNT = "bank_account"
    IP_ADDRESS = "ip_address"
    MEDICAL_RECORD = "medical_record"
    NAME = "name"
    API_KEY = "api_key"
    PASSWORD = "password"
    CUSTOM = "custom"


@dataclass
class PIIMatch:
    """A single PII detection match."""

    pii_type: PIIType
    value: str
    start: int
    end: int
    confidence: float
    masked: str

    def to_dict(self) -> dict:
        return {
            "pii_type": self.pii_type.value,
            "value_hash": _hash_value(self.value),
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "masked": self.masked,
        }


def _hash_value(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


# Luhn check for credit card validation
def _luhn_check(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse = digits[::-1]
    for i, d in enumerate(reverse):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


BUILTIN_PATTERNS: Dict[PIIType, List[re.Pattern]] = {
    PIIType.SSN: [
        re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
        re.compile(r"\b(?!000|666|9\d{2})\d{3}\s(?!00)\d{2}\s(?!0000)\d{4}\b"),
    ],
    PIIType.CREDIT_CARD: [
        re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
        re.compile(r"\b\d{4}[\s-]?\d{6}[\s-]?\d{5}\b"),
    ],
    PIIType.EMAIL: [
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    ],
    PIIType.PHONE: [
        re.compile(r"\b\+?1?\s*\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b"),
        re.compile(r"\b\+\d{1,3}\s\d{2,4}\s\d{3,4}\s\d{3,4}\b"),
    ],
    PIIType.DATE_OF_BIRTH: [
        re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
    ],
    PIIType.IP_ADDRESS: [
        re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"),
    ],
    PIIType.API_KEY: [
        re.compile(r'(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*["\']?[\w\-]{16,}["\']?'),
        re.compile(r"\bsk-[a-zA-Z0-9]{32,}\b"),
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(r"\bghp_[a-zA-Z0-9]{36}\b"),
        re.compile(r"\bglpat-[a-zA-Z0-9\-]{20,}\b"),
    ],
    PIIType.PASSWORD: [
        re.compile(r"(?i)(?:password|passwd|pwd)\s*[:=]\s*\S+"),
    ],
    PIIType.BANK_ACCOUNT: [
        re.compile(r"\b\d{8,17}\b"),
    ],
    PIIType.MEDICAL_RECORD: [
        re.compile(r"(?i)(?:mrn|medical[_-]?record|patient[_-]?id)\s*[:=]\s*[\w\-]{4,}"),
    ],
    PIIType.NAME: [
        re.compile(r"(?i)(?:full[_\s]?name|patient[_\s]?name)\s*[:=]\s*[A-Z][a-z]+\s+[A-Z][a-z]+"),
    ],
}


def _mask_value(value: str, visible_chars: int = 2) -> str:
    """Mask a value, keeping first N and last char visible."""
    if len(value) <= visible_chars + 1:
        return "*" * len(value)
    return value[:visible_chars] + "*" * (len(value) - visible_chars - 1) + value[-1]


class PIIDetector:
    """Detect personally identifiable information in text."""

    def __init__(self, custom_patterns: Optional[Dict[str, str]] = None):
        self._patterns: Dict[PIIType, List[re.Pattern]] = dict(BUILTIN_PATTERNS)
        self._custom: Dict[str, re.Pattern] = {}

        if custom_patterns:
            for name, pattern in custom_patterns.items():
                self._custom[name] = re.compile(pattern)
                # Also add as CUSTOM type
                if PIIType.CUSTOM not in self._patterns:
                    self._patterns[PIIType.CUSTOM] = []
                self._patterns[PIIType.CUSTOM].append(re.compile(pattern))

    def detect(self, text: str) -> List[PIIMatch]:
        """Scan text for PII patterns."""
        matches: List[PIIMatch] = []

        for pii_type, patterns in self._patterns.items():
            for pattern in patterns:
                for m in pattern.finditer(text):
                    value = m.group(0)

                    # Extra validation
                    if pii_type == PIIType.CREDIT_CARD:
                        digits_only = re.sub(r"[\s-]", "", value)
                        if not _luhn_check(digits_only):
                            continue
                        confidence = 0.95
                    elif pii_type == PIIType.EMAIL:
                        confidence = 0.95
                    elif pii_type == PIIType.SSN:
                        confidence = 0.9
                    elif pii_type in (PIIType.API_KEY, PIIType.PASSWORD):
                        confidence = 0.85
                    else:
                        confidence = 0.7

                    matches.append(
                        PIIMatch(
                            pii_type=pii_type,
                            value=value,
                            start=m.start(),
                            end=m.end(),
                            confidence=confidence,
                            masked=_mask_value(value),
                        )
                    )

        # Sort by position
        matches.sort(key=lambda m: m.start)
        return matches

    def detect_in_dict(self, data: dict) -> Dict[str, List[PIIMatch]]:
        """Scan all string values in a dictionary."""
        results: Dict[str, List[PIIMatch]] = {}
        for key, value in data.items():
            if isinstance(value, str):
                found = self.detect(value)
                if found:
                    results[key] = found
            elif isinstance(value, dict):
                nested = self.detect_in_dict(value)
                for nk, nv in nested.items():
                    results[f"{key}.{nk}"] = nv
        return results

    def has_pii(self, text: str) -> bool:
        """Quick check if text contains PII."""
        return len(self.detect(text)) > 0

    def get_pii_types(self, text: str) -> List[PIIType]:
        """Get list of PII types found in text."""
        matches = self.detect(text)
        return list(dict.fromkeys(m.pii_type for m in matches))  # Unique, ordered

    def add_custom_pattern(self, name: str, pattern: str):
        """Add a custom detection pattern."""
        compiled = re.compile(pattern)
        self._custom[name] = compiled
        if PIIType.CUSTOM not in self._patterns:
            self._patterns[PIIType.CUSTOM] = []
        self._patterns[PIIType.CUSTOM].append(compiled)

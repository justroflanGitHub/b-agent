"""Data sensitivity classification for extracted content.

Classifies data based on content patterns, source URL, and user-defined rules.
Used by the audit trail and DLP engine.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .audit_log import SensitivityLevel


class DataCategory(Enum):
    PII = "pii"
    PHI = "phi"
    FINANCIAL = "financial"
    CREDENTIALS = "credentials"
    INTERNAL = "internal"
    PUBLIC = "public"
    CONFIDENTIAL = "confidential"
    PERSONAL = "personal"


@dataclass
class FieldClassification:
    field_name: str
    categories: List[DataCategory]
    sensitivity: SensitivityLevel
    confidence: float
    patterns_matched: List[str]


@dataclass
class ClassificationResult:
    sensitivity: SensitivityLevel
    categories: List[DataCategory]
    pii_fields: List[str]
    phi_fields: List[str]
    financial_fields: List[str]
    confidence: float
    rules_matched: List[str]


@dataclass
class PageClassification:
    url: str
    sensitivity: SensitivityLevel
    categories: List[DataCategory]
    is_internal: bool
    is_admin: bool
    has_login: bool


# URL patterns for classification
INTERNAL_URL_PATTERNS = [
    r"^https?://(localhost|127\.0\.0\.1|10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)",
    r"^https?://.*\.internal\b",
    r"^https?://.*\.corp\b",
    r"^https?://.*\.intranet\b",
]

ADMIN_URL_PATTERNS = [
    r"/admin",
    r"/management",
    r"/dashboard",
    r"/console",
    r"/backoffice",
]

# Content patterns
PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "name": re.compile(r"\b(name|full[_ ]?name|first[_ ]?name|last[_ ]?name)\b", re.I),
}

FINANCIAL_PATTERNS = {
    "credit_card": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "price": re.compile(r"\$\d+[,.]?\d*"),
    "bank_account": re.compile(r"\b(account|iban|routing)\s*(number|no)?\b", re.I),
}

CREDENTIAL_PATTERNS = {
    "password": re.compile(r"(?i)(password|passwd|pwd|secret)"),
    "api_key": re.compile(r"(?i)(api[_-]?key|token|auth)"),
    "token": re.compile(r"\b(bearer|token)\s+[\w\-]+\b", re.I),
}

FIELD_NAME_RULES = {
    # field_name_pattern -> (DataCategory, SensitivityLevel)
    r"(?i)(email|e-mail)": (DataCategory.PII, SensitivityLevel.CONFIDENTIAL),
    r"(?i)(phone|tel|mobile)": (DataCategory.PII, SensitivityLevel.CONFIDENTIAL),
    r"(?i)(ssn|social.security)": (DataCategory.PII, SensitivityLevel.RESTRICTED),
    r"(?i)(name|full_?name|first_?name|last_?name)": (DataCategory.PERSONAL, SensitivityLevel.INTERNAL),
    r"(?i)(address|street|city|zip|postal)": (DataCategory.PII, SensitivityLevel.CONFIDENTIAL),
    r"(?i)(password|passwd|pwd|secret)": (DataCategory.CREDENTIALS, SensitivityLevel.RESTRICTED),
    r"(?i)(api_?key|token|auth)": (DataCategory.CREDENTIALS, SensitivityLevel.RESTRICTED),
    r"(?i)(credit_?card|cc_?num|card_?number)": (DataCategory.FINANCIAL, SensitivityLevel.RESTRICTED),
    r"(?i)(salary|compensation|income|revenue|profit)": (DataCategory.FINANCIAL, SensitivityLevel.CONFIDENTIAL),
    r"(?i)(diagnosis|medical|health|patient|prescription)": (DataCategory.PHI, SensitivityLevel.RESTRICTED),
    r"(?i)(dob|birth_?date|date_?of_?birth)": (DataCategory.PII, SensitivityLevel.CONFIDENTIAL),
    r"(?i)(passport|license|id_?number)": (DataCategory.PII, SensitivityLevel.RESTRICTED),
    r"(?i)(iban|bank|account|routing|swift)": (DataCategory.FINANCIAL, SensitivityLevel.RESTRICTED),
}


class DataClassifier:
    """Classify extracted data by sensitivity level."""

    def __init__(self, custom_rules: Optional[Dict[str, tuple]] = None):
        self._rules = dict(FIELD_NAME_RULES)
        if custom_rules:
            self._rules.update(custom_rules)

    def classify(self, data: Any, context: Optional[Dict] = None) -> ClassificationResult:
        """Classify data based on content and context."""
        if isinstance(data, dict):
            return self._classify_dict(data, context)
        elif isinstance(data, str):
            return self._classify_text(data, context)
        elif isinstance(data, list):
            # Classify each item, return highest sensitivity
            results = [self.classify(item, context) for item in data[:10]]
            if not results:
                return ClassificationResult(
                    sensitivity=SensitivityLevel.PUBLIC,
                    categories=[],
                    pii_fields=[],
                    phi_fields=[],
                    financial_fields=[],
                    confidence=1.0,
                    rules_matched=[],
                )
            max_sensitivity = max(results, key=lambda r: list(SensitivityLevel).index(r.sensitivity))
            return ClassificationResult(
                sensitivity=max_sensitivity.sensitivity,
                categories=list(set(c for r in results for c in r.categories)),
                pii_fields=list(set(f for r in results for f in r.pii_fields)),
                phi_fields=list(set(f for r in results for f in r.phi_fields)),
                financial_fields=list(set(f for r in results for f in r.financial_fields)),
                confidence=max(r.confidence for r in results),
                rules_matched=list(set(r for res in results for r in res.rules_matched)),
            )
        else:
            return ClassificationResult(
                sensitivity=SensitivityLevel.PUBLIC,
                categories=[],
                pii_fields=[],
                phi_fields=[],
                financial_fields=[],
                confidence=1.0,
                rules_matched=[],
            )

    def classify_field(self, field_name: str, field_value: Any) -> FieldClassification:
        """Classify a single data field."""
        categories = []
        sensitivity = SensitivityLevel.PUBLIC
        patterns_matched = []
        confidence = 0.5

        for pattern, (cat, sens) in self._rules.items():
            if re.search(pattern, field_name):
                categories.append(cat)
                if list(SensitivityLevel).index(sens) > list(SensitivityLevel).index(sensitivity):
                    sensitivity = sens
                patterns_matched.append(pattern)
                confidence = max(confidence, 0.8)

        # Check value content
        value_str = str(field_value) if field_value else ""
        for name, pattern in PII_PATTERNS.items():
            if pattern.search(value_str):
                categories.append(DataCategory.PII)
                patterns_matched.append(f"value:{name}")
                confidence = max(confidence, 0.9)

        return FieldClassification(
            field_name=field_name,
            categories=list(set(categories)),
            sensitivity=sensitivity,
            confidence=confidence,
            patterns_matched=patterns_matched,
        )

    def classify_page(self, url: str, page_content: str = "") -> PageClassification:
        """Classify an entire page's data sensitivity."""
        is_internal = any(re.match(p, url) for p in INTERNAL_URL_PATTERNS)
        is_admin = any(re.search(p, url) for p in ADMIN_URL_PATTERNS)
        has_login = bool(re.search(r"(?i)(login|signin|sign-in|authenticate)", page_content or url))

        sensitivity = SensitivityLevel.PUBLIC
        categories = []

        if is_internal:
            sensitivity = SensitivityLevel.INTERNAL
            categories.append(DataCategory.INTERNAL)
        if is_admin:
            sensitivity = SensitivityLevel.RESTRICTED
            categories.append(DataCategory.CONFIDENTIAL)
        if has_login:
            categories.append(DataCategory.CREDENTIALS)
            if list(SensitivityLevel).index(SensitivityLevel.CONFIDENTIAL) > list(SensitivityLevel).index(sensitivity):
                sensitivity = SensitivityLevel.CONFIDENTIAL

        return PageClassification(
            url=url,
            sensitivity=sensitivity,
            categories=categories,
            is_internal=is_internal,
            is_admin=is_admin,
            has_login=has_login,
        )

    def _classify_dict(self, data: Dict, context: Optional[Dict] = None) -> ClassificationResult:
        pii_fields = []
        phi_fields = []
        financial_fields = []
        categories = set()
        rules_matched = []
        max_sensitivity = SensitivityLevel.PUBLIC
        total_confidence = 0.0
        field_count = 0

        for field_name, field_value in data.items():
            fc = self.classify_field(field_name, field_value)
            if fc.categories:
                categories.update(fc.categories)
                rules_matched.extend(fc.patterns_matched)
                if DataCategory.PII in fc.categories:
                    pii_fields.append(field_name)
                if DataCategory.PHI in fc.categories:
                    phi_fields.append(field_name)
                if DataCategory.FINANCIAL in fc.categories:
                    financial_fields.append(field_name)
                if list(SensitivityLevel).index(fc.sensitivity) > list(SensitivityLevel).index(max_sensitivity):
                    max_sensitivity = fc.sensitivity
                total_confidence += fc.confidence
                field_count += 1

        avg_confidence = total_confidence / field_count if field_count else 1.0

        # Check value content for PII patterns
        for field_name, field_value in data.items():
            value_str = str(field_value) if field_value else ""
            for name, pattern in PII_PATTERNS.items():
                if pattern.search(value_str):
                    if field_name not in pii_fields:
                        pii_fields.append(field_name)
                    categories.add(DataCategory.PII)

        return ClassificationResult(
            sensitivity=max_sensitivity,
            categories=list(categories),
            pii_fields=pii_fields,
            phi_fields=phi_fields,
            financial_fields=financial_fields,
            confidence=avg_confidence,
            rules_matched=rules_matched,
        )

    def _classify_text(self, text: str, context: Optional[Dict] = None) -> ClassificationResult:
        categories = set()
        patterns_matched = []

        for name, pattern in PII_PATTERNS.items():
            if pattern.search(text):
                categories.add(DataCategory.PII)
                patterns_matched.append(name)

        for name, pattern in FINANCIAL_PATTERNS.items():
            if pattern.search(text):
                categories.add(DataCategory.FINANCIAL)
                patterns_matched.append(name)

        for name, pattern in CREDENTIAL_PATTERNS.items():
            if pattern.search(text):
                categories.add(DataCategory.CREDENTIALS)
                patterns_matched.append(name)

        if categories:
            sensitivity = SensitivityLevel.CONFIDENTIAL
            if DataCategory.CREDENTIALS in categories:
                sensitivity = SensitivityLevel.RESTRICTED
        else:
            sensitivity = SensitivityLevel.PUBLIC

        return ClassificationResult(
            sensitivity=sensitivity,
            categories=list(categories),
            pii_fields=[],
            phi_fields=[],
            financial_fields=[],
            confidence=0.9 if categories else 0.5,
            rules_matched=patterns_matched,
        )

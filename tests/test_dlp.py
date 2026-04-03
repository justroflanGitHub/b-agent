"""Tests for browser_agent.security.dlp — PII detection, redaction, DLP engine."""

import pytest
from browser_agent.security.dlp.pii_detector import PIIDetector, PIIType, PIIMatch
from browser_agent.security.dlp.redaction import DataRedactor, RedactionStrategy, TokenMap
from browser_agent.security.dlp.dlp_engine import DLPEngine, DLPPolicy, DLPAction


# --- PIIDetector ---


class TestPIIDetector:
    @pytest.fixture
    def detector(self):
        return PIIDetector()

    def test_detect_email(self, detector):
        text = "Contact us at admin@acme.com for help"
        matches = detector.detect(text)
        emails = [m for m in matches if m.pii_type == PIIType.EMAIL]
        assert len(emails) >= 1
        assert "admin@acme.com" in emails[0].value

    def test_detect_phone(self, detector):
        text = "Call 555-123-4567 now"
        matches = detector.detect(text)
        phones = [m for m in matches if m.pii_type == PIIType.PHONE]
        assert len(phones) >= 1

    def test_detect_ssn(self, detector):
        text = "SSN: 123-45-6789"
        matches = detector.detect(text)
        ssns = [m for m in matches if m.pii_type == PIIType.SSN]
        assert len(ssns) >= 1
        assert "123-45-6789" in ssns[0].value

    def test_detect_credit_card(self, detector):
        # Valid Luhn: 4532015112830366
        text = "Card: 4532-0151-1283-0366"
        matches = detector.detect(text)
        ccs = [m for m in matches if m.pii_type == PIIType.CREDIT_CARD]
        assert len(ccs) >= 1

    def test_reject_invalid_credit_card(self, detector):
        text = "Code: 1234-5678-9012-3456"
        matches = detector.detect(text)
        ccs = [m for m in matches if m.pii_type == PIIType.CREDIT_CARD]
        assert len(ccs) == 0  # Fails Luhn check

    def test_detect_api_key(self, detector):
        text = "api_key: sk-abcdefghijklmnopqrstuvwxyz123456"
        matches = detector.detect(text)
        keys = [m for m in matches if m.pii_type == PIIType.API_KEY]
        assert len(keys) >= 1

    def test_detect_aws_key(self, detector):
        text = "AWS key: AKIAIOSFODNN7EXAMPLE"
        matches = detector.detect(text)
        keys = [m for m in matches if m.pii_type == PIIType.API_KEY]
        assert len(keys) >= 1

    def test_detect_ip_address(self, detector):
        text = "Server at 192.168.1.100 responded"
        matches = detector.detect(text)
        ips = [m for m in matches if m.pii_type == PIIType.IP_ADDRESS]
        assert len(ips) >= 1
        assert "192.168.1.100" in ips[0].value

    def test_detect_password_in_text(self, detector):
        text = "password=MyS3cr3tP@ss!"
        matches = detector.detect(text)
        pwds = [m for m in matches if m.pii_type == PIIType.PASSWORD]
        assert len(pwds) >= 1

    def test_detect_multiple_types(self, detector):
        text = "User admin@corp.com called from 555-123-4567 about order at 192.168.1.1"
        matches = detector.detect(text)
        types = set(m.pii_type for m in matches)
        assert PIIType.EMAIL in types
        assert PIIType.PHONE in types
        assert PIIType.IP_ADDRESS in types

    def test_detect_in_dict(self, detector):
        data = {
            "email": "user@test.com",
            "safe_field": "hello world",
            "phone": "555-123-4567",
        }
        results = detector.detect_in_dict(data)
        assert "email" in results
        assert "phone" in results
        assert "safe_field" not in results

    def test_has_pii(self, detector):
        assert detector.has_pii("Email: test@corp.com") is True
        assert detector.has_pii("Hello world") is False

    def test_get_pii_types(self, detector):
        text = "admin@corp.com and 555-123-4567"
        types = detector.get_pii_types(text)
        assert PIIType.EMAIL in types
        assert PIIType.PHONE in types

    def test_custom_pattern(self, detector):
        detector.add_custom_pattern("employee_id", r"EMP-\d{6}")
        text = "Employee EMP-123456 logged in"
        matches = detector.detect(text)
        customs = [m for m in matches if m.pii_type == PIIType.CUSTOM]
        assert len(customs) >= 1

    def test_init_with_custom_patterns(self):
        detector = PIIDetector(custom_patterns={"project": r"PRJ-[A-Z]{3}-\d{3}"})
        text = "Project PRJ-ABC-123 started"
        matches = detector.detect(text)
        customs = [m for m in matches if m.pii_type == PIIType.CUSTOM]
        assert len(customs) >= 1

    def test_no_matches_clean_text(self, detector):
        matches = detector.detect("The quick brown fox jumps over the lazy dog")
        # Might match date-like patterns or phone-like, but should be minimal
        assert len(matches) == 0 or all(m.confidence < 0.9 for m in matches)

    def test_confidence_scores(self, detector):
        matches = detector.detect("Email: test@corp.com")
        assert all(m.confidence >= 0.5 for m in matches)


# --- DataRedactor ---


class TestDataRedactor:
    def _make_matches(self, detector, text):
        return detector.detect(text)

    def test_mask_strategy(self):
        from browser_agent.security.dlp.pii_detector import PIIDetector
        detector = PIIDetector()
        redactor = DataRedactor(strategy=RedactionStrategy.MASK)
        text = "Email: admin@acme.com is the contact"
        matches = detector.detect(text)
        result = redactor.redact_text(text, matches)
        assert "admin@acme.com" not in result.redacted_text
        assert result.redaction_count >= 1

    def test_replace_strategy(self):
        from browser_agent.security.dlp.pii_detector import PIIDetector
        detector = PIIDetector()
        redactor = DataRedactor(strategy=RedactionStrategy.REPLACE)
        text = "Email: admin@acme.com"
        matches = detector.detect(text)
        result = redactor.redact_text(text, matches)
        assert "[EMAIL]" in result.redacted_text
        assert "admin@acme.com" not in result.redacted_text

    def test_remove_strategy(self):
        from browser_agent.security.dlp.pii_detector import PIIDetector
        detector = PIIDetector()
        redactor = DataRedactor(strategy=RedactionStrategy.REMOVE)
        text = "Email: admin@acme.com here"
        matches = detector.detect(text)
        result = redactor.redact_text(text, matches)
        assert "admin@acme.com" not in result.redacted_text

    def test_partial_strategy(self):
        from browser_agent.security.dlp.pii_detector import PIIDetector
        detector = PIIDetector()
        redactor = DataRedactor(strategy=RedactionStrategy.PARTIAL)
        text = "Email: admin@acme.com"
        matches = detector.detect(text)
        result = redactor.redact_text(text, matches)
        assert result.redaction_count >= 1

    def test_redacted_text_has_original_hash(self):
        from browser_agent.security.dlp.pii_detector import PIIDetector
        detector = PIIDetector()
        redactor = DataRedactor()
        text = "admin@acme.com"
        matches = detector.detect(text)
        result = redactor.redact_text(text, matches)
        assert result.original_hash != ""
        assert len(result.original_hash) == 64


# --- TokenMap ---


class TestTokenMap:
    def test_create_and_detokenize(self):
        tm = TokenMap()
        token = tm.create_token("secret_value", "ssn")
        assert "[ssn:" in token
        restored = tm.detokenize(f"Data: {token}")
        assert "secret_value" in restored

    def test_get_original(self):
        tm = TokenMap()
        token = tm.create_token("secret_value", "email")
        assert tm.get_original(token) == "secret_value"

    def test_get_nonexistent(self):
        tm = TokenMap()
        assert tm.get_original("[nonexistent:abc]") is None

    def test_size(self):
        tm = TokenMap()
        tm.create_token("v1", "type1")
        tm.create_token("v2", "type2")
        assert tm.size == 2

    def test_clear(self):
        tm = TokenMap()
        tm.create_token("v1", "type1")
        tm.clear()
        assert tm.size == 0


# --- DLPEngine ---


class TestDLPEngine:
    @pytest.fixture
    def engine(self):
        return DLPEngine(policy=DLPPolicy(action=DLPAction.REDACT))

    @pytest.mark.asyncio
    async def test_scan_clean_text(self, engine):
        result = await engine.scan_text("Hello world, no PII here")
        assert result.has_violations is False

    @pytest.mark.asyncio
    async def test_scan_text_with_email(self, engine):
        result = await engine.scan_text("Contact admin@corp.com")
        assert result.has_violations is True
        assert result.action_taken == DLPAction.REDACT
        assert "admin@corp.com" not in (result.redacted_content or "")

    @pytest.mark.asyncio
    async def test_scan_text_blocked(self):
        engine = DLPEngine(policy=DLPPolicy(action=DLPAction.BLOCK, block_on_detection=True))
        result = await engine.scan_text("SSN: 123-45-6789")
        assert result.has_violations is True
        assert result.action_taken == DLPAction.BLOCK

    @pytest.mark.asyncio
    async def test_scan_dict(self, engine):
        data = {
            "name": "John",
            "email": "user@test.com",
            "safe": "hello",
        }
        result = await engine.scan_dict(data)
        assert result.has_violations is True

    @pytest.mark.asyncio
    async def test_scan_prompt(self, engine):
        result = await engine.scan_prompt("What is the weather? email: test@corp.com")
        assert result.has_violations is True
        assert result.violations[0].location == "prompt"

    @pytest.mark.asyncio
    async def test_scan_response(self, engine):
        result = await engine.scan_response("The user's email is admin@corp.com")
        assert result.has_violations is True
        assert result.violations[0].location == "response"

    @pytest.mark.asyncio
    async def test_scan_extraction(self, engine):
        result = await engine.scan_extraction({"email": "user@test.com"})
        assert result.has_violations is True
        assert result.violations[0].location == "extraction"

    @pytest.mark.asyncio
    async def test_scan_disabled(self):
        engine = DLPEngine(policy=DLPPolicy(scan_prompts=False))
        result = await engine.scan_prompt("Email: test@corp.com")
        assert result.has_violations is False

    @pytest.mark.asyncio
    async def test_confidence_threshold(self):
        engine = DLPEngine(policy=DLPPolicy(confidence_threshold=0.99))
        # Most patterns have < 0.99 confidence, so should pass
        result = await engine.scan_text("Some text with admin@corp.com")
        # Email has 0.95 confidence, below 0.99 threshold
        assert result.has_violations is False

    @pytest.mark.asyncio
    async def test_pii_type_filter(self):
        engine = DLPEngine(policy=DLPPolicy(
            action=DLPAction.REDACT,
            pii_types=[PIIType.EMAIL],
        ))
        result = await engine.scan_text("Email: test@corp.com and IP 192.168.1.1")
        assert result.has_violations is True
        # Should only flag email, not IP
        assert all(v.pii_type == PIIType.EMAIL for v in result.violations)

    @pytest.mark.asyncio
    async def test_violation_hashes(self, engine):
        result = await engine.scan_text("admin@corp.com")
        assert result.has_violations is True
        for v in result.violations:
            assert v.value_hash != ""
            assert len(v.value_hash) == 16

    @pytest.mark.asyncio
    async def test_result_serialization(self, engine):
        result = await engine.scan_text("admin@corp.com")
        d = result.to_dict()
        assert "has_violations" in d
        assert "violations" in d
        assert isinstance(d["violations"], list)

    @pytest.mark.asyncio
    async def test_audit_callback(self):
        called_with = []
        async def audit_cb(violations, context):
            called_with.append((violations, context))

        engine = DLPEngine(
            policy=DLPPolicy(action=DLPAction.REDACT, log_on_detection=True),
            audit_callback=audit_cb,
        )
        await engine.scan_text("admin@corp.com")
        assert len(called_with) == 1
        assert called_with[0][1] in ("unknown", "prompt", "response", "extraction")

    @pytest.mark.asyncio
    async def test_scan_duration_tracked(self, engine):
        result = await engine.scan_text("admin@corp.com")
        assert result.scan_duration_ms >= 0

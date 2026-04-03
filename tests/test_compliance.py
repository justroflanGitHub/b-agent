"""Tests for browser_agent.compliance.audit_log — Audit trail and chain verification."""

import pytest
from datetime import datetime, timedelta, timezone

from browser_agent.compliance.audit_log import (
    AuditEvent,
    AuditEventType,
    AuditFilter,
    AuditLog,
    AuditStore,
    ComplianceReport,
    FileAuditStore,
    SensitivityLevel,
    SQLiteAuditStore,
    TaskTimeline,
)
from browser_agent.compliance.chain import AuditChain, ChainVerificationResult


@pytest.fixture
def chain():
    return AuditChain(signing_key=b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!!")


@pytest.fixture
def sqlite_store(tmp_path):
    return SQLiteAuditStore(str(tmp_path / "audit.db"))


@pytest.fixture
def file_store(tmp_path):
    return FileAuditStore(str(tmp_path / "audit"))


@pytest.fixture
def audit_log(sqlite_store, chain):
    return AuditLog(sqlite_store, chain)


@pytest.fixture
def file_audit_log(file_store, chain):
    return AuditLog(file_store, chain)


# --- AuditEvent ---


class TestAuditEvent:
    def test_compute_hash_deterministic(self):
        event = AuditEvent(
            event_type=AuditEventType.TASK_CREATED,
            tenant_id="acme",
            task_id="task-1",
        )
        h1 = event.compute_hash()
        h2 = event.compute_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_different_events_different_hashes(self):
        e1 = AuditEvent(event_type=AuditEventType.TASK_CREATED, tenant_id="acme")
        e2 = AuditEvent(event_type=AuditEventType.TASK_FAILED, tenant_id="acme")
        assert e1.compute_hash() != e2.compute_hash()

    def test_to_dict_roundtrip(self):
        event = AuditEvent(
            event_type=AuditEventType.ACTION_EXECUTED,
            tenant_id="acme",
            user_id="alice",
            task_id="task-1",
            step_index=3,
            action_type="click",
            target_url="https://example.com",
            outcome="success",
            data_sensitivity=SensitivityLevel.CONFIDENTIAL,
        )
        d = event.to_dict()
        restored = AuditEvent.from_dict(d)
        assert restored.event_type == AuditEventType.ACTION_EXECUTED
        assert restored.tenant_id == "acme"
        assert restored.step_index == 3
        assert restored.data_sensitivity == SensitivityLevel.CONFIDENTIAL

    def test_serialization_all_fields(self):
        event = AuditEvent(
            event_type=AuditEventType.DATA_EXTRACTED,
            tenant_id="acme",
            task_id="t1",
            data_categories=["pii", "financial"],
            error_message=None,
        )
        d = event.to_dict()
        restored = AuditEvent.from_dict(d)
        assert restored.data_categories == ["pii", "financial"]


# --- AuditChain ---


class TestAuditChain:
    def test_link_sets_hash_and_signature(self, chain):
        event = AuditEvent(event_type=AuditEventType.TASK_CREATED, tenant_id="acme")
        event.previous_hash = "GENESIS"
        linked = chain.link(event)
        assert linked.event_hash != ""
        assert linked.chain_signature != ""

    def test_invalid_signing_key(self):
        with pytest.raises(ValueError, match="16 bytes"):
            AuditChain(signing_key=b"short")

    def test_verify_valid_chain(self, chain):
        events = []
        prev_hash = "GENESIS"
        for i in range(5):
            event = AuditEvent(
                event_type=AuditEventType.ACTION_EXECUTED,
                tenant_id="acme",
                step_index=i,
                previous_hash=prev_hash,
            )
            linked = chain.link(event)
            events.append(linked)
            prev_hash = linked.event_hash

        result = chain.verify(events)
        assert result.is_valid is True
        assert result.verified_events == 5
        assert result.total_events == 5
        assert len(result.tampered_events) == 0

    def test_verify_tampered_event(self, chain):
        events = []
        prev_hash = "GENESIS"
        for i in range(3):
            event = AuditEvent(
                event_type=AuditEventType.ACTION_EXECUTED,
                tenant_id="acme",
                step_index=i,
                previous_hash=prev_hash,
            )
            linked = chain.link(event)
            events.append(linked)
            prev_hash = linked.event_hash

        # Tamper with middle event
        events[1].outcome = "TAMPERED"

        result = chain.verify(events)
        assert result.is_valid is False
        assert len(result.tampered_events) >= 1

    def test_verify_broken_chain(self, chain):
        events = []
        for i in range(3):
            event = AuditEvent(
                event_type=AuditEventType.ACTION_EXECUTED,
                tenant_id="acme",
                previous_hash="GENESIS",  # All claim GENESIS — wrong
            )
            linked = chain.link(event)
            events.append(linked)

        result = chain.verify(events)
        assert result.is_valid is False

    def test_verify_empty_events(self, chain):
        result = chain.verify([])
        assert result.is_valid is True
        assert result.total_events == 0

    def test_seal(self, chain):
        events = []
        prev_hash = "GENESIS"
        for i in range(5):
            event = AuditEvent(
                event_type=AuditEventType.ACTION_EXECUTED,
                tenant_id="acme",
                previous_hash=prev_hash,
            )
            linked = chain.link(event)
            events.append(linked)
            prev_hash = linked.event_hash

        seal = chain.seal(events)
        assert seal.merkle_root != ""
        assert seal.event_count == 5
        assert seal.first_event_id == events[0].event_id
        assert seal.last_event_id == events[-1].event_id

        # Verify seal
        assert seal.verify(chain._signing_key, events) is True

    def test_seal_empty_raises(self, chain):
        with pytest.raises(ValueError, match="empty"):
            chain.seal([])


# --- AuditLog ---


class TestAuditLog:
    @pytest.mark.asyncio
    async def test_record_event(self, audit_log):
        event = await audit_log.record(
            event_type=AuditEventType.TASK_CREATED,
            tenant_id="acme",
            task_id="task-1",
            parameters={"goal": "Test task"},
        )
        assert event.event_id != ""
        assert event.event_hash != ""
        assert event.chain_signature != ""
        assert event.previous_hash == "GENESIS"

    @pytest.mark.asyncio
    async def test_chain_links_events(self, audit_log):
        e1 = await audit_log.record(
            event_type=AuditEventType.TASK_CREATED,
            tenant_id="acme",
            task_id="task-1",
        )
        e2 = await audit_log.record(
            event_type=AuditEventType.ACTION_EXECUTED,
            tenant_id="acme",
            task_id="task-1",
            step_index=0,
        )
        assert e2.previous_hash == e1.event_hash
        assert e2.previous_hash != "GENESIS"

    @pytest.mark.asyncio
    async def test_query_by_tenant(self, audit_log):
        for tenant in ["acme", "globex", "acme"]:
            await audit_log.record(
                event_type=AuditEventType.ACTION_EXECUTED,
                tenant_id=tenant,
            )
        events = await audit_log.query(AuditFilter(tenant_id="acme"))
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_query_by_task(self, audit_log):
        await audit_log.record(event_type="task.created", tenant_id="acme", task_id="t1")
        await audit_log.record(event_type="action.executed", tenant_id="acme", task_id="t1")
        await audit_log.record(event_type="action.executed", tenant_id="acme", task_id="t2")

        events = await audit_log.query(AuditFilter(tenant_id="acme", task_id="t1"))
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_query_by_event_type(self, audit_log):
        await audit_log.record(event_type=AuditEventType.TASK_CREATED, tenant_id="acme")
        await audit_log.record(event_type=AuditEventType.TASK_FAILED, tenant_id="acme")
        await audit_log.record(event_type=AuditEventType.TASK_CREATED, tenant_id="acme")

        events = await audit_log.query(AuditFilter(
            tenant_id="acme",
            event_types=[AuditEventType.TASK_CREATED],
        ))
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_query_by_time_range(self, audit_log):
        now = datetime.now(timezone.utc)
        await audit_log.record(event_type="task.created", tenant_id="acme")

        events = await audit_log.query(AuditFilter(
            tenant_id="acme",
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        ))
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_query_with_limit_offset(self, audit_log):
        for i in range(5):
            await audit_log.record(event_type="action.executed", tenant_id="acme", step_index=i)

        page1 = await audit_log.query(AuditFilter(tenant_id="acme", limit=2, offset=0))
        page2 = await audit_log.query(AuditFilter(tenant_id="acme", limit=2, offset=2))
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].event_id != page2[0].event_id

    @pytest.mark.asyncio
    async def test_verify_chain_valid(self, audit_log):
        for i in range(5):
            await audit_log.record(event_type="action.executed", tenant_id="acme", step_index=i)

        result = await audit_log.verify_chain("acme")
        assert result.is_valid is True
        assert result.verified_events == 5

    @pytest.mark.asyncio
    async def test_get_task_timeline(self, audit_log):
        await audit_log.record(event_type="task.created", tenant_id="acme", task_id="t1")
        await audit_log.record(event_type="action.executed", tenant_id="acme", task_id="t1", step_index=0, outcome="success")
        await audit_log.record(event_type="action.executed", tenant_id="acme", task_id="t1", step_index=1, outcome="failure")
        await audit_log.record(event_type="task.completed", tenant_id="acme", task_id="t1")

        timeline = await audit_log.get_task_timeline("t1", "acme")
        assert timeline.task_id == "t1"
        assert timeline.action_count == 2
        assert timeline.success_count == 3  # created + 1 success + completed
        assert timeline.failure_count == 1

    @pytest.mark.asyncio
    async def test_compliance_report(self, audit_log):
        await audit_log.record(event_type="task.created", tenant_id="acme", task_id="t1")
        await audit_log.record(event_type="task.completed", tenant_id="acme", task_id="t1")
        await audit_log.record(event_type="task.created", tenant_id="acme", task_id="t2")
        await audit_log.record(event_type="task.failed", tenant_id="acme", task_id="t2")

        now = datetime.now(timezone.utc)
        report = await audit_log.generate_compliance_report(
            framework="soc2",
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=1),
            tenant_id="acme",
        )
        assert report.total_tasks == 2
        assert report.completed_tasks == 1
        assert report.failed_tasks == 1
        assert report.chain_integrity is True

    @pytest.mark.asyncio
    async def test_compliance_report_dlp_finding(self, audit_log):
        await audit_log.record(event_type="dlp.violation", tenant_id="acme")
        now = datetime.now(timezone.utc)
        report = await audit_log.generate_compliance_report(
            framework="soc2",
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=1),
            tenant_id="acme",
        )
        assert report.dlp_violations == 1
        assert any("DLP" in f["message"] for f in report.findings)

    @pytest.mark.asyncio
    async def test_file_store_backend(self, file_audit_log):
        """Same operations work with file store."""
        await file_audit_log.record(event_type="task.created", tenant_id="acme", task_id="t1")
        await file_audit_log.record(event_type="action.executed", tenant_id="acme", task_id="t1")

        events = await file_audit_log.query(AuditFilter(tenant_id="acme"))
        assert len(events) == 2

        result = await file_audit_log.verify_chain("acme")
        assert result.is_valid is True


# --- AuditFilter ---


class TestAuditFilter:
    def test_defaults(self):
        f = AuditFilter()
        assert f.limit == 100
        assert f.offset == 0
        assert f.tenant_id is None


# --- ComplianceReport ---


class TestComplianceReport:
    def test_to_dict(self):
        report = ComplianceReport(
            framework="soc2",
            tenant_id="acme",
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
        )
        d = report.to_dict()
        assert d["framework"] == "soc2"
        assert d["tenant_id"] == "acme"
        assert d["chain_integrity"] is True

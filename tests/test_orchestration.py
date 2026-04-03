"""Tests for browser_agent.orchestration — multi-tenant, resource pool, quotas, metering."""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone

from browser_agent.orchestration.tenant_manager import (
    TenantManager, Tenant, TenantPlan, TenantStatus, TenantStore,
)
from browser_agent.orchestration.resource_pool import ResourcePool, ResourcePoolConfig, BrowserWorker, WorkerStatus
from browser_agent.orchestration.scheduler_fair import FairScheduler, TenantTask
from browser_agent.orchestration.quotas import QuotaManager, QuotaStore
from browser_agent.orchestration.metering import MeteringEngine, MeteringStore


# --- Tenant ---


class TestTenant:
    def test_with_plan_free(self):
        t = Tenant.with_plan(TenantPlan.FREE, name="test")
        assert t.max_concurrent_tasks == 1
        assert t.features["credential_vault"] is False

    def test_with_plan_enterprise(self):
        t = Tenant.with_plan(TenantPlan.ENTERPRISE, name="bigcorp")
        assert t.max_concurrent_tasks == 20
        assert t.features["recording"] is True

    def test_to_dict_roundtrip(self):
        t = Tenant(name="Test", plan=TenantPlan.PROFESSIONAL, owner_email="admin@test.com")
        d = t.to_dict()
        r = Tenant.from_dict(d)
        assert r.name == "Test"
        assert r.plan == TenantPlan.PROFESSIONAL
        assert r.owner_email == "admin@test.com"

    def test_auto_scopes(self):
        t = Tenant(name="test")
        assert t.credential_scope.startswith("tenant_")
        assert t.audit_scope == t.tenant_id


class TestTenantManager:
    @pytest.fixture
    def mgr(self, tmp_path):
        return TenantManager(TenantStore(str(tmp_path / "tenants.db")))

    @pytest.mark.asyncio
    async def test_create_and_get(self, mgr):
        t = await mgr.create_tenant("Acme Corp", TenantPlan.STARTER, owner_email="admin@acme.com")
        loaded = await mgr.get_tenant(t.tenant_id)
        assert loaded is not None
        assert loaded.name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_update(self, mgr):
        t = await mgr.create_tenant("Test")
        updated = await mgr.update_tenant(t.tenant_id, {"name": "Updated", "max_daily_tasks": 500})
        assert updated.name == "Updated"
        assert updated.max_daily_tasks == 500

    @pytest.mark.asyncio
    async def test_suspend_and_activate(self, mgr):
        t = await mgr.create_tenant("Test")
        assert await mgr.suspend_tenant(t.tenant_id, "billing") is True
        loaded = await mgr.get_tenant(t.tenant_id)
        assert loaded.status == TenantStatus.SUSPENDED
        assert await mgr.activate_tenant(t.tenant_id) is True
        loaded = await mgr.get_tenant(t.tenant_id)
        assert loaded.status == TenantStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_delete(self, mgr):
        t = await mgr.create_tenant("ToDelete")
        assert await mgr.delete_tenant(t.tenant_id) is True
        assert await mgr.get_tenant(t.tenant_id) is None

    @pytest.mark.asyncio
    async def test_list_tenants(self, mgr):
        await mgr.create_tenant("A")
        await mgr.create_tenant("B")
        tenants = await mgr.list_tenants()
        assert len(tenants) == 2

    @pytest.mark.asyncio
    async def test_api_key_validation(self, mgr):
        t = await mgr.create_tenant("KeyTest")
        await mgr.set_api_key(t.tenant_id, "sk-test-key-123")
        assert await mgr.validate_access(t.tenant_id, "sk-test-key-123") is True
        assert await mgr.validate_access(t.tenant_id, "wrong-key") is False

    @pytest.mark.asyncio
    async def test_nonexistent_tenant(self, mgr):
        assert await mgr.get_tenant("nope") is None


# --- ResourcePool ---


class TestResourcePool:
    @pytest.fixture
    def pool(self):
        return ResourcePool(ResourcePoolConfig(max_workers=5, min_workers=0))

    @pytest.mark.asyncio
    async def test_acquire_and_release(self, pool):
        pool.set_tenant_limit("acme", 2)
        w = await pool.acquire("acme")
        assert w.status == WorkerStatus.BUSY
        assert w.current_tenant_id == "acme"
        await pool.release(w)
        assert w.status == WorkerStatus.IDLE

    @pytest.mark.asyncio
    async def test_tenant_limit_enforced(self, pool):
        pool.set_tenant_limit("acme", 1)
        w1 = await pool.acquire("acme")
        with pytest.raises(TimeoutError):
            await pool.acquire("acme", timeout=1.0)
        await pool.release(w1)

    @pytest.mark.asyncio
    async def test_multiple_tenants(self, pool):
        pool.set_tenant_limit("acme", 2)
        pool.set_tenant_limit("globex", 2)
        w1 = await pool.acquire("acme")
        w2 = await pool.acquire("globex")
        assert w1.current_tenant_id == "acme"
        assert w2.current_tenant_id == "globex"
        await pool.release(w1)
        await pool.release(w2)

    @pytest.mark.asyncio
    async def test_scale_up(self, pool):
        await pool.scale(3)
        assert pool.total_count == 3

    @pytest.mark.asyncio
    async def test_scale_down(self, pool):
        await pool.scale(4)
        await pool.scale(2)
        assert pool.total_count == 2

    @pytest.mark.asyncio
    async def test_health_check(self, pool):
        await pool.scale(3)
        health = await pool.health_check()
        assert health["total"] == 3
        assert health["healthy"] is True

    @pytest.mark.asyncio
    async def test_stats(self, pool):
        pool.set_tenant_limit("acme", 2)
        w = await pool.acquire("acme")
        stats = pool.get_stats()
        assert stats["busy"] == 1
        await pool.release(w)

    @pytest.mark.asyncio
    async def test_max_workers_enforced(self):
        pool = ResourcePool(ResourcePoolConfig(max_workers=2, min_workers=0))
        pool.set_tenant_limit("t1", 5)
        pool.set_tenant_limit("t2", 5)
        w1 = await pool.acquire("t1")
        w2 = await pool.acquire("t2")
        with pytest.raises(TimeoutError):
            await pool.acquire("t1", timeout=1.0)
        await pool.release(w1)
        await pool.release(w2)


# --- QuotaManager ---


class TestQuotaManager:
    @pytest.fixture
    def quota(self, tmp_path):
        store = QuotaStore(str(tmp_path / "quotas.db"))
        qm = QuotaManager(store)
        qm.configure("acme", "daily_tasks", 100)
        qm.configure("acme", "monthly_tasks", 2000)
        return qm

    @pytest.mark.asyncio
    async def test_check_quota(self, quota):
        check = await quota.check("acme", "daily_tasks")
        assert check.allowed is True
        assert check.limit == 100
        assert check.remaining == 100

    @pytest.mark.asyncio
    async def test_consume(self, quota):
        assert await quota.consume("acme", "daily_tasks", 1) is True
        check = await quota.check("acme", "daily_tasks")
        assert check.used == 1
        assert check.remaining == 99

    @pytest.mark.asyncio
    async def test_quota_exceeded(self, quota):
        quota.configure("acme", "tiny", 2)
        assert await quota.consume("acme", "tiny", 1) is True
        assert await quota.consume("acme", "tiny", 1) is True
        check = await quota.check("acme", "tiny")
        assert check.remaining == 0

    @pytest.mark.asyncio
    async def test_reset(self, quota):
        await quota.consume("acme", "daily_tasks", 50)
        await quota.reset("acme", "daily_tasks")
        check = await quota.check("acme", "daily_tasks")
        assert check.used == 0

    @pytest.mark.asyncio
    async def test_get_usage(self, quota):
        await quota.consume("acme", "daily_tasks", 5)
        usage = await quota.get_usage("acme")
        assert "daily_tasks" in usage
        assert usage["daily_tasks"].used == 5

    @pytest.mark.asyncio
    async def test_unknown_resource(self, quota):
        check = await quota.check("acme", "nonexistent")
        assert check.allowed is True  # No quota = unlimited


# --- MeteringEngine ---


class TestMeteringEngine:
    @pytest.fixture
    def metering(self, tmp_path):
        return MeteringEngine(MeteringStore(str(tmp_path / "metering.db")))

    @pytest.mark.asyncio
    async def test_record_task(self, metering):
        await metering.record_task("acme", task_id="t1", duration=42.5)
        now = datetime.now(timezone.utc)
        events = await metering.get_billable_events("acme", now - timedelta(days=1), now + timedelta(days=1))
        assert len(events) == 1
        assert events[0].event_type == "task"

    @pytest.mark.asyncio
    async def test_record_tokens(self, metering):
        await metering.record_tokens("acme", "gpt-4", 1000, 500)
        now = datetime.now(timezone.utc)
        events = await metering.get_billable_events("acme", now - timedelta(days=1), now + timedelta(days=1))
        assert any(e.event_type == "tokens" for e in events)

    @pytest.mark.asyncio
    async def test_generate_invoice(self, metering):
        await metering.record_task("acme", "t1")
        await metering.record_task("acme", "t2")
        await metering.record_tokens("acme", "gpt-4", 5000, 2000)

        now = datetime.now(timezone.utc)
        invoice = await metering.generate_invoice_data(
            "acme", now - timedelta(days=1), now + timedelta(days=1),
        )
        assert invoice.total_tasks == 2
        assert invoice.total_tokens == 7000
        assert invoice.total_cost > 0
        assert len(invoice.line_items) >= 2

    @pytest.mark.asyncio
    async def test_invoice_empty_period(self, metering):
        now = datetime.now(timezone.utc)
        invoice = await metering.generate_invoice_data(
            "acme", now - timedelta(days=30), now - timedelta(days=20),
        )
        assert invoice.total_tasks == 0
        assert invoice.total_cost == 0

    @pytest.mark.asyncio
    async def test_invoice_serialization(self, metering):
        await metering.record_task("acme", "t1")
        now = datetime.now(timezone.utc)
        invoice = await metering.generate_invoice_data("acme", now - timedelta(days=1), now + timedelta(days=1))
        d = invoice.to_dict()
        assert "total_cost" in d
        assert "line_items" in d


# --- FairScheduler ---


class TestFairScheduler:
    @pytest.fixture
    def scheduler(self, tmp_path):
        tm = TenantManager(TenantStore(str(tmp_path / "tenants.db")))
        pool = ResourcePool(ResourcePoolConfig(max_workers=10, min_workers=0))
        qm = QuotaManager(QuotaStore(str(tmp_path / "quotas.db")))
        return FairScheduler(tm, pool, qm)

    @pytest.mark.asyncio
    async def test_submit_task(self, scheduler, tmp_path):
        # Create tenant and quota
        tenant = await scheduler._tenant_mgr.create_tenant("Test", TenantPlan.ENTERPRISE)
        scheduler._quota.configure(tenant.tenant_id, "daily_tasks", 100)
        scheduler._quota.configure(tenant.tenant_id, "monthly_tasks", 1000)
        scheduler._pool.set_tenant_limit(tenant.tenant_id, 5)

        task = TenantTask(tenant_id=tenant.tenant_id, goal="Test task")
        task_id = await scheduler.submit(task)
        assert task_id is not None

    @pytest.mark.asyncio
    async def test_queue_stats(self, scheduler, tmp_path):
        tenant = await scheduler._tenant_mgr.create_tenant("Test", TenantPlan.ENTERPRISE)
        scheduler._quota.configure(tenant.tenant_id, "daily_tasks", 100)
        scheduler._quota.configure(tenant.tenant_id, "monthly_tasks", 1000)
        scheduler._pool.set_tenant_limit(tenant.tenant_id, 5)

        await scheduler.submit(TenantTask(tenant_id=tenant.tenant_id, goal="Task 1"))
        await scheduler.submit(TenantTask(tenant_id=tenant.tenant_id, goal="Task 2"))

        stats = await scheduler.get_queue_stats(tenant.tenant_id)
        assert stats.pending_tasks == 2

    @pytest.mark.asyncio
    async def test_cancel_task(self, scheduler, tmp_path):
        tenant = await scheduler._tenant_mgr.create_tenant("Test", TenantPlan.ENTERPRISE)
        scheduler._quota.configure(tenant.tenant_id, "daily_tasks", 100)
        scheduler._quota.configure(tenant.tenant_id, "monthly_tasks", 1000)

        task = TenantTask(tenant_id=tenant.tenant_id, goal="Cancel me")
        task_id = await scheduler.submit(task)
        assert await scheduler.cancel(task_id, tenant.tenant_id) is True

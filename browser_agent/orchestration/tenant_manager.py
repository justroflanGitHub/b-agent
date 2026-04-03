"""Tenant management — CRUD, isolation, and lifecycle."""

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class TenantPlan(Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class TenantStatus(Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    CLOSED = "closed"


@dataclass
class Tenant:
    """A single tenant with resource limits and feature flags."""
    tenant_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    plan: TenantPlan = TenantPlan.STARTER
    status: TenantStatus = TenantStatus.ACTIVE

    # Resource limits
    max_concurrent_tasks: int = 3
    max_daily_tasks: int = 100
    max_monthly_tasks: int = 2000
    max_browser_workers: int = 2
    max_task_timeout: float = 600.0
    max_steps_per_task: int = 50

    # Feature flags
    features: Dict[str, bool] = field(default_factory=lambda: {
        "credential_vault": True,
        "audit_log": True,
        "dlp": False,
        "scheduling": False,
        "recording": False,
        "governance": False,
    })

    # Isolation scopes
    credential_scope: str = ""
    audit_scope: str = ""
    data_scope: str = ""

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    owner_email: str = ""
    admin_emails: List[str] = field(default_factory=list)
    api_key_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.credential_scope:
            self.credential_scope = f"tenant_{self.tenant_id}"
        if not self.audit_scope:
            self.audit_scope = self.tenant_id
        if not self.data_scope:
            self.data_scope = self.tenant_id

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "plan": self.plan.value,
            "status": self.status.value,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "max_daily_tasks": self.max_daily_tasks,
            "max_monthly_tasks": self.max_monthly_tasks,
            "max_browser_workers": self.max_browser_workers,
            "max_task_timeout": self.max_task_timeout,
            "max_steps_per_task": self.max_steps_per_task,
            "features": self.features,
            "credential_scope": self.credential_scope,
            "audit_scope": self.audit_scope,
            "data_scope": self.data_scope,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "owner_email": self.owner_email,
            "admin_emails": self.admin_emails,
            "api_key_hash": self.api_key_hash,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Tenant":
        return cls(
            tenant_id=data.get("tenant_id", str(uuid.uuid4())),
            name=data.get("name", ""),
            plan=TenantPlan(data.get("plan", "starter")),
            status=TenantStatus(data.get("status", "active")),
            max_concurrent_tasks=data.get("max_concurrent_tasks", 3),
            max_daily_tasks=data.get("max_daily_tasks", 100),
            max_monthly_tasks=data.get("max_monthly_tasks", 2000),
            max_browser_workers=data.get("max_browser_workers", 2),
            max_task_timeout=data.get("max_task_timeout", 600.0),
            max_steps_per_task=data.get("max_steps_per_task", 50),
            features=data.get("features", {}),
            credential_scope=data.get("credential_scope", ""),
            audit_scope=data.get("audit_scope", ""),
            data_scope=data.get("data_scope", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(timezone.utc),
            owner_email=data.get("owner_email", ""),
            admin_emails=data.get("admin_emails", []),
            api_key_hash=data.get("api_key_hash", ""),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def with_plan(cls, plan: TenantPlan, **kwargs) -> "Tenant":
        """Create tenant with plan-default limits."""
        defaults = {
            TenantPlan.FREE: dict(max_concurrent_tasks=1, max_daily_tasks=10, max_monthly_tasks=100, max_browser_workers=1, features={"credential_vault": False, "audit_log": False, "dlp": False, "scheduling": False, "recording": False, "governance": False}),
            TenantPlan.STARTER: dict(max_concurrent_tasks=2, max_daily_tasks=50, max_monthly_tasks=1000, max_browser_workers=1),
            TenantPlan.PROFESSIONAL: dict(max_concurrent_tasks=5, max_daily_tasks=500, max_monthly_tasks=10000, max_browser_workers=3, features={"credential_vault": True, "audit_log": True, "dlp": True, "scheduling": True, "recording": False, "governance": True}),
            TenantPlan.ENTERPRISE: dict(max_concurrent_tasks=20, max_daily_tasks=5000, max_monthly_tasks=100000, max_browser_workers=10, features={"credential_vault": True, "audit_log": True, "dlp": True, "scheduling": True, "recording": True, "governance": True}),
        }
        merged = {**defaults.get(plan, {}), **kwargs}
        return cls(plan=plan, **merged)


class TenantStore:
    """SQLite storage for tenants."""

    def __init__(self, path: str = ".orchestration/tenants.db"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._path = path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self._path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                status TEXT NOT NULL,
                plan TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tenant_status ON tenants(status)")
        conn.commit()
        conn.close()

    async def save(self, tenant: Tenant) -> str:
        conn = sqlite3.connect(self._path)
        conn.execute(
            "INSERT OR REPLACE INTO tenants VALUES (?,?,?,?,?)",
            (tenant.tenant_id, json.dumps(tenant.to_dict()), tenant.status.value, tenant.plan.value, tenant.created_at.isoformat()),
        )
        conn.commit()
        conn.close()
        return tenant.tenant_id

    async def load(self, tenant_id: str) -> Optional[Tenant]:
        conn = sqlite3.connect(self._path)
        cursor = conn.execute("SELECT data FROM tenants WHERE tenant_id=?", (tenant_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return Tenant.from_dict(json.loads(row[0]))

    async def load_by_api_key(self, api_key: str) -> Optional[Tenant]:
        """Find tenant by API key (simple hash comparison)."""
        import hashlib
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        conn = sqlite3.connect(self._path)
        cursor = conn.execute("SELECT data FROM tenants")
        for row in cursor.fetchall():
            t = Tenant.from_dict(json.loads(row[0]))
            if t.api_key_hash == key_hash:
                conn.close()
                return t
        conn.close()
        return None

    async def delete(self, tenant_id: str) -> bool:
        conn = sqlite3.connect(self._path)
        cursor = conn.execute("DELETE FROM tenants WHERE tenant_id=?", (tenant_id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    async def list_all(self, status: Optional[TenantStatus] = None) -> List[Tenant]:
        conn = sqlite3.connect(self._path)
        if status:
            cursor = conn.execute("SELECT data FROM tenants WHERE status=?", (status.value,))
        else:
            cursor = conn.execute("SELECT data FROM tenants")
        rows = cursor.fetchall()
        conn.close()
        return [Tenant.from_dict(json.loads(r[0])) for r in rows]


class TenantManager:
    """Manage multi-tenant lifecycle."""

    def __init__(self, store: Optional[TenantStore] = None):
        self._store = store or TenantStore()

    async def create_tenant(self, name: str, plan: TenantPlan = TenantPlan.STARTER,
                            owner_email: str = "", **kwargs) -> Tenant:
        tenant = Tenant.with_plan(plan, name=name, owner_email=owner_email, **kwargs)
        await self._store.save(tenant)
        return tenant

    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        return await self._store.load(tenant_id)

    async def update_tenant(self, tenant_id: str, updates: Dict[str, Any]) -> Optional[Tenant]:
        tenant = await self._store.load(tenant_id)
        if not tenant:
            return None
        for k, v in updates.items():
            if k == "plan" and isinstance(v, str):
                v = TenantPlan(v)
            if k == "status" and isinstance(v, str):
                v = TenantStatus(v)
            if hasattr(tenant, k):
                setattr(tenant, k, v)
        tenant.updated_at = datetime.now(timezone.utc)
        await self._store.save(tenant)
        return tenant

    async def suspend_tenant(self, tenant_id: str, reason: str = "") -> bool:
        tenant = await self._store.load(tenant_id)
        if not tenant:
            return False
        tenant.status = TenantStatus.SUSPENDED
        tenant.metadata["suspension_reason"] = reason
        tenant.updated_at = datetime.now(timezone.utc)
        await self._store.save(tenant)
        return True

    async def activate_tenant(self, tenant_id: str) -> bool:
        tenant = await self._store.load(tenant_id)
        if not tenant:
            return False
        tenant.status = TenantStatus.ACTIVE
        tenant.updated_at = datetime.now(timezone.utc)
        await self._store.save(tenant)
        return True

    async def delete_tenant(self, tenant_id: str) -> bool:
        return await self._store.delete(tenant_id)

    async def list_tenants(self, status: Optional[TenantStatus] = None) -> List[Tenant]:
        return await self._store.list_all(status)

    async def validate_access(self, tenant_id: str, api_key: str) -> bool:
        tenant = await self._store.load(tenant_id)
        if not tenant or tenant.status != TenantStatus.ACTIVE:
            return False
        import hashlib
        return tenant.api_key_hash == hashlib.sha256(api_key.encode()).hexdigest()

    async def set_api_key(self, tenant_id: str, api_key: str) -> bool:
        tenant = await self._store.load(tenant_id)
        if not tenant:
            return False
        import hashlib
        tenant.api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        tenant.updated_at = datetime.now(timezone.utc)
        await self._store.save(tenant)
        return True

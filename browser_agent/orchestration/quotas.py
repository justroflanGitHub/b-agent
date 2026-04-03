"""Quota tracking and enforcement per tenant."""

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class QuotaCheck:
    allowed: bool
    resource: str
    limit: int
    used: int
    remaining: int
    reset_at: Optional[datetime] = None


@dataclass
class UsageRecord:
    resource: str
    used: int
    limit: int
    period: str
    reset_at: Optional[datetime] = None


class QuotaStore:
    """SQLite storage for quota tracking."""

    def __init__(self, path: str = ".orchestration/quotas.db"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._path = path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self._path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quotas (
                tenant_id TEXT NOT NULL,
                resource TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                limit_val INTEGER DEFAULT 0,
                period TEXT DEFAULT 'daily',
                reset_at TEXT,
                PRIMARY KEY (tenant_id, resource)
            )
        """)
        conn.commit()
        conn.close()

    def _get_conn(self):
        return sqlite3.connect(self._path)

    def get(self, tenant_id: str, resource: str) -> Optional[dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT used, limit_val, period, reset_at FROM quotas WHERE tenant_id=? AND resource=?",
            (tenant_id, resource),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {"used": row[0], "limit": row[1], "period": row[2], "reset_at": row[3]}

    def set(self, tenant_id: str, resource: str, limit: int, period: str = "daily"):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO quotas (tenant_id, resource, used, limit_val, period, reset_at) VALUES (?,?,?,?,?,?)",
            (tenant_id, resource, 0, limit, period, None),
        )
        conn.commit()
        conn.close()

    def increment(self, tenant_id: str, resource: str, amount: int = 1) -> Optional[int]:
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE quotas SET used = used + ? WHERE tenant_id=? AND resource=?",
            (amount, tenant_id, resource),
        )
        conn.commit()
        if cursor.rowcount == 0:
            conn.close()
            return None
        # Get updated value
        cursor = conn.execute(
            "SELECT used FROM quotas WHERE tenant_id=? AND resource=?",
            (tenant_id, resource),
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def reset(self, tenant_id: str, resource: str):
        conn = self._get_conn()
        conn.execute(
            "UPDATE quotas SET used=0, reset_at=? WHERE tenant_id=? AND resource=?",
            (datetime.now(timezone.utc).isoformat(), tenant_id, resource),
        )
        conn.commit()
        conn.close()

    def get_all(self, tenant_id: str) -> List[dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT resource, used, limit_val, period, reset_at FROM quotas WHERE tenant_id=?",
            (tenant_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"resource": r[0], "used": r[1], "limit": r[2], "period": r[3], "reset_at": r[4]}
            for r in rows
        ]


class QuotaManager:
    """Track and enforce resource quotas per tenant."""

    def __init__(self, store: Optional[QuotaStore] = None):
        self._store = store or QuotaStore()

    def configure(self, tenant_id: str, resource: str, limit: int, period: str = "daily"):
        """Set quota for a tenant resource."""
        self._store.set(tenant_id, resource, limit, period)

    async def check(self, tenant_id: str, resource: str) -> QuotaCheck:
        """Check if tenant has quota remaining."""
        record = self._store.get(tenant_id, resource)
        if record is None:
            return QuotaCheck(allowed=True, resource=resource, limit=-1, used=0, remaining=-1)

        remaining = max(record["limit"] - record["used"], 0)
        reset_at = datetime.fromisoformat(record["reset_at"]) if record.get("reset_at") else None
        return QuotaCheck(
            allowed=remaining > 0,
            resource=resource,
            limit=record["limit"],
            used=record["used"],
            remaining=remaining,
            reset_at=reset_at,
        )

    async def consume(self, tenant_id: str, resource: str, amount: int = 1) -> bool:
        """Consume quota. Returns False if quota exceeded (still increments)."""
        check = await self.check(tenant_id, resource)
        if check.limit >= 0 and check.remaining < amount:
            return False
        self._store.increment(tenant_id, resource, amount)
        return True

    async def reset(self, tenant_id: str, resource: str):
        """Reset quota for a resource."""
        self._store.reset(tenant_id, resource)

    async def get_usage(self, tenant_id: str) -> Dict[str, UsageRecord]:
        """Get current usage for all resources."""
        records = self._store.get_all(tenant_id)
        return {
            r["resource"]: UsageRecord(
                resource=r["resource"],
                used=r["used"],
                limit=r["limit"],
                period=r["period"],
                reset_at=datetime.fromisoformat(r["reset_at"]) if r.get("reset_at") else None,
            )
            for r in records
        }

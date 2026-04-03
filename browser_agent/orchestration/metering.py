"""Usage metering for billing integration."""

import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BillableEvent:
    """A single billable event."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    event_type: str = ""        # "task", "tokens", "actions"
    quantity: int = 1
    unit: str = ""              # "task", "1k_tokens", "100_actions"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "event_type": self.event_type,
            "quantity": self.quantity,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class InvoiceLineItem:
    description: str = ""
    quantity: int = 0
    unit_price: float = 0.0
    total: float = 0.0


@dataclass
class InvoiceData:
    tenant_id: str = ""
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    line_items: List[InvoiceLineItem] = field(default_factory=list)
    total_tasks: int = 0
    total_tokens: int = 0
    total_actions: int = 0
    total_cost: float = 0.0

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "line_items": [{"description": i.description, "quantity": i.quantity, "unit_price": i.unit_price, "total": i.total} for i in self.line_items],
            "total_tasks": self.total_tasks,
            "total_tokens": self.total_tokens,
            "total_actions": self.total_actions,
            "total_cost": self.total_cost,
        }


class MeteringStore:
    """SQLite storage for metering events."""

    def __init__(self, path: str = ".orchestration/metering.db"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._path = path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self._path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS billable_events (
                event_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                unit TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_metering_tenant ON billable_events(tenant_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_metering_type ON billable_events(event_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_metering_ts ON billable_events(timestamp)")
        conn.commit()
        conn.close()

    async def save(self, event: BillableEvent) -> str:
        conn = sqlite3.connect(self._path)
        conn.execute(
            "INSERT INTO billable_events VALUES (?,?,?,?,?,?,?)",
            (event.event_id, event.tenant_id, event.event_type, event.quantity,
             event.unit, event.timestamp.isoformat(), json.dumps(event.metadata)),
        )
        conn.commit()
        conn.close()
        return event.event_id

    async def query(self, tenant_id: str, start: datetime, end: datetime,
                    event_type: Optional[str] = None) -> List[BillableEvent]:
        conn = sqlite3.connect(self._path)
        if event_type:
            cursor = conn.execute(
                "SELECT * FROM billable_events WHERE tenant_id=? AND timestamp>=? AND timestamp<=? AND event_type=?",
                (tenant_id, start.isoformat(), end.isoformat(), event_type),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM billable_events WHERE tenant_id=? AND timestamp>=? AND timestamp<=?",
                (tenant_id, start.isoformat(), end.isoformat()),
            )
        rows = cursor.fetchall()
        conn.close()
        return [BillableEvent(
            event_id=r[0], tenant_id=r[1], event_type=r[2],
            quantity=r[3], unit=r[4],
            timestamp=datetime.fromisoformat(r[5]),
            metadata=json.loads(r[6]),
        ) for r in rows]

    async def summarize(self, tenant_id: str, start: datetime, end: datetime) -> Dict[str, int]:
        """Sum quantities by event type."""
        events = await self.query(tenant_id, start, end)
        summary: Dict[str, int] = {}
        for e in events:
            summary[e.event_type] = summary.get(e.event_type, 0) + e.quantity
        return summary


class MeteringEngine:
    """Usage metering for billing integration."""

    def __init__(self, store: Optional[MeteringStore] = None,
                 pricing: Optional[Dict[str, float]] = None):
        self._store = store or MeteringStore()
        self._pricing = pricing or {
            "task": 0.10,
            "1k_tokens": 0.002,
            "100_actions": 0.05,
        }

    async def record_task(self, tenant_id: str, task_id: str = "",
                          duration: float = 0, success: bool = True):
        """Record task execution."""
        event = BillableEvent(
            tenant_id=tenant_id,
            event_type="task",
            quantity=1,
            unit="task",
            metadata={"task_id": task_id, "duration": duration, "success": success},
        )
        await self._store.save(event)

    async def record_tokens(self, tenant_id: str, model: str,
                            prompt_tokens: int, completion_tokens: int):
        """Record LLM token usage."""
        total = prompt_tokens + completion_tokens
        event = BillableEvent(
            tenant_id=tenant_id,
            event_type="tokens",
            quantity=total,
            unit="tokens",
            metadata={"model": model, "prompt": prompt_tokens, "completion": completion_tokens},
        )
        await self._store.save(event)

    async def record_actions(self, tenant_id: str, action_count: int):
        """Record action count."""
        event = BillableEvent(
            tenant_id=tenant_id,
            event_type="actions",
            quantity=action_count,
            unit="actions",
        )
        await self._store.save(event)

    async def get_billable_events(self, tenant_id: str, start: datetime,
                                  end: datetime) -> List[BillableEvent]:
        return await self._store.query(tenant_id, start, end)

    async def generate_invoice_data(self, tenant_id: str, period_start: datetime,
                                    period_end: datetime) -> InvoiceData:
        """Generate invoice data for a billing period."""
        summary = await self._store.summarize(tenant_id, period_start, period_end)

        invoice = InvoiceData(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
        )

        if "task" in summary:
            qty = summary["task"]
            price = self._pricing.get("task", 0.10)
            invoice.line_items.append(InvoiceLineItem(
                description="Task executions", quantity=qty,
                unit_price=price, total=qty * price,
            ))
            invoice.total_tasks = qty
            invoice.total_cost += qty * price

        if "tokens" in summary:
            qty_1k = summary["tokens"] / 1000
            price = self._pricing.get("1k_tokens", 0.002)
            invoice.line_items.append(InvoiceLineItem(
                description="LLM tokens (per 1K)", quantity=int(qty_1k),
                unit_price=price, total=qty_1k * price,
            ))
            invoice.total_tokens = summary["tokens"]
            invoice.total_cost += qty_1k * price

        if "actions" in summary:
            qty_100 = summary["actions"] / 100
            price = self._pricing.get("100_actions", 0.05)
            invoice.line_items.append(InvoiceLineItem(
                description="Browser actions (per 100)", quantity=int(qty_100),
                unit_price=price, total=qty_100 * price,
            ))
            invoice.total_actions = summary["actions"]
            invoice.total_cost += qty_100 * price

        return invoice

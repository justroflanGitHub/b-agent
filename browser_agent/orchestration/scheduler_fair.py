"""Fair-share scheduler across tenants."""

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .tenant_manager import TenantManager, Tenant
from .resource_pool import ResourcePool
from .quotas import QuotaManager

logger = logging.getLogger(__name__)


@dataclass
class TenantTask:
    """Task scoped to a tenant."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "default"
    goal: str = ""
    start_url: Optional[str] = None
    priority: int = 0
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_by: str = "system"
    credential_aliases: Optional[Dict[str, str]] = None
    config_overrides: Dict[str, Any] = field(default_factory=dict)
    scheduled_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    status: str = "queued"  # queued, running, completed, failed, cancelled

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "goal": self.goal,
            "start_url": self.start_url,
            "priority": self.priority,
            "submitted_at": self.submitted_at.isoformat(),
            "submitted_by": self.submitted_by,
            "status": self.status,
        }


@dataclass
class TenantQueueStats:
    tenant_id: str
    pending_tasks: int = 0
    running_tasks: int = 0
    completed_today: int = 0
    quota_remaining: Dict[str, int] = field(default_factory=dict)
    avg_wait_time: float = 0.0
    avg_execution_time: float = 0.0


class FairScheduler:
    """Fair-share scheduler across tenants.

    Round-robin with priority within each tenant's queue.
    Respects tenant resource limits and quotas.
    """

    def __init__(
        self,
        tenant_manager: TenantManager,
        resource_pool: ResourcePool,
        quota_manager: QuotaManager,
        agent_factory: Optional[Callable] = None,
    ):
        self._tenant_mgr = tenant_manager
        self._pool = resource_pool
        self._quota = quota_manager
        self._agent_factory = agent_factory
        self._queues: Dict[str, List[TenantTask]] = defaultdict(list)
        self._running: Dict[str, TenantTask] = {}
        self._lock = asyncio.Lock()
        self._running_flag = False
        self._rr_index = 0

    async def submit(self, task: TenantTask) -> str:
        """Submit task to tenant's queue."""
        # Check quota
        can_run = await self._quota.consume(task.tenant_id, "daily_tasks", 0)  # Just check
        if not can_run:
            allowed = await self._quota.check(task.tenant_id, "daily_tasks")
            if allowed and allowed.remaining <= 0:
                raise ValueError(f"Tenant {task.tenant_id} daily task quota exceeded")

        async with self._lock:
            self._queues[task.tenant_id].append(task)
            # Sort by priority (higher first)
            self._queues[task.tenant_id].sort(key=lambda t: -t.priority)

        logger.info("Task submitted: %s tenant=%s goal=%s", task.task_id, task.tenant_id, task.goal[:50])
        return task.task_id

    async def cancel(self, task_id: str, tenant_id: str) -> bool:
        """Cancel a queued or running task."""
        async with self._lock:
            # Check queue
            queue = self._queues.get(tenant_id, [])
            for i, t in enumerate(queue):
                if t.task_id == task_id:
                    t.status = "cancelled"
                    queue.pop(i)
                    return True
            # Check running
            if task_id in self._running:
                self._running[task_id].status = "cancelled"
                return True
        return False

    async def get_position(self, task_id: str) -> int:
        """Get task position in queue."""
        async with self._lock:
            for queue in self._queues.values():
                for i, t in enumerate(queue):
                    if t.task_id == task_id:
                        return i
        return -1

    async def start(self):
        """Start scheduler loop."""
        self._running_flag = True
        logger.info("Fair scheduler started")
        while self._running_flag:
            try:
                await self._dispatch_cycle()
            except Exception as e:
                logger.error("Scheduler error: %s", e)
            await asyncio.sleep(2)

    async def stop(self):
        self._running_flag = False

    async def get_queue_stats(self, tenant_id: str) -> TenantQueueStats:
        """Get queue statistics for a tenant."""
        queue = self._queues.get(tenant_id, [])
        running = sum(1 for t in self._running.values() if t.tenant_id == tenant_id)
        quota = await self._quota.check(tenant_id, "daily_tasks")
        return TenantQueueStats(
            tenant_id=tenant_id,
            pending_tasks=len(queue),
            running_tasks=running,
            quota_remaining={"daily_tasks": quota.remaining if quota else -1},
        )

    async def _dispatch_cycle(self):
        """One round of fair dispatch."""
        async with self._lock:
            tenants = list(self._queues.keys())
            if not tenants:
                return

            # Round-robin across tenants
            dispatched = 0
            for _ in range(len(tenants)):
                if self._rr_index >= len(tenants):
                    self._rr_index = 0
                tenant_id = tenants[self._rr_index]
                self._rr_index += 1

                queue = self._queues.get(tenant_id, [])
                if not queue:
                    continue

                # Check tenant limits
                tenant = await self._tenant_mgr.get_tenant(tenant_id)
                if not tenant or tenant.status.value != "active":
                    continue

                running_count = sum(1 for t in self._running.values() if t.tenant_id == tenant_id)
                if running_count >= tenant.max_concurrent_tasks:
                    continue

                # Check quota
                quota_ok = await self._quota.consume(tenant_id, "daily_tasks", 1)
                if not quota_ok:
                    continue

                task = queue.pop(0)
                task.status = "running"
                self._running[task.task_id] = task

                # Dispatch (fire and forget — release happens via completion)
                asyncio.create_task(self._execute_task(task))
                dispatched += 1

    async def _execute_task(self, task: TenantTask):
        """Execute a task using the resource pool."""
        start = time.monotonic()
        try:
            worker = await self._pool.acquire(task.tenant_id, timeout=30)
            worker.current_task_id = task.task_id

            try:
                if self._agent_factory:
                    agent = self._agent_factory()
                    result = await agent.execute_task(
                        goal=task.goal,
                        start_url=task.start_url,
                        credential_aliases=task.credential_aliases,
                    )
                    task.status = "completed" if result.success else "failed"
                else:
                    # Testing mode — simulate
                    task.status = "completed"
            finally:
                await self._pool.release(worker)

        except Exception as e:
            task.status = "failed"
            logger.error("Task %s failed: %s", task.task_id, e)

        finally:
            async with self._lock:
                self._running.pop(task.task_id, None)

            # Consume monthly quota
            await self._quota.consume(task.tenant_id, "monthly_tasks", 1)

            logger.info("Task %s: %s in %.1fs", task.task_id, task.status, time.monotonic() - start)

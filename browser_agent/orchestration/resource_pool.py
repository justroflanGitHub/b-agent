"""Resource pool — managed browser worker pool with tenant-aware allocation."""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkerStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    INITIALIZING = "initializing"
    ERROR = "error"
    DRAINING = "draining"


@dataclass
class BrowserWorker:
    """A browser instance available for task execution."""
    worker_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    browser_type: str = "chromium"
    status: WorkerStatus = WorkerStatus.IDLE
    current_task_id: Optional[str] = None
    current_tenant_id: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_tasks_completed: int = 0
    error_count: int = 0

    @property
    def is_available(self) -> bool:
        return self.status == WorkerStatus.IDLE

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "status": self.status.value,
            "current_task_id": self.current_task_id,
            "current_tenant_id": self.current_tenant_id,
            "started_at": self.started_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "total_tasks_completed": self.total_tasks_completed,
        }


@dataclass
class ResourcePoolConfig:
    min_workers: int = 2
    max_workers: int = 20
    idle_timeout: float = 300.0
    health_check_interval: float = 60.0
    browser_type: str = "chromium"
    headless: bool = True


class ResourcePool:
    """Pool of browser workers for multi-tenant task execution.

    Manages worker lifecycle, allocation, and release.
    Enforces per-tenant worker limits.
    """

    def __init__(self, config: Optional[ResourcePoolConfig] = None):
        self._config = config or ResourcePoolConfig()
        self._workers: Dict[str, BrowserWorker] = {}
        self._lock = asyncio.Lock()
        self._tenant_limits: Dict[str, int] = {}  # tenant_id → max workers

    def set_tenant_limit(self, tenant_id: str, max_workers: int):
        """Set max concurrent workers for a tenant."""
        self._tenant_limits[tenant_id] = max_workers

    async def acquire(self, tenant_id: str, timeout: float = 30.0) -> BrowserWorker:
        """Acquire a worker for a tenant.

        Respects tenant max_workers limit. Creates new worker if pool has capacity.
        Waits if no workers available.
        """
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            async with self._lock:
                # Try to find idle worker
                for w in self._workers.values():
                    if w.is_available:
                        # Check tenant limit
                        if self._tenant_count(tenant_id) >= self._tenant_limits.get(tenant_id, 2):
                            continue
                        w.status = WorkerStatus.BUSY
                        w.current_tenant_id = tenant_id
                        w.last_activity = datetime.now(timezone.utc)
                        logger.debug("Acquired existing worker %s for tenant %s", w.worker_id, tenant_id)
                        return w

                # Try to create new worker
                if len(self._workers) < self._config.max_workers:
                    if self._tenant_count(tenant_id) < self._tenant_limits.get(tenant_id, 2):
                        worker = BrowserWorker(
                            status=WorkerStatus.BUSY,
                            current_tenant_id=tenant_id,
                            browser_type=self._config.browser_type,
                        )
                        self._workers[worker.worker_id] = worker
                        logger.debug("Created new worker %s for tenant %s", worker.worker_id, tenant_id)
                        return worker

            await asyncio.sleep(0.5)

        raise TimeoutError(f"No worker available for tenant {tenant_id} within {timeout}s")

    async def release(self, worker: BrowserWorker):
        """Release worker back to pool."""
        async with self._lock:
            worker.status = WorkerStatus.IDLE
            worker.current_task_id = None
            worker.current_tenant_id = None
            worker.last_activity = datetime.now(timezone.utc)
            worker.total_tasks_completed += 1
            logger.debug("Released worker %s", worker.worker_id)

    async def drain(self, worker_id: str):
        """Gracefully drain a worker."""
        async with self._lock:
            w = self._workers.get(worker_id)
            if w:
                w.status = WorkerStatus.DRAINING

    async def remove_worker(self, worker_id: str):
        """Remove a worker from the pool."""
        async with self._lock:
            self._workers.pop(worker_id, None)

    async def scale(self, target_size: int):
        """Scale pool to target size (add/remove idle workers)."""
        async with self._lock:
            current = len(self._workers)
            if target_size > current:
                for _ in range(target_size - current):
                    w = BrowserWorker(browser_type=self._config.browser_type)
                    self._workers[w.worker_id] = w
                logger.info("Scaled pool up: %d → %d", current, target_size)
            elif target_size < current:
                idle = [w for w in self._workers.values() if w.is_available]
                to_remove = min(len(idle), current - target_size)
                for w in idle[:to_remove]:
                    del self._workers[w.worker_id]
                logger.info("Scaled pool down: %d → %d", current, current - to_remove)

    async def health_check(self) -> dict:
        """Check health of all workers."""
        total = len(self._workers)
        idle = sum(1 for w in self._workers.values() if w.is_available)
        busy = sum(1 for w in self._workers.values() if w.status == WorkerStatus.BUSY)
        errors = sum(1 for w in self._workers.values() if w.status == WorkerStatus.ERROR)
        return {
            "total": total,
            "idle": idle,
            "busy": busy,
            "errors": errors,
            "healthy": total > 0 and errors < total,
        }

    async def cleanup_idle(self):
        """Remove workers idle beyond timeout."""
        now = datetime.now(timezone.utc)
        async with self._lock:
            to_remove = []
            for wid, w in self._workers.items():
                if w.is_available:
                    age = (now - w.last_activity).total_seconds()
                    if age > self._config.idle_timeout and len(self._workers) - len(to_remove) > self._config.min_workers:
                        to_remove.append(wid)
            for wid in to_remove:
                del self._workers[wid]
            if to_remove:
                logger.info("Cleaned up %d idle workers", len(to_remove))

    @property
    def idle_count(self) -> int:
        return sum(1 for w in self._workers.values() if w.is_available)

    @property
    def total_count(self) -> int:
        return len(self._workers)

    def _tenant_count(self, tenant_id: str) -> int:
        return sum(1 for w in self._workers.values()
                   if w.current_tenant_id == tenant_id and w.status == WorkerStatus.BUSY)

    def get_stats(self) -> dict:
        return {
            "total": self.total_count,
            "idle": self.idle_count,
            "busy": sum(1 for w in self._workers.values() if w.status == WorkerStatus.BUSY),
            "tenants": list(set(w.current_tenant_id for w in self._workers.values() if w.current_tenant_id)),
        }

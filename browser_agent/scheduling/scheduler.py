"""Task scheduler — cron-like scheduler for recurring browser automation."""

import asyncio
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .cron_schedule import CronSchedule
from .recurring_task import RecurringTask, TaskRun

logger = logging.getLogger(__name__)


class ScheduleStore:
    """SQLite storage for scheduled tasks and runs."""

    def __init__(self, path: str = ".scheduling/schedules.db"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._path = path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self._path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                task_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                tenant_id TEXT DEFAULT 'default',
                next_run TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_runs (
                run_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                result TEXT,
                checkpoint_used TEXT,
                error TEXT,
                duration REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_task ON task_runs(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON task_runs(status)")
        conn.commit()
        conn.close()

    async def save_task(self, task: RecurringTask) -> str:
        conn = sqlite3.connect(self._path)
        conn.execute(
            "INSERT OR REPLACE INTO scheduled_tasks VALUES (?,?,?,?,?,?)",
            (
                task.task_id, json.dumps(task.to_dict()),
                1 if task.enabled else 0, task.tenant_id,
                task.next_run.isoformat() if task.next_run else None,
                task.created_at.isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return task.task_id

    async def load_task(self, task_id: str) -> Optional[RecurringTask]:
        conn = sqlite3.connect(self._path)
        cursor = conn.execute("SELECT data FROM scheduled_tasks WHERE task_id=?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return RecurringTask.from_dict(json.loads(row[0]))

    async def delete_task(self, task_id: str) -> bool:
        conn = sqlite3.connect(self._path)
        cursor = conn.execute("DELETE FROM scheduled_tasks WHERE task_id=?", (task_id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    async def list_tasks(self, tenant_id: Optional[str] = None, enabled_only: bool = False) -> List[RecurringTask]:
        conn = sqlite3.connect(self._path)
        if tenant_id and enabled_only:
            cursor = conn.execute(
                "SELECT data FROM scheduled_tasks WHERE tenant_id=? AND enabled=1",
                (tenant_id,),
            )
        elif tenant_id:
            cursor = conn.execute(
                "SELECT data FROM scheduled_tasks WHERE tenant_id=?", (tenant_id,),
            )
        elif enabled_only:
            cursor = conn.execute("SELECT data FROM scheduled_tasks WHERE enabled=1")
        else:
            cursor = conn.execute("SELECT data FROM scheduled_tasks")
        rows = cursor.fetchall()
        conn.close()
        return [RecurringTask.from_dict(json.loads(r[0])) for r in rows]

    async def save_run(self, run: TaskRun) -> str:
        conn = sqlite3.connect(self._path)
        conn.execute(
            "INSERT OR REPLACE INTO task_runs VALUES (?,?,?,?,?,?,?,?,?)",
            (
                run.run_id, run.task_id, run.started_at.isoformat(),
                run.completed_at.isoformat() if run.completed_at else None,
                run.status,
                json.dumps(run.result) if run.result else None,
                run.checkpoint_used, run.error, run.duration,
            ),
        )
        conn.commit()
        conn.close()
        return run.run_id

    async def get_run_history(self, task_id: str, limit: int = 50) -> List[TaskRun]:
        conn = sqlite3.connect(self._path)
        cursor = conn.execute(
            "SELECT * FROM task_runs WHERE task_id=? ORDER BY started_at DESC LIMIT ?",
            (task_id, limit),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_run(r) for r in rows]

    async def get_run(self, run_id: str) -> Optional[TaskRun]:
        conn = sqlite3.connect(self._path)
        cursor = conn.execute("SELECT * FROM task_runs WHERE run_id=?", (run_id,))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_run(row) if row else None

    def _row_to_run(self, row: tuple) -> TaskRun:
        return TaskRun(
            run_id=row[0], task_id=row[1],
            started_at=datetime.fromisoformat(row[2]),
            completed_at=datetime.fromisoformat(row[3]) if row[3] else None,
            status=row[4],
            result=json.loads(row[5]) if row[5] else None,
            checkpoint_used=row[6],
            error=row[7],
            duration=row[8],
        )


class TaskScheduler:
    """Cron-like scheduler for recurring browser automation tasks.

    Usage:
        scheduler = TaskScheduler(agent_factory=my_agent_factory)
        await scheduler.register(task)
        await scheduler.start()  # Starts the scheduling loop
    """

    def __init__(
        self,
        agent_factory: Optional[Callable] = None,
        store: Optional[ScheduleStore] = None,
        check_interval: int = 60,
        max_concurrent: int = 5,
    ):
        self._agent_factory = agent_factory
        self._store = store or ScheduleStore()
        self._check_interval = check_interval
        self._max_concurrent = max_concurrent
        self._running = False
        self._active_runs: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def register(self, task: RecurringTask) -> str:
        """Register a new recurring task."""
        task.compute_next_run()
        await self._store.save_task(task)
        logger.info("Registered task: %s (%s) next_run=%s",
                     task.name, task.task_id, task.next_run)
        return task.task_id

    async def unregister(self, task_id: str) -> bool:
        """Unregister a recurring task."""
        result = await self._store.delete_task(task_id)
        if result:
            logger.info("Unregistered task: %s", task_id)
        return result

    async def update(self, task_id: str, updates: Dict[str, Any]) -> Optional[RecurringTask]:
        """Update task schedule or parameters."""
        task = await self._store.load_task(task_id)
        if not task:
            return None

        for key, value in updates.items():
            if key == "schedule" and isinstance(value, str):
                task.schedule = CronSchedule(expression=value)
            elif key == "goal":
                task.goal = value
            elif key == "enabled":
                task.enabled = value
            elif key == "start_url":
                task.start_url = value
            elif key == "max_steps":
                task.max_steps = value
            elif key == "timeout":
                task.timeout = value
            elif hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.now(timezone.utc)
        task.compute_next_run()
        await self._store.save_task(task)
        return task

    async def trigger(self, task_id: str) -> TaskRun:
        """Manually trigger a task run (outside schedule)."""
        task = await self._store.load_task(task_id)
        if not task:
            raise KeyError(f"Task not found: {task_id}")
        return await self._execute_task(task)

    async def start(self):
        """Start the scheduler loop."""
        self._running = True
        logger.info("Scheduler started (check_interval=%ds, max_concurrent=%d)",
                     self._check_interval, self._max_concurrent)

        while self._running:
            try:
                await self._check_and_dispatch()
            except Exception as e:
                logger.error("Scheduler error: %s", e)
            await asyncio.sleep(self._check_interval)

    async def stop(self):
        """Gracefully stop scheduler."""
        self._running = False
        # Wait for active runs
        if self._active_runs:
            logger.info("Waiting for %d active runs...", len(self._active_runs))
            await asyncio.gather(*self._active_runs.values(), return_exceptions=True)
        logger.info("Scheduler stopped")

    async def list_tasks(self, tenant_id: Optional[str] = None, enabled_only: bool = False) -> List[RecurringTask]:
        """List registered tasks."""
        return await self._store.list_tasks(tenant_id, enabled_only)

    async def get_task(self, task_id: str) -> Optional[RecurringTask]:
        """Get a specific task."""
        return await self._store.load_task(task_id)

    async def get_run_history(self, task_id: str, limit: int = 50) -> List[TaskRun]:
        """Get execution history for a task."""
        return await self._store.get_run_history(task_id, limit)

    async def get_run(self, run_id: str) -> Optional[TaskRun]:
        """Get a specific run."""
        return await self._store.get_run(run_id)

    async def _check_and_dispatch(self):
        """Check for due tasks and dispatch them."""
        now = datetime.now(timezone.utc)
        tasks = await self._store.list_tasks(enabled_only=True)

        for task in tasks:
            if task.next_run and task.next_run <= now:
                if task.task_id not in self._active_runs:
                    run_task = asyncio.create_task(
                        self._run_with_semaphore(task)
                    )
                    self._active_runs[task.task_id] = run_task
                    run_task.add_done_callback(
                        lambda t, tid=task.task_id: self._active_runs.pop(tid, None)
                    )

    async def _run_with_semaphore(self, task: RecurringTask):
        """Execute task with concurrency control."""
        async with self._semaphore:
            try:
                await self._execute_task(task)
            except Exception as e:
                logger.error("Task %s failed: %s", task.task_id, e)

    async def _execute_task(self, task: RecurringTask) -> TaskRun:
        """Execute a single task run."""
        import time

        run = TaskRun(
            task_id=task.task_id,
            started_at=datetime.now(timezone.utc),
        )
        await self._store.save_run(run)

        start = time.monotonic()
        try:
            if self._agent_factory:
                agent = self._agent_factory()
                result = await agent.execute_task(
                    goal=task.goal,
                    start_url=task.start_url,
                    max_steps=task.max_steps,
                    credential_aliases=task.credential_aliases,
                )
                run.result = {
                    "success": result.success,
                    "steps": len(result.steps) if hasattr(result, "steps") else 0,
                    "data": result.data if hasattr(result, "data") else None,
                }
                run.status = "completed" if result.success else "failed"
                run.error = result.error if hasattr(result, "error") else None
            else:
                # No agent factory — mark as completed (testing mode)
                run.result = {"simulated": True}
                run.status = "completed"

        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            logger.error("Task run %s failed: %s", run.run_id, e)

        run.completed_at = datetime.now(timezone.utc)
        run.duration = time.monotonic() - start

        await self._store.save_run(run)

        # Update task stats
        task.run_count += 1
        if run.status == "completed":
            task.success_count += 1
        else:
            task.failure_count += 1
        task.last_run = run.started_at
        # Update average duration
        if task.avg_duration == 0:
            task.avg_duration = run.duration
        else:
            task.avg_duration = (task.avg_duration * (task.run_count - 1) + run.duration) / task.run_count
        task.compute_next_run()
        await self._store.save_task(task)

        logger.info("Task run completed: %s status=%s duration=%.1fs",
                     run.run_id, run.status, run.duration or 0)
        return run

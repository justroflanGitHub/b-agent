"""Recurring task definitions."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .cron_schedule import CronSchedule


@dataclass
class RecurringTask:
    """A recurring browser automation task."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    tenant_id: str = "default"
    created_by: str = "system"

    # Schedule
    schedule: Optional[CronSchedule] = None
    enabled: bool = True
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None

    # Task definition
    goal: str = ""
    start_url: Optional[str] = None
    max_steps: int = 20
    timeout: float = 300.0

    # Credential aliases
    credential_aliases: Optional[Dict[str, str]] = None

    # Checkpoint
    checkpoint_on_complete: bool = True
    resume_from_checkpoint: bool = True

    # Notifications
    notify_on_success: List[str] = field(default_factory=list)
    notify_on_failure: List[str] = field(default_factory=list)
    notify_on_missed: List[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_duration: float = 0.0

    # SLA
    max_duration: Optional[float] = None
    expected_duration: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "tenant_id": self.tenant_id,
            "created_by": self.created_by,
            "schedule_expression": self.schedule.expression if self.schedule else None,
            "schedule_tz": self.schedule.timezone if self.schedule else "UTC",
            "enabled": self.enabled,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "goal": self.goal,
            "start_url": self.start_url,
            "max_steps": self.max_steps,
            "timeout": self.timeout,
            "credential_aliases": self.credential_aliases,
            "checkpoint_on_complete": self.checkpoint_on_complete,
            "resume_from_checkpoint": self.resume_from_checkpoint,
            "notify_on_success": self.notify_on_success,
            "notify_on_failure": self.notify_on_failure,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "avg_duration": self.avg_duration,
            "max_duration": self.max_duration,
            "expected_duration": self.expected_duration,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecurringTask":
        schedule = None
        expr = data.get("schedule_expression")
        if expr:
            schedule = CronSchedule(
                expression=expr,
                timezone=data.get("schedule_tz", "UTC"),
            )
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            tenant_id=data.get("tenant_id", "default"),
            created_by=data.get("created_by", "system"),
            schedule=schedule,
            enabled=data.get("enabled", True),
            next_run=datetime.fromisoformat(data["next_run"]) if data.get("next_run") else None,
            last_run=datetime.fromisoformat(data["last_run"]) if data.get("last_run") else None,
            goal=data.get("goal", ""),
            start_url=data.get("start_url"),
            max_steps=data.get("max_steps", 20),
            timeout=data.get("timeout", 300.0),
            credential_aliases=data.get("credential_aliases"),
            checkpoint_on_complete=data.get("checkpoint_on_complete", True),
            resume_from_checkpoint=data.get("resume_from_checkpoint", True),
            notify_on_success=data.get("notify_on_success", []),
            notify_on_failure=data.get("notify_on_failure", []),
            created_at=(
                datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc)
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(timezone.utc)
            ),
            run_count=data.get("run_count", 0),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            avg_duration=data.get("avg_duration", 0.0),
            max_duration=data.get("max_duration"),
            expected_duration=data.get("expected_duration"),
        )

    def compute_next_run(self):
        """Calculate and set next_run based on schedule."""
        if self.schedule:
            after = self.last_run or datetime.now(timezone.utc)
            self.next_run = self.schedule.next_occurrence(after)


@dataclass
class TaskRun:
    """Record of a single task execution."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: str = "running"  # running, completed, failed, timeout, missed
    result: Optional[Dict[str, Any]] = None
    checkpoint_used: Optional[str] = None
    error: Optional[str] = None
    duration: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "result": self.result,
            "checkpoint_used": self.checkpoint_used,
            "error": self.error,
            "duration": self.duration,
        }

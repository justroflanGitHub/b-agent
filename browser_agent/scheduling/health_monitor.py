"""Schedule health monitoring and anomaly detection."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from .recurring_task import RecurringTask, TaskRun

logger = logging.getLogger(__name__)


@dataclass
class ScheduleAnomaly:
    task_id: str
    anomaly_type: str      # "missed_run", "duration_spike", "success_rate_drop", "stuck_checkpoint"
    severity: str          # "warning", "critical"
    details: str
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SLAViolation:
    task_id: str
    task_name: str
    expected_duration: float
    actual_duration: float
    max_duration: float
    run_id: str


@dataclass
class ScheduleHealthReport:
    total_tasks: int = 0
    healthy_tasks: int = 0
    degraded_tasks: int = 0
    unhealthy_tasks: int = 0
    missed_runs_24h: int = 0
    avg_success_rate: float = 0.0
    anomalies: List[ScheduleAnomaly] = field(default_factory=list)


class ScheduleHealthMonitor:
    """Monitor scheduled task health and alert on issues."""

    def __init__(self, success_rate_threshold: float = 0.8,
                 duration_spike_factor: float = 3.0):
        self._success_rate_threshold = success_rate_threshold
        self._duration_spike_factor = duration_spike_factor

    def check_health(self, tasks: List[RecurringTask],
                     recent_runs: dict = None) -> ScheduleHealthReport:
        """Check all tasks' health.

        Args:
            tasks: List of scheduled tasks
            recent_runs: Dict mapping task_id -> List[TaskRun] (last 10 runs)
        """
        report = ScheduleHealthReport(total_tasks=len(tasks))
        recent_runs = recent_runs or {}

        for task in tasks:
            if not task.enabled:
                continue

            runs = recent_runs.get(task.task_id, [])
            is_healthy = True
            is_degraded = False

            # Check success rate
            if runs:
                successes = sum(1 for r in runs if r.status == "completed")
                rate = successes / len(runs) if runs else 1.0
                if rate < self._success_rate_threshold:
                    is_healthy = False
                    report.anomalies.append(ScheduleAnomaly(
                        task_id=task.task_id,
                        anomaly_type="success_rate_drop",
                        severity="critical" if rate < 0.5 else "warning",
                        details=f"Success rate: {rate:.0%} (threshold: {self._success_rate_threshold:.0%})",
                    ))
                    is_degraded = True

            # Check for duration spikes
            if task.expected_duration and runs:
                recent_durations = [r.duration for r in runs if r.duration]
                if recent_durations:
                    avg_recent = sum(recent_durations) / len(recent_durations)
                    if avg_recent > task.expected_duration * self._duration_spike_factor:
                        is_healthy = False
                        report.anomalies.append(ScheduleAnomaly(
                            task_id=task.task_id,
                            anomaly_type="duration_spike",
                            severity="warning",
                            details=f"Avg duration: {avg_recent:.0f}s (expected: {task.expected_duration:.0f}s)",
                        ))
                        is_degraded = True

            # Check for stuck checkpoint (same checkpoint used repeatedly)
            if runs:
                checkpoints = [r.checkpoint_used for r in runs if r.checkpoint_used]
                if len(checkpoints) >= 3 and len(set(checkpoints)) == 1:
                    report.anomalies.append(ScheduleAnomaly(
                        task_id=task.task_id,
                        anomaly_type="stuck_checkpoint",
                        severity="warning",
                        details=f"Same checkpoint used {len(checkpoints)} times in a row",
                    ))
                    is_degraded = True

            if is_healthy and not is_degraded:
                report.healthy_tasks += 1
            elif is_degraded:
                report.degraded_tasks += 1
            else:
                report.unhealthy_tasks += 1

        # Overall success rate
        total_success = sum(t.success_count for t in tasks if t.enabled)
        total_runs = sum(t.run_count for t in tasks if t.enabled)
        report.avg_success_rate = total_success / total_runs if total_runs else 1.0

        return report

    def check_sla(self, task: RecurringTask, run: TaskRun) -> Optional[SLAViolation]:
        """Check if a task run violated SLA."""
        if not task.max_duration or not run.duration:
            return None

        if run.duration > task.max_duration:
            return SLAViolation(
                task_id=task.task_id,
                task_name=task.name,
                expected_duration=task.expected_duration or task.avg_duration,
                actual_duration=run.duration,
                max_duration=task.max_duration,
                run_id=run.run_id,
            )
        return None

    def detect_anomalies(self, tasks: List[RecurringTask],
                         recent_runs: dict = None) -> List[ScheduleAnomaly]:
        """Detect anomalies across all tasks."""
        report = self.check_health(tasks, recent_runs)
        return report.anomalies

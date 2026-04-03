"""Tests for browser_agent.scheduling — cron, scheduler, health, calendar."""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone

from browser_agent.scheduling.cron_schedule import CronSchedule
from browser_agent.scheduling.recurring_task import RecurringTask, TaskRun
from browser_agent.scheduling.scheduler import TaskScheduler, ScheduleStore
from browser_agent.scheduling.health_monitor import ScheduleHealthMonitor, ScheduleAnomaly
from browser_agent.scheduling.calendar import BusinessCalendar


# --- CronSchedule ---


class TestCronSchedule:
    def test_every_minute(self):
        cron = CronSchedule(expression="* * * * *")
        now = datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc)
        nxt = cron.next_occurrence(now)
        assert nxt > now
        assert nxt.minute == 1 or nxt.hour > now.hour

    def test_daily_at_9am(self):
        cron = CronSchedule(expression="0 9 * * *")
        now = datetime(2026, 4, 4, 8, 0, 0, tzinfo=timezone.utc)
        nxt = cron.next_occurrence(now)
        assert nxt.hour == 9
        assert nxt.minute == 0

    def test_monday_at_9am(self):
        cron = CronSchedule(expression="0 9 * * MON")
        now = datetime(2026, 4, 4, 8, 0, 0, tzinfo=timezone.utc)  # Saturday
        nxt = cron.next_occurrence(now)
        assert nxt.weekday() == 0  # Monday
        assert nxt.hour == 9

    def test_every_15_minutes(self):
        cron = CronSchedule(expression="*/15 * * * *")
        now = datetime(2026, 4, 4, 12, 7, 0, tzinfo=timezone.utc)
        nxt = cron.next_occurrence(now)
        assert nxt.minute == 15

    def test_first_of_month(self):
        cron = CronSchedule(expression="0 9 1 * *")
        now = datetime(2026, 4, 15, 8, 0, 0, tzinfo=timezone.utc)
        nxt = cron.next_occurrence(now)
        assert nxt.day == 1
        assert nxt.month == 5  # Next month

    def test_invalid_expression(self):
        with pytest.raises(ValueError, match="5 fields"):
            CronSchedule(expression="0 9 * *")

    def test_should_run_now(self):
        cron = CronSchedule(expression="0 9 * * *")
        at_9 = datetime(2026, 4, 6, 9, 0, 0, tzinfo=timezone.utc)
        assert cron.should_run_now(at_9) is True
        at_10 = datetime(2026, 4, 6, 10, 0, 0, tzinfo=timezone.utc)
        assert cron.should_run_now(at_10) is False

    def test_get_upcoming(self):
        cron = CronSchedule(expression="0 * * * *")
        now = datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc)
        upcoming = cron.get_upcoming(count=3, after=now)
        assert len(upcoming) == 3
        # Each should be 1 hour apart
        assert upcoming[1] > upcoming[0]

    def test_exclude_weekends(self):
        cron = CronSchedule(expression="0 9 * * *", exclude_weekends=True)
        # Friday at 10am
        fri = datetime(2026, 4, 3, 10, 0, 0, tzinfo=timezone.utc)
        nxt = cron.next_occurrence(fri)
        assert nxt.weekday() < 5  # Weekday

    def test_business_hours_only(self):
        cron = CronSchedule(
            expression="0 10 * * *",
            business_hours_only=True,
            business_hours=(9, 17),
        )
        now = datetime(2026, 4, 6, 7, 0, 0, tzinfo=timezone.utc)  # Monday 7am
        nxt = cron.next_occurrence(now)
        assert 9 <= nxt.hour < 17


# --- RecurringTask ---


class TestRecurringTask:
    def test_to_dict_roundtrip(self):
        task = RecurringTask(
            name="Weekly Report",
            goal="Download the weekly sales report",
            schedule=CronSchedule(expression="0 9 * * MON"),
            tenant_id="acme",
        )
        d = task.to_dict()
        restored = RecurringTask.from_dict(d)
        assert restored.name == "Weekly Report"
        assert restored.goal == "Download the weekly sales report"
        assert restored.schedule is not None
        assert restored.schedule.expression == "0 9 * * MON"

    def test_compute_next_run(self):
        task = RecurringTask(
            goal="test",
            schedule=CronSchedule(expression="0 9 * * *"),
        )
        task.compute_next_run()
        assert task.next_run is not None
        assert task.next_run > datetime.now(timezone.utc)

    def test_default_values(self):
        task = RecurringTask(goal="test")
        assert task.enabled is True
        assert task.run_count == 0
        assert task.max_steps == 20


# --- TaskRun ---


class TestTaskRun:
    def test_to_dict(self):
        run = TaskRun(task_id="t1", status="completed", duration=42.5)
        d = run.to_dict()
        assert d["task_id"] == "t1"
        assert d["status"] == "completed"
        assert d["duration"] == 42.5


# --- TaskScheduler ---


class TestTaskScheduler:
    @pytest.fixture
    def scheduler(self, tmp_path):
        store = ScheduleStore(str(tmp_path / "sched.db"))
        return TaskScheduler(store=store)

    @pytest.mark.asyncio
    async def test_register_and_list(self, scheduler):
        task = RecurringTask(
            name="Test Task",
            goal="Do something",
            schedule=CronSchedule(expression="0 9 * * *"),
            tenant_id="acme",
        )
        task_id = await scheduler.register(task)
        assert task_id is not None

        tasks = await scheduler.list_tasks()
        assert len(tasks) == 1
        assert tasks[0].name == "Test Task"

    @pytest.mark.asyncio
    async def test_unregister(self, scheduler):
        task = RecurringTask(goal="test", schedule=CronSchedule(expression="0 9 * * *"))
        task_id = await scheduler.register(task)
        assert await scheduler.unregister(task_id) is True
        tasks = await scheduler.list_tasks()
        assert len(tasks) == 0

    @pytest.mark.asyncio
    async def test_trigger_manual_run(self, scheduler):
        task = RecurringTask(goal="test manual run")
        task_id = await scheduler.register(task)

        run = await scheduler.trigger(task_id)
        assert run.status == "completed"
        assert run.duration is not None

    @pytest.mark.asyncio
    async def test_run_history(self, scheduler):
        task = RecurringTask(goal="test history")
        task_id = await scheduler.register(task)

        await scheduler.trigger(task_id)
        await scheduler.trigger(task_id)

        history = await scheduler.get_run_history(task_id)
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_update_task(self, scheduler):
        task = RecurringTask(
            goal="original",
            schedule=CronSchedule(expression="0 9 * * *"),
        )
        task_id = await scheduler.register(task)

        updated = await scheduler.update(task_id, {"goal": "updated goal", "enabled": False})
        assert updated is not None
        assert updated.goal == "updated goal"
        assert updated.enabled is False

    @pytest.mark.asyncio
    async def test_list_by_tenant(self, scheduler):
        for tenant in ["acme", "globex", "acme"]:
            await scheduler.register(RecurringTask(
                goal="test", tenant_id=tenant,
                schedule=CronSchedule(expression="0 9 * * *"),
            ))
        acme_tasks = await scheduler.list_tasks(tenant_id="acme")
        assert len(acme_tasks) == 2

    @pytest.mark.asyncio
    async def test_get_task(self, scheduler):
        task = RecurringTask(goal="specific", name="FindMe")
        task_id = await scheduler.register(task)

        loaded = await scheduler.get_task(task_id)
        assert loaded is not None
        assert loaded.name == "FindMe"

    @pytest.mark.asyncio
    async def test_task_stats_update(self, scheduler):
        task = RecurringTask(goal="stats test")
        task_id = await scheduler.register(task)

        await scheduler.trigger(task_id)
        updated = await scheduler.get_task(task_id)
        assert updated.run_count == 1
        assert updated.success_count == 1
        assert updated.avg_duration > 0


# --- ScheduleHealthMonitor ---


class TestScheduleHealthMonitor:
    def test_all_healthy(self):
        monitor = ScheduleHealthMonitor()
        task = RecurringTask(goal="test", run_count=10, success_count=10, enabled=True)
        report = monitor.check_health([task])
        assert report.healthy_tasks == 1
        assert report.unhealthy_tasks == 0

    def test_low_success_rate(self):
        monitor = ScheduleHealthMonitor(success_rate_threshold=0.8)
        task = RecurringTask(goal="test", run_count=10, success_count=3, enabled=True)
        runs = [TaskRun(task_id=task.task_id, status="failed") for _ in range(7)]
        runs += [TaskRun(task_id=task.task_id, status="completed") for _ in range(3)]

        report = monitor.check_health([task], {task.task_id: runs})
        assert len(report.anomalies) >= 1
        assert report.anomalies[0].anomaly_type == "success_rate_drop"

    def test_duration_spike(self):
        monitor = ScheduleHealthMonitor()
        task = RecurringTask(goal="test", expected_duration=10.0, enabled=True)
        runs = [TaskRun(task_id=task.task_id, status="completed", duration=50.0)]

        report = monitor.check_health([task], {task.task_id: runs})
        assert any(a.anomaly_type == "duration_spike" for a in report.anomalies)

    def test_sla_violation(self):
        monitor = ScheduleHealthMonitor()
        task = RecurringTask(goal="test", max_duration=30.0)
        run = TaskRun(task_id=task.task_id, status="completed", duration=60.0)

        violation = monitor.check_sla(task, run)
        assert violation is not None
        assert violation.actual_duration == 60.0

    def test_no_sla_violation(self):
        monitor = ScheduleHealthMonitor()
        task = RecurringTask(goal="test", max_duration=60.0)
        run = TaskRun(task_id=task.task_id, status="completed", duration=30.0)
        assert monitor.check_sla(task, run) is None

    def test_detect_anomalies(self):
        monitor = ScheduleHealthMonitor()
        task = RecurringTask(goal="test", run_count=5, success_count=1, enabled=True)
        runs = [TaskRun(task_id=task.task_id, status="failed") for _ in range(4)]
        runs += [TaskRun(task_id=task.task_id, status="completed")]
        anomalies = monitor.detect_anomalies([task], {task.task_id: runs})
        assert len(anomalies) >= 1


# --- BusinessCalendar ---


class TestBusinessCalendar:
    def test_is_business_hours(self):
        cal = BusinessCalendar()
        assert cal.is_business_hours(datetime(2026, 4, 6, 10, 0)) is True
        assert cal.is_business_hours(datetime(2026, 4, 6, 8, 0)) is False
        assert cal.is_business_hours(datetime(2026, 4, 6, 18, 0)) is False

    def test_is_weekend(self):
        cal = BusinessCalendar()
        assert cal.is_weekend(datetime(2026, 4, 4)) is True   # Saturday
        assert cal.is_weekend(datetime(2026, 4, 6)) is False  # Monday

    def test_custom_holidays(self):
        cal = BusinessCalendar()
        cal.add_holidays([datetime(2026, 4, 6)])
        assert cal.is_holiday(datetime(2026, 4, 6)) is True
        assert cal.is_holiday(datetime(2026, 4, 7)) is False

    def test_next_business_time(self):
        cal = BusinessCalendar()
        # Saturday 10am → Monday 9am
        sat = datetime(2026, 4, 4, 10, 0)
        nxt = cal.next_business_time(sat)
        assert nxt.weekday() == 0  # Monday
        assert nxt.hour == 9

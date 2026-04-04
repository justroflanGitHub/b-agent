"""
Browser Agent Metrics Collection

Collects and exposes metrics for monitoring.
"""

import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Any
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class MetricPoint:
    """A single metric data point."""

    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Counter:
    """A monotonically increasing counter."""

    name: str
    description: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def inc(self, amount: float = 1.0):
        """Increment the counter."""
        self.value += amount

    def reset(self):
        """Reset counter to zero."""
        self.value = 0.0


@dataclass
class Gauge:
    """A gauge that can go up and down."""

    name: str
    description: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def set(self, value: float):
        """Set the gauge value."""
        self.value = value

    def inc(self, amount: float = 1.0):
        """Increment the gauge."""
        self.value += amount

    def dec(self, amount: float = 1.0):
        """Decrement the gauge."""
        self.value -= amount


@dataclass
class Histogram:
    """A histogram for tracking value distributions."""

    name: str
    description: str
    buckets: List[float] = field(default_factory=lambda: [0.1, 0.5, 1.0, 2.5, 5.0, 10.0])
    counts: Dict[float, int] = field(default_factory=dict)
    sum: float = 0.0
    count: int = 0
    labels: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.counts:
            self.counts = {bucket: 0 for bucket in self.buckets}
            self.counts[float("inf")] = 0

    def observe(self, value: float):
        """Observe a value."""
        self.sum += value
        self.count += 1

        for bucket in self.buckets:
            if value <= bucket:
                self.counts[bucket] += 1
        self.counts[float("inf")] += 1

    def get_percentile(self, p: float) -> float:
        """Get approximate percentile value."""
        if self.count == 0:
            return 0.0

        target = self.count * p
        cumulative = 0

        for bucket in sorted(self.counts.keys()):
            cumulative += self.counts[bucket]
            if cumulative >= target:
                return bucket

        return float("inf")


class MetricsCollector:
    """
    Central metrics collection and exposition.

    Collects metrics for:
    - Task execution (duration, success rate)
    - Action latency
    - Error rates
    - Resource usage
    """

    def __init__(self, namespace: str = "browser_agent"):
        self.namespace = namespace
        self._lock = threading.Lock()

        # Counters
        self._counters: Dict[str, Counter] = {}

        # Gauges
        self._gauges: Dict[str, Gauge] = {}

        # Histograms
        self._histograms: Dict[str, Histogram] = {}

        # Time series data (for graphs)
        self._time_series: Dict[str, List[MetricPoint]] = defaultdict(list)
        self._max_time_series_points = 1000

        # Initialize default metrics
        self._init_default_metrics()

    def _init_default_metrics(self):
        """Initialize default metrics."""
        # Task metrics
        self._counters["tasks_total"] = Counter(
            name=f"{self.namespace}_tasks_total", description="Total number of tasks"
        )
        self._counters["tasks_completed"] = Counter(
            name=f"{self.namespace}_tasks_completed", description="Number of completed tasks"
        )
        self._counters["tasks_failed"] = Counter(
            name=f"{self.namespace}_tasks_failed", description="Number of failed tasks"
        )
        self._counters["tasks_cancelled"] = Counter(
            name=f"{self.namespace}_tasks_cancelled", description="Number of cancelled tasks"
        )

        # Action metrics
        self._counters["actions_total"] = Counter(
            name=f"{self.namespace}_actions_total", description="Total number of actions"
        )
        self._counters["actions_successful"] = Counter(
            name=f"{self.namespace}_actions_successful", description="Number of successful actions"
        )
        self._counters["actions_failed"] = Counter(
            name=f"{self.namespace}_actions_failed", description="Number of failed actions"
        )

        # Gauges
        self._gauges["active_tasks"] = Gauge(
            name=f"{self.namespace}_active_tasks", description="Number of currently active tasks"
        )
        self._gauges["queued_tasks"] = Gauge(
            name=f"{self.namespace}_queued_tasks", description="Number of queued tasks"
        )

        # Histograms
        self._histograms["task_duration_seconds"] = Histogram(
            name=f"{self.namespace}_task_duration_seconds",
            description="Task execution duration in seconds",
            buckets=[1, 5, 10, 30, 60, 120, 300, 600],
        )
        self._histograms["action_duration_seconds"] = Histogram(
            name=f"{self.namespace}_action_duration_seconds",
            description="Action execution duration in seconds",
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
        )

    def counter(self, name: str) -> Counter:
        """Get or create a counter."""
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name=f"{self.namespace}_{name}", description=f"Counter: {name}")
            return self._counters[name]

    def gauge(self, name: str) -> Gauge:
        """Get or create a gauge."""
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name=f"{self.namespace}_{name}", description=f"Gauge: {name}")
            return self._gauges[name]

    def histogram(self, name: str, buckets: List[float] = None) -> Histogram:
        """Get or create a histogram."""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(
                    name=f"{self.namespace}_{name}",
                    description=f"Histogram: {name}",
                    buckets=buckets or [0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
                )
            return self._histograms[name]

    def record_task_start(self, task_id: str):
        """Record task start."""
        self._counters["tasks_total"].inc()
        self._gauges["active_tasks"].inc()
        self._add_time_point("tasks_started", 1)

    def record_task_complete(self, task_id: str, duration: float, success: bool):
        """Record task completion."""
        self._gauges["active_tasks"].dec()

        if success:
            self._counters["tasks_completed"].inc()
        else:
            self._counters["tasks_failed"].inc()

        self._histograms["task_duration_seconds"].observe(duration)
        self._add_time_point("task_duration", duration)
        self._add_time_point("success_rate", 1 if success else 0)

    def record_task_cancel(self, task_id: str):
        """Record task cancellation."""
        self._gauges["active_tasks"].dec()
        self._counters["tasks_cancelled"].inc()

    def record_action(self, action_type: str, duration: float, success: bool):
        """Record action execution."""
        self._counters["actions_total"].inc()

        if success:
            self._counters["actions_successful"].inc()
        else:
            self._counters["actions_failed"].inc()

        self._histograms["action_duration_seconds"].observe(duration)
        self._add_time_point(f"action_{action_type}_duration", duration)

    def update_queue_size(self, size: int):
        """Update queued tasks gauge."""
        self._gauges["queued_tasks"].set(size)

    def _add_time_point(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Add a point to time series."""
        point = MetricPoint(timestamp=datetime.now(timezone.utc), value=value, labels=labels or {})

        with self._lock:
            self._time_series[metric_name].append(point)
            # Trim old points
            if len(self._time_series[metric_name]) > self._max_time_series_points:
                self._time_series[metric_name] = self._time_series[metric_name][-self._max_time_series_points :]

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary."""
        with self._lock:
            return {
                "counters": {name: c.value for name, c in self._counters.items()},
                "gauges": {name: g.value for name, g in self._gauges.items()},
                "histograms": {
                    name: {"sum": h.sum, "count": h.count, "buckets": {str(k): v for k, v in h.counts.items()}}
                    for name, h in self._histograms.items()
                },
            }

    def get_time_series(self, metric_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get time series data for a metric."""
        with self._lock:
            points = self._time_series.get(metric_name, [])[-limit:]
            return [{"timestamp": p.timestamp.isoformat(), "value": p.value, "labels": p.labels} for p in points]

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        # Export counters
        for name, counter in self._counters.items():
            lines.append(f"# HELP {counter.name} {counter.description}")
            lines.append(f"# TYPE {counter.name} counter")
            lines.append(f"{counter.name} {counter.value}")
            lines.append("")

        # Export gauges
        for name, gauge in self._gauges.items():
            lines.append(f"# HELP {gauge.name} {gauge.description}")
            lines.append(f"# TYPE {gauge.name} gauge")
            lines.append(f"{gauge.name} {gauge.value}")
            lines.append("")

        # Export histograms
        for name, hist in self._histograms.items():
            lines.append(f"# HELP {hist.name} {hist.description}")
            lines.append(f"# TYPE {hist.name} histogram")

            for bucket, count in sorted(hist.counts.items()):
                bucket_label = "+Inf" if bucket == float("inf") else str(bucket)
                lines.append(f'{hist.name}_bucket{{le="{bucket_label}"}} {count}')

            lines.append(f"{hist.name}_sum {hist.sum}")
            lines.append(f"{hist.name}_count {hist.count}")
            lines.append("")

        return "\n".join(lines)

    def reset(self):
        """Reset all metrics."""
        with self._lock:
            for counter in self._counters.values():
                counter.reset()
            for gauge in self._gauges.values():
                gauge.set(0)
            for hist in self._histograms.values():
                hist.counts = {bucket: 0 for bucket in hist.buckets}
                hist.counts[float("inf")] = 0
                hist.sum = 0
                hist.count = 0
            self._time_series.clear()


class Timer:
    """Context manager for timing operations."""

    def __init__(self, metrics: MetricsCollector, histogram_name: str, action_type: str = None):
        self.metrics = metrics
        self.histogram_name = histogram_name
        self.action_type = action_type
        self.start_time = None
        self.duration = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration = time.time() - self.start_time
        success = exc_type is None

        if self.action_type:
            self.metrics.record_action(self.action_type, self.duration, success)
        else:
            self.metrics.histogram(self.histogram_name).observe(self.duration)

        return False  # Don't suppress exceptions


# Global metrics instance
metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector."""
    return metrics

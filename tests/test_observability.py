"""
Tests for Browser Agent Observability Module

Tests for logging, metrics, and health checking.
"""

import pytest
import asyncio
import time
import json
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
import logging

from browser_agent.observability.logging_config import (
    setup_logging,
    get_logger,
    CorrelationIdFilter,
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id,
    StructuredFormatter,
    HumanReadableFormatter,
    LoggerAdapter,
    get_contextual_logger
)
from browser_agent.observability.metrics import (
    MetricsCollector,
    Counter,
    Gauge,
    Histogram,
    MetricPoint,
    Timer,
    metrics,
    get_metrics
)
from browser_agent.observability.health import (
    HealthChecker,
    HealthStatus,
    ComponentHealth,
    create_browser_health_checker,
    create_memory_health_checker,
    create_vision_health_checker,
    get_health_checker
)


# ============= Logging Tests =============

class TestCorrelationId:
    """Tests for correlation ID management."""
    
    def test_set_correlation_id(self):
        """Test setting correlation ID."""
        clear_correlation_id()
        corr_id = set_correlation_id()
        assert corr_id is not None
        assert len(corr_id) == 12
        assert get_correlation_id() == corr_id
    
    def test_set_specific_correlation_id(self):
        """Test setting specific correlation ID."""
        specific_id = "test123"
        set_correlation_id(specific_id)
        assert get_correlation_id() == specific_id
    
    def test_clear_correlation_id(self):
        """Test clearing correlation ID."""
        set_correlation_id("test")
        clear_correlation_id()
        assert get_correlation_id() is None


class TestStructuredFormatter:
    """Tests for structured JSON formatter."""
    
    def test_format_basic_record(self):
        """Test formatting a basic log record."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.correlation_id = "test123"
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert data["correlation_id"] == "test123"
        assert "timestamp" in data
        assert "location" in data
    
    def test_format_with_exception(self):
        """Test formatting with exception info."""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        record.correlation_id = "-"
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert "Test error" in data["exception"]["message"]


class TestCorrelationIdFilter:
    """Tests for correlation ID filter."""
    
    def test_filter_adds_correlation_id(self):
        """Test that filter adds correlation ID to record."""
        filter_obj = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test",
            args=(),
            exc_info=None
        )
        
        set_correlation_id("test_corr")
        result = filter_obj.filter(record)
        
        assert result is True
        assert hasattr(record, 'correlation_id')
        assert record.correlation_id == "test_corr"


class TestSetupLogging:
    """Tests for logging setup."""
    
    def test_setup_logging_default(self):
        """Test default logging setup."""
        setup_logging(level="INFO")
        logger = get_logger("test")
        assert logger.level == logging.NOTSET  # Uses root logger level
    
    def test_setup_logging_json(self):
        """Test JSON logging setup."""
        setup_logging(level="DEBUG", json_output=True)
        root = logging.getLogger()
        # Check that handler has StructuredFormatter
        assert any(
            isinstance(h.formatter, StructuredFormatter)
            for h in root.handlers
        )


class TestContextualLogger:
    """Tests for contextual logger."""
    
    def test_contextual_logger(self):
        """Test logger with persistent context."""
        logger = get_contextual_logger("test", task_id="123", action="click")
        
        assert isinstance(logger, LoggerAdapter)
        assert logger.extra == {"task_id": "123", "action": "click"}


# ============= Metrics Tests =============

class TestCounter:
    """Tests for Counter metric."""
    
    def test_counter_increment(self):
        """Test counter increment."""
        counter = Counter(name="test_counter", description="Test")
        counter.inc()
        assert counter.value == 1.0
        counter.inc(5)
        assert counter.value == 6.0
    
    def test_counter_reset(self):
        """Test counter reset."""
        counter = Counter(name="test", description="Test")
        counter.inc(10)
        counter.reset()
        assert counter.value == 0.0


class TestGauge:
    """Tests for Gauge metric."""
    
    def test_gauge_set(self):
        """Test gauge set."""
        gauge = Gauge(name="test_gauge", description="Test")
        gauge.set(42)
        assert gauge.value == 42
    
    def test_gauge_inc_dec(self):
        """Test gauge increment and decrement."""
        gauge = Gauge(name="test", description="Test")
        gauge.set(10)
        gauge.inc(5)
        assert gauge.value == 15
        gauge.dec(3)
        assert gauge.value == 12


class TestHistogram:
    """Tests for Histogram metric."""
    
    def test_histogram_observe(self):
        """Test histogram observation."""
        hist = Histogram(
            name="test_hist",
            description="Test",
            buckets=[1, 5, 10]
        )
        
        hist.observe(2)
        hist.observe(7)
        hist.observe(15)
        
        assert hist.count == 3
        assert hist.sum == 24
    
    def test_histogram_percentile(self):
        """Test histogram percentile calculation."""
        hist = Histogram(
            name="test",
            description="Test",
            buckets=[1, 5, 10]
        )
        
        for i in range(100):
            hist.observe(i)
        
        p50 = hist.get_percentile(0.5)
        assert p50 > 0


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    @pytest.fixture
    def collector(self):
        """Create fresh metrics collector."""
        return MetricsCollector(namespace="test")
    
    def test_get_counter(self, collector):
        """Test getting counter."""
        counter = collector.counter("my_counter")
        assert isinstance(counter, Counter)
        assert counter.name == "test_my_counter"
    
    def test_get_gauge(self, collector):
        """Test getting gauge."""
        gauge = collector.gauge("my_gauge")
        assert isinstance(gauge, Gauge)
        assert gauge.name == "test_my_gauge"
    
    def test_get_histogram(self, collector):
        """Test getting histogram."""
        hist = collector.histogram("my_hist")
        assert isinstance(hist, Histogram)
        assert hist.name == "test_my_hist"
    
    def test_record_task_start(self, collector):
        """Test recording task start."""
        collector.record_task_start("task1")
        
        assert collector._counters['tasks_total'].value == 1
        assert collector._gauges['active_tasks'].value == 1
    
    def test_record_task_complete(self, collector):
        """Test recording task completion."""
        collector.record_task_start("task1")
        collector.record_task_complete("task1", duration=5.0, success=True)
        
        assert collector._counters['tasks_completed'].value == 1
        assert collector._gauges['active_tasks'].value == 0
        assert collector._histograms['task_duration_seconds'].count == 1
    
    def test_record_task_failure(self, collector):
        """Test recording task failure."""
        collector.record_task_start("task1")
        collector.record_task_complete("task1", duration=5.0, success=False)
        
        assert collector._counters['tasks_failed'].value == 1
        assert collector._counters['tasks_completed'].value == 0
    
    def test_record_action(self, collector):
        """Test recording action."""
        collector.record_action("click", duration=0.5, success=True)
        
        assert collector._counters['actions_total'].value == 1
        assert collector._counters['actions_successful'].value == 1
    
    def test_get_all_metrics(self, collector):
        """Test getting all metrics."""
        collector.record_task_start("task1")
        collector.record_task_complete("task1", 5.0, True)
        
        all_metrics = collector.get_all_metrics()
        
        assert "counters" in all_metrics
        assert "gauges" in all_metrics
        assert "histograms" in all_metrics
    
    def test_export_prometheus(self, collector):
        """Test Prometheus export."""
        collector.record_task_start("task1")
        collector.record_task_complete("task1", 5.0, True)
        
        prom_output = collector.export_prometheus()
        
        assert "test_tasks_total" in prom_output
        assert "test_tasks_completed" in prom_output
        assert "# TYPE" in prom_output
        assert "# HELP" in prom_output
    
    def test_reset(self, collector):
        """Test metrics reset."""
        collector.record_task_start("task1")
        collector.record_task_complete("task1", 5.0, True)
        
        collector.reset()
        
        assert collector._counters['tasks_total'].value == 0
        assert collector._counters['tasks_completed'].value == 0


class TestTimer:
    """Tests for Timer context manager."""
    
    def test_timer(self):
        """Test timer context manager."""
        collector = MetricsCollector()
        
        with Timer(collector, "task_duration_seconds"):
            time.sleep(0.1)
        
        assert collector._histograms['task_duration_seconds'].count == 1
    
    def test_timer_with_action(self):
        """Test timer with action recording."""
        collector = MetricsCollector()
        
        with Timer(collector, "action_duration", action_type="click"):
            time.sleep(0.05)
        
        assert collector._counters['actions_total'].value == 1
        assert collector._counters['actions_successful'].value == 1


# ============= Health Check Tests =============

class TestComponentHealth:
    """Tests for ComponentHealth."""
    
    def test_component_health_creation(self):
        """Test creating component health."""
        health = ComponentHealth(
            name="test",
            status=HealthStatus.HEALTHY,
            message="All good"
        )
        assert health.name == "test"
        assert health.status == HealthStatus.HEALTHY
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        health = ComponentHealth(
            name="test",
            status=HealthStatus.HEALTHY,
            message="OK",
            details={"key": "value"}
        )
        
        data = health.to_dict()
        
        assert data["name"] == "test"
        assert data["status"] == "healthy"
        assert data["message"] == "OK"
        assert data["details"] == {"key": "value"}


class TestHealthChecker:
    """Tests for HealthChecker."""
    
    @pytest.fixture
    def health_checker(self):
        """Create fresh health checker."""
        return HealthChecker(check_interval=5.0)
    
    def test_register_checker(self, health_checker):
        """Test registering a health checker."""
        def test_checker():
            return ComponentHealth(
                name="test",
                status=HealthStatus.HEALTHY,
                message="OK"
            )
        
        health_checker.register_checker("test", test_checker)
        
        assert "test" in health_checker._checkers
        assert "test" in health_checker._components
    
    def test_get_component_health(self, health_checker):
        """Test getting component health."""
        health_checker.register_checker("test", lambda: ComponentHealth(
            name="test",
            status=HealthStatus.HEALTHY,
            message="OK"
        ))
        
        health = health_checker.get_component_health("test")
        assert health is not None
        assert health.name == "test"
    
    @pytest.mark.asyncio
    async def test_get_system_health_healthy(self, health_checker):
        """Test system health when all healthy."""
        health_checker.register_checker("comp1", lambda: ComponentHealth(
            name="comp1", status=HealthStatus.HEALTHY, message="OK"
        ))
        health_checker.register_checker("comp2", lambda: ComponentHealth(
            name="comp2", status=HealthStatus.HEALTHY, message="OK"
        ))
        
        # Run check_all to update component statuses from checkers
        await health_checker.check_all()
        
        system = health_checker.get_system_health()
        
        assert system.status == HealthStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_get_system_health_degraded(self, health_checker):
        """Test system health when degraded."""
        health_checker.register_checker("comp1", lambda: ComponentHealth(
            name="comp1", status=HealthStatus.HEALTHY, message="OK"
        ))
        health_checker.register_checker("comp2", lambda: ComponentHealth(
            name="comp2", status=HealthStatus.DEGRADED, message="Issues"
        ))
        
        # Run check_all to update component statuses from checkers
        await health_checker.check_all()
        
        system = health_checker.get_system_health()
        
        assert system.status == HealthStatus.DEGRADED
    
    @pytest.mark.asyncio
    async def test_get_system_health_unhealthy(self, health_checker):
        """Test system health when unhealthy."""
        health_checker.register_checker("comp1", lambda: ComponentHealth(
            name="comp1", status=HealthStatus.HEALTHY, message="OK"
        ))
        health_checker.register_checker("comp2", lambda: ComponentHealth(
            name="comp2", status=HealthStatus.UNHEALTHY, message="Failed"
        ))
        
        # Run check_all to update component statuses from checkers
        await health_checker.check_all()
        
        system = health_checker.get_system_health()
        
        assert system.status == HealthStatus.UNHEALTHY
    
    @pytest.mark.asyncio
    async def test_check_all(self, health_checker):
        """Test running all health checks."""
        check_count = 0
        
        def test_checker():
            nonlocal check_count
            check_count += 1
            return ComponentHealth(
                name="test",
                status=HealthStatus.HEALTHY,
                message="OK"
            )
        
        health_checker.register_checker("test", test_checker)
        
        results = await health_checker.check_all()
        
        assert check_count == 1
        assert "test" in results
    
    @pytest.mark.asyncio
    async def test_check_all_with_exception(self, health_checker):
        """Test health check with exception."""
        def failing_checker():
            raise RuntimeError("Check failed")
        
        health_checker.register_checker("failing", failing_checker)
        
        results = await health_checker.check_all()
        
        assert results["failing"].status == HealthStatus.UNHEALTHY
        assert "failed" in results["failing"].message.lower()
    
    def test_to_dict(self, health_checker):
        """Test converting to dictionary."""
        health_checker.register_checker("test", lambda: ComponentHealth(
            name="test", status=HealthStatus.HEALTHY, message="OK"
        ))
        
        data = health_checker.to_dict()
        
        assert "status" in data
        assert "components" in data
        assert "uptime" in data


class TestHealthCheckerFactories:
    """Tests for health checker factory functions."""
    
    def test_create_browser_health_checker_connected(self):
        """Test browser health checker when connected."""
        mock_browser = Mock()
        mock_browser.is_connected.return_value = True
        
        checker = create_browser_health_checker(mock_browser)
        result = checker()
        
        assert result.status == HealthStatus.HEALTHY
        assert "connected" in result.message.lower()
    
    def test_create_browser_health_checker_disconnected(self):
        """Test browser health checker when disconnected."""
        mock_browser = Mock()
        mock_browser.is_connected.return_value = False
        
        checker = create_browser_health_checker(mock_browser)
        result = checker()
        
        assert result.status == HealthStatus.UNHEALTHY
    
    def test_create_browser_health_checker_none(self):
        """Test browser health checker with None."""
        checker = create_browser_health_checker(None)
        result = checker()
        
        assert result.status == HealthStatus.DEGRADED
    
    def test_create_memory_health_checker(self):
        """Test memory health checker."""
        checker = create_memory_health_checker(threshold_mb=1000)
        result = checker()
        
        assert result.name == "memory"
        assert "memory_mb" in result.details
    
    def test_create_vision_health_checker(self):
        """Test vision health checker."""
        checker = create_vision_health_checker(None)
        result = checker()
        
        assert result.name == "vision"
        assert result.status == HealthStatus.DEGRADED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

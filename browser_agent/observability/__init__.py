"""
Browser Agent Observability Module

Structured logging, metrics, and health monitoring.
"""

from .logging_config import setup_logging, get_logger, CorrelationIdFilter
from .metrics import MetricsCollector, metrics
from .health import HealthChecker, HealthStatus

__all__ = [
    "setup_logging",
    "get_logger",
    "CorrelationIdFilter",
    "MetricsCollector",
    "metrics",
    "HealthChecker",
    "HealthStatus"
]

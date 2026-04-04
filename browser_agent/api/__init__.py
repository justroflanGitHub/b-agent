"""
Browser Agent API Module

FastAPI-based REST API for browser automation tasks.
"""

from .app import create_app
from .models import TaskRequest, TaskStatus, TaskResult, SessionInfo, HealthStatus, MetricsResponse
from .task_manager import TaskManager

__all__ = [
    "create_app",
    "TaskRequest",
    "TaskStatus",
    "TaskResult",
    "SessionInfo",
    "HealthStatus",
    "MetricsResponse",
    "TaskManager",
]

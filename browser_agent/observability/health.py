"""
Browser Agent Health Checking

Health check system for monitoring component status.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a single component."""

    name: str
    status: HealthStatus
    message: str = ""
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "last_check": self.last_check.isoformat(),
            "details": self.details,
        }


class HealthChecker:
    """
    System health checker.

    Checks health of various components:
    - Browser connection
    - LLM connection
    - Vision model
    - Memory usage
    """

    def __init__(self, check_interval: float = 30.0):
        self.check_interval = check_interval
        self._components: Dict[str, ComponentHealth] = {}
        self._checkers: Dict[str, Callable] = {}
        self._start_time = time.time()
        self._running = False
        self._check_task: Optional[asyncio.Task] = None

    def register_checker(self, name: str, checker: Callable[[], ComponentHealth]):
        """
        Register a health checker function.

        Args:
            name: Component name
            checker: Async or sync function that returns ComponentHealth
        """
        self._checkers[name] = checker
        # Initialize with unknown status
        self._components[name] = ComponentHealth(name=name, status=HealthStatus.DEGRADED, message="Not yet checked")

    def get_component_health(self, name: str) -> Optional[ComponentHealth]:
        """Get health of a specific component."""
        return self._components.get(name)

    def get_all_health(self) -> Dict[str, ComponentHealth]:
        """Get health of all components."""
        return self._components.copy()

    def get_system_health(self) -> ComponentHealth:
        """
        Get overall system health.

        Returns the worst status among all components.
        """
        if not self._components:
            return ComponentHealth(name="system", status=HealthStatus.DEGRADED, message="No components registered")

        # Find worst status
        has_unhealthy = False
        has_degraded = False

        for health in self._components.values():
            if health.status == HealthStatus.UNHEALTHY:
                has_unhealthy = True
            elif health.status == HealthStatus.DEGRADED:
                has_degraded = True

        if has_unhealthy:
            status = HealthStatus.UNHEALTHY
            message = "One or more components are unhealthy"
        elif has_degraded:
            status = HealthStatus.DEGRADED
            message = "One or more components are degraded"
        else:
            status = HealthStatus.HEALTHY
            message = "All components are healthy"

        return ComponentHealth(
            name="system",
            status=status,
            message=message,
            details={
                "uptime": time.time() - self._start_time,
                "components": {name: h.status.value for name, h in self._components.items()},
            },
        )

    async def check_all(self) -> Dict[str, ComponentHealth]:
        """Run all health checks."""
        for name, checker in self._checkers.items():
            try:
                if asyncio.iscoroutinefunction(checker):
                    health = await checker()
                else:
                    health = checker()

                self._components[name] = health
                logger.debug(f"Health check for {name}: {health.status.value}")

            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                self._components[name] = ComponentHealth(
                    name=name, status=HealthStatus.UNHEALTHY, message=f"Health check failed: {str(e)}"
                )

        return self._components.copy()

    async def start(self):
        """Start periodic health checking."""
        if self._running:
            return

        self._running = True
        self._check_task = asyncio.create_task(self._check_loop())
        logger.info("Health checker started")

    async def stop(self):
        """Stop health checking."""
        self._running = False

        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass

        logger.info("Health checker stopped")

    async def _check_loop(self):
        """Periodic health check loop."""
        while self._running:
            try:
                await self.check_all()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(5)  # Wait before retry

    def to_dict(self) -> Dict[str, Any]:
        """Get full health status as dictionary."""
        system = self.get_system_health()
        return {
            "status": system.status.value,
            "message": system.message,
            "uptime": system.details.get("uptime", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {name: health.to_dict() for name, health in self._components.items()},
        }


# Default health checkers


def create_browser_health_checker(browser_controller=None) -> Callable[[], ComponentHealth]:
    """Create a health checker for browser connection."""

    def check() -> ComponentHealth:
        try:
            if browser_controller is None:
                return ComponentHealth(name="browser", status=HealthStatus.DEGRADED, message="Browser not initialized")

            # Check if browser is connected
            if hasattr(browser_controller, "is_connected"):
                connected = browser_controller.is_connected()
            else:
                connected = (
                    browser_controller._browser is not None if hasattr(browser_controller, "_browser") else False
                )

            if connected:
                return ComponentHealth(name="browser", status=HealthStatus.HEALTHY, message="Browser connected")
            else:
                return ComponentHealth(name="browser", status=HealthStatus.UNHEALTHY, message="Browser not connected")
        except Exception as e:
            return ComponentHealth(name="browser", status=HealthStatus.UNHEALTHY, message=f"Check failed: {str(e)}")

    return check


def create_llm_health_checker(llm_client=None) -> Callable[[], ComponentHealth]:
    """Create a health checker for LLM connection."""

    async def check() -> ComponentHealth:
        try:
            if llm_client is None:
                return ComponentHealth(name="llm", status=HealthStatus.DEGRADED, message="LLM client not initialized")

            # Try a simple request
            if hasattr(llm_client, "health_check"):
                healthy = await llm_client.health_check()
            else:
                # Assume healthy if client exists
                healthy = True

            if healthy:
                return ComponentHealth(name="llm", status=HealthStatus.HEALTHY, message="LLM connected")
            else:
                return ComponentHealth(name="llm", status=HealthStatus.UNHEALTHY, message="LLM not responding")
        except Exception as e:
            return ComponentHealth(name="llm", status=HealthStatus.UNHEALTHY, message=f"Check failed: {str(e)}")

    return check


def create_memory_health_checker(threshold_mb: float = 500) -> Callable[[], ComponentHealth]:
    """Create a health checker for memory usage."""

    def check() -> ComponentHealth:
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            if memory_mb < threshold_mb * 0.7:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {memory_mb:.1f}MB"
            elif memory_mb < threshold_mb:
                status = HealthStatus.DEGRADED
                message = f"Memory usage elevated: {memory_mb:.1f}MB"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Memory usage high: {memory_mb:.1f}MB"

            return ComponentHealth(
                name="memory",
                status=status,
                message=message,
                details={"memory_mb": memory_mb, "threshold_mb": threshold_mb},
            )
        except ImportError:
            return ComponentHealth(name="memory", status=HealthStatus.DEGRADED, message="psutil not available")
        except Exception as e:
            return ComponentHealth(name="memory", status=HealthStatus.UNHEALTHY, message=f"Check failed: {str(e)}")

    return check


def create_vision_health_checker(vision_client=None) -> Callable[[], ComponentHealth]:
    """Create a health checker for vision model."""

    def check() -> ComponentHealth:
        try:
            if vision_client is None:
                return ComponentHealth(
                    name="vision", status=HealthStatus.DEGRADED, message="Vision client not initialized"
                )

            # Check if vision client is ready
            if hasattr(vision_client, "is_ready"):
                ready = vision_client.is_ready()
            else:
                ready = True  # Assume ready if exists

            if ready:
                return ComponentHealth(name="vision", status=HealthStatus.HEALTHY, message="Vision model ready")
            else:
                return ComponentHealth(name="vision", status=HealthStatus.UNHEALTHY, message="Vision model not ready")
        except Exception as e:
            return ComponentHealth(name="vision", status=HealthStatus.UNHEALTHY, message=f"Check failed: {str(e)}")

    return check


# Global health checker instance
health_checker = HealthChecker()


def get_health_checker() -> HealthChecker:
    """Get the global health checker."""
    return health_checker

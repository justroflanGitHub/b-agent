"""
Fallback Strategy System for Browser Agent Error Recovery.

Provides error classification and fallback strategies for resilient operation.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classification of browser agent errors."""

    ELEMENT_NOT_FOUND = "element_not_found"  # Target element not visible/present
    ACTION_TIMEOUT = "action_timeout"  # Action took too long
    NAVIGATION_ERROR = "navigation_error"  # Page navigation failed
    SELECTOR_INVALID = "selector_invalid"  # Invalid CSS selector
    STATE_MISMATCH = "state_mismatch"  # Page state different than expected
    CAPTCHA_BLOCK = "captcha_block"  # CAPTCHA detected
    RATE_LIMIT = "rate_limit"  # Rate limited by site
    NETWORK_ERROR = "network_error"  # Network connectivity issue
    BROWSER_CRASH = "browser_crash"  # Browser process crashed
    PERMISSION_DENIED = "permission_denied"  # Permission denied by site
    AUTH_REQUIRED = "auth_required"  # Authentication required
    VALIDATION_ERROR = "validation_error"  # Input validation failed
    UNKNOWN = "unknown"  # Unclassified error


@dataclass
class ErrorContext:
    """Context information for an error."""

    error_type: ErrorType
    error_message: str
    error_exception: Optional[Exception] = None
    action_name: Optional[str] = None
    action_params: Dict[str, Any] = field(default_factory=dict)
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    screenshot: Optional[bytes] = None
    timestamp: float = field(default_factory=time.time)
    attempt_count: int = 1
    previous_errors: List[ErrorType] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "error_type": self.error_type.value,
            "error_message": self.error_message,
            "action_name": self.action_name,
            "action_params": self.action_params,
            "page_url": self.page_url,
            "page_title": self.page_title,
            "timestamp": self.timestamp,
            "attempt_count": self.attempt_count,
            "previous_errors": [e.value for e in self.previous_errors],
        }


@dataclass
class FallbackResult:
    """Result of a fallback strategy execution."""

    success: bool
    strategy_name: str
    error_context: ErrorContext
    recovery_action: Optional[str] = None
    recovery_params: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    next_strategy_hint: Optional[str] = None
    should_retry: bool = True
    should_abort: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "strategy_name": self.strategy_name,
            "recovery_action": self.recovery_action,
            "message": self.message,
            "next_strategy_hint": self.next_strategy_hint,
            "should_retry": self.should_retry,
            "should_abort": self.should_abort,
        }


class FallbackStrategy(ABC):
    """Abstract base class for fallback strategies."""

    name: str = "base"
    priority: int = 100  # Lower = higher priority
    applicable_errors: List[ErrorType] = []
    max_attempts: int = 3

    @abstractmethod
    async def can_handle(self, error_context: ErrorContext) -> bool:
        """Check if this strategy can handle the given error."""

    @abstractmethod
    async def execute(self, error_context: ErrorContext, page: Any, **kwargs) -> FallbackResult:
        """Execute the fallback strategy."""

    def get_retry_delay(self, attempt: int) -> float:
        """Get delay before retry with exponential backoff."""
        return min(2**attempt, 30)  # Max 30 seconds


class VisualSearchFallback(FallbackStrategy):
    """Fallback using vision model to find elements."""

    name = "visual_search"
    priority = 10
    applicable_errors = [ErrorType.ELEMENT_NOT_FOUND, ErrorType.SELECTOR_INVALID]
    max_attempts = 2

    def __init__(self, vision_client: Any):
        self.vision_client = vision_client

    async def can_handle(self, error_context: ErrorContext) -> bool:
        """Check if visual search is applicable."""
        return error_context.error_type in self.applicable_errors

    async def execute(self, error_context: ErrorContext, page: Any, **kwargs) -> FallbackResult:
        """Use vision model to find element coordinates."""
        try:
            # Take screenshot
            screenshot = await page.screenshot(type="png")

            # Get element description from action params
            description = error_context.action_params.get("description", "")
            if not description:
                description = error_context.action_params.get("selector", "")

            # Use vision client to find coordinates
            result = await self.vision_client.get_click_coordinates(
                screenshot=screenshot, instruction=f"Find: {description}"
            )

            if result and result.get("coordinates"):
                coords = result["coordinates"]
                return FallbackResult(
                    success=True,
                    strategy_name=self.name,
                    error_context=error_context,
                    recovery_action="click",
                    recovery_params={"x": coords[0], "y": coords[1]},
                    message=f"Found element via visual search at ({coords[0]}, {coords[1]})",
                    metadata={"confidence": result.get("confidence", 0)},
                )

            return FallbackResult(
                success=False,
                strategy_name=self.name,
                error_context=error_context,
                message="Visual search failed to find element",
                should_retry=True,
            )

        except Exception as e:
            logger.error(f"Visual search fallback failed: {e}")
            return FallbackResult(
                success=False,
                strategy_name=self.name,
                error_context=error_context,
                message=f"Visual search error: {str(e)}",
                should_retry=False,
            )


class ScrollAndRetryFallback(FallbackStrategy):
    """Fallback that scrolls page and retries."""

    name = "scroll_and_retry"
    priority = 20
    applicable_errors = [ErrorType.ELEMENT_NOT_FOUND, ErrorType.STATE_MISMATCH]
    max_attempts = 3

    async def can_handle(self, error_context: ErrorContext) -> bool:
        """Check if scroll and retry is applicable."""
        return error_context.error_type in self.applicable_errors

    async def execute(self, error_context: ErrorContext, page: Any, **kwargs) -> FallbackResult:
        """Scroll page and prepare for retry."""
        try:
            scroll_direction = kwargs.get("scroll_direction", "down")
            scroll_amount = kwargs.get("scroll_amount", 500)

            if scroll_direction == "down":
                await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            else:
                await page.evaluate(f"window.scrollBy(0, -{scroll_amount})")

            # Wait for potential dynamic content to load
            await asyncio.sleep(0.5)

            return FallbackResult(
                success=True,
                strategy_name=self.name,
                error_context=error_context,
                recovery_action="retry",
                recovery_params={},
                message=f"Scrolled {scroll_direction} by {scroll_amount}px",
                should_retry=True,
            )

        except Exception as e:
            logger.error(f"Scroll and retry fallback failed: {e}")
            return FallbackResult(
                success=False,
                strategy_name=self.name,
                error_context=error_context,
                message=f"Scroll error: {str(e)}",
                should_retry=False,
            )


class ExtendedWaitFallback(FallbackStrategy):
    """Fallback that waits longer for element to appear."""

    name = "extended_wait"
    priority = 15
    applicable_errors = [ErrorType.ELEMENT_NOT_FOUND, ErrorType.ACTION_TIMEOUT]
    max_attempts = 2

    def __init__(self, max_wait: float = 10.0):
        self.max_wait = max_wait

    async def can_handle(self, error_context: ErrorContext) -> bool:
        """Check if extended wait is applicable."""
        return error_context.error_type in self.applicable_errors

    async def execute(self, error_context: ErrorContext, page: Any, **kwargs) -> FallbackResult:
        """Wait for element with extended timeout."""
        try:
            selector = error_context.action_params.get("selector")
            wait_time = min(error_context.attempt_count * 3, self.max_wait)

            if selector:
                try:
                    await page.wait_for_selector(selector, timeout=wait_time * 1000)
                    return FallbackResult(
                        success=True,
                        strategy_name=self.name,
                        error_context=error_context,
                        recovery_action="retry",
                        recovery_params={},
                        message=f"Element appeared after {wait_time}s wait",
                    )
                except Exception:
                    pass

            # Generic wait if no selector or selector wait failed
            await asyncio.sleep(wait_time)

            return FallbackResult(
                success=True,
                strategy_name=self.name,
                error_context=error_context,
                recovery_action="retry",
                recovery_params={},
                message=f"Waited {wait_time}s for page state",
                should_retry=True,
            )

        except Exception as e:
            logger.error(f"Extended wait fallback failed: {e}")
            return FallbackResult(
                success=False,
                strategy_name=self.name,
                error_context=error_context,
                message=f"Wait error: {str(e)}",
                should_retry=False,
            )


class RefreshAndRetryFallback(FallbackStrategy):
    """Fallback that refreshes page and retries."""

    name = "refresh_and_retry"
    priority = 50
    applicable_errors = [ErrorType.STATE_MISMATCH, ErrorType.NETWORK_ERROR, ErrorType.RATE_LIMIT]
    max_attempts = 2

    async def can_handle(self, error_context: ErrorContext) -> bool:
        """Check if refresh is applicable."""
        return error_context.error_type in self.applicable_errors

    async def execute(self, error_context: ErrorContext, page: Any, **kwargs) -> FallbackResult:
        """Refresh page and prepare for retry."""
        try:
            # Wait before refresh
            await asyncio.sleep(2)

            # Refresh page
            await page.reload(wait_until="domcontentloaded", timeout=30000)

            # Wait for page to stabilize
            await asyncio.sleep(1)

            return FallbackResult(
                success=True,
                strategy_name=self.name,
                error_context=error_context,
                recovery_action="retry",
                recovery_params={},
                message="Page refreshed successfully",
                should_retry=True,
            )

        except Exception as e:
            logger.error(f"Refresh and retry fallback failed: {e}")
            return FallbackResult(
                success=False,
                strategy_name=self.name,
                error_context=error_context,
                message=f"Refresh error: {str(e)}",
                should_retry=False,
            )


class NavigationRetryFallback(FallbackStrategy):
    """Fallback that retries navigation."""

    name = "navigation_retry"
    priority = 30
    applicable_errors = [ErrorType.NAVIGATION_ERROR, ErrorType.NETWORK_ERROR]
    max_attempts = 3

    async def can_handle(self, error_context: ErrorContext) -> bool:
        """Check if navigation retry is applicable."""
        return error_context.error_type in self.applicable_errors

    async def execute(self, error_context: ErrorContext, page: Any, **kwargs) -> FallbackResult:
        """Retry navigation with exponential backoff."""
        try:
            url = error_context.action_params.get("url")
            if not url:
                url = error_context.page_url

            if not url:
                return FallbackResult(
                    success=False,
                    strategy_name=self.name,
                    error_context=error_context,
                    message="No URL to navigate to",
                    should_retry=False,
                )

            # Wait with exponential backoff
            delay = self.get_retry_delay(error_context.attempt_count)
            await asyncio.sleep(delay)

            # Retry navigation
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            return FallbackResult(
                success=True,
                strategy_name=self.name,
                error_context=error_context,
                recovery_action="none",
                recovery_params={},
                message=f"Navigation to {url} succeeded after {delay}s delay",
                should_retry=False,  # Navigation succeeded, no need to retry original action
            )

        except Exception as e:
            logger.error(f"Navigation retry fallback failed: {e}")
            return FallbackResult(
                success=False,
                strategy_name=self.name,
                error_context=error_context,
                message=f"Navigation retry error: {str(e)}",
                should_retry=True,
                next_strategy_hint="checkpoint_restore",
            )


class CheckpointRestoreFallback(FallbackStrategy):
    """Fallback that restores from checkpoint."""

    name = "checkpoint_restore"
    priority = 80
    applicable_errors = [ErrorType.STATE_MISMATCH, ErrorType.BROWSER_CRASH]
    max_attempts = 1

    def __init__(self, checkpoint_manager: Any):
        self.checkpoint_manager = checkpoint_manager

    async def can_handle(self, error_context: ErrorContext) -> bool:
        """Check if checkpoint restore is applicable."""
        if error_context.error_type not in self.applicable_errors:
            return False

        # Check if we have a checkpoint to restore
        latest = self.checkpoint_manager.get_latest_checkpoint()
        return latest is not None

    async def execute(self, error_context: ErrorContext, page: Any, **kwargs) -> FallbackResult:
        """Restore from last known good checkpoint."""
        try:
            # Get latest pre-action checkpoint
            from .checkpoint import CheckpointType

            checkpoint = self.checkpoint_manager.get_latest_checkpoint(CheckpointType.PRE_ACTION)

            if not checkpoint:
                checkpoint = self.checkpoint_manager.get_latest_checkpoint()

            if not checkpoint:
                return FallbackResult(
                    success=False,
                    strategy_name=self.name,
                    error_context=error_context,
                    message="No checkpoint available for restore",
                    should_abort=True,
                )

            # Restore checkpoint
            success = await self.checkpoint_manager.restore_checkpoint(page=page, checkpoint_id=checkpoint.id)

            if success:
                return FallbackResult(
                    success=True,
                    strategy_name=self.name,
                    error_context=error_context,
                    recovery_action="retry",
                    recovery_params={},
                    message=f"Restored to checkpoint {checkpoint.id}",
                    metadata={"checkpoint_id": checkpoint.id},
                )

            return FallbackResult(
                success=False,
                strategy_name=self.name,
                error_context=error_context,
                message="Failed to restore checkpoint",
                should_abort=True,
            )

        except Exception as e:
            logger.error(f"Checkpoint restore fallback failed: {e}")
            return FallbackResult(
                success=False,
                strategy_name=self.name,
                error_context=error_context,
                message=f"Checkpoint restore error: {str(e)}",
                should_abort=True,
            )


class FallbackManager:
    """
    Manages fallback strategies for error recovery.

    Features:
    - Error classification
    - Strategy registration and prioritization
    - Automatic strategy selection
    - Strategy execution with tracking
    - Fallback chain management
    """

    def __init__(self):
        """Initialize fallback manager."""
        self._strategies: Dict[str, FallbackStrategy] = {}
        self._error_history: List[ErrorContext] = []
        self._fallback_history: List[FallbackResult] = []
        self._max_history: int = 100

        # Error classification patterns
        self._error_patterns: Dict[ErrorType, List[str]] = {
            ErrorType.ELEMENT_NOT_FOUND: [
                "not found",
                "no element",
                "timeout waiting for selector",
                "waiting for selector",
            ],
            ErrorType.ACTION_TIMEOUT: [
                "timeout",
                "timed out",
                "action timeout",
            ],
            ErrorType.NAVIGATION_ERROR: [
                "navigation",
                "net::",
                "connection refused",
                "connection reset",
            ],
            ErrorType.SELECTOR_INVALID: [
                "invalid selector",
                "syntax error",
                "is not a valid selector",
            ],
            ErrorType.CAPTCHA_BLOCK: [
                "captcha",
                "recaptcha",
                "hcaptcha",
                "robot check",
            ],
            ErrorType.RATE_LIMIT: [
                "rate limit",
                "too many requests",
                "429",
            ],
            ErrorType.NETWORK_ERROR: [
                "network",
                "connection",
                "socket",
                "dns",
            ],
        }

    def register_strategy(self, strategy: FallbackStrategy) -> None:
        """Register a fallback strategy."""
        self._strategies[strategy.name] = strategy
        logger.info(f"Registered fallback strategy: {strategy.name} (priority={strategy.priority})")

    def unregister_strategy(self, name: str) -> None:
        """Unregister a fallback strategy."""
        if name in self._strategies:
            del self._strategies[name]
            logger.info(f"Unregistered fallback strategy: {name}")

    def get_strategy(self, name: str) -> Optional[FallbackStrategy]:
        """Get strategy by name."""
        return self._strategies.get(name)

    def get_all_strategies(self) -> List[FallbackStrategy]:
        """Get all strategies sorted by priority."""
        return sorted(self._strategies.values(), key=lambda s: s.priority)

    def classify_error(
        self,
        error: Exception,
        action_name: Optional[str] = None,
        action_params: Optional[Dict[str, Any]] = None,
        page_url: Optional[str] = None,
        screenshot: Optional[bytes] = None,
    ) -> ErrorContext:
        """Classify an error and create error context."""
        error_message = str(error).lower()
        error_type = ErrorType.UNKNOWN

        # Match error patterns
        for etype, patterns in self._error_patterns.items():
            for pattern in patterns:
                if pattern.lower() in error_message:
                    error_type = etype
                    break
            if error_type != ErrorType.UNKNOWN:
                break

        # Get previous errors for context
        previous_errors = [ctx.error_type for ctx in self._error_history[-5:]]

        context = ErrorContext(
            error_type=error_type,
            error_message=str(error),
            error_exception=error,
            action_name=action_name,
            action_params=action_params or {},
            page_url=page_url,
            screenshot=screenshot,
            previous_errors=previous_errors,
        )

        # Track error
        self._error_history.append(context)
        if len(self._error_history) > self._max_history:
            self._error_history = self._error_history[-self._max_history :]

        return context

    async def get_applicable_strategies(self, error_context: ErrorContext) -> List[FallbackStrategy]:
        """Get strategies that can handle the error, sorted by priority."""
        applicable = []

        for strategy in self.get_all_strategies():
            try:
                if await strategy.can_handle(error_context):
                    applicable.append(strategy)
            except Exception as e:
                logger.warning(f"Error checking strategy {strategy.name}: {e}")

        return applicable

    async def execute_fallback(
        self, error_context: ErrorContext, page: Any, strategy_name: Optional[str] = None, **kwargs
    ) -> FallbackResult:
        """
        Execute fallback strategy for error recovery.

        Args:
            error_context: Error context with classification
            page: Playwright page object
            strategy_name: Specific strategy to use (optional)
            **kwargs: Additional parameters for strategy

        Returns:
            FallbackResult with recovery instructions
        """
        # Get strategy to use
        if strategy_name:
            strategy = self._strategies.get(strategy_name)
            if not strategy:
                return FallbackResult(
                    success=False,
                    strategy_name="none",
                    error_context=error_context,
                    message=f"Strategy not found: {strategy_name}",
                    should_abort=True,
                )
        else:
            # Get best applicable strategy
            strategies = await self.get_applicable_strategies(error_context)
            if not strategies:
                return FallbackResult(
                    success=False,
                    strategy_name="none",
                    error_context=error_context,
                    message="No applicable fallback strategy found",
                    should_abort=True,
                )
            strategy = strategies[0]

        # Check attempt limit
        f"{strategy.name}_{error_context.error_type.value}"
        attempt_count = sum(1 for r in self._fallback_history if r.strategy_name == strategy.name)

        if attempt_count >= strategy.max_attempts:
            return FallbackResult(
                success=False,
                strategy_name=strategy.name,
                error_context=error_context,
                message=f"Max attempts ({strategy.max_attempts}) reached for {strategy.name}",
                should_retry=False,
                next_strategy_hint=self._get_next_strategy_hint(strategy.name, error_context),
            )

        # Execute strategy
        logger.info(f"Executing fallback strategy: {strategy.name} for {error_context.error_type.value}")

        try:
            result = await strategy.execute(error_context=error_context, page=page, **kwargs)

            # Track result
            self._fallback_history.append(result)
            if len(self._fallback_history) > self._max_history:
                self._fallback_history = self._fallback_history[-self._max_history :]

            return result

        except Exception as e:
            logger.error(f"Fallback strategy {strategy.name} failed: {e}")
            return FallbackResult(
                success=False,
                strategy_name=strategy.name,
                error_context=error_context,
                message=f"Strategy execution error: {str(e)}",
                should_retry=False,
            )

    def _get_next_strategy_hint(self, current_strategy: str, error_context: ErrorContext) -> Optional[str]:
        """Get hint for next strategy to try."""
        strategy_order = [s.name for s in self.get_all_strategies()]

        try:
            current_idx = strategy_order.index(current_strategy)
            if current_idx < len(strategy_order) - 1:
                return strategy_order[current_idx + 1]
        except ValueError:
            pass

        return None

    def get_error_history(self, limit: int = 10) -> List[ErrorContext]:
        """Get recent error history."""
        return self._error_history[-limit:]

    def get_fallback_history(self, limit: int = 10) -> List[FallbackResult]:
        """Get recent fallback history."""
        return self._fallback_history[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get fallback manager statistics."""
        error_counts = {}
        for ctx in self._error_history:
            etype = ctx.error_type.value
            error_counts[etype] = error_counts.get(etype, 0) + 1

        strategy_success = {}
        for result in self._fallback_history:
            name = result.strategy_name
            if name not in strategy_success:
                strategy_success[name] = {"success": 0, "failure": 0}
            if result.success:
                strategy_success[name]["success"] += 1
            else:
                strategy_success[name]["failure"] += 1

        return {
            "total_errors": len(self._error_history),
            "total_fallbacks": len(self._fallback_history),
            "error_types": error_counts,
            "strategy_success": strategy_success,
            "registered_strategies": list(self._strategies.keys()),
        }

    def clear_history(self) -> None:
        """Clear error and fallback history."""
        self._error_history.clear()
        self._fallback_history.clear()
        logger.info("Cleared fallback history")

"""
Recovery Orchestration for Browser Agent.

Coordinates automatic recovery on failure using checkpoint, fallback, and state stack systems.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging

from .checkpoint import CheckpointManager, Checkpoint, CheckpointType
from .fallback import FallbackManager, FallbackResult, ErrorContext, ErrorType
from .state_stack import StateStack

logger = logging.getLogger(__name__)


class RecoveryStatus(Enum):
    """Status of recovery operation."""

    SUCCESS = "success"  # Recovery successful
    PARTIAL = "partial"  # Partial recovery, may need manual intervention
    FAILED = "failed"  # Recovery failed
    ABORTED = "aborted"  # Recovery aborted (max attempts, etc.)
    MANUAL_REQUIRED = "manual_required"  # Manual intervention required


@dataclass
class RecoveryResult:
    """Result of a recovery operation."""

    status: RecoveryStatus
    error_context: ErrorContext
    recovery_strategy: str
    attempts: int
    restored_state_id: Optional[str] = None
    message: str = ""
    actions_taken: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "status": self.status.value,
            "recovery_strategy": self.recovery_strategy,
            "attempts": self.attempts,
            "restored_state_id": self.restored_state_id,
            "message": self.message,
            "actions_taken": self.actions_taken,
            "timestamp": self.timestamp,
        }


@dataclass
class RecoveryConfig:
    """Configuration for recovery behavior."""

    max_recovery_attempts: int = 3
    recovery_delay: float = 1.0
    use_checkpoints: bool = True
    use_state_stack: bool = True
    use_fallback_strategies: bool = True
    checkpoint_before_recovery: bool = True
    notify_on_manual_required: Optional[Callable[[RecoveryResult], None]] = None
    on_recovery_success: Optional[Callable[[RecoveryResult], None]] = None
    on_recovery_failure: Optional[Callable[[RecoveryResult], None]] = None


class RecoveryOrchestrator:
    """
    Orchestrates automatic recovery on failure.

    Features:
    - Automatic recovery on failure detection
    - Coordinated use of checkpoint, fallback, and state stack
    - Recovery strategy execution
    - Success verification
    - Manual intervention hooks
    - Graceful degradation options
    """

    def __init__(
        self,
        checkpoint_manager: CheckpointManager,
        fallback_manager: FallbackManager,
        state_stack: StateStack,
        config: Optional[RecoveryConfig] = None,
    ):
        """
        Initialize recovery orchestrator.

        Args:
            checkpoint_manager: Checkpoint manager instance
            fallback_manager: Fallback manager instance
            state_stack: State stack instance
            config: Recovery configuration
        """
        self.checkpoint_manager = checkpoint_manager
        self.fallback_manager = fallback_manager
        self.state_stack = state_stack
        self.config = config or RecoveryConfig()

        # Recovery tracking
        self._recovery_history: List[RecoveryResult] = []
        self._active_recovery: bool = False
        self._recovery_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0

        # Callbacks for manual intervention
        self._manual_intervention_callbacks: List[Callable[[RecoveryResult], None]] = []
        if self.config.notify_on_manual_required:
            self._manual_intervention_callbacks.append(self.config.notify_on_manual_required)

    def add_manual_intervention_callback(self, callback: Callable[[RecoveryResult], None]) -> None:
        """Add callback for manual intervention notifications."""
        self._manual_intervention_callbacks.append(callback)

    def remove_manual_intervention_callback(self, callback: Callable[[RecoveryResult], None]) -> None:
        """Remove manual intervention callback."""
        if callback in self._manual_intervention_callbacks:
            self._manual_intervention_callbacks.remove(callback)

    async def _notify_manual_intervention(self, result: RecoveryResult) -> None:
        """Notify callbacks about manual intervention requirement."""
        for callback in self._manual_intervention_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Manual intervention callback error: {e}")

    async def create_recovery_checkpoint(
        self,
        page: Any,
        error_context: ErrorContext,
    ) -> Optional[Checkpoint]:
        """Create checkpoint before recovery attempt."""
        if not self.config.use_checkpoints or not self.config.checkpoint_before_recovery:
            return None

        try:
            checkpoint = await self.checkpoint_manager.create_checkpoint(
                page=page,
                checkpoint_type=CheckpointType.RECOVERY,
                metadata={
                    "error_type": error_context.error_type.value,
                    "error_message": error_context.error_message,
                    "recovery_attempt": True,
                },
            )
            logger.info(f"Created recovery checkpoint: {checkpoint.id}")
            return checkpoint
        except Exception as e:
            logger.error(f"Failed to create recovery checkpoint: {e}")
            return None

    async def attempt_checkpoint_restore(
        self,
        page: Any,
        error_context: ErrorContext,
    ) -> Tuple[bool, Optional[str]]:
        """
        Attempt to restore from checkpoint.

        Returns:
            Tuple of (success, checkpoint_id)
        """
        if not self.config.use_checkpoints:
            return False, None

        # Get best checkpoint to restore
        checkpoint = self.checkpoint_manager.get_latest_checkpoint(CheckpointType.PRE_ACTION)

        if not checkpoint:
            checkpoint = self.checkpoint_manager.get_latest_checkpoint()

        if not checkpoint:
            logger.warning("No checkpoint available for restore")
            return False, None

        # Attempt restore
        success = await self.checkpoint_manager.restore_checkpoint(
            page=page,
            checkpoint_id=checkpoint.id,
        )

        if success:
            logger.info(f"Restored from checkpoint: {checkpoint.id}")
            return True, checkpoint.id

        return False, None

    async def attempt_state_stack_rollback(
        self,
        page: Any,
        steps: int = 1,
    ) -> Tuple[bool, Optional[str]]:
        """
        Attempt rollback using state stack.

        Returns:
            Tuple of (success, frame_id)
        """
        if not self.config.use_state_stack:
            return False, None

        if self.state_stack.is_empty():
            logger.warning("State stack is empty, cannot rollback")
            return False, None

        # Rollback
        frame = self.state_stack.rollback(steps)

        if frame:
            # Restore browser state from frame
            try:
                # Navigate to URL
                if page.url != frame.state.url:
                    await page.goto(frame.state.url, wait_until="domcontentloaded")

                # Restore scroll
                await page.evaluate(f"window.scrollTo({frame.state.scroll_x}, {frame.state.scroll_y})")

                logger.info(f"Rolled back to frame: {frame.id}")
                return True, frame.id
            except Exception as e:
                logger.error(f"Failed to restore frame state: {e}")
                return False, None

        return False, None

    async def execute_fallback_strategy(
        self,
        page: Any,
        error_context: ErrorContext,
    ) -> FallbackResult:
        """Execute fallback strategy for error."""
        if not self.config.use_fallback_strategies:
            return FallbackResult(
                success=False,
                strategy_name="none",
                error_context=error_context,
                message="Fallback strategies disabled",
                should_abort=True,
            )

        return await self.fallback_manager.execute_fallback(
            error_context=error_context,
            page=page,
        )

    async def verify_recovery(
        self,
        page: Any,
        error_context: ErrorContext,
    ) -> bool:
        """
        Verify that recovery was successful.

        Checks if the page is in a usable state.
        """
        try:
            # Check page is responsive
            url = page.url
            if not url or url == "about:blank":
                return False

            # Check for error indicators
            page_content = await page.content()
            error_indicators = [
                "404 not found",
                "500 internal server error",
                "connection refused",
                "access denied",
            ]

            content_lower = page_content.lower()
            for indicator in error_indicators:
                if indicator in content_lower:
                    return False

            # If original error was element not found, check if element exists now
            if error_context.error_type == ErrorType.ELEMENT_NOT_FOUND:
                selector = error_context.action_params.get("selector")
                if selector:
                    try:
                        element = await page.wait_for_selector(selector, timeout=1000)
                        return element is not None
                    except Exception:
                        return False

            return True

        except Exception as e:
            logger.error(f"Recovery verification failed: {e}")
            return False

    async def recover(
        self,
        error: Exception,
        page: Any,
        action_name: Optional[str] = None,
        action_params: Optional[Dict[str, Any]] = None,
        max_attempts: Optional[int] = None,
    ) -> RecoveryResult:
        """
        Main recovery entry point.

        Args:
            error: The error that occurred
            page: Playwright page object
            action_name: Name of action that failed
            action_params: Parameters of failed action
            max_attempts: Maximum recovery attempts (uses config if not provided)

        Returns:
            RecoveryResult with recovery status and details
        """
        if self._active_recovery:
            logger.warning("Recovery already in progress, aborting new recovery")
            return RecoveryResult(
                status=RecoveryStatus.ABORTED,
                error_context=self.fallback_manager.classify_error(error),
                recovery_strategy="none",
                attempts=0,
                message="Recovery already in progress",
            )

        self._active_recovery = True
        self._recovery_count += 1

        max_attempts = max_attempts or self.config.max_recovery_attempts

        # Classify error
        try:
            page_url = page.url
        except Exception:
            page_url = None

        error_context = self.fallback_manager.classify_error(
            error=error,
            action_name=action_name,
            action_params=action_params,
            page_url=page_url,
        )

        logger.info(f"Starting recovery for {error_context.error_type.value}: {error_context.error_message}")

        # Track recovery attempts
        attempts = 0
        actions_taken: List[str] = []

        try:
            # Create recovery checkpoint
            await self.create_recovery_checkpoint(page, error_context)

            while attempts < max_attempts:
                attempts += 1
                logger.info(f"Recovery attempt {attempts}/{max_attempts}")

                # Strategy 1: Fallback strategies
                fallback_result = await self.execute_fallback_strategy(page, error_context)
                actions_taken.append(f"fallback:{fallback_result.strategy_name}")

                if fallback_result.success:
                    # Verify recovery
                    if await self.verify_recovery(page, error_context):
                        self._success_count += 1
                        result = RecoveryResult(
                            status=RecoveryStatus.SUCCESS,
                            error_context=error_context,
                            recovery_strategy=f"fallback:{fallback_result.strategy_name}",
                            attempts=attempts,
                            message=f"Recovery successful via {fallback_result.strategy_name}",
                            actions_taken=actions_taken,
                            metadata={"fallback_result": fallback_result.to_dict()},
                        )
                        self._recovery_history.append(result)

                        if self.config.on_recovery_success:
                            self.config.on_recovery_success(result)

                        return result

                # Strategy 2: State stack rollback
                if self.config.use_state_stack and not self.state_stack.is_empty():
                    success, frame_id = await self.attempt_state_stack_rollback(page)
                    actions_taken.append(f"state_stack_rollback:{frame_id}")

                    if success:
                        if await self.verify_recovery(page, error_context):
                            self._success_count += 1
                            result = RecoveryResult(
                                status=RecoveryStatus.SUCCESS,
                                error_context=error_context,
                                recovery_strategy="state_stack_rollback",
                                attempts=attempts,
                                restored_state_id=frame_id,
                                message="Recovery successful via state stack rollback",
                                actions_taken=actions_taken,
                            )
                            self._recovery_history.append(result)

                            if self.config.on_recovery_success:
                                self.config.on_recovery_success(result)

                            return result

                # Strategy 3: Checkpoint restore
                if self.config.use_checkpoints:
                    success, checkpoint_id = await self.attempt_checkpoint_restore(page, error_context)
                    actions_taken.append(f"checkpoint_restore:{checkpoint_id}")

                    if success:
                        if await self.verify_recovery(page, error_context):
                            self._success_count += 1
                            result = RecoveryResult(
                                status=RecoveryStatus.SUCCESS,
                                error_context=error_context,
                                recovery_strategy="checkpoint_restore",
                                attempts=attempts,
                                restored_state_id=checkpoint_id,
                                message="Recovery successful via checkpoint restore",
                                actions_taken=actions_taken,
                            )
                            self._recovery_history.append(result)

                            if self.config.on_recovery_success:
                                self.config.on_recovery_success(result)

                            return result

                # Wait before next attempt
                if attempts < max_attempts:
                    delay = self.config.recovery_delay * (2 ** (attempts - 1))
                    await asyncio.sleep(delay)

            # All recovery attempts failed
            self._failure_count += 1
            result = RecoveryResult(
                status=RecoveryStatus.FAILED,
                error_context=error_context,
                recovery_strategy="exhausted",
                attempts=attempts,
                message=f"Recovery failed after {attempts} attempts",
                actions_taken=actions_taken,
            )
            self._recovery_history.append(result)

            # Notify manual intervention required
            await self._notify_manual_intervention(result)

            if self.config.on_recovery_failure:
                self.config.on_recovery_failure(result)

            return result

        except Exception as e:
            logger.error(f"Recovery orchestration error: {e}")
            self._failure_count += 1
            result = RecoveryResult(
                status=RecoveryStatus.ABORTED,
                error_context=error_context,
                recovery_strategy="error",
                attempts=attempts,
                message=f"Recovery aborted due to error: {str(e)}",
                actions_taken=actions_taken,
            )
            self._recovery_history.append(result)
            return result

        finally:
            self._active_recovery = False

    async def graceful_degradation(
        self,
        page: Any,
        error_context: ErrorContext,
        fallback_action: Optional[str] = None,
        fallback_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """
        Attempt graceful degradation when full recovery fails.

        Args:
            page: Playwright page object
            error_context: Error context
            fallback_action: Alternative action to try
            fallback_params: Parameters for fallback action

        Returns:
            Tuple of (success, message)
        """
        logger.info("Attempting graceful degradation")

        # Option 1: Skip current step and continue
        if error_context.error_type == ErrorType.ELEMENT_NOT_FOUND:
            return True, "Skipped unavailable element, continuing with task"

        # Option 2: Use alternative action
        if fallback_action:
            return True, f"Using fallback action: {fallback_action}"

        # Option 3: Navigate to safe state
        try:
            # Go to homepage or last known good URL
            checkpoint = self.checkpoint_manager.get_latest_checkpoint()
            if checkpoint:
                await page.goto(checkpoint.state.url, wait_until="domcontentloaded")
                return True, f"Navigated to last known good URL: {checkpoint.state.url}"
        except Exception:
            pass

        # Option 4: Refresh page
        try:
            await page.reload(wait_until="domcontentloaded")
            return True, "Page refreshed as graceful degradation"
        except Exception:
            pass

        return False, "Graceful degradation failed"

    def get_recovery_history(self, limit: int = 10) -> List[RecoveryResult]:
        """Get recent recovery history."""
        return self._recovery_history[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get recovery orchestrator statistics."""
        success_rate = self._success_count / self._recovery_count * 100 if self._recovery_count > 0 else 0

        return {
            "total_recoveries": self._recovery_count,
            "successful_recoveries": self._success_count,
            "failed_recoveries": self._failure_count,
            "success_rate": success_rate,
            "active_recovery": self._active_recovery,
            "history_size": len(self._recovery_history),
            "config": {
                "max_recovery_attempts": self.config.max_recovery_attempts,
                "use_checkpoints": self.config.use_checkpoints,
                "use_state_stack": self.config.use_state_stack,
                "use_fallback_strategies": self.config.use_fallback_strategies,
            },
        }

    def clear_history(self) -> None:
        """Clear recovery history."""
        self._recovery_history.clear()
        logger.info("Cleared recovery history")

    def is_recovering(self) -> bool:
        """Check if recovery is in progress."""
        return self._active_recovery

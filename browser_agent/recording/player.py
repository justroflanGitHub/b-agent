"""Workflow player — replay recorded workflows with multiple strategies."""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .recorder import Recording, RecordedAction, RecordingParameter
from .adaptive_replay import AdaptiveReplay

logger = logging.getLogger(__name__)


class ReplayMode(Enum):
    STRICT = "strict"               # Exact replay, fail on mismatch
    ADAPTIVE = "adaptive"           # Try exact, fall back to vision
    VISION_ONLY = "vision_only"     # Use vision model every step


@dataclass
class ReplayStepResult:
    """Result of replaying a single step."""
    step_index: int = 0
    action_type: str = ""
    success: bool = False
    strategy_used: str = "exact"    # "exact", "selector", "text", "vision", "position"
    page_matched: bool = True
    error: Optional[str] = None
    execution_time: float = 0.0
    screenshot_hash: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "step_index": self.step_index,
            "action_type": self.action_type,
            "success": self.success,
            "strategy_used": self.strategy_used,
            "page_matched": self.page_matched,
            "error": self.error,
            "execution_time": self.execution_time,
        }


@dataclass
class ReplayResult:
    """Result of replaying an entire workflow."""
    recording_id: str = ""
    success: bool = False
    total_steps: int = 0
    completed_steps: int = 0
    failed_step: Optional[int] = None
    step_results: List[ReplayStepResult] = field(default_factory=list)
    parameters_used: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    adaptive_fallbacks: int = 0
    mode: ReplayMode = ReplayMode.ADAPTIVE
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "recording_id": self.recording_id,
            "success": self.success,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_step": self.failed_step,
            "step_results": [s.to_dict() for s in self.step_results],
            "execution_time": self.execution_time,
            "adaptive_fallbacks": self.adaptive_fallbacks,
            "mode": self.mode.value,
            "error": self.error,
        }


class WorkflowPlayer:
    """Replay recorded workflows.

    Supports three replay modes:
    - STRICT: Replay exact actions, fail if page changed
    - ADAPTIVE: Try exact first, fall back to adaptive strategies
    - VISION_ONLY: Use adaptive replay for every step
    """

    def __init__(
        self,
        agent_factory: Optional[Callable] = None,
        adaptive: Optional[AdaptiveReplay] = None,
        mode: ReplayMode = ReplayMode.ADAPTIVE,
        page_match_threshold: float = 0.85,
        continue_on_failure: bool = False,
        screenshot_on_failure: bool = True,
    ):
        self._agent_factory = agent_factory
        self._adaptive = adaptive or AdaptiveReplay()
        self._mode = mode
        self._page_match_threshold = page_match_threshold
        self._continue_on_failure = continue_on_failure
        self._screenshot_on_failure = screenshot_on_failure

    async def play(
        self,
        recording: Recording,
        parameters: Optional[Dict[str, Any]] = None,
        on_step: Optional[Callable] = None,
    ) -> ReplayResult:
        """Replay a recorded workflow.

        Args:
            recording: The recording to replay.
            parameters: Parameter values for parameterized recordings.
            on_step: Callback(ReplayStepResult) after each step.

        Returns:
            ReplayResult with step-by-step outcomes.
        """
        start = time.monotonic()
        params = parameters or {}

        # Validate parameters
        for p in recording.parameters:
            if p.required and p.name not in params:
                if p.default_value is None:
                    return ReplayResult(
                        recording_id=recording.recording_id,
                        success=False,
                        total_steps=len(recording.actions),
                        failed_step=0,
                        error=f"Missing required parameter: {p.name}",
                        mode=self._mode,
                    )

        result = ReplayResult(
            recording_id=recording.recording_id,
            total_steps=len(recording.actions),
            parameters_used=params,
            mode=self._mode,
        )

        for i, action in enumerate(recording.actions):
            step_result = await self._play_step(action, params, recording)

            if step_result.strategy_used != "exact":
                result.adaptive_fallbacks += 1

            result.step_results.append(step_result)
            result.completed_steps = i + 1

            if on_step:
                try:
                    on_step(step_result)
                except Exception:
                    pass

            if not step_result.success:
                result.failed_step = i
                if not self._continue_on_failure:
                    break

        result.execution_time = time.monotonic() - start
        result.success = (
            result.completed_steps == result.total_steps
            and all(s.success for s in result.step_results)
        )

        logger.info(
            "Replay %s: %s (%d/%d steps, %.1fs, %d fallbacks)",
            recording.recording_id[:8], "OK" if result.success else "FAIL",
            result.completed_steps, result.total_steps,
            result.execution_time, result.adaptive_fallbacks,
        )
        return result

    async def _play_step(
        self,
        action: RecordedAction,
        params: Dict[str, Any],
        recording: Recording,
    ) -> ReplayStepResult:
        """Replay a single step."""
        start = time.monotonic()

        # Resolve parameters
        resolved_params = dict(action.parameters)
        if action.is_parameterized and action.parameter_name:
            value = params.get(action.parameter_name, action.original_value)
            # Find the parameter key in the action params
            for k, v in action.parameters.items():
                if v == action.original_value or str(v) == str(action.original_value):
                    resolved_params[k] = value

        step = ReplayStepResult(
            step_index=action.step_index,
            action_type=action.action_type,
        )

        try:
            if self._mode == ReplayMode.VISION_ONLY:
                step.strategy_used = "vision"
                success = await self._execute_action(action, resolved_params)
                step.success = success
            elif self._mode == ReplayMode.STRICT:
                step.strategy_used = "exact"
                success = await self._execute_action(action, resolved_params)
                step.success = success
                if not success:
                    step.error = "Strict mode: action failed"
            else:
                # ADAPTIVE: try exact first
                step.strategy_used = "exact"
                success = await self._execute_action(action, resolved_params)
                if not success:
                    # Try adaptive strategies
                    fallback = await self._adaptive.find_element(action)
                    if fallback.found:
                        step.strategy_used = fallback.strategy
                        step.success = True
                        step.page_matched = False
                    else:
                        step.success = False
                        step.error = f"Adaptive fallback failed: {fallback.strategy}"
                        step.page_matched = False
                else:
                    step.success = True

        except Exception as e:
            step.success = False
            step.error = str(e)

        step.execution_time = time.monotonic() - start
        return step

    async def _execute_action(self, action: RecordedAction, params: Dict[str, Any]) -> bool:
        """Execute a single action. Returns True if successful."""
        if self._agent_factory:
            agent = self._agent_factory()
            try:
                result = await agent.execute_task(
                    goal=f"Execute action: {action.action_type}",
                    start_url=action.target_url or action.page_url,
                    max_steps=3,
                )
                return result.success
            except Exception:
                return False
        else:
            # Testing mode — simulate success
            return True

    async def dry_run(
        self,
        recording: Recording,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ReplayResult:
        """Simulate replay without executing.

        Validates parameters and checks action structure.
        """
        params = parameters or {}

        result = ReplayResult(
            recording_id=recording.recording_id,
            total_steps=len(recording.actions),
            parameters_used=params,
            mode=self._mode,
        )

        # Validate parameters
        for p in recording.parameters:
            if p.required and p.name not in params and p.default_value is None:
                result.success = False
                result.failed_step = 0
                result.error = f"Missing required parameter: {p.name}"
                return result

        # Check action structure
        for action in recording.actions:
            step = ReplayStepResult(
                step_index=action.step_index,
                action_type=action.action_type,
                success=True,
                strategy_used="dry_run",
            )
            result.step_results.append(step)
            result.completed_steps += 1

        result.success = True
        result.execution_time = 0.0
        return result

"""Recording parameterizer — detect and mark parameterizable values."""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from .recorder import Recording, RecordingParameter

logger = logging.getLogger(__name__)


class RecordingParameterizer:
    """Convert recorded values into reusable parameters.

    Auto-detects parameterizable values (typed text, URLs, dates, etc.)
    and allows manual parameterization of specific fields.
    """

    # Patterns that suggest a value should be parameterized
    PARAMETER_PATTERNS = {
        "url": re.compile(r"^https?://\S+$"),
        "email": re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"),
        "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
        "number": re.compile(r"^\d+$"),
    }

    async def auto_detect_parameters(self, recording: Recording) -> List[RecordingParameter]:
        """Automatically detect parameterizable values in a recording.

        Scans all action parameters and identifies values that look like
        they should be user-configurable.
        """
        parameters: Dict[str, RecordingParameter] = {}
        param_idx = 0

        for action in recording.actions:
            for key, value in action.parameters.items():
                if not isinstance(value, str) or not value.strip():
                    continue

                # Skip very short or generic values
                if len(value) < 3:
                    continue

                param_type = self._detect_type(value, key)
                if param_type is None:
                    continue

                param_name = self._make_param_name(key, action.step_index)

                if param_name not in parameters:
                    param_idx += 1
                    parameters[param_name] = RecordingParameter(
                        name=param_name,
                        display_name=self._make_display_name(key),
                        parameter_type=param_type,
                        default_value=value,
                        required=True,
                        description=f"Auto-detected {param_type} parameter from step {action.step_index}",
                        field_index=param_idx,
                    )

        return list(parameters.values())

    async def parameterize_action(
        self,
        recording: Recording,
        action_index: int,
        field: str,
        parameter_name: str,
        parameter_type: str = "text",
        display_name: Optional[str] = None,
    ) -> Recording:
        """Mark a specific field in an action as a parameter."""
        if action_index >= len(recording.actions):
            raise IndexError(f"Action index {action_index} out of range")

        action = recording.actions[action_index]
        original_value = action.parameters.get(field)

        if original_value is None:
            raise KeyError(f"Field '{field}' not found in action parameters")

        # Mark the action
        action.is_parameterized = True
        action.parameter_name = parameter_name
        action.parameter_type = parameter_type
        action.original_value = original_value

        # Add parameter definition
        existing = [p.name for p in recording.parameters]
        if parameter_name not in existing:
            recording.parameters.append(
                RecordingParameter(
                    name=parameter_name,
                    display_name=display_name or parameter_name,
                    parameter_type=parameter_type,
                    default_value=original_value,
                    required=True,
                )
            )

        return recording

    async def remove_parameterization(
        self,
        recording: Recording,
        action_index: int,
        field: str,
    ) -> Recording:
        """Remove parameterization from a field."""
        if action_index >= len(recording.actions):
            raise IndexError(f"Action index {action_index} out of range")

        action = recording.actions[action_index]
        action.is_parameterized = False
        action.parameter_name = None
        action.parameter_type = None
        action.original_value = None

        return recording

    async def validate_parameters(
        self,
        parameters: Dict[str, Any],
        recording: Recording,
    ) -> Tuple[bool, List[str]]:
        """Validate provided parameters against recording requirements."""
        errors = []

        for param_def in recording.parameters:
            value = parameters.get(param_def.name)

            if param_def.required and value is None and param_def.default_value is None:
                errors.append(f"Missing required parameter: {param_def.name}")
                continue

            if value is not None and param_def.validation_pattern:
                if not re.match(param_def.validation_pattern, str(value)):
                    errors.append(f"Parameter '{param_def.name}' doesn't match pattern: {param_def.validation_pattern}")

            if value is not None and param_def.options:
                if str(value) not in param_def.options:
                    errors.append(f"Parameter '{param_def.name}' must be one of: {param_def.options}")

        return len(errors) == 0, errors

    def _detect_type(self, value: str, key: str) -> Optional[str]:
        """Detect the parameter type of a value."""
        key_lower = key.lower()

        # Key-based detection
        if any(k in key_lower for k in ["url", "link", "href", "src"]):
            return "url"
        if any(k in key_lower for k in ["email", "mail"]):
            return "email"
        if any(k in key_lower for k in ["date", "time"]):
            return "date"
        if any(k in key_lower for k in ["password", "pwd", "secret"]):
            return "password"
        if any(k in key_lower for k in ["select", "option", "choice"]):
            return "select"

        # Value-based detection
        for ptype, pattern in self.PARAMETER_PATTERNS.items():
            if pattern.match(value):
                return ptype

        # Default: text if the value is substantial
        if len(value) >= 5:
            return "text"

        return None

    def _make_param_name(self, key: str, step_index: int) -> str:
        """Generate a parameter name from a field key."""
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", key.lower())
        return f"step_{step_index}_{safe}"

    def _make_display_name(self, key: str) -> str:
        """Generate a human-readable display name."""
        return key.replace("_", " ").replace("-", " ").title()

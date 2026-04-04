"""
Proactive Error Prevention System - Detect and prevent errors before they occur.

Provides:
- Anomaly detection in page behavior
- Heuristic-based warning system
- Automatic screenshot on suspicious states
- Pre-action risk assessment
"""

import hashlib
import logging
import time
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable, Tuple
from pathlib import Path
from enum import Enum
import math

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================


class RiskLevel(Enum):
    """Risk level for actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(Enum):
    """Types of anomalies."""

    PAGE_LOAD = "page_load"
    ELEMENT_MISSING = "element_missing"
    UNEXPECTED_REDIRECT = "unexpected_redirect"
    POPUP_DETECTED = "popup_detected"
    ERROR_MESSAGE = "error_message"
    SLOW_RESPONSE = "slow_response"
    CONTENT_CHANGE = "content_change"
    BEHAVIOR_DEVIATION = "behavior_deviation"


class WarningType(Enum):
    """Types of warnings."""

    NAVIGATION_RISK = "navigation_risk"
    ACTION_UNSTABLE = "action_unstable"
    STATE_UNFAMILIAR = "state_unfamiliar"
    ELEMENT_AMBIGUOUS = "element_ambiguous"
    FORM_VALIDATION = "form_validation"
    RATE_LIMIT = "rate_limit"


@dataclass
class Anomaly:
    """Detected anomaly."""

    anomaly_type: AnomalyType
    severity: RiskLevel
    description: str
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)
    screenshot_hash: Optional[str] = None
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "timestamp": self.timestamp,
            "context": self.context,
            "screenshot_hash": self.screenshot_hash,
            "resolved": self.resolved,
        }


@dataclass
class Warning:
    """Generated warning."""

    warning_type: WarningType
    risk_level: RiskLevel
    message: str
    recommendation: str
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)
    dismissed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "warning_type": self.warning_type.value,
            "risk_level": self.risk_level.value,
            "message": self.message,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp,
            "context": self.context,
            "dismissed": self.dismissed,
        }


@dataclass
class RiskAssessment:
    """Risk assessment for an action."""

    action_type: str
    overall_risk: RiskLevel
    risk_score: float  # 0-1
    factors: List[Dict[str, Any]]
    recommendations: List[str]
    should_proceed: bool
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_type": self.action_type,
            "overall_risk": self.overall_risk.value,
            "risk_score": self.risk_score,
            "factors": self.factors,
            "recommendations": self.recommendations,
            "should_proceed": self.should_proceed,
            "timestamp": self.timestamp,
        }


@dataclass
class SuspiciousState:
    """Recorded suspicious state."""

    state_hash: str
    screenshot_path: Optional[str]
    anomalies: List[Anomaly]
    warnings: List[Warning]
    timestamp: float = field(default_factory=time.time)
    reviewed: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "state_hash": self.state_hash,
            "screenshot_path": self.screenshot_path,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "warnings": [w.to_dict() for w in self.warnings],
            "timestamp": self.timestamp,
            "reviewed": self.reviewed,
            "notes": self.notes,
        }


@dataclass
class BehaviorBaseline:
    """Baseline for normal behavior."""

    metric_name: str
    mean: float
    std_dev: float
    sample_count: int
    min_value: float
    max_value: float
    last_updated: float = field(default_factory=time.time)

    def is_within_normal(self, value: float, z_score_threshold: float = 2.0) -> bool:
        """Check if value is within normal range."""
        if self.std_dev == 0:
            return value == self.mean

        z_score = abs(value - self.mean) / self.std_dev
        return z_score <= z_score_threshold

    def update(self, new_value: float):
        """Update baseline with new value."""
        # Online update of mean and std dev
        old_mean = self.mean
        self.sample_count += 1
        self.mean = old_mean + (new_value - old_mean) / self.sample_count

        if self.sample_count > 1:
            old_variance = self.std_dev**2
            new_variance = (
                old_variance + ((new_value - old_mean) * (new_value - self.mean) - old_variance) / self.sample_count
            )
            self.std_dev = math.sqrt(max(0, new_variance))

        self.min_value = min(self.min_value, new_value)
        self.max_value = max(self.max_value, new_value)
        self.last_updated = time.time()


# ============================================================================
# Anomaly Detector
# ============================================================================


class AnomalyDetector:
    """
    Detects anomalies in page behavior.

    Features:
    - Baseline learning for normal behavior
    - Statistical anomaly detection
    - Pattern-based detection
    - Configurable thresholds
    """

    def __init__(self, learning_mode: bool = True, z_score_threshold: float = 2.5, max_baselines: int = 100):
        """
        Initialize anomaly detector.

        Args:
            learning_mode: Whether to learn baselines from observations
            z_score_threshold: Z-score threshold for anomaly detection
            max_baselines: Maximum baselines to maintain
        """
        self.learning_mode = learning_mode
        self.z_score_threshold = z_score_threshold
        self.max_baselines = max_baselines

        self._baselines: Dict[str, BehaviorBaseline] = {}
        self._detected_anomalies: List[Anomaly] = []
        self._page_history: OrderedDict[str, List[Dict[str, Any]]] = OrderedDict()

    def observe_page_metrics(
        self, url: str, metrics: Dict[str, float], screenshot_hash: Optional[str] = None
    ) -> List[Anomaly]:
        """
        Observe page metrics and detect anomalies.

        Args:
            url: Page URL
            metrics: Dictionary of metric name -> value
            screenshot_hash: Optional screenshot hash

        Returns:
            List of detected anomalies
        """
        anomalies = []

        for metric_name, value in metrics.items():
            baseline_key = f"{url}:{metric_name}"

            if baseline_key in self._baselines:
                baseline = self._baselines[baseline_key]

                # Check for anomaly
                if not baseline.is_within_normal(value, self.z_score_threshold):
                    anomaly = Anomaly(
                        anomaly_type=AnomalyType.BEHAVIOR_DEVIATION,
                        severity=self._determine_severity(baseline, value),
                        description=f"Metric '{metric_name}' deviates from baseline: {value} vs mean {baseline.mean:.2f}",
                        context={
                            "metric_name": metric_name,
                            "value": value,
                            "baseline_mean": baseline.mean,
                            "baseline_std": baseline.std_dev,
                        },
                        screenshot_hash=screenshot_hash,
                    )
                    anomalies.append(anomaly)
                    self._detected_anomalies.append(anomaly)

                # Update baseline if in learning mode
                if self.learning_mode:
                    baseline.update(value)

            elif self.learning_mode:
                # Create new baseline
                self._baselines[baseline_key] = BehaviorBaseline(
                    metric_name=metric_name, mean=value, std_dev=0, sample_count=1, min_value=value, max_value=value
                )

                # Evict old baselines if at capacity
                if len(self._baselines) > self.max_baselines:
                    oldest_key = min(self._baselines.keys(), key=lambda k: self._baselines[k].last_updated)
                    del self._baselines[oldest_key]

        # Store in page history
        if url not in self._page_history:
            self._page_history[url] = []
        self._page_history[url].append({"timestamp": time.time(), "metrics": metrics, "anomalies": len(anomalies)})

        # Limit history size
        if len(self._page_history[url]) > 100:
            self._page_history[url] = self._page_history[url][-100:]

        return anomalies

    def _determine_severity(self, baseline: BehaviorBaseline, value: float) -> RiskLevel:
        """Determine severity of deviation."""
        if baseline.std_dev == 0:
            return RiskLevel.MEDIUM

        z_score = abs(value - baseline.mean) / baseline.std_dev

        if z_score > 4:
            return RiskLevel.CRITICAL
        elif z_score > 3:
            return RiskLevel.HIGH
        elif z_score > 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def detect_element_anomaly(
        self, selector: str, expected_present: bool, actual_present: bool, context: Dict[str, Any] = None
    ) -> Optional[Anomaly]:
        """Detect element presence anomaly."""
        if expected_present != actual_present:
            return Anomaly(
                anomaly_type=AnomalyType.ELEMENT_MISSING,
                severity=RiskLevel.HIGH if expected_present else RiskLevel.MEDIUM,
                description=f"Element '{selector}' {'missing' if expected_present else 'unexpectedly present'}",
                context=context or {},
            )
        return None

    def detect_redirect_anomaly(
        self, expected_url: str, actual_url: str, context: Dict[str, Any] = None
    ) -> Optional[Anomaly]:
        """Detect unexpected redirect."""
        if expected_url != actual_url:
            return Anomaly(
                anomaly_type=AnomalyType.UNEXPECTED_REDIRECT,
                severity=RiskLevel.HIGH,
                description=f"Unexpected redirect from {expected_url} to {actual_url}",
                context=context or {},
            )
        return None

    def detect_popup_anomaly(
        self, popup_detected: bool, popup_type: str = "unknown", context: Dict[str, Any] = None
    ) -> Optional[Anomaly]:
        """Detect popup anomaly."""
        if popup_detected:
            return Anomaly(
                anomaly_type=AnomalyType.POPUP_DETECTED,
                severity=RiskLevel.MEDIUM,
                description=f"Popup detected: {popup_type}",
                context=context or {},
            )
        return None

    def detect_error_message(self, error_text: str, context: Dict[str, Any] = None) -> Optional[Anomaly]:
        """Detect error message on page."""
        # Common error patterns
        error_patterns = ["error", "failed", "invalid", "not found", "access denied", "forbidden", "unauthorized"]

        error_lower = error_text.lower()
        if any(pattern in error_lower for pattern in error_patterns):
            return Anomaly(
                anomaly_type=AnomalyType.ERROR_MESSAGE,
                severity=RiskLevel.HIGH,
                description=f"Error message detected: {error_text[:100]}",
                context=context or {},
            )
        return None

    def get_recent_anomalies(self, count: int = 10, severity: Optional[RiskLevel] = None) -> List[Anomaly]:
        """Get recent anomalies."""
        anomalies = self._detected_anomalies

        if severity:
            anomalies = [a for a in anomalies if a.severity == severity]

        return anomalies[-count:]

    def get_baseline_stats(self) -> Dict[str, Any]:
        """Get baseline statistics."""
        return {
            "total_baselines": len(self._baselines),
            "tracked_pages": len(self._page_history),
            "total_anomalies": len(self._detected_anomalies),
            "learning_mode": self.learning_mode,
        }

    def clear_anomalies(self):
        """Clear detected anomalies."""
        self._detected_anomalies.clear()


# ============================================================================
# Heuristic Warning System
# ============================================================================


class HeuristicWarningSystem:
    """
    Generates warnings based on heuristics.

    Features:
    - Action stability analysis
    - Navigation risk assessment
    - Form validation warnings
    - Rate limit detection
    """

    def __init__(self, action_history_size: int = 100, warning_cooldown: float = 5.0):
        """
        Initialize warning system.

        Args:
            action_history_size: Size of action history to analyze
            warning_cooldown: Seconds between similar warnings
        """
        self.action_history_size = action_history_size
        self.warning_cooldown = warning_cooldown

        self._action_history: List[Dict[str, Any]] = []
        self._generated_warnings: List[Warning] = []
        self._last_warning_time: Dict[str, float] = {}

        # Initialize heuristics
        self._heuristics: List[Callable[[Dict[str, Any]], Optional[Warning]]] = [
            self._check_navigation_risk,
            self._check_action_stability,
            self._check_form_validation,
            self._check_rate_limit,
            self._check_element_ambiguity,
        ]

    def record_action(self, action: Dict[str, Any], result: Dict[str, Any]):
        """Record action and result."""
        self._action_history.append({"action": action, "result": result, "timestamp": time.time()})

        # Limit history size
        if len(self._action_history) > self.action_history_size:
            self._action_history = self._action_history[-self.action_history_size :]

    def check_action(self, action: Dict[str, Any], context: Dict[str, Any] = None) -> List[Warning]:
        """
        Check action against heuristics.

        Args:
            action: Proposed action
            context: Additional context

        Returns:
            List of warnings
        """
        warnings = []

        check_context = {**(context or {}), "action": action, "history": self._action_history}

        for heuristic in self._heuristics:
            warning = heuristic(check_context)
            if warning:
                # Check cooldown
                warning_key = f"{warning.warning_type.value}"
                last_time = self._last_warning_time.get(warning_key, 0)

                if time.time() - last_time >= self.warning_cooldown:
                    warnings.append(warning)
                    self._generated_warnings.append(warning)
                    self._last_warning_time[warning_key] = time.time()

        return warnings

    def _check_navigation_risk(self, context: Dict[str, Any]) -> Optional[Warning]:
        """Check for navigation risks."""
        action = context.get("action", {})

        if action.get("type") not in ["navigate", "click"]:
            return None

        url = action.get("url", action.get("target", ""))

        # Check for risky URL patterns
        risky_patterns = ["/logout", "/signout", "/delete", "/remove", "/confirm", "/verify", "/payment", "/checkout"]

        for pattern in risky_patterns:
            if pattern in url.lower():
                return Warning(
                    warning_type=WarningType.NAVIGATION_RISK,
                    risk_level=RiskLevel.HIGH,
                    message=f"Navigation to potentially risky URL: {url}",
                    recommendation="Verify this is the intended action before proceeding",
                )

        return None

    def _check_action_stability(self, context: Dict[str, Any]) -> Optional[Warning]:
        """Check for action stability issues."""
        history = context.get("history", [])
        action = context.get("action", {})

        if len(history) < 3:
            return None

        # Check for repeated failures
        recent = history[-5:]
        failures = sum(1 for h in recent if not h.get("result", {}).get("success", True))

        if failures >= 3:
            return Warning(
                warning_type=WarningType.ACTION_UNSTABLE,
                risk_level=RiskLevel.MEDIUM,
                message=f"High failure rate detected: {failures}/5 recent actions failed",
                recommendation="Consider alternative approach or investigate page state",
            )

        # Check for repeated similar actions
        action_type = action.get("type")
        similar_count = sum(1 for h in recent if h.get("action", {}).get("type") == action_type)

        if similar_count >= 4:
            return Warning(
                warning_type=WarningType.ACTION_UNSTABLE,
                risk_level=RiskLevel.MEDIUM,
                message=f"Repeated {action_type} actions detected",
                recommendation="Verify action is having intended effect",
            )

        return None

    def _check_form_validation(self, context: Dict[str, Any]) -> Optional[Warning]:
        """Check for form validation issues."""
        action = context.get("action", {})

        if action.get("type") != "fill":
            return None

        value = action.get("value", "")
        field_type = action.get("field_type", "text")

        # Check for empty required fields
        if not value and action.get("required", False):
            return Warning(
                warning_type=WarningType.FORM_VALIDATION,
                risk_level=RiskLevel.HIGH,
                message="Attempting to fill required field with empty value",
                recommendation="Provide a value for required field",
            )

        # Check for format issues
        if field_type == "email" and value:
            if "@" not in value:
                return Warning(
                    warning_type=WarningType.FORM_VALIDATION,
                    risk_level=RiskLevel.MEDIUM,
                    message="Email format appears invalid",
                    recommendation="Verify email address format",
                )

        return None

    def _check_rate_limit(self, context: Dict[str, Any]) -> Optional[Warning]:
        """Check for rate limiting issues."""
        history = context.get("history", [])

        if len(history) < 10:
            return None

        # Check action frequency
        recent = history[-10:]
        if recent:
            time_span = recent[-1].get("timestamp", 0) - recent[0].get("timestamp", 0)
            if time_span > 0:
                actions_per_second = len(recent) / time_span

                if actions_per_second > 2:
                    return Warning(
                        warning_type=WarningType.RATE_LIMIT,
                        risk_level=RiskLevel.MEDIUM,
                        message=f"High action frequency: {actions_per_second:.1f} actions/second",
                        recommendation="Slow down to avoid rate limiting",
                    )

        return None

    def _check_element_ambiguity(self, context: Dict[str, Any]) -> Optional[Warning]:
        """Check for element selector ambiguity."""
        action = context.get("action", {})

        if action.get("type") not in ["click", "fill", "select"]:
            return None

        selector = action.get("selector", "")

        # Check for overly generic selectors
        if selector.startswith("//") and len(selector) < 20:
            return Warning(
                warning_type=WarningType.ELEMENT_AMBIGUOUS,
                risk_level=RiskLevel.MEDIUM,
                message="XPath selector appears very short/generic",
                recommendation="Use more specific selector to avoid wrong element",
            )

        # Check for index-based selectors
        if "[1]" in selector or "[2]" in selector:
            return Warning(
                warning_type=WarningType.ELEMENT_AMBIGUOUS,
                risk_level=RiskLevel.LOW,
                message="Selector uses positional index which may be unstable",
                recommendation="Consider using more stable selector attributes",
            )

        return None

    def add_custom_heuristic(self, heuristic: Callable[[Dict[str, Any]], Optional[Warning]]):
        """Add custom heuristic function."""
        self._heuristics.append(heuristic)

    def get_recent_warnings(self, count: int = 10, warning_type: Optional[WarningType] = None) -> List[Warning]:
        """Get recent warnings."""
        warnings = self._generated_warnings

        if warning_type:
            warnings = [w for w in warnings if w.warning_type == warning_type]

        return warnings[-count:]

    def dismiss_warning(self, warning: Warning):
        """Dismiss a warning."""
        warning.dismissed = True

    def get_stats(self) -> Dict[str, Any]:
        """Get warning system statistics."""
        by_type = {}
        by_level = {}

        for warning in self._generated_warnings:
            by_type[warning.warning_type.value] = by_type.get(warning.warning_type.value, 0) + 1
            by_level[warning.risk_level.value] = by_level.get(warning.risk_level.value, 0) + 1

        return {
            "total_warnings": len(self._generated_warnings),
            "active_warnings": sum(1 for w in self._generated_warnings if not w.dismissed),
            "by_type": by_type,
            "by_level": by_level,
            "heuristics_count": len(self._heuristics),
        }


# ============================================================================
# Suspicious State Handler
# ============================================================================


class SuspiciousStateHandler:
    """
    Handles suspicious states with automatic screenshots.

    Features:
    - Automatic screenshot capture
    - State fingerprinting
    - Anomaly/warning association
    - Review queue management
    """

    def __init__(self, screenshot_dir: Optional[Path] = None, max_states: int = 100, auto_screenshot: bool = True):
        """
        Initialize suspicious state handler.

        Args:
            screenshot_dir: Directory for screenshots
            max_states: Maximum states to retain
            auto_screenshot: Whether to automatically capture screenshots
        """
        self.screenshot_dir = screenshot_dir
        self.max_states = max_states
        self.auto_screenshot = auto_screenshot

        self._suspicious_states: Dict[str, SuspiciousState] = {}
        self._review_queue: List[str] = []

        if screenshot_dir:
            screenshot_dir.mkdir(parents=True, exist_ok=True)

    def handle_suspicious_state(
        self,
        screenshot: Optional[bytes],
        anomalies: List[Anomaly],
        warnings: List[Warning],
        context: Dict[str, Any] = None,
    ) -> SuspiciousState:
        """
        Handle a suspicious state.

        Args:
            screenshot: Optional screenshot bytes
            anomalies: Detected anomalies
            warnings: Generated warnings
            context: Additional context

        Returns:
            Created suspicious state record
        """
        # Compute state hash
        state_hash = self._compute_state_hash(anomalies, warnings, context)

        # Check if similar state already recorded
        if state_hash in self._suspicious_states:
            existing = self._suspicious_states[state_hash]
            existing.anomalies.extend(anomalies)
            existing.warnings.extend(warnings)
            return existing

        # Save screenshot
        screenshot_path = None
        if screenshot and self.screenshot_dir and self.auto_screenshot:
            screenshot_path = self._save_screenshot(state_hash, screenshot)

        # Create state record
        state = SuspiciousState(
            state_hash=state_hash,
            screenshot_path=screenshot_path,
            anomalies=anomalies,
            warnings=warnings,
            notes=context.get("notes", "") if context else "",
        )

        self._add_state(state)

        logger.warning(f"Suspicious state detected: {len(anomalies)} anomalies, " f"{len(warnings)} warnings")

        return state

    def _compute_state_hash(
        self, anomalies: List[Anomaly], warnings: List[Warning], context: Dict[str, Any] = None
    ) -> str:
        """Compute hash for state identification."""
        hash_data = {
            "anomaly_types": sorted([a.anomaly_type.value for a in anomalies]),
            "warning_types": sorted([w.warning_type.value for w in warnings]),
        }

        if context:
            hash_data["context_keys"] = sorted(context.keys())

        return hashlib.md5(json.dumps(hash_data, sort_keys=True).encode()).hexdigest()[:16]

    def _save_screenshot(self, state_hash: str, screenshot: bytes) -> str:
        """Save screenshot to disk."""
        filename = f"suspicious_{state_hash}_{int(time.time())}.png"
        filepath = self.screenshot_dir / filename

        with open(filepath, "wb") as f:
            f.write(screenshot)

        return str(filepath)

    def _add_state(self, state: SuspiciousState):
        """Add state to tracking."""
        # Evict oldest if at capacity
        if len(self._suspicious_states) >= self.max_states:
            oldest_hash = min(self._suspicious_states.keys(), key=lambda h: self._suspicious_states[h].timestamp)
            del self._suspicious_states[oldest_hash]

        self._suspicious_states[state.state_hash] = state
        self._review_queue.append(state.state_hash)

    def get_unreviewed_states(self) -> List[SuspiciousState]:
        """Get all unreviewed states."""
        return [
            self._suspicious_states[h]
            for h in self._review_queue
            if h in self._suspicious_states and not self._suspicious_states[h].reviewed
        ]

    def mark_reviewed(self, state_hash: str, notes: str = ""):
        """Mark state as reviewed."""
        if state_hash in self._suspicious_states:
            self._suspicious_states[state_hash].reviewed = True
            self._suspicious_states[state_hash].notes = notes

            # Remove from review queue
            self._review_queue = [h for h in self._review_queue if h != state_hash]

    def get_state(self, state_hash: str) -> Optional[SuspiciousState]:
        """Get state by hash."""
        return self._suspicious_states.get(state_hash)

    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        return {
            "total_states": len(self._suspicious_states),
            "unreviewed": len(self.get_unreviewed_states()),
            "max_states": self.max_states,
            "screenshot_dir": str(self.screenshot_dir) if self.screenshot_dir else None,
        }


# ============================================================================
# Pre-Action Risk Assessment
# ============================================================================


class PreActionRiskAssessment:
    """
    Assesses risk before executing actions.

    Features:
    - Multi-factor risk analysis
    - Confidence scoring
    - Recommendation generation
    - Historical outcome analysis
    """

    def __init__(self, risk_threshold: float = 0.7, history_size: int = 200):
        """
        Initialize risk assessment.

        Args:
            risk_threshold: Threshold for blocking actions (0-1)
            history_size: Size of action history for analysis
        """
        self.risk_threshold = risk_threshold
        self.history_size = history_size

        self._action_outcomes: Dict[str, List[bool]] = {}  # action_type -> outcomes
        self._risk_factors: List[Callable[[Dict[str, Any]], Tuple[float, str]]] = [
            self._assess_action_history,
            self._assess_element_stability,
            self._assess_page_familiarity,
            self._assess_action_complexity,
            self._assess_context_risk,
        ]
        self._assessments: List[RiskAssessment] = []

    def assess_action(self, action: Dict[str, Any], context: Dict[str, Any] = None) -> RiskAssessment:
        """
        Assess risk of proposed action.

        Args:
            action: Proposed action
            context: Additional context

        Returns:
            Risk assessment
        """
        factors = []
        total_risk = 0.0
        recommendations = []

        assessment_context = {
            **(context or {}),
            "action": action,
            "outcomes": self._action_outcomes,
        }

        for factor_fn in self._risk_factors:
            try:
                risk_score, description = factor_fn(assessment_context)
                factors.append(
                    {
                        "description": description,
                        "risk_score": risk_score,
                    }
                )
                total_risk += risk_score
            except Exception as e:
                logger.warning(f"Risk factor assessment failed: {e}")

        # Calculate overall risk
        avg_risk = total_risk / len(self._risk_factors) if self._risk_factors else 0

        # Determine risk level
        if avg_risk >= 0.8:
            risk_level = RiskLevel.CRITICAL
            should_proceed = False
        elif avg_risk >= 0.6:
            risk_level = RiskLevel.HIGH
            should_proceed = avg_risk < self.risk_threshold
        elif avg_risk >= 0.4:
            risk_level = RiskLevel.MEDIUM
            should_proceed = True
        else:
            risk_level = RiskLevel.LOW
            should_proceed = True

        # Generate recommendations
        if not should_proceed:
            recommendations.append("Action blocked due to high risk")
            recommendations.append("Review action parameters or try alternative approach")
        elif risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]:
            recommendations.append("Proceed with caution")
            recommendations.append("Monitor for unexpected behavior")

        assessment = RiskAssessment(
            action_type=action.get("type", "unknown"),
            overall_risk=risk_level,
            risk_score=avg_risk,
            factors=factors,
            recommendations=recommendations,
            should_proceed=should_proceed,
        )

        self._assessments.append(assessment)

        return assessment

    def _assess_action_history(self, context: Dict[str, Any]) -> Tuple[float, str]:
        """Assess risk based on action history."""
        action = context.get("action", {})
        outcomes = context.get("outcomes", {})

        action_type = action.get("type", "unknown")

        if action_type not in outcomes or not outcomes[action_type]:
            return 0.3, "No historical data for action type"

        history = outcomes[action_type]
        success_rate = sum(history) / len(history)

        # Risk is inverse of success rate
        risk = 1.0 - success_rate

        return risk, f"Historical success rate: {success_rate:.1%} ({len(history)} attempts)"

    def _assess_element_stability(self, context: Dict[str, Any]) -> Tuple[float, str]:
        """Assess risk based on element selector stability."""
        action = context.get("action", {})

        selector = action.get("selector", "")

        if not selector:
            return 0.2, "No selector - using coordinates or other method"

        # Check selector quality
        risk = 0.0

        # ID selectors are most stable
        if selector.startswith("#") or "[id=" in selector:
            risk = 0.1
            desc = "ID-based selector (stable)"
        # Data attributes are good
        elif "[data-" in selector:
            risk = 0.2
            desc = "Data attribute selector (stable)"
        # Class selectors are moderate
        elif selector.startswith(".") or "[class=" in selector:
            risk = 0.4
            desc = "Class-based selector (moderate stability)"
        # XPath can be fragile
        elif selector.startswith("//") or selector.startswith("/"):
            risk = 0.5
            desc = "XPath selector (potentially fragile)"
        # Very short selectors might be ambiguous
        elif len(selector) < 10:
            risk = 0.6
            desc = "Short selector (potentially ambiguous)"
        else:
            risk = 0.3
            desc = "Standard selector"

        return risk, desc

    def _assess_page_familiarity(self, context: Dict[str, Any]) -> Tuple[float, str]:
        """Assess risk based on page familiarity."""
        # Check if we've been on this page before
        context.get("url", "")
        page_visits = context.get("page_visits", 0)

        if page_visits == 0:
            return 0.5, "Unfamiliar page"
        elif page_visits < 3:
            return 0.3, f"Somewhat familiar page ({page_visits} visits)"
        else:
            return 0.1, f"Familiar page ({page_visits} visits)"

    def _assess_action_complexity(self, context: Dict[str, Any]) -> Tuple[float, str]:
        """Assess risk based on action complexity."""
        action = context.get("action", {})

        action_type = action.get("type", "unknown")

        # Simple actions
        if action_type in ["click", "navigate"]:
            return 0.1, f"Simple action: {action_type}"

        # Moderate actions
        if action_type in ["fill", "select", "hover"]:
            return 0.2, f"Moderate action: {action_type}"

        # Complex actions
        if action_type in ["drag", "scroll", "wait"]:
            return 0.4, f"Complex action: {action_type}"

        # Unknown actions
        return 0.5, f"Unknown action type: {action_type}"

    def _assess_context_risk(self, context: Dict[str, Any]) -> Tuple[float, str]:
        """Assess risk based on context factors."""
        risk = 0.0
        factors = []

        # Check for error state
        if context.get("has_errors", False):
            risk += 0.3
            factors.append("page has errors")

        # Check for popup state
        if context.get("has_popup", False):
            risk += 0.2
            factors.append("popup detected")

        # Check for loading state
        if context.get("is_loading", False):
            risk += 0.4
            factors.append("page loading")

        if factors:
            return min(risk, 1.0), f"Context risks: {', '.join(factors)}"

        return 0.1, "No context risks detected"

    def record_outcome(self, action_type: str, success: bool):
        """Record action outcome for learning."""
        if action_type not in self._action_outcomes:
            self._action_outcomes[action_type] = []

        self._action_outcomes[action_type].append(success)

        # Limit history size
        if len(self._action_outcomes[action_type]) > self.history_size:
            self._action_outcomes[action_type] = self._action_outcomes[action_type][-self.history_size :]

    def add_risk_factor(self, factor_fn: Callable[[Dict[str, Any]], Tuple[float, str]]):
        """Add custom risk factor."""
        self._risk_factors.append(factor_fn)

    def get_assessment_history(self, count: int = 10) -> List[RiskAssessment]:
        """Get recent assessments."""
        return self._assessments[-count:]

    def get_stats(self) -> Dict[str, Any]:
        """Get assessment statistics."""
        action_stats = {}

        for action_type, outcomes in self._action_outcomes.items():
            if outcomes:
                action_stats[action_type] = {
                    "total": len(outcomes),
                    "success_rate": sum(outcomes) / len(outcomes),
                }

        return {
            "total_assessments": len(self._assessments),
            "action_outcomes": action_stats,
            "risk_threshold": self.risk_threshold,
            "risk_factors_count": len(self._risk_factors),
        }


# ============================================================================
# Error Prevention System (Main Coordinator)
# ============================================================================


class ErrorPreventionSystem:
    """
    Main error prevention system coordinating all components.

    Features:
    - Anomaly detection
    - Heuristic warnings
    - Suspicious state handling
    - Pre-action risk assessment
    """

    def __init__(
        self,
        anomaly_detector: Optional[AnomalyDetector] = None,
        warning_system: Optional[HeuristicWarningSystem] = None,
        suspicious_handler: Optional[SuspiciousStateHandler] = None,
        risk_assessment: Optional[PreActionRiskAssessment] = None,
        screenshot_dir: Optional[Path] = None,
    ):
        """
        Initialize error prevention system.

        Args:
            anomaly_detector: Optional custom anomaly detector
            warning_system: Optional custom warning system
            suspicious_handler: Optional custom suspicious state handler
            risk_assessment: Optional custom risk assessment
            screenshot_dir: Directory for suspicious state screenshots
        """
        self.screenshot_dir = screenshot_dir

        # Initialize components
        self.anomaly_detector = anomaly_detector or AnomalyDetector()
        self.warning_system = warning_system or HeuristicWarningSystem()
        self.suspicious_handler = suspicious_handler or SuspiciousStateHandler(screenshot_dir=screenshot_dir)
        self.risk_assessment = risk_assessment or PreActionRiskAssessment()

    def observe_page(
        self, url: str, metrics: Dict[str, float], screenshot: Optional[bytes] = None
    ) -> Tuple[List[Anomaly], List[Warning]]:
        """
        Observe page and detect issues.

        Args:
            url: Page URL
            metrics: Page metrics
            screenshot: Optional screenshot

        Returns:
            Tuple of (anomalies, warnings)
        """
        # Detect anomalies
        screenshot_hash = hashlib.md5(screenshot).hexdigest()[:16] if screenshot else None
        anomalies = self.anomaly_detector.observe_page_metrics(
            url=url, metrics=metrics, screenshot_hash=screenshot_hash
        )

        # Handle suspicious state if anomalies found
        if anomalies and screenshot:
            self.suspicious_handler.handle_suspicious_state(screenshot=screenshot, anomalies=anomalies, warnings=[])

        return anomalies, []

    def check_action(
        self, action: Dict[str, Any], context: Dict[str, Any] = None, screenshot: Optional[bytes] = None
    ) -> Tuple[RiskAssessment, List[Warning]]:
        """
        Check action for risks and warnings.

        Args:
            action: Proposed action
            context: Additional context
            screenshot: Optional current screenshot

        Returns:
            Tuple of (risk_assessment, warnings)
        """
        # Get warnings
        warnings = self.warning_system.check_action(action, context)

        # Assess risk
        assessment = self.risk_assessment.assess_action(action, context)

        # Handle suspicious state if high risk
        if assessment.overall_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            if screenshot:
                self.suspicious_handler.handle_suspicious_state(
                    screenshot=screenshot,
                    anomalies=[],
                    warnings=warnings,
                    context={"action": action, "assessment": assessment.to_dict()},
                )

        return assessment, warnings

    def record_action_result(self, action: Dict[str, Any], result: Dict[str, Any]):
        """Record action result for learning."""
        self.warning_system.record_action(action, result)
        self.risk_assessment.record_outcome(action.get("type", "unknown"), result.get("success", False))

    def should_proceed(self, action: Dict[str, Any], context: Dict[str, Any] = None) -> Tuple[bool, Optional[str]]:
        """
        Determine if action should proceed.

        Args:
            action: Proposed action
            context: Additional context

        Returns:
            Tuple of (should_proceed, reason)
        """
        assessment, warnings = self.check_action(action, context)

        if not assessment.should_proceed:
            return False, f"Risk too high: {assessment.overall_risk.value}"

        # Check for critical warnings
        critical_warnings = [w for w in warnings if w.risk_level == RiskLevel.CRITICAL]

        if critical_warnings:
            return False, f"Critical warning: {critical_warnings[0].message}"

        return True, None

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics from all components."""
        return {
            "anomaly_detector": self.anomaly_detector.get_baseline_stats(),
            "warning_system": self.warning_system.get_stats(),
            "suspicious_handler": self.suspicious_handler.get_stats(),
            "risk_assessment": self.risk_assessment.get_stats(),
        }

    def clear_history(self):
        """Clear all history."""
        self.anomaly_detector.clear_anomalies()
        self.risk_assessment._assessments.clear()
        logger.info("Error prevention history cleared")

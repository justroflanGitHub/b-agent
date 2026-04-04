"""
Conversation Memory System - Memory for user interactions and learning.

Provides:
- User preference persistence
- Correction feedback learning
- Task template creation and management
- Session memory and context
"""

import hashlib
import logging
import time
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, TypeVar, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class UserPreference:
    """A user preference entry."""

    key: str
    value: Any
    category: str = "general"
    confidence: float = 1.0
    source: str = "explicit"  # explicit, inferred, learned
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    usage_count: int = 0

    def update(self, new_value: Any, source: str = "explicit"):
        """Update preference value."""
        self.value = new_value
        self.source = source
        self.updated_at = time.time()
        self.usage_count += 1


@dataclass
class CorrectionFeedback:
    """A correction feedback entry."""

    feedback_id: str
    context: Dict[str, Any]  # What was the situation
    original_action: Dict[str, Any]  # What the agent did
    corrected_action: Dict[str, Any]  # What user wanted
    explanation: Optional[str] = None  # User explanation
    timestamp: float = field(default_factory=time.time)
    applied_count: int = 0  # How many times this correction was applied
    success_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "feedback_id": self.feedback_id,
            "context": self.context,
            "original_action": self.original_action,
            "corrected_action": self.corrected_action,
            "explanation": self.explanation,
            "timestamp": self.timestamp,
            "applied_count": self.applied_count,
            "success_rate": self.success_rate,
        }


@dataclass
class TaskTemplate:
    """A reusable task template."""

    template_id: str
    name: str
    description: str
    goal_pattern: str  # Pattern to match against goals
    steps: List[Dict[str, Any]]  # Sequence of steps
    parameters: Dict[str, Any] = field(default_factory=dict)  # Parameterizable values
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    use_count: int = 0
    success_count: int = 0
    avg_completion_time: float = 0.0
    tags: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return self.success_count / self.use_count if self.use_count > 0 else 0.0

    def record_use(self, success: bool, completion_time: float):
        """Record template usage."""
        self.use_count += 1
        if success:
            self.success_count += 1
        # Update rolling average
        self.avg_completion_time = (self.avg_completion_time * (self.use_count - 1) + completion_time) / self.use_count
        self.updated_at = time.time()

    def matches_goal(self, goal: str) -> float:
        """
        Check if template matches a goal.

        Returns match confidence (0-1).
        """
        goal_lower = goal.lower()
        pattern_lower = self.goal_pattern.lower()

        # Exact match
        if pattern_lower == goal_lower:
            return 1.0

        # Pattern is substring of goal
        if pattern_lower in goal_lower:
            return 0.8

        # Goal is substring of pattern
        if goal_lower in pattern_lower:
            return 0.7

        # Word overlap
        goal_words = set(goal_lower.split())
        pattern_words = set(pattern_lower.split())
        overlap = len(goal_words & pattern_words)
        max_words = max(len(goal_words), len(pattern_words))

        if max_words > 0:
            return overlap / max_words * 0.5

        return 0.0


@dataclass
class SessionMessage:
    """A message in the session."""

    role: str  # "user", "agent", "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionState:
    """State of a conversation session."""

    session_id: str
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    messages: List[SessionMessage] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    task_history: List[Dict[str, Any]] = field(default_factory=list)
    current_goal: Optional[str] = None
    status: str = "active"  # active, paused, completed

    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """Add a message to the session."""
        self.messages.append(SessionMessage(role=role, content=content, metadata=metadata or {}))
        self.last_activity = time.time()

    def get_recent_messages(self, count: int = 10) -> List[SessionMessage]:
        """Get recent messages."""
        return self.messages[-count:]

    def get_context_summary(self) -> Dict[str, Any]:
        """Get summary of session context."""
        return {
            "session_id": self.session_id,
            "duration": time.time() - self.started_at,
            "message_count": len(self.messages),
            "task_count": len(self.task_history),
            "current_goal": self.current_goal,
            "status": self.status,
        }


# ============================================================================
# User Preference Store
# ============================================================================


class UserPreferenceStore:
    """
    Persistent storage for user preferences.

    Features:
    - Category-based organization
    - Confidence-weighted values
    - Inferred preferences from behavior
    - Persistent storage
    """

    def __init__(self, persist_path: Optional[Path] = None, max_preferences: int = 500):
        """
        Initialize preference store.

        Args:
            persist_path: Path for persistent storage
            max_preferences: Maximum preferences to store
        """
        self.persist_path = persist_path
        self.max_preferences = max_preferences

        self._preferences: Dict[str, UserPreference] = {}
        self._category_index: Dict[str, List[str]] = {}

        if persist_path and persist_path.exists():
            self._load_from_disk()

    def set(self, key: str, value: Any, category: str = "general", source: str = "explicit", confidence: float = 1.0):
        """
        Set a preference value.

        Args:
            key: Preference key
            value: Preference value
            category: Category for organization
            source: Source of preference (explicit, inferred, learned)
            confidence: Confidence level (0-1)
        """
        if key in self._preferences:
            self._preferences[key].update(value, source)
        else:
            self._preferences[key] = UserPreference(
                key=key, value=value, category=category, source=source, confidence=confidence
            )

            # Update category index
            if category not in self._category_index:
                self._category_index[category] = []
            self._category_index[category].append(key)

            # Evict if at capacity
            self._evict_if_needed()

        logger.debug(f"Set preference: {key} = {value}")

    def get(self, key: str, default: Any = None, use: bool = True) -> Any:
        """
        Get a preference value.

        Args:
            key: Preference key
            default: Default value if not found
            use: Whether to increment usage count

        Returns:
            Preference value or default
        """
        if key not in self._preferences:
            return default

        pref = self._preferences[key]
        if use:
            pref.usage_count += 1
            pref.updated_at = time.time()

        return pref.value

    def get_category(self, category: str) -> Dict[str, Any]:
        """Get all preferences in a category."""
        if category not in self._category_index:
            return {}

        return {key: self._preferences[key].value for key in self._category_index[category] if key in self._preferences}

    def delete(self, key: str) -> bool:
        """Delete a preference."""
        if key not in self._preferences:
            return False

        pref = self._preferences[key]

        # Remove from category index
        if pref.category in self._category_index:
            self._category_index[pref.category] = [k for k in self._category_index[pref.category] if k != key]

        del self._preferences[key]
        return True

    def infer_preference(self, key: str, value: Any, category: str = "inferred", confidence: float = 0.7):
        """
        Infer a preference from behavior.

        Only updates if new confidence is higher than existing.
        """
        if key in self._preferences:
            existing = self._preferences[key]
            # Only update if higher confidence
            if confidence > existing.confidence:
                existing.update(value, "inferred")
                existing.confidence = confidence
        else:
            self.set(key, value, category, "inferred", confidence)

    def _evict_if_needed(self):
        """Evict low-confidence preferences if at capacity."""
        if len(self._preferences) <= self.max_preferences:
            return

        # Find lowest confidence, least used preferences
        candidates = sorted(self._preferences.items(), key=lambda x: (x[1].confidence, x[1].usage_count))

        # Remove bottom 10%
        to_remove = max(1, len(candidates) // 10)
        for key, _ in candidates[:to_remove]:
            self.delete(key)

    def get_all(self) -> Dict[str, Any]:
        """Get all preferences as dict."""
        return {k: v.value for k, v in self._preferences.items()}

    def get_stats(self) -> Dict[str, Any]:
        """Get preference store statistics."""
        sources = {}
        categories = {}

        for pref in self._preferences.values():
            sources[pref.source] = sources.get(pref.source, 0) + 1
            categories[pref.category] = categories.get(pref.category, 0) + 1

        return {
            "total_preferences": len(self._preferences),
            "max_preferences": self.max_preferences,
            "by_source": sources,
            "by_category": categories,
        }

    def save_to_disk(self):
        """Save preferences to disk."""
        if not self.persist_path:
            return

        self.persist_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "preferences": {
                k: {
                    "key": v.key,
                    "value": v.value,
                    "category": v.category,
                    "confidence": v.confidence,
                    "source": v.source,
                    "created_at": v.created_at,
                    "updated_at": v.updated_at,
                    "usage_count": v.usage_count,
                }
                for k, v in self._preferences.items()
            },
            "category_index": self._category_index,
        }

        with open(self.persist_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved {len(self._preferences)} preferences to disk")

    def _load_from_disk(self):
        """Load preferences from disk."""
        if not self.persist_path or not self.persist_path.exists():
            return

        try:
            with open(self.persist_path, "r") as f:
                data = json.load(f)

            for key, pref_data in data.get("preferences", {}).items():
                self._preferences[key] = UserPreference(
                    key=pref_data["key"],
                    value=pref_data["value"],
                    category=pref_data.get("category", "general"),
                    confidence=pref_data.get("confidence", 1.0),
                    source=pref_data.get("source", "explicit"),
                    created_at=pref_data.get("created_at", time.time()),
                    updated_at=pref_data.get("updated_at", time.time()),
                    usage_count=pref_data.get("usage_count", 0),
                )

            self._category_index = data.get("category_index", {})

            logger.info(f"Loaded {len(self._preferences)} preferences from disk")
        except Exception as e:
            logger.warning(f"Failed to load preferences: {e}")

    def clear(self):
        """Clear all preferences."""
        self._preferences.clear()
        self._category_index.clear()


# ============================================================================
# Correction Feedback Learner
# ============================================================================


class CorrectionFeedbackLearner:
    """
    Learns from user corrections to improve future actions.

    Features:
    - Stores correction patterns
    - Matches similar contexts
    - Applies learned corrections
    - Tracks success rates
    """

    def __init__(self, max_corrections: int = 200, context_similarity_threshold: float = 0.7):
        """
        Initialize feedback learner.

        Args:
            max_corrections: Maximum corrections to store
            context_similarity_threshold: Threshold for context matching
        """
        self.max_corrections = max_corrections
        self.context_similarity_threshold = context_similarity_threshold

        self._corrections: Dict[str, CorrectionFeedback] = {}
        self._action_index: Dict[str, List[str]] = {}  # action_type -> feedback_ids

    def record_correction(
        self,
        context: Dict[str, Any],
        original_action: Dict[str, Any],
        corrected_action: Dict[str, Any],
        explanation: Optional[str] = None,
    ) -> CorrectionFeedback:
        """
        Record a correction from the user.

        Args:
            context: Context when correction occurred
            original_action: What the agent did
            corrected_action: What user wanted
            explanation: Optional user explanation

        Returns:
            Created feedback entry
        """
        feedback_id = f"corr_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"

        feedback = CorrectionFeedback(
            feedback_id=feedback_id,
            context=context,
            original_action=original_action,
            corrected_action=corrected_action,
            explanation=explanation,
        )

        # Check for similar existing correction
        similar = self._find_similar_correction(context, original_action)
        if similar:
            # Update existing instead of creating new
            similar.corrected_action = corrected_action
            similar.explanation = explanation or similar.explanation
            similar.timestamp = time.time()
            return similar

        self._add_correction(feedback)

        return feedback

    def _find_similar_correction(self, context: Dict[str, Any], action: Dict[str, Any]) -> Optional[CorrectionFeedback]:
        """Find similar existing correction."""
        action_type = action.get("type", "unknown")

        if action_type not in self._action_index:
            return None

        for feedback_id in self._action_index[action_type]:
            if feedback_id not in self._corrections:
                continue

            feedback = self._corrections[feedback_id]
            similarity = self._calculate_context_similarity(context, feedback.context)

            if similarity >= self.context_similarity_threshold:
                return feedback

        return None

    def _calculate_context_similarity(self, ctx1: Dict[str, Any], ctx2: Dict[str, Any]) -> float:
        """Calculate similarity between contexts."""
        # Simple key overlap similarity
        keys1 = set(ctx1.keys())
        keys2 = set(ctx2.keys())

        if not keys1 and not keys2:
            return 1.0

        if not keys1 or not keys2:
            return 0.0

        key_overlap = len(keys1 & keys2) / max(len(keys1), len(keys2))

        # Check value similarity for common keys
        common_keys = keys1 & keys2
        value_matches = sum(1 for k in common_keys if ctx1.get(k) == ctx2.get(k))
        value_similarity = value_matches / len(common_keys) if common_keys else 0

        return 0.3 * key_overlap + 0.7 * value_similarity

    def _add_correction(self, feedback: CorrectionFeedback):
        """Add correction to storage."""
        # Evict oldest if at capacity
        if len(self._corrections) >= self.max_corrections:
            oldest_id = min(self._corrections.keys(), key=lambda x: self._corrections[x].timestamp)
            self._remove_correction(oldest_id)

        self._corrections[feedback.feedback_id] = feedback

        # Update action index
        action_type = feedback.original_action.get("type", "unknown")
        if action_type not in self._action_index:
            self._action_index[action_type] = []
        self._action_index[action_type].append(feedback.feedback_id)

    def _remove_correction(self, feedback_id: str):
        """Remove correction from storage."""
        if feedback_id not in self._corrections:
            return

        feedback = self._corrections[feedback_id]
        action_type = feedback.original_action.get("type", "unknown")

        if action_type in self._action_index:
            self._action_index[action_type] = [fid for fid in self._action_index[action_type] if fid != feedback_id]

        del self._corrections[feedback_id]

    def get_correction_for_action(
        self, context: Dict[str, Any], proposed_action: Dict[str, Any]
    ) -> Optional[CorrectionFeedback]:
        """
        Get applicable correction for a proposed action.

        Args:
            context: Current context
            proposed_action: Action being considered

        Returns:
            Applicable correction or None
        """
        return self._find_similar_correction(context, proposed_action)

    def apply_correction(self, feedback: CorrectionFeedback, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a correction to an action.

        Args:
            feedback: Correction to apply
            action: Original action

        Returns:
            Corrected action
        """
        corrected = action.copy()

        # Apply corrections from feedback
        for key, value in feedback.corrected_action.items():
            if key != "type" or value == action.get("type"):
                corrected[key] = value

        feedback.applied_count += 1

        return corrected

    def record_outcome(self, feedback_id: str, success: bool):
        """Record outcome of applied correction."""
        if feedback_id not in self._corrections:
            return

        feedback = self._corrections[feedback_id]
        total = feedback.applied_count

        # Update success rate
        if success:
            feedback.success_rate = (feedback.success_rate * (total - 1) + 1) / total
        else:
            feedback.success_rate = (feedback.success_rate * (total - 1)) / total

    def get_stats(self) -> Dict[str, Any]:
        """Get learner statistics."""
        if not self._corrections:
            return {
                "total_corrections": 0,
                "avg_success_rate": 0,
                "total_applications": 0,
            }

        return {
            "total_corrections": len(self._corrections),
            "max_corrections": self.max_corrections,
            "avg_success_rate": sum(c.success_rate for c in self._corrections.values()) / len(self._corrections),
            "total_applications": sum(c.applied_count for c in self._corrections.values()),
            "by_action_type": {k: len(v) for k, v in self._action_index.items()},
        }


# ============================================================================
# Task Template Manager
# ============================================================================


class TaskTemplateManager:
    """
    Manages reusable task templates.

    Features:
    - Template creation from successful tasks
    - Goal pattern matching
    - Parameter substitution
    - Success rate tracking
    """

    def __init__(self, max_templates: int = 100, min_success_rate: float = 0.5):
        """
        Initialize template manager.

        Args:
            max_templates: Maximum templates to store
            min_success_rate: Minimum success rate to keep template
        """
        self.max_templates = max_templates
        self.min_success_rate = min_success_rate

        self._templates: Dict[str, TaskTemplate] = {}
        self._tag_index: Dict[str, List[str]] = {}

    def create_template(
        self,
        name: str,
        description: str,
        goal_pattern: str,
        steps: List[Dict[str, Any]],
        parameters: Dict[str, Any] = None,
        tags: List[str] = None,
    ) -> TaskTemplate:
        """
        Create a new task template.

        Args:
            name: Template name
            description: Template description
            goal_pattern: Pattern to match against goals
            steps: List of steps
            parameters: Parameterizable values
            tags: Tags for categorization

        Returns:
            Created template
        """
        template_id = f"tpl_{hashlib.md5(name.encode()).hexdigest()[:8]}"

        template = TaskTemplate(
            template_id=template_id,
            name=name,
            description=description,
            goal_pattern=goal_pattern,
            steps=steps,
            parameters=parameters or {},
            tags=tags or [],
        )

        self._add_template(template)

        return template

    def create_from_execution(
        self, name: str, goal: str, steps: List[Dict[str, Any]], success: bool, completion_time: float
    ) -> Optional[TaskTemplate]:
        """
        Create template from task execution.

        Args:
            name: Template name
            goal: Original goal
            steps: Executed steps
            success: Whether task succeeded
            completion_time: Time to complete

        Returns:
            Created template or None
        """
        if not success or not steps:
            return None

        # Generalize goal pattern
        goal_pattern = self._generalize_pattern(goal)

        # Extract parameters from steps
        parameters = self._extract_parameters(steps)

        return self.create_template(
            name=name,
            description=f"Template created from: {goal}",
            goal_pattern=goal_pattern,
            steps=steps,
            parameters=parameters,
        )

    def _generalize_pattern(self, text: str) -> str:
        """Generalize text pattern for matching."""
        # Simple generalization - keep structure but allow variation
        pattern = text.lower()

        # Replace specific values with placeholders
        # In production, would use NER or similar
        return pattern

    def _extract_parameters(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract parameterizable values from steps."""
        parameters = {}

        for i, step in enumerate(steps):
            # Look for values that might be parameters
            for key, value in step.items():
                if isinstance(value, str) and len(value) > 10:
                    # Might be a specific value to parameterize
                    param_key = f"step_{i}_{key}"
                    parameters[param_key] = value

        return parameters

    def _add_template(self, template: TaskTemplate):
        """Add template to storage."""
        # Evict worst if at capacity
        if len(self._templates) >= self.max_templates:
            self._evict_worst_template()

        self._templates[template.template_id] = template

        # Update tag index
        for tag in template.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            self._tag_index[tag].append(template.template_id)

    def _evict_worst_template(self):
        """Evict template with lowest success rate."""
        if not self._templates:
            return

        # Only evict templates with enough data
        candidates = [(tid, t) for tid, t in self._templates.items() if t.use_count >= 3]

        if not candidates:
            # Evict oldest if no candidates
            oldest_id = min(self._templates.keys(), key=lambda x: self._templates[x].created_at)
            self._remove_template(oldest_id)
            return

        worst_id = min(candidates, key=lambda x: x[1].success_rate)[0]
        self._remove_template(worst_id)

    def _remove_template(self, template_id: str):
        """Remove template from storage."""
        if template_id not in self._templates:
            return

        template = self._templates[template_id]

        # Remove from tag index
        for tag in template.tags:
            if tag in self._tag_index:
                self._tag_index[tag] = [tid for tid in self._tag_index[tag] if tid != template_id]

        del self._templates[template_id]

    def find_matching_templates(self, goal: str, min_confidence: float = 0.5) -> List[Tuple[TaskTemplate, float]]:
        """
        Find templates matching a goal.

        Args:
            goal: Task goal
            min_confidence: Minimum match confidence

        Returns:
            List of (template, confidence) tuples
        """
        matches = []

        for template in self._templates.values():
            confidence = template.matches_goal(goal)
            if confidence >= min_confidence:
                # Boost by success rate
                adjusted_confidence = confidence * (0.5 + 0.5 * template.success_rate)
                matches.append((template, adjusted_confidence))

        return sorted(matches, key=lambda x: x[1], reverse=True)

    def get_template(self, template_id: str) -> Optional[TaskTemplate]:
        """Get template by ID."""
        return self._templates.get(template_id)

    def get_templates_by_tag(self, tag: str) -> List[TaskTemplate]:
        """Get templates by tag."""
        if tag not in self._tag_index:
            return []

        return [self._templates[tid] for tid in self._tag_index[tag] if tid in self._templates]

    def instantiate_template(self, template: TaskTemplate, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Instantiate template with parameters.

        Args:
            template: Template to instantiate
            parameters: Parameter values

        Returns:
            Instantiated steps
        """
        steps = []

        for step in template.steps:
            instantiated = step.copy()

            # Replace parameters
            for key, value in instantiated.items():
                if isinstance(value, str):
                    for param_key, param_value in parameters.items():
                        placeholder = f"{{{param_key}}}"
                        if placeholder in value:
                            value = value.replace(placeholder, str(param_value))
                    instantiated[key] = value

            steps.append(instantiated)

        return steps

    def record_use(self, template_id: str, success: bool, completion_time: float):
        """Record template usage."""
        if template_id in self._templates:
            self._templates[template_id].record_use(success, completion_time)

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        if not self._templates:
            return {
                "total_templates": 0,
                "avg_success_rate": 0,
            }

        return {
            "total_templates": len(self._templates),
            "max_templates": self.max_templates,
            "avg_success_rate": sum(t.success_rate for t in self._templates.values()) / len(self._templates),
            "total_uses": sum(t.use_count for t in self._templates.values()),
            "tags": list(self._tag_index.keys()),
        }


# ============================================================================
# Session Memory
# ============================================================================


class SessionMemory:
    """
    Manages conversation session memory.

    Features:
    - Message history
    - Context management
    - Task tracking
    - Session persistence
    """

    def __init__(self, session_id: Optional[str] = None, max_messages: int = 1000, persist_path: Optional[Path] = None):
        """
        Initialize session memory.

        Args:
            session_id: Optional session ID (auto-generated if not provided)
            max_messages: Maximum messages to keep
            persist_path: Path for session persistence
        """
        self.session_id = session_id or self._generate_session_id()
        self.max_messages = max_messages
        self.persist_path = persist_path

        self._state = SessionState(session_id=self.session_id)
        self._preference_store: Optional[UserPreferenceStore] = None

        if persist_path:
            self._load_session()

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        return f"sess_{hashlib.md5(str(time.time()).encode()).hexdigest()[:12]}"

    def add_user_message(self, content: str, metadata: Dict[str, Any] = None):
        """Add user message to session."""
        self._state.add_message("user", content, metadata)
        self._save_session()

    def add_agent_message(self, content: str, metadata: Dict[str, Any] = None):
        """Add agent message to session."""
        self._state.add_message("agent", content, metadata)
        self._save_session()

    def add_system_message(self, content: str, metadata: Dict[str, Any] = None):
        """Add system message to session."""
        self._state.add_message("system", content, metadata)

    def get_messages(self, count: Optional[int] = None, role: Optional[str] = None) -> List[SessionMessage]:
        """
        Get messages from session.

        Args:
            count: Maximum messages to return
            role: Filter by role

        Returns:
            List of messages
        """
        messages = self._state.messages

        if role:
            messages = [m for m in messages if m.role == role]

        if count:
            messages = messages[-count:]

        return messages

    def get_recent_messages(self, count: int = 10) -> List[SessionMessage]:
        """Get recent messages from session."""
        return self.get_messages(count=count)

    def get_conversation_context(self, max_messages: int = 10) -> str:
        """Get conversation as context string."""
        recent = self.get_recent_messages(max_messages)

        lines = []
        for msg in recent:
            prefix = {"user": "User", "agent": "Agent", "system": "System"}.get(msg.role, msg.role)
            lines.append(f"{prefix}: {msg.content}")

        return "\n".join(lines)

    def set_context(self, key: str, value: Any):
        """Set context value."""
        self._state.context[key] = value
        self._state.last_activity = time.time()

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get context value."""
        return self._state.context.get(key, default)

    def set_goal(self, goal: str):
        """Set current goal."""
        self._state.current_goal = goal
        self._state.last_activity = time.time()

    def get_goal(self) -> Optional[str]:
        """Get current goal."""
        return self._state.current_goal

    def add_task_record(self, task: Dict[str, Any]):
        """Add task to history."""
        self._state.task_history.append({**task, "timestamp": time.time()})
        self._state.last_activity = time.time()
        self._save_session()

    def get_task_history(self) -> List[Dict[str, Any]]:
        """Get task history."""
        return self._state.task_history

    def pause(self):
        """Pause session."""
        self._state.status = "paused"
        self._save_session()

    def resume(self):
        """Resume session."""
        self._state.status = "active"
        self._state.last_activity = time.time()

    def complete(self):
        """Mark session as complete."""
        self._state.status = "completed"
        self._save_session()

    def get_state(self) -> SessionState:
        """Get session state."""
        return self._state

    def get_summary(self) -> Dict[str, Any]:
        """Get session summary."""
        return self._state.get_context_summary()

    def _save_session(self):
        """Save session to disk."""
        if not self.persist_path:
            return

        self.persist_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "session_id": self._state.session_id,
            "started_at": self._state.started_at,
            "last_activity": self._state.last_activity,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "metadata": m.metadata,
                }
                for m in self._state.messages
            ],
            "context": self._state.context,
            "task_history": self._state.task_history,
            "current_goal": self._state.current_goal,
            "status": self._state.status,
        }

        session_file = self.persist_path / f"{self.session_id}.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        with open(session_file, "w") as f:
            json.dump(data, f, indent=2)

    def _load_session(self):
        """Load session from disk."""
        if not self.persist_path:
            return

        session_file = self.persist_path / f"{self.session_id}.json"

        if not session_file.exists():
            return

        try:
            with open(session_file, "r") as f:
                data = json.load(f)

            self._state = SessionState(
                session_id=data.get("session_id", self.session_id),
                started_at=data.get("started_at", time.time()),
                last_activity=data.get("last_activity", time.time()),
                messages=[
                    SessionMessage(
                        role=m["role"],
                        content=m["content"],
                        timestamp=m.get("timestamp", time.time()),
                        metadata=m.get("metadata", {}),
                    )
                    for m in data.get("messages", [])
                ],
                context=data.get("context", {}),
                task_history=data.get("task_history", []),
                current_goal=data.get("current_goal"),
                status=data.get("status", "active"),
            )

            logger.info(f"Loaded session {self.session_id}")
        except Exception as e:
            logger.warning(f"Failed to load session: {e}")

    def clear(self):
        """Clear session memory."""
        self._state = SessionState(session_id=self.session_id)


# ============================================================================
# Conversation Memory System (Main Coordinator)
# ============================================================================


class ConversationMemorySystem:
    """
    Main conversation memory system coordinating all components.

    Features:
    - User preference persistence
    - Correction feedback learning
    - Task template management
    - Session memory
    """

    def __init__(
        self,
        preference_store: Optional[UserPreferenceStore] = None,
        feedback_learner: Optional[CorrectionFeedbackLearner] = None,
        template_manager: Optional[TaskTemplateManager] = None,
        session_memory: Optional[SessionMemory] = None,
        persist_path: Optional[Path] = None,
    ):
        """
        Initialize conversation memory system.

        Args:
            preference_store: Optional custom preference store
            feedback_learner: Optional custom feedback learner
            template_manager: Optional custom template manager
            session_memory: Optional custom session memory
            persist_path: Path for persistent storage
        """
        self.persist_path = persist_path

        # Initialize components
        self.preference_store = preference_store or UserPreferenceStore(
            persist_path=persist_path / "preferences.json" if persist_path else None
        )
        self.feedback_learner = feedback_learner or CorrectionFeedbackLearner()
        self.template_manager = template_manager or TaskTemplateManager()
        self.session_memory = session_memory or SessionMemory(
            persist_path=persist_path / "sessions" if persist_path else None
        )

    def process_user_input(self, input_text: str, metadata: Dict[str, Any] = None):
        """Process user input."""
        self.session_memory.add_user_message(input_text, metadata)

    def process_agent_response(self, response: str, metadata: Dict[str, Any] = None):
        """Process agent response."""
        self.session_memory.add_agent_message(response, metadata)

    def record_correction(
        self,
        context: Dict[str, Any],
        original_action: Dict[str, Any],
        corrected_action: Dict[str, Any],
        explanation: Optional[str] = None,
    ) -> CorrectionFeedback:
        """Record user correction."""
        return self.feedback_learner.record_correction(
            context=context, original_action=original_action, corrected_action=corrected_action, explanation=explanation
        )

    def get_action_correction(
        self, context: Dict[str, Any], proposed_action: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get corrected action if applicable."""
        correction = self.feedback_learner.get_correction_for_action(context, proposed_action)

        if correction:
            return self.feedback_learner.apply_correction(correction, proposed_action)

        return None

    def find_task_templates(self, goal: str) -> List[Tuple[TaskTemplate, float]]:
        """Find templates matching goal."""
        return self.template_manager.find_matching_templates(goal)

    def create_template_from_task(
        self, name: str, goal: str, steps: List[Dict[str, Any]], success: bool, completion_time: float
    ) -> Optional[TaskTemplate]:
        """Create template from task execution."""
        return self.template_manager.create_from_execution(
            name=name, goal=goal, steps=steps, success=success, completion_time=completion_time
        )

    def set_preference(self, key: str, value: Any, category: str = "general"):
        """Set user preference."""
        self.preference_store.set(key, value, category)

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get user preference."""
        return self.preference_store.get(key, default)

    def get_conversation_context(self, max_messages: int = 10) -> str:
        """Get conversation context."""
        return self.session_memory.get_conversation_context(max_messages)

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics from all components."""
        return {
            "preferences": self.preference_store.get_stats(),
            "feedback": self.feedback_learner.get_stats(),
            "templates": self.template_manager.get_stats(),
            "session": self.session_memory.get_summary(),
        }

    def save_all(self):
        """Save all state to disk."""
        if self.persist_path:
            self.persist_path.mkdir(parents=True, exist_ok=True)
            self.preference_store.save_to_disk()
            self.session_memory._save_session()
            logger.info("Conversation memory saved")

    def clear_all(self):
        """Clear all memory."""
        self.preference_store.clear()
        self.session_memory.clear()
        logger.info("Conversation memory cleared")

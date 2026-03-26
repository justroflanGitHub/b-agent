"""
Memory Module - Advanced memory systems for browser agent.

Provides:
- Visual Memory: Screenshot embeddings, UI state detection, navigation patterns
- Conversation Memory: User preferences, feedback learning, task templates
- Error Prevention: Anomaly detection, heuristics, risk assessment
"""

from browser_agent.memory.visual_memory import (
    VisualMemorySystem,
    ScreenshotEmbeddingCache,
    UIStateDetector,
    NavigationPatternLearner,
    DynamicElementReidentifier,
)

from browser_agent.memory.conversation_memory import (
    ConversationMemorySystem,
    UserPreferenceStore,
    CorrectionFeedbackLearner,
    TaskTemplateManager,
    SessionMemory,
)

from browser_agent.memory.error_prevention import (
    ErrorPreventionSystem,
    AnomalyDetector,
    HeuristicWarningSystem,
    SuspiciousStateHandler,
    PreActionRiskAssessment,
)

__all__ = [
    # Visual Memory
    "VisualMemorySystem",
    "ScreenshotEmbeddingCache",
    "UIStateDetector",
    "NavigationPatternLearner",
    "DynamicElementReidentifier",
    # Conversation Memory
    "ConversationMemorySystem",
    "UserPreferenceStore",
    "CorrectionFeedbackLearner",
    "TaskTemplateManager",
    "SessionMemory",
    # Error Prevention
    "ErrorPreventionSystem",
    "AnomalyDetector",
    "HeuristicWarningSystem",
    "SuspiciousStateHandler",
    "PreActionRiskAssessment",
]

"""
Multi-Agent Coordination System

This module provides a supervisor orchestrator pattern with specialized sub-agents
for complex browser automation tasks.

Components:
- BaseAgent: Abstract base class for all agents
- PlannerAgent: Plans and decomposes tasks into steps
- AnalyzerAgent: Analyzes page state and elements
- ActorAgent: Executes actions on the page
- ValidatorAgent: Validates action results
- SupervisorAgent: Orchestrates all sub-agents
- AgentCommunication: Message passing between agents
"""

from .base import (
    BaseAgent,
    AgentConfig,
    AgentStatus,
    AgentCapability,
    AgentResult,
)

from .communication import (
    AgentMessage,
    MessageType,
    MessagePriority,
    AgentCommunicationBus,
)

from .planner import (
    PlannerAgent,
    TaskPlan,
    PlanStep,
    StepDependency,
)

from .analyzer import (
    AnalyzerAgent,
    AnalysisRequest,
    AnalysisResult,
)

from .actor import (
    ActorAgent,
    ActionRequest,
    ActionResult,
)

from .validator import (
    ValidatorAgent,
    ValidationRequest,
    ValidationResult,
    ValidationCriteria,
)

from .supervisor import (
    SupervisorAgent,
    SupervisorConfig,
    TaskDelegation,
    AgentPool,
)

__all__ = [
    # Base
    "BaseAgent",
    "AgentConfig",
    "AgentStatus",
    "AgentCapability",
    "AgentResult",
    # Communication
    "AgentMessage",
    "MessageType",
    "MessagePriority",
    "AgentCommunicationBus",
    # Planner
    "PlannerAgent",
    "TaskPlan",
    "PlanStep",
    "StepDependency",
    # Analyzer
    "AnalyzerAgent",
    "AnalysisRequest",
    "AnalysisResult",
    # Actor
    "ActorAgent",
    "ActionRequest",
    "ActionResult",
    # Validator
    "ValidatorAgent",
    "ValidationRequest",
    "ValidationResult",
    "ValidationCriteria",
    # Supervisor
    "SupervisorAgent",
    "SupervisorConfig",
    "TaskDelegation",
    "AgentPool",
]

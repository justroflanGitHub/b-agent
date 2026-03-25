"""
Resilience & Recovery Module for Browser Agent.

This module provides state management, error recovery, and rollback capabilities:
- Checkpoint system for browser state snapshots
- Fallback strategies for error handling
- State stack for rollback operations
- Recovery orchestration for automatic error recovery
"""

from .checkpoint import CheckpointManager, Checkpoint, BrowserState, CheckpointType
from .fallback import FallbackStrategy, FallbackManager, ErrorType, FallbackResult, ErrorContext
from .state_stack import StateStack, StateFrame
from .recovery import RecoveryOrchestrator, RecoveryResult, RecoveryStatus, RecoveryConfig

__all__ = [
    # Checkpoint system
    "CheckpointManager",
    "Checkpoint", 
    "BrowserState",
    "CheckpointType",
    # Fallback strategies
    "FallbackStrategy",
    "FallbackManager",
    "ErrorType",
    "FallbackResult",
    "ErrorContext",
    # State stack
    "StateStack",
    "StateFrame",
    # Recovery
    "RecoveryOrchestrator",
    "RecoveryResult",
    "RecoveryStatus",
    "RecoveryConfig",
]

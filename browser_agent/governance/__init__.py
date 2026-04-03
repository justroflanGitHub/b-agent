"""Governance module — policy engine, approval workflows, notifiers."""

from .policy_engine import PolicyEngine, PolicyRule, PolicyContext, PolicyDecision, PolicyEffect, PolicyCondition
from .approval import ApprovalManager, ApprovalRequest, ApprovalStatus, ApprovalConfig
from .notifiers import Notifier, SlackNotifier, TeamsNotifier, EmailNotifier, WebhookNotifier, CompositeNotifier
from .gates import (
    Gate,
    ProductionURLGate,
    DestructiveActionGate,
    SensitiveDataGate,
    FinancialTransactionGate,
    ExternalSiteGate,
)
from .policy_definitions import PolicyTemplates

__all__ = [
    "PolicyEngine", "PolicyRule", "PolicyContext", "PolicyDecision", "PolicyEffect", "PolicyCondition",
    "ApprovalManager", "ApprovalRequest", "ApprovalStatus", "ApprovalConfig",
    "Notifier", "SlackNotifier", "TeamsNotifier", "EmailNotifier", "WebhookNotifier", "CompositeNotifier",
    "Gate", "ProductionURLGate", "DestructiveActionGate", "SensitiveDataGate",
    "FinancialTransactionGate", "ExternalSiteGate",
    "PolicyTemplates",
]

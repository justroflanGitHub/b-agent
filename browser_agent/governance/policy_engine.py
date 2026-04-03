"""Policy engine — rule-based governance for agent actions.

Evaluates policies before each action to determine if it should be
allowed, denied, or require human approval.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PolicyEffect(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class PolicyCondition:
    """A single condition in a policy rule."""
    field: str       # "target_url", "action_type", "sensitivity", "tenant_id", "user_id"
    operator: str    # "equals", "contains", "matches", "in", "not_equals", "not_contains", "not_matches"
    value: Any

    def evaluate(self, context: Dict[str, Any]) -> bool:
        actual = context.get(self.field)
        if actual is None:
            return False

        if self.operator == "equals":
            return actual == self.value
        elif self.operator == "not_equals":
            return actual != self.value
        elif self.operator == "contains":
            return str(self.value) in str(actual)
        elif self.operator == "not_contains":
            return str(self.value) not in str(actual)
        elif self.operator == "matches":
            return bool(re.search(self.value, str(actual)))
        elif self.operator == "not_matches":
            return not bool(re.search(self.value, str(actual)))
        elif self.operator == "in":
            return actual in self.value
        elif self.operator == "not_in":
            return actual not in self.value
        elif self.operator == "greater_than":
            return float(actual) > float(self.value)
        elif self.operator == "less_than":
            return float(actual) < float(self.value)
        return False


@dataclass
class ApprovalConfig:
    """Configuration for an approval gate."""
    approvers: List[str] = field(default_factory=list)
    approval_type: str = "single"           # "single", "quorum", "escalation"
    timeout_seconds: int = 3600
    auto_deny_on_timeout: bool = True
    escalation_approvers: Optional[List[str]] = None
    escalation_after_seconds: Optional[int] = None
    notification_channels: List[str] = field(default_factory=list)
    message_template: Optional[str] = None


@dataclass
class PolicyRule:
    """A governance policy rule."""
    rule_id: str
    name: str
    description: str = ""
    effect: PolicyEffect = PolicyEffect.ALLOW
    conditions: List[PolicyCondition] = field(default_factory=list)
    approval_config: Optional[ApprovalConfig] = None
    priority: int = 0
    enabled: bool = True
    tenant_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def matches(self, context: Dict[str, Any]) -> bool:
        """Check if all conditions match (AND logic)."""
        if not self.enabled:
            return False
        return all(c.evaluate(context) for c in self.conditions)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "effect": self.effect.value,
            "conditions": [
                {"field": c.field, "operator": c.operator, "value": c.value}
                for c in self.conditions
            ],
            "approval_config": {
                "approval_type": self.approval_config.approval_type,
                "approvers": self.approval_config.approvers,
                "timeout_seconds": self.approval_config.timeout_seconds,
            } if self.approval_config else None,
            "priority": self.priority,
            "enabled": self.enabled,
            "tenant_id": self.tenant_id,
            "tags": self.tags,
        }


@dataclass
class PolicyContext:
    """Context for policy evaluation."""
    action_type: str = ""
    target_url: str = ""
    target_element: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    tenant_id: str = "default"
    user_id: str = "system"
    task_id: str = ""
    data_sensitivity: Optional[str] = None
    credential_alias: Optional[str] = None
    extracted_data_preview: Optional[str] = None
    step_index: int = 0
    daily_task_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target_url": self.target_url,
            "target_element": self.target_element,
            "parameters": self.parameters,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "task_id": self.task_id,
            "data_sensitivity": self.data_sensitivity,
            "credential_alias": self.credential_alias,
            "extracted_data_preview": self.extracted_data_preview,
            "step_index": self.step_index,
            "daily_task_count": self.daily_task_count,
        }


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""
    effect: PolicyEffect
    matched_rule: Optional[PolicyRule] = None
    reason: str = ""
    requires_approval: bool = False
    approval_config: Optional[ApprovalConfig] = None


class PolicyEngine:
    """Evaluate governance policies for actions.

    Rules are evaluated in priority order (highest first).
    First matching rule wins. If no rules match, default effect is ALLOW.
    """

    def __init__(self, rules: Optional[List[PolicyRule]] = None,
                 default_effect: PolicyEffect = PolicyEffect.ALLOW):
        self._rules: List[PolicyRule] = sorted(
            rules or [], key=lambda r: -r.priority
        )
        self._default_effect = default_effect

    @property
    def rules(self) -> List[PolicyRule]:
        return list(self._rules)

    async def evaluate(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate all applicable rules against context.

        Returns the highest-priority matching rule's effect.
        """
        ctx_dict = context.to_dict()

        for rule in self._rules:
            if not rule.enabled:
                continue
            # Check tenant scope
            if rule.tenant_id is not None and rule.tenant_id != context.tenant_id:
                continue

            if rule.matches(ctx_dict):
                return PolicyDecision(
                    effect=rule.effect,
                    matched_rule=rule,
                    reason=f"Matched rule: {rule.name} (id={rule.rule_id})",
                    requires_approval=rule.effect == PolicyEffect.REQUIRE_APPROVAL,
                    approval_config=rule.approval_config,
                )

        return PolicyDecision(
            effect=self._default_effect,
            reason="No matching rule — default effect applied",
        )

    async def add_rule(self, rule: PolicyRule) -> str:
        """Add a new policy rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: -r.priority)
        return rule.rule_id

    async def remove_rule(self, rule_id: str) -> bool:
        """Remove a policy rule by ID."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        return len(self._rules) < before

    async def update_rule(self, rule_id: str, **kwargs) -> Optional[PolicyRule]:
        """Update a rule's fields."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                for k, v in kwargs.items():
                    if hasattr(rule, k):
                        setattr(rule, k, v)
                self._rules.sort(key=lambda r: -r.priority)
                return rule
        return None

    async def list_rules(self, tenant_id: Optional[str] = None) -> List[PolicyRule]:
        """List rules, optionally filtered by tenant."""
        if tenant_id is None:
            return list(self._rules)
        return [r for r in self._rules if r.tenant_id is None or r.tenant_id == tenant_id]

    async def dry_run(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate without enforcing (for testing policies)."""
        return await self.evaluate(context)

    async def evaluate_action(
        self,
        action_type: str,
        target_url: str = "",
        tenant_id: str = "default",
        user_id: str = "system",
        task_id: str = "",
        **kwargs,
    ) -> PolicyDecision:
        """Convenience method for evaluating a single action."""
        context = PolicyContext(
            action_type=action_type,
            target_url=target_url,
            tenant_id=tenant_id,
            user_id=user_id,
            task_id=task_id,
            **kwargs,
        )
        return await self.evaluate(context)

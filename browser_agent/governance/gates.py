"""Built-in approval gates for common enterprise scenarios."""

from typing import List, Optional

from .policy_engine import PolicyRule, PolicyCondition, PolicyEffect, ApprovalConfig


class Gate:
    """Base class for approval gates."""
    def get_rules(self, tenant_id: Optional[str] = None) -> List[PolicyRule]:
        raise NotImplementedError


class ProductionURLGate(Gate):
    """Require approval for actions on production URLs."""

    def __init__(self, patterns: List[str], approvers: List[str],
                 priority: int = 100, tenant_id: Optional[str] = None):
        self._patterns = patterns
        self._approvers = approvers
        self._priority = priority
        self._tenant_id = tenant_id

    def get_rules(self, tenant_id: Optional[str] = None) -> List[PolicyRule]:
        return [PolicyRule(
            rule_id=f"gate_prod_url_{i}",
            name=f"Production URL Gate ({p})",
            description=f"Requires approval for actions on {p}",
            effect=PolicyEffect.REQUIRE_APPROVAL,
            conditions=[PolicyCondition(
                field="target_url", operator="matches", value=p,
            )],
            approval_config=ApprovalConfig(approvers=self._approvers),
            priority=self._priority,
            tenant_id=tenant_id or self._tenant_id,
        ) for i, p in enumerate(self._patterns)]


class DestructiveActionGate(Gate):
    """Require approval for delete, submit, and bulk operations."""

    DESTRUCTIVE_PATTERNS = [
        r"(?i)(delete|remove|destroy|purge|drop)",
        r"(?i)(submit|confirm|finalize)",
    ]

    def __init__(self, approvers: List[str], priority: int = 90,
                 tenant_id: Optional[str] = None):
        self._approvers = approvers
        self._priority = priority
        self._tenant_id = tenant_id

    def get_rules(self, tenant_id: Optional[str] = None) -> List[PolicyRule]:
        return [PolicyRule(
            rule_id=f"gate_destructive_{i}",
            name="Destructive Action Gate",
            description="Requires approval for destructive actions",
            effect=PolicyEffect.REQUIRE_APPROVAL,
            conditions=[PolicyCondition(
                field="target_element", operator="matches", value=p,
            )],
            approval_config=ApprovalConfig(approvers=self._approvers),
            priority=self._priority,
            tenant_id=tenant_id or self._tenant_id,
        ) for i, p in enumerate(self.DESTRUCTIVE_PATTERNS)]


class SensitiveDataGate(Gate):
    """Require approval when extracting CONFIDENTIAL or RESTRICTED data."""

    def __init__(self, threshold: str = "confidential", approvers: Optional[List[str]] = None,
                 priority: int = 80, tenant_id: Optional[str] = None):
        self._threshold = threshold
        self._approvers = approvers or []
        self._priority = priority
        self._tenant_id = tenant_id

    def get_rules(self, tenant_id: Optional[str] = None) -> List[PolicyRule]:
        rules = []
        for level in ["confidential", "restricted", "top_secret"]:
            if level == "public" or level == "internal":
                continue
            rules.append(PolicyRule(
                rule_id=f"gate_sensitive_{level}",
                name=f"Sensitive Data Gate ({level})",
                description=f"Requires approval for {level} data",
                effect=PolicyEffect.REQUIRE_APPROVAL,
                conditions=[PolicyCondition(
                    field="data_sensitivity", operator="equals", value=level,
                )],
                approval_config=ApprovalConfig(approvers=self._approvers),
                priority=self._priority,
                tenant_id=tenant_id or self._tenant_id,
            ))
        return rules


class FinancialTransactionGate(Gate):
    """Require approval for any action involving financial amounts."""

    FINANCIAL_PATTERNS = [
        r"\$[\d,]+\.?\d*",
        r"(?i)(payment|purchase|transfer|withdrawal)",
    ]

    def __init__(self, approvers: List[str], priority: int = 95,
                 tenant_id: Optional[str] = None):
        self._approvers = approvers
        self._priority = priority
        self._tenant_id = tenant_id

    def get_rules(self, tenant_id: Optional[str] = None) -> List[PolicyRule]:
        return [PolicyRule(
            rule_id=f"gate_financial_{i}",
            name="Financial Transaction Gate",
            description="Requires approval for financial transactions",
            effect=PolicyEffect.REQUIRE_APPROVAL,
            conditions=[PolicyCondition(
                field="extracted_data_preview", operator="matches", value=p,
            )],
            approval_config=ApprovalConfig(approvers=self._approvers),
            priority=self._priority,
            tenant_id=tenant_id or self._tenant_id,
        ) for i, p in enumerate(self.FINANCIAL_PATTERNS)]


class ExternalSiteGate(Gate):
    """Require approval for navigating to non-whitelisted domains."""

    def __init__(self, allowed_domains: List[str], approvers: List[str],
                 priority: int = 70, tenant_id: Optional[str] = None):
        self._allowed = allowed_domains
        self._approvers = approvers
        self._priority = priority
        self._tenant_id = tenant_id

    def get_rules(self, tenant_id: Optional[str] = None) -> List[PolicyRule]:
        # Build a negative match: deny anything NOT matching allowed domains
        # This is handled as: for each action on external URL, require approval
        # unless URL contains an allowed domain
        rules = []
        for domain in self._allowed:
            # Allow rule for whitelisted domains
            rules.append(PolicyRule(
                rule_id=f"gate_external_allow_{domain.replace('.', '_')}",
                name=f"External Site Allow ({domain})",
                description=f"Allow actions on {domain}",
                effect=PolicyEffect.ALLOW,
                conditions=[PolicyCondition(
                    field="target_url", operator="contains", value=domain,
                )],
                priority=self._priority + 1,  # Higher priority than the require_approval rule
                tenant_id=tenant_id or self._tenant_id,
            ))
        # Catch-all: require approval for anything else
        rules.append(PolicyRule(
            rule_id="gate_external_default",
            name="External Site Gate (default)",
            description="Requires approval for non-whitelisted external sites",
            effect=PolicyEffect.REQUIRE_APPROVAL,
            conditions=[],  # Matches everything if no higher-priority rule matched
            approval_config=ApprovalConfig(approvers=self._approvers),
            priority=self._priority,
            tenant_id=tenant_id or self._tenant_id,
        ))
        return rules

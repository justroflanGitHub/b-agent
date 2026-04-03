"""Built-in policy templates for common enterprise scenarios."""

from typing import List, Optional, Tuple

from .policy_engine import PolicyRule, PolicyCondition, PolicyEffect, ApprovalConfig


class PolicyTemplates:
    """Ready-to-use policy templates."""

    @staticmethod
    def production_only_approve(
        production_patterns: List[str],
        approvers: List[str],
        tenant_id: Optional[str] = None,
    ) -> List[PolicyRule]:
        """All actions on production systems require approval."""
        return [
            PolicyRule(
                rule_id=f"tpl_prod_{i}",
                name=f"Production Approve ({p})",
                effect=PolicyEffect.REQUIRE_APPROVAL,
                conditions=[PolicyCondition("target_url", "matches", p)],
                approval_config=ApprovalConfig(approvers=approvers),
                priority=100,
                tenant_id=tenant_id,
            )
            for i, p in enumerate(production_patterns)
        ]

    @staticmethod
    def data_extraction_guard(
        sensitivity_threshold: str,
        approvers: List[str],
        tenant_id: Optional[str] = None,
    ) -> List[PolicyRule]:
        """Guard against extracting sensitive data without approval."""
        levels = ["confidential", "restricted", "top_secret"]
        threshold_idx = levels.index(sensitivity_threshold) if sensitivity_threshold in levels else 0
        rules = []
        for level in levels[threshold_idx:]:
            rules.append(PolicyRule(
                rule_id=f"tpl_data_guard_{level}",
                name=f"Data Extraction Guard ({level})",
                effect=PolicyEffect.REQUIRE_APPROVAL,
                conditions=[PolicyCondition("data_sensitivity", "equals", level)],
                approval_config=ApprovalConfig(approvers=approvers),
                priority=80,
                tenant_id=tenant_id,
            ))
        return rules

    @staticmethod
    def cost_control(
        max_daily_tasks: int,
        approvers: List[str],
        tenant_id: Optional[str] = None,
    ) -> List[PolicyRule]:
        """Require approval if daily task count exceeds threshold."""
        return [PolicyRule(
            rule_id="tpl_cost_control",
            name="Cost Control Gate",
            effect=PolicyEffect.REQUIRE_APPROVAL,
            conditions=[PolicyCondition("daily_task_count", "greater_than", max_daily_tasks)],
            approval_config=ApprovalConfig(approvers=approvers),
            priority=50,
            tenant_id=tenant_id,
        )]

    @staticmethod
    def credential_use_approve(
        sensitive_aliases: List[str],
        approvers: List[str],
        tenant_id: Optional[str] = None,
    ) -> List[PolicyRule]:
        """Require approval when using certain credentials."""
        return [
            PolicyRule(
                rule_id=f"tpl_cred_{alias}",
                name=f"Credential Use Gate ({alias})",
                effect=PolicyEffect.REQUIRE_APPROVAL,
                conditions=[PolicyCondition("credential_alias", "equals", alias)],
                approval_config=ApprovalConfig(approvers=approvers),
                priority=90,
                tenant_id=tenant_id,
            )
            for alias in sensitive_aliases
        ]

    @staticmethod
    def block_by_action_type(
        blocked_actions: List[str],
        reason: str = "Action blocked by policy",
        tenant_id: Optional[str] = None,
    ) -> List[PolicyRule]:
        """Block specific action types entirely."""
        return [
            PolicyRule(
                rule_id=f"tpl_block_{action}",
                name=f"Block Action ({action})",
                description=reason,
                effect=PolicyEffect.DENY,
                conditions=[PolicyCondition("action_type", "equals", action)],
                priority=200,
                tenant_id=tenant_id,
            )
            for action in blocked_actions
        ]

    @staticmethod
    def full_compliance(tenant_id: Optional[str] = None) -> List[PolicyRule]:
        """Full compliance mode: approve everything."""
        return [PolicyRule(
            rule_id="tpl_full_compliance",
            name="Full Compliance Mode",
            description="All actions require approval",
            effect=PolicyEffect.REQUIRE_APPROVAL,
            conditions=[],
            approval_config=ApprovalConfig(approvers=["compliance@corp.com"]),
            priority=1,
            tenant_id=tenant_id,
        )]

"""Tests for browser_agent.governance — policy engine, approvals, gates."""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone

from browser_agent.governance.policy_engine import (
    PolicyEngine, PolicyRule, PolicyContext, PolicyDecision,
    PolicyEffect, PolicyCondition, ApprovalConfig,
)
from browser_agent.governance.approval import (
    ApprovalManager, ApprovalRequest, ApprovalStatus, ApprovalStore,
)
from browser_agent.governance.gates import (
    ProductionURLGate, DestructiveActionGate, SensitiveDataGate,
    FinancialTransactionGate, ExternalSiteGate,
)
from browser_agent.governance.policy_definitions import PolicyTemplates
from browser_agent.governance.notifiers import CompositeNotifier, EmailNotifier


# --- PolicyCondition ---


class TestPolicyCondition:
    def test_equals(self):
        c = PolicyCondition("action_type", "equals", "click")
        assert c.evaluate({"action_type": "click"}) is True
        assert c.evaluate({"action_type": "type"}) is False

    def test_contains(self):
        c = PolicyCondition("target_url", "contains", "salesforce")
        assert c.evaluate({"target_url": "https://prod.salesforce.com"}) is True
        assert c.evaluate({"target_url": "https://google.com"}) is False

    def test_matches(self):
        c = PolicyCondition("target_url", "matches", r"prod\.\w+\.com")
        assert c.evaluate({"target_url": "https://prod.salesforce.com"}) is True
        assert c.evaluate({"target_url": "https://dev.salesforce.com"}) is False

    def test_in(self):
        c = PolicyCondition("action_type", "in", ["click", "submit"])
        assert c.evaluate({"action_type": "click"}) is True
        assert c.evaluate({"action_type": "type"}) is False

    def test_not_equals(self):
        c = PolicyCondition("tenant_id", "not_equals", "blocked")
        assert c.evaluate({"tenant_id": "acme"}) is True
        assert c.evaluate({"tenant_id": "blocked"}) is False

    def test_missing_field(self):
        c = PolicyCondition("nonexistent", "equals", "x")
        assert c.evaluate({}) is False

    def test_greater_than(self):
        c = PolicyCondition("step_index", "greater_than", 5)
        assert c.evaluate({"step_index": 10}) is True
        assert c.evaluate({"step_index": 3}) is False


# --- PolicyRule ---


class TestPolicyRule:
    def test_matches_all_conditions(self):
        rule = PolicyRule(
            rule_id="r1", name="test",
            conditions=[
                PolicyCondition("action_type", "equals", "click"),
                PolicyCondition("target_url", "contains", "prod"),
            ],
        )
        assert rule.matches({"action_type": "click", "target_url": "https://prod.sf.com"}) is True
        assert rule.matches({"action_type": "click", "target_url": "https://dev.sf.com"}) is False

    def test_disabled_never_matches(self):
        rule = PolicyRule(
            rule_id="r2", name="test", enabled=False,
            conditions=[PolicyCondition("action_type", "equals", "click")],
        )
        assert rule.matches({"action_type": "click"}) is False

    def test_to_dict(self):
        rule = PolicyRule(rule_id="r3", name="test", effect=PolicyEffect.DENY)
        d = rule.to_dict()
        assert d["effect"] == "deny"


# --- PolicyEngine ---


class TestPolicyEngine:
    @pytest.mark.asyncio
    async def test_no_rules_default_allow(self):
        engine = PolicyEngine()
        decision = await engine.evaluate(PolicyContext(action_type="click"))
        assert decision.effect == PolicyEffect.ALLOW

    @pytest.mark.asyncio
    async def test_matching_rule_returns_effect(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="deny_click", name="Block clicks on prod",
                effect=PolicyEffect.DENY,
                conditions=[
                    PolicyCondition("action_type", "equals", "click"),
                    PolicyCondition("target_url", "contains", "prod"),
                ],
                priority=10,
            ),
        ])
        decision = await engine.evaluate(PolicyContext(
            action_type="click", target_url="https://prod.sf.com",
        ))
        assert decision.effect == PolicyEffect.DENY
        assert decision.matched_rule is not None

    @pytest.mark.asyncio
    async def test_higher_priority_wins(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="low", name="Low priority deny",
                effect=PolicyEffect.DENY,
                conditions=[PolicyCondition("action_type", "equals", "click")],
                priority=1,
            ),
            PolicyRule(
                rule_id="high", name="High priority allow",
                effect=PolicyEffect.ALLOW,
                conditions=[PolicyCondition("action_type", "equals", "click")],
                priority=100,
            ),
        ])
        decision = await engine.evaluate(PolicyContext(action_type="click"))
        assert decision.effect == PolicyEffect.ALLOW
        assert decision.matched_rule.rule_id == "high"

    @pytest.mark.asyncio
    async def test_require_approval(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="approve_prod", name="Require approval on prod",
                effect=PolicyEffect.REQUIRE_APPROVAL,
                conditions=[PolicyCondition("target_url", "contains", "prod")],
                approval_config=ApprovalConfig(approvers=["manager@corp.com"]),
                priority=50,
            ),
        ])
        decision = await engine.evaluate(PolicyContext(target_url="https://prod.sf.com"))
        assert decision.effect == PolicyEffect.REQUIRE_APPROVAL
        assert decision.requires_approval is True
        assert decision.approval_config is not None

    @pytest.mark.asyncio
    async def test_tenant_scoping(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="acme_only", name="Acme rule",
                effect=PolicyEffect.DENY,
                conditions=[PolicyCondition("action_type", "equals", "click")],
                tenant_id="acme",
                priority=10,
            ),
        ])
        # Matches for acme
        d1 = await engine.evaluate(PolicyContext(action_type="click", tenant_id="acme"))
        assert d1.effect == PolicyEffect.DENY
        # Does not match for other tenants
        d2 = await engine.evaluate(PolicyContext(action_type="click", tenant_id="globex"))
        assert d2.effect == PolicyEffect.ALLOW

    @pytest.mark.asyncio
    async def test_add_and_remove_rule(self):
        engine = PolicyEngine()
        rule = PolicyRule(
            rule_id="new_rule", name="New",
            effect=PolicyEffect.DENY,
            conditions=[PolicyCondition("action_type", "equals", "click")],
        )
        await engine.add_rule(rule)
        assert len(engine.rules) == 1
        await engine.remove_rule("new_rule")
        assert len(engine.rules) == 0

    @pytest.mark.asyncio
    async def test_list_rules(self):
        engine = PolicyEngine(rules=[
            PolicyRule(rule_id="r1", name="Global", tenant_id=None),
            PolicyRule(rule_id="r2", name="Acme", tenant_id="acme"),
        ])
        all_rules = await engine.list_rules()
        assert len(all_rules) == 2
        acme_rules = await engine.list_rules("acme")
        assert len(acme_rules) == 2  # global + acme

    @pytest.mark.asyncio
    async def test_dry_run(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="block", name="Block all",
                effect=PolicyEffect.DENY,
                conditions=[],
                priority=1,
            ),
        ])
        decision = await engine.dry_run(PolicyContext())
        assert decision.effect == PolicyEffect.DENY

    @pytest.mark.asyncio
    async def test_evaluate_action_convenience(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="block_delete", name="Block delete",
                effect=PolicyEffect.DENY,
                conditions=[PolicyCondition("action_type", "equals", "delete")],
            ),
        ])
        d = await engine.evaluate_action("click", "https://example.com")
        assert d.effect == PolicyEffect.ALLOW
        d = await engine.evaluate_action("delete", "https://example.com")
        assert d.effect == PolicyEffect.DENY


# --- ApprovalManager ---


class TestApprovalManager:
    @pytest.fixture
    def manager(self, tmp_path):
        store = ApprovalStore(str(tmp_path / "approvals.db"))
        return ApprovalManager(store=store)

    @pytest.mark.asyncio
    async def test_request_and_approve(self, manager):
        ctx = PolicyContext(action_type="click", target_url="https://prod.sf.com", task_id="t1")
        request = await manager.request_approval(
            context=ctx, rule_id="prod_gate",
            approval_config=ApprovalConfig(approvers=["manager@corp.com"]),
        )
        assert request.status == ApprovalStatus.PENDING

        resolved = await manager.approve(request.request_id, "manager@corp.com", "Looks good")
        assert resolved.status == ApprovalStatus.APPROVED
        assert resolved.resolved_by == "manager@corp.com"

    @pytest.mark.asyncio
    async def test_request_and_deny(self, manager):
        ctx = PolicyContext(action_type="delete", task_id="t2")
        request = await manager.request_approval(
            context=ctx,
            approval_config=ApprovalConfig(approvers=["admin@corp.com"]),
        )
        resolved = await manager.deny(request.request_id, "admin@corp.com", "Too risky")
        assert resolved.status == ApprovalStatus.DENIED

    @pytest.mark.asyncio
    async def test_approve_nonexistent_raises(self, manager):
        with pytest.raises(KeyError):
            await manager.approve("nonexistent", "user")

    @pytest.mark.asyncio
    async def test_double_approve_raises(self, manager):
        ctx = PolicyContext(task_id="t3")
        req = await manager.request_approval(
            context=ctx, approval_config=ApprovalConfig(approvers=["a@b.com"]),
        )
        await manager.approve(req.request_id, "a@b.com")
        with pytest.raises(ValueError, match="not pending"):
            await manager.approve(req.request_id, "a@b.com")

    @pytest.mark.asyncio
    async def test_cancel(self, manager):
        ctx = PolicyContext(task_id="t4")
        req = await manager.request_approval(
            context=ctx, approval_config=ApprovalConfig(approvers=["a@b.com"]),
        )
        resolved = await manager.cancel(req.request_id, "Task cancelled")
        assert resolved.status == ApprovalStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_get_pending(self, manager):
        for i in range(3):
            ctx = PolicyContext(task_id=f"t{i}")
            await manager.request_approval(
                context=ctx,
                approval_config=ApprovalConfig(approvers=["a@b.com"]),
            )
        pending = await manager.get_pending()
        assert len(pending) == 3

    @pytest.mark.asyncio
    async def test_check_expired(self, manager):
        config = ApprovalConfig(
            approvers=["a@b.com"],
            timeout_seconds=0,  # Immediately expires
            auto_deny_on_timeout=True,
        )
        ctx = PolicyContext(task_id="expired")
        req = await manager.request_approval(context=ctx, approval_config=config)
        # Force expiry
        req.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await manager._store.update(req)

        expired = await manager.check_expired()
        assert len(expired) == 1
        assert expired[0].status == ApprovalStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_wait_for_approval(self, manager):
        ctx = PolicyContext(task_id="t_wait")
        req = await manager.request_approval(
            context=ctx,
            approval_config=ApprovalConfig(approvers=["a@b.com"], timeout_seconds=60),
        )

        # Approve in background
        async def approve_later():
            await asyncio.sleep(0.1)
            await manager.approve(req.request_id, "a@b.com")

        asyncio.create_task(approve_later())
        resolved = await manager.wait_for_approval(req.request_id, timeout=5)
        assert resolved.status == ApprovalStatus.APPROVED


# --- Gates ---


class TestGates:
    def test_production_url_gate(self):
        gate = ProductionURLGate(
            patterns=[r"prod\.\w+\.com"],
            approvers=["admin@corp.com"],
        )
        rules = gate.get_rules()
        assert len(rules) == 1
        assert rules[0].effect == PolicyEffect.REQUIRE_APPROVAL

    def test_destructive_action_gate(self):
        gate = DestructiveActionGate(approvers=["admin@corp.com"])
        rules = gate.get_rules()
        assert len(rules) >= 1

    def test_sensitive_data_gate(self):
        gate = SensitiveDataGate(approvers=["dpo@corp.com"])
        rules = gate.get_rules()
        assert len(rules) >= 2  # confidential + restricted + top_secret

    def test_financial_transaction_gate(self):
        gate = FinancialTransactionGate(approvers=["cfo@corp.com"])
        rules = gate.get_rules()
        assert len(rules) >= 1

    def test_external_site_gate(self):
        gate = ExternalSiteGate(
            allowed_domains=["salesforce.com", "internal.corp.com"],
            approvers=["admin@corp.com"],
        )
        rules = gate.get_rules()
        # 2 allow rules + 1 catch-all
        assert len(rules) == 3


# --- PolicyTemplates ---


class TestPolicyTemplates:
    def test_production_only_approve(self):
        rules = PolicyTemplates.production_only_approve(
            production_patterns=[r"prod\.sf\.com"],
            approvers=["mgr@corp.com"],
        )
        assert len(rules) == 1
        assert rules[0].effect == PolicyEffect.REQUIRE_APPROVAL

    def test_data_extraction_guard(self):
        rules = PolicyTemplates.data_extraction_guard(
            sensitivity_threshold="confidential",
            approvers=["dpo@corp.com"],
        )
        assert len(rules) >= 1

    def test_credential_use_approve(self):
        rules = PolicyTemplates.credential_use_approve(
            sensitive_aliases=["prod_db", "admin_panel"],
            approvers=["admin@corp.com"],
        )
        assert len(rules) == 2

    def test_block_by_action_type(self):
        rules = PolicyTemplates.block_by_action_type(
            blocked_actions=["delete", "drop"],
        )
        assert len(rules) == 2
        assert all(r.effect == PolicyEffect.DENY for r in rules)

    def test_full_compliance(self):
        rules = PolicyTemplates.full_compliance()
        assert len(rules) == 1
        assert rules[0].effect == PolicyEffect.REQUIRE_APPROVAL

    def test_cost_control(self):
        rules = PolicyTemplates.cost_control(
            max_daily_tasks=100, approvers=["admin"],
        )
        assert len(rules) == 1


# --- CompositeNotifier ---


class TestCompositeNotifier:
    @pytest.mark.asyncio
    async def test_composite_sends_to_all(self):
        email1 = EmailNotifier()
        email2 = EmailNotifier()
        composite = CompositeNotifier([email1, email2])

        req = ApprovalRequest(
            task_id="t1",
            description="Test",
        )
        # Should not raise
        result = await composite.send_approval_request(req)
        assert result is True


# --- Integration: Engine + Approval ---


class TestGovernanceIntegration:
    @pytest.mark.asyncio
    async def test_full_governance_flow(self, tmp_path):
        """Test: policy evaluates → requires approval → manager approves → action proceeds."""
        store = ApprovalStore(str(tmp_path / "approvals.db"))
        manager = ApprovalManager(store=store)

        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="prod_gate",
                name="Production URL Gate",
                effect=PolicyEffect.REQUIRE_APPROVAL,
                conditions=[PolicyCondition("target_url", "contains", "prod")],
                approval_config=ApprovalConfig(
                    approvers=["manager@corp.com"],
                    timeout_seconds=3600,
                ),
                priority=100,
            ),
        ])

        # Step 1: Evaluate policy
        decision = await engine.evaluate(PolicyContext(
            action_type="click",
            target_url="https://prod.salesforce.com",
            tenant_id="acme",
            task_id="task-123",
        ))
        assert decision.requires_approval is True

        # Step 2: Request approval
        request = await manager.request_approval(
            context=PolicyContext(
                action_type="click",
                target_url="https://prod.salesforce.com",
                tenant_id="acme",
                task_id="task-123",
            ),
            rule_id="prod_gate",
            approval_config=decision.approval_config,
        )
        assert request.status == ApprovalStatus.PENDING

        # Step 3: Approve
        resolved = await manager.approve(request.request_id, "manager@corp.com", "Approved")
        assert resolved.status == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_deny_blocks_action(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="block_external",
                name="Block external",
                effect=PolicyEffect.DENY,
                conditions=[PolicyCondition("target_url", "contains", "facebook.com")],
                priority=100,
            ),
        ])
        decision = await engine.evaluate(PolicyContext(
            target_url="https://facebook.com",
        ))
        assert decision.effect == PolicyEffect.DENY
        assert decision.requires_approval is False

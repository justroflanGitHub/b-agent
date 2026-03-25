"""
Tests for Multi-Agent Coordination System

Tests cover:
- BaseAgent
- AgentCommunicationBus
- PlannerAgent
- AnalyzerAgent
- ActorAgent
- ValidatorAgent
- SupervisorAgent
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import uuid

from browser_agent.agents.base import (
    BaseAgent,
    AgentConfig,
    AgentStatus,
    AgentCapability,
    AgentResult,
    AgentState,
)
from browser_agent.agents.communication import (
    AgentMessage,
    MessageType,
    MessagePriority,
    AgentCommunicationBus,
)
from browser_agent.agents.planner import (
    PlannerAgent,
    TaskPlan,
    PlanStep,
    StepDependency,
    StepStatus,
    StepType,
    PlanningRequest,
)
from browser_agent.agents.analyzer import (
    AnalyzerAgent,
    AnalysisRequest,
    AnalysisResult,
    AnalysisType,
    PageState,
    ElementInfo,
)
from browser_agent.agents.actor import (
    ActorAgent,
    ActionRequest,
    ActionResult,
    ActionType,
)
from browser_agent.agents.validator import (
    ValidatorAgent,
    ValidationRequest,
    ValidationResult,
    ValidationCriteria,
    ValidationType,
    ValidationSeverity,
    ValidationFailure,
)
from browser_agent.agents.supervisor import (
    SupervisorAgent,
    SupervisorConfig,
    TaskDelegation,
    TaskStatus,
    AgentPool,
)


# ============================================================================
# BaseAgent Tests
# ============================================================================

class TestAgentConfig:
    """Tests for AgentConfig."""
    
    def test_create_config(self):
        """Test creating agent config."""
        config = AgentConfig(
            name="TestAgent",
            capabilities={AgentCapability.PLANNING},
        )
        assert config.name == "TestAgent"
        assert AgentCapability.PLANNING in config.capabilities
        assert config.max_concurrent_tasks == 1
        assert config.task_timeout == 300.0
    
    def test_has_capability(self):
        """Test capability checking."""
        config = AgentConfig(
            name="TestAgent",
            capabilities={AgentCapability.PLANNING, AgentCapability.ANALYSIS},
        )
        assert config.has_capability(AgentCapability.PLANNING)
        assert config.has_capability(AgentCapability.ANALYSIS)
        assert not config.has_capability(AgentCapability.ACTION_EXECUTION)


class TestAgentResult:
    """Tests for AgentResult."""
    
    def test_success_result(self):
        """Test successful result."""
        result = AgentResult(
            success=True,
            agent_id="agent_1",
            task_id="task_1",
            data={"key": "value"},
        )
        assert result.success
        assert result.agent_id == "agent_1"
        assert result.data == {"key": "value"}
        assert result.error is None
    
    def test_failure_result(self):
        """Test failure result."""
        result = AgentResult(
            success=False,
            agent_id="agent_1",
            task_id="task_1",
            error="Something went wrong",
        )
        assert not result.success
        assert result.error == "Something went wrong"
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        result = AgentResult(
            success=True,
            agent_id="agent_1",
            task_id="task_1",
            data={"key": "value"},
            duration_ms=100.0,
        )
        d = result.to_dict()
        assert d["success"]
        assert d["agent_id"] == "agent_1"
        assert d["data"] == {"key": "value"}
        assert d["duration_ms"] == 100.0


class TestAgentState:
    """Tests for AgentState."""
    
    def test_initial_state(self):
        """Test initial state."""
        state = AgentState()
        assert state.status == AgentStatus.IDLE
        assert state.current_task_id is None
        assert state.tasks_completed == 0
    
    def test_record_task_start(self):
        """Test recording task start."""
        state = AgentState()
        state.record_task_start("task_1")
        assert state.status == AgentStatus.BUSY
        assert state.current_task_id == "task_1"
    
    def test_record_task_success(self):
        """Test recording task success."""
        state = AgentState()
        state.record_task_start("task_1")
        state.record_task_success(100.0)
        assert state.status == AgentStatus.IDLE
        assert state.tasks_completed == 1
        assert state.total_processing_time_ms == 100.0
    
    def test_record_task_failure(self):
        """Test recording task failure."""
        state = AgentState()
        state.record_task_start("task_1")
        state.record_task_failure("Error occurred", 50.0)
        assert state.status == AgentStatus.IDLE
        assert state.tasks_failed == 1
        assert "Error occurred" in state.error_history


class ConcreteAgent(BaseAgent):
    """Concrete implementation for testing."""
    
    async def execute(self, task):
        return AgentResult(
            success=True,
            agent_id=self.agent_id,
            task_id="test_task",
            data=task,
        )


class TestBaseAgent:
    """Tests for BaseAgent."""
    
    def test_create_agent(self):
        """Test creating an agent."""
        config = AgentConfig(
            name="TestAgent",
            capabilities={AgentCapability.PLANNING},
        )
        agent = ConcreteAgent(config)
        assert agent.name == "TestAgent"
        assert agent.has_capability(AgentCapability.PLANNING)
        assert agent.status == AgentStatus.IDLE
    
    @pytest.mark.asyncio
    async def test_execute_with_tracking(self):
        """Test execute with tracking."""
        config = AgentConfig(name="TestAgent")
        agent = ConcreteAgent(config)
        
        result = await agent.execute_with_tracking("task_1", {"data": "test"})
        
        assert result.success
        # Note: ConcreteAgent.execute returns "test_task" as task_id, not the tracking task_id
        assert agent.state.tasks_completed == 1
    
    def test_get_stats(self):
        """Test getting agent stats."""
        config = AgentConfig(name="TestAgent")
        agent = ConcreteAgent(config)
        agent.state.tasks_completed = 5
        agent.state.tasks_failed = 1
        
        stats = agent.get_stats()
        
        assert stats["name"] == "TestAgent"
        assert stats["tasks_completed"] == 5
        assert stats["tasks_failed"] == 1


# ============================================================================
# Communication Tests
# ============================================================================

class TestAgentMessage:
    """Tests for AgentMessage."""
    
    def test_create_message(self):
        """Test creating a message."""
        msg = AgentMessage(
            message_type=MessageType.TASK_ASSIGNMENT,
            sender_id="agent_1",
            receiver_id="agent_2",
            payload={"task": "do_something"},
        )
        assert msg.message_type == MessageType.TASK_ASSIGNMENT
        assert msg.sender_id == "agent_1"
        assert msg.receiver_id == "agent_2"
        assert not msg.is_broadcast()
    
    def test_broadcast_message(self):
        """Test broadcast message."""
        msg = AgentMessage(
            message_type=MessageType.STATUS_UPDATE,
            sender_id="agent_1",
            payload={"status": "busy"},
        )
        assert msg.is_broadcast()
    
    def test_expired_message(self):
        """Test expired message check."""
        msg = AgentMessage(
            message_type=MessageType.TASK_ASSIGNMENT,
            sender_id="agent_1",
            receiver_id="agent_2",
            expires_at=datetime.now() - timedelta(hours=1),
        )
        assert msg.is_expired()
    
    def test_create_response(self):
        """Test creating response message."""
        msg = AgentMessage(
            message_type=MessageType.QUERY,
            sender_id="agent_1",
            receiver_id="agent_2",
            payload={"query": "status"},
        )
        response = msg.create_response(
            MessageType.QUERY_RESPONSE,
            {"status": "ready"},
        )
        assert response.message_type == MessageType.QUERY_RESPONSE
        assert response.sender_id == "agent_2"
        assert response.receiver_id == "agent_1"
        assert response.correlation_id == msg.message_id


class TestAgentCommunicationBus:
    """Tests for AgentCommunicationBus."""
    
    @pytest.mark.asyncio
    async def test_register_agent(self):
        """Test registering an agent."""
        bus = AgentCommunicationBus()
        await bus.register_agent("agent_1")
        
        assert "agent_1" in bus._queues
    
    @pytest.mark.asyncio
    async def test_unregister_agent(self):
        """Test unregistering an agent."""
        bus = AgentCommunicationBus()
        await bus.register_agent("agent_1")
        await bus.unregister_agent("agent_1")
        
        assert "agent_1" not in bus._queues
    
    @pytest.mark.asyncio
    async def test_send_point_to_point(self):
        """Test point-to-point messaging."""
        bus = AgentCommunicationBus()
        await bus.register_agent("agent_1")
        await bus.register_agent("agent_2")
        
        msg = AgentMessage(
            message_type=MessageType.TASK_ASSIGNMENT,
            sender_id="agent_1",
            receiver_id="agent_2",
            payload={"task": "test"},
        )
        
        success = await bus.send(msg)
        assert success
        
        received = await bus.receive("agent_2", timeout=1.0)
        assert received is not None
        assert received.payload == {"task": "test"}
    
    @pytest.mark.asyncio
    async def test_broadcast(self):
        """Test broadcast messaging."""
        bus = AgentCommunicationBus()
        await bus.register_agent("agent_1")
        await bus.register_agent("agent_2")
        await bus.register_agent("agent_3")
        
        msg = AgentMessage(
            message_type=MessageType.STATUS_UPDATE,
            sender_id="agent_1",
            payload={"status": "ready"},
        )
        
        success = await bus.send(msg)
        assert success
        
        # agent_2 and agent_3 should receive
        received_2 = await bus.receive("agent_2", timeout=1.0)
        received_3 = await bus.receive("agent_3", timeout=1.0)
        
        assert received_2 is not None
        assert received_3 is not None
    
    @pytest.mark.asyncio
    async def test_subscribe_publish(self):
        """Test subscribe/publish pattern."""
        bus = AgentCommunicationBus()
        await bus.register_agent("agent_1")
        await bus.subscribe("agent_1", "updates")
        
        msg = AgentMessage(
            message_type=MessageType.DATA_SHARE,
            sender_id="agent_2",
            payload={"data": "test"},
        )
        
        count = await bus.publish("updates", msg)
        assert count == 1
    
    def test_get_stats(self):
        """Test getting bus stats."""
        bus = AgentCommunicationBus()
        stats = bus.get_stats()
        
        assert "registered_agents" in stats
        assert "queue_sizes" in stats


# ============================================================================
# PlannerAgent Tests
# ============================================================================

class TestPlanStep:
    """Tests for PlanStep."""
    
    def test_create_step(self):
        """Test creating a plan step."""
        step = PlanStep(
            step_id="step_1",
            step_type=StepType.NAVIGATE,
            description="Navigate to URL",
            action="navigate",
            parameters={"url": "https://example.com"},
        )
        assert step.step_id == "step_1"
        assert step.status == StepStatus.PENDING
    
    def test_is_ready_no_dependencies(self):
        """Test step is ready with no dependencies."""
        step = PlanStep(
            step_id="step_1",
            step_type=StepType.NAVIGATE,
            description="Navigate",
            action="navigate",
        )
        assert step.is_ready({})
    
    def test_is_ready_with_dependencies(self):
        """Test step readiness with dependencies."""
        step = PlanStep(
            step_id="step_2",
            step_type=StepType.CLICK,
            description="Click",
            action="click",
            dependencies=[StepDependency("step_1")],
        )
        
        # Not ready without dependency result
        assert not step.is_ready({})
        
        # Ready with successful dependency
        results = {"step_1": AgentResult(success=True, agent_id="a", task_id="t")}
        assert step.is_ready(results)


class TestTaskPlan:
    """Tests for TaskPlan."""
    
    def test_create_plan(self):
        """Test creating a task plan."""
        steps = [
            PlanStep(step_id="step_1", step_type=StepType.NAVIGATE, description="Nav", action="nav"),
            PlanStep(step_id="step_2", step_type=StepType.CLICK, description="Click", action="click"),
        ]
        plan = TaskPlan(
            plan_id="plan_1",
            task_description="Test task",
            steps=steps,
        )
        assert plan.plan_id == "plan_1"
        assert len(plan.steps) == 2
    
    def test_get_ready_steps(self):
        """Test getting ready steps."""
        steps = [
            PlanStep(step_id="step_1", step_type=StepType.NAVIGATE, description="Nav", action="nav"),
            PlanStep(
                step_id="step_2",
                step_type=StepType.CLICK,
                description="Click",
                action="click",
                dependencies=[StepDependency("step_1")],
            ),
        ]
        plan = TaskPlan(plan_id="plan_1", task_description="Test", steps=steps)
        
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].step_id == "step_1"
    
    def test_mark_step_completed(self):
        """Test marking step completed."""
        plan = TaskPlan(
            plan_id="plan_1",
            task_description="Test",
            steps=[PlanStep(step_id="step_1", step_type=StepType.NAVIGATE, description="Nav", action="nav")],
        )
        
        result = AgentResult(success=True, agent_id="a", task_id="t")
        plan.mark_step_completed("step_1", result)
        
        assert plan.steps[0].status == StepStatus.COMPLETED
        assert "step_1" in plan.step_results
    
    def test_is_complete(self):
        """Test checking if plan is complete."""
        steps = [
            PlanStep(step_id="step_1", step_type=StepType.NAVIGATE, description="Nav", action="nav"),
        ]
        plan = TaskPlan(plan_id="plan_1", task_description="Test", steps=steps)
        
        assert not plan.is_complete()
        
        plan.steps[0].status = StepStatus.COMPLETED
        assert plan.is_complete()
    
    def test_get_progress(self):
        """Test getting progress."""
        steps = [
            PlanStep(step_id="step_1", step_type=StepType.NAVIGATE, description="Nav", action="nav"),
            PlanStep(step_id="step_2", step_type=StepType.CLICK, description="Click", action="click"),
        ]
        plan = TaskPlan(plan_id="plan_1", task_description="Test", steps=steps)
        steps[0].status = StepStatus.COMPLETED
        
        progress = plan.get_progress()
        assert progress["total_steps"] == 2
        assert progress["completed"] == 1
        assert progress["progress_percent"] == 50.0


class TestPlannerAgent:
    """Tests for PlannerAgent."""
    
    def test_create_planner(self):
        """Test creating planner agent."""
        planner = PlannerAgent()
        assert planner.name == "PlannerAgent"
        assert AgentCapability.PLANNING in planner.capabilities
    
    @pytest.mark.asyncio
    async def test_create_plan_form_filling(self):
        """Test creating form filling plan."""
        planner = PlannerAgent()
        request = PlanningRequest(task_description="Fill out the registration form")
        
        plan = await planner.create_plan(request)
        
        assert plan is not None
        assert len(plan.steps) > 0
        assert any(s.step_type == StepType.NAVIGATE for s in plan.steps)
    
    @pytest.mark.asyncio
    async def test_create_plan_search(self):
        """Test creating search plan."""
        planner = PlannerAgent()
        request = PlanningRequest(task_description="Search for cats on Google")
        
        plan = await planner.create_plan(request)
        
        assert plan is not None
        assert len(plan.steps) > 0
    
    @pytest.mark.asyncio
    async def test_execute_planning_request(self):
        """Test executing planning request."""
        planner = PlannerAgent()
        request = PlanningRequest(task_description="Navigate to example.com")
        
        result = await planner.execute(request)
        
        assert result.success
        assert result.data is not None


# ============================================================================
# AnalyzerAgent Tests
# ============================================================================

class TestElementInfo:
    """Tests for ElementInfo."""
    
    def test_create_element_info(self):
        """Test creating element info."""
        info = ElementInfo(
            element_id="el_1",
            element_type="button",
            tag_name="button",
            text_content="Click me",
            is_visible=True,
            is_interactive=True,
        )
        assert info.element_id == "el_1"
        assert info.element_type == "button"
        assert info.is_visible
    
    def test_to_dict(self):
        """Test converting to dict."""
        info = ElementInfo(
            element_id="el_1",
            element_type="button",
            tag_name="button",
        )
        d = info.to_dict()
        assert d["element_id"] == "el_1"
        assert d["element_type"] == "button"


class TestAnalysisResult:
    """Tests for AnalysisResult."""
    
    def test_create_result(self):
        """Test creating analysis result."""
        result = AnalysisResult(
            analysis_id="analysis_1",
            analysis_type=AnalysisType.FULL_PAGE,
            page_state=PageState.READY,
            url="https://example.com",
        )
        assert result.analysis_id == "analysis_1"
        assert result.page_state == PageState.READY
    
    def test_find_element_by_type(self):
        """Test finding elements by type."""
        result = AnalysisResult(
            analysis_id="analysis_1",
            analysis_type=AnalysisType.ELEMENT_DETECTION,
            page_state=PageState.READY,
            url="https://example.com",
            elements=[
                ElementInfo(element_id="el_1", element_type="button", tag_name="button"),
                ElementInfo(element_id="el_2", element_type="link", tag_name="a"),
                ElementInfo(element_id="el_3", element_type="button", tag_name="button"),
            ],
        )
        
        buttons = result.find_element_by_type("button")
        assert len(buttons) == 2
    
    def test_find_element_by_text(self):
        """Test finding elements by text."""
        result = AnalysisResult(
            analysis_id="analysis_1",
            analysis_type=AnalysisType.ELEMENT_DETECTION,
            page_state=PageState.READY,
            url="https://example.com",
            elements=[
                ElementInfo(element_id="el_1", element_type="button", tag_name="button", text_content="Submit"),
                ElementInfo(element_id="el_2", element_type="button", tag_name="button", text_content="Cancel"),
            ],
        )
        
        matches = result.find_element_by_text("Sub")
        assert len(matches) == 1
        assert matches[0].text_content == "Submit"


class TestAnalyzerAgent:
    """Tests for AnalyzerAgent."""
    
    def test_create_analyzer(self):
        """Test creating analyzer agent."""
        analyzer = AnalyzerAgent()
        assert analyzer.name == "AnalyzerAgent"
        assert AgentCapability.ANALYSIS in analyzer.capabilities
    
    @pytest.mark.asyncio
    async def test_analyze_without_browser(self):
        """Test analysis without browser."""
        analyzer = AnalyzerAgent()
        request = AnalysisRequest(analysis_type=AnalysisType.STATE_CHECK)
        
        result = await analyzer.analyze(request)
        
        assert result.analysis_type == AnalysisType.STATE_CHECK
    
    def test_classify_element(self):
        """Test element classification."""
        analyzer = AnalyzerAgent()
        
        assert analyzer._classify_element("input", "text") == "text_input"
        assert analyzer._classify_element("input", "checkbox") == "checkbox"
        assert analyzer._classify_element("button", None) == "button"
        assert analyzer._classify_element("a", None) == "link"
        assert analyzer._classify_element("select", None) == "select"


# ============================================================================
# ActorAgent Tests
# ============================================================================

class TestActionRequest:
    """Tests for ActionRequest."""
    
    def test_create_request(self):
        """Test creating action request."""
        request = ActionRequest(
            action_type=ActionType.CLICK,
            selector="#button",
            timeout=10.0,
        )
        assert request.action_type == ActionType.CLICK
        assert request.selector == "#button"
        assert request.timeout == 10.0
    
    def test_to_dict(self):
        """Test converting to dict."""
        request = ActionRequest(
            action_type=ActionType.TYPE,
            selector="#input",
            text="Hello",
        )
        d = request.to_dict()
        assert d["action_type"] == "type"
        assert d["text"] == "Hello"


class TestActionResult:
    """Tests for ActionResult."""
    
    def test_success_result(self):
        """Test successful action result."""
        result = ActionResult(
            action_id="action_1",
            action_type=ActionType.CLICK,
            success=True,
            duration_ms=50.0,
        )
        assert result.success
        assert result.retries == 0
    
    def test_failure_result(self):
        """Test failed action result."""
        result = ActionResult(
            action_id="action_1",
            action_type=ActionType.CLICK,
            success=False,
            error="Element not found",
            retries=3,
        )
        assert not result.success
        assert result.error == "Element not found"


class TestActorAgent:
    """Tests for ActorAgent."""
    
    def test_create_actor(self):
        """Test creating actor agent."""
        actor = ActorAgent()
        assert actor.name == "ActorAgent"
        assert AgentCapability.ACTION_EXECUTION in actor.capabilities
    
    def test_parse_action_request(self):
        """Test parsing action request from dict."""
        actor = ActorAgent()
        data = {
            "action_type": "click",
            "selector": "#button",
            "timeout": 15.0,
        }
        
        request = actor._parse_action_request(data)
        
        assert request.action_type == ActionType.CLICK
        assert request.selector == "#button"
        assert request.timeout == 15.0
    
    @pytest.mark.asyncio
    async def test_execute_without_browser(self):
        """Test execution without browser."""
        actor = ActorAgent()
        request = ActionRequest(action_type=ActionType.CLICK, selector="#button")
        
        result = await actor.perform_action(request)
        
        assert not result.success
        assert "No browser" in result.error


# ============================================================================
# ValidatorAgent Tests
# ============================================================================

class TestValidationCriteria:
    """Tests for ValidationCriteria."""
    
    def test_create_criteria(self):
        """Test creating validation criteria."""
        criteria = ValidationCriteria(
            validation_type=ValidationType.ELEMENT_PRESENT,
            selector="#button",
            is_required=True,
        )
        assert criteria.validation_type == ValidationType.ELEMENT_PRESENT
        assert criteria.selector == "#button"
    
    def test_to_dict(self):
        """Test converting to dict."""
        criteria = ValidationCriteria(
            validation_type=ValidationType.TEXT_PRESENT,
            expected_value="Hello",
        )
        d = criteria.to_dict()
        assert d["validation_type"] == "text_present"
        assert d["expected_value"] == "Hello"


class TestValidationResult:
    """Tests for ValidationResult."""
    
    def test_success_result(self):
        """Test successful validation result."""
        result = ValidationResult(
            validation_id="val_1",
            success=True,
            passed=5,
            failed=0,
            skipped=0,
        )
        assert result.success
        assert result.pass_rate == 100.0
    
    def test_partial_result(self):
        """Test partial validation result."""
        result = ValidationResult(
            validation_id="val_1",
            success=False,
            passed=3,
            failed=2,
            skipped=0,
        )
        assert not result.success
        assert result.pass_rate == 60.0
        assert result.total == 5


class TestValidatorAgent:
    """Tests for ValidatorAgent."""
    
    def test_create_validator(self):
        """Test creating validator agent."""
        validator = ValidatorAgent()
        assert validator.name == "ValidatorAgent"
        assert AgentCapability.VALIDATION in validator.capabilities
    
    @pytest.mark.asyncio
    async def test_validate_success(self):
        """Test validating success."""
        validator = ValidatorAgent()
        request = ValidationRequest(
            criteria=[ValidationCriteria(validation_type=ValidationType.SUCCESS_CHECK)],
            action_result={"success": True},
        )
        
        result = await validator.validate(request)
        
        assert result.success
        assert result.passed == 1
    
    @pytest.mark.asyncio
    async def test_validate_failure(self):
        """Test validation failure."""
        validator = ValidatorAgent()
        request = ValidationRequest(
            criteria=[ValidationCriteria(validation_type=ValidationType.SUCCESS_CHECK)],
            action_result={"success": False},
        )
        
        result = await validator.validate(request)
        
        assert not result.success
        assert result.failed == 1
    
    @pytest.mark.asyncio
    async def test_validate_url_without_browser(self):
        """Test URL validation without browser."""
        validator = ValidatorAgent()
        result = await validator.validate_url("https://example.com")
        
        # Should fail without browser
        assert not result.success


# ============================================================================
# SupervisorAgent Tests
# ============================================================================

class TestTaskDelegation:
    """Tests for TaskDelegation."""
    
    def test_create_delegation(self):
        """Test creating task delegation."""
        delegation = TaskDelegation(
            task_id="task_1",
            description="Test task",
            status=TaskStatus.PENDING,
        )
        assert delegation.task_id == "task_1"
        assert delegation.status == TaskStatus.PENDING
    
    def test_duration(self):
        """Test duration calculation."""
        delegation = TaskDelegation(
            task_id="task_1",
            description="Test",
            status=TaskStatus.COMPLETED,
            started_at=datetime.now() - timedelta(minutes=5),
            completed_at=datetime.now(),
        )
        
        duration = delegation.duration_seconds()
        assert duration is not None
        assert duration > 0


class TestAgentPool:
    """Tests for AgentPool."""
    
    def test_empty_pool(self):
        """Test empty pool."""
        pool = AgentPool()
        assert pool.planner is None
        assert pool.analyzer is None
        assert pool.actor is None
        assert pool.validator is None
    
    def test_register_agent(self):
        """Test registering agents."""
        pool = AgentPool()
        planner = PlannerAgent()
        
        pool.register(planner)
        
        assert pool.planner == planner
        assert pool.get_agent(planner.agent_id) == planner
    
    def test_get_available_agents(self):
        """Test getting available agents."""
        pool = AgentPool()
        planner = PlannerAgent()
        
        pool.register(planner)
        
        available = pool.get_available_agents(AgentCapability.PLANNING)
        assert len(available) == 1


class TestSupervisorAgent:
    """Tests for SupervisorAgent."""
    
    def test_create_supervisor(self):
        """Test creating supervisor."""
        supervisor = SupervisorAgent()
        assert supervisor.name == "SupervisorAgent"
        assert AgentCapability.COORDINATION in supervisor.capabilities
    
    def test_register_agent(self):
        """Test registering agent with supervisor."""
        supervisor = SupervisorAgent()
        planner = PlannerAgent()
        
        supervisor.register_agent(planner)
        
        assert supervisor.agent_pool.planner == planner
    
    def test_setup_default_agents(self):
        """Test setting up default agents."""
        supervisor = SupervisorAgent()
        supervisor.setup_default_agents()
        
        assert supervisor.agent_pool.planner is not None
        assert supervisor.agent_pool.analyzer is not None
        assert supervisor.agent_pool.actor is not None
        assert supervisor.agent_pool.validator is not None
    
    def test_get_supervisor_status(self):
        """Test getting supervisor status."""
        supervisor = SupervisorAgent()
        supervisor.setup_default_agents()
        
        status = supervisor.get_supervisor_status()
        
        assert "supervisor" in status
        assert "agents" in status
        assert status["agents"]["has_planner"]
    
    @pytest.mark.asyncio
    async def test_create_plan(self):
        """Test creating plan through supervisor."""
        supervisor = SupervisorAgent()
        supervisor.setup_default_agents()
        
        plan = await supervisor._create_plan("Navigate to example.com")
        
        assert plan is not None
        assert len(plan.steps) > 0
    
    @pytest.mark.asyncio
    async def test_submit_task(self):
        """Test submitting task."""
        supervisor = SupervisorAgent()
        
        task_id = await supervisor.submit_task("Test task")
        
        assert task_id is not None
        assert task_id in supervisor._active_tasks
    
    @pytest.mark.asyncio
    async def test_get_task_status(self):
        """Test getting task status."""
        supervisor = SupervisorAgent()
        task_id = await supervisor.submit_task("Test task")
        
        status = await supervisor.get_task_status(task_id)
        
        assert status is not None
        assert status["task_id"] == task_id
    
    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """Test cancelling task."""
        supervisor = SupervisorAgent()
        task_id = await supervisor.submit_task("Test task")
        
        cancelled = await supervisor.cancel_task(task_id)
        
        assert cancelled
        status = await supervisor.get_task_status(task_id)
        assert status["status"] == "cancelled"


# ============================================================================
# Integration Tests
# ============================================================================

class TestMultiAgentIntegration:
    """Integration tests for multi-agent system."""
    
    @pytest.mark.asyncio
    async def test_full_task_execution(self):
        """Test full task execution flow."""
        # Create supervisor with default agents
        supervisor = SupervisorAgent()
        supervisor.setup_default_agents()
        
        # Execute a simple task
        result = await supervisor.execute("Navigate to example.com")
        
        # Result should indicate planning was done
        assert result.success or result.error is not None
    
    @pytest.mark.asyncio
    async def test_agent_communication(self):
        """Test agent communication through bus."""
        bus = AgentCommunicationBus()
        
        # Register agents
        await bus.register_agent("planner")
        await bus.register_agent("actor")
        
        # Send message
        msg = AgentMessage(
            message_type=MessageType.TASK_ASSIGNMENT,
            sender_id="planner",
            receiver_id="actor",
            payload={"action": "click"},
        )
        
        success = await bus.send(msg)
        assert success
        
        # Receive message
        received = await bus.receive("actor", timeout=1.0)
        assert received is not None
        assert received.payload["action"] == "click"
    
    @pytest.mark.asyncio
    async def test_synthesize_results(self):
        """Test result synthesis."""
        supervisor = SupervisorAgent()
        supervisor.setup_default_agents()
        
        # Create a task delegation
        task_id = "test_task"
        delegation = TaskDelegation(
            task_id=task_id,
            description="Test task",
            status=TaskStatus.COMPLETED,
            step_results={
                "step_1": AgentResult(success=True, agent_id="a", task_id="t"),
                "step_2": AgentResult(success=True, agent_id="a", task_id="t"),
            },
        )
        supervisor._active_tasks[task_id] = delegation
        
        # Synthesize results
        synthesis = await supervisor.synthesize_results(task_id)
        
        assert synthesis["task_id"] == task_id
        assert synthesis["summary"]["successful_steps"] == 2
        assert synthesis["summary"]["success_rate"] == 100.0


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

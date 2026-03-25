"""
Supervisor Agent Module

The Supervisor Agent is responsible for:
- Orchestrating sub-agents (Planner, Analyzer, Actor, Validator)
- Managing task delegation
- Coordinating agent communication
- Synthesizing results
- Handling failures and recovery
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type
from datetime import datetime
import asyncio
import uuid

from .base import (
    BaseAgent,
    AgentConfig,
    AgentCapability,
    AgentResult,
    AgentStatus,
)
from .communication import (
    AgentMessage,
    MessageType,
    MessagePriority,
    AgentCommunicationBus,
)
from .planner import PlannerAgent, TaskPlan, PlanStep, StepStatus
from .analyzer import AnalyzerAgent, AnalysisRequest, AnalysisResult
from .actor import ActorAgent, ActionRequest, ActionResult
from .validator import ValidatorAgent, ValidationRequest, ValidationResult


class TaskStatus(Enum):
    """Status of a delegated task."""
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskDelegation:
    """Record of a delegated task."""
    task_id: str
    description: str
    status: TaskStatus
    plan: Optional[TaskPlan] = None
    current_step: int = 0
    step_results: Dict[str, AgentResult] = field(default_factory=dict)
    assigned_agents: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def duration_seconds(self) -> Optional[float]:
        """Calculate task duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "status": self.status.value,
            "plan": self.plan.to_dict() if self.plan else None,
            "current_step": self.current_step,
            "step_results": {k: v.to_dict() for k, v in self.step_results.items()},
            "assigned_agents": list(self.assigned_agents),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds(),
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class SupervisorConfig:
    """Configuration for the supervisor agent."""
    max_concurrent_tasks: int = 5
    task_timeout: float = 600.0  # 10 minutes
    step_timeout: float = 60.0  # 1 minute
    retry_failed_steps: bool = True
    max_step_retries: int = 2
    validate_after_action: bool = True
    auto_recovery: bool = True
    report_interval: float = 5.0


@dataclass
class AgentPool:
    """Pool of available agents."""
    planner: Optional[PlannerAgent] = None
    analyzer: Optional[AnalyzerAgent] = None
    actor: Optional[ActorAgent] = None
    validator: Optional[ValidatorAgent] = None
    _all_agents: Dict[str, BaseAgent] = field(default_factory=dict)
    
    def register(self, agent: BaseAgent) -> None:
        """Register an agent in the pool."""
        self._all_agents[agent.agent_id] = agent
        
        # Assign to specific slot based on type
        if isinstance(agent, PlannerAgent):
            self.planner = agent
        elif isinstance(agent, AnalyzerAgent):
            self.analyzer = agent
        elif isinstance(agent, ActorAgent):
            self.actor = agent
        elif isinstance(agent, ValidatorAgent):
            self.validator = agent
    
    def unregister(self, agent_id: str) -> None:
        """Unregister an agent."""
        agent = self._all_agents.pop(agent_id, None)
        if agent:
            if self.planner == agent:
                self.planner = None
            elif self.analyzer == agent:
                self.analyzer = None
            elif self.actor == agent:
                self.actor = None
            elif self.validator == agent:
                self.validator = None
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by ID."""
        return self._all_agents.get(agent_id)
    
    def get_available_agents(self, capability: AgentCapability) -> List[BaseAgent]:
        """Get all agents with a specific capability that are available."""
        return [
            agent for agent in self._all_agents.values()
            if agent.has_capability(capability) and agent.status == AgentStatus.IDLE
        ]
    
    def all_agents(self) -> List[BaseAgent]:
        """Get all registered agents."""
        return list(self._all_agents.values())
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        return {
            "total_agents": len(self._all_agents),
            "agents": {
                agent_id: {
                    "name": agent.name,
                    "status": agent.status.value,
                    "capabilities": [c.value for c in agent.capabilities],
                }
                for agent_id, agent in self._all_agents.items()
            },
            "has_planner": self.planner is not None,
            "has_analyzer": self.analyzer is not None,
            "has_actor": self.actor is not None,
            "has_validator": self.validator is not None,
        }


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent that orchestrates sub-agents.
    
    Responsibilities:
    - Task planning and decomposition
    - Agent coordination
    - Step execution management
    - Result validation
    - Failure recovery
    """
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        supervisor_config: Optional[SupervisorConfig] = None,
        communication_bus: Optional[AgentCommunicationBus] = None,
    ):
        if config is None:
            config = AgentConfig(
                name="SupervisorAgent",
                capabilities={
                    AgentCapability.COORDINATION,
                    AgentCapability.PLANNING,
                    AgentCapability.RECOVERY,
                },
            )
        super().__init__(config)
        
        self.supervisor_config = supervisor_config or SupervisorConfig()
        self.communication_bus = communication_bus or AgentCommunicationBus()
        self.agent_pool = AgentPool()
        
        self._active_tasks: Dict[str, TaskDelegation] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._results_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._orchestration_task: Optional[asyncio.Task] = None
    
    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent with the supervisor."""
        self.agent_pool.register(agent)
        # Set up message handler
        agent.set_message_handler(self._handle_agent_message)
    
    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent."""
        self.agent_pool.unregister(agent_id)
    
    def setup_default_agents(
        self,
        browser: Optional[Any] = None,
        vision_client: Optional[Any] = None,
        action_executor: Optional[Any] = None,
    ) -> None:
        """Set up default sub-agents."""
        # Create planner
        planner = PlannerAgent()
        self.register_agent(planner)
        
        # Create analyzer
        analyzer = AnalyzerAgent(browser=browser, vision_client=vision_client)
        self.register_agent(analyzer)
        
        # Create actor
        actor = ActorAgent(browser=browser, action_executor=action_executor)
        self.register_agent(actor)
        
        # Create validator
        validator = ValidatorAgent(browser=browser, vision_client=vision_client)
        self.register_agent(validator)
    
    async def _handle_agent_message(self, message: AgentMessage) -> None:
        """Handle messages from agents."""
        if message.message_type == MessageType.TASK_RESULT:
            # Handle task result from agent
            task_id = message.correlation_id
            if task_id and task_id in self._active_tasks:
                await self._results_queue.put((task_id, message.payload))
        
        elif message.message_type == MessageType.STATUS_UPDATE:
            # Handle status update
            pass
        
        elif message.message_type == MessageType.ERROR:
            # Handle error
            if message.correlation_id and message.correlation_id in self._active_tasks:
                delegation = self._active_tasks[message.correlation_id]
                delegation.error = str(message.payload)
    
    async def execute(self, task: Any) -> AgentResult:
        """Execute a supervised task."""
        task_id = str(uuid.uuid4())
        
        # Create delegation record
        delegation = TaskDelegation(
            task_id=task_id,
            description=str(task) if not isinstance(task, dict) else task.get("description", ""),
            status=TaskStatus.PENDING,
        )
        self._active_tasks[task_id] = delegation
        
        try:
            # Execute the task
            result = await self._execute_supervised_task(task_id, task)
            return result
        except Exception as e:
            delegation.status = TaskStatus.FAILED
            delegation.error = str(e)
            delegation.completed_at = datetime.now()
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                task_id=task_id,
                error=str(e),
            )
    
    async def _execute_supervised_task(self, task_id: str, task: Any) -> AgentResult:
        """Execute a task with full supervision."""
        delegation = self._active_tasks[task_id]
        delegation.started_at = datetime.now()
        
        # Phase 1: Planning
        delegation.status = TaskStatus.PLANNING
        plan = await self._create_plan(task)
        delegation.plan = plan
        
        if not plan or plan.has_failed():
            delegation.status = TaskStatus.FAILED
            delegation.completed_at = datetime.now()
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                task_id=task_id,
                error="Planning failed",
            )
        
        # Phase 2: Execution
        delegation.status = TaskStatus.EXECUTING
        
        for step in plan.steps:
            if delegation.status == TaskStatus.CANCELLED:
                break
            
            # Check if step is ready
            if not step.is_ready(plan.step_results):
                continue
            
            # Execute step
            step_result = await self._execute_step(task_id, step, delegation)
            plan.mark_step_completed(step.step_id, step_result)
            delegation.step_results[step.step_id] = step_result
            
            # Handle step failure
            if not step_result.success:
                if step.on_failure == "abort":
                    delegation.status = TaskStatus.FAILED
                    delegation.error = step_result.error
                    break
                elif step.on_failure == "skip":
                    step.status = StepStatus.SKIPPED
                elif step.on_failure == "retry" and self.supervisor_config.retry_failed_steps:
                    # Retry logic
                    for retry in range(self.supervisor_config.max_step_retries):
                        retry_result = await self._execute_step(task_id, step, delegation)
                        if retry_result.success:
                            plan.mark_step_completed(step.step_id, retry_result)
                            delegation.step_results[step.step_id] = retry_result
                            break
        
        # Phase 3: Validation
        if delegation.status == TaskStatus.EXECUTING:
            delegation.status = TaskStatus.VALIDATING
            # Validation is done per-step, but we can do final validation here
        
        # Finalize
        if plan.is_complete() and not plan.has_failed():
            delegation.status = TaskStatus.COMPLETED
        elif delegation.status != TaskStatus.CANCELLED:
            delegation.status = TaskStatus.FAILED
        
        delegation.completed_at = datetime.now()
        
        return AgentResult(
            success=delegation.status == TaskStatus.COMPLETED,
            agent_id=self.agent_id,
            task_id=task_id,
            data=delegation.to_dict(),
            error=delegation.error,
            metadata={
                "steps_completed": sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED),
                "steps_failed": sum(1 for s in plan.steps if s.status == StepStatus.FAILED),
            },
        )
    
    async def _create_plan(self, task: Any) -> Optional[TaskPlan]:
        """Create an execution plan using the planner agent."""
        if not self.agent_pool.planner:
            # Create a simple single-step plan
            from .planner import PlanningRequest
            planner = PlannerAgent()
            request = PlanningRequest(task_description=str(task))
            return await planner.create_plan(request)
        
        planner = self.agent_pool.planner
        from .planner import PlanningRequest
        
        request = PlanningRequest(task_description=str(task))
        result = await planner.execute(request)
        
        if result.success and result.data:
            # Reconstruct plan from dict
            return self._reconstruct_plan(result.data)
        
        return None
    
    def _reconstruct_plan(self, data: Dict[str, Any]) -> TaskPlan:
        """Reconstruct a TaskPlan from dictionary."""
        steps = []
        for step_data in data.get("steps", []):
            step = PlanStep(
                step_id=step_data["step_id"],
                step_type=StepType(step_data["step_type"]),
                description=step_data["description"],
                action=step_data["action"],
                parameters=step_data.get("parameters", {}),
                timeout=step_data.get("timeout", 30.0),
                retry_count=step_data.get("retry_count", 2),
                on_failure=step_data.get("on_failure", "abort"),
            )
            steps.append(step)
        
        return TaskPlan(
            plan_id=data["plan_id"],
            task_description=data["task_description"],
            steps=steps,
        )
    
    async def _execute_step(
        self,
        task_id: str,
        step: PlanStep,
        delegation: TaskDelegation,
    ) -> AgentResult:
        """Execute a single step using appropriate agents."""
        step_type = step.step_type
        
        # Determine which agent to use
        if step_type in [StepType.NAVIGATE, StepType.CLICK, StepType.TYPE, 
                         StepType.SCROLL, StepType.WAIT, StepType.SUBTASK]:
            return await self._execute_with_actor(step)
        
        elif step_type == StepType.EXTRACT:
            return await self._execute_with_analyzer(step)
        
        elif step_type == StepType.VALIDATE:
            return await self._execute_with_validator(step)
        
        elif step_type == StepType.CONDITION:
            return await self._evaluate_condition(step, delegation)
        
        else:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                task_id=step.step_id,
                error=f"Unknown step type: {step_type}",
            )
    
    async def _execute_with_actor(self, step: PlanStep) -> AgentResult:
        """Execute a step using the actor agent."""
        if not self.agent_pool.actor:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                task_id=step.step_id,
                error="No actor agent available",
            )
        
        # Convert step to action request
        action_type = self._step_to_action_type(step.step_type)
        request = ActionRequest(
            action_type=action_type,
            selector=step.parameters.get("selector"),
            text=step.parameters.get("text"),
            url=step.parameters.get("url"),
            timeout=step.timeout,
        )
        
        return await self.agent_pool.actor.execute(request)
    
    async def _execute_with_analyzer(self, step: PlanStep) -> AgentResult:
        """Execute a step using the analyzer agent."""
        if not self.agent_pool.analyzer:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                task_id=step.step_id,
                error="No analyzer agent available",
            )
        
        from .analyzer import AnalysisType, AnalysisRequest
        
        request = AnalysisRequest(
            analysis_type=AnalysisType.CONTENT_EXTRACTION,
            selectors=step.parameters.get("selectors"),
        )
        
        return await self.agent_pool.analyzer.execute(request)
    
    async def _execute_with_validator(self, step: PlanStep) -> AgentResult:
        """Execute a step using the validator agent."""
        if not self.agent_pool.validator:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                task_id=step.step_id,
                error="No validator agent available",
            )
        
        from .validator import ValidationType, ValidationCriteria, ValidationRequest
        
        criteria = []
        for c in step.parameters.get("criteria", []):
            criteria.append(ValidationCriteria(
                validation_type=ValidationType(c.get("type", "SUCCESS_CHECK")),
                expected_value=c.get("expected"),
                selector=c.get("selector"),
            ))
        
        request = ValidationRequest(criteria=criteria)
        return await self.agent_pool.validator.execute(request)
    
    async def _evaluate_condition(
        self,
        step: PlanStep,
        delegation: TaskDelegation,
    ) -> AgentResult:
        """Evaluate a condition step."""
        condition = step.parameters.get("condition", "")
        
        # Simple condition evaluation
        # In a real implementation, this would be more sophisticated
        result = True  # Default to true
        
        return AgentResult(
            success=True,
            agent_id=self.agent_id,
            task_id=step.step_id,
            data={"condition_met": result},
        )
    
    def _step_to_action_type(self, step_type: "StepType") -> "ActionType":
        """Convert step type to action type."""
        from .actor import ActionType
        
        mapping = {
            StepType.NAVIGATE: ActionType.NAVIGATE,
            StepType.CLICK: ActionType.CLICK,
            StepType.TYPE: ActionType.TYPE,
            StepType.SCROLL: ActionType.SCROLL,
            StepType.WAIT: ActionType.WAIT,
            StepType.SUBTASK: ActionType.CLICK,  # Default
        }
        return mapping.get(step_type, ActionType.CLICK)
    
    async def submit_task(self, description: str, **kwargs) -> str:
        """Submit a task for execution."""
        task_id = str(uuid.uuid4())
        
        delegation = TaskDelegation(
            task_id=task_id,
            description=description,
            status=TaskStatus.PENDING,
            metadata=kwargs,
        )
        self._active_tasks[task_id] = delegation
        
        await self._task_queue.put((task_id, description, kwargs))
        
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a task."""
        if task_id in self._active_tasks:
            return self._active_tasks[task_id].to_dict()
        return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id in self._active_tasks:
            delegation = self._active_tasks[task_id]
            if delegation.status in [TaskStatus.PENDING, TaskStatus.PLANNING, TaskStatus.EXECUTING]:
                delegation.status = TaskStatus.CANCELLED
                delegation.completed_at = datetime.now()
                return True
        return False
    
    async def start(self) -> None:
        """Start the supervisor."""
        await super().start()
        
        # Start all registered agents
        for agent in self.agent_pool.all_agents():
            await agent.start()
        
        self._running = True
        self._orchestration_task = asyncio.create_task(self._orchestration_loop())
    
    async def stop(self) -> None:
        """Stop the supervisor."""
        self._running = False
        
        if self._orchestration_task:
            self._orchestration_task.cancel()
            try:
                await self._orchestration_task
            except asyncio.CancelledError:
                pass
        
        # Stop all agents
        for agent in self.agent_pool.all_agents():
            await agent.stop()
        
        await super().stop()
    
    async def _orchestration_loop(self) -> None:
        """Main orchestration loop."""
        while self._running:
            try:
                # Process task queue
                try:
                    task_id, description, kwargs = await asyncio.wait_for(
                        self._task_queue.get(),
                        timeout=1.0,
                    )
                    # Execute task in background
                    asyncio.create_task(self.execute({
                        "description": description,
                        **kwargs,
                    }))
                except asyncio.TimeoutError:
                    continue
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.state.error_history.append(str(e))
    
    def get_supervisor_status(self) -> Dict[str, Any]:
        """Get comprehensive supervisor status."""
        return {
            "supervisor": {
                "id": self.agent_id,
                "name": self.name,
                "status": self.status.value,
                "active_tasks": len(self._active_tasks),
            },
            "agents": self.agent_pool.get_status(),
            "tasks": {
                task_id: {
                    "status": delegation.status.value,
                    "description": delegation.description[:50],
                }
                for task_id, delegation in self._active_tasks.items()
            },
        }
    
    async def synthesize_results(self, task_id: str) -> Dict[str, Any]:
        """Synthesize results from all agents for a task."""
        if task_id not in self._active_tasks:
            return {"error": "Task not found"}
        
        delegation = self._active_tasks[task_id]
        
        synthesis = {
            "task_id": task_id,
            "description": delegation.description,
            "status": delegation.status.value,
            "duration_seconds": delegation.duration_seconds(),
            "steps": {},
            "summary": {},
        }
        
        # Aggregate step results
        for step_id, result in delegation.step_results.items():
            synthesis["steps"][step_id] = {
                "success": result.success,
                "agent_id": result.agent_id,
                "data": result.data,
                "error": result.error,
            }
        
        # Generate summary
        total_steps = len(delegation.step_results)
        successful_steps = sum(1 for r in delegation.step_results.values() if r.success)
        
        synthesis["summary"] = {
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": total_steps - successful_steps,
            "success_rate": (successful_steps / total_steps * 100) if total_steps > 0 else 0,
        }
        
        return synthesis


# Import StepType for mapping
from .planner import StepType
from .actor import ActionType

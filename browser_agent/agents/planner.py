"""
Planner Agent Module

The Planner Agent is responsible for:
- Decomposing complex tasks into executable steps
- Managing step dependencies
- Creating execution plans
- Adapting plans based on feedback
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import uuid

from .base import (
    BaseAgent,
    AgentConfig,
    AgentCapability,
    AgentResult,
    AgentStatus,
)


class StepStatus(Enum):
    """Status of a plan step."""
    PENDING = "pending"
    READY = "ready"  # Dependencies satisfied
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepType(Enum):
    """Types of plan steps."""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    EXTRACT = "extract"
    WAIT = "wait"
    SCROLL = "scroll"
    VALIDATE = "validate"
    CONDITION = "condition"
    LOOP = "loop"
    SUBTASK = "subtask"


@dataclass
class StepDependency:
    """Dependency between steps."""
    step_id: str
    condition: Optional[str] = None  # e.g., "success", "result.contains('x')"
    
    def is_satisfied(self, step_results: Dict[str, AgentResult]) -> bool:
        """Check if the dependency is satisfied."""
        if self.step_id not in step_results:
            return False
        
        result = step_results[self.step_id]
        
        if not self.condition:
            return result.success
        
        # Simple condition evaluation
        if self.condition == "success":
            return result.success
        elif self.condition == "failure":
            return not result.success
        elif self.condition.startswith("result.contains"):
            # Extract the value to check
            try:
                check_value = self.condition.split("'")[1]
                return result.data and check_value in str(result.data)
            except (IndexError, TypeError):
                return False
        
        return result.success


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    step_id: str
    step_type: StepType
    description: str
    action: str  # Action to perform
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[StepDependency] = field(default_factory=list)
    expected_outcome: Optional[str] = None
    timeout: float = 30.0
    retry_count: int = 2
    on_failure: str = "abort"  # abort, skip, retry, continue
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    
    def is_ready(self, step_results: Dict[str, AgentResult]) -> bool:
        """Check if all dependencies are satisfied."""
        if not self.dependencies:
            return True
        return all(dep.is_satisfied(step_results) for dep in self.dependencies)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "description": self.description,
            "action": self.action,
            "parameters": self.parameters,
            "dependencies": [
                {"step_id": d.step_id, "condition": d.condition}
                for d in self.dependencies
            ],
            "expected_outcome": self.expected_outcome,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "on_failure": self.on_failure,
            "metadata": self.metadata,
            "status": self.status.value,
        }


@dataclass
class TaskPlan:
    """A complete execution plan for a task."""
    plan_id: str
    task_description: str
    steps: List[PlanStep]
    created_at: datetime = field(default_factory=datetime.now)
    current_step_index: int = 0
    status: str = "created"  # created, running, completed, failed, paused
    step_results: Dict[str, AgentResult] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_ready_steps(self) -> List[PlanStep]:
        """Get all steps that are ready to execute."""
        return [
            step for step in self.steps
            if step.status == StepStatus.PENDING and step.is_ready(self.step_results)
        ]
    
    def get_next_step(self) -> Optional[PlanStep]:
        """Get the next step to execute."""
        ready_steps = self.get_ready_steps()
        if ready_steps:
            return ready_steps[0]
        return None
    
    def mark_step_running(self, step_id: str) -> None:
        """Mark a step as running."""
        for step in self.steps:
            if step.step_id == step_id:
                step.status = StepStatus.RUNNING
                break
    
    def mark_step_completed(self, step_id: str, result: AgentResult) -> None:
        """Mark a step as completed with result."""
        for step in self.steps:
            if step.step_id == step_id:
                step.status = StepStatus.COMPLETED if result.success else StepStatus.FAILED
                break
        self.step_results[step_id] = result
    
    def is_complete(self) -> bool:
        """Check if all steps are completed or skipped."""
        return all(
            step.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
            for step in self.steps
        )
    
    def has_failed(self) -> bool:
        """Check if any critical step has failed."""
        return any(
            step.status == StepStatus.FAILED and step.on_failure == "abort"
            for step in self.steps
        )
    
    def get_progress(self) -> Dict[str, Any]:
        """Get plan progress information."""
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in self.steps if s.status == StepStatus.FAILED)
        pending = sum(1 for s in self.steps if s.status == StepStatus.PENDING)
        running = sum(1 for s in self.steps if s.status == StepStatus.RUNNING)
        
        return {
            "plan_id": self.plan_id,
            "total_steps": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "running": running,
            "progress_percent": (completed / total * 100) if total > 0 else 0,
            "status": self.status,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "task_description": self.task_description,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "current_step_index": self.current_step_index,
            "status": self.status,
            "step_results": {k: v.to_dict() for k, v in self.step_results.items()},
            "metadata": self.metadata,
            "progress": self.get_progress(),
        }


@dataclass
class PlanningRequest:
    """Request for the planner agent."""
    task_description: str
    context: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    max_steps: int = 20
    timeout_per_step: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class PlannerAgent(BaseAgent):
    """
    Agent responsible for planning and task decomposition.
    
    Capabilities:
    - Decompose complex tasks into steps
    - Identify step dependencies
    - Create execution plans
    - Adapt plans based on results
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="PlannerAgent",
                capabilities={
                    AgentCapability.PLANNING,
                    AgentCapability.COORDINATION,
                },
            )
        super().__init__(config)
        self._plan_templates: Dict[str, TaskPlan] = {}
    
    async def execute(self, task: Any) -> AgentResult:
        """Execute a planning task."""
        if isinstance(task, PlanningRequest):
            plan = await self.create_plan(task)
            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                task_id=task.task_description[:50],  # Use first 50 chars as ID
                data=plan.to_dict(),
                metadata={"plan_id": plan.plan_id},
            )
        elif isinstance(task, str):
            # Simple string task description
            request = PlanningRequest(task_description=task)
            plan = await self.create_plan(request)
            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                task_id=task[:50],
                data=plan.to_dict(),
                metadata={"plan_id": plan.plan_id},
            )
        else:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                task_id="unknown",
                error=f"Unknown task type: {type(task)}",
            )
    
    async def create_plan(self, request: PlanningRequest) -> TaskPlan:
        """
        Create an execution plan from a task description.
        
        This method analyzes the task and creates a structured plan
        with steps and dependencies.
        """
        plan_id = str(uuid.uuid4())
        
        # Parse the task description and create steps
        steps = await self._decompose_task(
            request.task_description,
            request.context,
            request.constraints,
            request.max_steps,
            request.timeout_per_step,
        )
        
        plan = TaskPlan(
            plan_id=plan_id,
            task_description=request.task_description,
            steps=steps,
            metadata={
                "constraints": request.constraints,
                "max_steps": request.max_steps,
                "timeout_per_step": request.timeout_per_step,
                **request.metadata,
            },
        )
        
        return plan
    
    async def _decompose_task(
        self,
        description: str,
        context: Dict[str, Any],
        constraints: Dict[str, Any],
        max_steps: int,
        timeout: float,
    ) -> List[PlanStep]:
        """
        Decompose a task into steps.
        
        This is a rule-based decomposition that can be enhanced with
        LLM-based planning in the future.
        """
        steps = []
        description_lower = description.lower()
        
        # Detect task patterns and create appropriate steps
        
        # Pattern 1: Form filling
        if any(kw in description_lower for kw in ["fill", "form", "submit", "register", "sign up"]):
            steps.extend(self._create_form_filling_steps(description, timeout))
        
        # Pattern 2: Search and extract
        elif any(kw in description_lower for kw in ["search", "find", "look for"]):
            steps.extend(self._create_search_steps(description, timeout))
            
            # Check if extraction is also needed
            if any(kw in description_lower for kw in ["extract", "get", "collect", "scrape"]):
                steps.extend(self._create_extraction_steps(description, timeout))
        
        # Pattern 3: Navigation
        elif any(kw in description_lower for kw in ["go to", "navigate", "open", "visit"]):
            steps.extend(self._create_navigation_steps(description, timeout))
        
        # Pattern 4: Data extraction
        elif any(kw in description_lower for kw in ["extract", "scrape", "collect", "gather"]):
            steps.extend(self._create_extraction_steps(description, timeout))
        
        # Pattern 5: Click/interact
        elif any(kw in description_lower for kw in ["click", "press", "select", "choose"]):
            steps.extend(self._create_interaction_steps(description, timeout))
        
        # Default: Create a generic step
        if not steps:
            steps.append(PlanStep(
                step_id="step_1",
                step_type=StepType.SUBTASK,
                description=description,
                action="execute_task",
                parameters={"task": description},
                timeout=timeout,
            ))
        
        # Limit steps
        return steps[:max_steps]
    
    def _create_form_filling_steps(self, description: str, timeout: float) -> List[PlanStep]:
        """Create steps for form filling tasks."""
        return [
            PlanStep(
                step_id="navigate_to_form",
                step_type=StepType.NAVIGATE,
                description="Navigate to the form page",
                action="navigate",
                parameters={},
                timeout=timeout,
            ),
            PlanStep(
                step_id="wait_for_form",
                step_type=StepType.WAIT,
                description="Wait for form to load",
                action="wait_for_element",
                parameters={"selector": "form"},
                dependencies=[StepDependency("navigate_to_form")],
                timeout=timeout,
            ),
            PlanStep(
                step_id="fill_form",
                step_type=StepType.TYPE,
                description="Fill in form fields",
                action="fill_form",
                parameters={},
                dependencies=[StepDependency("wait_for_form")],
                timeout=timeout,
            ),
            PlanStep(
                step_id="submit_form",
                step_type=StepType.CLICK,
                description="Submit the form",
                action="click",
                parameters={"selector": "button[type='submit']"},
                dependencies=[StepDependency("fill_form")],
                timeout=timeout,
            ),
            PlanStep(
                step_id="validate_submission",
                step_type=StepType.VALIDATE,
                description="Validate form submission",
                action="validate",
                parameters={},
                dependencies=[StepDependency("submit_form")],
                timeout=timeout,
            ),
        ]
    
    def _create_search_steps(self, description: str, timeout: float) -> List[PlanStep]:
        """Create steps for search tasks."""
        return [
            PlanStep(
                step_id="navigate_to_search",
                step_type=StepType.NAVIGATE,
                description="Navigate to search page",
                action="navigate",
                parameters={},
                timeout=timeout,
            ),
            PlanStep(
                step_id="enter_query",
                step_type=StepType.TYPE,
                description="Enter search query",
                action="type",
                parameters={},
                dependencies=[StepDependency("navigate_to_search")],
                timeout=timeout,
            ),
            PlanStep(
                step_id="submit_search",
                step_type=StepType.CLICK,
                description="Submit search",
                action="click",
                parameters={"selector": "button[type='submit'], input[type='submit']"},
                dependencies=[StepDependency("enter_query")],
                timeout=timeout,
            ),
            PlanStep(
                step_id="wait_for_results",
                step_type=StepType.WAIT,
                description="Wait for search results",
                action="wait_for_element",
                parameters={"selector": ".results, #results, .search-results"},
                dependencies=[StepDependency("submit_search")],
                timeout=timeout,
            ),
        ]
    
    def _create_navigation_steps(self, description: str, timeout: float) -> List[PlanStep]:
        """Create steps for navigation tasks."""
        return [
            PlanStep(
                step_id="navigate",
                step_type=StepType.NAVIGATE,
                description="Navigate to target page",
                action="navigate",
                parameters={},
                timeout=timeout,
            ),
            PlanStep(
                step_id="wait_for_page",
                step_type=StepType.WAIT,
                description="Wait for page to load",
                action="wait_for_load",
                parameters={},
                dependencies=[StepDependency("navigate")],
                timeout=timeout,
            ),
        ]
    
    def _create_extraction_steps(self, description: str, timeout: float) -> List[PlanStep]:
        """Create steps for data extraction tasks."""
        return [
            PlanStep(
                step_id="scroll_page",
                step_type=StepType.SCROLL,
                description="Scroll to load all content",
                action="scroll",
                parameters={"direction": "down", "amount": "full"},
                timeout=timeout,
            ),
            PlanStep(
                step_id="extract_data",
                step_type=StepType.EXTRACT,
                description="Extract data from page",
                action="extract",
                parameters={},
                dependencies=[StepDependency("scroll_page")],
                timeout=timeout,
            ),
        ]
    
    def _create_interaction_steps(self, description: str, timeout: float) -> List[PlanStep]:
        """Create steps for interaction tasks."""
        return [
            PlanStep(
                step_id="wait_for_element",
                step_type=StepType.WAIT,
                description="Wait for target element",
                action="wait_for_element",
                parameters={},
                timeout=timeout,
            ),
            PlanStep(
                step_id="interact",
                step_type=StepType.CLICK,
                description="Perform interaction",
                action="click",
                parameters={},
                dependencies=[StepDependency("wait_for_element")],
                timeout=timeout,
            ),
        ]
    
    async def adapt_plan(
        self,
        plan: TaskPlan,
        failed_step_id: str,
        failure_reason: str,
    ) -> TaskPlan:
        """
        Adapt a plan after a step failure.
        
        This can modify remaining steps, add recovery steps,
        or mark steps as skipped.
        """
        failed_step = next(
            (s for s in plan.steps if s.step_id == failed_step_id),
            None
        )
        
        if not failed_step:
            return plan
        
        # Handle based on failure strategy
        if failed_step.on_failure == "abort":
            # Mark all pending steps as skipped
            for step in plan.steps:
                if step.status == StepStatus.PENDING:
                    step.status = StepStatus.SKIPPED
            plan.status = "failed"
            
        elif failed_step.on_failure == "skip":
            # Skip just this step and continue
            failed_step.status = StepStatus.SKIPPED
            
        elif failed_step.on_failure == "retry":
            # Reset the step for retry
            failed_step.status = StepStatus.PENDING
            
        elif failed_step.on_failure == "continue":
            # Mark as failed but continue
            pass
        
        return plan
    
    def register_plan_template(self, name: str, plan: TaskPlan) -> None:
        """Register a plan template for reuse."""
        self._plan_templates[name] = plan
    
    def get_plan_template(self, name: str) -> Optional[TaskPlan]:
        """Get a registered plan template."""
        return self._plan_templates.get(name)

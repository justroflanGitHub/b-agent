"""
Workflow Automation Skill Module

Provides workflow automation capabilities with chained operations,
conditional logic, branching workflows, and error handling.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Union
from datetime import datetime
import asyncio
import logging
import copy

from .base import BaseSkill, SkillResult, SkillInput, SkillCapability

logger = logging.getLogger(__name__)


class StepType(Enum):
    """Types of workflow steps."""
    ACTION = "action"
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"
    WAIT = "wait"
    SKILL = "skill"
    SUBWORKFLOW = "subworkflow"


class ConditionOperator(Enum):
    """Operators for conditions."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    MATCHES = "matches"  # Regex match


class LoopType(Enum):
    """Types of loops."""
    COUNT = "count"  # Fixed number of iterations
    WHILE = "while"  # While condition is true
    FOR_EACH = "for_each"  # Iterate over list


@dataclass
class Condition:
    """
    Condition for branching logic.
    
    Defines a condition to evaluate.
    """
    # Variable to check
    variable: str
    
    # Operator
    operator: ConditionOperator = ConditionOperator.EQUALS
    
    # Value to compare against
    value: Any = None
    
    # Whether to negate the result
    negate: bool = False
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate the condition against context."""
        actual_value = self._get_nested_value(context, self.variable)
        
        if self.operator == ConditionOperator.EQUALS:
            result = actual_value == self.value
        elif self.operator == ConditionOperator.NOT_EQUALS:
            result = actual_value != self.value
        elif self.operator == ConditionOperator.CONTAINS:
            result = self.value in str(actual_value) if actual_value else False
        elif self.operator == ConditionOperator.NOT_CONTAINS:
            result = self.value not in str(actual_value) if actual_value else True
        elif self.operator == ConditionOperator.GREATER_THAN:
            result = actual_value > self.value if actual_value is not None else False
        elif self.operator == ConditionOperator.LESS_THAN:
            result = actual_value < self.value if actual_value is not None else False
        elif self.operator == ConditionOperator.IS_EMPTY:
            result = not actual_value
        elif self.operator == ConditionOperator.IS_NOT_EMPTY:
            result = bool(actual_value)
        elif self.operator == ConditionOperator.MATCHES:
            import re
            result = bool(re.search(self.value, str(actual_value))) if actual_value else False
        else:
            result = False
        
        return not result if self.negate else result
    
    def _get_nested_value(self, context: Dict[str, Any], path: str) -> Any:
        """Get nested value from context using dot notation."""
        keys = path.split('.')
        value = context
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value


@dataclass
class WorkflowStep:
    """
    Definition of a workflow step.
    
    Describes a single step in a workflow.
    """
    # Step identifier
    id: str
    
    # Step type
    step_type: StepType = StepType.ACTION
    
    # Step name/description
    name: Optional[str] = None
    
    # Action to perform (for ACTION type)
    action: Optional[str] = None
    
    # Action parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Condition for branching (for CONDITION type)
    condition: Optional[Condition] = None
    
    # Steps for true branch
    true_steps: List['WorkflowStep'] = field(default_factory=list)
    
    # Steps for false branch
    false_steps: List['WorkflowStep'] = field(default_factory=list)
    
    # Loop configuration (for LOOP type)
    loop_type: Optional[LoopType] = None
    loop_count: int = 1
    loop_condition: Optional[Condition] = None
    loop_variable: Optional[str] = None  # For for_each loops
    loop_steps: List['WorkflowStep'] = field(default_factory=list)
    
    # Parallel steps (for PARALLEL type)
    parallel_steps: List['WorkflowStep'] = field(default_factory=list)
    
    # Wait duration (for WAIT type)
    wait_seconds: float = 1.0
    
    # Skill name (for SKILL type)
    skill_name: Optional[str] = None
    skill_input: Dict[str, Any] = field(default_factory=dict)
    
    # Subworkflow (for SUBWORKFLOW type)
    subworkflow: Optional['Workflow'] = None
    
    # Error handling
    on_error: str = "fail"  # "fail", "skip", "retry"
    max_retries: int = 0
    retry_delay: float = 1.0
    
    # Whether to continue on error
    continue_on_error: bool = False
    
    # Timeout (seconds)
    timeout: float = 60.0
    
    # Output variable name
    output_variable: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "step_type": self.step_type.value,
            "name": self.name,
            "action": self.action,
            "parameters": self.parameters,
            "on_error": self.on_error,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "output_variable": self.output_variable,
            "metadata": self.metadata,
        }


@dataclass
class Workflow:
    """
    Definition of a workflow.
    
    A workflow is a sequence of steps with branching and looping support.
    """
    # Workflow name
    name: str
    
    # Workflow steps
    steps: List[WorkflowStep] = field(default_factory=list)
    
    # Input variables
    input_variables: List[str] = field(default_factory=list)
    
    # Output variables
    output_variables: List[str] = field(default_factory=list)
    
    # Default error handling
    default_on_error: str = "fail"
    
    # Maximum total execution time (seconds)
    max_execution_time: float = 3600.0
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """Get a step by ID."""
        return self._find_step(self.steps, step_id)
    
    def _find_step(
        self,
        steps: List[WorkflowStep],
        step_id: str,
    ) -> Optional[WorkflowStep]:
        """Recursively find a step by ID."""
        for step in steps:
            if step.id == step_id:
                return step
            
            # Search in nested steps
            result = self._find_step(step.true_steps, step_id)
            if result:
                return result
            
            result = self._find_step(step.false_steps, step_id)
            if result:
                return result
            
            result = self._find_step(step.loop_steps, step_id)
            if result:
                return result
            
            result = self._find_step(step.parallel_steps, step_id)
            if result:
                return result
        
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "steps": [s.to_dict() for s in self.steps],
            "input_variables": self.input_variables,
            "output_variables": self.output_variables,
            "default_on_error": self.default_on_error,
            "max_execution_time": self.max_execution_time,
            "metadata": self.metadata,
        }


@dataclass
class WorkflowContext:
    """
    Execution context for a workflow.
    
    Maintains state during workflow execution.
    """
    # Variable storage
    variables: Dict[str, Any] = field(default_factory=dict)
    
    # Step execution history
    history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Current step index
    current_step: int = 0
    
    # Execution start time
    start_time: datetime = field(default_factory=datetime.now)
    
    # Errors encountered
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    # Warnings
    warnings: List[str] = field(default_factory=list)
    
    # Whether workflow is paused
    paused: bool = False
    
    # Checkpoint data for resume
    checkpoint: Optional[Dict[str, Any]] = None
    
    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable."""
        self.variables[name] = value
    
    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a variable."""
        return self.variables.get(name, default)
    
    def add_history(self, step_id: str, result: Any, success: bool) -> None:
        """Add step to history."""
        self.history.append({
            "step_id": step_id,
            "result": result,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        })
    
    def add_error(self, step_id: str, error: str) -> None:
        """Add an error."""
        self.errors.append({
            "step_id": step_id,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "variables": self.variables,
            "history": self.history,
            "current_step": self.current_step,
            "start_time": self.start_time.isoformat(),
            "errors": self.errors,
            "warnings": self.warnings,
            "paused": self.paused,
        }


@dataclass
class WorkflowInput(SkillInput):
    """
    Input for workflow skill.
    """
    # Workflow definition
    workflow: Optional[Workflow] = None
    
    # Initial variables
    variables: Dict[str, Any] = field(default_factory=dict)
    
    # Whether to resume from checkpoint
    resume: bool = False
    
    # Checkpoint data for resume
    checkpoint_data: Optional[Dict[str, Any]] = None
    
    # Whether to save checkpoints
    save_checkpoints: bool = True
    
    # Checkpoint interval (steps)
    checkpoint_interval: int = 5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        d = super().to_dict()
        d.update({
            "workflow": self.workflow.to_dict() if self.workflow else None,
            "variables": self.variables,
            "resume": self.resume,
            "checkpoint_data": self.checkpoint_data,
            "save_checkpoints": self.save_checkpoints,
            "checkpoint_interval": self.checkpoint_interval,
        })
        return d


class WorkflowSkill(BaseSkill[WorkflowInput]):
    """
    Skill for workflow automation.
    
    Capabilities:
    - Chained operations
    - Conditional logic
    - Branching workflows
    - Loop/repeat operations
    - Error handling
    """
    
    name = "workflow"
    description = "Execute automated workflows with branching, loops, and error handling"
    version = "1.0.0"
    
    required_capabilities: Set[SkillCapability] = {
        SkillCapability.BROWSER_INTERACTION,
        SkillCapability.ERROR_RECOVERY,
    }
    
    provided_capabilities: Set[SkillCapability] = {
        SkillCapability.ERROR_RECOVERY,
        SkillCapability.STATE_CHECKPOINT,
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._context: Optional[WorkflowContext] = None
        self._skill_registry: Optional[Any] = None
    
    def set_skill_registry(self, registry: Any) -> None:
        """Set the skill registry for skill steps."""
        self._skill_registry = registry
    
    async def execute(self, input_data: WorkflowInput) -> SkillResult:
        """
        Execute workflow.
        
        Args:
            input_data: Workflow input with workflow definition
            
        Returns:
            SkillResult with workflow execution results
        """
        result = SkillResult(success=False)
        
        try:
            workflow = input_data.workflow
            if workflow is None:
                self._set_error(result, "No workflow provided", "WORKFLOW_ERROR")
                return result
            
            result.metadata["workflow_name"] = workflow.name
            
            # Initialize context
            if input_data.resume and input_data.checkpoint_data:
                self._context = self._restore_context(input_data.checkpoint_data)
            else:
                self._context = WorkflowContext(
                    variables=copy.deepcopy(input_data.variables)
                )
            
            self._logger.info(f"Starting workflow: {workflow.name}")
            
            # Execute steps
            await self._execute_steps(workflow.steps, input_data, result)
            
            # Set result
            result.success = len(self._context.errors) == 0
            result.data = {
                "variables": self._context.variables,
                "history": self._context.history,
                "errors": self._context.errors,
                "warnings": self._context.warnings,
                "execution_time": (datetime.now() - self._context.start_time).total_seconds(),
            }
            result.metadata["steps_executed"] = len(self._context.history)
            result.metadata["errors_count"] = len(self._context.errors)
            
            self._add_step(result, f"Workflow completed: {workflow.name}")
            
        except Exception as e:
            self._set_error(result, f"Workflow error: {e}", "WORKFLOW_ERROR")
            self._logger.exception("Workflow execution failed")
        
        return result
    
    def validate_input(self, input_data: WorkflowInput) -> bool:
        """
        Validate workflow input.
        
        Args:
            input_data: Input to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not input_data.workflow:
            self._logger.warning("No workflow provided")
            return False
        
        if not input_data.workflow.steps:
            self._logger.warning("Workflow has no steps")
            return False
        
        return True
    
    def verify_results(self, result: SkillResult) -> bool:
        """
        Verify workflow results.
        
        Args:
            result: Result to verify
            
        Returns:
            True if valid, False otherwise
        """
        if not result.success:
            return False
        
        if not result.data:
            return False
        
        return True
    
    async def _execute_steps(
        self,
        steps: List[WorkflowStep],
        input_data: WorkflowInput,
        result: SkillResult,
    ) -> None:
        """Execute a list of steps."""
        for step in steps:
            if self._context.paused:
                break
            
            await self._execute_step(step, input_data, result)
    
    async def _execute_step(
        self,
        step: WorkflowStep,
        input_data: WorkflowInput,
        result: SkillResult,
    ) -> Any:
        """Execute a single step."""
        self._logger.info(f"Executing step: {step.id} ({step.step_type.value})")
        
        step_result = None
        retries = 0
        max_retries = step.max_retries if step.on_error == "retry" else 0
        
        while retries <= max_retries:
            try:
                if step.step_type == StepType.ACTION:
                    step_result = await self._execute_action(step, result)
                
                elif step.step_type == StepType.CONDITION:
                    step_result = await self._execute_condition(step, input_data, result)
                
                elif step.step_type == StepType.LOOP:
                    step_result = await self._execute_loop(step, input_data, result)
                
                elif step.step_type == StepType.PARALLEL:
                    step_result = await self._execute_parallel(step, input_data, result)
                
                elif step.step_type == StepType.WAIT:
                    step_result = await self._execute_wait(step, result)
                
                elif step.step_type == StepType.SKILL:
                    step_result = await self._execute_skill(step, result)
                
                elif step.step_type == StepType.SUBWORKFLOW:
                    step_result = await self._execute_subworkflow(step, input_data, result)
                
                # Success - record and continue
                self._context.add_history(step.id, step_result, True)
                
                # Store output variable
                if step.output_variable and step_result is not None:
                    self._context.set_variable(step.output_variable, step_result)
                
                break
                
            except Exception as e:
                retries += 1
                error_msg = f"Step {step.id} failed: {e}"
                self._logger.error(error_msg)
                
                if retries <= max_retries:
                    self._logger.info(f"Retrying step {step.id} ({retries}/{max_retries})")
                    await asyncio.sleep(step.retry_delay)
                else:
                    self._context.add_error(step.id, str(e))
                    self._context.add_history(step.id, None, False)
                    
                    if step.continue_on_error or step.on_error == "skip":
                        self._add_warning(result, error_msg)
                    else:
                        raise
        
        return step_result
    
    async def _execute_action(
        self,
        step: WorkflowStep,
        result: SkillResult,
    ) -> Any:
        """Execute an action step."""
        if self.executor is None:
            raise ValueError("No action executor available")
        
        action = step.action
        params = step.parameters
        
        # Resolve variables in parameters
        resolved_params = self._resolve_variables(params)
        
        self._add_step(result, f"Action: {action}")
        
        # Execute action
        action_result = await self.executor.execute_action(action, **resolved_params)
        
        return action_result.data if hasattr(action_result, 'data') else action_result
    
    async def _execute_condition(
        self,
        step: WorkflowStep,
        input_data: WorkflowInput,
        result: SkillResult,
    ) -> Any:
        """Execute a conditional step."""
        if step.condition is None:
            return None
        
        condition_result = step.condition.evaluate(self._context.variables)
        
        self._add_step(result, f"Condition: {step.id} = {condition_result}")
        
        if condition_result:
            await self._execute_steps(step.true_steps, input_data, result)
        else:
            await self._execute_steps(step.false_steps, input_data, result)
        
        return condition_result
    
    async def _execute_loop(
        self,
        step: WorkflowStep,
        input_data: WorkflowInput,
        result: SkillResult,
    ) -> Any:
        """Execute a loop step."""
        loop_results = []
        
        if step.loop_type == LoopType.COUNT:
            for i in range(step.loop_count):
                self._context.set_variable("loop_index", i)
                await self._execute_steps(step.loop_steps, input_data, result)
                loop_results.append(i)
        
        elif step.loop_type == LoopType.WHILE:
            iteration = 0
            max_iterations = 1000  # Safety limit
            while step.loop_condition.evaluate(self._context.variables):
                if iteration >= max_iterations:
                    self._add_warning(result, f"Loop {step.id} exceeded max iterations")
                    break
                
                self._context.set_variable("loop_index", iteration)
                await self._execute_steps(step.loop_steps, input_data, result)
                iteration += 1
                loop_results.append(iteration)
        
        elif step.loop_type == LoopType.FOR_EACH:
            items = self._context.get_variable(step.loop_variable, [])
            for i, item in enumerate(items):
                self._context.set_variable("loop_item", item)
                self._context.set_variable("loop_index", i)
                await self._execute_steps(step.loop_steps, input_data, result)
                loop_results.append(item)
        
        self._add_step(result, f"Loop: {step.id} ({len(loop_results)} iterations)")
        return loop_results
    
    async def _execute_parallel(
        self,
        step: WorkflowStep,
        input_data: WorkflowInput,
        result: SkillResult,
    ) -> Any:
        """Execute parallel steps."""
        tasks = []
        
        for parallel_step in step.parallel_steps:
            task = self._execute_step(parallel_step, input_data, result)
            tasks.append(task)
        
        parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        self._add_step(result, f"Parallel: {step.id} ({len(tasks)} tasks)")
        return parallel_results
    
    async def _execute_wait(
        self,
        step: WorkflowStep,
        result: SkillResult,
    ) -> Any:
        """Execute a wait step."""
        await asyncio.sleep(step.wait_seconds)
        self._add_step(result, f"Wait: {step.wait_seconds}s")
        return step.wait_seconds
    
    async def _execute_skill(
        self,
        step: WorkflowStep,
        result: SkillResult,
    ) -> Any:
        """Execute a skill step."""
        if self._skill_registry is None:
            raise ValueError("No skill registry available")
        
        skill = self._skill_registry.get_skill(step.skill_name)
        if skill is None:
            raise ValueError(f"Skill not found: {step.skill_name}")
        
        # Resolve variables in skill input
        resolved_input = self._resolve_variables(step.skill_input)
        
        self._add_step(result, f"Skill: {step.skill_name}")
        
        # Create skill input
        skill_input = type('SkillInput', (), resolved_input)()
        skill_result = await skill.execute(skill_input)
        
        return skill_result.data if skill_result.success else None
    
    async def _execute_subworkflow(
        self,
        step: WorkflowStep,
        input_data: WorkflowInput,
        result: SkillResult,
    ) -> Any:
        """Execute a subworkflow step."""
        if step.subworkflow is None:
            return None
        
        self._add_step(result, f"Subworkflow: {step.subworkflow.name}")
        
        # Create nested input
        nested_input = WorkflowInput(
            task=f"Execute subworkflow: {step.subworkflow.name}",
            workflow=step.subworkflow,
            variables=copy.deepcopy(self._context.variables),
            max_retries=1,
        )
        
        # Execute subworkflow
        nested_result = await self.execute(nested_input)
        
        # Merge variables back
        if nested_result.success and nested_result.data:
            for key, value in nested_result.data.get("variables", {}).items():
                self._context.set_variable(key, value)
        
        return nested_result.data
    
    def _resolve_variables(self, data: Any) -> Any:
        """Resolve variable references in data."""
        if isinstance(data, dict):
            return {k: self._resolve_variables(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_variables(item) for item in data]
        elif isinstance(data, str):
            # Check for variable reference ${var}
            if data.startswith("${") and data.endswith("}"):
                var_name = data[2:-1]
                return self._context.get_variable(var_name, data)
            return data
        return data
    
    def _restore_context(self, checkpoint_data: Dict[str, Any]) -> WorkflowContext:
        """Restore context from checkpoint."""
        context = WorkflowContext()
        context.variables = checkpoint_data.get("variables", {})
        context.history = checkpoint_data.get("history", [])
        context.current_step = checkpoint_data.get("current_step", 0)
        context.errors = checkpoint_data.get("errors", [])
        context.warnings = checkpoint_data.get("warnings", [])
        return context
    
    def get_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Get current context as checkpoint."""
        if self._context:
            return self._context.to_dict()
        return None

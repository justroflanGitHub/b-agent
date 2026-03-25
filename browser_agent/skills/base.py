"""
Base Skill Module

Provides the abstract base class and data structures for all skills.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, TypeVar, Generic
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


class SkillCapability(Enum):
    """Capabilities that a skill may require or provide."""
    # Browser capabilities
    BROWSER_NAVIGATION = "browser_navigation"
    BROWSER_INTERACTION = "browser_interaction"
    BROWSER_SCREENSHOT = "browser_screenshot"
    BROWSER_WAIT = "browser_wait"
    
    # Vision capabilities
    VISION_ELEMENT_DETECTION = "vision_element_detection"
    VISION_TEXT_RECOGNITION = "vision_text_recognition"
    VISION_SCREENSHOT_ANALYSIS = "vision_screenshot_analysis"
    
    # Data capabilities
    DATA_EXTRACTION = "data_extraction"
    DATA_VALIDATION = "data_validation"
    DATA_TRANSFORMATION = "data_transformation"
    
    # Recovery capabilities
    ERROR_RECOVERY = "error_recovery"
    STATE_CHECKPOINT = "state_checkpoint"
    ROLLBACK = "rollback"
    
    # Advanced capabilities
    MULTI_PAGE_NAVIGATION = "multi_page_navigation"
    PAGINATION_HANDLING = "pagination_handling"
    FORM_HANDLING = "form_handling"
    DYNAMIC_CONTENT = "dynamic_content"


@dataclass
class SkillInput:
    """
    Base input for skill execution.
    
    Contains common parameters needed by all skills.
    """
    # Task description
    task: str
    
    # Optional context from previous operations
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Timeout for skill execution (seconds)
    timeout: float = 300.0
    
    # Maximum retries on failure
    max_retries: int = 3
    
    # Whether to validate input before execution
    validate_input: bool = True
    
    # Whether to verify results after execution
    verify_results: bool = True
    
    # Custom options for specific skills
    options: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "task": self.task,
            "context": self.context,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "validate_input": self.validate_input,
            "verify_results": self.verify_results,
            "options": self.options,
        }


@dataclass
class SkillResult:
    """
    Result of skill execution.
    
    Contains success status, extracted data, errors, and metadata.
    """
    # Whether the skill executed successfully
    success: bool
    
    # Extracted or processed data
    data: Any = None
    
    # Error message if failed
    error: Optional[str] = None
    
    # Error type classification
    error_type: Optional[str] = None
    
    # Execution metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Steps completed during execution
    steps_completed: List[str] = field(default_factory=list)
    
    # Warnings encountered
    warnings: List[str] = field(default_factory=list)
    
    # Execution time in seconds
    execution_time: float = 0.0
    
    # Number of retries attempted
    retries: int = 0
    
    # Timestamp
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Checkpoint ID for potential rollback
    checkpoint_id: Optional[str] = None
    
    @property
    def failed(self) -> bool:
        """Check if the skill failed."""
        return not self.success
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "error_type": self.error_type,
            "metadata": self.metadata,
            "steps_completed": self.steps_completed,
            "warnings": self.warnings,
            "execution_time": self.execution_time,
            "retries": self.retries,
            "timestamp": self.timestamp.isoformat(),
            "checkpoint_id": self.checkpoint_id,
        }


T = TypeVar('T', bound=SkillInput)


class BaseSkill(ABC, Generic[T]):
    """
    Abstract base class for all skills.
    
    Skills are specialized capabilities that can be executed by the browser agent.
    Each skill implements specific functionality like form filling, data extraction, etc.
    """
    
    # Skill metadata (override in subclasses)
    name: str = "base_skill"
    description: str = "Base skill class"
    version: str = "1.0.0"
    
    # Capabilities required by this skill
    required_capabilities: Set[SkillCapability] = set()
    
    # Capabilities provided by this skill
    provided_capabilities: Set[SkillCapability] = set()
    
    def __init__(
        self,
        browser_controller: Any = None,
        vision_client: Any = None,
        action_executor: Any = None,
        recovery_manager: Any = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the skill.
        
        Args:
            browser_controller: Browser controller instance
            vision_client: Vision client instance
            action_executor: Action executor instance
            recovery_manager: Recovery manager instance
            config: Optional configuration dictionary
        """
        self.browser = browser_controller
        self.vision = vision_client
        self.executor = action_executor
        self.recovery = recovery_manager
        self.config = config or {}
        self._logger = logging.getLogger(f"{__name__}.{self.name}")
    
    @abstractmethod
    async def execute(self, input_data: T) -> SkillResult:
        """
        Execute the skill.
        
        Args:
            input_data: Skill-specific input data
            
        Returns:
            SkillResult with execution outcome
        """
        pass
    
    @abstractmethod
    def validate_input(self, input_data: T) -> bool:
        """
        Validate input data before execution.
        
        Args:
            input_data: Skill-specific input data
            
        Returns:
            True if input is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def verify_results(self, result: SkillResult) -> bool:
        """
        Verify results after execution.
        
        Args:
            result: Result from skill execution
            
        Returns:
            True if results are valid, False otherwise
        """
        pass
    
    def get_required_capabilities(self) -> Set[SkillCapability]:
        """Get capabilities required by this skill."""
        return self.required_capabilities
    
    def get_provided_capabilities(self) -> Set[SkillCapability]:
        """Get capabilities provided by this skill."""
        return self.provided_capabilities
    
    async def _execute_with_retry(
        self,
        input_data: T,
        max_retries: Optional[int] = None,
    ) -> SkillResult:
        """
        Execute skill with retry logic.
        
        Args:
            input_data: Skill-specific input data
            max_retries: Override max retries
            
        Returns:
            SkillResult with execution outcome
        """
        retries = max_retries or input_data.max_retries
        last_result = None
        start_time = datetime.now()
        
        for attempt in range(retries + 1):
            try:
                self._logger.info(
                    f"Executing skill {self.name} (attempt {attempt + 1}/{retries + 1})"
                )
                
                # Validate input if requested
                if input_data.validate_input and not self.validate_input(input_data):
                    return SkillResult(
                        success=False,
                        error="Input validation failed",
                        error_type="VALIDATION_ERROR",
                        retries=attempt,
                    )
                
                # Execute the skill
                result = await self.execute(input_data)
                result.retries = attempt
                
                # Verify results if requested
                if input_data.verify_results and result.success:
                    if not self.verify_results(result):
                        result.success = False
                        result.error = "Result verification failed"
                        result.error_type = "VERIFICATION_ERROR"
                
                # Calculate execution time
                result.execution_time = (datetime.now() - start_time).total_seconds()
                
                if result.success:
                    return result
                
                last_result = result
                
                # Wait before retry (exponential backoff)
                if attempt < retries:
                    wait_time = min(2 ** attempt, 30)  # Max 30 seconds
                    self._logger.warning(
                        f"Skill {self.name} failed, retrying in {wait_time}s: {result.error}"
                    )
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                self._logger.error(f"Skill {self.name} exception: {e}")
                last_result = SkillResult(
                    success=False,
                    error=str(e),
                    error_type="EXECUTION_ERROR",
                    retries=attempt,
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )
                
                if attempt < retries:
                    wait_time = min(2 ** attempt, 30)
                    await asyncio.sleep(wait_time)
        
        # All retries exhausted
        if last_result:
            return last_result
        
        return SkillResult(
            success=False,
            error="Unknown error - no result obtained",
            error_type="UNKNOWN_ERROR",
            retries=retries,
            execution_time=(datetime.now() - start_time).total_seconds(),
        )
    
    def _add_step(self, result: SkillResult, step: str) -> None:
        """Add a completed step to the result."""
        result.steps_completed.append(step)
        self._logger.debug(f"Step completed: {step}")
    
    def _add_warning(self, result: SkillResult, warning: str) -> None:
        """Add a warning to the result."""
        result.warnings.append(warning)
        self._logger.warning(warning)
    
    def _set_error(
        self,
        result: SkillResult,
        error: str,
        error_type: str = "EXECUTION_ERROR",
    ) -> None:
        """Set error on the result."""
        result.success = False
        result.error = error
        result.error_type = error_type
        self._logger.error(f"Error: {error} ({error_type})")
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, version={self.version})"

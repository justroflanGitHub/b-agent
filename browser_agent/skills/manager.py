"""
Skill Manager Module

Provides integration between BrowserAgent and Skills.
Manages skill registration, discovery, and execution.
"""

from typing import Any, Dict, List, Optional, Type
import logging
import asyncio

from .base import BaseSkill, SkillResult, SkillInput, SkillCapability
from .registry import SkillRegistry
from .form_filling import FormFillingSkill, FormFillingInput, FormSchema
from .data_extraction import DataExtractionSkill, DataExtractionInput, ExtractionSchema
from .web_scraping import WebScrapingSkill, WebScrapingInput, ScrapingConfig
from .workflow import WorkflowSkill, WorkflowInput, Workflow

logger = logging.getLogger(__name__)


class SkillManager:
    """
    Manages skill registration and execution for BrowserAgent.
    
    Usage:
        manager = SkillManager(agent)
        manager.register_defaults()
        
        # Execute a skill
        result = await manager.execute_skill("form_filling", input_data)
        
        # Or use convenience methods
        result = await manager.fill_form(schema, data)
    """
    
    def __init__(
        self,
        browser_controller: Any = None,
        vision_client: Any = None,
        action_executor: Any = None,
        recovery_manager: Any = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the skill manager.
        
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
        
        self._registry = SkillRegistry()
        self._instances: Dict[str, BaseSkill] = {}
        self._logger = logging.getLogger(__name__)
    
    def register_defaults(self) -> None:
        """Register all default skills."""
        self._registry.register(FormFillingSkill)
        self._registry.register(DataExtractionSkill)
        self._registry.register(WebScrapingSkill)
        self._registry.register(WorkflowSkill)
        self._logger.info("Registered default skills")
    
    def register_skill(self, skill_class: Type[BaseSkill]) -> None:
        """
        Register a custom skill.
        
        Args:
            skill_class: The skill class to register
        """
        self._registry.register(skill_class)
    
    def unregister_skill(self, name: str) -> bool:
        """
        Unregister a skill.
        
        Args:
            name: Name of the skill to unregister
            
        Returns:
            True if unregistered, False if not found
        """
        return self._registry.unregister(name)
    
    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """
        Get a skill instance.
        
        Args:
            name: Name of the skill
            
        Returns:
            Skill instance or None if not found
        """
        if name in self._instances:
            return self._instances[name]
        
        skill = self._registry.get_skill(
            name,
            browser_controller=self.browser,
            vision_client=self.vision,
            action_executor=self.executor,
            recovery_manager=self.recovery,
            config=self.config,
        )
        
        if skill:
            self._instances[name] = skill
        
        return skill
    
    def list_skills(self) -> List[str]:
        """List all registered skills."""
        return self._registry.list_skills()
    
    def get_skill_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a skill."""
        return self._registry.get_skill_info(name)
    
    async def execute_skill(
        self,
        name: str,
        input_data: SkillInput,
        with_retry: bool = True,
    ) -> SkillResult:
        """
        Execute a skill by name.
        
        Args:
            name: Name of the skill to execute
            input_data: Input data for the skill
            with_retry: Whether to use built-in retry logic
            
        Returns:
            SkillResult from execution
        """
        skill = self.get_skill(name)
        if skill is None:
            return SkillResult(
                success=False,
                error=f"Skill not found: {name}",
                error_type="SKILL_NOT_FOUND",
            )
        
        self._logger.info(f"Executing skill: {name}")
        
        if with_retry:
            return await skill._execute_with_retry(input_data)
        else:
            return await skill.execute(input_data)
    
    # ========================================================================
    # Convenience Methods for Common Skills
    # ========================================================================
    
    async def fill_form(
        self,
        schema: FormSchema,
        data: Dict[str, Any],
        url: Optional[str] = None,
        **kwargs,
    ) -> SkillResult:
        """
        Fill a form with data.
        
        Args:
            schema: Form schema defining fields
            data: Data to fill in the form
            url: Optional URL to navigate to first
            **kwargs: Additional options
            
        Returns:
            SkillResult with filling outcome
        """
        if url:
            schema.url = url
        
        input_data = FormFillingInput(
            task=f"Fill form: {schema.name}",
            schema=schema,
            data=data,
            **kwargs,
        )
        
        return await self.execute_skill("form_filling", input_data)
    
    async def extract_data(
        self,
        schema: ExtractionSchema,
        url: Optional[str] = None,
        **kwargs,
    ) -> SkillResult:
        """
        Extract data from a page.
        
        Args:
            schema: Extraction schema defining fields
            url: Optional URL to navigate to first
            **kwargs: Additional options
            
        Returns:
            SkillResult with extracted data
        """
        input_data = DataExtractionInput(
            task=f"Extract data: {schema.name}",
            schema=schema,
            url=url,
            **kwargs,
        )
        
        return await self.execute_skill("data_extraction", input_data)
    
    async def scrape_website(
        self,
        config: ScrapingConfig,
        **kwargs,
    ) -> SkillResult:
        """
        Scrape data from a website.
        
        Args:
            config: Scraping configuration
            **kwargs: Additional options
            
        Returns:
            SkillResult with scraped data
        """
        input_data = WebScrapingInput(
            task=f"Scrape: {config.start_urls}",
            config=config,
            **kwargs,
        )
        
        return await self.execute_skill("web_scraping", input_data)
    
    async def run_workflow(
        self,
        workflow: Workflow,
        variables: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> SkillResult:
        """
        Run a workflow.
        
        Args:
            workflow: Workflow definition
            variables: Initial variables
            **kwargs: Additional options
            
        Returns:
            SkillResult with workflow results
        """
        input_data = WorkflowInput(
            task=f"Run workflow: {workflow.name}",
            workflow=workflow,
            variables=variables or {},
            **kwargs,
        )
        
        skill = self.get_skill("workflow")
        if skill:
            skill.set_skill_registry(self._registry)
        
        return await self.execute_skill("workflow", input_data)
    
    # ========================================================================
    # Skill Discovery by Capability
    # ========================================================================
    
    def get_skills_by_capability(self, capability: SkillCapability) -> List[str]:
        """Get skills that require a specific capability."""
        return self._registry.get_skills_by_capability(capability)
    
    def get_skills_for_task(
        self,
        required_capabilities: List[SkillCapability],
    ) -> List[str]:
        """
        Find skills suitable for a task based on required capabilities.
        
        Args:
            required_capabilities: List of required capabilities
            
        Returns:
            List of skill names that provide all required capabilities
        """
        required = set(required_capabilities)
        suitable = []
        
        for name in self._registry.list_skills():
            skill_class = self._registry.get_skill_class(name)
            if skill_class:
                provided = skill_class.provided_capabilities
                if required.issubset(provided):
                    suitable.append(name)
        
        return suitable
    
    # ========================================================================
    # Batch Operations
    # ========================================================================
    
    async def execute_skills_sequential(
        self,
        skills: List[tuple],  # List of (name, input_data) tuples
    ) -> List[SkillResult]:
        """
        Execute multiple skills sequentially.
        
        Args:
            skills: List of (skill_name, input_data) tuples
            
        Returns:
            List of SkillResult objects
        """
        results = []
        
        for name, input_data in skills:
            result = await self.execute_skill(name, input_data)
            results.append(result)
            
            if not result.success:
                self._logger.warning(f"Skill {name} failed, stopping sequence")
                break
        
        return results
    
    async def execute_skills_parallel(
        self,
        skills: List[tuple],  # List of (name, input_data) tuples
    ) -> List[SkillResult]:
        """
        Execute multiple skills in parallel.
        
        Args:
            skills: List of (skill_name, input_data) tuples
            
        Returns:
            List of SkillResult objects
        """
        tasks = [
            self.execute_skill(name, input_data)
            for name, input_data in skills
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed results
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(SkillResult(
                    success=False,
                    error=str(result),
                    error_type="EXECUTION_ERROR",
                ))
            else:
                processed.append(result)
        
        return processed
    
    def __repr__(self) -> str:
        return f"SkillManager(skills={len(self._registry)})"


# ============================================================================
# Integration Helper
# ============================================================================

def create_skill_manager_for_agent(agent: Any) -> SkillManager:
    """
    Create a SkillManager configured for a BrowserAgent.
    
    Args:
        agent: BrowserAgent instance
        
    Returns:
        Configured SkillManager
    """
    manager = SkillManager(
        browser_controller=agent.browser,
        vision_client=agent.vision_client,
        action_executor=agent.action_executor,
        recovery_manager=getattr(agent, 'recovery_manager', None),
        config=agent.config.to_dict() if hasattr(agent.config, 'to_dict') else {},
    )
    manager.register_defaults()
    return manager

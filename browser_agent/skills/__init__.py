"""
Skills Module for Browser Agent

This module provides specialized skills for complex browser automation tasks:
- Form filling
- Data extraction
- Web scraping
- Workflow automation

Usage:
    from browser_agent.skills import SkillManager, create_skill_manager_for_agent
    
    # Create skill manager
    manager = SkillManager(browser, vision, executor)
    manager.register_defaults()
    
    # Execute a skill
    result = await manager.fill_form(schema, data)
    
    # Or integrate with agent
    manager = create_skill_manager_for_agent(agent)
"""

from .base import BaseSkill, SkillResult, SkillInput, SkillCapability
from .registry import SkillRegistry, get_global_registry, register_skill
from .form_filling import (
    FormFillingSkill,
    FormFillingInput,
    FormSchema,
    FormField,
    FieldType,
)
from .data_extraction import (
    DataExtractionSkill,
    DataExtractionInput,
    ExtractionSchema,
    ExtractionField,
    ExtractionFieldType,
)
from .web_scraping import (
    WebScrapingSkill,
    WebScrapingInput,
    ScrapingConfig,
    ScrapingMode,
    RateLimitConfig,
    ComplianceLevel,
)
from .workflow import (
    WorkflowSkill,
    WorkflowInput,
    Workflow,
    WorkflowStep,
    WorkflowContext,
    StepType,
    Condition,
    ConditionOperator,
    LoopType,
)
from .manager import SkillManager, create_skill_manager_for_agent

__all__ = [
    # Base classes
    "BaseSkill",
    "SkillResult",
    "SkillInput",
    "SkillCapability",
    # Registry
    "SkillRegistry",
    "get_global_registry",
    "register_skill",
    # Form filling
    "FormFillingSkill",
    "FormFillingInput",
    "FormSchema",
    "FormField",
    "FieldType",
    # Data extraction
    "DataExtractionSkill",
    "DataExtractionInput",
    "ExtractionSchema",
    "ExtractionField",
    "ExtractionFieldType",
    # Web scraping
    "WebScrapingSkill",
    "WebScrapingInput",
    "ScrapingConfig",
    "ScrapingMode",
    "RateLimitConfig",
    "ComplianceLevel",
    # Workflow
    "WorkflowSkill",
    "WorkflowInput",
    "Workflow",
    "WorkflowStep",
    "WorkflowContext",
    "StepType",
    "Condition",
    "ConditionOperator",
    "LoopType",
    # Manager
    "SkillManager",
    "create_skill_manager_for_agent",
]

"""
Skills Module for Browser Agent

This module provides specialized skills for complex browser automation tasks:
- Form filling
- Data extraction
- Web scraping
- Workflow automation
"""

from .base import BaseSkill, SkillResult, SkillInput, SkillCapability
from .registry import SkillRegistry
from .form_filling import FormFillingSkill, FormSchema, FormField
from .data_extraction import DataExtractionSkill, ExtractionSchema, ExtractionField
from .web_scraping import WebScrapingSkill, ScrapingConfig
from .workflow import WorkflowSkill, WorkflowStep, WorkflowContext

__all__ = [
    # Base classes
    "BaseSkill",
    "SkillResult",
    "SkillInput",
    "SkillCapability",
    # Registry
    "SkillRegistry",
    # Form filling
    "FormFillingSkill",
    "FormSchema",
    "FormField",
    # Data extraction
    "DataExtractionSkill",
    "ExtractionSchema",
    "ExtractionField",
    # Web scraping
    "WebScrapingSkill",
    "ScrapingConfig",
    # Workflow
    "WorkflowSkill",
    "WorkflowStep",
    "WorkflowContext",
]

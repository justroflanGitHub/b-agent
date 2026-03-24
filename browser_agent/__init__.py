"""
Browser Agent - Advanced browser automation with visual intelligence.

A modular browser automation framework with:
- Multi-agent orchestration
- Visual element detection via UI-TARS
- Resilient execution with checkpoints and fallbacks
- Skill-based task automation
"""

__version__ = "0.2.0"
__author__ = "Browser Agent Team"

from .config import Config, get_config, default_config
from .browser import BrowserController, BrowserState, create_browser
from .llm import LLMClient, VisionClient, ChatMessage, ChatResponse, MessageRole
from .actor import ActionType, ActionResult, ActionExecutor
from .agent import BrowserAgent, TaskResult, create_agent

__all__ = [
    # Config
    "Config",
    "get_config", 
    "default_config",
    # Browser
    "BrowserController",
    "BrowserState",
    "create_browser",
    # LLM
    "LLMClient",
    "VisionClient",
    "ChatMessage",
    "ChatResponse",
    "MessageRole",
    # Actor
    "ActionType",
    "ActionResult",
    "ActionExecutor",
    # Agent
    "BrowserAgent",
    "TaskResult",
    "create_agent",
]

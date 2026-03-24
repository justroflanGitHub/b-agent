"""
Configuration management for Browser Agent.

This module provides centralized configuration with:
- YAML file support
- Environment variable overrides
- Default configurations
- Validation
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BrowserConfig:
    """Browser configuration settings."""
    viewport_width: int = 2560
    viewport_height: int = 1440
    headless: bool = False
    browser_type: str = "chromium"  # chromium, firefox, webkit
    max_tabs: int = 3
    stealth_mode: bool = True
    user_agent: Optional[str] = None
    startup_timeout: int = 30  # seconds
    

@dataclass
class LLMConfig:
    """LLM configuration settings."""
    provider: str = "lmstudio"  # lmstudio, ollama, openai
    base_url: str = "http://127.0.0.1:1234"
    model: str = "mradermacher/ui-tars-1.5-7b"
    vision_model: str = "mradermacher/ui-tars-1.5-7b"
    temperature: float = 0.1
    max_tokens: int = 4000
    timeout: int = 60  # seconds
    retries: int = 3
    fallback_heuristic: bool = True


@dataclass
class ResilienceConfig:
    """Resilience and recovery configuration."""
    checkpoint_interval: int = 5  # actions between checkpoints
    max_retry_per_action: int = 3
    global_timeout: int = 300  # seconds
    exponential_backoff_base: float = 0.5
    max_checkpoints: int = 50
    state_stack_depth: int = 100


@dataclass
class ActionConfig:
    """Action execution configuration."""
    default_timeout: int = 5000  # milliseconds
    scroll_amount: int = 500  # pixels
    typing_delay: int = 50  # milliseconds between keystrokes
    mouse_move_steps: int = 10  # steps for smooth mouse movement
    wait_after_action: float = 0.5  # seconds


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class Config:
    """Main configuration class."""
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    resilience: ResilienceConfig = field(default_factory=ResilienceConfig)
    action: ActionConfig = field(default_factory=ActionConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Additional settings
    debug_mode: bool = False
    data_dir: str = "./data"
    checkpoints_dir: str = "./checkpoints"
    screenshots_dir: str = "./screenshots"
    
    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """Load configuration from YAML file."""
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f) or {}
        
        return cls._from_dict(data)
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()
        
        # Browser settings
        if os.environ.get('BROWSER_HEADLESS'):
            config.browser.headless = os.environ['BROWSER_HEADLESS'].lower() == 'true'
        if os.environ.get('BROWSER_TYPE'):
            config.browser.browser_type = os.environ['BROWSER_TYPE']
        if os.environ.get('BROWSER_VIEWPORT_WIDTH'):
            config.browser.viewport_width = int(os.environ['BROWSER_VIEWPORT_WIDTH'])
        if os.environ.get('BROWSER_VIEWPORT_HEIGHT'):
            config.browser.viewport_height = int(os.environ['BROWSER_VIEWPORT_HEIGHT'])
        
        # LLM settings
        if os.environ.get('LM_STUDIO_URL'):
            config.llm.base_url = os.environ['LM_STUDIO_URL']
        if os.environ.get('LLM_MODEL'):
            config.llm.model = os.environ['LLM_MODEL']
        if os.environ.get('LLM_TEMPERATURE'):
            config.llm.temperature = float(os.environ['LLM_TEMPERATURE'])
        if os.environ.get('LLM_MAX_TOKENS'):
            config.llm.max_tokens = int(os.environ['LLM_MAX_TOKENS'])
        if os.environ.get('LLM_TIMEOUT'):
            config.llm.timeout = int(os.environ['LLM_TIMEOUT'])
        
        # Resilience settings
        if os.environ.get('MAX_RETRIES'):
            config.resilience.max_retry_per_action = int(os.environ['MAX_RETRIES'])
        if os.environ.get('GLOBAL_TIMEOUT'):
            config.resilience.global_timeout = int(os.environ['GLOBAL_TIMEOUT'])
        
        # Debug mode
        if os.environ.get('DEBUG_MODE'):
            config.debug_mode = os.environ['DEBUG_MODE'].lower() == 'true'
        
        # Directories
        if os.environ.get('DATA_DIR'):
            config.data_dir = os.environ['DATA_DIR']
        if os.environ.get('CHECKPOINTS_DIR'):
            config.checkpoints_dir = os.environ['CHECKPOINTS_DIR']
        
        return config
    
    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        config = cls()
        
        if 'browser' in data:
            config.browser = BrowserConfig(**data['browser'])
        if 'llm' in data:
            config.llm = LLMConfig(**{k: v for k, v in data['llm'].items() 
                                       if k in LLMConfig.__dataclass_fields__})
        if 'resilience' in data:
            config.resilience = ResilienceConfig(**data['resilience'])
        if 'action' in data:
            config.action = ActionConfig(**data['action'])
        if 'logging' in data:
            config.logging = LoggingConfig(**data['logging'])
        
        # Top-level settings
        for key in ['debug_mode', 'data_dir', 'checkpoints_dir', 'screenshots_dir']:
            if key in data:
                setattr(config, key, data[key])
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        from dataclasses import asdict
        return {
            'browser': asdict(self.browser),
            'llm': asdict(self.llm),
            'resilience': asdict(self.resilience),
            'action': asdict(self.action),
            'logging': asdict(self.logging),
            'debug_mode': self.debug_mode,
            'data_dir': self.data_dir,
            'checkpoints_dir': self.checkpoints_dir,
            'screenshots_dir': self.screenshots_dir,
        }
    
    def save_yaml(self, path: str):
        """Save configuration to YAML file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)
    
    def ensure_directories(self):
        """Ensure all required directories exist."""
        for dir_path in [self.data_dir, self.checkpoints_dir, self.screenshots_dir]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)


def get_config(config_path: Optional[str] = None) -> Config:
    """
    Get configuration with priority:
    1. Environment variables (highest)
    2. YAML file
    3. Defaults (lowest)
    """
    # Start with defaults
    config = Config()
    
    # Load from YAML if provided
    if config_path:
        config = Config.from_yaml(config_path)
    
    # Override with environment variables
    env_config = Config.from_env()
    
    # Merge environment overrides
    if os.environ.get('BROWSER_HEADLESS'):
        config.browser.headless = env_config.browser.headless
    if os.environ.get('LM_STUDIO_URL'):
        config.llm.base_url = env_config.llm.base_url
    if os.environ.get('DEBUG_MODE'):
        config.debug_mode = env_config.debug_mode
    
    return config


# Default configuration instance
default_config = get_config()

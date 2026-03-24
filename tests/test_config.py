"""
Unit tests for browser_agent/config.py

Tests cover:
- Default configuration values
- Configuration from dictionary
- Configuration from environment variables
- Configuration to dictionary conversion
- YAML file loading/saving
"""

import os
import pytest
import tempfile
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from browser_agent.config import (
    Config,
    BrowserConfig,
    LLMConfig,
    ResilienceConfig,
    ActionConfig,
    LoggingConfig,
    get_config,
)


class TestBrowserConfig:
    """Tests for BrowserConfig dataclass."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = BrowserConfig()
        
        assert config.viewport_width == 2560
        assert config.viewport_height == 1440
        assert config.headless == False
        assert config.browser_type == "chromium"
        assert config.max_tabs == 3
        assert config.stealth_mode == True
        assert config.user_agent is None
        assert config.startup_timeout == 30
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = BrowserConfig(
            viewport_width=1366,
            viewport_height=768,
            headless=True,
            browser_type="firefox"
        )
        
        assert config.viewport_width == 1366
        assert config.viewport_height == 768
        assert config.headless == True
        assert config.browser_type == "firefox"


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""
    
    def test_default_values(self):
        """Test default LLM configuration."""
        config = LLMConfig()
        
        assert config.provider == "lmstudio"
        assert config.base_url == "http://127.0.0.1:1234"
        assert config.model == "mradermacher/ui-tars-1.5-7b"
        assert config.temperature == 0.1
        assert config.max_tokens == 4000
        assert config.timeout == 60
        assert config.retries == 3
    
    def test_custom_values(self):
        """Test custom LLM configuration."""
        config = LLMConfig(
            provider="openai",
            base_url="https://api.openai.com",
            model="gpt-4",
            temperature=0.7
        )
        
        assert config.provider == "openai"
        assert config.base_url == "https://api.openai.com"
        assert config.model == "gpt-4"
        assert config.temperature == 0.7


class TestResilienceConfig:
    """Tests for ResilienceConfig dataclass."""
    
    def test_default_values(self):
        """Test default resilience configuration."""
        config = ResilienceConfig()
        
        assert config.checkpoint_interval == 5
        assert config.max_retry_per_action == 3
        assert config.global_timeout == 300
        assert config.exponential_backoff_base == 0.5
        assert config.max_checkpoints == 50
        assert config.state_stack_depth == 100


class TestActionConfig:
    """Tests for ActionConfig dataclass."""
    
    def test_default_values(self):
        """Test default action configuration."""
        config = ActionConfig()
        
        assert config.default_timeout == 5000
        assert config.scroll_amount == 500
        assert config.typing_delay == 50
        assert config.mouse_move_steps == 10
        assert config.wait_after_action == 0.5


class TestLoggingConfig:
    """Tests for LoggingConfig dataclass."""
    
    def test_default_values(self):
        """Test default logging configuration."""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert config.file_path is None
        assert config.max_file_size == 10 * 1024 * 1024
        assert config.backup_count == 5


class TestConfig:
    """Tests for main Config class."""
    
    def test_default_values(self):
        """Test default main configuration."""
        config = Config()
        
        assert isinstance(config.browser, BrowserConfig)
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.resilience, ResilienceConfig)
        assert isinstance(config.action, ActionConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert config.debug_mode == False
        assert config.data_dir == "./data"
    
    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "browser": {
                "viewport_width": 1366,
                "headless": True
            },
            "llm": {
                "temperature": 0.5
            },
            "debug_mode": True
        }
        
        config = Config._from_dict(data)
        
        assert config.browser.viewport_width == 1366
        assert config.browser.headless == True
        assert config.llm.temperature == 0.5
        assert config.debug_mode == True
    
    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = Config()
        config.browser.headless = True
        config.debug_mode = True
        
        data = config.to_dict()
        
        assert "browser" in data
        assert "llm" in data
        assert data["browser"]["headless"] == True
        assert data["debug_mode"] == True
    
    def test_save_and_load_yaml(self):
        """Test saving and loading config from YAML file."""
        config = Config()
        config.browser.headless = True
        config.browser.viewport_width = 1366
        config.llm.temperature = 0.5
        config.debug_mode = True
        
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            temp_path = f.name
        
        try:
            # Save
            config.save_yaml(temp_path)
            
            # Load
            loaded_config = Config.from_yaml(temp_path)
            
            assert loaded_config.browser.headless == True
            assert loaded_config.browser.viewport_width == 1366
            assert loaded_config.llm.temperature == 0.5
            assert loaded_config.debug_mode == True
        finally:
            os.unlink(temp_path)
    
    def test_from_yaml_nonexistent(self):
        """Test loading from nonexistent YAML file returns defaults."""
        config = Config.from_yaml("/nonexistent/path/config.yaml")
        
        assert config.browser.viewport_width == 2560  # Default value
    
    def test_ensure_directories(self):
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config()
            config.data_dir = f"{temp_dir}/data"
            config.checkpoints_dir = f"{temp_dir}/checkpoints"
            config.screenshots_dir = f"{temp_dir}/screenshots"
            
            config.ensure_directories()
            
            assert Path(config.data_dir).exists()
            assert Path(config.checkpoints_dir).exists()
            assert Path(config.screenshots_dir).exists()


class TestGetConfig:
    """Tests for get_config function."""
    
    def test_default_config(self):
        """Test getting default configuration."""
        config = get_config()
        
        assert isinstance(config, Config)
        assert config.browser.viewport_width == 2560
    
    def test_env_override(self, monkeypatch):
        """Test environment variable overrides."""
        # Set environment variables
        monkeypatch.setenv("BROWSER_HEADLESS", "true")
        monkeypatch.setenv("LM_STUDIO_URL", "http://custom:8080")
        monkeypatch.setenv("DEBUG_MODE", "true")
        
        config = get_config()
        
        assert config.browser.headless == True
        assert config.llm.base_url == "http://custom:8080"
        assert config.debug_mode == True
    
    def test_env_override_false(self, monkeypatch):
        """Test environment variable with false value."""
        monkeypatch.setenv("BROWSER_HEADLESS", "false")
        
        config = get_config()
        
        assert config.browser.headless == False


class TestConfigIntegration:
    """Integration tests for configuration."""
    
    def test_full_config_workflow(self):
        """Test complete configuration workflow."""
        # Create config with custom values
        config = Config()
        config.browser.headless = True
        config.browser.viewport_width = 1366
        config.llm.temperature = 0.7
        config.resilience.max_retry_per_action = 5
        config.debug_mode = True
        
        # Convert to dict
        data = config.to_dict()
        
        # Recreate from dict
        new_config = Config._from_dict(data)
        
        # Verify values
        assert new_config.browser.headless == True
        assert new_config.browser.viewport_width == 1366
        assert new_config.llm.temperature == 0.7
        assert new_config.resilience.max_retry_per_action == 5
        assert new_config.debug_mode == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

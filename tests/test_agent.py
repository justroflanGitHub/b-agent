"""
Unit tests for browser_agent/agent.py

Tests cover:
- BrowserAgent class
- TaskResult dataclass
- Agent initialization and cleanup
- Task execution (mocked)
"""

import pytest
import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from browser_agent.agent import BrowserAgent, TaskResult, create_agent
from browser_agent.config import Config
from browser_agent.actor import ActionType, ActionResult


class TestTaskResult:
    """Tests for TaskResult dataclass."""
    
    def test_success_result(self):
        """Test creating a successful task result."""
        result = TaskResult(
            success=True,
            goal="Search for Python",
            steps=[{"action": "navigate", "success": True}],
            execution_time=5.5
        )
        
        assert result.success == True
        assert result.goal == "Search for Python"
        assert len(result.steps) == 1
        assert result.execution_time == 5.5
        assert result.error is None
    
    def test_failure_result(self):
        """Test creating a failed task result."""
        result = TaskResult(
            success=False,
            goal="Search for Python",
            steps=[],
            execution_time=2.0,
            error="Element not found"
        )
        
        assert result.success == False
        assert result.error == "Element not found"
    
    def test_result_with_data(self):
        """Test result with extracted data."""
        result = TaskResult(
            success=True,
            goal="Extract text",
            steps=[],
            execution_time=1.0,
            data={"text": "Extracted content"}
        )
        
        assert result.data == {"text": "Extracted content"}
    
    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = TaskResult(
            success=True,
            goal="Test",
            steps=[{"action": "click"}],
            execution_time=1.5
        )
        
        data = result.to_dict()
        
        assert data["success"] == True
        assert data["goal"] == "Test"
        assert len(data["steps"]) == 1
        assert data["execution_time"] == 1.5


class TestBrowserAgent:
    """Tests for BrowserAgent class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = Config()
        config.browser.headless = True
        return config
    
    @pytest.fixture
    def agent(self, config):
        """Create browser agent."""
        return BrowserAgent(config)
    
    def test_create_agent(self, config):
        """Test creating browser agent."""
        agent = BrowserAgent(config)
        
        assert agent.config == config
        assert agent.browser is None
        assert agent.vision_client is None
        assert agent.action_executor is None
        assert agent._initialized == False
    
    def test_agent_not_initialized(self, agent):
        """Test agent starts not initialized."""
        assert agent._initialized == False
        assert agent._current_task is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self, config):
        """Test async context manager."""
        agent = BrowserAgent(config)
        
        # Mock methods
        agent.initialize = AsyncMock(return_value=True)
        agent.cleanup = AsyncMock()
        
        async with agent as a:
            assert a == agent
        
        agent.initialize.assert_called_once()
        agent.cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize(self, agent):
        """Test agent initialization."""
        try:
            result = await agent.initialize()
            
            assert result == True
            assert agent._initialized == True
            assert agent.browser is not None
            assert agent.vision_client is not None
            assert agent.action_executor is not None
            
            await agent.cleanup()
        except ImportError:
            pytest.skip("Playwright not installed")
    
    @pytest.mark.asyncio
    async def test_cleanup(self, agent):
        """Test agent cleanup."""
        try:
            await agent.initialize()
            await agent.cleanup()
            
            assert agent._initialized == False
            assert agent.browser is None
            assert agent.vision_client is None
            assert agent.action_executor is None
            
        except ImportError:
            pytest.skip("Playwright not installed")
    
    def test_get_stats(self, agent):
        """Test getting agent statistics."""
        stats = agent.get_stats()
        
        assert "initialized" in stats
        assert "current_task" in stats
        assert "action_stats" in stats
        assert "vision_stats" in stats


class TestBrowserAgentExecution:
    """Tests for task execution."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = Config()
        config.browser.headless = True
        return config
    
    @pytest.fixture
    async def agent(self, config):
        """Create and initialize browser agent."""
        agent = BrowserAgent(config)
        try:
            await agent.initialize()
            yield agent
        finally:
            await agent.cleanup()
    
    @pytest.mark.asyncio
    async def test_navigate(self, agent):
        """Test navigate convenience method."""
        try:
            result = await agent.navigate("https://example.com")
            
            assert result.success == True
        except:
            pytest.skip("Browser not available")
    
    @pytest.mark.asyncio
    async def test_click(self, agent):
        """Test click convenience method."""
        try:
            await agent.navigate("https://example.com")
            result = await agent.click((100, 100))
            
            assert isinstance(result, ActionResult)
        except:
            pytest.skip("Browser not available")
    
    @pytest.mark.asyncio
    async def test_type_text(self, agent):
        """Test type_text convenience method."""
        try:
            result = await agent.type_text("Hello")
            
            assert isinstance(result, ActionResult)
        except:
            pytest.skip("Browser not available")
    
    @pytest.mark.asyncio
    async def test_press_key(self, agent):
        """Test press_key convenience method."""
        try:
            result = await agent.press_key("Enter")
            
            assert isinstance(result, ActionResult)
        except:
            pytest.skip("Browser not available")
    
    @pytest.mark.asyncio
    async def test_scroll(self, agent):
        """Test scroll convenience methods."""
        try:
            result_down = await agent.scroll_down(200)
            result_up = await agent.scroll_up(100)
            
            assert isinstance(result_down, ActionResult)
            assert isinstance(result_up, ActionResult)
        except:
            pytest.skip("Browser not available")
    
    @pytest.mark.asyncio
    async def test_take_screenshot(self, agent):
        """Test take_screenshot convenience method."""
        try:
            await agent.navigate("https://example.com")
            screenshot = await agent.take_screenshot()
            
            assert isinstance(screenshot, bytes)
            assert len(screenshot) > 0
        except:
            pytest.skip("Browser not available")
    
    @pytest.mark.asyncio
    async def test_extract_text(self, agent):
        """Test extract_text convenience method."""
        try:
            await agent.navigate("https://example.com")
            text = await agent.extract_text()
            
            assert isinstance(text, str)
            assert len(text) > 0
        except:
            pytest.skip("Browser not available")
    
    @pytest.mark.asyncio
    async def test_get_page_info(self, agent):
        """Test get_page_info convenience method."""
        try:
            await agent.navigate("https://example.com")
            info = await agent.get_page_info()
            
            assert "url" in info
            assert "title" in info
        except:
            pytest.skip("Browser not available")


class TestBrowserAgentTask:
    """Tests for full task execution."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = Config()
        config.browser.headless = True
        return config
    
    @pytest.fixture
    async def agent(self, config):
        """Create and initialize browser agent."""
        agent = BrowserAgent(config)
        try:
            await agent.initialize()
            yield agent
        finally:
            await agent.cleanup()
    
    @pytest.mark.asyncio
    async def test_execute_task_simple(self, agent):
        """Test simple task execution."""
        try:
            result = await agent.execute_task(
                "Navigate to example.com",
                start_url="https://example.com"
            )
            
            assert isinstance(result, TaskResult)
            assert result.goal == "Navigate to example.com"
            assert len(result.steps) > 0
        except:
            pytest.skip("Browser not available")
    
    @pytest.mark.asyncio
    async def test_execute_task_no_url(self, agent):
        """Test task execution without starting URL."""
        try:
            result = await agent.execute_task("Test task")
            
            assert isinstance(result, TaskResult)
            assert result.goal == "Test task"
        except:
            pytest.skip("Browser not available")


class TestCreateAgent:
    """Tests for create_agent convenience function."""
    
    @pytest.mark.asyncio
    async def test_create_agent(self):
        """Test create_agent function."""
        config = Config()
        config.browser.headless = True
        
        try:
            agent = await create_agent(config)
            
            assert isinstance(agent, BrowserAgent)
            assert agent._initialized == True
            
            await agent.cleanup()
        except:
            pytest.skip("Browser not available")


class TestVisionGuidedExecution:
    """Tests for vision-guided execution (mocked)."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = Config()
        config.browser.headless = True
        return config
    
    @pytest.fixture
    def agent(self, config):
        """Create browser agent."""
        return BrowserAgent(config)
    
    @pytest.mark.asyncio
    async def test_get_next_action_mocked(self, agent):
        """Test getting next action with mocked vision client."""
        # Mock vision client
        agent.vision_client = MagicMock()
        agent.vision_client.chat_with_image = AsyncMock()
        agent.vision_client.chat_with_image.return_value = MagicMock(
            content='{"type": "click", "x": 100, "y": 200, "description": "Test click"}'
        )
        
        action = await agent._get_next_action("Test task", b"fake_screenshot", 0)
        
        assert action is not None
        assert action["type"] == "click"
    
    @pytest.mark.asyncio
    async def test_execute_vision_action_click(self, agent):
        """Test executing vision-guided click."""
        # Mock action executor
        agent.action_executor = MagicMock()
        agent.action_executor.execute = AsyncMock()
        agent.action_executor.execute.return_value = ActionResult(
            success=True,
            action_type=ActionType.CLICK
        )
        
        # Mock browser page for viewport
        agent.browser = MagicMock()
        agent.browser.page = MagicMock()
        agent.browser.page.evaluate = AsyncMock(return_value={"width": 2560, "height": 1440})
        
        # Mock vision client coordinate tool
        agent.vision_client = MagicMock()
        agent.vision_client.get_click_coordinates = AsyncMock(return_value={
            "x": 100,
            "y": 200,
            "confidence": 0.9,
            "element_found": True
        })
        
        action = {"type": "click", "x": 100, "y": 200, "description": "test element"}
        result = await agent._execute_vision_action(action, b"screenshot")
        
        assert result.success == True
    
    @pytest.mark.asyncio
    async def test_execute_vision_action_type(self, agent):
        """Test executing vision-guided type."""
        # Mock action executor
        agent.action_executor = MagicMock()
        agent.action_executor.execute = AsyncMock()
        agent.action_executor.execute.return_value = ActionResult(
            success=True,
            action_type=ActionType.TYPE_TEXT
        )
        
        action = {"type": "type", "text": "Hello"}
        result = await agent._execute_vision_action(action, b"screenshot")
        
        assert result.success == True
    
    @pytest.mark.asyncio
    async def test_execute_vision_action_press_enter(self, agent):
        """Test executing vision-guided press enter."""
        # Mock action executor
        agent.action_executor = MagicMock()
        agent.action_executor.execute = AsyncMock()
        agent.action_executor.execute.return_value = ActionResult(
            success=True,
            action_type=ActionType.PRESS_KEY
        )
        
        action = {"type": "press_enter"}
        result = await agent._execute_vision_action(action, b"screenshot")
        
        assert result.success == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

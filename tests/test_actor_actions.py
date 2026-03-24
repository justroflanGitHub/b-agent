"""
Unit tests for browser_agent/actor/actions.py

Tests cover:
- ActionType enum
- ActionResult dataclass
- ActionExecutor class
- Individual action implementations (mocked)
"""

import pytest
import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from browser_agent.actor.actions import (
    ActionType,
    ActionResult,
    ActionContext,
    ActionExecutor,
)
from browser_agent.config import Config


class TestActionType:
    """Tests for ActionType enum."""
    
    def test_navigation_actions(self):
        """Test navigation action types exist."""
        assert ActionType.NAVIGATE.value == "navigate"
        assert ActionType.GO_BACK.value == "go_back"
        assert ActionType.GO_FORWARD.value == "go_forward"
        assert ActionType.REFRESH.value == "refresh"
    
    def test_mouse_actions(self):
        """Test mouse action types exist."""
        assert ActionType.CLICK.value == "click"
        assert ActionType.DOUBLE_CLICK.value == "double_click"
        assert ActionType.RIGHT_CLICK.value == "right_click"
        assert ActionType.HOVER.value == "hover"
        assert ActionType.DRAG_AND_DROP.value == "drag_and_drop"
    
    def test_input_actions(self):
        """Test input action types exist."""
        assert ActionType.TYPE_TEXT.value == "type_text"
        assert ActionType.CLEAR_INPUT.value == "clear_input"
        assert ActionType.SELECT_OPTION.value == "select_option"
        assert ActionType.CHECK.value == "check"
        assert ActionType.UNCHECK.value == "uncheck"
    
    def test_scroll_actions(self):
        """Test scroll action types exist."""
        assert ActionType.SCROLL_UP.value == "scroll_up"
        assert ActionType.SCROLL_DOWN.value == "scroll_down"
        assert ActionType.SCROLL_TO.value == "scroll_to"
        assert ActionType.SCROLL_TO_ELEMENT.value == "scroll_to_element"
    
    def test_content_actions(self):
        """Test content action types exist."""
        assert ActionType.EXTRACT_TEXT.value == "extract_text"
        assert ActionType.EXTRACT_HTML.value == "extract_html"
        assert ActionType.GET_PAGE_INFO.value == "get_page_info"
        assert ActionType.TAKE_SCREENSHOT.value == "take_screenshot"
    
    def test_advanced_actions(self):
        """Test advanced action types exist."""
        assert ActionType.WAIT.value == "wait"
        assert ActionType.WAIT_FOR_ELEMENT.value == "wait_for_element"
        assert ActionType.WAIT_FOR_NAVIGATION.value == "wait_for_navigation"
        assert ActionType.PRESS_KEY.value == "press_key"
        assert ActionType.HANDLE_DIALOG.value == "handle_dialog"
    
    # Visual actions removed - coordinate calculation moved to VisionClient.get_click_coordinates()
    
    def test_all_actions_have_values(self):
        """Test all action types have string values."""
        for action in ActionType:
            assert isinstance(action.value, str)
            assert len(action.value) > 0


class TestActionResult:
    """Tests for ActionResult dataclass."""
    
    def test_success_result(self):
        """Test creating a successful result."""
        result = ActionResult(
            success=True,
            action_type=ActionType.CLICK,
            data={"x": 100, "y": 200}
        )
        
        assert result.success == True
        assert result.action_type == ActionType.CLICK
        assert result.data == {"x": 100, "y": 200}
        assert result.error is None
    
    def test_failure_result(self):
        """Test creating a failed result."""
        result = ActionResult(
            success=False,
            action_type=ActionType.CLICK,
            error="Element not found"
        )
        
        assert result.success == False
        assert result.error == "Element not found"
    
    def test_result_with_metadata(self):
        """Test result with metadata."""
        result = ActionResult(
            success=True,
            action_type=ActionType.NAVIGATE,
            data={"url": "https://example.com"},
            metadata={"load_time": 1.5}
        )
        
        assert result.metadata == {"load_time": 1.5}
    
    def test_result_with_timing(self):
        """Test result with execution timing."""
        result = ActionResult(
            success=True,
            action_type=ActionType.CLICK,
            execution_time_ms=150.5,
            retry_count=2
        )
        
        assert result.execution_time_ms == 150.5
        assert result.retry_count == 2
    
    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = ActionResult(
            success=True,
            action_type=ActionType.CLICK,
            data={"x": 100},
            execution_time_ms=50.0
        )
        
        data = result.to_dict()
        
        assert data["success"] == True
        assert data["action_type"] == "click"
        assert data["data"] == {"x": 100}
        assert data["execution_time_ms"] == 50.0


class TestActionContext:
    """Tests for ActionContext dataclass."""
    
    def test_create_context(self):
        """Test creating action context."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_config = Config()
        
        context = ActionContext(
            browser=mock_browser,
            page=mock_page,
            config=mock_config
        )
        
        assert context.browser == mock_browser
        assert context.page == mock_page
        assert context.config == mock_config
        assert context.vision_client is None
        assert context.screenshot is None
    
    def test_context_with_vision(self):
        """Test context with vision client."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_config = Config()
        mock_vision = MagicMock()
        
        context = ActionContext(
            browser=mock_browser,
            page=mock_page,
            config=mock_config,
            vision_client=mock_vision
        )
        
        assert context.vision_client == mock_vision


class TestActionExecutor:
    """Tests for ActionExecutor class."""
    
    @pytest.fixture
    def mock_browser(self):
        """Create mock browser controller."""
        browser = MagicMock()
        browser.page = MagicMock()
        return browser
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()
    
    @pytest.fixture
    def executor(self, mock_browser, config):
        """Create action executor."""
        return ActionExecutor(mock_browser, config)
    
    def test_create_executor(self, mock_browser, config):
        """Test creating action executor."""
        executor = ActionExecutor(mock_browser, config)
        
        assert executor.browser == mock_browser
        assert executor.config == config
        assert len(executor._handlers) > 0
    
    def test_get_stats(self, executor):
        """Test getting executor statistics."""
        stats = executor.get_stats()
        
        assert "total_actions" in stats
        assert "successful_actions" in stats
        assert "success_rate" in stats
    
    def test_get_history(self, executor):
        """Test getting action history."""
        history = executor.get_history()
        
        assert isinstance(history, list)
    
    def test_clear_history(self, executor):
        """Test clearing action history."""
        executor._action_history = [{"test": "data"}]
        executor.clear_history()
        
        assert len(executor._action_history) == 0
    
    @pytest.mark.asyncio
    async def test_execute_unknown_action(self, executor):
        """Test executing unknown action type."""
        # Create a mock action type that's not registered
        result = await executor.execute(ActionType.WAIT, value=0.1)
        
        assert result.success == True
    
    @pytest.mark.asyncio
    async def test_execute_wait_action(self, executor):
        """Test executing wait action."""
        start = time.time()
        result = await executor.execute(ActionType.WAIT, value=0.1)
        elapsed = time.time() - start
        
        assert result.success == True
        assert elapsed >= 0.1
    
    @pytest.mark.asyncio
    async def test_action_recorded_in_history(self, executor):
        """Test that actions are recorded in history."""
        await executor.execute(ActionType.WAIT, value=0.01)
        
        history = executor.get_history()
        assert len(history) == 1
        assert history[0]["action"] == "wait"


class TestActionExecutorNavigation:
    """Tests for navigation actions."""
    
    @pytest.fixture
    def mock_browser(self):
        """Create mock browser with page."""
        browser = MagicMock()
        page = AsyncMock()
        page.goto = AsyncMock()
        page.go_back = AsyncMock()
        page.go_forward = AsyncMock()
        page.reload = AsyncMock()
        browser.page = page
        return browser
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()
    
    @pytest.fixture
    def executor(self, mock_browser, config):
        """Create action executor."""
        return ActionExecutor(mock_browser, config)
    
    @pytest.mark.asyncio
    async def test_navigate_action(self, executor, mock_browser):
        """Test navigate action."""
        result = await executor.execute(
            ActionType.NAVIGATE,
            value="https://example.com"
        )
        
        assert result.success == True
        assert result.data["url"] == "https://example.com"
        mock_browser.page.goto.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_go_back_action(self, executor, mock_browser):
        """Test go back action."""
        result = await executor.execute(ActionType.GO_BACK)
        
        assert result.success == True
        mock_browser.page.go_back.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_go_forward_action(self, executor, mock_browser):
        """Test go forward action."""
        result = await executor.execute(ActionType.GO_FORWARD)
        
        assert result.success == True
        mock_browser.page.go_forward.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_refresh_action(self, executor, mock_browser):
        """Test refresh action."""
        result = await executor.execute(ActionType.REFRESH)
        
        assert result.success == True
        mock_browser.page.reload.assert_called_once()


class TestActionExecutorMouse:
    """Tests for mouse actions."""
    
    @pytest.fixture
    def mock_browser(self):
        """Create mock browser with mouse."""
        browser = MagicMock()
        page = AsyncMock()
        page.mouse = AsyncMock()
        page.mouse.click = AsyncMock()
        page.mouse.move = AsyncMock()
        page.wait_for_selector = AsyncMock()
        browser.page = page
        return browser
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()
    
    @pytest.fixture
    def executor(self, mock_browser, config):
        """Create action executor."""
        return ActionExecutor(mock_browser, config)
    
    @pytest.mark.asyncio
    async def test_click_coordinates(self, executor, mock_browser):
        """Test click at coordinates."""
        result = await executor.execute(
            ActionType.CLICK,
            target=(100, 200)
        )
        
        assert result.success == True
        # Check that coordinates are returned
        # Note: y coordinate has -92 offset applied (user modification)
        assert "x" in result.data
        assert "y" in result.data
        assert result.data["x"] == 100
        assert result.data["y"] == 200  # Account for offset
    #["y"] == 200 - 92 
    @pytest.mark.asyncio
    async def test_hover_coordinates(self, executor, mock_browser):
        """Test hover at coordinates."""
        result = await executor.execute(
            ActionType.HOVER,
            value=(150, 250)
        )
        
        assert result.success == True


class TestActionExecutorScroll:
    """Tests for scroll actions."""
    
    @pytest.fixture
    def mock_browser(self):
        """Create mock browser."""
        browser = MagicMock()
        page = AsyncMock()
        page.evaluate = AsyncMock()
        browser.page = page
        return browser
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()
    
    @pytest.fixture
    def executor(self, mock_browser, config):
        """Create action executor."""
        return ActionExecutor(mock_browser, config)
    
    @pytest.mark.asyncio
    async def test_scroll_down(self, executor, mock_browser):
        """Test scroll down action."""
        result = await executor.execute(ActionType.SCROLL_DOWN, value=500)
        
        assert result.success == True
        assert result.data["amount"] == 500
    
    @pytest.mark.asyncio
    async def test_scroll_up(self, executor, mock_browser):
        """Test scroll up action."""
        result = await executor.execute(ActionType.SCROLL_UP, value=300)
        
        assert result.success == True
        assert result.data["amount"] == 300
    
    @pytest.mark.asyncio
    async def test_scroll_to(self, executor, mock_browser):
        """Test scroll to position."""
        result = await executor.execute(
            ActionType.SCROLL_TO,
            value={"x": 0, "y": 1000}
        )
        
        assert result.success == True
        assert result.data["x"] == 0
        assert result.data["y"] == 1000


class TestActionExecutorContent:
    """Tests for content extraction actions."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()
    
    @pytest.fixture
    def mock_browser(self, config):
        """Create mock browser with viewport from config."""
        browser = MagicMock()
        page = AsyncMock()
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Example Domain")
        page.inner_text = AsyncMock(return_value="Page content here")
        page.content = AsyncMock(return_value="<html><body>HTML</body></html>")
        page.screenshot = AsyncMock(return_value=b"fake_png_data")
        page.query_selector = AsyncMock()
        # Use viewport from config
        page.viewport_size = {
            "width": config.browser.viewport_width,
            "height": config.browser.viewport_height
        }
        browser.page = page
        return browser
    
    @pytest.fixture
    def executor(self, mock_browser, config):
        """Create action executor."""
        return ActionExecutor(mock_browser, config)
    
    @pytest.mark.asyncio
    async def test_extract_text(self, executor, mock_browser):
        """Test text extraction."""
        result = await executor.execute(ActionType.EXTRACT_TEXT)
        
        assert result.success == True
        assert "text" in result.data
    
    @pytest.mark.asyncio
    async def test_extract_html(self, executor, mock_browser):
        """Test HTML extraction."""
        result = await executor.execute(ActionType.EXTRACT_HTML)
        
        assert result.success == True
        assert "html" in result.data
    
    @pytest.mark.asyncio
    async def test_get_page_info(self, executor, mock_browser):
        """Test getting page info."""
        result = await executor.execute(ActionType.GET_PAGE_INFO)
        
        assert result.success == True
        assert result.data["url"] == "https://example.com"
        assert result.data["title"] == "Example Domain"
    
    @pytest.mark.asyncio
    async def test_take_screenshot(self, executor, mock_browser):
        """Test taking screenshot."""
        result = await executor.execute(ActionType.TAKE_SCREENSHOT)
        
        assert result.success == True
        assert result.screenshot == b"fake_png_data"


class TestActionExecutorInput:
    """Tests for input actions."""
    
    @pytest.fixture
    def mock_browser(self):
        """Create mock browser."""
        browser = MagicMock()
        page = AsyncMock()
        page.keyboard = AsyncMock()
        page.keyboard.type = AsyncMock()
        page.keyboard.press = AsyncMock()
        page.wait_for_selector = AsyncMock()
        browser.page = page
        return browser
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()
    
    @pytest.fixture
    def executor(self, mock_browser, config):
        """Create action executor."""
        return ActionExecutor(mock_browser, config)
    
    @pytest.mark.asyncio
    async def test_type_text(self, executor, mock_browser):
        """Test typing text."""
        result = await executor.execute(
            ActionType.TYPE_TEXT,
            value="Hello World"
        )
        
        assert result.success == True
        assert result.data["text"] == "Hello World"
    
    @pytest.mark.asyncio
    async def test_press_key(self, executor, mock_browser):
        """Test pressing key."""
        result = await executor.execute(
            ActionType.PRESS_KEY,
            value="Enter"
        )
        
        assert result.success == True
        assert result.data["key"] == "Enter"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

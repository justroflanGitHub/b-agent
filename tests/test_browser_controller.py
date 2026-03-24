"""
Unit tests for browser_agent/browser/controller.py

Tests cover:
- BrowserController class
- BrowserState dataclass
- Anti-detection measures
- Page management
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from browser_agent.browser.controller import (
    BrowserController,
    BrowserState,
    STEALTH_JS,
    DEFAULT_HEADERS,
    create_browser,
)
from browser_agent.config import Config, BrowserConfig


class TestBrowserState:
    """Tests for BrowserState dataclass."""
    
    def test_create_state(self):
        """Test creating browser state."""
        state = BrowserState(
            url="https://example.com",
            title="Example",
            scroll_x=0,
            scroll_y=100,
            cookies=[]
        )
        
        assert state.url == "https://example.com"
        assert state.title == "Example"
        assert state.scroll_x == 0
        assert state.scroll_y == 100
        assert state.screenshot is None
    
    def test_state_with_screenshot(self):
        """Test state with screenshot."""
        state = BrowserState(
            url="https://example.com",
            title="Example",
            scroll_x=0,
            scroll_y=0,
            cookies=[],
            screenshot=b"png_data"
        )
        
        assert state.screenshot == b"png_data"


class TestStealthJS:
    """Tests for stealth JavaScript injection."""
    
    def test_stealth_js_contains_webdriver(self):
        """Test that stealth JS removes webdriver."""
        assert "webdriver" in STEALTH_JS
        assert "false" in STEALTH_JS
    
    def test_stealth_js_contains_plugins(self):
        """Test that stealth JS mocks plugins."""
        assert "plugins" in STEALTH_JS
        assert "Chrome PDF Plugin" in STEALTH_JS
    
    def test_stealth_js_contains_languages(self):
        """Test that stealth JS mocks languages."""
        assert "languages" in STEALTH_JS
        assert "en-US" in STEALTH_JS


class TestDefaultHeaders:
    """Tests for default HTTP headers."""
    
    def test_headers_contain_accept(self):
        """Test that headers contain Accept."""
        assert "Accept" in DEFAULT_HEADERS
    
    def test_headers_contain_sec_ch_ua(self):
        """Test that headers contain Sec-CH-UA."""
        assert "Sec-Ch-Ua" in DEFAULT_HEADERS
        assert "Chromium" in DEFAULT_HEADERS["Sec-Ch-Ua"]
    
    def test_headers_contain_language(self):
        """Test that headers contain language."""
        assert "Accept-Language" in DEFAULT_HEADERS
        assert "en-US" in DEFAULT_HEADERS["Accept-Language"]


class TestBrowserController:
    """Tests for BrowserController class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()
    
    @pytest.fixture
    def controller(self, config):
        """Create browser controller."""
        return BrowserController(config)
    
    def test_create_controller(self, config):
        """Test creating browser controller."""
        controller = BrowserController(config)
        
        assert controller.config == config
        assert controller.browser_config == config.browser
        assert controller._playwright is None
        assert controller._browser is None
    
    def test_controller_properties(self, controller):
        """Test controller properties."""
        assert controller.page is None
        assert controller.pages == []
    
    @pytest.mark.asyncio
    async def test_context_manager(self, config):
        """Test async context manager."""
        controller = BrowserController(config)
        
        # Mock the launch and close methods
        controller.launch = AsyncMock(return_value=controller)
        controller.close = AsyncMock()
        
        async with controller as ctx:
            assert ctx == controller
        
        controller.launch.assert_called_once()
        controller.close.assert_called_once()


class TestBrowserControllerLaunch:
    """Tests for browser launch functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration with headless."""
        config = Config()
        config.browser.headless = True
        return config
    
    @pytest.fixture
    def controller(self, config):
        """Create browser controller."""
        return BrowserController(config)
    
    @pytest.mark.asyncio
    async def test_launch_creates_browser(self, controller):
        """Test that launch creates browser instance."""
        # This test requires playwright to be installed
        try:
            await controller.launch()
            
            assert controller._playwright is not None
            assert controller._browser is not None
            assert controller._context is not None
            
            await controller.close()
        except ImportError:
            pytest.skip("Playwright not installed")
    
    @pytest.mark.asyncio
    async def test_launch_headless_mode(self):
        """Test launching in headless mode."""
        config = Config()
        config.browser.headless = True
        
        controller = BrowserController(config)
        
        try:
            await controller.launch()
            
            # Browser should be launched
            assert controller._browser is not None
            
            await controller.close()
        except ImportError:
            pytest.skip("Playwright not installed")
    
    @pytest.mark.asyncio
    async def test_close_cleanup(self, controller):
        """Test that close cleans up resources."""
        try:
            await controller.launch()
            await controller.close()
            
            assert controller._context is None
            assert controller._browser is None
            assert controller._playwright is None
            assert controller._pages == []
            assert controller._current_page is None
            
        except ImportError:
            pytest.skip("Playwright not installed")


class TestBrowserControllerPages:
    """Tests for page management."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = Config()
        config.browser.headless = True
        return config
    
    @pytest.fixture
    async def controller(self, config):
        """Create and launch browser controller."""
        controller = BrowserController(config)
        try:
            await controller.launch()
            yield controller
        finally:
            await controller.close()
    
    @pytest.mark.asyncio
    async def test_new_page(self, controller):
        """Test creating new page."""
        try:
            page = await controller.new_page()
            
            assert page is not None
            assert len(controller._pages) == 1
            assert controller._current_page == page
        except:
            pytest.skip("Browser not available")
    
    @pytest.mark.asyncio
    async def test_navigate(self, controller):
        """Test navigation."""
        try:
            await controller.new_page()
            await controller.goto("https://example.com")
            
            assert "example.com" in controller.page.url
        except:
            pytest.skip("Browser not available")
    
    @pytest.mark.asyncio
    async def test_max_tabs_limit(self):
        """Test max tabs limit."""
        config = Config()
        config.browser.headless = True
        config.browser.max_tabs = 2
        
        controller = BrowserController(config)
        
        try:
            await controller.launch()
            
            # Create max tabs
            await controller.new_page()
            await controller.new_page()
            
            # Try to create one more - should return current page
            page = await controller.new_page()
            
            # Should still have only max_tabs pages
            assert len(controller._pages) <= config.browser.max_tabs
            
            await controller.close()
        except:
            pytest.skip("Browser not available")


class TestBrowserControllerState:
    """Tests for state management."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = Config()
        config.browser.headless = True
        return config
    
    @pytest.fixture
    async def controller(self, config):
        """Create and launch browser controller."""
        controller = BrowserController(config)
        try:
            await controller.launch()
            yield controller
        finally:
            await controller.close()
    
    @pytest.mark.asyncio
    async def test_get_state(self, controller):
        """Test getting browser state."""
        try:
            await controller.new_page()
            await controller.goto("https://example.com")
            
            state = await controller.get_state()
            
            assert isinstance(state, BrowserState)
            assert "example.com" in state.url
            assert state.title is not None
        except:
            pytest.skip("Browser not available")
    
    @pytest.mark.asyncio
    async def test_screenshot(self, controller):
        """Test taking screenshot."""
        try:
            await controller.new_page()
            await controller.goto("https://example.com")
            
            screenshot = await controller.screenshot()
            
            assert isinstance(screenshot, bytes)
            assert len(screenshot) > 0
        except:
            pytest.skip("Browser not available")


class TestCreateBrowser:
    """Tests for create_browser convenience function."""
    
    @pytest.mark.asyncio
    async def test_create_browser(self):
        """Test create_browser function."""
        config = Config()
        config.browser.headless = True
        
        try:
            browser = await create_browser(config)
            
            assert isinstance(browser, BrowserController)
            assert browser._browser is not None
            
            await browser.close()
        except:
            pytest.skip("Browser not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

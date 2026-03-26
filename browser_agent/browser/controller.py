"""
Browser Controller - Playwright-based browser automation.

This module provides:
- Browser lifecycle management
- Page/tab management
- Anti-detection measures
- Stealth mode configuration
"""

import asyncio
import logging
import random
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

from ..config import Config, BrowserConfig

logger = logging.getLogger(__name__)


# Anti-detection JavaScript to inject
STEALTH_JS = """
// Remove webdriver property
Object.defineProperty(navigator, 'webdriver', {
    get: () => false,
});

// Mock plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
        { name: 'Chromium PDF Plugin', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
        { name: 'Microsoft Edge PDF Plugin', filename: 'internal-pdf-viewer' },
        { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer' }
    ],
});

// Mock languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});

// Mock permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// Mock screen properties
Object.defineProperty(screen, 'availHeight', { get: () => screen.height - 40 });
Object.defineProperty(screen, 'availWidth', { get: () => screen.width });

// Mock battery
if ('getBattery' in navigator) {
    navigator.getBattery = () => Promise.resolve({
        charging: true,
        chargingTime: Infinity,
        dischargingTime: Infinity,
        level: 1,
    });
}

// Mock connection
if ('connection' in navigator) {
    Object.defineProperty(navigator.connection, 'rtt', { get: () => 50 });
}

// Hide automation indicators
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};

// Mock permissions API more thoroughly
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        parameters.name === 'geolocation' ?
            Promise.resolve({ state: PromptResultType.GRANTED }) :
            originalQuery(parameters)
);
"""

# Realistic HTTP headers
DEFAULT_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9',
    'Cache-Control': 'max-age=0',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1'
}


@dataclass
class BrowserState:
    """Current browser state snapshot."""
    url: str
    title: str
    scroll_x: int
    scroll_y: int
    cookies: List[Dict]
    screenshot: Optional[bytes] = None


class BrowserController:
    """
    Playwright-based browser controller with anti-detection.
    
    Usage:
        async with BrowserController(config) as browser:
            page = await browser.new_page()
            await page.goto("https://example.com")
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.browser_config = self.config.browser
        
        self._playwright = None
        self._browser = None
        self._context = None
        self._pages: List = []
        self._current_page = None
        self._current_frame = None  # Current iframe (if any)
        self._frame_stack: List = []  # Stack for nested iframes
        
    async def __aenter__(self):
        await self.launch()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    @property
    def page(self):
        """Get current active page."""
        return self._current_page
    
    @property
    def pages(self):
        """Get all open pages."""
        return self._pages.copy()
    
    async def launch(self) -> "BrowserController":
        """Launch browser with configured settings."""
        try:
            from playwright.async_api import async_playwright
            
            logger.info(f"Launching {self.browser_config.browser_type} browser...")
            
            self._playwright = await async_playwright().start()
            
            # Select browser type
            browser_types = {
                "chromium": self._playwright.chromium,
                "firefox": self._playwright.firefox,
                "webkit": self._playwright.webkit
            }
            
            browser_type = browser_types.get(
                self.browser_config.browser_type,
                self._playwright.chromium
            )
            
            # Launch arguments
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-extensions",
            ]
            
            if not self.browser_config.headless:
                # Calculate window position to center on screen
                # Assume screen is 2560x1440, window will be viewport size
                window_width = self.browser_config.viewport_width
                window_height = self.browser_config.viewport_height
                
                launch_args.extend([
                    f"--window-size={window_width},{window_height}",
                    f"--window-position=0,0",
                ])
            
            # Launch browser
            self._browser = await browser_type.launch(
                headless=self.browser_config.headless,
                args=launch_args
            )
            
            # Create context - ALWAYS set viewport to ensure accurate coordinate mapping
            context_options = {
                "viewport": {
                    "width": self.browser_config.viewport_width,
                    "height": self.browser_config.viewport_height
                }
            }
            
            if self.browser_config.user_agent:
                context_options["user_agent"] = self.browser_config.user_agent
            
            self._context = await self._browser.new_context(**context_options)
            
            # Add stealth scripts if enabled
            if self.browser_config.stealth_mode:
                await self._context.add_init_script(STEALTH_JS)
                await self._context.set_extra_http_headers(DEFAULT_HEADERS)
            
            logger.info("✅ Browser launched successfully")
            return self
            
        except Exception as e:
            logger.error(f"❌ Failed to launch browser: {e}")
            raise
    
    async def new_page(self, url: Optional[str] = None):
        """Create a new page/tab."""
        if not self._context:
            raise RuntimeError("Browser not launched. Call launch() first.")
        
        if len(self._pages) >= self.browser_config.max_tabs:
            logger.warning(f"Max tabs ({self.browser_config.max_tabs}) reached")
            return self._current_page
        
        page = await self._context.new_page()
        self._pages.append(page)
        self._current_page = page
        
        # Add human-like behavior
        await self._add_human_behavior(page)
        
        if url:
            await self.goto(url)
        
        logger.info(f"Created new page (total: {len(self._pages)})")
        return page
    
    async def goto(self, url: str, wait_until: str = "networkidle", timeout: Optional[int] = None):
        """Navigate to URL."""
        if not self._current_page:
            await self.new_page()
        
        timeout = timeout or self.browser_config.startup_timeout * 1000
        logger.info(f"Navigating to: {url}")
        
        await self._current_page.goto(url, wait_until=wait_until, timeout=timeout)
        await asyncio.sleep(0.5)  # Brief pause after navigation
        
        logger.info(f"Loaded: {url}")
    
    async def go_back(self):
        """Navigate back."""
        if self._current_page:
            await self._current_page.go_back()
            logger.info("Navigated back")
    
    async def go_forward(self):
        """Navigate forward."""
        if self._current_page:
            await self._current_page.go_forward()
            logger.info("Navigated forward")
    
    async def refresh(self):
        """Refresh current page."""
        if self._current_page:
            await self._current_page.reload()
            logger.info("Page refreshed")
    
    async def switch_page(self, index: int):
        """Switch to a different page by index."""
        if 0 <= index < len(self._pages):
            self._current_page = self._pages[index]
            logger.info(f"Switched to page {index}")
            return self._current_page
        raise IndexError(f"Page index {index} out of range")
    
    async def close_page(self, index: Optional[int] = None):
        """Close a page by index (or current page if no index)."""
        if index is None:
            index = self._pages.index(self._current_page)
        
        if 0 <= index < len(self._pages):
            page = self._pages.pop(index)
            await page.close()
            
            if self._current_page == page:
                self._current_page = self._pages[0] if self._pages else None
            
            logger.info(f"Closed page {index}")
    
    async def screenshot(self, full_page: bool = False) -> bytes:
        """Take screenshot of current page."""
        if not self._current_page:
            raise RuntimeError("No active page")
        
        return await self._current_page.screenshot(type="png", full_page=full_page)
    
    async def get_state(self) -> BrowserState:
        """Get current browser state snapshot."""
        if not self._current_page:
            raise RuntimeError("No active page")
        
        page = self._current_page
        
        # Get scroll position
        scroll_position = await page.evaluate("""
            () => ({
                x: window.scrollX,
                y: window.scrollY
            })
        """)
        
        # Get cookies
        cookies = await self._context.cookies()
        
        return BrowserState(
            url=page.url,
            title=await page.title(),
            scroll_x=scroll_position["x"],
            scroll_y=scroll_position["y"],
            cookies=cookies
        )
    
    async def set_cookies(self, cookies: List[Dict]):
        """Set cookies."""
        await self._context.add_cookies(cookies)
    
    async def execute_script(self, script: str):
        """Execute JavaScript on current page."""
        if self._current_page:
            return await self._current_page.evaluate(script)
    
    async def wait_for_selector(self, selector: str, timeout: int = 5000):
        """Wait for element to appear."""
        if self._current_page:
            await self._current_page.wait_for_selector(selector, timeout=timeout)
    
    async def wait_for_navigation(self, timeout: int = 30000):
        """Wait for navigation to complete."""
        if self._current_page:
            async with self._current_page.expect_navigation(timeout=timeout):
                pass
    
    async def query_selector(self, selector: str):
        """Query for a single element."""
        if self._current_page:
            return await self._current_page.query_selector(selector)
    
    async def query_selector_all(self, selector: str) -> List:
        """Query for all matching elements."""
        if self._current_page:
            return await self._current_page.query_selector_all(selector)
        return []
    
    # ==================== Frame Management ====================
    
    async def switch_frame(self, frame_selector: str) -> bool:
        """
        Switch to an iframe by selector.
        
        Args:
            frame_selector: CSS selector for the iframe element
            
        Returns:
            True if frame was found and switched to
        """
        if not self._current_page:
            raise RuntimeError("No active page")
        
        frame = self._current_page.frame_locator(frame_selector)
        if frame:
            self._frame_stack.append(self._current_frame)
            self._current_frame = frame
            logger.info(f"Switched to frame: {frame_selector}")
            return True
        logger.warning(f"Frame not found: {frame_selector}")
        return False
    
    async def switch_to_main_frame(self):
        """Switch back to the main page frame."""
        self._current_frame = None
        self._frame_stack = []
        logger.info("Switched to main frame")
    
    async def switch_to_parent_frame(self) -> bool:
        """Switch to parent frame (if nested iframes)."""
        if self._frame_stack:
            self._current_frame = self._frame_stack.pop()
            logger.info("Switched to parent frame")
            return True
        logger.warning("No parent frame to switch to")
        return False
    
    def get_current_frame(self):
        """Get the current frame (or main page if no frame selected)."""
        return self._current_frame or self._current_page
    
    async def get_frames(self) -> List[str]:
        """Get list of all iframe selectors on the page."""
        if not self._current_page:
            return []
        
        frames = await self._current_page.query_selector_all("iframe")
        return [await frame.get_attribute("id") or await frame.get_attribute("name") or f"iframe[{i}]"
                for i, frame in enumerate(frames)]
    
    # ==================== End Frame Management ====================
    
    async def _add_human_behavior(self, page):
        """Add human-like behavior patterns."""
        try:
            # Random mouse movements
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, self.browser_config.viewport_width - 100)
                y = random.randint(100, self.browser_config.viewport_height - 100)
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.05, 0.2))
            
            # Random scroll
            await page.evaluate(f"""
                window.scrollTo({{
                    top: Math.random() * {random.randint(100, 300)},
                    behavior: 'smooth'
                }});
            """)
            await asyncio.sleep(0.3)
            
        except Exception as e:
            logger.debug(f"Human behavior simulation skipped: {e}")
    
    async def close(self):
        """Close browser and cleanup."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            
            self._context = None
            self._browser = None
            self._playwright = None
            self._pages = []
            self._current_page = None
            
            logger.info("Browser closed")
            
        except Exception as e:
            logger.warning(f"Error during browser cleanup: {e}")


# Convenience function
async def create_browser(config: Optional[Config] = None) -> BrowserController:
    """Create and launch a browser controller."""
    browser = BrowserController(config)
    await browser.launch()
    return browser

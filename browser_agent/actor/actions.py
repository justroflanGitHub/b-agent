"""
Actor Actions - Browser action definitions and execution.

This module provides:
- Action type enumeration
- Action result data structure
- Action executor with retry logic
- All browser actions implementation
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ..browser.controller import BrowserController

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """All available browser action types."""

    # Navigation
    NAVIGATE = "navigate"
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"
    REFRESH = "refresh"

    # Mouse
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    HOVER = "hover"
    DRAG_AND_DROP = "drag_and_drop"

    # Visual Mouse (Phase 2)
    HOVER_VISUAL = "hover_visual"
    TYPE_VISUAL = "type_visual"

    # Input
    TYPE_TEXT = "type_text"
    CLEAR_INPUT = "clear_input"
    SELECT_OPTION = "select_option"
    CHECK = "check"
    UNCHECK = "uncheck"

    # Scroll
    SCROLL_UP = "scroll_up"
    SCROLL_DOWN = "scroll_down"
    SCROLL_TO = "scroll_to"
    SCROLL_TO_ELEMENT = "scroll_to_element"

    # Content
    EXTRACT_TEXT = "extract_text"
    EXTRACT_HTML = "extract_html"
    GET_PAGE_INFO = "get_page_info"
    TAKE_SCREENSHOT = "take_screenshot"

    # Advanced
    WAIT = "wait"
    WAIT_FOR_ELEMENT = "wait_for_element"
    WAIT_FOR_NAVIGATION = "wait_for_navigation"
    SWITCH_FRAME = "switch_frame"
    HANDLE_DIALOG = "handle_dialog"
    PRESS_KEY = "press_key"


@dataclass
class ActionResult:
    """Result of an action execution."""

    success: bool
    action_type: ActionType
    data: Any = None
    error: Optional[str] = None
    screenshot: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "action_type": self.action_type.value,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "execution_time_ms": self.execution_time_ms,
            "retry_count": self.retry_count,
        }


@dataclass
class ActionContext:
    """Context for action execution."""

    browser: "BrowserController"
    page: Any  # Playwright page
    config: Any  # Config object
    vision_client: Optional[Any] = None  # VisionClient
    screenshot: Optional[bytes] = None


class ActionExecutor:
    """
    Executes browser actions with retry logic and logging.

    Usage:
        executor = ActionExecutor(browser, config)
        result = await executor.execute(ActionType.CLICK, selector="#button")
    """

    def __init__(self, browser: "BrowserController", config, vision_client=None):
        self.browser = browser
        self.config = config
        self.vision_client = vision_client

        self._action_history: List[Dict[str, Any]] = []
        self._total_actions = 0
        self._successful_actions = 0

        # Register action handlers
        self._handlers: Dict[ActionType, Callable] = {
            ActionType.NAVIGATE: self._navigate,
            ActionType.GO_BACK: self._go_back,
            ActionType.GO_FORWARD: self._go_forward,
            ActionType.REFRESH: self._refresh,
            ActionType.CLICK: self._click,
            ActionType.DOUBLE_CLICK: self._double_click,
            ActionType.RIGHT_CLICK: self._right_click,
            ActionType.HOVER: self._hover,
            ActionType.DRAG_AND_DROP: self._drag_and_drop,
            ActionType.HOVER_VISUAL: self._hover_visual,
            ActionType.TYPE_VISUAL: self._type_visual,
            ActionType.TYPE_TEXT: self._type_text,
            ActionType.CLEAR_INPUT: self._clear_input,
            ActionType.SELECT_OPTION: self._select_option,
            ActionType.CHECK: self._check,
            ActionType.UNCHECK: self._uncheck,
            ActionType.SCROLL_UP: self._scroll_up,
            ActionType.SCROLL_DOWN: self._scroll_down,
            ActionType.SCROLL_TO: self._scroll_to,
            ActionType.SCROLL_TO_ELEMENT: self._scroll_to_element,
            ActionType.EXTRACT_TEXT: self._extract_text,
            ActionType.EXTRACT_HTML: self._extract_html,
            ActionType.GET_PAGE_INFO: self._get_page_info,
            ActionType.TAKE_SCREENSHOT: self._take_screenshot,
            ActionType.WAIT: self._wait,
            ActionType.WAIT_FOR_ELEMENT: self._wait_for_element,
            ActionType.WAIT_FOR_NAVIGATION: self._wait_for_navigation,
            ActionType.PRESS_KEY: self._press_key,
            ActionType.HANDLE_DIALOG: self._handle_dialog,
            ActionType.SWITCH_FRAME: self._switch_frame,
        }

    async def execute(
        self,
        action_type: ActionType,
        target: Optional[str] = None,
        value: Any = None,
        options: Optional[Dict[str, Any]] = None,
        screenshot: Optional[bytes] = None,
    ) -> ActionResult:
        """
        Execute an action with retry logic.

        Args:
            action_type: Type of action to execute
            target: CSS selector, XPath, or coordinates
            value: Value for the action (text to type, etc.)
            options: Additional options
            screenshot: Current screenshot for visual actions

        Returns:
            ActionResult with success status and data
        """
        options = options or {}
        max_retries = self.config.resilience.max_retry_per_action
        base_delay = self.config.resilience.exponential_backoff_base

        last_error = None
        start_time = time.time()

        for attempt in range(max_retries):
            try:
                # Get handler
                handler = self._handlers.get(action_type)
                if not handler:
                    return ActionResult(
                        success=False, action_type=action_type, error=f"Unknown action type: {action_type}"
                    )

                # Build context
                context = ActionContext(
                    browser=self.browser,
                    page=self.browser.page,
                    config=self.config,
                    vision_client=self.vision_client,
                    screenshot=screenshot,
                )

                # Execute handler
                result = await handler(context, target, value, options)

                # Record success
                self._total_actions += 1
                self._successful_actions += 1
                self._record_action(action_type, target, True, attempt)

                result.execution_time_ms = (time.time() - start_time) * 1000
                result.retry_count = attempt

                # Wait after action
                await asyncio.sleep(self.config.action.wait_after_action)

                return result

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Action {action_type.value} failed (attempt {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)

        # All retries failed
        self._total_actions += 1
        self._record_action(action_type, target, False, max_retries - 1)

        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Failed after {max_retries} attempts: {last_error}",
            execution_time_ms=(time.time() - start_time) * 1000,
            retry_count=max_retries - 1,
        )

    def _record_action(self, action_type: ActionType, target: Optional[str], success: bool, attempts: int):
        """Record action in history."""
        self._action_history.append(
            {
                "action": action_type.value,
                "target": target,
                "success": success,
                "attempts": attempts + 1,
                "timestamp": time.time(),
            }
        )

        # Limit history size
        if len(self._action_history) > 1000:
            self._action_history = self._action_history[-500:]

    # ==================== Navigation Actions ====================

    async def _navigate(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Navigate to URL."""
        url = value or target
        if not url:
            return ActionResult(success=False, action_type=ActionType.NAVIGATE, error="No URL provided")

        wait_until = options.get("wait_until", "networkidle")
        timeout = options.get("timeout", self.config.browser.startup_timeout * 1000)

        await ctx.page.goto(url, wait_until=wait_until, timeout=timeout)

        return ActionResult(success=True, action_type=ActionType.NAVIGATE, data={"url": url})

    async def _go_back(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Navigate back."""
        await ctx.page.go_back()
        return ActionResult(success=True, action_type=ActionType.GO_BACK)

    async def _go_forward(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Navigate forward."""
        await ctx.page.go_forward()
        return ActionResult(success=True, action_type=ActionType.GO_FORWARD)

    async def _refresh(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Refresh page."""
        await ctx.page.reload()
        return ActionResult(success=True, action_type=ActionType.REFRESH)

    # ==================== Mouse Actions ====================

    async def _click(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Click on element or coordinates."""
        button = options.get("button", "left")
        click_count = options.get("click_count", 1)
        delay = options.get("delay", 50)

        # Check if target is coordinates
        if isinstance(target, (list, tuple)) and len(target) == 2:
            x, y = target
            logger.info(f"🖱️ Click at coordinates: ({x}, {y})")
            await ctx.page.mouse.click(x, y, button=button, click_count=click_count, delay=delay)
            return ActionResult(success=True, action_type=ActionType.CLICK, data={"x": x, "y": y})

        # Check if target is coordinates in value
        if isinstance(value, (list, tuple)) and len(value) == 2:
            x, y = value
            logger.info(f"🖱️ Click at coordinates: ({x}, {y})")
            await ctx.page.mouse.click(x, y, button=button, click_count=click_count, delay=delay)
            return ActionResult(success=True, action_type=ActionType.CLICK, data={"x": x, "y": y})

        # Click by selector
        if target:
            element = await ctx.page.wait_for_selector(target, timeout=self.config.action.default_timeout)
            # Get element bounding box to log click coordinates
            box = await element.bounding_box()
            if box:
                center_x = box["x"] + box["width"] / 2
                center_y = box["y"] + box["height"] / 2
                logger.info(f"🖱️ Click on element '{target}' at coordinates: ({center_x:.0f}, {center_y:.0f})")
            await element.click(button=button, click_count=click_count, delay=delay)
            return ActionResult(
                success=True,
                action_type=ActionType.CLICK,
                data={"selector": target, "coordinates": {"x": center_x, "y": center_y} if box else None},
            )

        return ActionResult(success=False, action_type=ActionType.CLICK, error="No target or coordinates provided")

    async def _double_click(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Double click on element."""
        if target:
            element = await ctx.page.wait_for_selector(target, timeout=self.config.action.default_timeout)
            await element.dblclick()
            return ActionResult(success=True, action_type=ActionType.DOUBLE_CLICK)

        return ActionResult(success=False, action_type=ActionType.DOUBLE_CLICK, error="No selector provided")

    async def _right_click(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Right click on element."""
        if target:
            element = await ctx.page.wait_for_selector(target, timeout=self.config.action.default_timeout)
            await element.click(button="right")
            return ActionResult(success=True, action_type=ActionType.RIGHT_CLICK)

        # Right click at coordinates
        if isinstance(value, (list, tuple)) and len(value) == 2:
            x, y = value
            await ctx.page.mouse.click(x, y, button="right")
            return ActionResult(success=True, action_type=ActionType.RIGHT_CLICK)

        return ActionResult(success=False, action_type=ActionType.RIGHT_CLICK, error="No target provided")

    async def _hover(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Hover over element."""
        if target:
            element = await ctx.page.wait_for_selector(target, timeout=self.config.action.default_timeout)
            await element.hover()
            return ActionResult(success=True, action_type=ActionType.HOVER)

        # Hover at coordinates
        if isinstance(value, (list, tuple)) and len(value) == 2:
            x, y = value
            await ctx.page.mouse.move(x, y)
            return ActionResult(success=True, action_type=ActionType.HOVER)

        return ActionResult(success=False, action_type=ActionType.HOVER, error="No target provided")

    async def _drag_and_drop(
        self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict
    ) -> ActionResult:
        """Drag and drop element."""
        source = target
        target_selector = options.get("target_selector") or value

        if not source or not target_selector:
            return ActionResult(success=False, action_type=ActionType.DRAG_AND_DROP, error="Source and target required")

        source_el = await ctx.page.wait_for_selector(source, timeout=self.config.action.default_timeout)
        target_el = await ctx.page.wait_for_selector(target_selector, timeout=self.config.action.default_timeout)

        await source_el.drag_and_drop(target_el)
        return ActionResult(success=True, action_type=ActionType.DRAG_AND_DROP)

    # ==================== Visual Actions (Phase 2) ====================

    async def _hover_visual(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """
        Hover over element by visual description.

        Uses vision model to find element coordinates from description.

        Args:
            target: Visual description of element to hover
            value: Alternative to target
            options: May contain 'screenshot' for vision analysis
        """
        description = target or value
        if not description:
            return ActionResult(
                success=False, action_type=ActionType.HOVER_VISUAL, error="No visual description provided"
            )

        # Check if we have vision client
        if not self.vision_client:
            return ActionResult(
                success=False, action_type=ActionType.HOVER_VISUAL, error="Vision client not available for visual hover"
            )

        # Get screenshot from context or take new one
        screenshot = ctx.screenshot or options.get("screenshot")
        if not screenshot:
            screenshot = await ctx.page.screenshot()

        try:
            # Use vision client to get coordinates
            coords = await self.vision_client.get_click_coordinates(
                screenshot=screenshot,
                element_description=description,
                viewport_width=ctx.page.viewport_size.get("width", 2560),
                viewport_height=ctx.page.viewport_size.get("height", 1440),
            )

            x = coords.get("x", 0)
            y = coords.get("y", 0)
            confidence = coords.get("confidence", 0)

            if confidence < 0.5 or not coords.get("element_found", False):
                return ActionResult(
                    success=False,
                    action_type=ActionType.HOVER_VISUAL,
                    error=f"Could not locate element: {description}",
                    data={"confidence": confidence},
                )

            logger.info(f"🖱️ Visual hover on '{description}' at ({x}, {y}) confidence={confidence:.2f}")

            # Perform hover
            await ctx.page.mouse.move(x, y)

            return ActionResult(
                success=True,
                action_type=ActionType.HOVER_VISUAL,
                data={"x": x, "y": y, "description": description, "confidence": confidence},
            )

        except Exception as e:
            logger.error(f"Visual hover failed: {e}")
            return ActionResult(success=False, action_type=ActionType.HOVER_VISUAL, error=str(e))

    async def _type_visual(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """
        Click on element by visual description and type text.

        Combines visual click with typing in one action.

        Args:
            target: Visual description of input element
            value: Text to type
            options: May contain 'screenshot', 'clear' (bool), 'delay' (int)
        """
        description = target
        text = str(value) if value else ""

        if not description:
            return ActionResult(
                success=False, action_type=ActionType.TYPE_VISUAL, error="No visual description provided"
            )

        if not text:
            return ActionResult(success=False, action_type=ActionType.TYPE_VISUAL, error="No text provided to type")

        # Check if we have vision client
        if not self.vision_client:
            return ActionResult(
                success=False, action_type=ActionType.TYPE_VISUAL, error="Vision client not available for visual typing"
            )

        # Get screenshot from context or take new one
        screenshot = ctx.screenshot or options.get("screenshot")
        if not screenshot:
            screenshot = await ctx.page.screenshot()

        try:
            # Use vision client to get coordinates
            coords = await self.vision_client.get_click_coordinates(
                screenshot=screenshot,
                element_description=description,
                viewport_width=ctx.page.viewport_size.get("width", 2560),
                viewport_height=ctx.page.viewport_size.get("height", 1440),
            )

            x = coords.get("x", 0)
            y = coords.get("y", 0)
            confidence = coords.get("confidence", 0)

            if confidence < 0.5 or not coords.get("element_found", False):
                return ActionResult(
                    success=False,
                    action_type=ActionType.TYPE_VISUAL,
                    error=f"Could not locate element: {description}",
                    data={"confidence": confidence},
                )

            logger.info(f"🖱️ Visual click on '{description}' at ({x}, {y}) for typing")

            # Click to focus
            await ctx.page.mouse.click(x, y)

            # Small delay for focus
            await asyncio.sleep(0.1)

            # Clear if requested
            if options.get("clear", False):
                await ctx.page.keyboard.press("Control+A")
                await asyncio.sleep(0.05)

            # Type text
            delay = options.get("delay", self.config.action.typing_delay)
            await ctx.page.keyboard.type(text, delay=delay)

            logger.info(f"⌨️ Typed '{text}' into '{description}'")

            return ActionResult(
                success=True,
                action_type=ActionType.TYPE_VISUAL,
                data={"x": x, "y": y, "text": text, "description": description, "confidence": confidence},
            )

        except Exception as e:
            logger.error(f"Visual type failed: {e}")
            return ActionResult(success=False, action_type=ActionType.TYPE_VISUAL, error=str(e))

    # ==================== Input Actions ====================

    async def _type_text(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Type text into element."""
        text = str(value) if value else ""
        delay = options.get("delay", self.config.action.typing_delay)
        clear = options.get("clear", False)

        if target:
            element = await ctx.page.wait_for_selector(target, timeout=self.config.action.default_timeout)

            if clear:
                await element.fill("")

            await element.type(text, delay=delay)
            return ActionResult(success=True, action_type=ActionType.TYPE_TEXT, data={"text": text, "selector": target})

        # Type into currently focused element
        await ctx.page.keyboard.type(text, delay=delay)
        return ActionResult(success=True, action_type=ActionType.TYPE_TEXT, data={"text": text})

    async def _clear_input(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Clear input field."""
        if not target:
            return ActionResult(success=False, action_type=ActionType.CLEAR_INPUT, error="No selector provided")

        element = await ctx.page.wait_for_selector(target, timeout=self.config.action.default_timeout)
        await element.fill("")
        return ActionResult(success=True, action_type=ActionType.CLEAR_INPUT)

    async def _select_option(
        self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict
    ) -> ActionResult:
        """Select option from dropdown."""
        if not target:
            return ActionResult(success=False, action_type=ActionType.SELECT_OPTION, error="No selector provided")

        element = await ctx.page.wait_for_selector(target, timeout=self.config.action.default_timeout)

        # Select by value, label, or index
        if isinstance(value, int):
            await element.select_option(index=value)
        else:
            await element.select_option(value)

        return ActionResult(success=True, action_type=ActionType.SELECT_OPTION, data={"value": value})

    async def _check(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Check checkbox."""
        if not target:
            return ActionResult(success=False, action_type=ActionType.CHECK, error="No selector provided")

        element = await ctx.page.wait_for_selector(target, timeout=self.config.action.default_timeout)
        await element.check()
        return ActionResult(success=True, action_type=ActionType.CHECK)

    async def _uncheck(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Uncheck checkbox."""
        if not target:
            return ActionResult(success=False, action_type=ActionType.UNCHECK, error="No selector provided")

        element = await ctx.page.wait_for_selector(target, timeout=self.config.action.default_timeout)
        await element.uncheck()
        return ActionResult(success=True, action_type=ActionType.UNCHECK)

    # ==================== Scroll Actions ====================

    async def _scroll_up(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Scroll up."""
        amount = value or self.config.action.scroll_amount
        await ctx.page.evaluate(f"window.scrollBy(0, -{amount})")
        return ActionResult(success=True, action_type=ActionType.SCROLL_UP, data={"amount": amount})

    async def _scroll_down(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Scroll down."""
        amount = value or self.config.action.scroll_amount
        await ctx.page.evaluate(f"window.scrollBy(0, {amount})")
        return ActionResult(success=True, action_type=ActionType.SCROLL_DOWN, data={"amount": amount})

    async def _scroll_to(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Scroll to position."""
        if isinstance(value, (list, tuple)) and len(value) == 2:
            x, y = value
        elif isinstance(value, dict):
            x = value.get("x", 0)
            y = value.get("y", 0)
        else:
            return ActionResult(success=False, action_type=ActionType.SCROLL_TO, error="Invalid scroll position")

        await ctx.page.evaluate(f"window.scrollTo({x}, {y})")
        return ActionResult(success=True, action_type=ActionType.SCROLL_TO, data={"x": x, "y": y})

    async def _scroll_to_element(
        self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict
    ) -> ActionResult:
        """Scroll to element."""
        if not target:
            return ActionResult(success=False, action_type=ActionType.SCROLL_TO_ELEMENT, error="No selector provided")

        element = await ctx.page.wait_for_selector(target, timeout=self.config.action.default_timeout)
        await element.scroll_into_view_if_needed()
        return ActionResult(success=True, action_type=ActionType.SCROLL_TO_ELEMENT)

    # ==================== Content Actions ====================

    async def _extract_text(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Extract text from page or element."""
        if target:
            element = await ctx.page.query_selector(target)
            if element:
                text = await element.inner_text()
                return ActionResult(success=True, action_type=ActionType.EXTRACT_TEXT, data={"text": text})
            return ActionResult(success=False, action_type=ActionType.EXTRACT_TEXT, error="Element not found")

        # Get all page text
        text = await ctx.page.inner_text("body")
        return ActionResult(success=True, action_type=ActionType.EXTRACT_TEXT, data={"text": text})

    async def _extract_html(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Extract HTML from page or element."""
        if target:
            element = await ctx.page.query_selector(target)
            if element:
                html = await element.inner_html()
                return ActionResult(success=True, action_type=ActionType.EXTRACT_HTML, data={"html": html})
            return ActionResult(success=False, action_type=ActionType.EXTRACT_HTML, error="Element not found")

        # Get all page HTML
        html = await ctx.page.content()
        return ActionResult(success=True, action_type=ActionType.EXTRACT_HTML, data={"html": html})

    async def _get_page_info(
        self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict
    ) -> ActionResult:
        """Get page information."""
        info = {
            "url": ctx.page.url,
            "title": await ctx.page.title(),
        }

        # Get additional info
        viewport = ctx.page.viewport_size
        info["viewport"] = viewport

        return ActionResult(success=True, action_type=ActionType.GET_PAGE_INFO, data=info)

    async def _take_screenshot(
        self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict
    ) -> ActionResult:
        """Take screenshot."""
        full_page = options.get("full_page", False)
        screenshot = await ctx.page.screenshot(type="png", full_page=full_page)

        return ActionResult(
            success=True, action_type=ActionType.TAKE_SCREENSHOT, screenshot=screenshot, data={"full_page": full_page}
        )

    # ==================== Advanced Actions ====================

    async def _wait(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Wait for specified time."""
        seconds = float(value) if value else 1.0
        await asyncio.sleep(seconds)
        return ActionResult(success=True, action_type=ActionType.WAIT, data={"seconds": seconds})

    async def _wait_for_element(
        self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict
    ) -> ActionResult:
        """Wait for element to appear."""
        if not target:
            return ActionResult(success=False, action_type=ActionType.WAIT_FOR_ELEMENT, error="No selector provided")

        timeout = options.get("timeout", self.config.action.default_timeout)
        state = options.get("state", "visible")

        await ctx.page.wait_for_selector(target, timeout=timeout, state=state)
        return ActionResult(success=True, action_type=ActionType.WAIT_FOR_ELEMENT)

    async def _wait_for_navigation(
        self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict
    ) -> ActionResult:
        """Wait for navigation."""
        timeout = options.get("timeout", 30000)
        url = target or value

        if url:
            async with ctx.page.expect_navigation(url=url, timeout=timeout):
                pass
        else:
            async with ctx.page.expect_navigation(timeout=timeout):
                pass

        return ActionResult(success=True, action_type=ActionType.WAIT_FOR_NAVIGATION)

    async def _press_key(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Press keyboard key."""
        key = value or target
        if not key:
            return ActionResult(success=False, action_type=ActionType.PRESS_KEY, error="No key specified")

        await ctx.page.keyboard.press(key)
        return ActionResult(success=True, action_type=ActionType.PRESS_KEY, data={"key": key})

    async def _handle_dialog(
        self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict
    ) -> ActionResult:
        """Handle browser dialog (alert, confirm, prompt)."""
        accept = options.get("accept", True)
        prompt_text = value

        # Set up dialog handler
        async def dialog_handler(dialog):
            if prompt_text and dialog.type == "prompt":
                await dialog.accept(prompt_text)
            elif accept:
                await dialog.accept()
            else:
                await dialog.dismiss()

        ctx.page.on("dialog", dialog_handler)
        return ActionResult(success=True, action_type=ActionType.HANDLE_DIALOG)

    async def _switch_frame(self, ctx: ActionContext, target: Optional[str], value: Any, options: Dict) -> ActionResult:
        """Switch to iframe or back to main frame.

        Args:
            target: CSS selector for iframe, or "main" to switch to main frame,
                   or "parent" to switch to parent frame
        """
        if not target:
            return ActionResult(success=False, action_type=ActionType.SWITCH_FRAME, error="No frame selector provided")

        try:
            if target == "main":
                await self.browser.switch_to_main_frame()
                return ActionResult(success=True, action_type=ActionType.SWITCH_FRAME, data={"frame": "main"})
            elif target == "parent":
                success = await self.browser.switch_to_parent_frame()
                return ActionResult(
                    success=success,
                    action_type=ActionType.SWITCH_FRAME,
                    data={"frame": "parent"} if success else None,
                    error=None if success else "No parent frame to switch to",
                )
            else:
                success = await self.browser.switch_frame(target)
                return ActionResult(
                    success=success,
                    action_type=ActionType.SWITCH_FRAME,
                    data={"frame": target} if success else None,
                    error=None if success else f"Frame not found: {target}",
                )
        except Exception as e:
            return ActionResult(success=False, action_type=ActionType.SWITCH_FRAME, error=str(e))

    # ==================== Utility Methods ====================

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        return {
            "total_actions": self._total_actions,
            "successful_actions": self._successful_actions,
            "success_rate": self._successful_actions / max(1, self._total_actions),
            "action_history_size": len(self._action_history),
        }

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get action history."""
        return self._action_history[-limit:]

    def clear_history(self):
        """Clear action history."""
        self._action_history = []

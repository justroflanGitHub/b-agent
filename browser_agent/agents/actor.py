"""
Actor Agent Module

The Actor Agent is responsible for:
- Executing browser actions
- Performing interactions with web pages
- Handling action failures and retries
- Reporting action results
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import asyncio
import uuid

from .base import (
    BaseAgent,
    AgentConfig,
    AgentCapability,
    AgentResult,
)


class ActionType(Enum):
    """Types of actions the actor can perform."""
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    HOVER = "hover"
    TYPE = "type"
    PRESS_KEY = "press_key"
    SCROLL = "scroll"
    NAVIGATE = "navigate"
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"
    REFRESH = "refresh"
    WAIT = "wait"
    SELECT = "select"
    CHECK = "check"
    UNCHECK = "uncheck"
    UPLOAD = "upload"
    DRAG = "drag"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"


@dataclass
class ActionRequest:
    """Request to perform an action."""
    action_type: ActionType
    selector: Optional[str] = None
    coordinates: Optional[Dict[str, float]] = None  # x, y
    text: Optional[str] = None
    value: Optional[str] = None
    url: Optional[str] = None
    keys: Optional[str] = None  # For press_key
    direction: Optional[str] = None  # For scroll: up, down
    amount: Optional[int] = None  # For scroll
    timeout: float = 30.0
    wait_before: float = 0.0
    wait_after: float = 0.5
    retry_count: int = 2
    retry_delay: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_type": self.action_type.value,
            "selector": self.selector,
            "coordinates": self.coordinates,
            "text": self.text,
            "value": self.value,
            "url": self.url,
            "keys": self.keys,
            "direction": self.direction,
            "amount": self.amount,
            "timeout": self.timeout,
            "wait_before": self.wait_before,
            "wait_after": self.wait_after,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "metadata": self.metadata,
        }


@dataclass
class ActionResult:
    """Result of an action execution."""
    action_id: str
    action_type: ActionType
    success: bool
    data: Any = None
    error: Optional[str] = None
    screenshot_before: Optional[bytes] = None
    screenshot_after: Optional[bytes] = None
    duration_ms: float = 0.0
    retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class ActorAgent(BaseAgent):
    """
    Agent responsible for executing browser actions.
    
    Capabilities:
    - Click, type, scroll, navigate
    - Form interactions
    - Keyboard input
    - Waiting and synchronization
    - Screenshot capture
    """
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        browser: Optional[Any] = None,
        action_executor: Optional[Any] = None,
    ):
        if config is None:
            config = AgentConfig(
                name="ActorAgent",
                capabilities={
                    AgentCapability.ACTION_EXECUTION,
                    AgentCapability.NAVIGATION,
                    AgentCapability.FORM_HANDLING,
                },
            )
        super().__init__(config)
        self._browser = browser
        self._action_executor = action_executor
    
    def set_browser(self, browser: Any) -> None:
        """Set the browser instance."""
        self._browser = browser
    
    def set_action_executor(self, executor: Any) -> None:
        """Set the action executor."""
        self._action_executor = executor
    
    async def execute(self, task: Any) -> AgentResult:
        """Execute an action task."""
        if isinstance(task, ActionRequest):
            result = await self.perform_action(task)
            return AgentResult(
                success=result.success,
                agent_id=self.agent_id,
                task_id=result.action_id,
                data=result.to_dict(),
                error=result.error,
                metadata={"action_type": task.action_type.value},
            )
        elif isinstance(task, dict):
            # Parse dict as action request
            try:
                request = self._parse_action_request(task)
                result = await self.perform_action(request)
                return AgentResult(
                    success=result.success,
                    agent_id=self.agent_id,
                    task_id=result.action_id,
                    data=result.to_dict(),
                    error=result.error,
                )
            except Exception as e:
                return AgentResult(
                    success=False,
                    agent_id=self.agent_id,
                    task_id="unknown",
                    error=str(e),
                )
        else:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                task_id="unknown",
                error=f"Unknown task type: {type(task)}",
            )
    
    def _parse_action_request(self, data: Dict[str, Any]) -> ActionRequest:
        """Parse a dictionary into an ActionRequest."""
        action_type = ActionType(data.get("action_type", "click"))
        return ActionRequest(
            action_type=action_type,
            selector=data.get("selector"),
            coordinates=data.get("coordinates"),
            text=data.get("text"),
            value=data.get("value"),
            url=data.get("url"),
            keys=data.get("keys"),
            direction=data.get("direction"),
            amount=data.get("amount"),
            timeout=data.get("timeout", 30.0),
            wait_before=data.get("wait_before", 0.0),
            wait_after=data.get("wait_after", 0.5),
            retry_count=data.get("retry_count", 2),
            retry_delay=data.get("retry_delay", 1.0),
            metadata=data.get("metadata", {}),
        )
    
    async def perform_action(self, request: ActionRequest) -> ActionResult:
        """Perform an action with retries."""
        action_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # Wait before action
        if request.wait_before > 0:
            await asyncio.sleep(request.wait_before)
        
        # Take screenshot before if browser available
        screenshot_before = None
        if self._browser:
            try:
                screenshot_before = await self._take_screenshot()
            except Exception:
                pass
        
        # Execute with retries
        last_error = None
        for attempt in range(request.retry_count + 1):
            try:
                result_data = await self._execute_action(request)
                
                # Wait after action
                if request.wait_after > 0:
                    await asyncio.sleep(request.wait_after)
                
                # Take screenshot after
                screenshot_after = None
                if self._browser:
                    try:
                        screenshot_after = await self._take_screenshot()
                    except Exception:
                        pass
                
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                return ActionResult(
                    action_id=action_id,
                    action_type=request.action_type,
                    success=True,
                    data=result_data,
                    screenshot_before=screenshot_before,
                    screenshot_after=screenshot_after,
                    duration_ms=duration_ms,
                    retries=attempt,
                )
                
            except Exception as e:
                last_error = str(e)
                if attempt < request.retry_count:
                    await asyncio.sleep(request.retry_delay)
        
        # All retries failed
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        return ActionResult(
            action_id=action_id,
            action_type=request.action_type,
            success=False,
            error=last_error,
            screenshot_before=screenshot_before,
            duration_ms=duration_ms,
            retries=request.retry_count,
        )
    
    async def _execute_action(self, request: ActionRequest) -> Any:
        """Execute a single action."""
        # Use action executor if available
        if self._action_executor:
            return await self._action_executor.execute_action(
                request.action_type.value,
                **self._get_action_params(request),
            )
        
        # Fall back to direct browser control
        if not self._browser:
            raise RuntimeError("No browser or action executor available")
        
        page = self._browser.get_current_page()
        if not page:
            raise RuntimeError("No active page available")
        
        action_type = request.action_type
        
        if action_type == ActionType.CLICK:
            return await self._do_click(page, request)
        elif action_type == ActionType.DOUBLE_CLICK:
            return await self._do_double_click(page, request)
        elif action_type == ActionType.RIGHT_CLICK:
            return await self._do_right_click(page, request)
        elif action_type == ActionType.HOVER:
            return await self._do_hover(page, request)
        elif action_type == ActionType.TYPE:
            return await self._do_type(page, request)
        elif action_type == ActionType.PRESS_KEY:
            return await self._do_press_key(page, request)
        elif action_type == ActionType.SCROLL:
            return await self._do_scroll(page, request)
        elif action_type == ActionType.NAVIGATE:
            return await self._do_navigate(page, request)
        elif action_type == ActionType.GO_BACK:
            return await page.go_back()
        elif action_type == ActionType.GO_FORWARD:
            return await page.go_forward()
        elif action_type == ActionType.REFRESH:
            return await page.reload()
        elif action_type == ActionType.WAIT:
            return await self._do_wait(page, request)
        elif action_type == ActionType.SELECT:
            return await self._do_select(page, request)
        elif action_type == ActionType.CHECK:
            return await self._do_check(page, request, True)
        elif action_type == ActionType.UNCHECK:
            return await self._do_check(page, request, False)
        elif action_type == ActionType.DRAG:
            return await self._do_drag(page, request)
        elif action_type == ActionType.SCREENSHOT:
            return await self._take_screenshot()
        elif action_type == ActionType.EXTRACT:
            return await self._do_extract(page, request)
        else:
            raise ValueError(f"Unknown action type: {action_type}")
    
    def _get_action_params(self, request: ActionRequest) -> Dict[str, Any]:
        """Get action parameters from request."""
        params = {}
        if request.selector:
            params["selector"] = request.selector
        if request.coordinates:
            params["x"] = request.coordinates.get("x")
            params["y"] = request.coordinates.get("y")
        if request.text:
            params["text"] = request.text
        if request.value:
            params["value"] = request.value
        if request.url:
            params["url"] = request.url
        if request.keys:
            params["keys"] = request.keys
        if request.direction:
            params["direction"] = request.direction
        if request.amount:
            params["amount"] = request.amount
        return params
    
    async def _do_click(self, page: Any, request: ActionRequest) -> bool:
        """Perform click action."""
        if request.coordinates:
            await page.mouse.click(
                request.coordinates["x"],
                request.coordinates["y"],
            )
        elif request.selector:
            element = await page.wait_for_selector(
                request.selector,
                timeout=request.timeout * 1000,
            )
            await element.click()
        else:
            raise ValueError("Click requires either selector or coordinates")
        return True
    
    async def _do_double_click(self, page: Any, request: ActionRequest) -> bool:
        """Perform double click action."""
        if request.coordinates:
            await page.mouse.dblclick(
                request.coordinates["x"],
                request.coordinates["y"],
            )
        elif request.selector:
            element = await page.wait_for_selector(
                request.selector,
                timeout=request.timeout * 1000,
            )
            await element.dblclick()
        else:
            raise ValueError("Double click requires either selector or coordinates")
        return True
    
    async def _do_right_click(self, page: Any, request: ActionRequest) -> bool:
        """Perform right click action."""
        if request.coordinates:
            await page.mouse.click(
                request.coordinates["x"],
                request.coordinates["y"],
                button="right",
            )
        elif request.selector:
            element = await page.wait_for_selector(
                request.selector,
                timeout=request.timeout * 1000,
            )
            await element.click(button="right")
        else:
            raise ValueError("Right click requires either selector or coordinates")
        return True
    
    async def _do_hover(self, page: Any, request: ActionRequest) -> bool:
        """Perform hover action."""
        if request.coordinates:
            await page.mouse.move(
                request.coordinates["x"],
                request.coordinates["y"],
            )
        elif request.selector:
            element = await page.wait_for_selector(
                request.selector,
                timeout=request.timeout * 1000,
            )
            await element.hover()
        else:
            raise ValueError("Hover requires either selector or coordinates")
        return True
    
    async def _do_type(self, page: Any, request: ActionRequest) -> bool:
        """Perform type action."""
        if not request.text:
            raise ValueError("Type action requires text")
        
        if request.selector:
            element = await page.wait_for_selector(
                request.selector,
                timeout=request.timeout * 1000,
            )
            await element.fill(request.text)
        elif request.coordinates:
            # Click first to focus, then type
            await page.mouse.click(
                request.coordinates["x"],
                request.coordinates["y"],
            )
            await page.keyboard.type(request.text)
        else:
            # Just type into focused element
            await page.keyboard.type(request.text)
        return True
    
    async def _do_press_key(self, page: Any, request: ActionRequest) -> bool:
        """Press a key."""
        if not request.keys:
            raise ValueError("Press key action requires keys")
        await page.keyboard.press(request.keys)
        return True
    
    async def _do_scroll(self, page: Any, request: ActionRequest) -> bool:
        """Perform scroll action."""
        direction = request.direction or "down"
        amount = request.amount or 300
        
        if direction == "down":
            await page.mouse.wheel(0, amount)
        elif direction == "up":
            await page.mouse.wheel(0, -amount)
        elif direction == "right":
            await page.mouse.wheel(amount, 0)
        elif direction == "left":
            await page.mouse.wheel(-amount, 0)
        else:
            # Scroll to element
            if request.selector:
                element = await page.wait_for_selector(
                    request.selector,
                    timeout=request.timeout * 1000,
                )
                await element.scroll_into_view_if_needed()
        
        return True
    
    async def _do_navigate(self, page: Any, request: ActionRequest) -> bool:
        """Navigate to URL."""
        if not request.url:
            raise ValueError("Navigate action requires URL")
        await page.goto(request.url, timeout=request.timeout * 1000)
        return True
    
    async def _do_wait(self, page: Any, request: ActionRequest) -> bool:
        """Wait for condition."""
        if request.selector:
            await page.wait_for_selector(
                request.selector,
                timeout=request.timeout * 1000,
            )
        else:
            await asyncio.sleep(request.timeout)
        return True
    
    async def _do_select(self, page: Any, request: ActionRequest) -> bool:
        """Select option from dropdown."""
        if not request.selector or not request.value:
            raise ValueError("Select requires selector and value")
        
        element = await page.wait_for_selector(
            request.selector,
            timeout=request.timeout * 1000,
        )
        await element.select_option(value=request.value)
        return True
    
    async def _do_check(self, page: Any, request: ActionRequest, checked: bool) -> bool:
        """Check or uncheck a checkbox."""
        if not request.selector:
            raise ValueError("Check/Uncheck requires selector")
        
        element = await page.wait_for_selector(
            request.selector,
            timeout=request.timeout * 1000,
        )
        if checked:
            await element.check()
        else:
            await element.uncheck()
        return True
    
    async def _do_drag(self, page: Any, request: ActionRequest) -> bool:
        """Perform drag action."""
        if not request.selector:
            raise ValueError("Drag requires selector")
        
        # For drag, we need source and target
        # This is a simplified implementation
        element = await page.wait_for_selector(
            request.selector,
            timeout=request.timeout * 1000,
        )
        
        if request.coordinates:
            box = await element.bounding_box()
            if box:
                source_x = box["x"] + box["width"] / 2
                source_y = box["y"] + box["height"] / 2
                await page.mouse.move(source_x, source_y)
                await page.mouse.down()
                await page.mouse.move(
                    request.coordinates["x"],
                    request.coordinates["y"],
                )
                await page.mouse.up()
        return True
    
    async def _take_screenshot(self) -> bytes:
        """Take a screenshot."""
        if self._browser:
            page = self._browser.get_current_page()
            if page:
                return await page.screenshot()
        raise RuntimeError("Cannot take screenshot without browser")
    
    async def _do_extract(self, page: Any, request: ActionRequest) -> Dict[str, Any]:
        """Extract data from page."""
        result = {}
        
        if request.selector:
            element = await page.query_selector(request.selector)
            if element:
                result["text"] = await element.text_content()
                result["html"] = await element.inner_html()
        else:
            result["text"] = await page.text_content("body")
            result["html"] = await page.content()
            result["url"] = page.url
            result["title"] = await page.title()
        
        return result
    
    # Convenience methods
    
    async def click(self, selector: str, **kwargs) -> ActionResult:
        """Click an element."""
        request = ActionRequest(
            action_type=ActionType.CLICK,
            selector=selector,
            **kwargs,
        )
        return await self.perform_action(request)
    
    async def type_text(self, selector: str, text: str, **kwargs) -> ActionResult:
        """Type text into an element."""
        request = ActionRequest(
            action_type=ActionType.TYPE,
            selector=selector,
            text=text,
            **kwargs,
        )
        return await self.perform_action(request)
    
    async def navigate(self, url: str, **kwargs) -> ActionResult:
        """Navigate to a URL."""
        request = ActionRequest(
            action_type=ActionType.NAVIGATE,
            url=url,
            **kwargs,
        )
        return await self.perform_action(request)
    
    async def scroll(self, direction: str = "down", amount: int = 300, **kwargs) -> ActionResult:
        """Scroll the page."""
        request = ActionRequest(
            action_type=ActionType.SCROLL,
            direction=direction,
            amount=amount,
            **kwargs,
        )
        return await self.perform_action(request)
    
    async def wait_for_element(self, selector: str, timeout: float = 30.0, **kwargs) -> ActionResult:
        """Wait for an element to appear."""
        request = ActionRequest(
            action_type=ActionType.WAIT,
            selector=selector,
            timeout=timeout,
            **kwargs,
        )
        return await self.perform_action(request)

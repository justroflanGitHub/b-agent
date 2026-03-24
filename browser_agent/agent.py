"""
Browser Agent - Main agent class combining all components.

This module provides the main BrowserAgent class that orchestrates:
- Browser controller
- LLM/Vision client
- Action executor
- State management
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

from .config import Config, get_config
from .browser import BrowserController, BrowserState
from .llm import VisionClient, ChatMessage, MessageRole
from .actor import ActionExecutor, ActionType, ActionResult

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of a task execution."""
    success: bool
    goal: str
    steps: List[Dict[str, Any]]
    execution_time: float
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "goal": self.goal,
            "steps": self.steps,
            "execution_time": self.execution_time,
            "error": self.error,
            "data": self.data,
        }


class BrowserAgent:
    """
    Main browser agent that orchestrates all components.
    
    Usage:
        async with BrowserAgent() as agent:
            result = await agent.execute_task(
                "Search for Python tutorials",
                "https://google.com"
            )
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        
        # Components (initialized on start)
        self.browser: Optional[BrowserController] = None
        self.vision_client: Optional[VisionClient] = None
        self.action_executor: Optional[ActionExecutor] = None
        
        # State
        self._initialized = False
        self._current_task: Optional[str] = None
        self._execution_history: List[Dict[str, Any]] = []
    
    async def __aenter__(self):
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
    
    async def initialize(self) -> bool:
        """Initialize all components."""
        if self._initialized:
            return True
        
        try:
            logger.info("Initializing Browser Agent...")
            
            # Ensure directories exist
            self.config.ensure_directories()
            
            # Initialize browser
            self.browser = BrowserController(self.config)
            await self.browser.launch()
            
            # Initialize vision client
            self.vision_client = VisionClient(self.config)
            await self.vision_client._ensure_session()
            
            # Initialize action executor
            self.action_executor = ActionExecutor(
                self.browser,
                self.config,
                self.vision_client
            )
            
            self._initialized = True
            logger.info("✅ Browser Agent initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Browser Agent: {e}")
            await self.cleanup()
            return False
    
    async def cleanup(self):
        """Clean up all resources."""
        logger.info("Cleaning up Browser Agent...")
        
        if self.browser:
            await self.browser.close()
            self.browser = None
        
        if self.vision_client:
            await self.vision_client.close()
            self.vision_client = None
        
        self.action_executor = None
        self._initialized = False
        
        logger.info("✅ Browser Agent cleaned up")
    
    async def execute_task(
        self,
        goal: str,
        start_url: Optional[str] = None,
        max_steps: int = 20
    ) -> TaskResult:
        """
        Execute a task using vision-guided automation.
        
        Args:
            goal: Natural language description of the task
            start_url: Optional starting URL
            max_steps: Maximum number of action steps
            
        Returns:
            TaskResult with success status and execution details
        """
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        self._current_task = goal
        steps = []
        
        try:
            # Navigate to start URL if provided
            if start_url:
                await self.browser.goto(start_url)
                steps.append({
                    "action": "navigate",
                    "url": start_url,
                    "success": True
                })
            
            # Execute vision-guided task
            result = await self._execute_vision_task(goal, max_steps - len(steps))
            steps.extend(result.get("steps", []))
            
            execution_time = time.time() - start_time
            
            return TaskResult(
                success=result.get("success", False),
                goal=goal,
                steps=steps,
                execution_time=execution_time,
                data=result.get("data"),
                error=result.get("error")
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Task execution failed: {e}")
            
            return TaskResult(
                success=False,
                goal=goal,
                steps=steps,
                execution_time=execution_time,
                error=str(e)
            )
    
    async def _execute_vision_task(
        self,
        goal: str,
        max_steps: int
    ) -> Dict[str, Any]:
        """Execute task using vision guidance with step validation and retry."""
        steps = []
        completed = False
        last_actions = []  # Track last few actions for context
        consecutive_failures = 0
        max_consecutive_failures = 3
        max_action_retries = 1  # No per-action retry, just move to next step
        
        for step_num in range(max_steps):
            try:
                # Take screenshot
                screenshot = await self.browser.screenshot()
                
                # Get next action from vision model
                action = await self._get_next_action(goal, screenshot, step_num, last_actions)
                
                if not action:
                    logger.warning("No action returned from vision model")
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error("Too many consecutive failures, stopping")
                        break
                    continue
                
                action_type = action.get("type")
                
                # Prevent repeating the same action after success
                if last_actions:
                    last_successful = [a for a in last_actions if a.get("success")]
                    if last_successful:
                        last_success_type = last_successful[-1].get("type")
                        # Enforce action transitions after success
                        if action_type == last_success_type:
                            logger.warning(f"⚠️ Vision model returned same action '{action_type}' after success, enforcing transition")
                            if action_type == "click":
                                # Force transition to type
                                action_type = "type"
                                action["type"] = "type"
                                # Extract search query from goal
                                import re
                                match = re.search(r'[Ss]earch\s+(?:for\s+)?["\']?([^"\']+)["\']?', goal)
                                if match:
                                    action["text"] = match.group(1).strip()
                                else:
                                    action["text"] = goal
                                logger.info(f"🔄 Forcing transition: click → type '{action.get('text')}'")
                
                # Check for completion
                if action_type == "complete" or action.get("complete", False):
                    # Validate completion with screenshot
                    validation = await self._validate_action_success(
                        action_type, goal, screenshot, action
                    )
                    completed = validation["success"]
                    steps.append({
                        "step": step_num,
                        "action": "complete",
                        "success": completed,
                        "data": action.get("result"),
                        "validation": validation
                    })
                    if completed:
                        logger.info("✅ Task completed and validated successfully")
                    else:
                        logger.warning(f"⚠️ Task marked complete but validation failed: {validation.get('reason')}")
                    break
                
                # Execute the action with retry logic
                action_success = False
                last_result = None
                last_validation = None
                
                for retry in range(max_action_retries):
                    # Note: max_action_retries=1 means no retry, just single attempt
                    
                    # Execute the action
                    result = await self._execute_vision_action(action, screenshot)
                    last_result = result
                    
                    # Wait for page to stabilize
                    await asyncio.sleep(0.8)
                    
                    # Take new screenshot to validate action success
                    post_screenshot = await self.browser.screenshot()
                    
                    # Validate the action succeeded via screenshot analysis
                    validation = await self._validate_action_success(
                        action_type, goal, post_screenshot, action, result
                    )
                    last_validation = validation
                    
                    # Check if action succeeded
                    if validation["success"]:
                        result.success = True
                        action_success = True
                        consecutive_failures = 0
                        logger.info(f"✅ Action '{action_type}' validated: {validation.get('reason', 'OK')}")
                        break
                    else:
                        logger.warning(f"⚠️ Action '{action_type}' validation failed (attempt {retry + 1}/{max_action_retries}): {validation.get('reason', 'Unknown')}")
                
                # Update result based on final validation
                if not action_success:
                    consecutive_failures += 1
                    logger.error(f"❌ Action '{action_type}' failed (consecutive failures: {consecutive_failures}/{max_consecutive_failures})")
                
                # Track last actions for context
                last_actions.append({
                    "type": action_type,
                    "description": action.get("description", ""),
                    "success": action_success,
                    "validated": action_success
                })
                # Keep only last 5 actions
                if len(last_actions) > 5:
                    last_actions.pop(0)
                
                steps.append({
                    "step": step_num,
                    "action": action_type,
                    "success": action_success,
                    "data": last_result.data if last_result else None,
                    "error": last_result.error if last_result else None,
                    "validation": last_validation,
                    "retries": retry + 1 if not action_success else retry
                })
                
                if not action_success:
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error("Too many consecutive failures, stopping")
                        break
                
                # Brief pause between actions
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error in step {step_num}: {e}")
                steps.append({
                    "step": step_num,
                    "action": "error",
                    "success": False,
                    "error": str(e)
                })
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logger.error("Too many consecutive failures, stopping")
                    break
        
        return {
            "success": completed,
            "steps": steps,
            "data": {"total_steps": len(steps)}
        }
    
    async def _validate_action_success(
        self,
        action_type: str,
        goal: str,
        screenshot: bytes,
        action: Dict[str, Any],
        result: Optional[ActionResult] = None
    ) -> Dict[str, Any]:
        """
        Validate that an action succeeded using screenshot analysis.
        
        Returns:
            Dict with 'success' bool and 'reason' string
        """
        try:
            # For complete action, validate task completion
            if action_type == "complete":
                return await self._validate_task_completion(goal, screenshot)
            
            # For click actions, check if element state changed
            if action_type == "click":
                return await self._validate_click_action(goal, screenshot, action, result)
            
            # For type actions, check if text appeared
            if action_type == "type":
                return await self._validate_type_action(goal, screenshot, action)
            
            # For press_enter, check if navigation occurred
            if action_type == "press_enter":
                return await self._validate_enter_action(goal, screenshot)
            
            # For scroll, always success
            if action_type == "scroll_down":
                return {"success": True, "reason": "Scroll action completed"}
            
            # Default: trust the result
            return {"success": True, "reason": "No validation available"}
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {"success": False, "reason": f"Validation error: {e}"}
    
    async def _validate_task_completion(
        self,
        goal: str,
        screenshot: bytes
    ) -> Dict[str, Any]:
        """Validate that the overall task is complete."""
        try:
            # Check URL for search results indicators
            current_url = self.browser.page.url if self.browser.page else ""
            logger.info(f"📍 Current URL: {current_url}")
            
            # For search tasks, check if we're on search results page
            if "search" in goal.lower():
                # Check URL for search parameters
                if "search?q=" in current_url or "&q=" in current_url:
                    # Check for search result elements
                    page = self.browser.page
                    if page:
                        # Look for common search result selectors
                        selectors = ["div.g", "[data-ved]", "h3", ".search-result"]
                        for selector in selectors:
                            try:
                                elements = await page.query_selector_all(selector)
                                if len(elements) > 0:
                                    logger.info(f"✅ Found {len(elements)} search results with {selector}")
                                    return {
                                        "success": True,
                                        "reason": f"Found {len(elements)} search results on page"
                                    }
                            except:
                                continue
                        
                        # Check page title
                        title = await page.title()
                        search_term = goal.lower().replace("search for", "").strip()
                        if search_term and search_term in title.lower():
                            return {
                                "success": True,
                                "reason": f"Search term found in page title: {title}"
                            }
                    
                    return {
                        "success": True,
                        "reason": "On search results page (URL validated)"
                    }
                
                # Not on search results page
                return {
                    "success": False,
                    "reason": "Not on search results page - URL doesn't contain search parameters"
                }
            
            # For non-search tasks, use vision validation
            validation_prompt = f"""Look at this screenshot and determine if this task is complete:

Task: {goal}

Check:
1. Is the task goal achieved?
2. Are there any error messages visible?
3. Is the expected result visible on the page?

Return JSON:
{{
    "success": true/false,
    "reason": "explanation"
}}"""
            
            response = await self.vision_client.chat_with_image(validation_prompt, screenshot)
            content = response.content
            
            # Parse JSON
            import json
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            
            return {"success": True, "reason": "Could not validate, assuming success"}
            
        except Exception as e:
            logger.error(f"Task completion validation error: {e}")
            return {"success": False, "reason": f"Validation error: {e}"}
    
    async def _validate_click_action(
        self,
        goal: str,
        screenshot: bytes,
        action: Dict[str, Any],
        result: Optional[ActionResult]
    ) -> Dict[str, Any]:
        """Validate that a click action succeeded."""
        try:
            page = self.browser.page
            if not page:
                return {"success": False, "reason": "No page available"}
            
            # Determine if this was a click on a search/input field based on goal
            is_search_task = "search" in goal.lower()
            action_desc = action.get("description", "").lower()
            is_input_click = any(keyword in action_desc for keyword in
                ["search", "input", "field", "text", "box", "type", "enter"])
            
            # Check if an input field is now focused (for search field clicks)
            focused_element = await page.evaluate("""() => {
                const el = document.activeElement;
                if (el) {
                    return {
                        tag: el.tagName,
                        type: el.type || '',
                        id: el.id || '',
                        name: el.name || '',
                        placeholder: el.placeholder || '',
                        isContentEditable: el.isContentEditable
                    };
                }
                return null;
            }""")
            
            logger.info(f"🔍 Focused element after click: {focused_element}")
            
            if focused_element:
                tag = focused_element.get("tag", "").lower()
                el_type = focused_element.get("type", "").lower()
                is_editable = focused_element.get("isContentEditable", False)
                
                # Check if input/textarea is focused (must have actual input tag)
                if tag in ["input", "textarea"]:
                    logger.info(f"✅ Input field focused: {focused_element}")
                    return {
                        "success": True,
                        "reason": f"Input field is now focused: {focused_element.get('placeholder', focused_element.get('id', 'unknown'))}"
                    }
                
                # Check for contenteditable elements (but not body)
                if is_editable and tag not in ["body", "html"]:
                    logger.info(f"✅ Contenteditable element focused: {focused_element}")
                    return {
                        "success": True,
                        "reason": f"Contenteditable element focused"
                    }
            
            # For search tasks, if we clicked on an input field but it's not focused, FAIL
            if is_search_task and is_input_click:
                logger.warning(f"⚠️ Click on input field failed - no input focused. Body element: {focused_element.get('tag') if focused_element else 'none'}")
                return {
                    "success": False,
                    "reason": f"Click on input field failed - no input focused (active: {focused_element.get('tag', 'none') if focused_element else 'none'})"
                }
            
            # Check URL change (for link clicks)
            current_url = page.url
            if result and result.data:
                prev_url = result.data.get("url", "")
                if prev_url and current_url != prev_url:
                    return {
                        "success": True,
                        "reason": f"URL changed from {prev_url} to {current_url}"
                    }
            
            # For non-search tasks or non-input clicks, check if click coordinates were valid
            if result and result.success:
                # Use vision to verify click success for non-input clicks
                return await self._validate_click_via_vision(goal, screenshot, action)
            
            return {"success": False, "reason": "Could not verify click success"}
            
        except Exception as e:
            logger.error(f"Click validation error: {e}")
            return {"success": False, "reason": f"Validation error: {e}"}
    
    async def _validate_click_via_vision(
        self,
        goal: str,
        screenshot: bytes,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use vision model to validate click success."""
        try:
            prompt = f"""Look at this screenshot and determine if the click action was successful.

Action: {action.get('description', 'Click')}                                    
Goal: {goal}

Check:
1. Is there a visible cursor or focus indicator on an input field?
2. Are there any error messages visible?
3. Does the page state look correct for the action?

Return JSON:
{{
    "success": true/false,
    "reason": "explanation"
}}"""
            
            response = await self.vision_client.chat_with_image(prompt, screenshot)
            content = response.content
            
            # Parse JSON
            import json
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(content[json_start:json_end])
                return result
            
            return {"success": True, "reason": "Could not validate via vision, assuming success"}
            
        except Exception as e:
            logger.error(f"Vision validation error: {e}")
            return {"success": True, "reason": f"Vision validation failed: {e}, assuming success"}
    
    async def _validate_type_action(
        self,
        goal: str,
        screenshot: bytes,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate that text was typed successfully."""
        try:
            page = self.browser.page
            if not page:
                return {"success": False, "reason": "No page available"}
            
            typed_text = action.get("text", "")
            
            if not typed_text:
                logger.warning("⚠️ No text provided in type action")
                return {"success": False, "reason": "No text provided to type"}
            
            # Check if the typed text is in the focused input
            input_info = await page.evaluate("""() => {
                const el = document.activeElement;
                if (el) {
                    return {
                        tag: el.tagName,
                        type: el.type || '',
                        value: el.value || '',
                        textContent: el.textContent || ''
                    };
                }
                return null;
            }""")
        
            
            if input_info:
                tag = input_info.get("tag", "").lower()
                input_value = input_info.get("value", "")
                text_content = input_info.get("textContent", "")
                
                # Check input/textarea value
                if tag in ["input", "textarea"]:
                    if typed_text.lower() in input_value.lower():
                        logger.info(f"✅ Text verified in input: '{input_value}'")
                        return {
                            "success": True,
                            "reason": f"Text '{typed_text}' found in input field"
                        }
                    else:
                        logger.warning(f"⚠️ Text not found in input. Expected '{typed_text}', got '{input_value}'")
                        return {
                            "success": False,
                            "reason": f"Text '{typed_text}' not found in input field (has '{input_value}')"
                        }
                
                # Check contenteditable elements
                if text_content and typed_text.lower() in text_content.lower():
                    logger.info(f"✅ Text verified in contenteditable: '{text_content}'")
                    return {
                        "success": True,
                        "reason": f"Text '{typed_text}' found in content element"
                    }
            
            # If no input is focused, the previous click might have failed
            logger.warning("⚠️ No input field focused after type action - click may have failed")
            return {
                "success": False,
                "reason": "No input field focused - text could not be typed"
            }
            
        except Exception as e:
            logger.error(f"Type validation error: {e}")
            return {"success": False, "reason": f"Validation error: {e}"}
    
    async def _validate_enter_action(
        self,
        goal: str,
        screenshot: bytes
    ) -> Dict[str, Any]:
        """Validate that pressing Enter triggered the expected action."""
        try:
            page = self.browser.page
            if not page:
                return {"success": False, "reason": "No page available"}
            
            # Wait a moment for navigation
            await asyncio.sleep(0.5)
            
            current_url = page.url
            
            # For search tasks, check if we navigated to search results
            if "search" in goal.lower():
                if "search?q=" in current_url or "&q=" in current_url:
                    logger.info(f"✅ Enter pressed, now on search results: {current_url}")
                    return {
                        "success": True,
                        "reason": "Successfully navigated to search results"
                    }
                
                # Check for search results on page
                try:
                    elements = await page.query_selector_all("div.g, [data-ved], h3")
                    if len(elements) > 0:
                        return {
                            "success": True,
                            "reason": f"Found {len(elements)} search result elements"
                        }
                except:
                    pass
                
                return {
                    "success": False,
                    "reason": "Enter pressed but not on search results page"
                }
            
            # For non-search tasks, check if any navigation occurred
            return {"success": True, "reason": "Enter key pressed"}
            
        except Exception as e:
            logger.error(f"Enter validation error: {e}")
            return {"success": False, "reason": f"Validation error: {e}"}
    
    async def _get_next_action(
        self,
        goal: str,
        screenshot: bytes,
        step_num: int,
        last_actions: Optional[List[Dict]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get next action from vision model."""
        last_actions = last_actions or []
        
        # Build context from recent actions
        action_history = ""
        if last_actions:
            action_history = "\nRecent actions taken:\n"
            for i, action in enumerate(last_actions[-3:], 1):
                action_history += f"  {i}. {action.get('type', 'unknown')}: {action.get('description', '')} ({'success' if action.get('success') else 'failed'})\n"
        
        prompt = f"""
You are a precise UI automation assistant.
        
Task: {goal}

Current step: {step_num + 1}
{action_history}
Analyze the screenshot and determine the next action to accomplish this task.

Available actions:
- click: Click at coordinates (provide x, y)
- type: Type text (provide text) - use when input field is already focused
- press_enter: Press Enter key
- scroll_down: Scroll down the page
- complete: Task is finished (provide result summary)

Return as JSON:
{{
    "type": "click|type|press_enter|scroll_down|complete",
    "x": coordinate_x (for click),
    "y": coordinate_y (for click),
    "text": "text to type" (for type),
    "description": "What this action does",
    "complete": false,
    "result": "summary if complete"
}}

Screenshot dimensions: 2560x1440 (width x height)

CRITICAL COORDINATE RULES:
1. Look at the screenshot CAREFULLY and identify the EXACT pixel coordinates of elements
2. The search/input field is usually in the CENTER of the page horizontally 
3. IMPORTANT: Google search bar is (x=1280, y=400)

CRITICAL ACTION RULES - STRICT SEQUENCE:
1. NEVER repeat "click" after a successful click - move to NEXT step!
2. After successful "click" on input field → NEXT action MUST be "type"
3. After "type" → NEXT action MUST be "press_enter"
4. After "press_enter" → Check if task is complete

MANDATORY ACTION TRANSITIONS:
- click (success) → type (MANDATORY - do not click again!)
- type → press_enter (MANDATORY)
- press_enter → complete (if search results appear)

IMPORTANT: Look at recent actions above!
- If last action was "click" with success=true, you MUST return "type" next
- If you see "click: success" in recent actions, DO NOT click again - TYPE instead!

For "{goal}" on Google:
- Step 1: Click on search field (x=1280, y=400)
- Step 2: Type the search query (extract from task goal)
- Step 3: Press Enter
- Step 4: Complete with result
"""
        
        try:
            response = await self.vision_client.chat_with_image(prompt, screenshot)
            
            # Parse JSON from response
            import json
            content = response.content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                action = json.loads(content[json_start:json_end])
                logger.info(f"Vision action: {action.get('type')} - {action.get('description', '')}")
                return action
            
        except Exception as e:
            logger.error(f"Failed to get vision action: {e}")
        
        return None
    
    async def _execute_vision_action(
        self,
        action: Dict[str, Any],
        screenshot: bytes
    ) -> ActionResult:
        """Execute an action from vision model."""
        action_type = action.get("type")
        
        if action_type == "click":
            x = action.get("x", 0)
            y = action.get("y", 0)
            return await self.action_executor.execute(
                ActionType.CLICK,
                target=(x, y),
                screenshot=screenshot
            )
        
        elif action_type == "type":
            text = action.get("text", "")
            return await self.action_executor.execute(
                ActionType.TYPE_TEXT,
                value=text,
                screenshot=screenshot
            )
        
        elif action_type == "press_enter":
            return await self.action_executor.execute(
                ActionType.PRESS_KEY,
                value="Enter",
                screenshot=screenshot
            )
        
        elif action_type == "scroll_down":
            return await self.action_executor.execute(
                ActionType.SCROLL_DOWN,
                screenshot=screenshot
            )
        
        else:
            return ActionResult(
                success=False,
                action_type=ActionType.WAIT,
                error=f"Unknown action type: {action_type}"
            )
    
    # ==================== Convenience Methods ====================
    
    async def navigate(self, url: str) -> ActionResult:
        """Navigate to URL."""
        return await self.action_executor.execute(ActionType.NAVIGATE, value=url)
    
    async def click(self, selector_or_coords, options: Optional[Dict] = None) -> ActionResult:
        """Click on element or coordinates."""
        return await self.action_executor.execute(
            ActionType.CLICK,
            target=selector_or_coords,
            options=options
        )
    
    async def type_text(
        self,
        text: str,
        selector: Optional[str] = None,
        clear: bool = False
    ) -> ActionResult:
        """Type text into element."""
        return await self.action_executor.execute(
            ActionType.TYPE_TEXT,
            target=selector,
            value=text,
            options={"clear": clear}
        )
    
    async def press_key(self, key: str) -> ActionResult:
        """Press a keyboard key."""
        return await self.action_executor.execute(ActionType.PRESS_KEY, value=key)
    
    async def scroll_down(self, amount: int = 500) -> ActionResult:
        """Scroll down."""
        return await self.action_executor.execute(ActionType.SCROLL_DOWN, value=amount)
    
    async def scroll_up(self, amount: int = 500) -> ActionResult:
        """Scroll up."""
        return await self.action_executor.execute(ActionType.SCROLL_UP, value=amount)
    
    async def take_screenshot(self, full_page: bool = False) -> bytes:
        """Take screenshot."""
        result = await self.action_executor.execute(
            ActionType.TAKE_SCREENSHOT,
            options={"full_page": full_page}
        )
        return result.screenshot or b""
    
    async def extract_text(self, selector: Optional[str] = None) -> str:
        """Extract text from page or element."""
        result = await self.action_executor.execute(
            ActionType.EXTRACT_TEXT,
            target=selector
        )
        return result.data.get("text", "") if result.success else ""
    
    async def wait_for_element(self, selector: str, timeout: int = 5000) -> ActionResult:
        """Wait for element to appear."""
        return await self.action_executor.execute(
            ActionType.WAIT_FOR_ELEMENT,
            target=selector,
            options={"timeout": timeout}
        )
    
    async def get_page_info(self) -> Dict[str, Any]:
        """Get current page information."""
        result = await self.action_executor.execute(ActionType.GET_PAGE_INFO)
        return result.data if result.success else {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "initialized": self._initialized,
            "current_task": self._current_task,
            "action_stats": self.action_executor.get_stats() if self.action_executor else {},
            "vision_stats": self.vision_client.get_stats() if self.vision_client else {},
        }


# Convenience function
async def create_agent(config: Optional[Config] = None) -> BrowserAgent:
    """Create and initialize a browser agent."""
    agent = BrowserAgent(config)
    await agent.initialize()
    return agent

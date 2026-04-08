"""
Browser Agent - Main agent class combining all components.

This module provides the main BrowserAgent class that orchestrates:
- Browser controller
- LLM/Vision client
- Action executor
- State management
"""

import asyncio
import json
import logging
import re
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .config import Config, get_config
from .browser import BrowserController
from .llm import VisionClient
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

    def __init__(
        self,
        config: Optional[Config] = None,
        credential_vault=None,
        audit_log=None,
        tenant_id: Optional[str] = None,
    ):
        self.config = config or get_config()

        # Components (initialized on start)
        self.browser: Optional[BrowserController] = None
        self.vision_client: Optional[VisionClient] = None
        self.action_executor: Optional[ActionExecutor] = None

        # Security
        self.credential_vault = credential_vault  # Optional CredentialVault
        self.audit_log = audit_log  # Optional AuditLog
        self.tenant_id = tenant_id or "default"

        # State
        self._initialized = False
        self._current_task: Optional[str] = None
        self._current_task_id: Optional[str] = None
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

            # Create initial page
            await self.browser.new_page()

            # Initialize vision client
            self.vision_client = VisionClient(self.config)
            await self.vision_client._ensure_session()

            # Initialize action executor
            self.action_executor = ActionExecutor(self.browser, self.config, self.vision_client)

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
        max_steps: int = 20,
        credential_aliases: Optional[Dict[str, str]] = None,
    ) -> TaskResult:
        """
        Execute a task using vision-guided automation.

        Args:
            goal: Natural language description of the task
            start_url: Optional starting URL
            max_steps: Maximum number of action steps
            credential_aliases: Dict mapping field names to vault aliases

        Returns:
            TaskResult with success status and execution details
        """
        if not self._initialized:
            await self.initialize()

        # Resolve credential placeholders in goal and URL
        resolved_goal = goal
        resolved_url = start_url
        if self.credential_vault and credential_aliases:
            try:
                resolved_goal = await self._resolve_credentials_in_text(goal, credential_aliases)
                if start_url:
                    resolved_url = await self._resolve_credentials_in_text(start_url, credential_aliases)
                logger.info("Resolved %d credential alias(es)", len(credential_aliases))
            except Exception as e:
                logger.warning("Credential resolution failed: %s", e)

        start_time = time.time()
        self._current_task = resolved_goal

        # Generate task ID
        import uuid

        self._current_task_id = str(uuid.uuid4())

        # Audit: task created
        if self.audit_log:
            await self.audit_log.record(
                event_type="task.created",
                tenant_id=self.tenant_id,
                task_id=self._current_task_id,
                parameters={"goal": goal, "start_url": start_url},
            )

        steps = []

        try:
            # Navigate to start URL if provided
            if resolved_url:
                await self.browser.goto(resolved_url)
                steps.append({"action": "navigate", "url": resolved_url, "success": True})

                if self.audit_log:
                    await self.audit_log.record(
                        event_type="action.executed",
                        tenant_id=self.tenant_id,
                        task_id=self._current_task_id,
                        action_type="navigate",
                        target_url=resolved_url,
                        outcome="success",
                    )

            # Execute vision-guided task
            result = await self._execute_vision_task(resolved_goal, max_steps - len(steps))
            steps.extend(result.get("steps", []))

            execution_time = time.time() - start_time

            # Audit: task completed/failed
            if self.audit_log:
                success = result.get("success", False)
                await self.audit_log.record(
                    event_type="task.completed" if success else "task.failed",
                    tenant_id=self.tenant_id,
                    task_id=self._current_task_id,
                    outcome="success" if success else "failure",
                    error_message=result.get("error"),
                    parameters={"execution_time": execution_time, "steps": len(steps)},
                )

            return TaskResult(
                success=result.get("success", False),
                goal=goal,
                steps=steps,
                execution_time=execution_time,
                data=result.get("data"),
                error=result.get("error"),
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Task execution failed: {e}")

            # Audit: task failed
            if self.audit_log:
                await self.audit_log.record(
                    event_type="task.failed",
                    tenant_id=self.tenant_id,
                    task_id=self._current_task_id,
                    outcome="failure",
                    error_message=str(e),
                )

            return TaskResult(success=False, goal=goal, steps=steps, execution_time=execution_time, error=str(e))

    async def _execute_vision_task(self, goal: str, max_steps: int) -> Dict[str, Any]:
        """Execute task using vision guidance with step validation and retry."""
        steps = []
        completed = False
        last_actions = []  # Track last few actions for context
        filled_fields = {}  # Track filled fields: {label: value}
        consecutive_failures = 0
        max_consecutive_failures = 3
        max_action_retries = 1  # No per-action retry, just move to next step

        for step_num in range(max_steps):
            try:
                # Take screenshot
                screenshot = await self.browser.screenshot()

                # Get next action from vision model
                action = await self._get_next_action(goal, screenshot, step_num, last_actions, filled_fields)
                # Build context about already-filled fields
                if filled_fields:
                    filled_ctx = "Already filled fields (DO NOT fill these again):\n"
                    for fl, fv in filled_fields.items():
                        filled_ctx += f"  - {fl}: {fv}\n"
                    last_actions.append({"type": "info", "description": filled_ctx, "success": True})

                if not action:
                    logger.warning("No action returned from vision model")
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error("Too many consecutive failures, stopping")
                        break
                    continue

                action_type = action.get("type")

                # Break click loops: if 3+ consecutive clicks at same coordinates, force DOM fallback
                if action_type in ("click", "fill_field") and len(last_actions) >= 3:
                    recent_clicks = [a for a in last_actions[-5:] if a.get("type") in ("click", "fill_field")]
                    if len(recent_clicks) >= 3:
                        recent_coords = [(a.get("x", -1), a.get("y", -1)) for a in recent_clicks[-3:]]
                        # Check if all 3 clicks are within 20px of each other
                        if all(abs(recent_coords[i][0] - recent_coords[0][0]) < 20 and 
                               abs(recent_coords[i][1] - recent_coords[0][1]) < 20 
                               for i in range(1, len(recent_coords))):
                            logger.info(f"🔄 Breaking click loop at ({recent_coords[0][0]}, {recent_coords[0][1]}) - forcing DOM fallback")
                            # Force a scroll or different action to break the loop
                            action_type = "scroll_down"
                            action["type"] = "scroll_down"

                # Break scroll loops: if 3+ consecutive scrolls, force a different action
                if action_type == "scroll_down" and len(last_actions) >= 3:
                    recent_types = [a.get("type") for a in last_actions[-3:]]
                    if recent_types == ["scroll_down", "scroll_down", "scroll_down"]:
                        logger.info("🔄 Breaking scroll loop - forcing click action")
                        page = self.browser.page
                        if page:
                            # Scroll back to top first to find buttons
                            await page.evaluate("window.scrollTo(0, 0)")
                            await asyncio.sleep(0.3)
                            # If we're on a different page than expected, go back
                            current_url = page.url
                            if "cart" in current_url or "checkout" in current_url:
                                logger.info(f"🔄 On {current_url}, going back to find products")
                                await page.go_back()
                                await asyncio.sleep(0.5)
                            # Use goal text to find relevant buttons, not hardcoded keywords
                            _loop_js = "(goalText) => {" + """
                                const goalWords = goalText.toLowerCase().split(/[^a-z0-9]+/).filter(w => w.length > 2);
                                const selectors = 'button, [role="button"], [onclick], .accordion-header, .tab, .toggle, [data-testid]';
                                const candidates = Array.from(document.querySelectorAll(selectors));
                                let bestMatch = null;
                                let bestScore = 0;
                                for (const el of candidates) {
                                    const text = (el.textContent || '').trim().toLowerCase();
                                    const matchCount = goalWords.filter(w => text.includes(w)).length;
                                    if (matchCount > bestScore && el.getBoundingClientRect().width > 0) {
                                        const box = el.getBoundingClientRect();
                                        bestScore = matchCount;
                                        bestMatch = {x: box.x + box.width/2, y: box.y + box.height/2, found: true, text: text, score: matchCount};
                                    }
                                }
                                return bestMatch || {found: false};
                            }"""
                            btn_data = await page.evaluate(_loop_js, goal)
                            if btn_data and btn_data.get("found"):
                                # Scroll element into view if off-screen
                                by = btn_data["y"]
                                if by < 50 or by > self.config.browser.viewport_height - 50:
                                    logger.info(f"🔄 Element at y={by:.0f} off-screen, scrolling into view")
                                    await page.evaluate(
                                        f"window.scrollBy(0, {int(by - self.config.browser.viewport_height / 2)})"
                                    )
                                    await asyncio.sleep(0.3)
                                    btn_data2 = await page.evaluate(_loop_js, goal)
                                    if btn_data2 and btn_data2.get("found"):
                                        btn_data = btn_data2
                            if btn_data and btn_data.get("found"):
                                logger.info(
                                    f"Scroll loop: found '{btn_data.get('text', '')}' (score={btn_data.get('score', 0)}) at ({btn_data['x']:.0f}, {btn_data['y']:.0f})"
                                )
                                action_type = "click"
                                action = {
                                    "type": "click",
                                    "x": btn_data["x"],
                                    "y": btn_data["y"],
                                    "description": f"Click {btn_data.get('text', 'button')} to break scroll loop",
                                }
                                logger.info(
                                    f"🔄 Found button via DOM: {btn_data.get('text')} at ({btn_data['x']:.0f}, {btn_data['y']:.0f})"
                                )
                            else:
                                # No button found, force complete
                                action_type = "complete"
                                action = {
                                    "type": "complete",
                                    "complete": True,
                                    "result": "No more actions found after scrolling",
                                }
                                logger.info("🔄 No actionable buttons found, forcing complete")

                # Prevent repeating the same action after success
                if last_actions:
                    last_successful = [a for a in last_actions if a.get("success")]
                    if last_successful:
                        last_success_type = last_successful[-1].get("type")
                        # After successful press_enter, force complete (task done)
                        if last_success_type == "press_enter" and action_type != "complete":
                            action_type = "complete"
                            action["type"] = "complete"
                            action["complete"] = True
                            action["result"] = "Search completed successfully"
                            logger.info("🔄 Forcing transition: any after press_enter → complete")
                        # Enforce action transitions for click-type sequences
                        elif action_type == last_success_type and action_type in ("click", "type"):
                            is_search = "search" in goal.lower()[:50]  # Only for search tasks
                            if action_type == "click" and is_search:
                                action_type = "type"
                                action["type"] = "type"
                                import re

                                match = re.search(r'[Ss]earch\s+(?:for\s+)?["\']?([^"\']+)["\']?', goal)
                                if match:
                                    action["text"] = match.group(1).strip()
                                else:
                                    action["text"] = goal
                                logger.info(f"🔄 Forcing transition: click → type '{action.get('text')}'")
                            elif action_type == "type" and is_search:
                                action_type = "press_enter"
                                action["type"] = "press_enter"
                                logger.info("🔄 Forcing transition: type → press_enter")

                # Skip already-filled fields (only if same value)
                if action_type == "fill_field":
                    fl = action.get("field_label", "")
                    fv = action.get("field_value", "") or action.get("text", "")
                    fl_lower = fl.lower() if fl else ""
                    if fl_lower and fl_lower in {k.lower() for k in filled_fields}:
                        # Allow re-fill if the value is different
                        existing = filled_fields.get(next(k for k in filled_fields if k.lower() == fl_lower), "")
                        if existing and fv and existing.lower() == fv.lower():
                            logger.info(f"⏭️ Skipping already-filled field: {fl} (same value)")
                            steps.append(
                                {"step": step_num, "action": "skip", "success": True, "data": f"Already filled: {fl}"}
                            )
                            consecutive_failures = 0
                            continue
                        else:
                            logger.info(f"🔄 Re-filling field {fl} with new value: {fv}")
                            # Update the tracked value
                            for k in list(filled_fields.keys()):
                                if k.lower() == fl_lower:
                                    filled_fields[k] = fv
                                    break

                # Check for completion
                if action_type == "complete" or action.get("complete", False):
                    # Validate completion with screenshot
                    validation = await self._validate_action_success(action_type, goal, screenshot, action)
                    completed = validation["success"]
                    steps.append(
                        {
                            "step": step_num,
                            "action": "complete",
                            "success": completed,
                            "data": action.get("result"),
                            "validation": validation,
                        }
                    )
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
                    validation = await self._validate_action_success(action_type, goal, post_screenshot, action, result)
                    last_validation = validation

                    # Check if action succeeded
                    if validation["success"]:
                        result.success = True
                        action_success = True
                        consecutive_failures = 0
                        logger.info(f"✅ Action '{action_type}' validated: {validation.get('reason', 'OK')}")
                        break
                    else:
                        logger.warning(
                            f"⚠️ Action '{action_type}' validation failed (attempt {retry + 1}/{max_action_retries}): {validation.get('reason', 'Unknown')}"
                        )

                # Update result based on final validation
                if not action_success:
                    consecutive_failures += 1
                    logger.error(
                        f"❌ Action '{action_type}' failed (consecutive failures: {consecutive_failures}/{max_consecutive_failures})"
                    )

                # Track filled fields
                if action_type == "fill_field" and action_success:
                    fl = action.get("field_label", "")
                    fv = action.get("field_value", action.get("text", ""))
                    if fl:
                        filled_fields[fl] = fv
                        logger.info(f"Tracked: {fl} = {fv}")

                # Track last actions for context
                last_actions.append(
                    {
                        "type": action_type,
                        "description": action.get("description", ""),
                        "success": action_success,
                        "validated": action_success,
                    }
                )
                # Keep only last 5 actions
                if len(last_actions) > 5:
                    last_actions.pop(0)

                steps.append(
                    {
                        "step": step_num,
                        "action": action_type,
                        "success": action_success,
                        "data": last_result.data if last_result else None,
                        "error": last_result.error if last_result else None,
                        "validation": last_validation,
                        "retries": retry + 1 if not action_success else retry,
                    }
                )

                if not action_success:
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error("Too many consecutive failures, stopping")
                        break

                # Brief pause between actions
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error in step {step_num}: {e}")
                steps.append({"step": step_num, "action": "error", "success": False, "error": str(e)})
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logger.error("Too many consecutive failures, stopping")
                    break

        return {"success": completed, "steps": steps, "data": {"total_steps": len(steps)}}

    async def _validate_action_success(
        self,
        action_type: str,
        goal: str,
        screenshot: bytes,
        action: Dict[str, Any],
        result: Optional[ActionResult] = None,
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

            # For fill_field, check if text was entered in the field
            if action_type == "fill_field":
                field_value = action.get("field_value", action.get("text", ""))
                page = self.browser.page
                if page and field_value:
                    value = await page.evaluate("() => document.activeElement?.value || String()")
                    if field_value in value:
                        return {"success": True, "reason": f"Field filled with '{field_value}'"}
                # Fall through to screenshot validation
                return {"success": True, "reason": "Field action completed"}

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

    async def _validate_task_completion(self, goal: str, screenshot: bytes) -> Dict[str, Any]:
        """Validate that the overall task is complete."""
        try:
            # Check URL for search results indicators
            current_url = self.browser.page.url if self.browser.page else ""
            logger.info(f"📍 Current URL: {current_url}")

            # For search tasks, check if we're on search results page
            if "search" in goal.lower():
                page = self.browser.page
                # First check for search result elements (works for client-side search too)
                if page:
                    selectors = [
                        "div.g",
                        "[data-ved]",
                        ".search-result",
                        ".result",
                        ".article",
                        ".post",
                        "[class*=result]",
                        "[class*=article]",
                    ]
                    for selector in selectors:
                        try:
                            elements = await page.query_selector_all(selector)
                            if len(elements) > 0:
                                logger.info(f"✅ Found {len(elements)} search results with {selector}")
                                return {"success": True, "reason": f"Found {len(elements)} search results on page"}
                        except Exception:
                            continue

                # Then check URL for search parameters
                if "search?q=" in current_url or "&q=" in current_url:
                    return {"success": True, "reason": "On search results page (URL validated)"}

                # Not on search results page
                return {"success": False, "reason": "Not on search results page - no results found"}

            # For non-search tasks, check DOM for success indicators first, then use vision
            page = self.browser.page
            if page:
                try:
                    dom_check = await page.evaluate("""() => {
                        // Check for common success indicators
                        const successSelectors = ['.success', '.alert-success', '.login-success', '.message.success', '[class*=success]', '#success'];
                        for (const sel of successSelectors) {
                            const el = document.querySelector(sel);
                            if (el && el.offsetWidth > 0) return {found: true, text: el.textContent.trim().substring(0, 200)};
                        }
                        // Check URL for dashboard/redirect
                        if (location.pathname.includes('dashboard') || location.pathname.includes('welcome') || location.pathname.includes('home')) return {found: true, text: 'Redirected to ' + location.pathname};
                        return {found: false};
                    }""")
                    if dom_check and dom_check.get("found"):
                        logger.info(f"✅ DOM completion check: {dom_check.get('text')}")
                        return {"success": True, "reason": dom_check.get("text", "Success indicator found")}
                except Exception as e:
                    logger.debug(f"DOM completion check failed: {e}")

            # Fall back to vision validation
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

            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])

            return {"success": True, "reason": "Could not validate, assuming success"}

        except Exception as e:
            logger.error(f"Task completion validation error: {e}")
            return {"success": False, "reason": f"Validation error: {e}"}

    async def _validate_click_action(
        self, goal: str, screenshot: bytes, action: Dict[str, Any], result: Optional[ActionResult]
    ) -> Dict[str, Any]:
        """Validate that a click action succeeded."""
        try:
            page = self.browser.page
            if not page:
                return {"success": False, "reason": "No page available"}

            # Determine if this was a click on a search/input field based on goal
            is_search_task = "search" in goal.lower()
            action_desc = action.get("description", "").lower()
            is_input_click = any(
                keyword in action_desc for keyword in ["search", "input", "field", "text", "box", "type", "enter"]
            )

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
                focused_element.get("type", "").lower()
                is_editable = focused_element.get("isContentEditable", False)

                # Check if input/textarea is focused (must have actual input tag)
                if tag in ["input", "textarea"]:
                    logger.info(f"✅ Input field focused: {focused_element}")
                    return {
                        "success": True,
                        "reason": f"Input field is now focused: {focused_element.get('placeholder', focused_element.get('id', 'unknown'))}",
                    }

                # Check for contenteditable elements (but not body)
                if is_editable and tag not in ["body", "html"]:
                    logger.info(f"✅ Contenteditable element focused: {focused_element}")
                    return {"success": True, "reason": "Contenteditable element focused"}

            # For search tasks, if we clicked on an input field but it's not focused
            if is_search_task and is_input_click:
                focused_tag = focused_element.get("tag", "") if focused_element else ""
                if focused_tag == "BUTTON":
                    # Clicked near the input but hit the search button instead - still progress
                    logger.info("Search button focused instead of input, accepting")
                    return {"success": True, "reason": "Search button or nearby element focused"}
                logger.warning(
                    f"⚠️ Click on input field failed - no input focused. Body element: {focused_element.get('tag') if focused_element else 'none'}"
                )
                return {
                    "success": False,
                    "reason": f"Click on input field failed - no input focused (active: {focused_element.get('tag', 'none') if focused_element else 'none'})",
                }

            # Check URL change (for link clicks)
            current_url = page.url
            if result and result.data:
                prev_url = result.data.get("url", "")
                if prev_url and current_url != prev_url:
                    return {"success": True, "reason": f"URL changed from {prev_url} to {current_url}"}

            # Check if a button was clicked (not an input field click)
            goal_lower = goal.lower()
            is_button_click = any(
                kw in action_desc
                for kw in [
                    "next",
                    "previous",
                    "submit",
                    "button",
                    "click",
                    "load more",
                    "tab",
                    "modal",
                    "toggle",
                    "expand",
                    "open",
                    "close",
                    "confirm",
                    "agree",
                    "check",
                ]
            ) or any(
                kw in goal_lower
                for kw in ["click the", "load more", "pagination", "next", "navigate", "submit", "button"]
            )

            if is_button_click:
                # For button clicks, trust the action if coordinates were valid
                if result and result.success:
                    return {"success": True, "reason": "Button click completed"}
                return {"success": False, "reason": "Button click failed"}

            # For non-search tasks or non-input clicks, check if click coordinates were valid
            if result and result.success:
                return await self._validate_click_via_vision(goal, screenshot, action)

            return {"success": False, "reason": "Could not verify click success"}

        except Exception as e:
            logger.error(f"Click validation error: {e}")
            return {"success": False, "reason": f"Validation error: {e}"}

    async def _validate_click_via_vision(self, goal: str, screenshot: bytes, action: Dict[str, Any]) -> Dict[str, Any]:
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

            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(content[json_start:json_end])
                return result

            return {"success": True, "reason": "Could not validate via vision, assuming success"}

        except Exception as e:
            logger.error(f"Vision validation error: {e}")
            return {"success": True, "reason": f"Vision validation failed: {e}, assuming success"}

    async def _validate_type_action(self, goal: str, screenshot: bytes, action: Dict[str, Any]) -> Dict[str, Any]:
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
                        return {"success": True, "reason": f"Text '{typed_text}' found in input field"}
                    else:
                        logger.warning(f"⚠️ Text not found in input. Expected '{typed_text}', got '{input_value}'")
                        return {
                            "success": False,
                            "reason": f"Text '{typed_text}' not found in input field (has '{input_value}')",
                        }

                # Check contenteditable elements
                if text_content and typed_text.lower() in text_content.lower():
                    logger.info(f"✅ Text verified in contenteditable: '{text_content}'")
                    return {"success": True, "reason": f"Text '{typed_text}' found in content element"}

            # If no input is focused, the previous click might have failed
            logger.warning("⚠️ No input field focused after type action - click may have failed")
            return {"success": False, "reason": "No input field focused - text could not be typed"}

        except Exception as e:
            logger.error(f"Type validation error: {e}")
            return {"success": False, "reason": f"Validation error: {e}"}

    async def _validate_enter_action(self, goal: str, screenshot: bytes) -> Dict[str, Any]:
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
                    return {"success": True, "reason": "Successfully navigated to search results"}

                # Check for search results on page
                try:
                    elements = await page.query_selector_all("div.g, [data-ved], h3")
                    if len(elements) > 0:
                        return {"success": True, "reason": f"Found {len(elements)} search result elements"}
                except Exception:
                    pass

                return {"success": False, "reason": "Enter pressed but not on search results page"}

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
        last_actions: Optional[List[Dict]] = None,
        filled_fields: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get next action from vision model."""
        filled_fields = filled_fields or {}
        last_actions = last_actions or []

        # Build context from recent actions
        action_history = ""
        if last_actions:
            action_history = "\n\n## History\n"
            for i, action in enumerate(last_actions[-5:], 1):
                status = "✓" if action.get("success") else "✗"
                desc = action.get("description", action.get("field_label", ""))
                atype = action.get("type", "unknown")
                action_history += f"{i}. {atype}: {desc} {status}\n"

        # Build progress context from filled_fields
        progress_ctx = ""
        if filled_fields:
            progress_ctx = "\n\n## Already completed fields (do NOT fill again):\n"
            for fl, fv in filled_fields.items():
                progress_ctx += f"- {fl}: {fv}\n"

        prompt = f"""You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the next action to complete the task.

## Output Format
```
Thought: ...
Action: ...
```

## Action Space
click(point='<point>x y</point>')  # Click at pixel coordinates in the screenshot image.
fill_field(point='<point>x y</point>', field_label='label', field_value='value')  # Click a form field and type the value.
type(content='xxx')  # Type text into the currently focused field.
press_enter()  # Press the Enter key.
scroll(direction='down')  # Scroll the page down.
finished(content='summary')  # The task is fully finished.

## Note
- Write a small plan in Thought, then summarize your next action in one sentence.
- For fill_field, field_value must be ONLY the short value to type (e.g. "John"), NEVER the full task text.
- Do NOT repeat actions that already succeeded.
- When all tasks are done, use finished().
- Coordinates are absolute pixel positions in the screenshot image. (0,0) is top-left.
- IMPORTANT: Look carefully at the screenshot and identify the EXACT pixel location of the target element. Do NOT click the center of the page or use approximate coordinates. If you are unsure of the exact location, pick the coordinates of the most likely element you can see, NOT the center of the image. Each element has a specific position — find it precisely.

## Task
{goal}
{action_history}{progress_ctx}
"""

        try:
            response = await self.vision_client.chat_with_image(prompt, screenshot)

            # Parse response
            content = response.content.strip()
            # Remove invisible unicode chars (zero-width spaces etc) that models may add
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\ufeff\u00a0]', '', content)

            # Extract thought
            thought = ""
            thought_match = re.search(r"Thought:\s*(.+?)(?=\s*Action:|$)", content, re.DOTALL)
            if thought_match:
                thought = thought_match.group(1).strip()

            # Extract action
            action_str = None
            if "Action:" in content:
                action_str = content.split("Action:")[-1].strip()
            elif "action:" in content.lower():
                action_str = content.lower().split("action:")[-1].strip()

            if not action_str:
                # Fallback: try JSON parsing
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    parsed = json.loads(content[json_start:json_end])
                    if "tool_calls" in parsed:
                        tc = parsed["tool_calls"][0]
                        if "name" in tc:
                            return {"type": tc["name"], **tc.get("arguments", {})}
                        else:
                            for k, v in tc.items():
                                if isinstance(v, dict):
                                    return {"type": k, **v}
                    elif "type" in parsed:
                        return parsed
                logger.warning(f"No action found in response: {content[:200]}")
                return None

            # Parse the action string (e.g. click(start_box='(400,300)'))
            # Strip backticks that GLM models add around actions
            action_str = action_str.strip('`').strip()
            # Remove zero-width spaces and other invisible unicode that GLM adds
            action_str = re.sub(r'[\x00-\x1f\x7f-\x9f\u200b-\u200f\ufeff\u00a0]', '', action_str)
            logger.info(f"🔍 Parsed action_str: {repr(action_str)}")
            action_match = re.match(r"(\w+)\((.+)\)$", action_str, re.DOTALL)
            if not action_match:
                logger.warning(f"Cannot parse action: {action_str}")
                return None

            action_type = action_match.group(1).lower()
            args_str = action_match.group(2)

            # Map action types
            type_map = {
                "left_single": "click",
                "left_double": "click",
                "right_single": "click",
                "finished": "complete",
            }
            action_type = type_map.get(action_type, action_type)

            # Parse keyword arguments
            action = {"type": action_type}

            # Parse coordinates from action arguments
            # Format 1: UI-TARS <point>x y</point>
            # Format 2: GLM bbox [x1, y1, x2, y2] → center point
            # Format 3: start_box='(x,y)' or point='(x,y)'
            point_match = re.search(r'<point>(\d+)\s+(\d+)</point>', args_str)
            coord_match = None
            bbox_match = None
            if point_match:
                raw_x, raw_y = float(point_match.group(1)), float(point_match.group(2))
            else:
                # Try GLM bbox format: [x1, y1, x2, y2]
                bbox_match = re.search(r'(?:point|start_box)\s*=\s*[\'\"]?\[(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\][\'\"]?', args_str)
                if bbox_match:
                    x1, y1, x2, y2 = float(bbox_match.group(1)), float(bbox_match.group(2)), float(bbox_match.group(3)), float(bbox_match.group(4))
                    raw_x = (x1 + x2) / 2  # center of bbox
                    raw_y = (y1 + y2) / 2
                else:
                    # Fallback: parse (x,y) format
                    clean_args = re.sub(r'<\|[^>]*\|>', '', args_str)
                    coord_match = re.search(r'(?:start_box|point)\s*=\s*[\'\"]?\((\d+)\s*,\s*(\d+)\)[\'\"]?', clean_args)
                    if coord_match:
                        raw_x, raw_y = float(coord_match.group(1)), float(coord_match.group(2))

            if point_match or coord_match or bbox_match:
                # Coordinates are in the resized image pixel space.
                # Scale from resized image to viewport.
                import math
                def smart_resize(h, w, factor=28, min_pixels=78400, max_pixels=12845056):
                    h_bar = max(factor, round(h / factor) * factor)
                    w_bar = max(factor, round(w / factor) * factor)
                    if h_bar * w_bar > max_pixels:
                        beta = math.sqrt((h * w) / max_pixels)
                        h_bar = math.floor(h / beta / factor) * factor
                        w_bar = math.floor(w / beta / factor) * factor
                    elif h_bar * w_bar < min_pixels:
                        beta = math.sqrt(min_pixels / (h * w))
                        h_bar = math.ceil(h * beta / factor) * factor
                        w_bar = math.ceil(w * beta / factor) * factor
                    return h_bar, w_bar

                rh, rw = smart_resize(self.config.browser.viewport_height, self.config.browser.viewport_width)
                screen_x = int(raw_x / rw * self.config.browser.viewport_width)
                screen_y = int(raw_y / rh * self.config.browser.viewport_height) - 95
                # Clamp to viewport bounds
                screen_y = max(0, screen_y)
                action["x"] = screen_x
                action["y"] = screen_y
            # Parse other arguments
            # field_label
            fl_match = re.search(r"field_label\s*=\s*['\"]([^'\"]+)['\"]", args_str)
            if fl_match:
                action["field_label"] = fl_match.group(1)

            # field_value
            fv_match = re.search(r"field_value\s*=\s*['\"]([^'\"]+)['\"]", args_str)
            if fv_match:
                action["field_value"] = fv_match.group(1)

            # content
            ct_match = re.search(r"content\s*=\s*['\"]([^'\"]+)['\"]", args_str)
            if ct_match:
                action["content"] = ct_match.group(1)
                if action_type == "type":
                    action["text"] = ct_match.group(1)
                elif action_type == "complete":
                    action["result"] = ct_match.group(1)

            # description from thought
            action["description"] = thought[:100] if thought else ""

            logger.info(
                f"Vision action: {action.get('type')} - {action.get('description', action.get('field_label', ''))}"
                + (f" coords=({action.get('x')}, {action.get('y')})" if 'x' in action else "")
            )
            return action

        except Exception as e:
            logger.error(f"Failed to get vision action: {e}")

        return None

    async def _execute_vision_action(self, action: Dict[str, Any], screenshot: bytes) -> ActionResult:
        """Execute an action from vision model."""
        action_type = action.get("type")

        if action_type == "click":
            # Use coordinates directly from the model (native UI-TARS grounding)
            x = action.get("x", 0)
            y = action.get("y", 0)
            element_description = action.get("description", "click target")

            logger.info(f"🎯 Model-grounded click coordinates: ({x}, {y}) for '{element_description}'")
            result = await self.action_executor.execute(ActionType.CLICK, target=(x, y), screenshot=screenshot)

            # DOM fallback: if coordinate click didn't focus an input, find nearest input field
            if result.success:
                page = self.browser.page
                if page:
                    focused = await page.evaluate("() => document.activeElement?.tagName")
                    if focused not in ("INPUT", "TEXTAREA", "SELECT"):
                        logger.info("🔄 Coordinate click didn't focus any element, searching for nearby input...")
                        # Find the closest visible input/textarea to the click coordinates
                        nearest = await page.evaluate("""
                        ([clickX, clickY]) => {
                            const inputs = Array.from(document.querySelectorAll("input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='checkbox']):not([type='radio']), textarea, select"));
                            let closest = null;
                            let minDist = Infinity;
                            for (const el of inputs) {
                                const box = el.getBoundingClientRect();
                                if (box.width === 0 || box.height === 0) continue;
                                const cx = box.x + box.width / 2;
                                const cy = box.y + box.height / 2;
                                const dist = Math.sqrt((cx - clickX) ** 2 + (cy - clickY) ** 2);
                                if (dist < minDist) {
                                    minDist = dist;
                                    closest = {x: cx, y: cy, dist: dist, tag: el.tagName, id: el.id, placeholder: el.placeholder};
                                }
                            }
                            return closest;
                        }
                        """, [x, y])
                        if nearest and nearest["dist"] < 300:
                            logger.info(
                                f"🎯 DOM fallback: nearest input '{nearest.get('tag')}' at ({nearest['x']:.0f}, {nearest['y']:.0f}), dist={nearest['dist']:.0f}px"
                            )
                            result = await self.action_executor.execute(
                                ActionType.CLICK, target=(nearest["x"], nearest["y"]), screenshot=screenshot
                            )
                        else:
                            logger.info(f"🔄 No nearby input found (nearest: {nearest})")

            # DOM button/link fallback: if click didn't seem to work, try finding button by text
            if result.success and page:
                desc_lower = (element_description or "").lower()
                _btn_js = "(descText) => {" + """
                    const keywords = descText.toLowerCase().split(' ').filter(k => k.length > 2);
                    // Search buttons, clickable divs, and interactive elements
                    const selectors = 'button, [onclick], [role="button"], .accordion-header, .tab, .toggle, [class*="tab"], [class*="toggle"], [data-testid]';
                    const candidates = Array.from(document.querySelectorAll(selectors));
                    let bestMatch = null;
                    let bestScore = 0;
                    for (const el of candidates) {
                        // Use short text only - first line or first 80 chars to avoid matching containers with nested content
                        const fullText = (el.textContent || el.value || el.getAttribute('aria-label') || '').trim().toLowerCase();
                        const text = fullText.split(String.fromCharCode(10))[0].substring(0, 80);
                        const matchCount = keywords.filter(k => text.includes(k)).length;
                        if (matchCount > bestScore && el.getBoundingClientRect().width > 0) {
                            const box = el.getBoundingClientRect();
                            bestScore = matchCount;
                            bestMatch = {x: box.x + box.width/2, y: box.y + box.height/2, found: true, text: text, score: matchCount};
                        }
                    }
                    return bestMatch || {found: false};
                }"""
                btn_data = await page.evaluate(_btn_js, desc_lower)
                if btn_data and btn_data.get("found"):
                    # Scroll element into view if off-screen (negative y or y > viewport)
                    by = btn_data["y"]
                    if by < 0 or by > self.config.browser.viewport_height:
                        logger.info(f"🎯 Element at y={by:.0f} is off-screen, scrolling into view")
                        await page.evaluate(f"window.scrollBy(0, {by - self.config.browser.viewport_height / 2:.0f})")
                        await asyncio.sleep(0.3)
                        # Recalculate position after scroll
                        btn_data = await page.evaluate(_btn_js, desc_lower)
                    if btn_data and btn_data.get("found"):
                        logger.info(
                            f"🎯 DOM button fallback: found '{btn_data.get('text', '')}' at ({btn_data['x']:.0f}, {btn_data['y']:.0f})"
                        )
                        result = await self.action_executor.execute(
                            ActionType.CLICK, target=(btn_data["x"], btn_data["y"]), screenshot=screenshot
                        )

            return result

        elif action_type == "fill_field":
            field_label = action.get("field_label", "")
            field_value = action.get("field_value", "") or action.get("text", "")
            page = self.browser.page
            field_found = False

            result = None

            if page:
                label_lower = field_label.lower()
                el_data = await page.evaluate(
                    """(labelText) => {
                    const searchWords = labelText.split(/\\s+/).filter(w => w.length > 2);
                    const labels = Array.from(document.querySelectorAll('label'));
                    for (const label of labels) {
                        const labelWords = label.textContent.toLowerCase().trim().split(/\\s+/);
                        // Check bidirectional: do most search words appear in label, or most label words in search?
                        const matchCount = searchWords.filter(w => labelWords.some(lw => lw.includes(w) || w.includes(lw))).length;
                        if (matchCount > 0 && matchCount >= Math.ceil(searchWords.length * 0.5)) {
                            const input = label.htmlFor ? document.getElementById(label.htmlFor) : label.querySelector('input,textarea');
                            if (input && input.getBoundingClientRect().width > 0) {
                                input.focus();
                                input.value = '';
                                const box = input.getBoundingClientRect();
                                return {x: box.x + box.width/2, y: box.y + box.height/2, found: true};
                            }
                        }
                    }
                    const inputs = Array.from(document.querySelectorAll('input:not([type=hidden]):not([type=radio]):not([type=checkbox]), textarea'));
                    for (const inp of inputs) {
                        const ph = (inp.placeholder || '').toLowerCase();
                        const nm = (inp.name || '').toLowerCase();
                        const id = (inp.id || '').toLowerCase();
                        const allText = ph + ' ' + nm + ' ' + id;
                        const matchCount = searchWords.filter(w => allText.includes(w)).length;
                        if (matchCount > 0 && matchCount >= Math.ceil(searchWords.length * 0.5)) {
                            inp.focus();
                            inp.value = '';
                            const box = inp.getBoundingClientRect();
                            return {x: box.x + box.width/2, y: box.y + box.height/2, found: true};
                        }
                    }
                    return {found: false};
                }""",
                    label_lower,
                )

                if el_data and el_data.get("found"):
                    logger.info("Found field via DOM: %s", field_label)
                    await self.action_executor.execute(ActionType.CLICK, target=(el_data["x"], el_data["y"]))
                    await asyncio.sleep(0.2)
                    result = await self.action_executor.execute(ActionType.TYPE_TEXT, value=field_value)
                    field_found = True
                    await asyncio.sleep(0.2)
                    value = await page.evaluate("() => document.activeElement?.value || ''")
                    if field_value in value:
                        logger.info("Fill verified: %s=%s", field_label, field_value)
                        return result

            if not field_found:
                x = action.get("x", 0)
                y = action.get("y", 0)
                logger.info("Field not found via DOM, using coords (%s, %s)", x, y)
                await self.action_executor.execute(ActionType.CLICK, target=(x, y))
                await asyncio.sleep(0.2)
                result = await self.action_executor.execute(ActionType.TYPE_TEXT, value=field_value)

            return result or ActionResult(success=True, action_type=ActionType.TYPE_TEXT)

        elif action_type == "type":
            text = action.get("text", "")
            # Guard: skip if text looks like instructions (not a value to type)
            if text and ("\n" in text or len(text) > 120):
                logger.warning(f"Skipping type action with instruction-like text: {text[:80]}...")
                return ActionResult(
                    success=False,
                    action_type=ActionType.TYPE_TEXT,
                    error="text too long, looks like instructions not a value",
                )
            # Auto-focus: if no input is focused, find and click the nearest one
            page = self.browser.page
            if page:
                focused = await page.evaluate("() => document.activeElement?.tagName")
                if focused not in ("INPUT", "TEXTAREA", "SELECT"):
                    logger.info("🔄 No input focused for type action, clicking first visible input...")
                    _first_input_js = "() => {" + """
                        const el = document.querySelector("input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='checkbox']):not([type='radio']):not([hidden]), textarea:not([hidden])");
                        if (el) {
                            const box = el.getBoundingClientRect();
                            if (box.width > 0 && box.height > 0) {
                                return {x: box.x + box.width/2, y: box.y + box.height/2, tag: el.tagName, id: el.id, placeholder: el.placeholder};
                            }
                        }
                        return null;
                    """ + "}"
                    input_info = await page.evaluate(_first_input_js)
                    if input_info:
                        logger.info(f"🎯 Auto-focusing input '{input_info.get('tag')}' at ({input_info['x']:.0f}, {input_info['y']:.0f})")
                        await self.action_executor.execute(ActionType.CLICK, target=(input_info["x"], input_info["y"]))
                        await asyncio.sleep(0.3)
                        # Double-check focus, force it via JS if needed
                        focused2 = await page.evaluate("() => document.activeElement?.tagName")
                        if focused2 not in ("INPUT", "TEXTAREA", "SELECT"):
                            logger.info("🎯 Click didn't focus input, forcing focus via JS...")
                            await page.evaluate("""() => {
                                const el = document.querySelector("input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='checkbox']):not([type='radio']):not([hidden]), textarea:not([hidden])");
                                if (el) el.focus();
                            }""")
                            await asyncio.sleep(0.2)
            return await self.action_executor.execute(ActionType.TYPE_TEXT, value=text, screenshot=screenshot)

        elif action_type == "press_enter":
            return await self.action_executor.execute(ActionType.PRESS_KEY, value="Enter", screenshot=screenshot)

        elif action_type == "scroll_down" or action_type == "scroll":
            return await self.action_executor.execute(ActionType.SCROLL_DOWN, screenshot=screenshot)

        else:
            return ActionResult(success=False, action_type=ActionType.WAIT, error=f"Unknown action type: {action_type}")

    # ==================== Convenience Methods ====================

    async def navigate(self, url: str) -> ActionResult:
        """Navigate to URL."""
        return await self.action_executor.execute(ActionType.NAVIGATE, value=url)

    async def click(self, selector_or_coords, options: Optional[Dict] = None) -> ActionResult:
        """Click on element or coordinates."""
        return await self.action_executor.execute(ActionType.CLICK, target=selector_or_coords, options=options)

    async def type_text(self, text: str, selector: Optional[str] = None, clear: bool = False) -> ActionResult:
        """Type text into element."""
        return await self.action_executor.execute(
            ActionType.TYPE_TEXT, target=selector, value=text, options={"clear": clear}
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
        result = await self.action_executor.execute(ActionType.TAKE_SCREENSHOT, options={"full_page": full_page})
        return result.screenshot or b""

    async def extract_text(self, selector: Optional[str] = None) -> str:
        """Extract text from page or element."""
        result = await self.action_executor.execute(ActionType.EXTRACT_TEXT, target=selector)
        return result.data.get("text", "") if result.success else ""

    async def wait_for_element(self, selector: str, timeout: int = 5000) -> ActionResult:
        """Wait for element to appear."""
        return await self.action_executor.execute(
            ActionType.WAIT_FOR_ELEMENT, target=selector, options={"timeout": timeout}
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
            "credential_vault_enabled": self.credential_vault is not None,
            "audit_log_enabled": self.audit_log is not None,
            "tenant_id": self.tenant_id,
        }

    # --- Credential Resolution ---

    async def _resolve_credentials_in_text(
        self,
        text: str,
        credential_aliases: Dict[str, str],
    ) -> str:
        """Replace ${vault:alias.field} placeholders with resolved credentials.

        Also supports simple ${field_name} syntax where field_name maps to
        credential_aliases dict.
        """
        import re

        if not self.credential_vault:
            return text

        result = text

        # Resolve ${vault:alias.field} patterns
        vault_pattern = r"\$\{vault:([^.}]+)\.?([^}]*)\}"
        for match in re.finditer(vault_pattern, result):
            alias = match.group(1)
            field = match.group(2) or "secret"
            try:
                cred = await self.credential_vault.get_credential(alias, self.tenant_id, requested_by="agent")
                try:
                    if field == "secret":
                        value = cred.secret
                    elif field == "username":
                        value = cred.username or ""
                    else:
                        value = str(cred.metadata.get(field, ""))
                    result = result.replace(match.group(0), value)
                finally:
                    cred.wipe()
            except Exception as e:
                logger.warning("Failed to resolve vault reference %s: %s", match.group(0), e)

        # Resolve simple ${field_name} using credential_aliases mapping
        simple_pattern = r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}"
        for match in re.finditer(simple_pattern, result):
            field_name = match.group(1)
            if field_name in credential_aliases:
                alias = credential_aliases[field_name]
                try:
                    cred = await self.credential_vault.get_credential(alias, self.tenant_id, requested_by="agent")
                    try:
                        value = cred.secret
                        result = result.replace(match.group(0), value)
                    finally:
                        cred.wipe()
                except Exception as e:
                    logger.warning(
                        "Failed to resolve credential %s -> %s: %s",
                        field_name,
                        alias,
                        e,
                    )

        return result


# Convenience function
async def create_agent(config: Optional[Config] = None) -> BrowserAgent:
    """Create and initialize a browser agent."""
    agent = BrowserAgent(config)
    await agent.initialize()
    return agent

#!/usr/bin/env python3
"""
Simple Browser Agent for Host System

Direct browser automation without complex dependencies.
"""

import asyncio
import logging
import sys
import os
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class SimpleBrowserAgent:
    """Simple browser agent for direct host execution."""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    async def initialize_browser(self):
        """Initialize browser for visible operation."""
        try:
            from playwright.async_api import async_playwright

            logger.info("Initializing browser for visible operation...")

            self.playwright = await async_playwright().start()

            # Check environment variable for headless mode
            headless_env = os.environ.get('BROWSER_HEADLESS', 'false')
            headless = headless_env.lower() == 'true'
            logger.info(f"BROWSER_HEADLESS env var: '{headless_env}', parsed as headless={headless}")

            self.browser = await self.playwright.chromium.launch(
                headless=headless,  # Use environment variable
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-extensions",
                    "--start-maximized",  # Start maximized
                    "--always-on-top",    # Keep on top
                ]
            )

            self.page = await self.browser.new_page()

            # Enhanced anti-detection measures
            await self.page.add_init_script("""
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });

                // Mock plugins and languages
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                        { name: 'Chromium PDF Plugin', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                        { name: 'Microsoft Edge PDF Plugin', filename: 'internal-pdf-viewer' },
                        { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer' }
                    ],
                });

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

                // Mock battery (if available)
                if ('getBattery' in navigator) {
                    navigator.getBattery = () => Promise.resolve({
                        charging: true,
                        chargingTime: Infinity,
                        dischargingTime: Infinity,
                        level: 1,
                    });
                }
            """)

            # Set realistic user agent
            await self.page.set_extra_http_headers({
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
            })

            # Set viewport to realistic size
            await self.page.set_viewport_size({"width": 1920, "height": 1080})

            # Add random mouse movements and human-like behavior before interactions
            await self._add_human_like_behavior()

            # Add random delays and human-like patterns
            await asyncio.sleep(1)  # Initial pause

            # Simulate human reading time
            await self.page.wait_for_timeout(2000)

            logger.info("✅ Browser initialized successfully!")
            return True

        except Exception as e:
            logger.error(f"❌ Browser initialization failed: {e}")
            return False

    async def navigate_and_search_with_vision(self, url: str, goal: str):
        """Navigate to URL and use vision AI to perform search."""
        try:
            logger.info(f"Navigating to {url}...")

            # Navigate to the page
            await self.page.goto(url, wait_until="networkidle")
            await asyncio.sleep(2)  # Wait for page to load

            logger.info(f"Using vision AI for goal: {goal}")

            # Take screenshot for vision analysis
            screenshot = await self.page.screenshot(type='png')
            import base64
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

            # Use vision model to get instructions
            instructions = await self._get_vision_instructions(goal, screenshot_b64)

            if not instructions:
                logger.warning("⚠️ Could not get instructions from vision model")
                return False

            # Execute the instructions
            success = await self._execute_vision_instructions(instructions, goal)
            return success

        except Exception as e:
            logger.error(f"❌ Vision-based navigation/search failed: {e}")
            return False

    async def _get_vision_instructions(self, goal: str, screenshot_b64: str):
        """Get instructions from vision model."""
        try:
            import aiohttp
            import json

            # LM Studio endpoint
            lm_studio_url = os.environ.get('LM_STUDIO_URL', 'http://127.0.0.1:1234')
            url = f"{lm_studio_url}/v1/chat/completions"
            logger.info(f"🤖 Using LM Studio URL: {url}")

            prompt = f"""
You are a precise UI automation assistant. Analyze this screenshot and provide precise instructions to accomplish: "{goal}"

Look at the webpage CAREFULLY and determine:
1. Exact location of search input field (usually a text box)
2. What text needs to be entered
3. How to submit the search (preferably press Enter key)

IMPORTANT: Provide REAL coordinates based on what you see in the screenshot. Don't use generic coordinates.
Screenshot size is x=1920, y=1080

Coordinates are in the format xxxx, yyyy or xxx, yyy

Return your response in this exact JSON format:
{{
  "actions": [
    {{
      "type": "click",
      "description": "Click on the search input field",
      "x": xxxx,
      "y": yyyy
    }},
    {{
      "type": "type_text",
      "description": "Enter search query",
      "text": "AI"
    }},
    {{
      "type": "press_enter",
      "description": "Submit search by pressing Enter"
    }}
  ]
}}

CRITICAL: Use real coordinates you observe in the screenshot. For Google:
- Look for the actual search box position
- After typing, use press_enter instead of clicking search button
"""

            payload = {
                "model": "mradermacher/ui-tars-1.5-7b",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [screenshot_b64]
                    }
                ],
                "max_tokens": 4000,
                "temperature": 0.1
            }

            async with aiohttp.ClientSession() as session:
                lm_studio_url = os.environ.get('LM_STUDIO_URL', 'http://127.0.0.1:1234')
                async with session.post(f"{lm_studio_url}/v1/chat/completions", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        vision_response = result["choices"][0]["message"]["content"]

                        # Try to extract JSON from response
                        logger.info(f"🤖 Raw LM Studio response: {vision_response}")
                        try:
                            # Look for JSON in the response
                            json_start = vision_response.find('{')
                            json_end = vision_response.rfind('}') + 1
                            if json_start >= 0 and json_end > json_start:
                                json_str = vision_response[json_start:json_end]
                                logger.info(f"📄 Extracted JSON string: {json_str}")
                                instructions = json.loads(json_str)
                                logger.info(f"✅ Parsed vision instructions: {instructions}")
                                logger.info(f"📋 Got vision instructions: {len(instructions.get('actions', []))} actions")
                                return instructions
                            else:
                                logger.warning(f"⚠️ No JSON found in vision response: {vision_response}")
                                return None
                        except json.JSONDecodeError as e:
                            logger.warning(f"⚠️ Could not parse vision response as JSON: {vision_response}, error: {e}")
                            return None
                    else:
                        logger.error(f"❌ LM Studio API error: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"❌ Vision instruction request failed: {e}")
            return None

    async def _execute_vision_instructions(self, instructions: dict, goal: str):
        """Execute instructions from vision model."""
        try:
            actions = instructions.get('actions', [])
            logger.info(f"📋 Executing {len(actions)} vision-guided actions")

            for i, action in enumerate(actions, 1):
                action_type = action.get('type')
                description = action.get('description', '')
                logger.info(f"🎯 Step {i}: {description} (type: {action_type})")

                if action_type == 'click':
                    x, y = action.get('x', 0), action.get('y', 0)
                    logger.info(f"🖱️ Clicking at coordinates: ({x}, {y})")
                    await self.page.mouse.click((x)*0.75-17, (y)*0.75-96)
                    logger.info(f"✅ Click completed at ({(x)*0.75}, {(y)*0.75})")
                    await asyncio.sleep(0.5)

                elif action_type == 'type_text':
                    text = action.get('text', '')
                    logger.info(f"⌨️ Typing text '{text}' into focused input field")
                    # Type directly (assuming focus is already on input field)
                    await self.page.keyboard.type(text)
                    logger.info(f"✅ Typed '{text}' successfully")
                    await asyncio.sleep(0.5)

                elif action_type == 'press_enter':
                    logger.info(f"⏎ Pressing Enter key")
                    await self.page.keyboard.press('Enter')
                    logger.info(f"✅ Enter key pressed")
                    await asyncio.sleep(0.5)

                else:
                    logger.warning(f"⚠️ Unknown action type: {action_type}")

            logger.info("✅ All vision-guided actions completed!")
            await asyncio.sleep(3)  # Wait for search results to load

            # Validate that search was successful
            validation_result = await self._validate_search_completion(goal)
            if validation_result:
                logger.info("✅ Search validation passed - results are displayed")

                # Now proceed to extract information from search results
                extraction_result = await self._extract_information_from_results(goal)
                if extraction_result:
                    logger.info("✅ Information extraction completed successfully")
                    return True
                else:
                    logger.warning("⚠️ Information extraction failed")
                    return False
            else:
                logger.warning("⚠️ Search validation failed - results may not be displayed")
                return False

        except Exception as e:
            logger.error(f"❌ Action execution failed: {e}")
            return False

    async def execute_task(self, goal: str, url: str) -> Dict[str, Any]:
        """Execute browser automation task."""
        start_time = asyncio.get_event_loop().time()

        try:
            # Initialize browser if not already initialized
            if not self.browser or not self.page:
                if not await self.initialize_browser():
                    return {
                        "task_id": "simple-task",
                        "status": "failed",
                        "goal": goal,
                        "results": [],
                        "success": False,
                        "execution_time": 0,
                        "error": "Browser initialization failed"
                    }

            # Use vision AI for all tasks with retry logic
            success = await self._execute_with_retry(url, goal, max_retries=3)

            execution_time = asyncio.get_event_loop().time() - start_time

            logger.info("✅ Task completed successfully - browser window remains open")

            return {
                "task_id": "simple-task",
                "status": "completed",
                "goal": goal,
                "results": [{
                    "step_number": 1,
                    "success": success,
                    "action_type": "navigate_and_search",
                    "execution_time": execution_time
                }],
                "success": success,
                "execution_time": execution_time,
                "error": "",
                "browser_status": "open"
            }

        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"Task execution failed: {e}")
            return {
                "task_id": "simple-task",
                "status": "error",
                "goal": goal,
                "results": [],
                "success": False,
                "execution_time": execution_time,
                "error": str(e),
                "browser_status": "open"
            }

    async def _execute_with_retry(self, url: str, goal: str, max_retries: int = 3) -> bool:
        """Execute vision-guided task with retry logic."""
        search_completed = False

        for attempt in range(max_retries):
            logger.info(f"🔄 Attempt {attempt + 1}/{max_retries} to complete search task")

            try:
                # If search hasn't been completed yet, do the full search
                if not search_completed:
                    success = await self.navigate_and_search_with_vision(url, goal)

                    if success:
                        logger.info(f"✅ Search task completed successfully on attempt {attempt + 1}")
                        search_completed = True
                        return True
                    else:
                        logger.warning(f"⚠️ Search validation failed on attempt {attempt + 1}")

                        # If not the last attempt, navigate back to original page for retry
                        if attempt < max_retries - 1:
                            logger.info(f"🔄 Retrying search... Navigating back to {url}")
                            try:
                                await self.page.goto(url, wait_until="networkidle")
                                await asyncio.sleep(2)  # Wait for page to reload
                            except Exception as nav_error:
                                logger.warning(f"⚠️ Could not navigate back for retry: {nav_error}")
                else:
                    # Search is done, but information extraction failed - retry just extraction
                    logger.info(f"🔄 Search completed, retrying information extraction (attempt {attempt + 1})")

                    # Try information extraction again on current search results page
                    extraction_result = await self._extract_information_from_results(goal)
                    if extraction_result:
                        logger.info(f"✅ Information extraction succeeded on retry {attempt + 1}")
                        return True
                    else:
                        logger.warning(f"⚠️ Information extraction failed on retry {attempt + 1}")

                        # If extraction fails, we might need to redo the search
                        if attempt < max_retries - 1:
                            logger.info("🔄 Information extraction failed, restarting full search...")
                            search_completed = False  # Reset to redo full search
                            try:
                                await self.page.goto(url, wait_until="networkidle")
                                await asyncio.sleep(2)
                            except Exception as nav_error:
                                logger.warning(f"⚠️ Could not navigate back: {nav_error}")

            except Exception as e:
                logger.error(f"❌ Attempt {attempt + 1} failed with error: {e}")

                # If not the last attempt, try to reset browser state
                if attempt < max_retries - 1:
                    logger.info("🔄 Resetting browser state for retry...")
                    search_completed = False  # Reset on error
                    try:
                        await self.page.reload()
                        await asyncio.sleep(2)
                    except Exception as reset_error:
                        logger.warning(f"⚠️ Could not reset browser state: {reset_error}")

        logger.error(f"❌ All {max_retries} attempts failed")
        return False

    async def _validate_search_completion(self, goal: str) -> bool:
        """Validate that the search was completed successfully."""
        try:
            logger.info("🔍 Validating search completion...")

            # Extract search term from goal
            search_term = ""
            if "search for" in goal.lower():
                search_term = goal.lower().split("search for")[-1].strip()
            elif "search" in goal.lower():
                # Try to extract from general search pattern
                search_term = goal.lower().split("search")[-1].strip()

            logger.info(f"🎯 Looking for search results containing: '{search_term}'")

            # Check URL to see if we're on search results page
            current_url = self.page.url
            logger.info(f"📍 Current URL: {current_url}")
            logger.info(f"🔍 URL contains 'google.com': {'google.com' in current_url}")
            logger.info(f"🔍 URL contains 'search?q=': {'search?q=' in current_url}")
            logger.info(f"🔍 URL contains '&q=': {'&q=' in current_url}")

            # Check page content for search results first
            try:
                # Look for common search result indicators
                search_indicators = [
                    "div.g",  # Google search results
                    "[data-ved]",  # Google result links
                    "h3",  # Result titles
                    ".result",  # Generic result class
                    ".search-result"
                ]

                results_found = False
                for selector in search_indicators:
                    try:
                        elements = await self.page.query_selector_all(selector)
                        if len(elements) > 0:
                            logger.info(f"✅ Found {len(elements)} search result elements with selector: {selector}")
                            results_found = True
                            break
                    except:
                        continue

                if not results_found:
                    logger.warning("⚠️ No search result elements found on page")

                # Additional validation: check for search term in page title or content
                title = await self.page.title()
                logger.info(f"📄 Page title: {title}")

                content_check = False
                if search_term and search_term.lower() in title.lower():
                    logger.info(f"✅ Search term '{search_term}' found in page title")
                    content_check = True
                elif "google" in title.lower() and ("search" in title.lower() or len(title.split()) > 3):
                    logger.info("✅ Appears to be Google search results page")
                    content_check = True

                # URL validation - check if we're on actual search results page (not just homepage)
                url_valid = False
                if "google.com" in current_url and ("search?q=" in current_url or "&q=" in current_url):
                    logger.info("✅ On Google search results page")
                    url_valid = True
                else:
                    logger.warning("⚠️ Not on expected search results page")

                # Overall validation
                validation_passed = url_valid and (results_found or content_check)

                if validation_passed:
                    logger.info("✅ Search validation PASSED - results page detected")
                else:
                    logger.warning("❌ Search validation FAILED - no results detected")

                return validation_passed

            except Exception as e:
                logger.warning(f"⚠️ Content validation failed: {e}")
                # If content check fails but we're on google.com, still consider it passed for dynamic results
                return "google.com" in current_url

        except Exception as e:
            logger.error(f"❌ Search validation error: {e}")
            return False

    async def _extract_information_from_results(self, goal: str) -> bool:
        """Extract information from search results by clicking on relevant links."""
        try:
            logger.info("📖 Starting information extraction from search results...")

            # Wait a bit for results to fully load
            await asyncio.sleep(2)

            # Take screenshot of search results
            screenshot = await self.page.screenshot(type='png')
            import base64
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

            # Use vision AI to find relevant search result to click
            click_instructions = await self._get_click_instructions(goal, screenshot_b64)

            if not click_instructions:
                logger.warning("⚠️ Could not get click instructions from vision model")
                return False

            # Execute the click on search result
            click_success = await self._execute_click_instructions(click_instructions)
            if not click_success:
                logger.warning("⚠️ Failed to click on search result")
                return False

            # Wait for new page to load
            await asyncio.sleep(3)

            # Validate we're on a content page (not still on search results)
            current_url = self.page.url
            logger.info(f"📍 Navigated to: {current_url}")

            if "google.com/search" in current_url or "google.com/webhp" in current_url:
                logger.warning("⚠️ Still on search page - navigation may have failed")
                return False

            # Extract information from the page
            extraction_success = await self._extract_and_summarize_content(goal)

            return extraction_success

        except Exception as e:
            logger.error(f"❌ Information extraction failed: {e}")
            return False

    async def _get_click_instructions(self, goal: str, screenshot_b64: str):
        """Get instructions for clicking on relevant search results."""
        try:
            import aiohttp
            import json

            # Extract the search topic from goal
            search_topic = ""
            if "search for" in goal.lower():
                search_topic = goal.lower().split("search for")[-1].strip()
            elif "search" in goal.lower():
                search_topic = goal.lower().split("search")[-1].strip()

            prompt = f"""
You are analyzing Google search results. Find the MOST RELEVANT search result link to click.

SEARCH TOPIC: "{search_topic}"

Look at the search results and identify:
1. The only on most authoritative/relevant result (preferably from .edu, .gov, wikipedia, or reputable sources)
2. Blue or purple color text is usually on the left side of the screenshot (these are clickable search results)
3. Avoid ads, "People also ask", "Возможно, вы искали", "Развернуть", "Обзор от ИИ" or secondary content

Return the EXACT coordinates to click on the most relevant search result title/link.
Screenshot size is x=1920, y=1080

Return JSON format:
{{
  "click_target": {{
    "x": xxx,
    "y": yyy,
    "description": "Description of the chosen site",
    "reason": "This appears to be the most authoritative or relevant source",
    "confidence": "high/medium/low"
  }}
}}
"""

            payload = {
                "model": "mradermacher/ui-tars-1.5-7b",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [screenshot_b64]
                    }
                ],
                "max_tokens": 4000,
                "temperature": 0.1
            }

            async with aiohttp.ClientSession() as session:
                lm_studio_url = os.environ.get('LM_STUDIO_URL', 'http://127.0.0.1:1234')
                async with session.post(f"{lm_studio_url}/v1/chat/completions", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        vision_response = result["choices"][0]["message"]["content"]

                        logger.info(f"🤖 Click instruction response: {vision_response}")

                        try:
                            json_start = vision_response.find('{')
                            json_end = vision_response.rfind('}') + 1
                            if json_start >= 0 and json_end > json_start:
                                json_str = vision_response[json_start:json_end]
                                instructions = json.loads(json_str)
                                logger.info(f"✅ Parsed click instructions: {instructions}")
                                return instructions
                            else:
                                logger.warning(f"⚠️ No JSON found in click response: {vision_response}")
                                return None
                        except json.JSONDecodeError as e:
                            logger.warning(f"⚠️ Could not parse click response as JSON: {vision_response}, error: {e}")
                            return None
                    else:
                        logger.error(f"❌ LM Studio API error for click instructions: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"❌ Click instruction request failed: {e}")
            return None

    async def _execute_click_instructions(self, instructions: dict) -> bool:
        """Execute click on search result."""
        try:
            click_target = instructions.get('click_target', {})
            x = click_target.get('x', 0)
            y = click_target.get('y', 0)
            description = click_target.get('description', 'Click on search result')
            reason = click_target.get('reason', '')

            logger.info(f"🎯 Clicking on search result: {description}")
            logger.info(f"📍 Reason: {reason}")
            logger.info(f"🖱️ Coordinates: ({(x)}, {(y)})")

            await self.page.mouse.click((x-17)*0.55, (y-96))
            logger.info("✅ Click completed on search result")
            logger.info(f"✅ Click completed at ({(x)*0.75}, {(y)*0.75})")

            return True

        except Exception as e:
            logger.error(f"❌ Click execution failed: {e}")
            return False

    async def _extract_and_summarize_content(self, goal: str) -> bool:
        """Extract relevant information from the content page and provide summary."""
        try:
            logger.info("📝 Extracting and summarizing content...")

            # Wait for content to load
            await asyncio.sleep(2)

            # Take screenshot of the content page
            screenshot = await self.page.screenshot(type='png')
            import base64
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

            # Extract the search topic
            search_topic = ""
            if "search for" in goal.lower():
                search_topic = goal.lower().split("search for")[-1].strip()
            elif "search" in goal.lower():
                search_topic = goal.lower().split("search")[-1].strip()

            prompt = f"""
You are analyzing a webpage about "{search_topic}".

TASK: Extract the most relevant information and provide a BRIEF, CONCISE answer (2-3 sentences maximum).

Look at the page content and:
1. Identify the main information related to "{search_topic}"
2. Extract key facts, definitions, or explanations
3. Provide a brief summary answer

Return your response in this JSON format:
{{
  "summary": "Brief 2-3 sentence answer about the topic",
  "key_points": ["Point 1", "Point 2", "Point 3"],
  "confidence": "high/medium/low"
}}
"""

            payload = {
                "model": "mradermacher/ui-tars-1.5-7b",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [screenshot_b64]
                    }
                ],
                "max_tokens": 1500,
                "temperature": 0.1
            }

            import aiohttp
            import json

            async with aiohttp.ClientSession() as session:
                lm_studio_url = os.environ.get('LM_STUDIO_URL', 'http://127.0.0.1:1234')
                async with session.post(f"{lm_studio_url}/v1/chat/completions", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        vision_response = result["choices"][0]["message"]["content"]

                        logger.info(f"🤖 Content extraction response: {vision_response}")

                        try:
                            json_start = vision_response.find('{')
                            json_end = vision_response.rfind('}') + 1
                            if json_start >= 0 and json_end > json_start:
                                json_str = vision_response[json_start:json_end]
                                content_data = json.loads(json_str)

                                summary = content_data.get('summary', '')
                                key_points = content_data.get('key_points', [])
                                confidence = content_data.get('confidence', 'unknown')

                                logger.info("✅ Content extracted successfully!")
                                logger.info(f"📋 Summary: {summary}")
                                logger.info(f"🔑 Key points: {key_points}")
                                logger.info(f"🎯 Confidence: {confidence}")

                                # Log the final answer for the user
                                print(f"\n🤖 AI Answer for '{search_topic}':")
                                print(f"📝 {summary}")
                                if key_points:
                                    print("🔑 Key points:")
                                    for point in key_points:
                                        print(f"   • {point}")
                                print(f"🎯 Confidence: {confidence}")
                                print()

                                return True
                            else:
                                logger.warning(f"⚠️ No JSON found in content response: {vision_response}")
                                return False
                        except json.JSONDecodeError as e:
                            logger.warning(f"⚠️ Could not parse content response as JSON: {vision_response}, error: {e}")
                            return False
                    else:
                        logger.error(f"❌ LM Studio API error for content extraction: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"❌ Content extraction failed: {e}")
            return False

    async def _add_human_like_behavior(self):
        """Add human-like behavior to avoid detection."""
        try:
            import random

            # Random mouse movements before starting
            for _ in range(3):
                x = random.randint(100, 1800)
                y = random.randint(100, 900)
                await self.page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.3))

            # Random scroll to simulate reading
            await self.page.evaluate("""
                window.scrollTo({
                    top: Math.random() * 300,
                    behavior: 'smooth'
                });
            """)
            await asyncio.sleep(0.5)

            logger.info("🤖 Human-like behavior simulation completed")

        except Exception as e:
            logger.warning(f"⚠️ Could not add human-like behavior: {e}")

    async def cleanup(self):
        """Clean up browser resources."""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser cleanup completed")
        except Exception as e:
            logger.warning(f"Browser cleanup warning: {e}")

# Global agent instance
agent = SimpleBrowserAgent()

async def execute_browser_task(goal: str, url: str) -> Dict[str, Any]:
    """Execute browser automation task."""
    return await agent.execute_task(goal, url)

async def main():
    """Main function for testing."""
    try:
        print("🎯 Simple Browser Agent Started")
        print("Browser will open and be visible on top of other applications")
        print("Press Ctrl+C to exit")
        print()

        # Keep running for API calls
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down browser agent...")
        await agent.cleanup()
        print("✅ Browser agent shut down cleanly")
    except Exception as e:
        print(f"❌ Error: {e}")
        await agent.cleanup()
        print("✅ Browser agent shut down after error")

if __name__ == "__main__":
    # For testing with persistent browser
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("🤖 Simple Browser Agent - Interactive Mode")
        print("==========================================")
        print()
        goal = input("🔍 Enter your search query: ").strip()
        if not goal:
            print("❌ No search query provided. Exiting.")
            exit(1)
        url = "https://www.google.com"
        print(f"🌐 Will search Google for: '{goal}'")
        print()

        async def test_run():
            print("🧪 Running browser test...")
            print("Browser will open, perform search, and stay open for you to see!")
            print("Press Ctrl+C to exit and close browser")
            print()

            result = await execute_browser_task(goal, url)
            print("\nTest Result:", result)

            if result.get("success"):
                print("\n✅ Browser completed the task successfully!")
                print("🔍 Check your screen - browser should be open with Google search results")
                print("🌐 Browser window will stay open until you press Ctrl+C")
                print()

                # Keep browser open for user to see
                try:
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    print("\nClosing browser...")
                    await agent.cleanup()
                    print("✅ Browser closed")
            else:
                print("\n❌ Task failed")
                await agent.cleanup()

        asyncio.run(test_run())
    else:
        # Run as server
        asyncio.run(main())

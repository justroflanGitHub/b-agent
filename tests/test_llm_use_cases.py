#!/usr/bin/env python3
"""
LLM-Based Integration Tests for Phase 4.5: Use Case Evaluation

These tests call the LLM model to perform tasks on localhost test pages
and evaluate the percentage of successful actions.

Usage:
    pytest tests/test_llm_use_cases.py -v --run-llm-tests
    pytest tests/test_llm_use_cases.py -v --run-llm-tests -k "form_filling"
"""

import asyncio
import json
import os
import pytest
import time
import subprocess
import socket
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

# Skip all tests unless --run-llm-tests flag is provided
# (handled via conftest.py or pytest marker instead)
# pytestmark = pytest.mark.skip(reason="Need --run-llm-tests option to run LLM integration tests")


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--run-llm-tests",
        action="store_true",
        default=False,
        help="Run LLM-based integration tests"
    )
    parser.addoption(
        "--llm-endpoint",
        action="store",
        default="http://localhost:1234/v1",
        help="LM Studio API endpoint"
    )
    parser.addoption(
        "--llm-model",
        action="store",
        default="local-model",
        help="Model name to use"
    )
    parser.addoption(
        "--test-server-port",
        action="store",
        default=8765,
        type=int,
        help="Port for the test page server"
    )
    parser.addoption(
        "--success-threshold",
        action="store",
        default=70.0,
        type=float,
        help="Minimum success rate percentage to pass tests"
    )


@dataclass
class LLMAction:
    """Represents a single action performed by the LLM."""
    step_number: int
    action_type: str
    description: str
    selector: Optional[str]
    value: Optional[str]
    reasoning: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class LLMActionResult:
    """Result of executing an LLM action."""
    action: LLMAction
    success: bool
    expected_outcome: str
    actual_outcome: str
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class UseCaseTestResult:
    """Complete result of a use case test."""
    use_case: str
    task_description: str
    llm_actions: List[LLMAction] = field(default_factory=list)
    action_results: List[LLMActionResult] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_tokens_used: int = 0
    
    @property
    def total_actions(self) -> int:
        return len(self.action_results)
    
    @property
    def successful_actions(self) -> int:
        return sum(1 for r in self.action_results if r.success)
    
    @property
    def success_rate(self) -> float:
        if self.total_actions == 0:
            return 0.0
        return (self.successful_actions / self.total_actions) * 100
    
    @property
    def duration_seconds(self) -> float:
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict:
        return {
            "use_case": self.use_case,
            "task_description": self.task_description,
            "summary": {
                "total_actions": self.total_actions,
                "successful_actions": self.successful_actions,
                "success_rate_percent": round(self.success_rate, 2),
                "duration_seconds": round(self.duration_seconds, 2),
                "total_tokens_used": self.total_tokens_used
            },
            "actions": [
                {
                    "step": r.action.step_number,
                    "type": r.action.action_type,
                    "description": r.action.description,
                    "success": r.success,
                    "expected": r.expected_outcome,
                    "actual": r.actual_outcome,
                    "error": r.error
                }
                for r in self.action_results
            ]
        }


class TestPageServer:
    """Manages the test page HTTP server."""
    
    def __init__(self, port: int = 8765):
        self.port = port
        self.process = None
        self.base_url = f"http://localhost:{port}"
        
    def start(self):
        """Start the test server."""
        if self._is_port_in_use(self.port):
            print(f"Port {self.port} already in use, assuming server is running")
            return
            
        server_path = Path(__file__).parent.parent / "test_pages" / "server.py"
        self.process = subprocess.Popen(
            ["python", str(server_path), "--port", str(self.port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(2)
        
    def stop(self):
        """Stop the test server."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                
    def _is_port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    
    def get_url(self, path: str) -> str:
        return f"{self.base_url}/{path}"


class LLMAgent:
    """LLM-powered browser agent for testing."""
    
    def __init__(
        self,
        endpoint: str = "http://localhost:1234/v1",
        model: str = "local-model"
    ):
        self.endpoint = endpoint
        self.model = model
        self.browser = None
        self.page = None
        self.playwright = None
        self.total_tokens = 0
        
    async def initialize(self, headless: bool = False):
        """Initialize the browser."""
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--window-size=1280,720'
            ]
        )
        self.page = await self.browser.new_page()
        
        # Set viewport
        await self.page.set_viewport_size({"width": 1280, "height": 720})
        
    async def cleanup(self):
        """Clean up browser resources."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def navigate(self, url: str):
        """Navigate to a URL."""
        await self.page.goto(url, wait_until="networkidle")
        
    async def get_page_state(self) -> Dict:
        """Get current page state for LLM context."""
        return await self.page.evaluate("""
            () => {
                const elements = [];
                
                // Get all interactive elements
                const interactives = document.querySelectorAll(
                    'input, button, select, textarea, a[href], [onclick], [role="button"]'
                );
                
                interactives.forEach((el, i) => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        elements.push({
                            index: i,
                            tag: el.tagName.toLowerCase(),
                            type: el.type || null,
                            id: el.id || null,
                            name: el.name || null,
                            placeholder: el.placeholder || null,
                            text: el.innerText?.substring(0, 50) || null,
                            value: el.value || null,
                            selector: el.id ? `#${el.id}` : 
                                     el.name ? `[name="${el.name}"]` :
                                     `${el.tagName.toLowerCase()}:nth-of-type(${i+1})`
                        });
                    }
                });
                
                return {
                    url: window.location.href,
                    title: document.title,
                    elements: elements.slice(0, 50)  // Limit to 50 elements
                };
            }
        """)
    
    async def call_llm(self, prompt: str) -> Dict:
        """Call the LLM and get a response."""
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.endpoint}/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": """You are a browser automation agent. Analyze the page state and determine the next action to complete the user's task.

Respond in JSON format:
{
    "thinking": "Your reasoning about what to do next",
    "action": {
        "type": "click|fill|select|wait|done|error",
        "selector": "CSS selector for the element",
        "value": "Value to fill or select",
        "description": "Human-readable description of the action"
    },
    "expected_outcome": "What should happen after this action",
    "task_complete": false
}

Action types:
- click: Click an element (provide selector)
- fill: Fill a text input (provide selector and value)
- select: Select an option (provide selector and value)
- wait: Wait for an element or condition (provide selector)
- done: Task is complete
- error: Cannot proceed with task"""
                            },
                            {
                                "role": "user", 
                                "content": prompt
                            }
                        ],
                        "temperature": 0.1,
                        "max_tokens": 500
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.total_tokens += data.get("usage", {}).get("total_tokens", 0)
                        content = data["choices"][0]["message"]["content"]
                        
                        # Parse JSON from response
                        try:
                            # Try to extract JSON from markdown code blocks
                            if "```json" in content:
                                json_str = content.split("```json")[1].split("```")[0].strip()
                            elif "```" in content:
                                json_str = content.split("```")[1].split("```")[0].strip()
                            else:
                                json_str = content.strip()
                            
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            return {
                                "thinking": content,
                                "action": {"type": "error"},
                                "expected_outcome": "Failed to parse LLM response",
                                "task_complete": False
                            }
                    else:
                        return {
                            "thinking": f"LLM API error: {response.status}",
                            "action": {"type": "error"},
                            "expected_outcome": "API call failed",
                            "task_complete": False
                        }
        except Exception as e:
            return {
                "thinking": f"Exception calling LLM: {str(e)}",
                "action": {"type": "error"},
                "expected_outcome": "Exception occurred",
                "task_complete": False
            }
    
    async def execute_action(self, action: Dict, step: int) -> LLMActionResult:
        """Execute an action and return the result."""
        action_type = action.get("type", "error")
        selector = action.get("selector")
        value = action.get("value", "")
        description = action.get("description", action_type)
        expected = action.get("expected_outcome", "")
        
        llm_action = LLMAction(
            step_number=step,
            action_type=action_type,
            description=description,
            selector=selector,
            value=value,
            reasoning=action.get("thinking", "")
        )
        
        start_time = time.time()
        
        try:
            if action_type == "click":
                if not selector:
                    return LLMActionResult(
                        action=llm_action,
                        success=False,
                        expected_outcome=expected,
                        actual_outcome="No selector provided",
                        error="Missing selector"
                    )
                
                element = await self.page.wait_for_selector(selector, timeout=5000)
                if element:
                    await element.click()
                    await asyncio.sleep(0.5)
                    return LLMActionResult(
                        action=llm_action,
                        success=True,
                        expected_outcome=expected,
                        actual_outcome=f"Clicked {selector}",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                else:
                    return LLMActionResult(
                        action=llm_action,
                        success=False,
                        expected_outcome=expected,
                        actual_outcome="Element not found",
                        error=f"Could not find element: {selector}"
                    )
                    
            elif action_type == "fill":
                if not selector or value is None:
                    return LLMActionResult(
                        action=llm_action,
                        success=False,
                        expected_outcome=expected,
                        actual_outcome="Missing selector or value",
                        error="Missing parameters"
                    )
                
                element = await self.page.wait_for_selector(selector, timeout=5000)
                if element:
                    await element.fill(str(value))
                    return LLMActionResult(
                        action=llm_action,
                        success=True,
                        expected_outcome=expected,
                        actual_outcome=f"Filled {selector} with '{value}'",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                else:
                    return LLMActionResult(
                        action=llm_action,
                        success=False,
                        expected_outcome=expected,
                        actual_outcome="Element not found",
                        error=f"Could not find element: {selector}"
                    )
                    
            elif action_type == "select":
                if not selector or not value:
                    return LLMActionResult(
                        action=llm_action,
                        success=False,
                        expected_outcome=expected,
                        actual_outcome="Missing selector or value",
                        error="Missing parameters"
                    )
                
                await self.page.select_option(selector, value)
                return LLMActionResult(
                    action=llm_action,
                    success=True,
                    expected_outcome=expected,
                    actual_outcome=f"Selected '{value}' in {selector}",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
                
            elif action_type == "wait":
                if selector:
                    await self.page.wait_for_selector(selector, timeout=5000)
                else:
                    await asyncio.sleep(1)
                return LLMActionResult(
                    action=llm_action,
                    success=True,
                    expected_outcome=expected,
                    actual_outcome="Wait completed",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
                
            elif action_type == "done":
                return LLMActionResult(
                    action=llm_action,
                    success=True,
                    expected_outcome=expected,
                    actual_outcome="Task marked as complete",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
                
            elif action_type == "error":
                return LLMActionResult(
                    action=llm_action,
                    success=False,
                    expected_outcome=expected,
                    actual_outcome="Agent reported error",
                    error=action.get("description", "Unknown error")
                )
                
            else:
                return LLMActionResult(
                    action=llm_action,
                    success=False,
                    expected_outcome=expected,
                    actual_outcome=f"Unknown action type: {action_type}",
                    error="Invalid action type"
                )
                
        except Exception as e:
            return LLMActionResult(
                action=llm_action,
                success=False,
                expected_outcome=expected,
                actual_outcome="Exception during execution",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    async def run_task(
        self,
        task_description: str,
        start_url: str,
        max_steps: int = 15
    ) -> UseCaseTestResult:
        """Run a complete task and return results."""
        result = UseCaseTestResult(
            use_case="unknown",
            task_description=task_description
        )
        
        try:
            await self.initialize(headless=False)
            await self.navigate(start_url)
            await asyncio.sleep(1)
            
            step = 0
            task_complete = False
            
            while not task_complete and step < max_steps:
                step += 1
                
                # Get page state
                page_state = await self.get_page_state()
                
                # Build prompt for LLM
                prompt = f"""Task: {task_description}

Current Page State:
URL: {page_state['url']}
Title: {page_state['title']}

Available Interactive Elements:
{json.dumps(page_state['elements'][:20], indent=2)}

Previous Actions:
{json.dumps([{'step': r.action.step_number, 'action': r.action.description, 'success': r.success} for r in result.action_results[-5:]], indent=2)}

Determine the next action to complete the task. Respond in JSON format."""

                # Call LLM
                llm_response = await self.call_llm(prompt)
                
                # Create action object
                action = llm_response.get("action", {"type": "error"})
                
                # Execute action
                action_result = await self.execute_action(action, step)
                result.action_results.append(action_result)
                
                # Check if task is complete
                task_complete = llm_response.get("task_complete", False)
                if action.get("type") == "done":
                    task_complete = True
                    
                # Small delay between actions
                await asyncio.sleep(0.5)
            
            result.total_tokens_used = self.total_tokens
            
        except Exception as e:
            result.action_results.append(LLMActionResult(
                action=LLMAction(
                    step_number=0,
                    action_type="error",
                    description="Task execution failed",
                    selector=None,
                    value=None,
                    reasoning=str(e)
                ),
                success=False,
                expected_outcome="Task completed",
                actual_outcome="Exception occurred",
                error=str(e)
            ))
        
        finally:
            await self.cleanup()
            
        result.end_time = time.time()
        return result


class TestFormFillingLLM:
    """LLM-based tests for form filling use case."""
    
    @pytest.fixture(autouse=True)
    def setup(self, request):
        """Set up test fixtures."""
        self.port = request.config.getoption("--test-server-port", default=8765)
        self.endpoint = request.config.getoption("--llm-endpoint", default="http://localhost:1234/v1")
        self.model = request.config.getoption("--llm-model", default="local-model")
        self.threshold = request.config.getoption("--success-threshold", default=70.0)
        
        self.server = TestPageServer(self.port)
        self.server.start()
        
        yield
        
    @pytest.mark.asyncio
    async def test_llm_fill_contact_form(self):
        """Test LLM filling out the contact form."""
        agent = LLMAgent(endpoint=self.endpoint, model=self.model)
        
        result = await agent.run_task(
            task_description="Fill out the contact form with test data: First Name 'John', Last Name 'Doe', Email 'john@example.com', Username 'johndoe', Password 'Password123!', Confirm Password 'Password123!', Subject 'general', Message 'This is a test message.', and check the Terms checkbox. Then submit the form.",
            start_url=self.server.get_url("form_filling/index.html")
        )
        
        result.use_case = "form_filling"
        
        # Log result
        print(f"\n=== Form Filling Test Results ===")
        print(f"Success Rate: {result.success_rate:.1f}%")
        print(f"Actions: {result.successful_actions}/{result.total_actions}")
        print(f"Duration: {result.duration_seconds:.1f}s")
        
        # Assert minimum success rate
        assert result.success_rate >= self.threshold, \
            f"Success rate {result.success_rate:.1f}% is below threshold {self.threshold}%"
    
    @pytest.mark.asyncio
    async def test_llm_form_validation(self):
        """Test LLM handling form validation."""
        agent = LLMAgent(endpoint=self.endpoint, model=self.model)
        
        result = await agent.run_task(
            task_description="Try to submit the form without filling any fields. Verify that validation errors appear.",
            start_url=self.server.get_url("form_filling/index.html")
        )
        
        result.use_case = "form_filling_validation"
        
        print(f"\n=== Form Validation Test Results ===")
        print(f"Success Rate: {result.success_rate:.1f}%")
        
        # Lower threshold for validation test
        assert result.success_rate >= 50.0, \
            f"Success rate {result.success_rate:.1f}% is below threshold 50%"


class TestDataExtractionLLM:
    """LLM-based tests for data extraction use case."""
    
    @pytest.fixture(autouse=True)
    def setup(self, request):
        """Set up test fixtures."""
        self.port = request.config.getoption("--test-server-port", default=8765)
        self.endpoint = request.config.getoption("--llm-endpoint", default="http://localhost:1234/v1")
        self.model = request.config.getoption("--llm-model", default="local-model")
        self.threshold = request.config.getoption("--success-threshold", default=70.0)
        
        self.server = TestPageServer(self.port)
        self.server.start()
        
        yield
    
    @pytest.mark.asyncio
    async def test_llm_extract_products(self):
        """Test LLM extracting product information."""
        agent = LLMAgent(endpoint=self.endpoint, model=self.model)
        
        result = await agent.run_task(
            task_description="Count the number of products on the page and identify the cheapest product.",
            start_url=self.server.get_url("data_extraction/index.html")
        )
        
        result.use_case = "data_extraction"
        
        print(f"\n=== Data Extraction Test Results ===")
        print(f"Success Rate: {result.success_rate:.1f}%")
        
        assert result.success_rate >= 50.0, \
            f"Success rate {result.success_rate:.1f}% is below threshold 50%"


class TestWebScrapingLLM:
    """LLM-based tests for web scraping use case."""
    
    @pytest.fixture(autouse=True)
    def setup(self, request):
        """Set up test fixtures."""
        self.port = request.config.getoption("--test-server-port", default=8765)
        self.endpoint = request.config.getoption("--llm-endpoint", default="http://localhost:1234/v1")
        self.model = request.config.getoption("--llm-model", default="local-model")
        
        self.server = TestPageServer(self.port)
        self.server.start()
        
        yield
    
    @pytest.mark.asyncio
    async def test_llm_scrape_blog_posts(self):
        """Test LLM scraping blog posts."""
        agent = LLMAgent(endpoint=self.endpoint, model=self.model)
        
        result = await agent.run_task(
            task_description="Count the number of blog posts visible on the first page. Then navigate to page 2 and count the posts there.",
            start_url=self.server.get_url("web_scraping/index.html")
        )
        
        result.use_case = "web_scraping"
        
        print(f"\n=== Web Scraping Test Results ===")
        print(f"Success Rate: {result.success_rate:.1f}%")
        
        assert result.success_rate >= 50.0, \
            f"Success rate {result.success_rate:.1f}% is below threshold 50%"


class TestSearchResearchLLM:
    """LLM-based tests for search & research use case."""
    
    @pytest.fixture(autouse=True)
    def setup(self, request):
        """Set up test fixtures."""
        self.port = request.config.getoption("--test-server-port", default=8765)
        self.endpoint = request.config.getoption("--llm-endpoint", default="http://localhost:1234/v1")
        self.model = request.config.getoption("--llm-model", default="local-model")
        
        self.server = TestPageServer(self.port)
        self.server.start()
        
        yield
    
    @pytest.mark.asyncio
    async def test_llm_search(self):
        """Test LLM performing a search."""
        agent = LLMAgent(endpoint=self.endpoint, model=self.model)
        
        result = await agent.run_task(
            task_description="Search for 'machine learning' using the search box and verify that results appear.",
            start_url=self.server.get_url("search_research/index.html")
        )
        
        result.use_case = "search_research"
        
        print(f"\n=== Search & Research Test Results ===")
        print(f"Success Rate: {result.success_rate:.1f}%")
        
        assert result.success_rate >= 50.0, \
            f"Success rate {result.success_rate:.1f}% is below threshold 50%"


class TestWorkflowAutomationLLM:
    """LLM-based tests for workflow automation use case."""
    
    @pytest.fixture(autouse=True)
    def setup(self, request):
        """Set up test fixtures."""
        self.port = request.config.getoption("--test-server-port", default=8765)
        self.endpoint = request.config.getoption("--llm-endpoint", default="http://localhost:1234/v1")
        self.model = request.config.getoption("--llm-model", default="local-model")
        self.threshold = request.config.getoption("--success-threshold", default=70.0)
        
        self.server = TestPageServer(self.port)
        self.server.start()
        
        yield
    
    @pytest.mark.asyncio
    async def test_llm_login(self):
        """Test LLM logging in."""
        agent = LLMAgent(endpoint=self.endpoint, model=self.model)
        
        result = await agent.run_task(
            task_description="Log in with username 'demo' and password 'demo'. Wait for the dashboard to load.",
            start_url=self.server.get_url("workflow_automation/login.html")
        )
        
        result.use_case = "workflow_automation"
        
        print(f"\n=== Workflow Automation Test Results ===")
        print(f"Success Rate: {result.success_rate:.1f}%")
        
        assert result.success_rate >= 60.0, \
            f"Success rate {result.success_rate:.1f}% is below threshold 60%"


class TestEcommerceLLM:
    """LLM-based tests for e-commerce use case."""
    
    @pytest.fixture(autouse=True)
    def setup(self, request):
        """Set up test fixtures."""
        self.port = request.config.getoption("--test-server-port", default=8765)
        self.endpoint = request.config.getoption("--llm-endpoint", default="http://localhost:1234/v1")
        self.model = request.config.getoption("--llm-model", default="local-model")
        
        self.server = TestPageServer(self.port)
        self.server.start()
        
        yield
    
    @pytest.mark.asyncio
    async def test_llm_add_to_cart(self):
        """Test LLM adding product to cart."""
        agent = LLMAgent(endpoint=self.endpoint, model=self.model)
        
        result = await agent.run_task(
            task_description="Add the 'Wireless Headphones' product to the cart by clicking its 'Add to Cart' button.",
            start_url=self.server.get_url("ecommerce/index.html")
        )
        
        result.use_case = "ecommerce"
        
        print(f"\n=== E-commerce Test Results ===")
        print(f"Success Rate: {result.success_rate:.1f}%")
        
        assert result.success_rate >= 50.0, \
            f"Success rate {result.success_rate:.1f}% is below threshold 50%"


class TestSuccessRateReport:
    """Generate comprehensive success rate reports."""
    
    def test_report_generation(self, tmp_path):
        """Test that reports are generated correctly."""
        # Create sample result
        result = UseCaseTestResult(
            use_case="test",
            task_description="Sample task"
        )
        
        action = LLMAction(
            step_number=1,
            action_type="click",
            description="Click button",
            selector="#button",
            value=None,
            reasoning="Need to click the button"
        )
        
        result.action_results.append(LLMActionResult(
            action=action,
            success=True,
            expected_outcome="Button clicked",
            actual_outcome="Button was clicked"
        ))
        
        result.end_time = time.time()
        
        # Generate report
        report = result.to_dict()
        
        # Verify structure
        assert "use_case" in report
        assert "summary" in report
        assert "actions" in report
        assert report["summary"]["success_rate_percent"] == 100.0
        
        # Save report
        report_path = tmp_path / "test_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        assert report_path.exists()
        print(f"\nReport saved to: {report_path}")


def run_all_llm_tests(
    endpoint: str = "http://localhost:1234/v1",
    port: int = 8765,
    threshold: float = 70.0
) -> Dict[str, Any]:
    """
    Run all LLM tests and return aggregated results.
    
    Args:
        endpoint: LLM API endpoint
        port: Test server port
        threshold: Success rate threshold
        
    Returns:
        Dictionary with aggregated test results
    """
    import subprocess
    import sys
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_llm_use_cases.py",
        "-v",
        "--run-llm-tests",
        f"--llm-endpoint={endpoint}",
        f"--test-server-port={port}",
        f"--success-threshold={threshold}"
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.returncode == 0
    }


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([
        __file__,
        "-v",
        "--run-llm-tests",
        "--tb=short"
    ])

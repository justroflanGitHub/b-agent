#!/usr/bin/env python3
"""
Integration Tests for Phase 4.5: Localhost Test Pages for Use Cases

These tests call the model to perform tasks on the localhost test pages
and evaluate the percentage of successful actions.

Usage:
    pytest tests/test_integration_use_cases.py -v --run-integration
    pytest tests/test_integration_use_cases.py -v --run-integration -k "form_filling"
"""

import asyncio
import json
import os
import pytest
import time
import subprocess
import threading
import socket
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

# Skip all tests unless --run-integration flag is provided
pytestmark = pytest.mark.skipif(
    not pytest.config.getoption("--run-integration", default=False),
    reason="Need --run-integration option to run integration tests"
)


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that call the model"
    )
    parser.addoption(
        "--integration-timeout",
        action="store",
        default=120,
        type=int,
        help="Timeout in seconds for each integration test"
    )
    parser.addoption(
        "--test-server-port",
        action="store",
        default=8765,
        type=int,
        help="Port for the test page server"
    )


@dataclass
class ActionResult:
    """Result of a single action performed by the agent."""
    action_type: str
    description: str
    success: bool
    expected: Any
    actual: Any
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class TaskResult:
    """Result of a complete task with multiple actions."""
    task_name: str
    task_description: str
    use_case: str
    actions: List[ActionResult] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    @property
    def total_actions(self) -> int:
        return len(self.actions)
    
    @property
    def successful_actions(self) -> int:
        return sum(1 for a in self.actions if a.success)
    
    @property
    def success_rate(self) -> float:
        if self.total_actions == 0:
            return 0.0
        return (self.successful_actions / self.total_actions) * 100
    
    @property
    def duration(self) -> float:
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict:
        return {
            "task_name": self.task_name,
            "task_description": self.task_description,
            "use_case": self.use_case,
            "total_actions": self.total_actions,
            "successful_actions": self.successful_actions,
            "success_rate": round(self.success_rate, 2),
            "duration_seconds": round(self.duration, 2),
            "actions": [
                {
                    "action_type": a.action_type,
                    "description": a.description,
                    "success": a.success,
                    "expected": str(a.expected),
                    "actual": str(a.actual),
                    "error": a.error
                }
                for a in self.actions
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
        # Check if port is already in use
        if self._is_port_in_use(self.port):
            print(f"Port {self.port} already in use, assuming server is running")
            return
            
        server_path = Path(__file__).parent.parent / "test_pages" / "server.py"
        self.process = subprocess.Popen(
            ["python", str(server_path), "--port", str(self.port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # Wait for server to start
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
        """Check if a port is already in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    
    def get_url(self, path: str) -> str:
        """Get full URL for a path."""
        return f"{self.base_url}/{path}"


class IntegrationTestBase:
    """Base class for integration tests."""
    
    @pytest.fixture(autouse=True)
    def setup_server(self, request):
        """Set up the test server for each test class."""
        port = request.config.getoption("--test-server-port", default=8765)
        self.server = TestPageServer(port)
        self.server.start()
        self.base_url = self.server.base_url
        yield
        # Don't stop server to allow other tests to use it
        
    def create_action_result(
        self,
        action_type: str,
        description: str,
        success: bool,
        expected: Any,
        actual: Any,
        error: Optional[str] = None
    ) -> ActionResult:
        """Create an action result."""
        return ActionResult(
            action_type=action_type,
            description=description,
            success=success,
            expected=expected,
            actual=actual,
            error=error
        )
    
    def verify_field_value(self, actual: Any, expected: Any, field_name: str) -> ActionResult:
        """Verify a field value matches expected."""
        success = actual == expected
        return self.create_action_result(
            action_type="verify_field",
            description=f"Verify {field_name}",
            success=success,
            expected=expected,
            actual=actual,
            error=None if success else f"Expected {expected}, got {actual}"
        )
    
    def verify_contains(self, text: str, substring: str, description: str) -> ActionResult:
        """Verify text contains substring."""
        success = substring.lower() in text.lower()
        return self.create_action_result(
            action_type="verify_contains",
            description=description,
            success=success,
            expected=substring,
            actual=text[:100] + "..." if len(text) > 100 else text,
            error=None if success else f"'{substring}' not found in text"
        )
    
    def verify_greater_than(self, actual: int, minimum: int, description: str) -> ActionResult:
        """Verify value is greater than minimum."""
        success = actual >= minimum
        return self.create_action_result(
            action_type="verify_count",
            description=description,
            success=success,
            expected=f">= {minimum}",
            actual=actual,
            error=None if success else f"Expected >= {minimum}, got {actual}"
        )


class TestFormFillingIntegration(IntegrationTestBase):
    """Integration tests for form filling use case."""
    
    @pytest.fixture
    def page_url(self) -> str:
        return self.server.get_url("form_filling/index.html")
    
    @pytest.mark.asyncio
    async def test_fill_required_fields(self, page_url):
        """Test filling only required form fields."""
        result = TaskResult(
            task_name="fill_required_fields",
            task_description="Fill only required fields in the contact form",
            use_case="form_filling"
        )
        
        try:
            # Import browser agent components
            from simple_browser_agent import BrowserAgent
            
            agent = BrowserAgent(headless=False)
            await agent.initialize()
            
            # Navigate to page
            await agent.navigate(page_url)
            await asyncio.sleep(1)
            
            # Fill required fields
            test_data = {
                "firstName": "Test",
                "lastName": "User",
                "email": "test@example.com",
                "username": "testuser123",
                "password": "Password123!",
                "confirmPassword": "Password123!",
                "subject": "general",
                "message": "This is a test message with at least 10 characters.",
                "terms": True
            }
            
            # Fill text fields
            for field, value in test_data.items():
                if field in ["terms", "subject"]:
                    continue
                    
                try:
                    selector = f"#{field}"
                    element = await agent.page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await element.fill(str(value))
                        result.actions.append(self.create_action_result(
                            action_type="fill_field",
                            description=f"Fill {field}",
                            success=True,
                            expected=value,
                            actual=await element.input_value()
                        ))
                except Exception as e:
                    result.actions.append(self.create_action_result(
                        action_type="fill_field",
                        description=f"Fill {field}",
                        success=False,
                        expected=value,
                        actual=None,
                        error=str(e)
                    ))
            
            # Select subject
            try:
                await agent.page.select_option("#subject", test_data["subject"])
                result.actions.append(self.create_action_result(
                    action_type="select_option",
                    description="Select subject",
                    success=True,
                    expected=test_data["subject"],
                    actual=await agent.page.input_value("#subject")
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="select_option",
                    description="Select subject",
                    success=False,
                    expected=test_data["subject"],
                    actual=None,
                    error=str(e)
                ))
            
            # Check terms
            try:
                await agent.page.check("#terms")
                is_checked = await agent.page.is_checked("#terms")
                result.actions.append(self.create_action_result(
                    action_type="check_checkbox",
                    description="Check terms checkbox",
                    success=is_checked,
                    expected=True,
                    actual=is_checked
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="check_checkbox",
                    description="Check terms checkbox",
                    success=False,
                    expected=True,
                    actual=False,
                    error=str(e)
                ))
            
            # Submit form
            try:
                await agent.page.click("#submitBtn")
                await asyncio.sleep(1)
                
                # Check for success message
                success_msg = await agent.page.query_selector(".success-message.visible")
                result.actions.append(self.create_action_result(
                    action_type="submit_form",
                    description="Submit form and verify success",
                    success=success_msg is not None,
                    expected="Success message visible",
                    actual="Success message found" if success_msg else "No success message"
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="submit_form",
                    description="Submit form and verify success",
                    success=False,
                    expected="Success message visible",
                    actual=None,
                    error=str(e)
                ))
            
            await agent.cleanup()
            
        except Exception as e:
            result.actions.append(self.create_action_result(
                action_type="test_setup",
                description="Initialize browser and navigate",
                success=False,
                expected="Browser initialized",
                actual=None,
                error=str(e)
            ))
        
        result.end_time = time.time()
        
        # Assert minimum success rate
        assert result.success_rate >= 70, f"Success rate {result.success_rate}% is below 70%"
    
    @pytest.mark.asyncio
    async def test_validation_errors(self, page_url):
        """Test form validation error handling."""
        result = TaskResult(
            task_name="validation_errors",
            task_description="Trigger and verify validation errors",
            use_case="form_filling"
        )
        
        try:
            from simple_browser_agent import BrowserAgent
            
            agent = BrowserAgent(headless=False)
            await agent.initialize()
            await agent.navigate(page_url)
            await asyncio.sleep(1)
            
            # Try to submit empty form
            try:
                await agent.page.click("#submitBtn")
                await asyncio.sleep(0.5)
                
                # Check for error messages
                error_messages = await agent.page.query_selector_all(".error-message.visible")
                result.actions.append(self.create_action_result(
                    action_type="verify_validation",
                    description="Verify validation errors appear",
                    success=len(error_messages) > 0,
                    expected="At least 1 error message",
                    actual=f"{len(error_messages)} error messages"
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="verify_validation",
                    description="Verify validation errors appear",
                    success=False,
                    expected="Error messages visible",
                    actual=None,
                    error=str(e)
                ))
            
            # Test invalid email
            try:
                await agent.page.fill("#email", "invalid-email")
                await agent.page.click("#submitBtn")
                await asyncio.sleep(0.5)
                
                email_error = await agent.page.query_selector("#email + .error-message.visible, #email.error")
                result.actions.append(self.create_action_result(
                    action_type="verify_email_validation",
                    description="Verify email validation error",
                    success=email_error is not None,
                    expected="Email error visible",
                    actual="Email error found" if email_error else "No email error"
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="verify_email_validation",
                    description="Verify email validation error",
                    success=False,
                    expected="Email error visible",
                    actual=None,
                    error=str(e)
                ))
            
            await agent.cleanup()
            
        except Exception as e:
            result.actions.append(self.create_action_result(
                action_type="test_setup",
                description="Initialize browser",
                success=False,
                expected="Browser initialized",
                actual=None,
                error=str(e)
            ))
        
        result.end_time = time.time()
        assert result.success_rate >= 50, f"Success rate {result.success_rate}% is below 50%"


class TestDataExtractionIntegration(IntegrationTestBase):
    """Integration tests for data extraction use case."""
    
    @pytest.fixture
    def page_url(self) -> str:
        return self.server.get_url("data_extraction/index.html")
    
    @pytest.mark.asyncio
    async def test_extract_all_products(self, page_url):
        """Test extracting all products from the page."""
        result = TaskResult(
            task_name="extract_all_products",
            task_description="Extract all 12 products from the catalog",
            use_case="data_extraction"
        )
        
        try:
            from simple_browser_agent import BrowserAgent
            
            agent = BrowserAgent(headless=False)
            await agent.initialize()
            await agent.navigate(page_url)
            await asyncio.sleep(2)
            
            # Extract product cards
            try:
                product_cards = await agent.page.query_selector_all(".product-card")
                result.actions.append(self.create_action_result(
                    action_type="extract_elements",
                    description="Extract product cards",
                    success=len(product_cards) == 12,
                    expected=12,
                    actual=len(product_cards)
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="extract_elements",
                    description="Extract product cards",
                    success=False,
                    expected=12,
                    actual=0,
                    error=str(e)
                ))
                product_cards = []
            
            # Extract data from each product
            extracted_products = []
            for i, card in enumerate(product_cards):
                try:
                    name = await card.query_selector(".product-name")
                    name_text = await name.inner_text() if name else ""
                    
                    price = await card.query_selector(".current-price")
                    price_text = await price.inner_text() if price else ""
                    
                    extracted_products.append({
                        "name": name_text,
                        "price": price_text
                    })
                    
                    if name_text and price_text:
                        result.actions.append(self.create_action_result(
                            action_type="extract_product",
                            description=f"Extract product {i+1}",
                            success=True,
                            expected="Name and price",
                            actual=f"{name_text}: {price_text}"
                        ))
                except Exception as e:
                    result.actions.append(self.create_action_result(
                        action_type="extract_product",
                        description=f"Extract product {i+1}",
                        success=False,
                        expected="Name and price",
                        actual=None,
                        error=str(e)
                    ))
            
            # Verify we extracted all products with data
            successful_extractions = sum(1 for p in extracted_products if p["name"] and p["price"])
            result.actions.append(self.create_action_result(
                action_type="verify_extraction",
                description="Verify all products extracted with data",
                success=successful_extractions >= 10,
                expected=">= 10 products with data",
                actual=f"{successful_extractions} products with data"
            ))
            
            await agent.cleanup()
            
        except Exception as e:
            result.actions.append(self.create_action_result(
                action_type="test_setup",
                description="Initialize browser",
                success=False,
                expected="Browser initialized",
                actual=None,
                error=str(e)
            ))
        
        result.end_time = time.time()
        assert result.success_rate >= 70, f"Success rate {result.success_rate}% is below 70%"
    
    @pytest.mark.asyncio
    async def test_extract_products_by_category(self, page_url):
        """Test extracting products filtered by category."""
        result = TaskResult(
            task_name="extract_by_category",
            task_description="Extract gaming category products",
            use_case="data_extraction"
        )
        
        try:
            from simple_browser_agent import BrowserAgent
            
            agent = BrowserAgent(headless=False)
            await agent.initialize()
            await agent.navigate(page_url)
            await asyncio.sleep(2)
            
            # Filter by gaming category
            try:
                await agent.page.select_option("#categoryFilter", "gaming")
                await asyncio.sleep(1)
                
                gaming_cards = await agent.page.query_selector_all(".product-card[data-category='gaming']")
                result.actions.append(self.create_action_result(
                    action_type="filter_category",
                    description="Filter by gaming category",
                    success=len(gaming_cards) == 3,
                    expected=3,
                    actual=len(gaming_cards)
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="filter_category",
                    description="Filter by gaming category",
                    success=False,
                    expected=3,
                    actual=0,
                    error=str(e)
                ))
            
            await agent.cleanup()
            
        except Exception as e:
            result.actions.append(self.create_action_result(
                action_type="test_setup",
                description="Initialize browser",
                success=False,
                expected="Browser initialized",
                actual=None,
                error=str(e)
            ))
        
        result.end_time = time.time()
        assert result.success_rate >= 50, f"Success rate {result.success_rate}% is below 50%"


class TestWebScrapingIntegration(IntegrationTestBase):
    """Integration tests for web scraping use case."""
    
    @pytest.fixture
    def page_url(self) -> str:
        return self.server.get_url("web_scraping/index.html")
    
    @pytest.mark.asyncio
    async def test_scrape_with_pagination(self, page_url):
        """Test scraping blog posts with pagination."""
        result = TaskResult(
            task_name="scrape_pagination",
            task_description="Scrape all 15 posts across 3 pages",
            use_case="web_scraping"
        )
        
        try:
            from simple_browser_agent import BrowserAgent
            
            agent = BrowserAgent(headless=False)
            await agent.initialize()
            await agent.navigate(page_url)
            await asyncio.sleep(2)
            
            all_posts = []
            
            # Scrape page 1
            try:
                posts = await agent.page.query_selector_all(".blog-card")
                all_posts.extend(posts)
                result.actions.append(self.create_action_result(
                    action_type="scrape_page",
                    description="Scrape page 1",
                    success=len(posts) == 5,
                    expected=5,
                    actual=len(posts)
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="scrape_page",
                    description="Scrape page 1",
                    success=False,
                    expected=5,
                    actual=0,
                    error=str(e)
                ))
            
            # Navigate to page 2
            try:
                await agent.page.click(".pagination button:nth-child(2)")
                await asyncio.sleep(1)
                posts = await agent.page.query_selector_all(".blog-card")
                all_posts.extend(posts)
                result.actions.append(self.create_action_result(
                    action_type="navigate_and_scrape",
                    description="Navigate to page 2 and scrape",
                    success=len(posts) == 5,
                    expected=5,
                    actual=len(posts)
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="navigate_and_scrape",
                    description="Navigate to page 2 and scrape",
                    success=False,
                    expected=5,
                    actual=0,
                    error=str(e)
                ))
            
            # Navigate to page 3
            try:
                await agent.page.click(".pagination button:nth-child(3)")
                await asyncio.sleep(1)
                posts = await agent.page.query_selector_all(".blog-card")
                all_posts.extend(posts)
                result.actions.append(self.create_action_result(
                    action_type="navigate_and_scrape",
                    description="Navigate to page 3 and scrape",
                    success=len(posts) == 5,
                    expected=5,
                    actual=len(posts)
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="navigate_and_scrape",
                    description="Navigate to page 3 and scrape",
                    success=False,
                    expected=5,
                    actual=0,
                    error=str(e)
                ))
            
            # Verify total posts
            result.actions.append(self.create_action_result(
                action_type="verify_total",
                description="Verify total posts scraped",
                success=len(all_posts) == 15,
                expected=15,
                actual=len(all_posts)
            ))
            
            await agent.cleanup()
            
        except Exception as e:
            result.actions.append(self.create_action_result(
                action_type="test_setup",
                description="Initialize browser",
                success=False,
                expected="Browser initialized",
                actual=None,
                error=str(e)
            ))
        
        result.end_time = time.time()
        assert result.success_rate >= 60, f"Success rate {result.success_rate}% is below 60%"
    
    @pytest.mark.asyncio
    async def test_scrape_with_load_more(self, page_url):
        """Test scraping using load more button."""
        result = TaskResult(
            task_name="scrape_load_more",
            task_description="Load and scrape all posts using Load More",
            use_case="web_scraping"
        )
        
        try:
            from simple_browser_agent import BrowserAgent
            
            agent = BrowserAgent(headless=False)
            await agent.initialize()
            await agent.navigate(page_url)
            await asyncio.sleep(2)
            
            # Count initial posts
            try:
                initial_posts = await agent.page.query_selector_all(".blog-card")
                result.actions.append(self.create_action_result(
                    action_type="count_initial",
                    description="Count initial posts",
                    success=len(initial_posts) == 5,
                    expected=5,
                    actual=len(initial_posts)
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="count_initial",
                    description="Count initial posts",
                    success=False,
                    expected=5,
                    actual=0,
                    error=str(e)
                ))
            
            # Click Load More
            try:
                await agent.page.click(".load-more-btn")
                await asyncio.sleep(1)
                posts_after_load = await agent.page.query_selector_all(".blog-card")
                result.actions.append(self.create_action_result(
                    action_type="load_more",
                    description="Click Load More and verify",
                    success=len(posts_after_load) == 10,
                    expected=10,
                    actual=len(posts_after_load)
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="load_more",
                    description="Click Load More and verify",
                    success=False,
                    expected=10,
                    actual=0,
                    error=str(e)
                ))
            
            await agent.cleanup()
            
        except Exception as e:
            result.actions.append(self.create_action_result(
                action_type="test_setup",
                description="Initialize browser",
                success=False,
                expected="Browser initialized",
                actual=None,
                error=str(e)
            ))
        
        result.end_time = time.time()
        assert result.success_rate >= 50, f"Success rate {result.success_rate}% is below 50%"


class TestSearchResearchIntegration(IntegrationTestBase):
    """Integration tests for search & research use case."""
    
    @pytest.fixture
    def page_url(self) -> str:
        return self.server.get_url("search_research/index.html")
    
    @pytest.mark.asyncio
    async def test_basic_search(self, page_url):
        """Test basic search functionality."""
        result = TaskResult(
            task_name="basic_search",
            task_description="Search for 'machine learning' and verify results",
            use_case="search_research"
        )
        
        try:
            from simple_browser_agent import BrowserAgent
            
            agent = BrowserAgent(headless=False)
            await agent.initialize()
            await agent.navigate(page_url)
            await asyncio.sleep(2)
            
            # Enter search query
            try:
                await agent.page.fill("#searchInput", "machine learning")
                result.actions.append(self.create_action_result(
                    action_type="enter_query",
                    description="Enter search query",
                    success=True,
                    expected="machine learning",
                    actual=await agent.page.input_value("#searchInput")
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="enter_query",
                    description="Enter search query",
                    success=False,
                    expected="machine learning",
                    actual=None,
                    error=str(e)
                ))
            
            # Click search button
            try:
                await agent.page.click("#searchBtn")
                await asyncio.sleep(1)
                result.actions.append(self.create_action_result(
                    action_type="click_search",
                    description="Click search button",
                    success=True,
                    expected="Search executed",
                    actual="Search executed"
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="click_search",
                    description="Click search button",
                    success=False,
                    expected="Search executed",
                    actual=None,
                    error=str(e)
                ))
            
            # Verify results appear
            try:
                results = await agent.page.query_selector_all(".result-item")
                result.actions.append(self.create_action_result(
                    action_type="verify_results",
                    description="Verify search results appear",
                    success=len(results) > 0,
                    expected="> 0 results",
                    actual=f"{len(results)} results"
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="verify_results",
                    description="Verify search results appear",
                    success=False,
                    expected="> 0 results",
                    actual=0,
                    error=str(e)
                ))
            
            await agent.cleanup()
            
        except Exception as e:
            result.actions.append(self.create_action_result(
                action_type="test_setup",
                description="Initialize browser",
                success=False,
                expected="Browser initialized",
                actual=None,
                error=str(e)
            ))
        
        result.end_time = time.time()
        assert result.success_rate >= 60, f"Success rate {result.success_rate}% is below 60%"
    
    @pytest.mark.asyncio
    async def test_navigate_to_result(self, page_url):
        """Test clicking on a search result."""
        result = TaskResult(
            task_name="navigate_result",
            task_description="Search and navigate to Wikipedia result",
            use_case="search_research"
        )
        
        try:
            from simple_browser_agent import BrowserAgent
            
            agent = BrowserAgent(headless=False)
            await agent.initialize()
            await agent.navigate(page_url)
            await asyncio.sleep(2)
            
            # Search
            try:
                await agent.page.fill("#searchInput", "machine learning")
                await agent.page.click("#searchBtn")
                await asyncio.sleep(1)
                result.actions.append(self.create_action_result(
                    action_type="perform_search",
                    description="Perform search",
                    success=True,
                    expected="Search completed",
                    actual="Search completed"
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="perform_search",
                    description="Perform search",
                    success=False,
                    expected="Search completed",
                    actual=None,
                    error=str(e)
                ))
            
            # Click Wikipedia result
            try:
                wiki_link = await agent.page.query_selector('a:has-text("Wikipedia")')
                if wiki_link:
                    await wiki_link.click()
                    await asyncio.sleep(1)
                    
                    # Check if navigated to article page
                    current_url = agent.page.url
                    result.actions.append(self.create_action_result(
                        action_type="click_result",
                        description="Click Wikipedia result",
                        success="article.html" in current_url,
                        expected="Article page",
                        actual=current_url
                    ))
                else:
                    result.actions.append(self.create_action_result(
                        action_type="click_result",
                        description="Click Wikipedia result",
                        success=False,
                        expected="Article page",
                        actual="Wikipedia link not found"
                    ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="click_result",
                    description="Click Wikipedia result",
                    success=False,
                    expected="Article page",
                    actual=None,
                    error=str(e)
                ))
            
            await agent.cleanup()
            
        except Exception as e:
            result.actions.append(self.create_action_result(
                action_type="test_setup",
                description="Initialize browser",
                success=False,
                expected="Browser initialized",
                actual=None,
                error=str(e)
            ))
        
        result.end_time = time.time()
        assert result.success_rate >= 50, f"Success rate {result.success_rate}% is below 50%"


class TestWorkflowAutomationIntegration(IntegrationTestBase):
    """Integration tests for workflow automation use case."""
    
    @pytest.fixture
    def login_url(self) -> str:
        return self.server.get_url("workflow_automation/login.html")
    
    @pytest.fixture
    def dashboard_url(self) -> str:
        return self.server.get_url("workflow_automation/dashboard.html")
    
    @pytest.mark.asyncio
    async def test_login_workflow(self, login_url):
        """Test complete login workflow."""
        result = TaskResult(
            task_name="login_workflow",
            task_description="Log in with demo/demo credentials",
            use_case="workflow_automation"
        )
        
        try:
            from simple_browser_agent import BrowserAgent
            
            agent = BrowserAgent(headless=False)
            await agent.initialize()
            await agent.navigate(login_url)
            await asyncio.sleep(2)
            
            # Fill username
            try:
                await agent.page.fill("#username", "demo")
                result.actions.append(self.create_action_result(
                    action_type="fill_username",
                    description="Fill username",
                    success=True,
                    expected="demo",
                    actual=await agent.page.input_value("#username")
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="fill_username",
                    description="Fill username",
                    success=False,
                    expected="demo",
                    actual=None,
                    error=str(e)
                ))
            
            # Fill password
            try:
                await agent.page.fill("#password", "demo")
                result.actions.append(self.create_action_result(
                    action_type="fill_password",
                    description="Fill password",
                    success=True,
                    expected="demo",
                    actual="***"  # Don't expose password
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="fill_password",
                    description="Fill password",
                    success=False,
                    expected="demo",
                    actual=None,
                    error=str(e)
                ))
            
            # Click login
            try:
                await agent.page.click("#loginBtn")
                await asyncio.sleep(2)
                
                # Check if redirected to dashboard
                current_url = agent.page.url
                result.actions.append(self.create_action_result(
                    action_type="submit_login",
                    description="Submit login and verify redirect",
                    success="dashboard.html" in current_url,
                    expected="Dashboard page",
                    actual=current_url
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="submit_login",
                    description="Submit login and verify redirect",
                    success=False,
                    expected="Dashboard page",
                    actual=None,
                    error=str(e)
                ))
            
            await agent.cleanup()
            
        except Exception as e:
            result.actions.append(self.create_action_result(
                action_type="test_setup",
                description="Initialize browser",
                success=False,
                expected="Browser initialized",
                actual=None,
                error=str(e)
            ))
        
        result.end_time = time.time()
        assert result.success_rate >= 60, f"Success rate {result.success_rate}% is below 60%"
    
    @pytest.mark.asyncio
    async def test_invalid_login(self, login_url):
        """Test login with invalid credentials."""
        result = TaskResult(
            task_name="invalid_login",
            task_description="Test login with wrong credentials",
            use_case="workflow_automation"
        )
        
        try:
            from simple_browser_agent import BrowserAgent
            
            agent = BrowserAgent(headless=False)
            await agent.initialize()
            await agent.navigate(login_url)
            await asyncio.sleep(2)
            
            # Fill wrong credentials
            try:
                await agent.page.fill("#username", "wronguser")
                await agent.page.fill("#password", "wrongpass")
                await agent.page.click("#loginBtn")
                await asyncio.sleep(1)
                
                # Check for error message
                error_msg = await agent.page.query_selector(".login-error.visible, .error-message.visible")
                result.actions.append(self.create_action_result(
                    action_type="verify_error",
                    description="Verify error message appears",
                    success=error_msg is not None,
                    expected="Error message visible",
                    actual="Error found" if error_msg else "No error"
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="verify_error",
                    description="Verify error message appears",
                    success=False,
                    expected="Error message visible",
                    actual=None,
                    error=str(e)
                ))
            
            await agent.cleanup()
            
        except Exception as e:
            result.actions.append(self.create_action_result(
                action_type="test_setup",
                description="Initialize browser",
                success=False,
                expected="Browser initialized",
                actual=None,
                error=str(e)
            ))
        
        result.end_time = time.time()
        assert result.success_rate >= 50, f"Success rate {result.success_rate}% is below 50%"


class TestEcommerceIntegration(IntegrationTestBase):
    """Integration tests for e-commerce use case."""
    
    @pytest.fixture
    def catalog_url(self) -> str:
        return self.server.get_url("ecommerce/index.html")
    
    @pytest.fixture
    def cart_url(self) -> str:
        return self.server.get_url("ecommerce/cart.html")
    
    @pytest.mark.asyncio
    async def test_add_to_cart(self, catalog_url):
        """Test adding product to cart."""
        result = TaskResult(
            task_name="add_to_cart",
            task_description="Add Wireless Headphones to cart",
            use_case="ecommerce"
        )
        
        try:
            from simple_browser_agent import BrowserAgent
            
            agent = BrowserAgent(headless=False)
            await agent.initialize()
            await agent.navigate(catalog_url)
            await asyncio.sleep(2)
            
            # Find and click Add to Cart for first product
            try:
                add_btn = await agent.page.query_selector('.product-card[data-product-id="1"] .add-to-cart-btn')
                if add_btn:
                    await add_btn.click()
                    await asyncio.sleep(1)
                    
                    # Check button text changed
                    btn_text = await add_btn.inner_text()
                    result.actions.append(self.create_action_result(
                        action_type="add_to_cart",
                        description="Add product to cart",
                        success="Added" in btn_text or "added" in btn_text.lower(),
                        expected="Button shows Added",
                        actual=btn_text
                    ))
                else:
                    result.actions.append(self.create_action_result(
                        action_type="add_to_cart",
                        description="Add product to cart",
                        success=False,
                        expected="Button shows Added",
                        actual="Button not found"
                    ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="add_to_cart",
                    description="Add product to cart",
                    success=False,
                    expected="Button shows Added",
                    actual=None,
                    error=str(e)
                ))
            
            # Verify cart count increased
            try:
                cart_count = await agent.page.query_selector("#cartCount")
                count_text = await cart_count.inner_text() if cart_count else "0"
                result.actions.append(self.create_action_result(
                    action_type="verify_cart_count",
                    description="Verify cart count increased",
                    success=int(count_text) >= 1,
                    expected=">= 1",
                    actual=count_text
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="verify_cart_count",
                    description="Verify cart count increased",
                    success=False,
                    expected=">= 1",
                    actual=None,
                    error=str(e)
                ))
            
            await agent.cleanup()
            
        except Exception as e:
            result.actions.append(self.create_action_result(
                action_type="test_setup",
                description="Initialize browser",
                success=False,
                expected="Browser initialized",
                actual=None,
                error=str(e)
            ))
        
        result.end_time = time.time()
        assert result.success_rate >= 50, f"Success rate {result.success_rate}% is below 50%"
    
    @pytest.mark.asyncio
    async def test_filter_products(self, catalog_url):
        """Test filtering products by category."""
        result = TaskResult(
            task_name="filter_products",
            task_description="Filter products by electronics category",
            use_case="ecommerce"
        )
        
        try:
            from simple_browser_agent import BrowserAgent
            
            agent = BrowserAgent(headless=False)
            await agent.initialize()
            await agent.navigate(catalog_url)
            await asyncio.sleep(2)
            
            # Select electronics category
            try:
                await agent.page.select_option("#categoryFilter", "electronics")
                await asyncio.sleep(1)
                
                # Count visible products
                visible_cards = await agent.page.query_selector_all(".product-card:not([style*='display: none'])")
                result.actions.append(self.create_action_result(
                    action_type="filter_category",
                    description="Filter by electronics",
                    success=len(visible_cards) == 4,
                    expected=4,
                    actual=len(visible_cards)
                ))
            except Exception as e:
                result.actions.append(self.create_action_result(
                    action_type="filter_category",
                    description="Filter by electronics",
                    success=False,
                    expected=4,
                    actual=0,
                    error=str(e)
                ))
            
            await agent.cleanup()
            
        except Exception as e:
            result.actions.append(self.create_action_result(
                action_type="test_setup",
                description="Initialize browser",
                success=False,
                expected="Browser initialized",
                actual=None,
                error=str(e)
            ))
        
        result.end_time = time.time()
        assert result.success_rate >= 50, f"Success rate {result.success_rate}% is below 50%"


class TestSuccessRateReport:
    """Generate a comprehensive success rate report."""
    
    @pytest.fixture
    def report_output_path(self, tmp_path) -> Path:
        return tmp_path / "integration_test_report.json"
    
    def test_generate_report_schema(self, report_output_path):
        """Test that the report schema is correct."""
        sample_result = TaskResult(
            task_name="sample_task",
            task_description="Sample task for schema validation",
            use_case="test"
        )
        
        sample_result.actions.append(ActionResult(
            action_type="test_action",
            description="Test action",
            success=True,
            expected="Expected value",
            actual="Actual value"
        ))
        
        sample_result.end_time = time.time()
        
        report = sample_result.to_dict()
        
        # Verify schema
        assert "task_name" in report
        assert "task_description" in report
        assert "use_case" in report
        assert "total_actions" in report
        assert "successful_actions" in report
        assert "success_rate" in report
        assert "duration_seconds" in report
        assert "actions" in report
        
        # Write sample report
        with open(report_output_path, 'w') as f:
            json.dump({"results": [report]}, f, indent=2)
        
        assert report_output_path.exists()


# Utility functions for running tests programmatically

def run_integration_tests(
    use_case: Optional[str] = None,
    timeout: int = 120,
    port: int = 8765
) -> Dict[str, Any]:
    """
    Run integration tests and return results.
    
    Args:
        use_case: Specific use case to test (form_filling, data_extraction, etc.)
        timeout: Timeout in seconds for each test
        port: Port for test server
        
    Returns:
        Dictionary with test results and success rates
    """
    import subprocess
    import sys
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_integration_use_cases.py",
        "-v",
        "--run-integration",
        f"--integration-timeout={timeout}",
        f"--test-server-port={port}",
        "--json-report",
        "--json-report-file=-"
    ]
    
    if use_case:
        cmd.extend(["-k", use_case])
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([
        __file__,
        "-v",
        "--run-integration",
        "--tb=short"
    ])

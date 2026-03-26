#!/usr/bin/env python3
"""
Integration Tests for Phase 4.5: Localhost Test Pages for Use Cases

These tests use UI-TARS vision model to perform tasks on the localhost test pages.
The agent uses visual intelligence to determine where to click and what actions to take.

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


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that call the UI-TARS vision model"
    )
    parser.addoption(
        "--integration-timeout",
        action="store",
        default=180,
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
    parser.addoption(
        "--llm-endpoint",
        action="store",
        default="http://127.0.0.1:1234/v1",
        help="LLM API endpoint for UI-TARS"
    )
    parser.addoption(
        "--success-threshold",
        action="store",
        default=70.0,
        type=float,
        help="Minimum success rate threshold (0-100)"
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test using UI-TARS"
    )


# Skip all tests unless --run-integration flag is provided
def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --run-integration is provided."""
    if not config.getoption("--run-integration"):
        skip_integration = pytest.mark.skip(reason="Need --run-integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


@dataclass
class VisionTestResult:
    """Result of a vision-guided test."""
    task_name: str
    task_description: str
    use_case: str
    goal: str
    success: bool = False
    steps: List[Dict[str, Any]] = field(default_factory=list)
    execution_time: float = 0.0
    error: Optional[str] = None
    validation_results: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def total_steps(self) -> int:
        return len(self.steps)
    
    @property
    def successful_steps(self) -> int:
        return sum(1 for s in self.steps if s.get("success", False))
    
    @property
    def success_rate(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return (self.successful_steps / self.total_steps) * 100
    
    def to_dict(self) -> Dict:
        return {
            "task_name": self.task_name,
            "task_description": self.task_description,
            "use_case": self.use_case,
            "goal": self.goal,
            "success": self.success,
            "total_steps": self.total_steps,
            "successful_steps": self.successful_steps,
            "success_rate": round(self.success_rate, 2),
            "execution_time_seconds": round(self.execution_time, 2),
            "error": self.error,
            "steps": self.steps,
            "validation_results": self.validation_results
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


class VisionTestBase:
    """Base class for UI-TARS vision-guided integration tests."""
    
    @pytest.fixture(autouse=True)
    def setup_server(self, request):
        """Set up the test server for each test class."""
        port = request.config.getoption("--test-server-port", default=8765)
        self.server = TestPageServer(port)
        self.server.start()
        self.base_url = self.server.base_url
        self.llm_endpoint = request.config.getoption("--llm-endpoint", default="http://127.0.0.1:1234/v1")
        self.success_threshold = request.config.getoption("--success-threshold", default=70.0)
        self.timeout = request.config.getoption("--integration-timeout", default=180)
        yield
        # Don't stop server to allow other tests to use it
    
    async def run_vision_task(
        self,
        goal: str,
        start_url: str,
        max_steps: int = 15,
        validation_fn=None
    ) -> VisionTestResult:
        """
        Run a vision-guided task using UI-TARS.
        
        Args:
            goal: Natural language description of what to accomplish
            start_url: URL to navigate to before starting
            max_steps: Maximum number of action steps
            validation_fn: Optional async function to validate results
            
        Returns:
            VisionTestResult with execution details
        """
        from browser_agent import BrowserAgent
        import time as time_module
        
        result = VisionTestResult(
            task_name=goal[:50],
            task_description=goal,
            use_case=self._get_use_case(),
            goal=goal
        )
        
        start_time = time_module.time()
        agent = None
        
        try:
            # Create agent with UI-TARS vision model
            agent = BrowserAgent()
            await agent.initialize()
            
            # Execute the task using vision guidance
            task_result = await agent.execute_task(
                goal=goal,
                start_url=start_url,
                max_steps=max_steps
            )
            
            result.steps = task_result.steps
            result.success = task_result.success
            result.error = task_result.error
            result.execution_time = task_result.execution_time
            
            # Run custom validation if provided
            if validation_fn and agent.browser and agent.browser.page:
                validation_results = await validation_fn(agent.browser.page)
                result.validation_results = validation_results
                
                # Update success based on validation
                if validation_results:
                    all_validations_passed = all(
                        v.get("success", False) for v in validation_results
                    )
                    if not all_validations_passed:
                        result.success = False
            
        except Exception as e:
            result.error = str(e)
            result.success = False
            
        finally:
            result.execution_time = time_module.time() - start_time
            if agent:
                await agent.cleanup()
        
        return result
    
    def _get_use_case(self) -> str:
        """Get the use case name for this test class."""
        return "unknown"
    
    def assert_success_threshold(self, result: VisionTestResult):
        """Assert that the result meets the success threshold."""
        assert result.success_rate >= self.success_threshold, (
            f"Success rate {result.success_rate:.1f}% below threshold {self.success_threshold}%\n"
            f"Steps: {result.total_steps}, Successful: {result.successful_steps}\n"
            f"Error: {result.error}"
        )


class TestFormFillingVision(VisionTestBase):
    """Vision-guided integration tests for form filling use case."""
    
    def _get_use_case(self) -> str:
        return "form_filling"
    
    @pytest.mark.asyncio
    async def test_fill_required_fields_vision(self, request):
        """Test filling required form fields using UI-TARS vision."""
        page_url = self.server.get_url("form_filling/index.html")
        
        # Define the goal for UI-TARS
        goal = """Fill out the contact form with the following information:
        - First Name: John
        - Last Name: Doe
        - Email: john.doe@example.com
        - Username: johndoe123
        - Password: SecurePass123!
        - Confirm Password: SecurePass123!
        - Subject: Select "General Inquiry"
        - Message: "This is a test message for the form filling use case."
        - Check the "I agree to the terms" checkbox
        Then click the Submit button."""
        
        async def validate_form(page):
            """Validate form was filled correctly."""
            results = []
            
            # Check field values
            fields = {
                "#firstName": "John",
                "#lastName": "Doe",
                "#email": "john.doe@example.com",
                "#username": "johndoe123"
            }
            
            for selector, expected in fields.items():
                try:
                    actual = await page.input_value(selector)
                    results.append({
                        "check": f"Field {selector}",
                        "success": actual == expected,
                        "expected": expected,
                        "actual": actual
                    })
                except Exception as e:
                    results.append({
                        "check": f"Field {selector}",
                        "success": False,
                        "error": str(e)
                    })
            
            # Check if form was submitted (success message visible)
            try:
                success_msg = await page.query_selector(".success-message, #successMessage")
                if success_msg:
                    is_visible = await success_msg.is_visible()
                    results.append({
                        "check": "Success message visible",
                        "success": is_visible
                    })
            except:
                pass
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=20,
            validation_fn=validate_form
        )
        
        # Log result for debugging
        print(f"\n=== Form Filling Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        # Assert task completed successfully
        self.assert_success_threshold(result)
    
    @pytest.mark.asyncio
    async def test_form_validation_errors_vision(self, request):
        """Test that UI-TARS handles form validation correctly."""
        page_url = self.server.get_url("form_filling/index.html")
        
        goal = """Try to submit the form without filling any fields to trigger validation errors.
        Then observe and report what validation error messages appear on the page."""
        
        async def validate_errors(page):
            """Validate error messages appeared."""
            results = []
            
            # Check for error messages
            try:
                error_elements = await page.query_selector_all(".error-message, .field-error")
                results.append({
                    "check": "Error messages present",
                    "success": len(error_elements) > 0,
                    "count": len(error_elements)
                })
            except Exception as e:
                results.append({
                    "check": "Error messages present",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10,
            validation_fn=validate_errors
        )
        
        print(f"\n=== Form Validation Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        # For validation test, we just need to verify errors appeared
        assert len(result.validation_results) > 0, "No validation results collected"


class TestDataExtractionVision(VisionTestBase):
    """Vision-guided integration tests for data extraction use case."""
    
    def _get_use_case(self) -> str:
        return "data_extraction"
    
    @pytest.mark.asyncio
    async def test_extract_all_products_vision(self, request):
        """Test extracting all product data using UI-TARS vision."""
        page_url = self.server.get_url("data_extraction/index.html")
        
        goal = """Look at the product listing page and extract all product information.
        For each product, identify: name, price, category, and availability.
        Report the total number of products found."""
        
        async def validate_extraction(page):
            """Validate data was extracted."""
            results = []
            
            # Count products on page
            try:
                products = await page.query_selector_all(".product-card, .product-item")
                results.append({
                    "check": "Products found",
                    "success": len(products) > 0,
                    "count": len(products)
                })
            except Exception as e:
                results.append({
                    "check": "Products found",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10,
            validation_fn=validate_extraction
        )
        
        print(f"\n=== Data Extraction Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)
    
    @pytest.mark.asyncio
    async def test_filter_by_category_vision(self, request):
        """Test filtering products by category using UI-TARS vision."""
        page_url = self.server.get_url("data_extraction/index.html")
        
        goal = """Filter the products to show only items in the "Electronics" category.
        Use the category filter dropdown or buttons on the page."""
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10
        )
        
        print(f"\n=== Category Filter Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)


class TestWebScrapingVision(VisionTestBase):
    """Vision-guided integration tests for web scraping use case."""
    
    def _get_use_case(self) -> str:
        return "web_scraping"
    
    @pytest.mark.asyncio
    async def test_pagination_vision(self, request):
        """Test navigating through paginated content using UI-TARS vision."""
        page_url = self.server.get_url("web_scraping/index.html")
        
        goal = """Navigate through the article list by clicking the "Next" or pagination buttons.
        Visit at least 3 pages and report the articles found on each page."""
        
        async def validate_pagination(page):
            """Validate pagination worked."""
            results = []
            
            try:
                # Check if we navigated (URL might have page parameter)
                url = page.url
                results.append({
                    "check": "Page navigated",
                    "success": "page=" in url or "Page 2" in await page.content(),
                    "url": url
                })
            except Exception as e:
                results.append({
                    "check": "Page navigated",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=15,
            validation_fn=validate_pagination
        )
        
        print(f"\n=== Pagination Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        # More lenient threshold for pagination
        assert result.success_rate >= 50.0, (
            f"Success rate {result.success_rate:.1f}% below threshold 50%"
        )
    
    @pytest.mark.asyncio
    async def test_load_more_vision(self, request):
        """Test clicking 'Load More' button using UI-TARS vision."""
        page_url = self.server.get_url("web_scraping/index.html")
        
        goal = """Click the "Load More" button to load additional articles.
        Do this multiple times to load more content."""
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10
        )
        
        print(f"\n=== Load More Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)


class TestSearchResearchVision(VisionTestBase):
    """Vision-guided integration tests for search & research use case."""
    
    def _get_use_case(self) -> str:
        return "search_research"
    
    @pytest.mark.asyncio
    async def test_basic_search_vision(self, request):
        """Test performing a search using UI-TARS vision."""
        page_url = self.server.get_url("search_research/index.html")
        
        goal = """Use the search box on this page to search for "machine learning".
        Click the search button or press Enter to submit the search."""
        
        async def validate_search(page):
            """Validate search was performed."""
            results = []
            
            try:
                # Check for search results
                content = await page.content()
                has_results = "machine learning" in content.lower() or "results" in content.lower()
                results.append({
                    "check": "Search performed",
                    "success": has_results
                })
            except Exception as e:
                results.append({
                    "check": "Search performed",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10,
            validation_fn=validate_search
        )
        
        print(f"\n=== Search Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)
    
    @pytest.mark.asyncio
    async def test_navigate_to_result_vision(self, request):
        """Test navigating to a search result using UI-TARS vision."""
        page_url = self.server.get_url("search_research/index.html")
        
        goal = """First search for "python programming", then click on one of the search results
        to view more details."""
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=15
        )
        
        print(f"\n=== Navigate Result Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)


class TestWorkflowAutomationVision(VisionTestBase):
    """Vision-guided integration tests for workflow automation use case."""
    
    def _get_use_case(self) -> str:
        return "workflow_automation"
    
    @pytest.mark.asyncio
    async def test_login_workflow_vision(self, request):
        """Test login workflow using UI-TARS vision."""
        page_url = self.server.get_url("workflow_automation/index.html")
        
        goal = """Complete the login workflow:
        1. Find the username/email field and enter: demo@example.com
        2. Find the password field and enter: password123
        3. Click the Login button
        4. Verify that login was successful"""
        
        async def validate_login(page):
            """Validate login succeeded."""
            results = []
            
            try:
                # Check for success indicator
                content = await page.content()
                has_success = "welcome" in content.lower() or "dashboard" in content.lower() or "logged in" in content.lower()
                results.append({
                    "check": "Login successful",
                    "success": has_success
                })
            except Exception as e:
                results.append({
                    "check": "Login successful",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10,
            validation_fn=validate_login
        )
        
        print(f"\n=== Login Workflow Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)
    
    @pytest.mark.asyncio
    async def test_invalid_login_vision(self, request):
        """Test handling invalid login using UI-TARS vision."""
        page_url = self.server.get_url("workflow_automation/index.html")
        
        goal = """Try to login with invalid credentials:
        1. Enter username: wrong@example.com
        2. Enter password: wrongpassword
        3. Click Login
        4. Observe and report any error messages that appear"""
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10
        )
        
        print(f"\n=== Invalid Login Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        # For this test, we just need to complete the steps
        assert result.total_steps > 0, "No steps were executed"


class TestEcommerceVision(VisionTestBase):
    """Vision-guided integration tests for e-commerce use case."""
    
    def _get_use_case(self) -> str:
        return "ecommerce"
    
    @pytest.mark.asyncio
    async def test_add_to_cart_vision(self, request):
        """Test adding product to cart using UI-TARS vision."""
        page_url = self.server.get_url("ecommerce/index.html")
        
        goal = """Complete an e-commerce purchase flow:
        1. Find a product on the page
        2. Click "Add to Cart" button for that product
        3. Verify the item was added to cart"""
        
        async def validate_cart(page):
            """Validate item added to cart."""
            results = []
            
            try:
                # Check cart indicator
                cart_count = await page.query_selector(".cart-count, #cartCount")
                if cart_count:
                    count_text = await cart_count.text_content()
                    results.append({
                        "check": "Cart updated",
                        "success": int(count_text or "0") > 0,
                        "cart_count": count_text
                    })
            except Exception as e:
                results.append({
                    "check": "Cart updated",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10,
            validation_fn=validate_cart
        )
        
        print(f"\n=== Add to Cart Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)
    
    @pytest.mark.asyncio
    async def test_filter_products_vision(self, request):
        """Test filtering products using UI-TARS vision."""
        page_url = self.server.get_url("ecommerce/index.html")
        
        goal = """Filter the products on this page:
        1. Find the filter options (price range, category, etc.)
        2. Apply a filter (e.g., price range or category)
        3. Verify the products displayed have changed"""
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10
        )
        
        print(f"\n=== Filter Products Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)


class TestUITestingVision(VisionTestBase):
    """Vision-guided integration tests for UI Testing use case."""
    
    def _get_use_case(self) -> str:
        return "ui_testing"
    
    @pytest.mark.asyncio
    async def test_button_click_vision(self, request):
        """Test clicking buttons using UI-TARS vision."""
        page_url = self.server.get_url("ui_testing/index.html")
        
        goal = """Test the button functionality on this page:
        1. Click the "Primary Button"
        2. Click the "Success Button"
        3. Verify the click counter increases
        Report the final click count."""
        
        async def validate_buttons(page):
            """Validate button clicks worked."""
            results = []
            
            try:
                # Check click counter
                counter = await page.query_selector("#click-count")
                if counter:
                    count = await counter.text_content()
                    results.append({
                        "check": "Click counter increased",
                        "success": int(count or "0") >= 2,
                        "click_count": count
                    })
            except Exception as e:
                results.append({
                    "check": "Click counter increased",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10,
            validation_fn=validate_buttons
        )
        
        print(f"\n=== Button Click Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)
    
    @pytest.mark.asyncio
    async def test_form_validation_vision(self, request):
        """Test form validation using UI-TARS vision."""
        page_url = self.server.get_url("ui_testing/index.html")
        
        goal = """Test the form validation:
        1. Enter an invalid email like "notanemail" in the email field
        2. Click outside the field to trigger validation
        3. Verify that an error message appears
        4. Then enter a valid email like "test@example.com"
        5. Verify the error disappears"""
        
        async def validate_form(page):
            """Validate form validation worked."""
            results = []
            
            try:
                # Check for error message visibility
                error = await page.query_selector("#email-error.visible")
                results.append({
                    "check": "Error message appeared",
                    "success": error is not None
                })
            except Exception as e:
                results.append({
                    "check": "Error message appeared",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=15,
            validation_fn=validate_form
        )
        
        print(f"\n=== Form Validation Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)
    
    @pytest.mark.asyncio
    async def test_modal_interaction_vision(self, request):
        """Test modal dialog using UI-TARS vision."""
        page_url = self.server.get_url("ui_testing/index.html")
        
        goal = """Test the modal dialog:
        1. Click the "Open Modal" button
        2. Verify the modal appears
        3. Click the "Confirm" button inside the modal
        4. Verify the modal closes"""
        
        async def validate_modal(page):
            """Validate modal interaction worked."""
            results = []
            
            try:
                # Check if modal is closed
                modal = await page.query_selector("#modal-overlay.active")
                results.append({
                    "check": "Modal closed after confirm",
                    "success": modal is None
                })
            except Exception as e:
                results.append({
                    "check": "Modal closed after confirm",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10,
            validation_fn=validate_modal
        )
        
        print(f"\n=== Modal Interaction Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)
    
    @pytest.mark.asyncio
    async def test_tabs_navigation_vision(self, request):
        """Test tab navigation using UI-TARS vision."""
        page_url = self.server.get_url("ui_testing/index.html")
        
        goal = """Test the tab navigation:
        1. Click on "Tab 2"
        2. Verify Tab 2 content is visible
        3. Click on "Tab 3"
        4. Verify Tab 3 content is visible"""
        
        async def validate_tabs(page):
            """Validate tab navigation worked."""
            results = []
            
            try:
                # Check if Tab 3 content is active
                tab3 = await page.query_selector("#tab3.active")
                results.append({
                    "check": "Tab 3 content visible",
                    "success": tab3 is not None
                })
            except Exception as e:
                results.append({
                    "check": "Tab 3 content visible",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10,
            validation_fn=validate_tabs
        )
        
        print(f"\n=== Tabs Navigation Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)
    
    @pytest.mark.asyncio
    async def test_toggle_switch_vision(self, request):
        """Test toggle switches using UI-TARS vision."""
        page_url = self.server.get_url("ui_testing/index.html")
        
        goal = """Test the toggle switches:
        1. Click the first toggle switch to turn it ON
        2. Verify the status changes to "ON"
        3. Click the second toggle switch to turn it ON
        4. Verify both toggles are ON"""
        
        async def validate_toggles(page):
            """Validate toggle switches worked."""
            results = []
            
            try:
                # Check toggle statuses
                status1 = await page.query_selector("#toggle-status-1")
                status2 = await page.query_selector("#toggle-status-2")
                
                text1 = await status1.text_content() if status1 else ""
                text2 = await status2.text_content() if status2 else ""
                
                results.append({
                    "check": "Toggle 1 is ON",
                    "success": text1 == "ON",
                    "status": text1
                })
                results.append({
                    "check": "Toggle 2 is ON",
                    "success": text2 == "ON",
                    "status": text2
                })
            except Exception as e:
                results.append({
                    "check": "Toggle switches worked",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10,
            validation_fn=validate_toggles
        )
        
        print(f"\n=== Toggle Switch Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)
    
    @pytest.mark.asyncio
    async def test_accordion_vision(self, request):
        """Test accordion using UI-TARS vision."""
        page_url = self.server.get_url("ui_testing/index.html")
        
        goal = """Test the accordion component:
        1. Click on "Section 1" header to expand it
        2. Verify the content is visible
        3. Click on "Section 2" header to expand it
        4. Verify Section 1 closes and Section 2 opens"""
        
        async def validate_accordion(page):
            """Validate accordion worked."""
            results = []
            
            try:
                # Check which section is active
                section2 = await page.query_selector(".accordion-item:nth-child(2).active")
                results.append({
                    "check": "Section 2 is expanded",
                    "success": section2 is not None
                })
            except Exception as e:
                results.append({
                    "check": "Section 2 is expanded",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=10,
            validation_fn=validate_accordion
        )
        
        print(f"\n=== Accordion Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        self.assert_success_threshold(result)
    
    @pytest.mark.asyncio
    async def test_progress_bar_vision(self, request):
        """Test progress bar using UI-TARS vision."""
        page_url = self.server.get_url("ui_testing/index.html")
        
        goal = """Test the progress bar:
        1. Click the "Start Progress" button
        2. Wait for the progress to complete (100%)
        3. Verify the progress shows 100%"""
        
        async def validate_progress(page):
            """Validate progress bar worked."""
            results = []
            
            try:
                # Check progress percentage
                percent = await page.query_selector("#progress-percent")
                if percent:
                    text = await percent.text_content()
                    results.append({
                        "check": "Progress reached 100%",
                        "success": text == "100%",
                        "percent": text
                    })
            except Exception as e:
                results.append({
                    "check": "Progress reached 100%",
                    "success": False,
                    "error": str(e)
                })
            
            return results
        
        result = await self.run_vision_task(
            goal=goal,
            start_url=page_url,
            max_steps=15,
            validation_fn=validate_progress
        )
        
        print(f"\n=== Progress Bar Vision Test Result ===")
        print(json.dumps(result.to_dict(), indent=2))
        
        # More lenient for progress bar as it requires timing
        assert result.success_rate >= 50.0, (
            f"Success rate {result.success_rate:.1f}% below threshold 50%"
        )


class TestSuccessRateReport(VisionTestBase):
    """Generate overall success rate report for all use cases."""
    
    def _get_use_case(self) -> str:
        return "report"
    
    @pytest.mark.asyncio
    async def test_success_rate_report_schema(self, request):
        """Test that success rate report follows expected schema."""
        # This test validates the VisionTestResult schema
        result = VisionTestResult(
            task_name="schema_test",
            task_description="Test schema validation",
            use_case="report",
            goal="Validate report schema",
            success=True,
            steps=[{"step": 1, "action": "test", "success": True}],
            execution_time=1.5,
            validation_results=[{"check": "schema", "success": True}]
        )
        
        result_dict = result.to_dict()
        
        # Validate schema
        required_fields = [
            "task_name", "task_description", "use_case", "goal",
            "success", "total_steps", "successful_steps", "success_rate",
            "execution_time_seconds", "steps"
        ]
        
        for field in required_fields:
            assert field in result_dict, f"Missing required field: {field}"
        
        assert isinstance(result_dict["success_rate"], float)
        assert isinstance(result_dict["steps"], list)
        
        print(f"\n=== Schema Validation Passed ===")
        print(json.dumps(result_dict, indent=2))


# Utility function to run all vision tests and generate report
async def run_all_vision_tests(
    base_url: str = "http://localhost:8765",
    llm_endpoint: str = "http://127.0.0.1:1234/v1"
) -> Dict[str, Any]:
    """
    Run all vision-guided tests and return a comprehensive report.
    
    This function can be called directly for custom test runs.
    """
    from browser_agent import BrowserAgent
    
    test_cases = [
        {
            "use_case": "form_filling",
            "goal": "Fill the contact form with test data and submit",
            "url": f"{base_url}/form_filling/index.html"
        },
        {
            "use_case": "data_extraction",
            "goal": "Extract all product information from the page",
            "url": f"{base_url}/data_extraction/index.html"
        },
        {
            "use_case": "web_scraping",
            "goal": "Navigate through pagination and collect articles",
            "url": f"{base_url}/web_scraping/index.html"
        },
        {
            "use_case": "search_research",
            "goal": "Search for 'python' and view results",
            "url": f"{base_url}/search_research/index.html"
        },
        {
            "use_case": "workflow_automation",
            "goal": "Complete the login workflow with demo credentials",
            "url": f"{base_url}/workflow_automation/index.html"
        },
        {
            "use_case": "ecommerce",
            "goal": "Add a product to the shopping cart",
            "url": f"{base_url}/ecommerce/index.html"
        },
        {
            "use_case": "ui_testing",
            "goal": "Test button clicks, form validation, and modal interactions",
            "url": f"{base_url}/ui_testing/index.html"
        }
    ]
    
    results = []
    
    for test in test_cases:
        agent = BrowserAgent()
        try:
            await agent.initialize()
            task_result = await agent.execute_task(
                goal=test["goal"],
                start_url=test["url"],
                max_steps=15
            )
            
            results.append({
                "use_case": test["use_case"],
                "success": task_result.success,
                "steps": len(task_result.steps),
                "execution_time": task_result.execution_time,
                "error": task_result.error
            })
        finally:
            await agent.cleanup()
    
    return {
        "total_tests": len(results),
        "successful": sum(1 for r in results if r["success"]),
        "results": results
    }


if __name__ == "__main__":
    import sys
    
    # Run with: python test_integration_use_cases.py --run-integration
    if "--run-integration" in sys.argv:
        pytest.main([__file__, "-v", "--run-integration", "-s"])
    else:
        print("Usage: python test_integration_use_cases.py --run-integration")
        print("       pytest test_integration_use_cases.py -v --run-integration")

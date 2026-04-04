"""
Web Scraping Skill Module

Provides comprehensive web scraping capabilities with multi-page navigation,
data aggregation, rate limiting, and robots.txt compliance.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import asyncio
import logging
import time
from urllib.parse import urljoin, urlparse
from collections import deque

from .base import BaseSkill, SkillResult, SkillInput, SkillCapability
from .data_extraction import DataExtractionSkill, ExtractionSchema

logger = logging.getLogger(__name__)


class ScrapingMode(Enum):
    """Scraping modes."""

    SINGLE_PAGE = "single_page"
    PAGINATED = "paginated"
    CRAWL = "crawl"
    SITEMAP = "sitemap"


class ComplianceLevel(Enum):
    """Robots.txt compliance levels."""

    STRICT = "strict"  # Always respect robots.txt
    MODERATE = "moderate"  # Respect for sensitive paths
    NONE = "none"  # Ignore robots.txt


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    # Minimum delay between requests (seconds)
    min_delay: float = 1.0

    # Maximum delay between requests (seconds)
    max_delay: float = 3.0

    # Maximum requests per minute
    max_requests_per_minute: int = 30

    # Maximum concurrent requests
    max_concurrent: int = 1

    # Exponential backoff on errors
    backoff_on_error: bool = True

    # Maximum backoff time (seconds)
    max_backoff: float = 60.0


@dataclass
class ScrapingConfig:
    """
    Configuration for web scraping.

    Defines how scraping should be performed.
    """

    # Starting URLs
    start_urls: List[str] = field(default_factory=list)

    # Scraping mode
    mode: ScrapingMode = ScrapingMode.SINGLE_PAGE

    # Extraction schema
    extraction_schema: Optional[ExtractionSchema] = None

    # URL patterns to include (regex)
    include_patterns: List[str] = field(default_factory=list)

    # URL patterns to exclude (regex)
    exclude_patterns: List[str] = field(default_factory=list)

    # Maximum pages to scrape
    max_pages: int = 100

    # Maximum depth for crawling
    max_depth: int = 3

    # Rate limiting configuration
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)

    # Robots.txt compliance
    compliance_level: ComplianceLevel = ComplianceLevel.MODERATE

    # Custom user agent
    user_agent: Optional[str] = None

    # Timeout per page (seconds)
    page_timeout: float = 30.0

    # Retry failed pages
    retry_failed: bool = True

    # Maximum retries per page
    max_retries: int = 3

    # Output format
    output_format: str = "json"

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "start_urls": self.start_urls,
            "mode": self.mode.value,
            "extraction_schema": self.extraction_schema.to_dict() if self.extraction_schema else None,
            "include_patterns": self.include_patterns,
            "exclude_patterns": self.exclude_patterns,
            "max_pages": self.max_pages,
            "max_depth": self.max_depth,
            "rate_limit": {
                "min_delay": self.rate_limit.min_delay,
                "max_delay": self.rate_limit.max_delay,
                "max_requests_per_minute": self.rate_limit.max_requests_per_minute,
                "max_concurrent": self.rate_limit.max_concurrent,
            },
            "compliance_level": self.compliance_level.value,
            "user_agent": self.user_agent,
            "page_timeout": self.page_timeout,
            "retry_failed": self.retry_failed,
            "max_retries": self.max_retries,
            "output_format": self.output_format,
            "metadata": self.metadata,
        }


@dataclass
class WebScrapingInput(SkillInput):
    """
    Input for web scraping skill.
    """

    # Scraping configuration
    config: Optional[ScrapingConfig] = None

    # Custom extraction function name
    extraction_function: Optional[str] = None

    # Whether to save raw HTML
    save_raw_html: bool = False

    # Whether to save screenshots
    save_screenshots: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        d = super().to_dict()
        d.update(
            {
                "config": self.config.to_dict() if self.config else None,
                "extraction_function": self.extraction_function,
                "save_raw_html": self.save_raw_html,
                "save_screenshots": self.save_screenshots,
            }
        )
        return d


@dataclass
class ScrapedPage:
    """Result from scraping a single page."""

    url: str
    data: Dict[str, Any]
    timestamp: datetime
    status_code: int = 200
    error: Optional[str] = None
    depth: int = 0
    raw_html: Optional[str] = None
    screenshot_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "url": self.url,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "status_code": self.status_code,
            "error": self.error,
            "depth": self.depth,
        }


class WebScrapingSkill(BaseSkill[WebScrapingInput]):
    """
    Skill for comprehensive web scraping.

    Capabilities:
    - Multi-page navigation
    - Data aggregation
    - Rate limiting
    - Robots.txt compliance
    - Crawling with depth control
    """

    name = "web_scraping"
    description = "Scrape data from multiple web pages with rate limiting and compliance"
    version = "1.0.0"

    required_capabilities: Set[SkillCapability] = {
        SkillCapability.BROWSER_NAVIGATION,
        SkillCapability.DATA_EXTRACTION,
        SkillCapability.MULTI_PAGE_NAVIGATION,
    }

    provided_capabilities: Set[SkillCapability] = {
        SkillCapability.MULTI_PAGE_NAVIGATION,
        SkillCapability.DATA_EXTRACTION,
        SkillCapability.PAGINATION_HANDLING,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._request_times: List[float] = []
        self._robots_cache: Dict[str, Any] = {}
        self._scraped_urls: Set[str] = set()

    async def execute(self, input_data: WebScrapingInput) -> SkillResult:
        """
        Execute web scraping.

        Args:
            input_data: Web scraping input with configuration

        Returns:
            SkillResult with scraped data
        """
        result = SkillResult(success=False)

        try:
            config = input_data.config
            if config is None:
                self._set_error(result, "No scraping configuration provided", "CONFIG_ERROR")
                return result

            if not config.start_urls:
                self._set_error(result, "No start URLs provided", "CONFIG_ERROR")
                return result

            result.metadata["start_urls"] = config.start_urls
            result.metadata["mode"] = config.mode.value

            # Reset state
            self._request_times = []
            self._scraped_urls = set()

            # Execute based on mode
            if config.mode == ScrapingMode.SINGLE_PAGE:
                pages = await self._scrape_single_page(config, input_data, result)
            elif config.mode == ScrapingMode.PAGINATED:
                pages = await self._scrape_paginated(config, input_data, result)
            elif config.mode == ScrapingMode.CRAWL:
                pages = await self._scrape_crawl(config, input_data, result)
            else:
                pages = await self._scrape_single_page(config, input_data, result)

            # Aggregate results
            all_data = [p.data for p in pages if p.data]

            result.success = True
            result.data = {
                "pages": [p.to_dict() for p in pages],
                "aggregated_data": all_data,
                "total_pages": len(pages),
                "successful_pages": len([p for p in pages if p.error is None]),
                "failed_pages": len([p for p in pages if p.error is not None]),
            }
            result.metadata["pages_scraped"] = len(pages)

            self._add_step(result, f"Scraped {len(pages)} pages")

        except Exception as e:
            self._set_error(result, f"Web scraping error: {e}", "SCRAPING_ERROR")
            self._logger.exception("Web scraping failed")

        return result

    def validate_input(self, input_data: WebScrapingInput) -> bool:
        """
        Validate web scraping input.

        Args:
            input_data: Input to validate

        Returns:
            True if valid, False otherwise
        """
        if not input_data.config:
            self._logger.warning("No scraping configuration provided")
            return False

        if not input_data.config.start_urls:
            self._logger.warning("No start URLs provided")
            return False

        return True

    def verify_results(self, result: SkillResult) -> bool:
        """
        Verify web scraping results.

        Args:
            result: Result to verify

        Returns:
            True if valid, False otherwise
        """
        if not result.success:
            return False

        if not result.data:
            return False

        pages = result.data.get("pages", [])
        if not pages:
            return False

        return True

    async def _scrape_single_page(
        self,
        config: ScrapingConfig,
        input_data: WebScrapingInput,
        result: SkillResult,
    ) -> List[ScrapedPage]:
        """Scrape single page."""
        pages = []

        for url in config.start_urls[:1]:  # Only first URL
            page = await self._scrape_page(url, config, input_data, 0, result)
            if page:
                pages.append(page)

        return pages

    async def _scrape_paginated(
        self,
        config: ScrapingConfig,
        input_data: WebScrapingInput,
        result: SkillResult,
    ) -> List[ScrapedPage]:
        """Scrape paginated content."""
        pages = []

        for url in config.start_urls:
            current_url = url
            page_count = 0

            while current_url and page_count < config.max_pages:
                # Rate limit
                await self._apply_rate_limit(config)

                # Scrape page
                page = await self._scrape_page(current_url, config, input_data, 0, result)
                if page:
                    pages.append(page)
                    page_count += 1

                # Find next page URL
                next_url = await self._find_next_page(config)
                if not next_url:
                    break

                current_url = next_url
                self._scraped_urls.add(current_url)

        return pages

    async def _scrape_crawl(
        self,
        config: ScrapingConfig,
        input_data: WebScrapingInput,
        result: SkillResult,
    ) -> List[ScrapedPage]:
        """Crawl multiple pages with depth control."""
        pages = []
        queue = deque()

        # Initialize queue with start URLs
        for url in config.start_urls:
            queue.append((url, 0))
            self._scraped_urls.add(url)

        while queue and len(pages) < config.max_pages:
            url, depth = queue.popleft()

            # Check depth limit
            if depth > config.max_depth:
                continue

            # Rate limit
            await self._apply_rate_limit(config)

            # Scrape page
            page = await self._scrape_page(url, config, input_data, depth, result)
            if page:
                pages.append(page)

                # Find links for crawling
                if depth < config.max_depth:
                    links = await self._find_links(config)
                    for link in links:
                        if link not in self._scraped_urls:
                            if self._should_follow_url(link, config):
                                queue.append((link, depth + 1))
                                self._scraped_urls.add(link)

        return pages

    async def _scrape_page(
        self,
        url: str,
        config: ScrapingConfig,
        input_data: WebScrapingInput,
        depth: int,
        result: SkillResult,
    ) -> Optional[ScrapedPage]:
        """Scrape a single page."""
        self._logger.info(f"Scraping: {url}")

        # Check robots.txt compliance
        if not await self._check_robots_compliance(url, config):
            self._add_warning(result, f"Blocked by robots.txt: {url}")
            return ScrapedPage(
                url=url,
                data={},
                timestamp=datetime.now(),
                error="Blocked by robots.txt",
                depth=depth,
            )

        try:
            # Navigate to page
            if self.browser:
                await self.browser.navigate(url)
                await asyncio.sleep(1.0)  # Wait for page load

            # Extract data
            data = {}
            if config.extraction_schema:
                extraction_skill = DataExtractionSkill(
                    browser_controller=self.browser,
                    vision_client=self.vision,
                )
                extraction_input = type(
                    "ExtractionInput",
                    (),
                    {
                        "task": f"Extract from {url}",
                        "schema": config.extraction_schema,
                        "max_retries": config.max_retries,
                        "validate_input": True,
                        "verify_results": False,
                    },
                )()

                extraction_result = await extraction_skill.execute(extraction_input)
                if extraction_result.success:
                    data = extraction_result.data or {}

            # Save raw HTML if requested
            raw_html = None
            if input_data.save_raw_html and self.browser:
                raw_html = await self.browser.extract_html()

            # Save screenshot if requested
            screenshot_path = None
            if input_data.save_screenshots and self.browser:
                screenshot_path = await self.browser.take_screenshot()

            return ScrapedPage(
                url=url,
                data=data,
                timestamp=datetime.now(),
                status_code=200,
                depth=depth,
                raw_html=raw_html,
                screenshot_path=screenshot_path,
            )

        except Exception as e:
            self._logger.error(f"Failed to scrape {url}: {e}")
            return ScrapedPage(
                url=url,
                data={},
                timestamp=datetime.now(),
                error=str(e),
                status_code=500,
                depth=depth,
            )

    async def _apply_rate_limit(self, config: ScrapingConfig) -> None:
        """Apply rate limiting."""
        rate = config.rate_limit

        # Clean old request times
        now = time.time()
        minute_ago = now - 60
        self._request_times = [t for t in self._request_times if t > minute_ago]

        # Check requests per minute
        if len(self._request_times) >= rate.max_requests_per_minute:
            wait_time = 60 - (now - self._request_times[0])
            if wait_time > 0:
                self._logger.debug(f"Rate limit: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

        # Apply minimum delay
        import random

        delay = random.uniform(rate.min_delay, rate.max_delay)
        await asyncio.sleep(delay)

        # Record request time
        self._request_times.append(time.time())

    async def _check_robots_compliance(
        self,
        url: str,
        config: ScrapingConfig,
    ) -> bool:
        """Check if URL is allowed by robots.txt."""
        if config.compliance_level == ComplianceLevel.NONE:
            return True

        # Simple check - in production, parse actual robots.txt
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        # Cache robots.txt
        if robots_url not in self._robots_cache:
            try:
                if self.browser:
                    await self.browser.navigate(robots_url)
                    content = await self.browser.extract_text()
                    self._robots_cache[robots_url] = self._parse_robots(content)
                else:
                    self._robots_cache[robots_url] = {"allowed": ["*"]}
            except Exception:
                self._robots_cache[robots_url] = {"allowed": ["*"]}

        # Check path against rules
        robots = self._robots_cache[robots_url]
        path = parsed.path

        for disallowed in robots.get("disallowed", []):
            if path.startswith(disallowed):
                return False

        return True

    def _parse_robots(self, content: str) -> Dict[str, List[str]]:
        """Parse robots.txt content."""
        result = {
            "allowed": [],
            "disallowed": [],
        }

        for line in content.split("\n"):
            line = line.strip().lower()
            if line.startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path:
                    result["disallowed"].append(path)
            elif line.startswith("allow:"):
                path = line.split(":", 1)[1].strip()
                if path:
                    result["allowed"].append(path)

        return result

    def _should_follow_url(self, url: str, config: ScrapingConfig) -> bool:
        """Check if URL should be followed during crawling."""
        import re

        # Check include patterns
        if config.include_patterns:
            if not any(re.search(p, url) for p in config.include_patterns):
                return False

        # Check exclude patterns
        for pattern in config.exclude_patterns:
            if re.search(pattern, url):
                return False

        # Skip common non-content URLs
        skip_extensions = [".pdf", ".zip", ".jpg", ".png", ".gif", ".mp4", ".mp3"]
        if any(url.lower().endswith(ext) for ext in skip_extensions):
            return False

        return True

    async def _find_next_page(self, config: ScrapingConfig) -> Optional[str]:
        """Find next page URL for pagination."""
        if not self.browser:
            return None

        try:
            page = self.browser.page

            # Common pagination selectors
            selectors = [
                'a[rel="next"]',
                "a.next",
                'a[aria-label="Next"]',
                "li.next a",
                ".pagination a:last-child",
            ]

            for selector in selectors:
                element = await page.query_selector(selector)
                if element:
                    href = await element.get_attribute("href")
                    if href:
                        if href.startswith("/"):
                            base_url = page.url
                            return urljoin(base_url, href)
                        return href

        except Exception as e:
            self._logger.debug(f"Failed to find next page: {e}")

        return None

    async def _find_links(self, config: ScrapingConfig) -> List[str]:
        """Find all links on current page."""
        if not self.browser:
            return []

        links = []

        try:
            page = self.browser.page
            elements = await page.query_selector_all("a[href]")

            for element in elements:
                href = await element.get_attribute("href")
                if href and href.startswith("http"):
                    links.append(href)

        except Exception as e:
            self._logger.debug(f"Failed to find links: {e}")

        return links

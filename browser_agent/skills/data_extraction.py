"""
Data Extraction Skill Module

Provides structured data extraction from web pages with schema support,
pagination handling, and deduplication.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, TypeVar
import asyncio
import logging
import hashlib
import re

from .base import BaseSkill, SkillResult, SkillInput, SkillCapability

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ExtractionFieldType(Enum):
    """Types of extraction fields."""

    TEXT = "text"
    NUMBER = "number"
    URL = "url"
    IMAGE_URL = "image_url"
    DATE = "date"
    PRICE = "price"
    RATING = "rating"
    BOOLEAN = "boolean"
    LIST = "list"
    NESTED = "nested"
    HTML = "html"


@dataclass
class ExtractionField:
    """
    Definition of a field to extract.

    Describes how to locate and extract a single piece of data.
    """

    # Field name
    name: str

    # Field type
    field_type: ExtractionFieldType = ExtractionFieldType.TEXT

    # CSS selector
    selector: Optional[str] = None

    # Attribute to extract (e.g., "href", "src")
    attribute: Optional[str] = None

    # Visual description for detection
    visual_description: Optional[str] = None

    # Regex pattern for extraction
    pattern: Optional[str] = None

    # Default value if not found
    default: Any = None

    # Whether field is required
    required: bool = False

    # Whether to strip whitespace
    strip: bool = True

    # Post-processing function name
    process: Optional[str] = None

    # For nested extraction
    nested_fields: List["ExtractionField"] = field(default_factory=list)

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "field_type": self.field_type.value,
            "selector": self.selector,
            "attribute": self.attribute,
            "visual_description": self.visual_description,
            "pattern": self.pattern,
            "default": self.default,
            "required": self.required,
            "strip": self.strip,
            "process": self.process,
            "nested_fields": [f.to_dict() for f in self.nested_fields],
            "metadata": self.metadata,
        }


@dataclass
class ExtractionSchema:
    """
    Schema for data extraction.

    Defines the structure of data to extract from a page.
    """

    # Schema name
    name: str

    # Fields to extract
    fields: List[ExtractionField] = field(default_factory=list)

    # Container selector (extract multiple items)
    container_selector: Optional[str] = None

    # Whether to extract multiple items
    multiple: bool = False

    # Maximum items to extract
    max_items: int = 100

    # Pagination selector
    pagination_selector: Optional[str] = None

    # Maximum pages to traverse
    max_pages: int = 10

    # Wait time between pages (seconds)
    page_wait: float = 1.0

    # Whether to deduplicate results
    deduplicate: bool = True

    # Fields to use for deduplication
    deduplicate_fields: List[str] = field(default_factory=list)

    # URL to start extraction from
    url: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_field(self, name: str) -> Optional[ExtractionField]:
        """Get a field by name."""
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def get_required_fields(self) -> List[ExtractionField]:
        """Get all required fields."""
        return [f for f in self.fields if f.required]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "fields": [f.to_dict() for f in self.fields],
            "container_selector": self.container_selector,
            "multiple": self.multiple,
            "max_items": self.max_items,
            "pagination_selector": self.pagination_selector,
            "max_pages": self.max_pages,
            "page_wait": self.page_wait,
            "deduplicate": self.deduplicate,
            "deduplicate_fields": self.deduplicate_fields,
            "url": self.url,
            "metadata": self.metadata,
        }


@dataclass
class DataExtractionInput(SkillInput):
    """
    Input for data extraction skill.
    """

    # Extraction schema
    schema: Optional[ExtractionSchema] = None

    # URL to extract from (overrides schema URL)
    url: Optional[str] = None

    # Whether to use visual extraction
    visual_extraction: bool = True

    # Timeout for page load (seconds)
    page_timeout: float = 30.0

    # Timeout for extraction (seconds)
    extraction_timeout: float = 60.0

    # Custom extraction prompt
    extraction_prompt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        d = super().to_dict()
        d.update(
            {
                "schema": self.schema.to_dict() if self.schema else None,
                "url": self.url,
                "visual_extraction": self.visual_extraction,
                "page_timeout": self.page_timeout,
                "extraction_timeout": self.extraction_timeout,
                "extraction_prompt": self.extraction_prompt,
            }
        )
        return d


class DataExtractionSkill(BaseSkill[DataExtractionInput]):
    """
    Skill for structured data extraction.

    Capabilities:
    - Schema-based extraction
    - Multi-item extraction
    - Pagination handling
    - Deduplication
    - Visual extraction
    """

    name = "data_extraction"
    description = "Extract structured data from web pages using schemas and visual detection"
    version = "1.0.0"

    required_capabilities: Set[SkillCapability] = {
        SkillCapability.BROWSER_SCREENSHOT,
        SkillCapability.VISION_ELEMENT_DETECTION,
        SkillCapability.DATA_EXTRACTION,
    }

    provided_capabilities: Set[SkillCapability] = {
        SkillCapability.DATA_EXTRACTION,
        SkillCapability.DATA_TRANSFORMATION,
        SkillCapability.PAGINATION_HANDLING,
    }

    async def execute(self, input_data: DataExtractionInput) -> SkillResult:
        """
        Execute data extraction.

        Args:
            input_data: Data extraction input with schema

        Returns:
            SkillResult with extracted data
        """
        result = SkillResult(success=False)
        result.metadata["schema_name"] = input_data.schema.name if input_data.schema else "unknown"

        try:
            # Navigate to URL if specified
            url = input_data.url or (input_data.schema.url if input_data.schema else None)
            if url:
                await self._navigate_to_page(url, input_data, result)
                if result.failed:
                    return result

            # Get schema
            schema = input_data.schema
            if schema is None:
                self._set_error(result, "No extraction schema provided", "SCHEMA_ERROR")
                return result

            all_items = []
            current_page = 1
            max_pages = schema.max_pages if schema.multiple else 1

            # Extract from current and paginated pages
            while current_page <= max_pages:
                self._logger.info(f"Extracting from page {current_page}")

                # Extract items
                items = await self._extract_items(schema, input_data, result)
                all_items.extend(items)

                self._add_step(result, f"Extracted {len(items)} items from page {current_page}")

                # Check max items
                if len(all_items) >= schema.max_items:
                    all_items = all_items[: schema.max_items]
                    break

                # Check for pagination
                if not schema.multiple or not schema.pagination_selector:
                    break

                # Navigate to next page
                has_next = await self._go_to_next_page(schema, result)
                if not has_next:
                    break

                current_page += 1
                await asyncio.sleep(schema.page_wait)

            # Deduplicate if enabled
            if schema.deduplicate and all_items:
                all_items = self._deduplicate_items(all_items, schema)
                self._add_step(result, f"Deduplicated to {len(all_items)} items")

            result.success = True
            result.data = {
                "items": all_items,
                "total_count": len(all_items),
                "pages_extracted": current_page,
            }
            result.metadata["items_count"] = len(all_items)

        except Exception as e:
            self._set_error(result, f"Data extraction error: {e}", "EXTRACTION_ERROR")
            self._logger.exception("Data extraction failed")

        return result

    def validate_input(self, input_data: DataExtractionInput) -> bool:
        """
        Validate data extraction input.

        Args:
            input_data: Input to validate

        Returns:
            True if valid, False otherwise
        """
        if not input_data.task:
            self._logger.warning("No task description provided")
            return False

        if not input_data.schema:
            self._logger.warning("No extraction schema provided")
            return False

        if not input_data.schema.fields:
            self._logger.warning("Schema has no fields defined")
            return False

        return True

    def verify_results(self, result: SkillResult) -> bool:
        """
        Verify data extraction results.

        Args:
            result: Result to verify

        Returns:
            True if valid, False otherwise
        """
        if not result.success:
            return False

        if not result.data:
            return False

        items = result.data.get("items", [])
        if not items:
            self._logger.warning("No items extracted")
            return False

        return True

    async def _navigate_to_page(
        self,
        url: str,
        input_data: DataExtractionInput,
        result: SkillResult,
    ) -> bool:
        """Navigate to a page."""
        if self.browser is None:
            self._set_error(result, "No browser controller available", "CONFIG_ERROR")
            return False

        self._logger.info(f"Navigating to: {url}")

        try:
            await self.browser.navigate(url)
            await asyncio.sleep(1.0)
            self._add_step(result, f"Navigated to {url}")
            return True
        except Exception as e:
            self._set_error(result, f"Navigation failed: {e}", "NAVIGATION_ERROR")
            return False

    async def _extract_items(
        self,
        schema: ExtractionSchema,
        input_data: DataExtractionInput,
        result: SkillResult,
    ) -> List[Dict[str, Any]]:
        """Extract items from current page."""
        if self.browser is None:
            return []

        items = []

        try:
            page = self.browser.page

            if schema.multiple and schema.container_selector:
                # Extract multiple items
                containers = await page.query_selector_all(schema.container_selector)
                self._logger.info(f"Found {len(containers)} containers")

                for container in containers:
                    item = await self._extract_from_container(container, schema.fields)
                    if item:
                        items.append(item)
            else:
                # Extract single item
                item = await self._extract_from_page(schema.fields)
                if item:
                    items.append(item)

        except Exception as e:
            self._logger.error(f"Extraction failed: {e}")
            self._add_warning(result, f"Extraction error: {e}")

        return items

    async def _extract_from_container(
        self,
        container: Any,
        fields: List[ExtractionField],
    ) -> Optional[Dict[str, Any]]:
        """Extract fields from a container element."""
        item = {}

        for field in fields:
            try:
                value = await self._extract_field_from_container(container, field)
                item[field.name] = value
            except Exception as e:
                self._logger.debug(f"Field extraction failed for {field.name}: {e}")
                item[field.name] = field.default

        # Check if item has any non-None values
        if all(v is None for v in item.values()):
            return None

        return item

    async def _extract_field_from_container(
        self,
        container: Any,
        field: ExtractionField,
    ) -> Any:
        """Extract a single field from a container."""
        if field.selector:
            element = await container.query_selector(field.selector)
            if element:
                return await self._extract_value_from_element(element, field)
        else:
            # No selector, extract from container itself
            return await self._extract_value_from_element(container, field)

        return field.default

    async def _extract_from_page(
        self,
        fields: List[ExtractionField],
    ) -> Optional[Dict[str, Any]]:
        """Extract fields from the entire page."""
        if self.browser is None:
            return None

        item = {}
        page = self.browser.page

        for field in fields:
            try:
                if field.selector:
                    element = await page.query_selector(field.selector)
                    if element:
                        value = await self._extract_value_from_element(element, field)
                    else:
                        value = field.default
                else:
                    # Use visual extraction
                    value = await self._extract_visual(field)

                item[field.name] = value
            except Exception as e:
                self._logger.debug(f"Field extraction failed for {field.name}: {e}")
                item[field.name] = field.default

        return item if any(v is not None for v in item.values()) else None

    async def _extract_value_from_element(
        self,
        element: Any,
        field: ExtractionField,
    ) -> Any:
        """Extract value from an element."""
        value = None

        # Get attribute if specified
        if field.attribute:
            value = await element.get_attribute(field.attribute)
        else:
            # Get text content
            value = await element.text_content()

        if value is None:
            return field.default

        # Strip whitespace
        if field.strip and isinstance(value, str):
            value = value.strip()

        # Apply regex pattern
        if field.pattern and isinstance(value, str):
            match = re.search(field.pattern, value)
            if match:
                value = match.group(1) if match.groups() else match.group(0)
            else:
                return field.default

        # Process by type
        value = self._process_value(value, field.field_type)

        return value

    async def _extract_visual(self, field: ExtractionField) -> Any:
        """Extract value using visual detection."""
        if self.vision is None or not field.visual_description:
            return field.default

        try:
            # Use vision client to find element
            result = await self.vision.analyze_element(field.visual_description)
            if result:
                return result.get("text", field.default)
        except Exception as e:
            self._logger.debug(f"Visual extraction failed: {e}")

        return field.default

    def _process_value(self, value: Any, field_type: ExtractionFieldType) -> Any:
        """Process value based on field type."""
        if value is None:
            return None

        if field_type == ExtractionFieldType.NUMBER:
            # Extract number from string
            if isinstance(value, str):
                match = re.search(r"[\d,]+\.?\d*", value.replace(",", ""))
                if match:
                    return float(match.group())
            return value

        elif field_type == ExtractionFieldType.PRICE:
            # Extract price
            if isinstance(value, str):
                match = re.search(r"[\$€£]?\s*([\d,]+\.?\d*)", value)
                if match:
                    return float(match.group(1).replace(",", ""))
            return value

        elif field_type == ExtractionFieldType.RATING:
            # Extract rating (e.g., "4.5 out of 5")
            if isinstance(value, str):
                match = re.search(r"(\d+\.?\d*)\s*(?:out of|/)\s*(\d+)", value)
                if match:
                    return float(match.group(1))
                match = re.search(r"(\d+\.?\d*)", value)
                if match:
                    return float(match.group(1))
            return value

        elif field_type == ExtractionFieldType.BOOLEAN:
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "1", "checked", "selected")
            return bool(value)

        elif field_type == ExtractionFieldType.URL:
            # Ensure URL is absolute
            if isinstance(value, str) and value.startswith("/"):
                if self.browser:
                    base_url = self.browser.page.url
                    from urllib.parse import urljoin

                    return urljoin(base_url, value)
            return value

        return value

    async def _go_to_next_page(
        self,
        schema: ExtractionSchema,
        result: SkillResult,
    ) -> bool:
        """Navigate to next page."""
        if self.browser is None or not schema.pagination_selector:
            return False

        try:
            page = self.browser.page
            next_button = await page.query_selector(schema.pagination_selector)

            if next_button:
                is_disabled = await next_button.get_attribute("disabled")
                if is_disabled:
                    return False

                await next_button.click()
                await asyncio.sleep(schema.page_wait)
                return True

        except Exception as e:
            self._logger.debug(f"Pagination failed: {e}")

        return False

    def _deduplicate_items(
        self,
        items: List[Dict[str, Any]],
        schema: ExtractionSchema,
    ) -> List[Dict[str, Any]]:
        """Remove duplicate items."""
        if not items:
            return items

        dedup_fields = schema.deduplicate_fields or list(items[0].keys())
        seen = set()
        unique_items = []

        for item in items:
            # Create hash from dedup fields
            key_parts = []
            for field in dedup_fields:
                value = item.get(field)
                if value is not None:
                    key_parts.append(str(value))

            key = hashlib.md5("|".join(key_parts).encode()).hexdigest()

            if key not in seen:
                seen.add(key)
                unique_items.append(item)

        return unique_items

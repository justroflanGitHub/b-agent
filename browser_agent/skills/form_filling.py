"""
Form Filling Skill Module

Provides intelligent form filling capabilities with field detection,
data mapping, and validation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
import asyncio
import logging
import re

from .base import BaseSkill, SkillResult, SkillInput, SkillCapability

logger = logging.getLogger(__name__)


class FieldType(Enum):
    """Types of form fields."""
    TEXT = "text"
    EMAIL = "email"
    PASSWORD = "password"
    NUMBER = "number"
    TELEPHONE = "tel"
    URL = "url"
    TEXTAREA = "textarea"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    DATE = "date"
    FILE = "file"
    HIDDEN = "hidden"
    UNKNOWN = "unknown"


@dataclass
class FormField:
    """
    Definition of a form field.
    
    Describes a single field in a form with its properties and constraints.
    """
    # Field identifier
    name: str
    
    # Field type
    field_type: FieldType = FieldType.TEXT
    
    # Human-readable label
    label: Optional[str] = None
    
    # CSS selector or XPath
    selector: Optional[str] = None
    
    # Visual description for detection
    visual_description: Optional[str] = None
    
    # Whether the field is required
    required: bool = False
    
    # Default value
    default_value: Optional[str] = None
    
    # Placeholder text
    placeholder: Optional[str] = None
    
    # Validation pattern (regex)
    pattern: Optional[str] = None
    
    # Minimum length
    min_length: Optional[int] = None
    
    # Maximum length
    max_length: Optional[int] = None
    
    # For select fields: available options
    options: List[str] = field(default_factory=list)
    
    # For checkbox/radio: value when checked
    checked_value: Optional[str] = None
    
    # Priority for filling order (lower = higher priority)
    priority: int = 100
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "field_type": self.field_type.value,
            "label": self.label,
            "selector": self.selector,
            "visual_description": self.visual_description,
            "required": self.required,
            "default_value": self.default_value,
            "placeholder": self.placeholder,
            "pattern": self.pattern,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "options": self.options,
            "checked_value": self.checked_value,
            "priority": self.priority,
            "metadata": self.metadata,
        }


@dataclass
class FormSchema:
    """
    Schema definition for a form.
    
    Describes the structure and constraints of a form.
    """
    # Form name/identifier
    name: str
    
    # Form fields
    fields: List[FormField] = field(default_factory=list)
    
    # Form selector (CSS or XPath)
    selector: Optional[str] = None
    
    # Submit button selector
    submit_selector: Optional[str] = None
    
    # Visual description of submit button
    submit_visual_description: Optional[str] = None
    
    # URL to navigate to before filling
    url: Optional[str] = None
    
    # Whether to auto-submit after filling
    auto_submit: bool = True
    
    # Wait time after submit (seconds)
    submit_wait: float = 2.0
    
    # Success indicator (URL pattern or element selector)
    success_indicator: Optional[str] = None
    
    # Error indicator selector
    error_indicator: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_field(self, name: str) -> Optional[FormField]:
        """Get a field by name."""
        for f in self.fields:
            if f.name == name:
                return f
        return None
    
    def get_required_fields(self) -> List[FormField]:
        """Get all required fields."""
        return [f for f in self.fields if f.required]
    
    def get_fields_by_type(self, field_type: FieldType) -> List[FormField]:
        """Get fields by type."""
        return [f for f in self.fields if f.field_type == field_type]
    
    def get_sorted_fields(self) -> List[FormField]:
        """Get fields sorted by priority."""
        return sorted(self.fields, key=lambda f: f.priority)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "fields": [f.to_dict() for f in self.fields],
            "selector": self.selector,
            "submit_selector": self.submit_selector,
            "submit_visual_description": self.submit_visual_description,
            "url": self.url,
            "auto_submit": self.auto_submit,
            "submit_wait": self.submit_wait,
            "success_indicator": self.success_indicator,
            "error_indicator": self.error_indicator,
            "metadata": self.metadata,
        }


@dataclass
class FormFillingInput(SkillInput):
    """
    Input for form filling skill.
    """
    # Form schema
    schema: Optional[FormSchema] = None
    
    # Data to fill (field_name -> value)
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Whether to detect fields visually
    visual_detection: bool = True
    
    # Whether to validate before submit
    validate_before_submit: bool = True
    
    # Timeout for field detection (seconds)
    detection_timeout: float = 30.0
    
    # Timeout for form submission (seconds)
    submit_timeout: float = 60.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        d = super().to_dict()
        d.update({
            "schema": self.schema.to_dict() if self.schema else None,
            "data": self.data,
            "visual_detection": self.visual_detection,
            "validate_before_submit": self.validate_before_submit,
            "detection_timeout": self.detection_timeout,
            "submit_timeout": self.submit_timeout,
        })
        return d


class FormFillingSkill(BaseSkill[FormFillingInput]):
    """
    Skill for intelligent form filling.
    
    Capabilities:
    - Field type detection
    - Visual field matching
    - Data mapping and validation
    - Multi-field form completion
    - Form submission
    """
    
    name = "form_filling"
    description = "Fill web forms with data using visual and selector-based field detection"
    version = "1.0.0"
    
    required_capabilities: Set[SkillCapability] = {
        SkillCapability.BROWSER_INTERACTION,
        SkillCapability.VISION_ELEMENT_DETECTION,
        SkillCapability.DATA_VALIDATION,
    }
    
    provided_capabilities: Set[SkillCapability] = {
        SkillCapability.FORM_HANDLING,
        SkillCapability.DATA_VALIDATION,
    }
    
    async def execute(self, input_data: FormFillingInput) -> SkillResult:
        """
        Execute form filling.
        
        Args:
            input_data: Form filling input with schema and data
            
        Returns:
            SkillResult with filling outcome
        """
        result = SkillResult(success=False)
        result.metadata["form_name"] = input_data.schema.name if input_data.schema else "unknown"
        
        try:
            # Navigate to URL if specified
            if input_data.schema and input_data.schema.url:
                await self._navigate_to_form(input_data, result)
                if result.failed:
                    return result
            
            # Detect form fields if no schema
            schema = input_data.schema
            if schema is None:
                schema = await self._detect_form_schema(input_data, result)
                if schema is None:
                    self._set_error(result, "Failed to detect form schema", "DETECTION_ERROR")
                    return result
            
            result.metadata["detected_fields"] = len(schema.fields)
            self._add_step(result, f"Detected {len(schema.fields)} form fields")
            
            # Fill form fields
            fill_result = await self._fill_fields(schema, input_data.data, input_data, result)
            if not fill_result:
                return result
            
            # Validate form if requested
            if input_data.validate_before_submit:
                validation_result = await self._validate_form(schema, result)
                if not validation_result:
                    self._add_warning(result, "Form validation failed")
            
            # Submit form if auto-submit
            if schema.auto_submit:
                submit_result = await self._submit_form(schema, input_data, result)
                if not submit_result:
                    return result
            
            result.success = True
            result.data = {
                "fields_filled": len([s for s in result.steps_completed if "Filled" in s]),
                "form_submitted": schema.auto_submit,
            }
            
        except Exception as e:
            self._set_error(result, f"Form filling error: {e}", "EXECUTION_ERROR")
            self._logger.exception("Form filling failed")
        
        return result
    
    def validate_input(self, input_data: FormFillingInput) -> bool:
        """
        Validate form filling input.
        
        Args:
            input_data: Input to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not input_data.task:
            self._logger.warning("No task description provided")
            return False
        
        if not input_data.data:
            self._logger.warning("No form data provided")
            return False
        
        # If schema provided, check required fields
        if input_data.schema:
            for field in input_data.schema.get_required_fields():
                if field.name not in input_data.data:
                    self._logger.warning(f"Missing required field: {field.name}")
                    return False
        
        return True
    
    def verify_results(self, result: SkillResult) -> bool:
        """
        Verify form filling results.
        
        Args:
            result: Result to verify
            
        Returns:
            True if valid, False otherwise
        """
        if not result.success:
            return False
        
        if not result.data:
            return False
        
        fields_filled = result.data.get("fields_filled", 0)
        if fields_filled == 0:
            return False
        
        return True
    
    async def _navigate_to_form(
        self,
        input_data: FormFillingInput,
        result: SkillResult,
    ) -> bool:
        """Navigate to the form URL."""
        if self.browser is None:
            self._set_error(result, "No browser controller available", "CONFIG_ERROR")
            return False
        
        url = input_data.schema.url
        self._logger.info(f"Navigating to form URL: {url}")
        
        try:
            await self.browser.navigate(url)
            await asyncio.sleep(1.0)  # Wait for page load
            self._add_step(result, f"Navigated to {url}")
            return True
        except Exception as e:
            self._set_error(result, f"Navigation failed: {e}", "NAVIGATION_ERROR")
            return False
    
    async def _detect_form_schema(
        self,
        input_data: FormFillingInput,
        result: SkillResult,
    ) -> Optional[FormSchema]:
        """Detect form schema from current page."""
        if self.browser is None:
            return None
        
        self._logger.info("Detecting form schema from page")
        
        try:
            # Get page HTML
            html = await self.browser.extract_html()
            
            # Parse form elements
            fields = []
            
            # Simple regex-based detection (in production, use proper HTML parser)
            # Detect input fields
            input_pattern = r'<input[^>]+name=["\']([^"\']+)["\'][^>]*type=["\']([^"\']+)["\']'
            for match in re.finditer(input_pattern, html, re.IGNORECASE):
                name, input_type = match.groups()
                field_type = self._map_input_type(input_type)
                fields.append(FormField(
                    name=name,
                    field_type=field_type,
                    required="required" in match.group(0).lower(),
                ))
            
            # Detect textareas
            textarea_pattern = r'<textarea[^>]+name=["\']([^"\']+)["\']'
            for match in re.finditer(textarea_pattern, html, re.IGNORECASE):
                fields.append(FormField(
                    name=match.group(1),
                    field_type=FieldType.TEXTAREA,
                    required="required" in match.group(0).lower(),
                ))
            
            # Detect select elements
            select_pattern = r'<select[^>]+name=["\']([^"\']+)["\']'
            for match in re.finditer(select_pattern, html, re.IGNORECASE):
                fields.append(FormField(
                    name=match.group(1),
                    field_type=FieldType.SELECT,
                    required="required" in match.group(0).lower(),
                ))
            
            schema = FormSchema(
                name="detected_form",
                fields=fields,
            )
            
            self._logger.info(f"Detected {len(fields)} form fields")
            return schema
            
        except Exception as e:
            self._logger.error(f"Schema detection failed: {e}")
            return None
    
    def _map_input_type(self, input_type: str) -> FieldType:
        """Map HTML input type to FieldType."""
        type_map = {
            "text": FieldType.TEXT,
            "email": FieldType.EMAIL,
            "password": FieldType.PASSWORD,
            "number": FieldType.NUMBER,
            "tel": FieldType.TELEPHONE,
            "url": FieldType.URL,
            "checkbox": FieldType.CHECKBOX,
            "radio": FieldType.RADIO,
            "date": FieldType.DATE,
            "file": FieldType.FILE,
            "hidden": FieldType.HIDDEN,
        }
        return type_map.get(input_type.lower(), FieldType.UNKNOWN)
    
    async def _fill_fields(
        self,
        schema: FormSchema,
        data: Dict[str, Any],
        input_data: FormFillingInput,
        result: SkillResult,
    ) -> bool:
        """Fill form fields with data."""
        if self.browser is None:
            self._set_error(result, "No browser controller available", "CONFIG_ERROR")
            return False
        
        sorted_fields = schema.get_sorted_fields()
        filled_count = 0
        
        for field in sorted_fields:
            if field.name not in data:
                if field.required and field.default_value is None:
                    self._add_warning(result, f"Missing required field: {field.name}")
                continue
            
            value = data[field.name]
            fill_success = await self._fill_single_field(field, value, input_data, result)
            
            if fill_success:
                filled_count += 1
                self._add_step(result, f"Filled field '{field.name}' with value")
            else:
                if field.required:
                    self._add_warning(result, f"Failed to fill required field: {field.name}")
        
        result.metadata["fields_filled_count"] = filled_count
        return filled_count > 0
    
    async def _fill_single_field(
        self,
        field: FormField,
        value: Any,
        input_data: FormFillingInput,
        result: SkillResult,
    ) -> bool:
        """Fill a single form field."""
        try:
            # Get selector
            selector = field.selector or f"[name='{field.name}']"
            
            if field.field_type == FieldType.TEXT or field.field_type == FieldType.EMAIL:
                return await self._fill_text_field(selector, str(value))
            
            elif field.field_type == FieldType.TEXTAREA:
                return await self._fill_textarea(selector, str(value))
            
            elif field.field_type == FieldType.SELECT:
                return await self._fill_select(selector, str(value))
            
            elif field.field_type == FieldType.CHECKBOX:
                return await self._fill_checkbox(selector, bool(value))
            
            elif field.field_type == FieldType.RADIO:
                return await self._fill_radio(selector, str(value))
            
            elif field.field_type == FieldType.NUMBER:
                return await self._fill_text_field(selector, str(value))
            
            elif field.field_type == FieldType.PASSWORD:
                return await self._fill_text_field(selector, str(value))
            
            else:
                # Default: try text input
                return await self._fill_text_field(selector, str(value))
                
        except Exception as e:
            self._logger.error(f"Failed to fill field {field.name}: {e}")
            return False
    
    async def _fill_text_field(self, selector: str, value: str) -> bool:
        """Fill a text input field."""
        if self.browser is None:
            return False
        
        try:
            # Clear and type
            page = self.browser.page
            element = await page.wait_for_selector(selector, timeout=5000)
            if element:
                await element.fill(value)
                return True
        except Exception as e:
            self._logger.debug(f"Text field fill failed: {e}")
        return False
    
    async def _fill_textarea(self, selector: str, value: str) -> bool:
        """Fill a textarea field."""
        return await self._fill_text_field(selector, value)
    
    async def _fill_select(self, selector: str, value: str) -> bool:
        """Fill a select dropdown."""
        if self.browser is None:
            return False
        
        try:
            page = self.browser.page
            await page.select_option(selector, value)
            return True
        except Exception as e:
            self._logger.debug(f"Select fill failed: {e}")
        return False
    
    async def _fill_checkbox(self, selector: str, checked: bool) -> bool:
        """Fill a checkbox field."""
        if self.browser is None:
            return False
        
        try:
            page = self.browser.page
            if checked:
                await page.check(selector)
            else:
                await page.uncheck(selector)
            return True
        except Exception as e:
            self._logger.debug(f"Checkbox fill failed: {e}")
        return False
    
    async def _fill_radio(self, selector: str, value: str) -> bool:
        """Fill a radio button field."""
        if self.browser is None:
            return False
        
        try:
            page = self.browser.page
            # Radio buttons are selected by value
            radio_selector = f"{selector}[value='{value}']"
            await page.check(radio_selector)
            return True
        except Exception as e:
            self._logger.debug(f"Radio fill failed: {e}")
        return False
    
    async def _validate_form(
        self,
        schema: FormSchema,
        result: SkillResult,
    ) -> bool:
        """Validate filled form."""
        self._logger.info("Validating form")
        
        # Check for visible error messages
        if schema.error_indicator and self.browser:
            try:
                page = self.browser.page
                error_elem = await page.query_selector(schema.error_indicator)
                if error_elem:
                    error_text = await error_elem.text_content()
                    self._add_warning(result, f"Form validation error: {error_text}")
                    return False
            except Exception:
                pass
        
        self._add_step(result, "Form validation passed")
        return True
    
    async def _submit_form(
        self,
        schema: FormSchema,
        input_data: FormFillingInput,
        result: SkillResult,
    ) -> bool:
        """Submit the form."""
        if self.browser is None:
            self._set_error(result, "No browser controller available", "CONFIG_ERROR")
            return False
        
        self._logger.info("Submitting form")
        
        try:
            page = self.browser.page
            
            # Find submit button
            submit_selector = schema.submit_selector or "button[type='submit']"
            
            if schema.submit_visual_description and self.vision:
                # Use visual detection for submit button
                coords = await self.vision.get_click_coordinates(
                    schema.submit_visual_description
                )
                if coords:
                    await page.mouse.click(coords[0], coords[1])
                else:
                    await page.click(submit_selector)
            else:
                await page.click(submit_selector)
            
            # Wait after submit
            await asyncio.sleep(schema.submit_wait)
            
            # Check success indicator
            if schema.success_indicator:
                current_url = page.url
                if schema.success_indicator in current_url:
                    self._add_step(result, "Form submitted successfully (URL match)")
                    return True
                else:
                    self._add_warning(result, "Success indicator not matched")
                    return False
            
            self._add_step(result, "Form submitted")
            return True
            
        except Exception as e:
            self._set_error(result, f"Form submission failed: {e}", "SUBMIT_ERROR")
            return False

"""
Validator Agent Module

The Validator Agent is responsible for:
- Validating action results
- Checking expected outcomes
- Verifying page state
- Detecting errors and anomalies
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime
import uuid
import re

from .base import (
    BaseAgent,
    AgentConfig,
    AgentCapability,
    AgentResult,
)


class ValidationType(Enum):
    """Types of validation."""
    SUCCESS_CHECK = "success_check"
    ELEMENT_PRESENT = "element_present"
    ELEMENT_ABSENT = "element_absent"
    TEXT_PRESENT = "text_present"
    TEXT_ABSENT = "text_absent"
    URL_MATCH = "url_match"
    URL_CONTAINS = "url_contains"
    VALUE_CHECK = "value_check"
    STATE_CHECK = "state_check"
    CUSTOM = "custom"


class ValidationSeverity(Enum):
    """Severity of validation failures."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationCriteria:
    """Criteria for validation."""
    validation_type: ValidationType
    expected_value: Any = None
    selector: Optional[str] = None
    attribute: Optional[str] = None
    regex_pattern: Optional[str] = None
    custom_validator: Optional[str] = None  # Function name or expression
    is_required: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "validation_type": self.validation_type.value,
            "expected_value": self.expected_value,
            "selector": self.selector,
            "attribute": self.attribute,
            "regex_pattern": self.regex_pattern,
            "custom_validator": self.custom_validator,
            "is_required": self.is_required,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class ValidationFailure:
    """Details of a validation failure."""
    criteria: ValidationCriteria
    actual_value: Any
    message: str
    severity: ValidationSeverity
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "criteria": self.criteria.to_dict(),
            "actual_value": str(self.actual_value),
            "message": self.message,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ValidationResult:
    """Result of validation."""
    validation_id: str
    success: bool
    passed: int
    failed: int
    skipped: int
    failures: List[ValidationFailure] = field(default_factory=list)
    warnings: List[ValidationFailure] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def total(self) -> int:
        """Total validations performed."""
        return self.passed + self.failed + self.skipped
    
    @property
    def pass_rate(self) -> float:
        """Pass rate as percentage."""
        if self.total == 0:
            return 100.0
        return (self.passed / self.total) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "validation_id": self.validation_id,
            "success": self.success,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "total": self.total,
            "pass_rate": self.pass_rate,
            "failures": [f.to_dict() for f in self.failures],
            "warnings": [w.to_dict() for w in self.warnings],
            "data": self.data,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ValidationRequest:
    """Request for validation."""
    criteria: List[ValidationCriteria]
    action_result: Optional[Dict[str, Any]] = None
    page_state: Optional[Dict[str, Any]] = None
    screenshot: Optional[bytes] = None
    stop_on_failure: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class ValidatorAgent(BaseAgent):
    """
    Agent responsible for validating action results.
    
    Capabilities:
    - Verify expected outcomes
    - Check page state
    - Detect errors
    - Generate validation reports
    """
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        browser: Optional[Any] = None,
        vision_client: Optional[Any] = None,
    ):
        if config is None:
            config = AgentConfig(
                name="ValidatorAgent",
                capabilities={
                    AgentCapability.VALIDATION,
                    AgentCapability.VISUAL_PROCESSING,
                },
            )
        super().__init__(config)
        self._browser = browser
        self._vision_client = vision_client
        self._custom_validators: Dict[str, Callable] = {}
    
    def set_browser(self, browser: Any) -> None:
        """Set the browser instance."""
        self._browser = browser
    
    def set_vision_client(self, vision_client: Any) -> None:
        """Set the vision client."""
        self._vision_client = vision_client
    
    def register_validator(self, name: str, func: Callable) -> None:
        """Register a custom validator function."""
        self._custom_validators[name] = func
    
    async def execute(self, task: Any) -> AgentResult:
        """Execute a validation task."""
        if isinstance(task, ValidationRequest):
            result = await self.validate(task)
            return AgentResult(
                success=result.success,
                agent_id=self.agent_id,
                task_id=result.validation_id,
                data=result.to_dict(),
                metadata={"passed": result.passed, "failed": result.failed},
            )
        elif isinstance(task, dict):
            # Parse dict as validation request
            try:
                request = self._parse_validation_request(task)
                result = await self.validate(request)
                return AgentResult(
                    success=result.success,
                    agent_id=self.agent_id,
                    task_id=result.validation_id,
                    data=result.to_dict(),
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
    
    def _parse_validation_request(self, data: Dict[str, Any]) -> ValidationRequest:
        """Parse a dictionary into a ValidationRequest."""
        criteria = []
        for c in data.get("criteria", []):
            criteria.append(ValidationCriteria(
                validation_type=ValidationType(c.get("validation_type", "success_check")),
                expected_value=c.get("expected_value"),
                selector=c.get("selector"),
                attribute=c.get("attribute"),
                regex_pattern=c.get("regex_pattern"),
                custom_validator=c.get("custom_validator"),
                is_required=c.get("is_required", True),
                error_message=c.get("error_message"),
            ))
        
        return ValidationRequest(
            criteria=criteria,
            action_result=data.get("action_result"),
            page_state=data.get("page_state"),
            stop_on_failure=data.get("stop_on_failure", False),
            metadata=data.get("metadata", {}),
        )
    
    async def validate(self, request: ValidationRequest) -> ValidationResult:
        """Perform validation against criteria."""
        validation_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        passed = 0
        failed = 0
        skipped = 0
        failures = []
        warnings = []
        data = {}
        
        for criteria in request.criteria:
            if request.stop_on_failure and failures:
                skipped += 1
                continue
            
            try:
                result = await self._validate_criteria(criteria, request)
                
                if result["success"]:
                    passed += 1
                    data[criteria.validation_type.value] = result.get("value")
                else:
                    if criteria.is_required:
                        failed += 1
                        failures.append(ValidationFailure(
                            criteria=criteria,
                            actual_value=result.get("value"),
                            message=result.get("message", "Validation failed"),
                            severity=ValidationSeverity.ERROR,
                        ))
                    else:
                        warnings.append(ValidationFailure(
                            criteria=criteria,
                            actual_value=result.get("value"),
                            message=result.get("message", "Validation warning"),
                            severity=ValidationSeverity.WARNING,
                        ))
                        passed += 1  # Non-required failures still count as passed
                        
            except Exception as e:
                failed += 1
                failures.append(ValidationFailure(
                    criteria=criteria,
                    actual_value=str(e),
                    message=f"Validation error: {str(e)}",
                    severity=ValidationSeverity.ERROR,
                ))
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        return ValidationResult(
            validation_id=validation_id,
            success=failed == 0,
            passed=passed,
            failed=failed,
            skipped=skipped,
            failures=failures,
            warnings=warnings,
            data=data,
            duration_ms=duration_ms,
        )
    
    async def _validate_criteria(
        self,
        criteria: ValidationCriteria,
        request: ValidationRequest,
    ) -> Dict[str, Any]:
        """Validate a single criteria."""
        validation_type = criteria.validation_type
        
        if validation_type == ValidationType.SUCCESS_CHECK:
            return await self._validate_success(criteria, request)
        elif validation_type == ValidationType.ELEMENT_PRESENT:
            return await self._validate_element_present(criteria)
        elif validation_type == ValidationType.ELEMENT_ABSENT:
            return await self._validate_element_absent(criteria)
        elif validation_type == ValidationType.TEXT_PRESENT:
            return await self._validate_text_present(criteria)
        elif validation_type == ValidationType.TEXT_ABSENT:
            return await self._validate_text_absent(criteria)
        elif validation_type == ValidationType.URL_MATCH:
            return await self._validate_url_match(criteria)
        elif validation_type == ValidationType.URL_CONTAINS:
            return await self._validate_url_contains(criteria)
        elif validation_type == ValidationType.VALUE_CHECK:
            return await self._validate_value(criteria, request)
        elif validation_type == ValidationType.STATE_CHECK:
            return await self._validate_state(criteria, request)
        elif validation_type == ValidationType.CUSTOM:
            return await self._validate_custom(criteria, request)
        else:
            return {
                "success": False,
                "message": f"Unknown validation type: {validation_type}",
            }
    
    async def _validate_success(
        self,
        criteria: ValidationCriteria,
        request: ValidationRequest,
    ) -> Dict[str, Any]:
        """Validate that an action succeeded."""
        if request.action_result:
            success = request.action_result.get("success", False)
            return {
                "success": success,
                "value": success,
                "message": "Action success" if success else "Action failed",
            }
        return {
            "success": False,
            "message": "No action result provided",
        }
    
    async def _validate_element_present(
        self,
        criteria: ValidationCriteria,
    ) -> Dict[str, Any]:
        """Validate that an element is present."""
        if not self._browser or not criteria.selector:
            return {
                "success": False,
                "message": "Browser or selector not available",
            }
        
        try:
            page = self._browser.get_current_page()
            if not page:
                return {"success": False, "message": "No active page"}
            
            element = await page.query_selector(criteria.selector)
            is_present = element is not None
            
            if is_present:
                is_visible = await element.is_visible()
                return {
                    "success": True,
                    "value": {"present": True, "visible": is_visible},
                }
            else:
                return {
                    "success": False,
                    "value": {"present": False},
                    "message": f"Element not found: {criteria.selector}",
                }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }
    
    async def _validate_element_absent(
        self,
        criteria: ValidationCriteria,
    ) -> Dict[str, Any]:
        """Validate that an element is absent."""
        if not self._browser or not criteria.selector:
            return {
                "success": False,
                "message": "Browser or selector not available",
            }
        
        try:
            page = self._browser.get_current_page()
            if not page:
                return {"success": False, "message": "No active page"}
            
            element = await page.query_selector(criteria.selector)
            is_absent = element is None
            
            return {
                "success": is_absent,
                "value": {"absent": is_absent},
                "message": "Element is absent" if is_absent else f"Element found: {criteria.selector}",
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }
    
    async def _validate_text_present(
        self,
        criteria: ValidationCriteria,
    ) -> Dict[str, Any]:
        """Validate that text is present on the page."""
        if not self._browser:
            return {
                "success": False,
                "message": "Browser not available",
            }
        
        try:
            page = self._browser.get_current_page()
            if not page:
                return {"success": False, "message": "No active page"}
            
            expected_text = str(criteria.expected_value) if criteria.expected_value else ""
            
            if criteria.selector:
                element = await page.query_selector(criteria.selector)
                if element:
                    text = await element.text_content() or ""
                else:
                    return {
                        "success": False,
                        "message": f"Element not found: {criteria.selector}",
                    }
            else:
                text = await page.text_content("body") or ""
            
            if criteria.regex_pattern:
                pattern = re.compile(criteria.regex_pattern)
                is_present = bool(pattern.search(text))
            else:
                is_present = expected_text.lower() in text.lower()
            
            return {
                "success": is_present,
                "value": text[:200],  # Truncate for response
                "message": "Text found" if is_present else f"Text not found: {expected_text}",
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }
    
    async def _validate_text_absent(
        self,
        criteria: ValidationCriteria,
    ) -> Dict[str, Any]:
        """Validate that text is absent from the page."""
        if not self._browser:
            return {
                "success": False,
                "message": "Browser not available",
            }
        
        try:
            page = self._browser.get_current_page()
            if not page:
                return {"success": False, "message": "No active page"}
            
            forbidden_text = str(criteria.expected_value) if criteria.expected_value else ""
            
            if criteria.selector:
                element = await page.query_selector(criteria.selector)
                if element:
                    text = await element.text_content() or ""
                else:
                    return {"success": True, "value": "Element not found"}
            else:
                text = await page.text_content("body") or ""
            
            is_absent = forbidden_text.lower() not in text.lower()
            
            return {
                "success": is_absent,
                "value": is_absent,
                "message": "Text is absent" if is_absent else f"Text found: {forbidden_text}",
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }
    
    async def _validate_url_match(
        self,
        criteria: ValidationCriteria,
    ) -> Dict[str, Any]:
        """Validate that URL matches expected value."""
        if not self._browser:
            return {
                "success": False,
                "message": "Browser not available",
            }
        
        try:
            page = self._browser.get_current_page()
            if not page:
                return {"success": False, "message": "No active page"}
            
            current_url = page.url
            expected_url = str(criteria.expected_value) if criteria.expected_value else ""
            
            if criteria.regex_pattern:
                pattern = re.compile(criteria.regex_pattern)
                is_match = bool(pattern.match(current_url))
            else:
                is_match = current_url == expected_url
            
            return {
                "success": is_match,
                "value": current_url,
                "message": "URL matches" if is_match else f"URL mismatch: {current_url} != {expected_url}",
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }
    
    async def _validate_url_contains(
        self,
        criteria: ValidationCriteria,
    ) -> Dict[str, Any]:
        """Validate that URL contains expected value."""
        if not self._browser:
            return {
                "success": False,
                "message": "Browser not available",
            }
        
        try:
            page = self._browser.get_current_page()
            if not page:
                return {"success": False, "message": "No active page"}
            
            current_url = page.url
            expected_part = str(criteria.expected_value) if criteria.expected_value else ""
            
            is_match = expected_part.lower() in current_url.lower()
            
            return {
                "success": is_match,
                "value": current_url,
                "message": "URL contains expected value" if is_match else f"URL does not contain: {expected_part}",
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }
    
    async def _validate_value(
        self,
        criteria: ValidationCriteria,
        request: ValidationRequest,
    ) -> Dict[str, Any]:
        """Validate a specific value."""
        actual_value = None
        
        # Get value from different sources
        if criteria.selector and self._browser:
            try:
                page = self._browser.get_current_page()
                if page:
                    element = await page.query_selector(criteria.selector)
                    if element:
                        if criteria.attribute:
                            actual_value = await element.get_attribute(criteria.attribute)
                        else:
                            actual_value = await element.input_value()
            except Exception:
                pass
        elif request.action_result:
            actual_value = request.action_result.get("data")
        elif request.page_state:
            actual_value = request.page_state.get(criteria.attribute or "value")
        
        expected_value = criteria.expected_value
        
        # Compare values
        if criteria.regex_pattern and actual_value:
            pattern = re.compile(criteria.regex_pattern)
            is_match = bool(pattern.match(str(actual_value)))
        else:
            is_match = actual_value == expected_value
        
        return {
            "success": is_match,
            "value": actual_value,
            "message": "Value matches" if is_match else f"Value mismatch: {actual_value} != {expected_value}",
        }
    
    async def _validate_state(
        self,
        criteria: ValidationCriteria,
        request: ValidationRequest,
    ) -> Dict[str, Any]:
        """Validate page state."""
        if not self._browser:
            return {
                "success": False,
                "message": "Browser not available",
            }
        
        try:
            page = self._browser.get_current_page()
            if not page:
                return {"success": False, "message": "No active page"}
            
            # Check ready state
            ready_state = await page.evaluate("document.readyState")
            expected_state = str(criteria.expected_value) if criteria.expected_value else "complete"
            
            is_match = ready_state == expected_state
            
            return {
                "success": is_match,
                "value": ready_state,
                "message": f"Page state: {ready_state}",
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }
    
    async def _validate_custom(
        self,
        criteria: ValidationCriteria,
        request: ValidationRequest,
    ) -> Dict[str, Any]:
        """Run a custom validator."""
        validator_name = criteria.custom_validator
        
        if not validator_name:
            return {
                "success": False,
                "message": "No custom validator specified",
            }
        
        if validator_name in self._custom_validators:
            try:
                validator = self._custom_validators[validator_name]
                result = await validator(criteria, request)
                return result
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Custom validator error: {str(e)}",
                }
        else:
            return {
                "success": False,
                "message": f"Unknown custom validator: {validator_name}",
            }
    
    # Convenience methods
    
    async def validate_success(self, action_result: Dict[str, Any]) -> ValidationResult:
        """Validate that an action succeeded."""
        request = ValidationRequest(
            criteria=[ValidationCriteria(
                validation_type=ValidationType.SUCCESS_CHECK,
            )],
            action_result=action_result,
        )
        return await self.validate(request)
    
    async def validate_element_exists(self, selector: str) -> ValidationResult:
        """Validate that an element exists."""
        request = ValidationRequest(
            criteria=[ValidationCriteria(
                validation_type=ValidationType.ELEMENT_PRESENT,
                selector=selector,
            )],
        )
        return await self.validate(request)
    
    async def validate_url(self, expected: str, exact: bool = True) -> ValidationResult:
        """Validate current URL."""
        validation_type = ValidationType.URL_MATCH if exact else ValidationType.URL_CONTAINS
        request = ValidationRequest(
            criteria=[ValidationCriteria(
                validation_type=validation_type,
                expected_value=expected,
            )],
        )
        return await self.validate(request)
    
    async def validate_text_on_page(self, text: str, present: bool = True) -> ValidationResult:
        """Validate text presence on page."""
        validation_type = ValidationType.TEXT_PRESENT if present else ValidationType.TEXT_ABSENT
        request = ValidationRequest(
            criteria=[ValidationCriteria(
                validation_type=validation_type,
                expected_value=text,
            )],
        )
        return await self.validate(request)
    
    async def create_combined_validation(
        self,
        checks: List[Dict[str, Any]],
    ) -> ValidationResult:
        """Create and run multiple validations."""
        criteria = []
        for check in checks:
            criteria.append(ValidationCriteria(
                validation_type=ValidationType(check.get("type", "success_check")),
                expected_value=check.get("expected"),
                selector=check.get("selector"),
                attribute=check.get("attribute"),
                is_required=check.get("required", True),
            ))
        
        request = ValidationRequest(criteria=criteria)
        return await self.validate(request)

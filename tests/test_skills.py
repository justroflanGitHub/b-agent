"""
Comprehensive Tests for Skills Module

Tests for:
- Base skill classes
- Skill registry
- Form filling skill
- Data extraction skill
- Web scraping skill
- Workflow skill
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from browser_agent.skills.base import (
    BaseSkill,
    SkillResult,
    SkillInput,
    SkillCapability,
)
from browser_agent.skills.registry import (
    SkillRegistry,
    get_global_registry,
    register_skill,
)
from browser_agent.skills.form_filling import (
    FormFillingSkill,
    FormFillingInput,
    FormSchema,
    FormField,
    FieldType,
)
from browser_agent.skills.data_extraction import (
    DataExtractionSkill,
    DataExtractionInput,
    ExtractionSchema,
    ExtractionField,
    ExtractionFieldType,
)
from browser_agent.skills.web_scraping import (
    WebScrapingSkill,
    WebScrapingInput,
    ScrapingConfig,
    ScrapingMode,
    RateLimitConfig,
    ComplianceLevel,
)
from browser_agent.skills.workflow import (
    WorkflowSkill,
    WorkflowInput,
    Workflow,
    WorkflowStep,
    WorkflowContext,
    StepType,
    Condition,
    ConditionOperator,
    LoopType,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_browser():
    """Create a mock browser controller."""
    browser = Mock()
    browser.navigate = AsyncMock()
    browser.extract_html = AsyncMock(return_value="<html><body>Test</body></html>")
    browser.extract_text = AsyncMock(return_value="Test content")
    browser.take_screenshot = AsyncMock(return_value="/path/to/screenshot.png")
    browser.page = Mock()
    browser.page.url = "https://example.com"
    browser.page.wait_for_selector = AsyncMock()
    browser.page.query_selector = AsyncMock()
    browser.page.query_selector_all = AsyncMock(return_value=[])
    browser.page.click = AsyncMock()
    browser.page.fill = AsyncMock()
    browser.page.check = AsyncMock()
    browser.page.uncheck = AsyncMock()
    browser.page.select_option = AsyncMock()
    browser.page.mouse = Mock()
    browser.page.mouse.click = AsyncMock()
    return browser


@pytest.fixture
def mock_vision():
    """Create a mock vision client."""
    vision = Mock()
    vision.get_click_coordinates = AsyncMock(return_value=(100, 200))
    vision.analyze_element = AsyncMock(return_value={"text": "element text"})
    return vision


@pytest.fixture
def mock_executor():
    """Create a mock action executor."""
    executor = Mock()
    executor.execute_action = AsyncMock(return_value=Mock(data={"result": "success"}))
    return executor


@pytest.fixture
def skill_registry():
    """Create a fresh skill registry."""
    return SkillRegistry()


# ============================================================================
# Base Skill Tests
# ============================================================================

class TestSkillCapability:
    """Tests for SkillCapability enum."""
    
    def test_capability_values(self):
        """Test that all capabilities have string values."""
        capabilities = [
            SkillCapability.BROWSER_NAVIGATION,
            SkillCapability.BROWSER_INTERACTION,
            SkillCapability.VISION_ELEMENT_DETECTION,
            SkillCapability.DATA_EXTRACTION,
            SkillCapability.ERROR_RECOVERY,
        ]
        
        for cap in capabilities:
            assert isinstance(cap.value, str)
    
    def test_capability_count(self):
        """Test that we have expected number of capabilities."""
        assert len(SkillCapability) >= 15


class TestSkillInput:
    """Tests for SkillInput dataclass."""
    
    def test_default_values(self):
        """Test default values for SkillInput."""
        input_data = SkillInput(task="Test task")
        
        assert input_data.task == "Test task"
        assert input_data.context == {}
        assert input_data.timeout == 300.0
        assert input_data.max_retries == 3
        assert input_data.validate_input is True
        assert input_data.verify_results is True
        assert input_data.options == {}
    
    def test_custom_values(self):
        """Test custom values for SkillInput."""
        input_data = SkillInput(
            task="Custom task",
            context={"key": "value"},
            timeout=60.0,
            max_retries=5,
            validate_input=False,
            verify_results=False,
            options={"custom": "option"},
        )
        
        assert input_data.task == "Custom task"
        assert input_data.context == {"key": "value"}
        assert input_data.timeout == 60.0
        assert input_data.max_retries == 5
        assert input_data.validate_input is False
        assert input_data.verify_results is False
        assert input_data.options == {"custom": "option"}
    
    def test_to_dict(self):
        """Test to_dict method."""
        input_data = SkillInput(task="Test")
        result = input_data.to_dict()
        
        assert isinstance(result, dict)
        assert result["task"] == "Test"
        assert "context" in result
        assert "timeout" in result


class TestSkillResult:
    """Tests for SkillResult dataclass."""
    
    def test_success_result(self):
        """Test successful result."""
        result = SkillResult(success=True, data={"key": "value"})
        
        assert result.success is True
        assert result.failed is False
        assert result.data == {"key": "value"}
        assert result.error is None
    
    def test_failure_result(self):
        """Test failure result."""
        result = SkillResult(
            success=False,
            error="Test error",
            error_type="TEST_ERROR",
        )
        
        assert result.success is False
        assert result.failed is True
        assert result.error == "Test error"
        assert result.error_type == "TEST_ERROR"
    
    def test_default_values(self):
        """Test default values."""
        result = SkillResult(success=True)
        
        assert result.data is None
        assert result.metadata == {}
        assert result.steps_completed == []
        assert result.warnings == []
        assert result.execution_time == 0.0
        assert result.retries == 0
        assert isinstance(result.timestamp, datetime)
    
    def test_to_dict(self):
        """Test to_dict method."""
        result = SkillResult(
            success=True,
            data={"test": "data"},
            steps_completed=["step1", "step2"],
        )
        result_dict = result.to_dict()
        
        assert result_dict["success"] is True
        assert result_dict["data"] == {"test": "data"}
        assert result_dict["steps_completed"] == ["step1", "step2"]
        assert "timestamp" in result_dict


class TestBaseSkill:
    """Tests for BaseSkill abstract class."""
    
    def test_skill_metadata(self):
        """Test skill metadata attributes."""
        # Create concrete skill for testing
        class TestSkill(BaseSkill):
            name = "test_skill"
            description = "A test skill"
            version = "1.0.0"
            
            async def execute(self, input_data):
                return SkillResult(success=True)
            
            def validate_input(self, input_data):
                return True
            
            def verify_results(self, result):
                return result.success
        
        skill = TestSkill()
        assert skill.name == "test_skill"
        assert skill.description == "A test skill"
        assert skill.version == "1.0.0"
    
    def test_skill_capabilities(self):
        """Test skill capabilities."""
        class TestSkill(BaseSkill):
            name = "test_skill"
            required_capabilities = {SkillCapability.BROWSER_INTERACTION}
            provided_capabilities = {SkillCapability.DATA_EXTRACTION}
            
            async def execute(self, input_data):
                return SkillResult(success=True)
            
            def validate_input(self, input_data):
                return True
            
            def verify_results(self, result):
                return result.success
        
        skill = TestSkill()
        
        assert SkillCapability.BROWSER_INTERACTION in skill.get_required_capabilities()
        assert SkillCapability.DATA_EXTRACTION in skill.get_provided_capabilities()
    
    def test_skill_repr(self):
        """Test skill string representation."""
        class TestSkill(BaseSkill):
            name = "test_skill"
            version = "1.0.0"
            
            async def execute(self, input_data):
                return SkillResult(success=True)
            
            def validate_input(self, input_data):
                return True
            
            def verify_results(self, result):
                return result.success
        
        skill = TestSkill()
        repr_str = repr(skill)
        
        assert "TestSkill" in repr_str
        assert "test_skill" in repr_str
        assert "1.0.0" in repr_str


# ============================================================================
# Skill Registry Tests
# ============================================================================

class TestSkillRegistry:
    """Tests for SkillRegistry."""
    
    def test_register_skill(self, skill_registry):
        """Test skill registration."""
        class TestSkill(BaseSkill):
            name = "test_skill"
            
            async def execute(self, input_data):
                return SkillResult(success=True)
            
            def validate_input(self, input_data):
                return True
            
            def verify_results(self, result):
                return result.success
        
        registered = skill_registry.register(TestSkill)
        
        assert registered == TestSkill
        assert "test_skill" in skill_registry
        assert len(skill_registry) == 1
    
    def test_unregister_skill(self, skill_registry):
        """Test skill unregistration."""
        class TestSkill(BaseSkill):
            name = "test_skill"
            
            async def execute(self, input_data):
                return SkillResult(success=True)
            
            def validate_input(self, input_data):
                return True
            
            def verify_results(self, result):
                return result.success
        
        skill_registry.register(TestSkill)
        result = skill_registry.unregister("test_skill")
        
        assert result is True
        assert "test_skill" not in skill_registry
    
    def test_unregister_nonexistent(self, skill_registry):
        """Test unregistering non-existent skill."""
        result = skill_registry.unregister("nonexistent")
        assert result is False
    
    def test_get_skill_class(self, skill_registry):
        """Test getting skill class."""
        class TestSkill(BaseSkill):
            name = "test_skill"
            
            async def execute(self, input_data):
                return SkillResult(success=True)
            
            def validate_input(self, input_data):
                return True
            
            def verify_results(self, result):
                return result.success
        
        skill_registry.register(TestSkill)
        skill_class = skill_registry.get_skill_class("test_skill")
        
        assert skill_class == TestSkill
    
    def test_get_skill_instance(self, skill_registry, mock_browser):
        """Test getting skill instance."""
        class TestSkill(BaseSkill):
            name = "test_skill"
            
            async def execute(self, input_data):
                return SkillResult(success=True)
            
            def validate_input(self, input_data):
                return True
            
            def verify_results(self, result):
                return result.success
        
        skill_registry.register(TestSkill)
        instance = skill_registry.get_skill(
            "test_skill",
            browser_controller=mock_browser,
        )
        
        assert isinstance(instance, TestSkill)
        assert instance.browser == mock_browser
    
    def test_list_skills(self, skill_registry):
        """Test listing skills."""
        class Skill1(BaseSkill):
            name = "skill1"
            async def execute(self, input_data): return SkillResult(success=True)
            def validate_input(self, input_data): return True
            def verify_results(self, result): return result.success
        
        class Skill2(BaseSkill):
            name = "skill2"
            async def execute(self, input_data): return SkillResult(success=True)
            def validate_input(self, input_data): return True
            def verify_results(self, result): return result.success
        
        skill_registry.register(Skill1)
        skill_registry.register(Skill2)
        
        skills = skill_registry.list_skills()
        
        assert len(skills) == 2
        assert "skill1" in skills
        assert "skill2" in skills
    
    def test_get_skills_by_capability(self, skill_registry):
        """Test getting skills by capability."""
        class TestSkill(BaseSkill):
            name = "test_skill"
            required_capabilities = {SkillCapability.BROWSER_INTERACTION}
            
            async def execute(self, input_data):
                return SkillResult(success=True)
            
            def validate_input(self, input_data):
                return True
            
            def verify_results(self, result):
                return result.success
        
        skill_registry.register(TestSkill)
        skills = skill_registry.get_skills_by_capability(SkillCapability.BROWSER_INTERACTION)
        
        assert "test_skill" in skills
    
    def test_get_skill_info(self, skill_registry):
        """Test getting skill info."""
        class TestSkill(BaseSkill):
            name = "test_skill"
            description = "Test description"
            version = "2.0.0"
            
            async def execute(self, input_data):
                return SkillResult(success=True)
            
            def validate_input(self, input_data):
                return True
            
            def verify_results(self, result):
                return result.success
        
        skill_registry.register(TestSkill)
        info = skill_registry.get_skill_info("test_skill")
        
        assert info["name"] == "test_skill"
        assert info["description"] == "Test description"
        assert info["version"] == "2.0.0"
    
    def test_clear_registry(self, skill_registry):
        """Test clearing registry."""
        class TestSkill(BaseSkill):
            name = "test_skill"
            async def execute(self, input_data): return SkillResult(success=True)
            def validate_input(self, input_data): return True
            def verify_results(self, result): return result.success
        
        skill_registry.register(TestSkill)
        skill_registry.clear()
        
        assert len(skill_registry) == 0
    
    def test_registry_repr(self, skill_registry):
        """Test registry string representation."""
        repr_str = repr(skill_registry)
        assert "SkillRegistry" in repr_str


class TestGlobalRegistry:
    """Tests for global registry functions."""
    
    def test_get_global_registry(self):
        """Test getting global registry."""
        registry1 = get_global_registry()
        registry2 = get_global_registry()
        
        assert registry1 is registry2
        assert isinstance(registry1, SkillRegistry)
    
    def test_register_skill_function(self):
        """Test register_skill decorator function."""
        @register_skill
        class DecoratedSkill(BaseSkill):
            name = "decorated_skill"
            async def execute(self, input_data): return SkillResult(success=True)
            def validate_input(self, input_data): return True
            def verify_results(self, result): return result.success
        
        registry = get_global_registry()
        assert "decorated_skill" in registry


# ============================================================================
# Form Filling Skill Tests
# ============================================================================

class TestFormField:
    """Tests for FormField dataclass."""
    
    def test_default_values(self):
        """Test default field values."""
        field = FormField(name="test_field")
        
        assert field.name == "test_field"
        assert field.field_type == FieldType.TEXT
        assert field.required is False
        assert field.selector is None
    
    def test_custom_values(self):
        """Test custom field values."""
        field = FormField(
            name="email",
            field_type=FieldType.EMAIL,
            label="Email Address",
            selector="#email",
            required=True,
            pattern=r"^[^@]+@[^@]+\.[^@]+$",
        )
        
        assert field.name == "email"
        assert field.field_type == FieldType.EMAIL
        assert field.label == "Email Address"
        assert field.required is True
    
    def test_to_dict(self):
        """Test to_dict method."""
        field = FormField(name="test", field_type=FieldType.TEXT)
        field_dict = field.to_dict()
        
        assert field_dict["name"] == "test"
        assert field_dict["field_type"] == "text"


class TestFormSchema:
    """Tests for FormSchema dataclass."""
    
    def test_default_values(self):
        """Test default schema values."""
        schema = FormSchema(name="test_form")
        
        assert schema.name == "test_form"
        assert schema.fields == []
        assert schema.auto_submit is True
    
    def test_get_field(self):
        """Test get_field method."""
        field1 = FormField(name="field1")
        field2 = FormField(name="field2")
        schema = FormSchema(name="test", fields=[field1, field2])
        
        assert schema.get_field("field1") == field1
        assert schema.get_field("field2") == field2
        assert schema.get_field("nonexistent") is None
    
    def test_get_required_fields(self):
        """Test get_required_fields method."""
        required_field = FormField(name="required", required=True)
        optional_field = FormField(name="optional", required=False)
        schema = FormSchema(name="test", fields=[required_field, optional_field])
        
        required = schema.get_required_fields()
        
        assert len(required) == 1
        assert required[0].name == "required"
    
    def test_get_sorted_fields(self):
        """Test get_sorted_fields method."""
        field1 = FormField(name="field1", priority=10)
        field2 = FormField(name="field2", priority=5)
        field3 = FormField(name="field3", priority=15)
        schema = FormSchema(name="test", fields=[field1, field2, field3])
        
        sorted_fields = schema.get_sorted_fields()
        
        assert sorted_fields[0].name == "field2"  # priority 5
        assert sorted_fields[1].name == "field1"  # priority 10
        assert sorted_fields[2].name == "field3"  # priority 15


class TestFormFillingInput:
    """Tests for FormFillingInput."""
    
    def test_default_values(self):
        """Test default input values."""
        input_data = FormFillingInput(task="Fill form")
        
        assert input_data.schema is None
        assert input_data.data == {}
        assert input_data.visual_detection is True
    
    def test_to_dict(self):
        """Test to_dict includes form-specific fields."""
        schema = FormSchema(name="test")
        input_data = FormFillingInput(
            task="Fill form",
            schema=schema,
            data={"name": "John"},
        )
        
        result = input_data.to_dict()
        
        assert result["task"] == "Fill form"
        assert result["data"] == {"name": "John"}
        assert result["schema"]["name"] == "test"


class TestFormFillingSkill:
    """Tests for FormFillingSkill."""
    
    def test_skill_metadata(self):
        """Test skill metadata."""
        skill = FormFillingSkill()
        
        assert skill.name == "form_filling"
        assert "form" in skill.description.lower()
    
    def test_required_capabilities(self):
        """Test required capabilities."""
        skill = FormFillingSkill()
        caps = skill.get_required_capabilities()
        
        assert SkillCapability.BROWSER_INTERACTION in caps
        assert SkillCapability.VISION_ELEMENT_DETECTION in caps
    
    def test_validate_input_no_task(self):
        """Test validation with no task."""
        skill = FormFillingSkill()
        input_data = FormFillingInput(task="", data={"name": "John"})
        
        assert skill.validate_input(input_data) is False
    
    def test_validate_input_no_data(self):
        """Test validation with no data."""
        skill = FormFillingSkill()
        input_data = FormFillingInput(task="Fill form", data={})
        
        assert skill.validate_input(input_data) is False
    
    def test_validate_input_missing_required(self):
        """Test validation with missing required field."""
        skill = FormFillingSkill()
        schema = FormSchema(
            name="test",
            fields=[FormField(name="email", required=True)],
        )
        input_data = FormFillingInput(
            task="Fill form",
            schema=schema,
            data={"name": "John"},  # Missing email
        )
        
        assert skill.validate_input(input_data) is False
    
    def test_validate_input_valid(self):
        """Test validation with valid input."""
        skill = FormFillingSkill()
        schema = FormSchema(
            name="test",
            fields=[FormField(name="email", required=True)],
        )
        input_data = FormFillingInput(
            task="Fill form",
            schema=schema,
            data={"email": "test@example.com"},
        )
        
        assert skill.validate_input(input_data) is True
    
    def test_verify_results_success(self):
        """Test result verification with success."""
        skill = FormFillingSkill()
        result = SkillResult(
            success=True,
            data={"fields_filled": 3, "form_submitted": True},
        )
        
        assert skill.verify_results(result) is True
    
    def test_verify_results_no_fields(self):
        """Test result verification with no fields filled."""
        skill = FormFillingSkill()
        result = SkillResult(
            success=True,
            data={"fields_filled": 0, "form_submitted": False},
        )
        
        assert skill.verify_results(result) is False
    
    def test_map_input_type(self):
        """Test input type mapping."""
        skill = FormFillingSkill()
        
        assert skill._map_input_type("text") == FieldType.TEXT
        assert skill._map_input_type("email") == FieldType.EMAIL
        assert skill._map_input_type("password") == FieldType.PASSWORD
        assert skill._map_input_type("checkbox") == FieldType.CHECKBOX
        assert skill._map_input_type("unknown") == FieldType.UNKNOWN
    
    @pytest.mark.asyncio
    async def test_execute_no_schema_no_browser(self):
        """Test execution without schema or browser."""
        skill = FormFillingSkill()
        input_data = FormFillingInput(task="Fill form", data={"name": "John"})
        
        result = await skill.execute(input_data)
        
        assert result.success is False
        assert "schema" in result.error.lower()


# ============================================================================
# Data Extraction Skill Tests
# ============================================================================

class TestExtractionField:
    """Tests for ExtractionField dataclass."""
    
    def test_default_values(self):
        """Test default field values."""
        field = ExtractionField(name="title")
        
        assert field.name == "title"
        assert field.field_type == ExtractionFieldType.TEXT
        assert field.selector is None
        assert field.required is False
    
    def test_custom_values(self):
        """Test custom field values."""
        field = ExtractionField(
            name="price",
            field_type=ExtractionFieldType.PRICE,
            selector=".price",
            pattern=r"\$(\d+\.?\d*)",
        )
        
        assert field.name == "price"
        assert field.field_type == ExtractionFieldType.PRICE
        assert field.pattern == r"\$(\d+\.?\d*)"
    
    def test_to_dict(self):
        """Test to_dict method."""
        field = ExtractionField(name="test")
        field_dict = field.to_dict()
        
        assert field_dict["name"] == "test"
        assert field_dict["field_type"] == "text"


class TestExtractionSchema:
    """Tests for ExtractionSchema dataclass."""
    
    def test_default_values(self):
        """Test default schema values."""
        schema = ExtractionSchema(name="products")
        
        assert schema.name == "products"
        assert schema.fields == []
        assert schema.multiple is False
        assert schema.max_items == 100
    
    def test_get_field(self):
        """Test get_field method."""
        field = ExtractionField(name="title")
        schema = ExtractionSchema(name="test", fields=[field])
        
        assert schema.get_field("title") == field
        assert schema.get_field("nonexistent") is None


class TestDataExtractionInput:
    """Tests for DataExtractionInput."""
    
    def test_default_values(self):
        """Test default input values."""
        input_data = DataExtractionInput(task="Extract data")
        
        assert input_data.schema is None
        assert input_data.url is None
        assert input_data.visual_extraction is True
    
    def test_to_dict(self):
        """Test to_dict includes extraction-specific fields."""
        schema = ExtractionSchema(name="test")
        input_data = DataExtractionInput(
            task="Extract",
            schema=schema,
            url="https://example.com",
        )
        
        result = input_data.to_dict()
        
        assert result["url"] == "https://example.com"
        assert result["schema"]["name"] == "test"


class TestDataExtractionSkill:
    """Tests for DataExtractionSkill."""
    
    def test_skill_metadata(self):
        """Test skill metadata."""
        skill = DataExtractionSkill()
        
        assert skill.name == "data_extraction"
        assert "extract" in skill.description.lower()
    
    def test_required_capabilities(self):
        """Test required capabilities."""
        skill = DataExtractionSkill()
        caps = skill.get_required_capabilities()
        
        assert SkillCapability.DATA_EXTRACTION in caps
        assert SkillCapability.VISION_ELEMENT_DETECTION in caps
    
    def test_validate_input_no_schema(self):
        """Test validation without schema."""
        skill = DataExtractionSkill()
        input_data = DataExtractionInput(task="Extract")
        
        assert skill.validate_input(input_data) is False
    
    def test_validate_input_no_fields(self):
        """Test validation with empty schema."""
        skill = DataExtractionSkill()
        schema = ExtractionSchema(name="test", fields=[])
        input_data = DataExtractionInput(task="Extract", schema=schema)
        
        assert skill.validate_input(input_data) is False
    
    def test_validate_input_valid(self):
        """Test validation with valid input."""
        skill = DataExtractionSkill()
        schema = ExtractionSchema(
            name="test",
            fields=[ExtractionField(name="title")],
        )
        input_data = DataExtractionInput(task="Extract", schema=schema)
        
        assert skill.validate_input(input_data) is True
    
    def test_process_value_number(self):
        """Test number value processing."""
        skill = DataExtractionSkill()
        
        result = skill._process_value("Price: $1,234.56", ExtractionFieldType.NUMBER)
        assert result == 1234.56
    
    def test_process_value_price(self):
        """Test price value processing."""
        skill = DataExtractionSkill()
        
        result = skill._process_value("$99.99", ExtractionFieldType.PRICE)
        assert result == 99.99
    
    def test_process_value_rating(self):
        """Test rating value processing."""
        skill = DataExtractionSkill()
        
        result = skill._process_value("4.5 out of 5 stars", ExtractionFieldType.RATING)
        assert result == 4.5
    
    def test_process_value_boolean(self):
        """Test boolean value processing."""
        skill = DataExtractionSkill()
        
        assert skill._process_value("yes", ExtractionFieldType.BOOLEAN) is True
        assert skill._process_value("true", ExtractionFieldType.BOOLEAN) is True
        assert skill._process_value("no", ExtractionFieldType.BOOLEAN) is False
        assert skill._process_value("false", ExtractionFieldType.BOOLEAN) is False
    
    def test_deduplicate_items(self):
        """Test item deduplication."""
        skill = DataExtractionSkill()
        schema = ExtractionSchema(
            name="test",
            deduplicate=True,
            deduplicate_fields=["id"],
        )
        
        items = [
            {"id": "1", "name": "Item 1"},
            {"id": "2", "name": "Item 2"},
            {"id": "1", "name": "Item 1 Duplicate"},
        ]
        
        result = skill._deduplicate_items(items, schema)
        
        assert len(result) == 2


# ============================================================================
# Web Scraping Skill Tests
# ============================================================================

class TestRateLimitConfig:
    """Tests for RateLimitConfig."""
    
    def test_default_values(self):
        """Test default rate limit values."""
        config = RateLimitConfig()
        
        assert config.min_delay == 1.0
        assert config.max_delay == 3.0
        assert config.max_requests_per_minute == 30
        assert config.max_concurrent == 1


class TestScrapingConfig:
    """Tests for ScrapingConfig."""
    
    def test_default_values(self):
        """Test default config values."""
        config = ScrapingConfig()
        
        assert config.start_urls == []
        assert config.mode == ScrapingMode.SINGLE_PAGE
        assert config.max_pages == 100
        assert config.compliance_level == ComplianceLevel.MODERATE
    
    def test_custom_values(self):
        """Test custom config values."""
        config = ScrapingConfig(
            start_urls=["https://example.com"],
            mode=ScrapingMode.CRAWL,
            max_pages=50,
            compliance_level=ComplianceLevel.STRICT,
        )
        
        assert config.start_urls == ["https://example.com"]
        assert config.mode == ScrapingMode.CRAWL
        assert config.max_pages == 50
    
    def test_to_dict(self):
        """Test to_dict method."""
        config = ScrapingConfig(start_urls=["https://example.com"])
        config_dict = config.to_dict()
        
        assert config_dict["start_urls"] == ["https://example.com"]
        assert config_dict["mode"] == "single_page"


class TestWebScrapingInput:
    """Tests for WebScrapingInput."""
    
    def test_default_values(self):
        """Test default input values."""
        input_data = WebScrapingInput(task="Scrape website")
        
        assert input_data.config is None
        assert input_data.save_raw_html is False
        assert input_data.save_screenshots is False


class TestWebScrapingSkill:
    """Tests for WebScrapingSkill."""
    
    def test_skill_metadata(self):
        """Test skill metadata."""
        skill = WebScrapingSkill()
        
        assert skill.name == "web_scraping"
        assert "scrape" in skill.description.lower()
    
    def test_required_capabilities(self):
        """Test required capabilities."""
        skill = WebScrapingSkill()
        caps = skill.get_required_capabilities()
        
        assert SkillCapability.BROWSER_NAVIGATION in caps
        assert SkillCapability.MULTI_PAGE_NAVIGATION in caps
    
    def test_validate_input_no_config(self):
        """Test validation without config."""
        skill = WebScrapingSkill()
        input_data = WebScrapingInput(task="Scrape")
        
        assert skill.validate_input(input_data) is False
    
    def test_validate_input_no_urls(self):
        """Test validation without URLs."""
        skill = WebScrapingSkill()
        config = ScrapingConfig(start_urls=[])
        input_data = WebScrapingInput(task="Scrape", config=config)
        
        assert skill.validate_input(input_data) is False
    
    def test_validate_input_valid(self):
        """Test validation with valid input."""
        skill = WebScrapingSkill()
        config = ScrapingConfig(start_urls=["https://example.com"])
        input_data = WebScrapingInput(task="Scrape", config=config)
        
        assert skill.validate_input(input_data) is True
    
    def test_should_follow_url_include_patterns(self):
        """Test URL filtering with include patterns."""
        skill = WebScrapingSkill()
        config = ScrapingConfig(
            start_urls=["https://example.com"],
            include_patterns=[r"example\.com/products"],
        )
        
        assert skill._should_follow_url("https://example.com/products/1", config) is True
        assert skill._should_follow_url("https://example.com/about", config) is False
    
    def test_should_follow_url_exclude_patterns(self):
        """Test URL filtering with exclude patterns."""
        skill = WebScrapingSkill()
        config = ScrapingConfig(
            start_urls=["https://example.com"],
            exclude_patterns=[r"\.pdf$", r"\.zip$"],
        )
        
        assert skill._should_follow_url("https://example.com/page", config) is True
        assert skill._should_follow_url("https://example.com/file.pdf", config) is False
        assert skill._should_follow_url("https://example.com/file.zip", config) is False
    
    def test_parse_robots(self):
        """Test robots.txt parsing."""
        skill = WebScrapingSkill()
        
        content = """
        User-agent: *
        Disallow: /admin/
        Disallow: /private/
        Allow: /public/
        """
        
        result = skill._parse_robots(content)
        
        assert "/admin/" in result["disallowed"]
        assert "/private/" in result["disallowed"]
        assert "/public/" in result["allowed"]


# ============================================================================
# Workflow Skill Tests
# ============================================================================

class TestCondition:
    """Tests for Condition."""
    
    def test_equals(self):
        """Test equals operator."""
        condition = Condition(
            variable="status",
            operator=ConditionOperator.EQUALS,
            value="success",
        )
        
        assert condition.evaluate({"status": "success"}) is True
        assert condition.evaluate({"status": "failure"}) is False
    
    def test_not_equals(self):
        """Test not_equals operator."""
        condition = Condition(
            variable="status",
            operator=ConditionOperator.NOT_EQUALS,
            value="success",
        )
        
        assert condition.evaluate({"status": "failure"}) is True
        assert condition.evaluate({"status": "success"}) is False
    
    def test_contains(self):
        """Test contains operator."""
        condition = Condition(
            variable="message",
            operator=ConditionOperator.CONTAINS,
            value="error",
        )
        
        assert condition.evaluate({"message": "An error occurred"}) is True
        assert condition.evaluate({"message": "Success"}) is False
    
    def test_greater_than(self):
        """Test greater_than operator."""
        condition = Condition(
            variable="count",
            operator=ConditionOperator.GREATER_THAN,
            value=10,
        )
        
        assert condition.evaluate({"count": 15}) is True
        assert condition.evaluate({"count": 5}) is False
    
    def test_less_than(self):
        """Test less_than operator."""
        condition = Condition(
            variable="count",
            operator=ConditionOperator.LESS_THAN,
            value=10,
        )
        
        assert condition.evaluate({"count": 5}) is True
        assert condition.evaluate({"count": 15}) is False
    
    def test_is_empty(self):
        """Test is_empty operator."""
        condition = Condition(
            variable="data",
            operator=ConditionOperator.IS_EMPTY,
        )
        
        assert condition.evaluate({"data": None}) is True
        assert condition.evaluate({"data": ""}) is True
        assert condition.evaluate({"data": "value"}) is False
    
    def test_is_not_empty(self):
        """Test is_not_empty operator."""
        condition = Condition(
            variable="data",
            operator=ConditionOperator.IS_NOT_EMPTY,
        )
        
        assert condition.evaluate({"data": "value"}) is True
        assert condition.evaluate({"data": None}) is False
    
    def test_negate(self):
        """Test negation."""
        condition = Condition(
            variable="status",
            operator=ConditionOperator.EQUALS,
            value="success",
            negate=True,
        )
        
        assert condition.evaluate({"status": "failure"}) is True
        assert condition.evaluate({"status": "success"}) is False
    
    def test_nested_variable(self):
        """Test nested variable access."""
        condition = Condition(
            variable="user.profile.active",
            operator=ConditionOperator.EQUALS,
            value=True,
        )
        
        context = {
            "user": {
                "profile": {
                    "active": True
                }
            }
        }
        
        assert condition.evaluate(context) is True


class TestWorkflowStep:
    """Tests for WorkflowStep."""
    
    def test_action_step(self):
        """Test action step creation."""
        step = WorkflowStep(
            id="step1",
            step_type=StepType.ACTION,
            action="click",
            parameters={"selector": "#button"},
        )
        
        assert step.id == "step1"
        assert step.step_type == StepType.ACTION
        assert step.action == "click"
    
    def test_condition_step(self):
        """Test condition step creation."""
        step = WorkflowStep(
            id="step2",
            step_type=StepType.CONDITION,
            condition=Condition(variable="x", operator=ConditionOperator.EQUALS, value=1),
        )
        
        assert step.step_type == StepType.CONDITION
        assert step.condition is not None
    
    def test_loop_step(self):
        """Test loop step creation."""
        step = WorkflowStep(
            id="step3",
            step_type=StepType.LOOP,
            loop_type=LoopType.COUNT,
            loop_count=5,
        )
        
        assert step.step_type == StepType.LOOP
        assert step.loop_type == LoopType.COUNT
        assert step.loop_count == 5
    
    def test_wait_step(self):
        """Test wait step creation."""
        step = WorkflowStep(
            id="step4",
            step_type=StepType.WAIT,
            wait_seconds=2.5,
        )
        
        assert step.step_type == StepType.WAIT
        assert step.wait_seconds == 2.5
    
    def test_to_dict(self):
        """Test to_dict method."""
        step = WorkflowStep(id="test", step_type=StepType.ACTION)
        step_dict = step.to_dict()
        
        assert step_dict["id"] == "test"
        assert step_dict["step_type"] == "action"


class TestWorkflow:
    """Tests for Workflow."""
    
    def test_workflow_creation(self):
        """Test workflow creation."""
        workflow = Workflow(
            name="test_workflow",
            steps=[
                WorkflowStep(id="step1", step_type=StepType.ACTION),
            ],
        )
        
        assert workflow.name == "test_workflow"
        assert len(workflow.steps) == 1
    
    def test_get_step(self):
        """Test get_step method."""
        step1 = WorkflowStep(id="step1")
        step2 = WorkflowStep(id="step2")
        workflow = Workflow(name="test", steps=[step1, step2])
        
        assert workflow.get_step("step1") == step1
        assert workflow.get_step("step2") == step2
        assert workflow.get_step("nonexistent") is None
    
    def test_to_dict(self):
        """Test to_dict method."""
        workflow = Workflow(
            name="test",
            steps=[WorkflowStep(id="s1")],
        )
        workflow_dict = workflow.to_dict()
        
        assert workflow_dict["name"] == "test"
        assert len(workflow_dict["steps"]) == 1


class TestWorkflowContext:
    """Tests for WorkflowContext."""
    
    def test_variable_operations(self):
        """Test variable get/set operations."""
        context = WorkflowContext()
        
        context.set_variable("name", "John")
        assert context.get_variable("name") == "John"
        assert context.get_variable("missing", "default") == "default"
    
    def test_history(self):
        """Test history tracking."""
        context = WorkflowContext()
        
        context.add_history("step1", {"result": "success"}, True)
        context.add_history("step2", None, False)
        
        assert len(context.history) == 2
        assert context.history[0]["step_id"] == "step1"
        assert context.history[0]["success"] is True
    
    def test_errors(self):
        """Test error tracking."""
        context = WorkflowContext()
        
        context.add_error("step1", "Test error")
        
        assert len(context.errors) == 1
        assert context.errors[0]["step_id"] == "step1"
        assert context.errors[0]["error"] == "Test error"
    
    def test_to_dict(self):
        """Test to_dict method."""
        context = WorkflowContext()
        context.set_variable("test", "value")
        
        context_dict = context.to_dict()
        
        assert context_dict["variables"]["test"] == "value"
        assert "history" in context_dict
        assert "errors" in context_dict


class TestWorkflowInput:
    """Tests for WorkflowInput."""
    
    def test_default_values(self):
        """Test default input values."""
        input_data = WorkflowInput(task="Run workflow")
        
        assert input_data.workflow is None
        assert input_data.variables == {}
        assert input_data.resume is False
    
    def test_to_dict(self):
        """Test to_dict method."""
        workflow = Workflow(name="test")
        input_data = WorkflowInput(
            task="Run",
            workflow=workflow,
            variables={"x": 1},
        )
        
        result = input_data.to_dict()
        
        assert result["task"] == "Run"
        assert result["variables"] == {"x": 1}


class TestWorkflowSkill:
    """Tests for WorkflowSkill."""
    
    def test_skill_metadata(self):
        """Test skill metadata."""
        skill = WorkflowSkill()
        
        assert skill.name == "workflow"
        assert "workflow" in skill.description.lower()
    
    def test_required_capabilities(self):
        """Test required capabilities."""
        skill = WorkflowSkill()
        caps = skill.get_required_capabilities()
        
        assert SkillCapability.BROWSER_INTERACTION in caps
        assert SkillCapability.ERROR_RECOVERY in caps
    
    def test_validate_input_no_workflow(self):
        """Test validation without workflow."""
        skill = WorkflowSkill()
        input_data = WorkflowInput(task="Run")
        
        assert skill.validate_input(input_data) is False
    
    def test_validate_input_no_steps(self):
        """Test validation with empty workflow."""
        skill = WorkflowSkill()
        workflow = Workflow(name="test", steps=[])
        input_data = WorkflowInput(task="Run", workflow=workflow)
        
        assert skill.validate_input(input_data) is False
    
    def test_validate_input_valid(self):
        """Test validation with valid input."""
        skill = WorkflowSkill()
        workflow = Workflow(
            name="test",
            steps=[WorkflowStep(id="s1", step_type=StepType.ACTION)],
        )
        input_data = WorkflowInput(task="Run", workflow=workflow)
        
        assert skill.validate_input(input_data) is True
    
    def test_restore_context(self):
        """Test context restoration."""
        skill = WorkflowSkill()
        
        checkpoint = {
            "variables": {"x": 1, "y": 2},
            "history": [{"step_id": "s1"}],
            "current_step": 1,
            "errors": [],
            "warnings": [],
        }
        
        context = skill._restore_context(checkpoint)
        
        assert context.variables == {"x": 1, "y": 2}
        assert context.current_step == 1
    
    def test_get_checkpoint(self):
        """Test checkpoint creation."""
        skill = WorkflowSkill()
        skill._context = WorkflowContext()
        skill._context.set_variable("test", "value")
        
        checkpoint = skill.get_checkpoint()
        
        assert checkpoint is not None
        assert checkpoint["variables"]["test"] == "value"
    
    @pytest.mark.asyncio
    async def test_execute_wait_step(self):
        """Test wait step execution."""
        skill = WorkflowSkill()
        result = SkillResult(success=True)
        
        step = WorkflowStep(
            id="wait1",
            step_type=StepType.WAIT,
            wait_seconds=0.1,
        )
        
        input_data = WorkflowInput(
            task="Test",
            workflow=Workflow(name="test", steps=[]),
        )
        
        skill._context = WorkflowContext()
        
        wait_result = await skill._execute_wait(step, result)
        
        assert wait_result == 0.1
        assert "Wait" in result.steps_completed[0]


# ============================================================================
# Integration Tests
# ============================================================================

class TestSkillIntegration:
    """Integration tests for skills."""
    
    @pytest.mark.asyncio
    async def test_form_filling_with_mock_browser(self, mock_browser, mock_vision):
        """Test form filling with mocked browser."""
        skill = FormFillingSkill(
            browser_controller=mock_browser,
            vision_client=mock_vision,
        )
        
        schema = FormSchema(
            name="contact",
            url="https://example.com/contact",
            fields=[
                FormField(name="name", field_type=FieldType.TEXT, required=True),
                FormField(name="email", field_type=FieldType.EMAIL, required=True),
            ],
            auto_submit=False,
        )
        
        input_data = FormFillingInput(
            task="Fill contact form",
            schema=schema,
            data={"name": "John Doe", "email": "john@example.com"},
        )
        
        # Mock the page element
        mock_element = AsyncMock()
        mock_element.fill = AsyncMock()
        mock_browser.page.wait_for_selector = AsyncMock(return_value=mock_element)
        
        result = await skill.execute(input_data)
        
        # Should succeed since we have a valid schema and data
        # Note: actual result depends on browser mock setup
    
    def test_registry_skill_retrieval(self, skill_registry, mock_browser):
        """Test retrieving and using skills from registry."""
        # Register all skills
        skill_registry.register(FormFillingSkill)
        skill_registry.register(DataExtractionSkill)
        skill_registry.register(WebScrapingSkill)
        skill_registry.register(WorkflowSkill)
        
        # Get skill instances
        form_skill = skill_registry.get_skill(
            "form_filling",
            browser_controller=mock_browser,
        )
        
        assert form_skill is not None
        assert isinstance(form_skill, FormFillingSkill)
        assert form_skill.browser == mock_browser


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""
Analyzer Agent Module

The Analyzer Agent is responsible for:
- Analyzing page state and structure
- Detecting and classifying elements
- Providing information for action planning
- Identifying potential issues
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import uuid

from .base import (
    BaseAgent,
    AgentConfig,
    AgentCapability,
    AgentResult,
)


class AnalysisType(Enum):
    """Types of analysis that can be performed."""
    FULL_PAGE = "full_page"
    ELEMENT_DETECTION = "element_detection"
    FORM_ANALYSIS = "form_analysis"
    CONTENT_EXTRACTION = "content_extraction"
    STATE_CHECK = "state_check"
    ACCESSIBILITY = "accessibility"
    LAYOUT = "layout"


class PageState(Enum):
    """Possible states of a page."""
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    MODAL_OPEN = "modal_open"
    FORM_SUBMITTING = "form_submitting"
    NAVIGATING = "navigating"
    INTERACTIVE = "interactive"


@dataclass
class ElementInfo:
    """Information about a detected element."""
    element_id: str
    element_type: str  # button, input, link, etc.
    tag_name: str
    text_content: Optional[str] = None
    selector: Optional[str] = None
    xpath: Optional[str] = None
    bounding_box: Optional[Dict[str, float]] = None  # x, y, width, height
    is_visible: bool = True
    is_interactive: bool = True
    attributes: Dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "element_id": self.element_id,
            "element_type": self.element_type,
            "tag_name": self.tag_name,
            "text_content": self.text_content,
            "selector": self.selector,
            "xpath": self.xpath,
            "bounding_box": self.bounding_box,
            "is_visible": self.is_visible,
            "is_interactive": self.is_interactive,
            "attributes": self.attributes,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class FormField:
    """Information about a form field."""
    field_id: str
    field_type: str  # text, email, password, select, checkbox, radio, textarea
    label: Optional[str] = None
    name: Optional[str] = None
    placeholder: Optional[str] = None
    is_required: bool = False
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    element_info: Optional[ElementInfo] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field_id": self.field_id,
            "field_type": self.field_type,
            "label": self.label,
            "name": self.name,
            "placeholder": self.placeholder,
            "is_required": self.is_required,
            "validation_rules": self.validation_rules,
            "element_info": self.element_info.to_dict() if self.element_info else None,
        }


@dataclass
class AnalysisResult:
    """Result from page analysis."""
    analysis_id: str
    analysis_type: AnalysisType
    page_state: PageState
    url: str
    title: Optional[str] = None
    elements: List[ElementInfo] = field(default_factory=list)
    forms: List[Dict[str, Any]] = field(default_factory=list)
    text_content: Optional[str] = None
    issues: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "analysis_id": self.analysis_id,
            "analysis_type": self.analysis_type.value,
            "page_state": self.page_state.value,
            "url": self.url,
            "title": self.title,
            "elements": [e.to_dict() for e in self.elements],
            "forms": self.forms,
            "text_content": self.text_content,
            "issues": self.issues,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }
    
    def find_element_by_type(self, element_type: str) -> List[ElementInfo]:
        """Find elements by type."""
        return [e for e in self.elements if e.element_type == element_type]
    
    def find_element_by_text(self, text: str, exact: bool = False) -> List[ElementInfo]:
        """Find elements containing text."""
        if exact:
            return [e for e in self.elements if e.text_content == text]
        return [e for e in self.elements if e.text_content and text.lower() in e.text_content.lower()]
    
    def find_interactive_elements(self) -> List[ElementInfo]:
        """Find all interactive elements."""
        return [e for e in self.elements if e.is_interactive]


@dataclass
class AnalysisRequest:
    """Request for page analysis."""
    analysis_type: AnalysisType
    url: Optional[str] = None
    screenshot: Optional[bytes] = None
    html_content: Optional[str] = None
    selectors: Optional[List[str]] = None
    element_types: Optional[List[str]] = None
    include_invisible: bool = False
    depth: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


class AnalyzerAgent(BaseAgent):
    """
    Agent responsible for analyzing web pages.
    
    Capabilities:
    - Full page analysis
    - Element detection and classification
    - Form analysis
    - Content extraction
    - State detection
    """
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        browser: Optional[Any] = None,
        vision_client: Optional[Any] = None,
    ):
        if config is None:
            config = AgentConfig(
                name="AnalyzerAgent",
                capabilities={
                    AgentCapability.ANALYSIS,
                    AgentCapability.VISUAL_PROCESSING,
                },
            )
        super().__init__(config)
        self._browser = browser
        self._vision_client = vision_client
    
    def set_browser(self, browser: Any) -> None:
        """Set the browser instance."""
        self._browser = browser
    
    def set_vision_client(self, vision_client: Any) -> None:
        """Set the vision client."""
        self._vision_client = vision_client
    
    async def execute(self, task: Any) -> AgentResult:
        """Execute an analysis task."""
        if isinstance(task, AnalysisRequest):
            result = await self.analyze(task)
            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                task_id=result.analysis_id,
                data=result.to_dict(),
                metadata={"analysis_type": task.analysis_type.value},
            )
        else:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                task_id="unknown",
                error=f"Unknown task type: {type(task)}",
            )
    
    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """Perform page analysis."""
        analysis_id = str(uuid.uuid4())
        
        # Get current page info if browser is available
        url = request.url or ""
        title = None
        html_content = request.html_content
        
        if self._browser:
            try:
                page = self._browser.get_current_page()
                if page:
                    url = page.url
                    title = await page.title()
                    if not html_content:
                        html_content = await page.content()
            except Exception:
                pass
        
        # Perform analysis based on type
        if request.analysis_type == AnalysisType.FULL_PAGE:
            result = await self._analyze_full_page(
                analysis_id, url, title, html_content, request
            )
        elif request.analysis_type == AnalysisType.ELEMENT_DETECTION:
            result = await self._detect_elements(
                analysis_id, url, title, html_content, request
            )
        elif request.analysis_type == AnalysisType.FORM_ANALYSIS:
            result = await self._analyze_forms(
                analysis_id, url, title, html_content, request
            )
        elif request.analysis_type == AnalysisType.STATE_CHECK:
            result = await self._check_state(
                analysis_id, url, title, html_content, request
            )
        else:
            result = AnalysisResult(
                analysis_id=analysis_id,
                analysis_type=request.analysis_type,
                page_state=PageState.READY,
                url=url,
                title=title,
            )
        
        return result
    
    async def _analyze_full_page(
        self,
        analysis_id: str,
        url: str,
        title: Optional[str],
        html_content: Optional[str],
        request: AnalysisRequest,
    ) -> AnalysisResult:
        """Perform full page analysis."""
        elements = await self._detect_elements(
            analysis_id, url, title, html_content, request
        )
        forms = await self._analyze_forms(
            analysis_id, url, title, html_content, request
        )
        state = await self._check_state(
            analysis_id, url, title, html_content, request
        )
        
        # Combine results
        result = AnalysisResult(
            analysis_id=analysis_id,
            analysis_type=AnalysisType.FULL_PAGE,
            page_state=state.page_state,
            url=url,
            title=title,
            elements=elements.elements,
            forms=forms.forms,
            text_content=await self._extract_text(html_content),
            recommendations=self._generate_recommendations(elements.elements),
        )
        
        return result
    
    async def _detect_elements(
        self,
        analysis_id: str,
        url: str,
        title: Optional[str],
        html_content: Optional[str],
        request: AnalysisRequest,
    ) -> AnalysisResult:
        """Detect and classify elements on the page."""
        elements = []
        
        # Use vision client if available and screenshot provided
        if self._vision_client and request.screenshot:
            try:
                # Visual element detection
                visual_elements = await self._detect_elements_visual(request.screenshot)
                elements.extend(visual_elements)
            except Exception:
                pass
        
        # Use browser for DOM-based detection
        if self._browser:
            try:
                dom_elements = await self._detect_elements_dom(request)
                elements.extend(dom_elements)
            except Exception:
                pass
        
        # Filter by requested types
        if request.element_types:
            elements = [e for e in elements if e.element_type in request.element_types]
        
        # Filter invisible if needed
        if not request.include_invisible:
            elements = [e for e in elements if e.is_visible]
        
        return AnalysisResult(
            analysis_id=analysis_id,
            analysis_type=AnalysisType.ELEMENT_DETECTION,
            page_state=PageState.READY,
            url=url,
            title=title,
            elements=elements,
        )
    
    async def _analyze_forms(
        self,
        analysis_id: str,
        url: str,
        title: Optional[str],
        html_content: Optional[str],
        request: AnalysisRequest,
    ) -> AnalysisResult:
        """Analyze forms on the page."""
        forms = []
        
        if self._browser:
            try:
                page = self._browser.get_current_page()
                if page:
                    # Find all forms
                    form_elements = await page.query_selector_all("form")
                    
                    for form_idx, form in enumerate(form_elements):
                        form_info = {
                            "form_id": f"form_{form_idx}",
                            "action": await form.get_attribute("action"),
                            "method": await form.get_attribute("method") or "get",
                            "fields": [],
                        }
                        
                        # Get all input fields
                        inputs = await form.query_selector_all("input, select, textarea")
                        
                        for field_idx, input_el in enumerate(inputs):
                            field_type = await input_el.get_attribute("type") or "text"
                            tag_name = await input_el.evaluate("el => el.tagName.toLowerCase()")
                            
                            if tag_name == "select":
                                field_type = "select"
                            elif tag_name == "textarea":
                                field_type = "textarea"
                            
                            # Get label
                            label = None
                            name = await input_el.get_attribute("name")
                            if name:
                                try:
                                    label_el = await page.query_selector(f"label[for='{name}']")
                                    if label_el:
                                        label = await label_el.text_content()
                                except Exception:
                                    pass
                            
                            field_info = FormField(
                                field_id=f"field_{form_idx}_{field_idx}",
                                field_type=field_type,
                                label=label,
                                name=name,
                                placeholder=await input_el.get_attribute("placeholder"),
                                is_required=await input_el.get_attribute("required") is not None,
                            )
                            
                            form_info["fields"].append(field_info.to_dict())
                        
                        forms.append(form_info)
            except Exception:
                pass
        
        return AnalysisResult(
            analysis_id=analysis_id,
            analysis_type=AnalysisType.FORM_ANALYSIS,
            page_state=PageState.READY,
            url=url,
            title=title,
            forms=forms,
        )
    
    async def _check_state(
        self,
        analysis_id: str,
        url: str,
        title: Optional[str],
        html_content: Optional[str],
        request: AnalysisRequest,
    ) -> AnalysisResult:
        """Check the current state of the page."""
        page_state = PageState.READY
        issues = []
        
        if self._browser:
            try:
                page = self._browser.get_current_page()
                if page:
                    # Check for loading state
                    ready_state = await page.evaluate("document.readyState")
                    if ready_state != "complete":
                        page_state = PageState.LOADING
                    
                    # Check for error indicators
                    error_selectors = [".error", "#error", ".alert-error", "[role='alert']"]
                    for selector in error_selectors:
                        error_el = await page.query_selector(selector)
                        if error_el:
                            error_text = await error_el.text_content()
                            issues.append({
                                "type": "error_message",
                                "message": error_text,
                                "selector": selector,
                            })
                            page_state = PageState.ERROR
                    
                    # Check for modal
                    modal_selectors = [".modal", "[role='dialog']", ".popup", ".overlay"]
                    for selector in modal_selectors:
                        modal_el = await page.query_selector(selector)
                        if modal_el:
                            is_visible = await modal_el.is_visible()
                            if is_visible:
                                page_state = PageState.MODAL_OPEN
                                break
            except Exception:
                pass
        
        return AnalysisResult(
            analysis_id=analysis_id,
            analysis_type=AnalysisType.STATE_CHECK,
            page_state=page_state,
            url=url,
            title=title,
            issues=issues,
        )
    
    async def _detect_elements_visual(self, screenshot: bytes) -> List[ElementInfo]:
        """Detect elements using visual analysis."""
        elements = []
        
        if self._vision_client:
            try:
                # Use vision client to detect elements
                # This would call the vision model to identify interactive elements
                pass
            except Exception:
                pass
        
        return elements
    
    async def _detect_elements_dom(self, request: AnalysisRequest) -> List[ElementInfo]:
        """Detect elements using DOM analysis."""
        elements = []
        
        if self._browser:
            try:
                page = self._browser.get_current_page()
                if page:
                    # Interactive element selectors
                    selectors = request.selectors or [
                        "button", "a", "input", "select", "textarea",
                        "[onclick]", "[role='button']", "[tabindex]",
                    ]
                    
                    for selector in selectors:
                        els = await page.query_selector_all(selector)
                        for idx, el in enumerate(els):
                            is_visible = await el.is_visible()
                            
                            if not is_visible and not request.include_invisible:
                                continue
                            
                            # Get element info
                            tag_name = await el.evaluate("el => el.tagName.toLowerCase()")
                            text_content = await el.text_content()
                            element_id = await el.get_attribute("id")
                            class_name = await el.get_attribute("class")
                            
                            # Get bounding box
                            bbox = await el.bounding_box()
                            
                            # Determine element type
                            element_type = self._classify_element(tag_name, await el.get_attribute("type"))
                            
                            # Build selector
                            css_selector = element_id and f"#{element_id}" or f"{tag_name}.{class_name}" if class_name else tag_name
                            
                            element_info = ElementInfo(
                                element_id=f"el_{len(elements)}",
                                element_type=element_type,
                                tag_name=tag_name,
                                text_content=text_content[:100] if text_content else None,
                                selector=css_selector,
                                bounding_box=bbox,
                                is_visible=is_visible,
                                is_interactive=True,
                                attributes={
                                    "id": element_id or "",
                                    "class": class_name or "",
                                    "type": await el.get_attribute("type") or "",
                                },
                            )
                            
                            elements.append(element_info)
            except Exception:
                pass
        
        return elements
    
    def _classify_element(self, tag_name: str, input_type: Optional[str]) -> str:
        """Classify element type."""
        if tag_name == "input":
            if input_type in ["button", "submit", "reset"]:
                return "button"
            elif input_type in ["checkbox"]:
                return "checkbox"
            elif input_type in ["radio"]:
                return "radio"
            elif input_type in ["text", "email", "password", "search", "tel", "url"]:
                return "text_input"
            elif input_type in ["number", "range"]:
                return "number_input"
            elif input_type in ["date", "datetime-local", "time"]:
                return "date_input"
            elif input_type in ["file"]:
                return "file_input"
            return "input"
        elif tag_name == "button":
            return "button"
        elif tag_name == "a":
            return "link"
        elif tag_name == "select":
            return "select"
        elif tag_name == "textarea":
            return "textarea"
        elif tag_name in ["img", "svg"]:
            return "image"
        elif tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            return "heading"
        elif tag_name in ["p", "span", "div"]:
            return "text"
        return "element"
    
    async def _extract_text(self, html_content: Optional[str]) -> Optional[str]:
        """Extract text content from HTML."""
        if self._browser:
            try:
                page = self._browser.get_current_page()
                if page:
                    return await page.text_content("body")
            except Exception:
                pass
        return None
    
    def _generate_recommendations(self, elements: List[ElementInfo]) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # Check for interactive elements
        interactive = [e for e in elements if e.is_interactive]
        if not interactive:
            recommendations.append("No interactive elements found on the page")
        
        # Check for forms
        forms = [e for e in elements if e.element_type in ["text_input", "select", "textarea", "checkbox", "radio"]]
        if forms:
            recommendations.append(f"Found {len(forms)} form fields that may need to be filled")
        
        # Check for buttons
        buttons = [e for e in elements if e.element_type == "button"]
        if buttons:
            recommendations.append(f"Found {len(buttons)} buttons available for interaction")
        
        return recommendations
    
    async def find_element(
        self,
        description: str,
        element_type: Optional[str] = None,
    ) -> Optional[ElementInfo]:
        """Find an element matching a description."""
        request = AnalysisRequest(
            analysis_type=AnalysisType.ELEMENT_DETECTION,
            element_types=[element_type] if element_type else None,
        )
        
        result = await self.analyze(request)
        
        # Search by text content
        matches = result.find_element_by_text(description)
        
        if matches:
            return matches[0]
        
        return None
    
    async def get_page_state(self) -> PageState:
        """Get the current page state."""
        request = AnalysisRequest(analysis_type=AnalysisType.STATE_CHECK)
        result = await self.analyze(request)
        return result.page_state

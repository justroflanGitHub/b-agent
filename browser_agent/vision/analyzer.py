"""
Visual Analyzer - Advanced screenshot analysis for browser automation.

Provides:
- Bounding box extraction for elements
- Element type classification
- Multi-element detection
- Page state determination
- Element visibility/interactivity assessment
"""

import asyncio
import base64
import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

from ..llm.client import VisionClient

logger = logging.getLogger(__name__)


class PageState(Enum):
    """Page state classification."""
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    MODAL = "modal"
    LOGIN_REQUIRED = "login_required"
    CAPTCHA = "captcha"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    REDIRECTING = "redirecting"


class ElementType(Enum):
    """Element type classification."""
    BUTTON = "button"
    LINK = "link"
    INPUT_TEXT = "input_text"
    INPUT_PASSWORD = "input_password"
    INPUT_EMAIL = "input_email"
    INPUT_SEARCH = "input_search"
    TEXTAREA = "textarea"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    IMAGE = "image"
    ICON = "icon"
    TEXT = "text"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    FORM = "form"
    NAVIGATION = "navigation"
    FOOTER = "footer"
    HEADER = "header"
    SIDEBAR = "sidebar"
    MODAL = "modal"
    POPUP = "popup"
    ADVERTISEMENT = "advertisement"
    VIDEO = "video"
    IFRAME = "iframe"
    UNKNOWN = "unknown"


@dataclass
class BoundingBox:
    """Bounding box for an element."""
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0
    
    @property
    def center(self) -> Tuple[int, int]:
        """Get center coordinates."""
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    @property
    def area(self) -> int:
        """Get bounding box area."""
        return self.width * self.height
    
    def contains(self, x: int, y: int) -> bool:
        """Check if point is inside bounding box."""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)
    
    def overlaps(self, other: "BoundingBox") -> bool:
        """Check if two bounding boxes overlap."""
        return (self.x < other.x + other.width and
                self.x + self.width > other.x and
                self.y < other.y + other.height and
                self.y + self.height > other.y)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": self.confidence,
            "center": self.center
        }


@dataclass
class ElementInfo:
    """Information about a detected element."""
    bounding_box: BoundingBox
    element_type: ElementType
    description: str
    text_content: Optional[str] = None
    is_visible: bool = True
    is_interactive: bool = False
    is_clickable: bool = False
    is_typeable: bool = False
    attributes: Dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bounding_box": self.bounding_box.to_dict(),
            "element_type": self.element_type.value,
            "description": self.description,
            "text_content": self.text_content,
            "is_visible": self.is_visible,
            "is_interactive": self.is_interactive,
            "is_clickable": self.is_clickable,
            "is_typeable": self.is_typeable,
            "attributes": self.attributes,
            "confidence": self.confidence
        }


@dataclass
class PageAnalysis:
    """Complete page analysis result."""
    state: PageState
    elements: List[ElementInfo]
    summary: str
    recommended_actions: List[str]
    loading_percentage: Optional[int] = None
    error_message: Optional[str] = None
    modal_content: Optional[str] = None
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "state": self.state.value,
            "elements": [e.to_dict() for e in self.elements],
            "summary": self.summary,
            "recommended_actions": self.recommended_actions,
            "loading_percentage": self.loading_percentage,
            "error_message": self.error_message,
            "modal_content": self.modal_content,
            "confidence": self.confidence
        }


class VisualAnalyzer:
    """
    Advanced visual analyzer for browser automation.
    
    Uses vision model to:
    - Extract bounding boxes for elements
    - Classify element types
    - Detect multiple elements in single query
    - Determine page state
    - Assess element visibility and interactivity
    """
    
    def __init__(self, vision_client: VisionClient, cache_enabled: bool = True):
        """
        Initialize visual analyzer.
        
        Args:
            vision_client: Vision client for screenshot analysis
            cache_enabled: Whether to cache analysis results
        """
        self.vision_client = vision_client
        self.cache_enabled = cache_enabled
        self._cache: Dict[str, PageAnalysis] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def _get_screenshot_hash(self, screenshot: bytes) -> str:
        """Get hash of screenshot for caching."""
        return hashlib.md5(screenshot).hexdigest()
    
    async def analyze_page(
        self,
        screenshot: bytes,
        task_context: Optional[str] = None,
        use_cache: bool = True
    ) -> PageAnalysis:
        """
        Perform complete page analysis.
        
        Args:
            screenshot: PNG screenshot bytes
            task_context: Optional task context for better analysis
            use_cache: Whether to use cached results
            
        Returns:
            PageAnalysis with state, elements, and recommendations
        """
        # Check cache
        if use_cache and self.cache_enabled:
            cache_key = self._get_screenshot_hash(screenshot)
            if cache_key in self._cache:
                self._cache_hits += 1
                logger.debug(f"Cache hit for page analysis")
                return self._cache[cache_key]
            self._cache_misses += 1
        
        # Analyze page state
        state_result = await self._analyze_page_state(screenshot)
        
        # Detect elements
        elements = await self._detect_elements(screenshot, task_context)
        
        # Generate summary and recommendations
        summary = await self._generate_summary(screenshot, state_result, elements)
        recommendations = self._generate_recommendations(state_result, elements, task_context)
        
        analysis = PageAnalysis(
            state=state_result["state"],
            elements=elements,
            summary=summary,
            recommended_actions=recommendations,
            loading_percentage=state_result.get("loading_percentage"),
            error_message=state_result.get("error_message"),
            modal_content=state_result.get("modal_content"),
            confidence=state_result.get("confidence", 1.0)
        )
        
        # Cache result
        if self.cache_enabled:
            cache_key = self._get_screenshot_hash(screenshot)
            self._cache[cache_key] = analysis
        
        return analysis
    
    async def _analyze_page_state(self, screenshot: bytes) -> Dict[str, Any]:
        """Analyze page state from screenshot."""
        prompt = """Analyze this webpage screenshot and determine its state.

Return JSON:
{
    "state": "loading|ready|error|modal|login_required|captcha|rate_limited|not_found|redirecting",
    "loading_percentage": <int 0-100 if loading, else null>,
    "error_message": "<error text if error state, else null>",
    "modal_content": "<modal text if modal present, else null>",
    "confidence": <float 0.0-1.0>
}

State definitions:
- loading: Page is still loading (spinner, skeleton, partial content)
- ready: Page is fully loaded and interactive
- error: Error page or error message visible
- modal: Modal dialog or popup overlay present
- login_required: Login form or authentication required
- captcha: CAPTCHA challenge visible
- rate_limited: Rate limit or blocking message
- not_found: 404 or similar not found page
- redirecting: Redirect notice or automatic redirect in progress
"""
        
        response = await self.vision_client.chat_with_image(prompt, screenshot)
        
        try:
            content = response.content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(content[json_start:json_end])
                result["state"] = PageState(result.get("state", "ready"))
                return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse page state: {e}")
        
        return {"state": PageState.READY, "confidence": 0.5}
    
    async def _detect_elements(
        self,
        screenshot: bytes,
        task_context: Optional[str] = None
    ) -> List[ElementInfo]:
        """Detect interactive elements in screenshot."""
        context_hint = f"\nTask context: {task_context}" if task_context else ""
        
        prompt = f"""Detect all interactive and important elements in this webpage screenshot.
{context_hint}

For each element, return JSON:
{{
    "elements": [
        {{
            "bbox": {{"x": int, "y": int, "width": int, "height": int}},
            "type": "button|link|input_text|input_password|input_email|input_search|textarea|select|checkbox|radio|image|icon|text|heading|modal|popup",
            "description": "Brief description of the element",
            "text_content": "Visible text on/inside the element",
            "is_visible": true/false,
            "is_interactive": true/false,
            "is_clickable": true/false,
            "is_typeable": true/false,
            "confidence": 0.0-1.0
        }}
    ]
}}

Focus on:
1. Interactive elements (buttons, links, inputs)
2. Important text content (headings, labels)
3. Modal/popup overlays
4. Navigation elements

Screenshot dimensions: 1920x1080
Return up to 20 most important elements.
"""
        
        response = await self.vision_client.chat_with_image(prompt, screenshot)
        
        elements = []
        try:
            content = response.content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(content[json_start:json_end])
                
                for elem_data in data.get("elements", []):
                    try:
                        bbox_data = elem_data.get("bbox", {})
                        bbox = BoundingBox(
                            x=bbox_data.get("x", 0),
                            y=bbox_data.get("y", 0),
                            width=bbox_data.get("width", 0),
                            height=bbox_data.get("height", 0),
                            confidence=elem_data.get("confidence", 1.0)
                        )
                        
                        element_type_str = elem_data.get("type", "unknown").upper()
                        try:
                            element_type = ElementType[element_type_str]
                        except KeyError:
                            element_type = ElementType.UNKNOWN
                        
                        element = ElementInfo(
                            bounding_box=bbox,
                            element_type=element_type,
                            description=elem_data.get("description", ""),
                            text_content=elem_data.get("text_content"),
                            is_visible=elem_data.get("is_visible", True),
                            is_interactive=elem_data.get("is_interactive", False),
                            is_clickable=elem_data.get("is_clickable", False),
                            is_typeable=elem_data.get("is_typeable", False),
                            confidence=elem_data.get("confidence", 1.0)
                        )
                        elements.append(element)
                    except Exception as e:
                        logger.warning(f"Failed to parse element: {e}")
                        continue
                        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse element detection response: {e}")
        
        logger.info(f"Detected {len(elements)} elements")
        return elements
    
    async def _generate_summary(
        self,
        screenshot: bytes,
        state_result: Dict[str, Any],
        elements: List[ElementInfo]
    ) -> str:
        """Generate page summary."""
        # Build element summary
        element_counts: Dict[ElementType, int] = {}
        for elem in elements:
            element_counts[elem.element_type] = element_counts.get(elem.element_type, 0) + 1
        
        element_summary = ", ".join(
            f"{count} {et.value}" for et, count in element_counts.items()
        )
        
        prompt = f"""Summarize this webpage in 1-2 sentences.

Page state: {state_result.get("state", "unknown").value if isinstance(state_result.get("state"), PageState) else state_result.get("state", "unknown")}
Detected elements: {element_summary}

Return JSON:
{{"summary": "Brief description of the page content and purpose"}}
"""
        
        response = await self.vision_client.chat_with_image(prompt, screenshot)
        
        try:
            content = response.content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(content[json_start:json_end])
                return result.get("summary", "Unable to generate summary")
        except json.JSONDecodeError:
            pass
        
        return f"Page in {state_result.get('state', 'unknown')} state with {len(elements)} detected elements"
    
    def _generate_recommendations(
        self,
        state_result: Dict[str, Any],
        elements: List[ElementInfo],
        task_context: Optional[str] = None
    ) -> List[str]:
        """Generate recommended actions based on page state and elements."""
        recommendations = []
        state = state_result.get("state", PageState.READY)
        
        if state == PageState.LOADING:
            recommendations.append("Wait for page to finish loading")
        elif state == PageState.ERROR:
            recommendations.append("Handle error: " + (state_result.get("error_message") or "Unknown error"))
        elif state == PageState.MODAL:
            recommendations.append("Handle modal/popup before proceeding")
        elif state == PageState.LOGIN_REQUIRED:
            recommendations.append("Authentication required - provide credentials")
        elif state == PageState.CAPTCHA:
            recommendations.append("CAPTCHA detected - manual intervention may be needed")
        elif state == PageState.RATE_LIMITED:
            recommendations.append("Rate limited - wait before retrying")
        elif state == PageState.READY:
            # Find clickable elements
            clickable = [e for e in elements if e.is_clickable]
            typeable = [e for e in elements if e.is_typeable]
            
            if task_context:
                recommendations.append(f"Proceed with task: {task_context}")
            
            if typeable:
                recommendations.append(f"Found {len(typeable)} input fields for text entry")
            if clickable:
                recommendations.append(f"Found {len(clickable)} clickable elements")
        
        return recommendations
    
    async def find_element(
        self,
        screenshot: bytes,
        description: str,
        element_type: Optional[ElementType] = None
    ) -> Optional[ElementInfo]:
        """
        Find a specific element by description.
        
        Args:
            screenshot: PNG screenshot bytes
            description: Element description to find
            element_type: Optional expected element type
            
        Returns:
            ElementInfo if found, None otherwise
        """
        type_hint = f"\nExpected element type: {element_type.value}" if element_type else ""
        
        prompt = f"""Find this specific element in the webpage screenshot: "{description}"
{type_hint}

Return JSON:
{{
    "found": true/false,
    "bbox": {{"x": int, "y": int, "width": int, "height": int}},
    "type": "element type",
    "description": "what you found",
    "text_content": "visible text",
    "is_visible": true/false,
    "is_interactive": true/false,
    "is_clickable": true/false,
    "is_typeable": true/false,
    "confidence": 0.0-1.0
}}

If element not found, return {{"found": false}}

Screenshot dimensions: 1920x1080
"""
        
        response = await self.vision_client.chat_with_image(prompt, screenshot)
        
        try:
            content = response.content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(content[json_start:json_end])
                
                if not result.get("found", False):
                    return None
                
                bbox_data = result.get("bbox", {})
                bbox = BoundingBox(
                    x=bbox_data.get("x", 0),
                    y=bbox_data.get("y", 0),
                    width=bbox_data.get("width", 0),
                    height=bbox_data.get("height", 0),
                    confidence=result.get("confidence", 1.0)
                )
                
                element_type_str = result.get("type", "unknown").upper()
                try:
                    found_type = ElementType[element_type_str]
                except KeyError:
                    found_type = ElementType.UNKNOWN
                
                return ElementInfo(
                    bounding_box=bbox,
                    element_type=found_type,
                    description=result.get("description", description),
                    text_content=result.get("text_content"),
                    is_visible=result.get("is_visible", True),
                    is_interactive=result.get("is_interactive", False),
                    is_clickable=result.get("is_clickable", False),
                    is_typeable=result.get("is_typeable", False),
                    confidence=result.get("confidence", 1.0)
                )
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse find element response: {e}")
        
        return None
    
    async def find_all_elements(
        self,
        screenshot: bytes,
        description: str,
        max_results: int = 10
    ) -> List[ElementInfo]:
        """
        Find all elements matching a description.
        
        Args:
            screenshot: PNG screenshot bytes
            description: Element description to find
            max_results: Maximum number of results
            
        Returns:
            List of matching ElementInfo objects
        """
        prompt = f"""Find all elements matching this description: "{description}"

Return JSON:
{{
    "elements": [
        {{
            "bbox": {{"x": int, "y": int, "width": int, "height": int}},
            "type": "element type",
            "description": "what you found",
            "text_content": "visible text",
            "is_visible": true/false,
            "is_interactive": true/false,
            "is_clickable": true/false,
            "is_typeable": true/false,
            "confidence": 0.0-1.0
        }}
    ]
}}

Return up to {max_results} best matches.
Screenshot dimensions: 1920x1080
"""
        
        response = await self.vision_client.chat_with_image(prompt, screenshot)
        
        elements = []
        try:
            content = response.content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(content[json_start:json_end])
                
                for elem_data in data.get("elements", [])[:max_results]:
                    try:
                        bbox_data = elem_data.get("bbox", {})
                        bbox = BoundingBox(
                            x=bbox_data.get("x", 0),
                            y=bbox_data.get("y", 0),
                            width=bbox_data.get("width", 0),
                            height=bbox_data.get("height", 0),
                            confidence=elem_data.get("confidence", 1.0)
                        )
                        
                        element_type_str = elem_data.get("type", "unknown").upper()
                        try:
                            element_type = ElementType[element_type_str]
                        except KeyError:
                            element_type = ElementType.UNKNOWN
                        
                        element = ElementInfo(
                            bounding_box=bbox,
                            element_type=element_type,
                            description=elem_data.get("description", ""),
                            text_content=elem_data.get("text_content"),
                            is_visible=elem_data.get("is_visible", True),
                            is_interactive=elem_data.get("is_interactive", False),
                            is_clickable=elem_data.get("is_clickable", False),
                            is_typeable=elem_data.get("is_typeable", False),
                            confidence=elem_data.get("confidence", 1.0)
                        )
                        elements.append(element)
                    except Exception as e:
                        logger.warning(f"Failed to parse element: {e}")
                        continue
                        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse find all elements response: {e}")
        
        logger.info(f"Found {len(elements)} elements matching '{description}'")
        return elements
    
    def clear_cache(self):
        """Clear the analysis cache."""
        self._cache.clear()
        logger.info("Visual analyzer cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0
        }

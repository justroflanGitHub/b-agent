Received. I'm starting to work on a detailed plan and ideas for your advanced browser use agent, including its capabilities, sub-agents, and fallback mechanisms.

I'll help you create an advanced browser use agent. Let me first check any existing context and then invoke the ai-agents-architect skill to get expert guidance on this complex project.


# Advanced Browser Use Agent Architecture Plan

Based on the AI Agents Architect principles, I've designed a comprehensive architecture for your browser use agent. Let me present the plan:

<genui-step-collapse title="🖥️ Advanced Browser Use Agent - Architecture Plan">
<genui-step-collapse-item label="1. Core Architecture Overview" key="step1">
<genui-li-item>Multi-agent orchestration with Supervisor pattern for task coordination</genui-li-item>
<genui-li-item>UI_TARS 1.5 as UI grounding model for visual understanding and action prediction</genui-li-item>
<genui-li-item>Modular sub-agent system: Planner, Analyzer, Actor, Validator</genui-li-item>
<genui-li-item>State machine with checkpointing for fallback/recovery mechanism</genui-li-item>
<genui-li-item>Tool registry for dynamic action capabilities</genui-li-item>
</genui-step-collapse-item>
<genui-step-collapse-item label="2. Sub-Agent Specifications" key="step2">
<genui-li-item>Flexible Planner - decomposes tasks into executable steps with dependency tracking</genui-li-item>
<genui-li-item>Screenshot Analyzer - uses UI_TARS for element detection and state assessment</genui-li-item>
<genui-li-item>Actor - executes low-level browser actions with retry logic</genui-li-item>
<genui-li-item>Validator - verifies action success against expected outcomes</genui-li-item>
</genui-step-collapse-item>
<genui-step-collapse-item label="3. Actor Action Set (Expanded)" key="step3">
<genui-li-item>Navigation: go_to_url, back, forward, refresh, navigate_to</genui-li-item>
<genui-li-item>Interaction: click, double_click, right_click, hover, drag_and_drop</genui-li-item>
<genui-li-item>Input: type_text, select_dropdown, check_box, radio_button, toggle</genui-li-item>
<genui-li-item>Scroll: scroll_up, scroll_down, scroll_to_element, scroll_to_position</genui-li-item>
<genui-li-item>Content: extract_text, extract_table, extract_image, get_page_info</genui-li-item>
<genui-li-item>Advanced: wait_for_element, wait_for_navigation, switch_frame, handle_popup</genui-li-item>
</genui-step-collapse-item>
<genui-step-collapse-item label="4. Fallback & Recovery System" key="step4">
<genui-li-item>Checkpoint snapshots before each major action sequence</genui-li-item>
<genui-li-item>State stack for rollback to previous successful states</genui-li-item>
<genui-li-item>Alternative strategy generator when primary path fails</genui-li-item>
<genui-li-item>Max retry limits with exponential backoff</genui-li-item>
<genui-li-item>Graceful degradation to manual intervention option</genui-li-item>
</genui-step-collapse-item>
<genui-step-collapse-item label="5. Skill System" key="step5">
<genui-li-item>Forms Filling - multi-field form completion with validation</genui-li-item>
<genui-li-item>Data Extraction - structured extraction from dynamic pages</genui-li-item>
<genui-li-item>Scraping Pipeline - multi-page navigation and data aggregation</genui-li-item>
<genui-li-item>Workflow Automation - chained operations with conditional logic</genui-li-item>
</genui-step-collapse-item>
<genui-step-collapse-item label="6. LLM Integration (LM Studio)" key="step6">
<genui-li-item>Local inference server connection via OpenAI-compatible API</genui-li-item>
<genui-li-item>Streaming responses for real-time feedback</genui-li-item>
<genui-li-item>Caching layer for repeated visual understanding calls</genui-li-item>
<genui-li-item>Temperature/top-p config for deterministic vs creative reasoning</genui-li-item>
</genui-step-collapse-item>
</genui-step-collapse>

**Goal:** Build a production-ready browser automation agent with human-level UI interaction capabilities, powered by local LLM with visual grounding.

**Deliverable:** Complete Python codebase with architecture documentation and usage examples.

---

## 🔬 Detailed Architecture Design

### High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACE                                 │
│                    (CLI / Web UI / API Endpoint)                        │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      SUPERVISOR ORCHESTRATOR                            │
│         (Task Decomposition → Agent Dispatch → Result Synthesis)        │
└─────────┬─────────────┬─────────────┬─────────────┬─────────────────────┘
          │             │             │             │
          ▼             ▼             ▼             ▼
┌─────────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐
│ FLEXIBLE        │ │SCREENSHOT│ │  ACTOR   │ │    VALIDATOR     │
│ PLANNER         │ │ ANALYZER │ │          │ │                  │
│                 │ │ (UI_TARS)│ │          │ │                  │
│ - Task breakdown│ │          │ │  Actions │ │ - Pre-conditions │
│ - Dependency    │ │ - Element │ │ - Retry  │ │ - Post-checks    │
│   analysis      │ │   detect  │ │ - Rollback│ │ - State verify   │
│ - Strategy gen  │ │ - State   │ │          │ │                  │
│                 │ │   assess  │ │          │ │                  │
└─────────────────┘ └──────────┘ └──────────┘ └──────────────────┘
          │             │             │             │
          └─────────────┴─────────────┴─────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         BROWSER CONTROLLER                              │
│                    (Playwright / Puppeteer / CDP)                      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 💡 Enhanced Ideas & Suggestions

### 1. **Visual Memory System**
- Cache screenshot embeddings for similar UI states
- Use for faster re-identification of dynamic elements
- Enable "learned" navigation patterns for repeat tasks
- Configuration management

### 2. **Multi-Tab Manager**
- Parallel tab operations for independent tasks
- Tab state tracking and synchronization
- Cross-tab data passing mechanisms
- Selector health monitoring
- Visual diff for validation (compare before/after screenshots pixel-wise)

### 3. **Intelligent Element Matching**
- Fuzzy matching for dynamic IDs (e.g., `id_abc123`)
- Multi-attribute fallback (text + position + class)
- Accessibility tree integration for semantic understanding
- Human-in-the-loop hooks for uncertainty

### 4. **Proactive Error Prevention**
- Anomaly detection in page behavior
- Heuristic-based warning system
- Automatic screenshot on suspicious states

### 5. **Conversation Memory**
- Remember user preferences across sessions
- Learn from correction feedback
- Build task templates from demonstrations

### 6. **Resource Management**
- Intelligent page loading (lazy vs eager)
- Memory-efficient screenshot handling
- Connection pooling for multiple agent instances

---

## 📋 Implementation Roadmap

### Phase 1: Core Foundation
1. Browser controller with Playwright
2. Basic actor actions (click, type, scroll)
3. Simple planner with sequential execution
4. LM Studio integration

### Phase 2: Visual Intelligence
1. UI_TARS screenshot analyzer integration
2. Element detection and localization
3. State-based action targeting
4. Validator with visual diff

### Phase 3: Resilience & Recovery
1. Checkpoint system implementation
2. Fallback strategy generator
3. State stack for rollback
4. Error classification and handling

### Phase 4: Advanced Capabilities
1. Skill system (forms, extraction, scraping)
2. Multi-agent coordination
3. Learning and adaptation
4. Web UI and API exposure

---

## 🎯 Next Steps

Would you like me to proceed with implementation? I can:

1. **Start with Phase 1** - Build the core foundation with browser controller and basic actions
2. **Create the full architecture** - Implement all components in a modular structure
3. **Focus on specific component** - Start with the Actor or Planner based on your priorities

Please confirm which approach you'd prefer, and I'll begin building the browser use agent with all the components we've discussed.

好的，我已收到您的请求，并正在为您准备关于ai-agents-architect的功能介绍、使用方法、高级浏览器代理的构建计划以及相关创意。

# Advanced Browser Use Agent - Complete Implementation Roadmap

## 🔧 Technological Stack

### Core Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Browser Automation** | Playwright (Python) | Cross-browser control, CDP access |
| **UI Grounding Model** | UI-TARS 1.5 | Visual element detection, state analysis |
| **LLM Backend** | LM Studio + Ollama | Local inference, OpenAI-compatible API |
| **Agent Framework** | LangChain / Custom | Orchestration, tool calling |
| **State Management** | Redis / SQLite | Checkpointing, session persistence |
| **API Framework** | FastAPI | HTTP endpoints, streaming responses |
| **Task Queue** | Celery / In-memory | Async task processing |
| **Logging** | Structured Logging + Weights & Biases | Observability, debugging |

### Python Dependencies

```python
# requirements.txt
playwright>=1.40.0
langchain>=0.1.0
langchain-openai>=0.0.5
openai>=1.0.0
pydantic>=2.0.0
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
structlog>=24.0.0
tenacity>=8.2.0
pillow>=10.0.0
numpy>=1.24.0
httpx>=0.26.0
```

---

## 📋 Detailed Implementation Phases

### Phase 1: Core Foundation (Week 1-2)

**Objective:** Build the basic browser automation infrastructure with LM Studio integration.

#### 1.1 Browser Controller Layer

```
browser_controller/
├── __init__.py
├── base.py              # Abstract browser interface
├── playwright_controller.py  # Playwright implementation
├── page.py             # Page abstraction
├── frame.py            # iFrame handling
├── popup.py            # Popup/dialog management
└── exceptions.py       # Custom exceptions
```

**Key Components:**

| Class | Responsibility |
|-------|----------------|
| `BrowserController` | Browser lifecycle, context management |
| `PageManager` | Tab management, navigation |
| `ElementHandle` | DOM element abstraction |
| `CDPConnection` | Chrome DevTools Protocol access |


10. Configuration as Code
Externalize hardcoded values:

```yaml
# config.yaml
browser:
  viewport: [1920, 1080]
  stealth: true
  max_tabs: 3

llm:
  provider: lmstudio
  timeout: 30s
  retries: 3
  fallback_heuristic: true  # Use rule-based if LLM fails

resilience:
  checkpoint_interval: 5  # actions
  max_retry_per_action: 3
  global_timeout: 300s

```

**Playwright Setup:**

```python
from playwright.async_api import async_playwright
from typing import Optional, List

class PlaywrightController:
    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "chromium",
        viewport: dict = {"width": 1920, "height": 1080}
    ):
        self.headless = headless
        self.browser_type = browser_type
        self.viewport = viewport
        self._playwright = None
        self._browser = None
        self._context = None
        self._pages: List[Page] = []
    
    async def launch(self):
        """Initialize browser instance."""
        self._playwright = await async_playwright().start()
        browser_map = {
            "chromium": self._playwright.chromium,
            "firefox": self._playwright.firefox,
            "webkit": self._playwright.webkit
        }
        self._browser = await browser_map[self.browser_type].launch(
            headless=self.headless
        )
        self._context = await self._browser.new_context(
            viewport=self.viewport
        )
        return self
    
    async def new_page(self) -> Page:
        """Create new tab/page."""
        page = await self._context.new_page()
        self._pages.append(Page(page))
        return self._pages[-1]
    
    async def close(self):
        """Cleanup resources."""
        await self._context.close()
        await self._browser.close()
        await self._playwright.stop()
```

#### 1.2 LM Studio Integration

```python
# llm/
# ├── __init__.py
# ├── base.py
# ├── lmstudio_client.py
# ├── config.py
# └── prompts.py

from openai import AsyncOpenAI
from typing import Optional, List, Dict, Any
import json

class LMStudioClient:
    """OpenAI-compatible client for LM Studio."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        model: str = "local-model",
        temperature: float = 0.7,
        max_tokens: int = 2048
    ):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="lm-studio"  # Dummy key for LM Studio
        )
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Send chat completion request."""
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            stream=kwargs.get("stream", False)
        )
        return response.choices[0].message.content
    
    async def chat_stream(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None):
        """Streaming chat for real-time feedback."""
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)
        
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            stream=True
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

#### 1.3 Basic Actor Actions

```python
# actor/
# ├── __init__.py
# ├── actions.py          # Action definitions
# ├── action_executor.py  # Execution logic
# └── action_registry.py  # Action registration

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import asyncio

class ActionType(Enum):
    # Navigation
    NAVIGATE = "navigate"
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"
    REFRESH = "refresh"
    
    # Mouse
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    HOVER = "hover"
    DRAG_AND_DROP = "drag_and_drop"
    
    # Input
    TYPE_TEXT = "type_text"
    CLEAR_INPUT = "clear_input"
    SELECT_OPTION = "select_option"
    CHECK = "check"
    UNCHECK = "uncheck"
    
    # Scroll
    SCROLL_UP = "scroll_up"
    SCROLL_DOWN = "scroll_down"
    SCROLL_TO = "scroll_to"
    
    # Content
    EXTRACT_TEXT = "extract_text"
    EXTRACT_HTML = "extract_html"
    GET_PAGE_INFO = "get_page_info"
    
    # Advanced
    WAIT_FOR = "wait_for"
    SWITCH_FRAME = "switch_frame"
    HANDLE_POPUP = "handle_popup"
    TAKE_SCREENSHOT = "take_screenshot"

@dataclass
class ActionResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    screenshot: Optional[bytes] = None
    metadata: Dict[str, Any] = None

class ActionExecutor:
    """Executes browser actions with retry logic."""
    
    def __init__(self, page, max_retries: int = 3):
        self.page = page
        self.max_retries = max_retries
        self.action_history = []
    
    async def execute(
        self,
        action_type: ActionType,
        target: Optional[str] = None,
        value: Any = None,
        options: Dict[str, Any] = None
    ) -> ActionResult:
        """Execute action with retry and logging."""
        for attempt in range(self.max_retries):
            try:
                result = await self._execute_action(
                    action_type, target, value, options or {}
                )
                self.action_history.append({
                    "action": action_type.value,
                    "target": target,
                    "result": "success" if result.success else "failed",
                    "attempt": attempt + 1
                })
                return result
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return ActionResult(
                        success=False,
                        error=f"Action failed after {self.max_retries} attempts: {str(e)}"
                    )
                await asyncio.sleep(0.5 * (attempt + 1))  # Backoff
        
        return ActionResult(success=False, error="Max retries exceeded")
    
    async def _execute_action(
        self,
        action_type: ActionType,
        target: Optional[str],
        value: Any,
        options: Dict[str, Any]
    ) -> ActionResult:
        """Internal action execution."""
        handlers = {
            ActionType.CLICK: self._click,
            ActionType.TYPE_TEXT: self._type_text,
            ActionType.SCROLL_DOWN: self._scroll_down,
            # ... other handlers
        }
        
        handler = handlers.get(action_type)
        if not handler:
            return ActionResult(success=False, error=f"Unknown action: {action_type}")
        
        return await handler(target, value, options)
    
    async def _click(self, target: str, value: Any, options: Dict) -> ActionResult:
        """Click element by selector."""
        element = await self.page.wait_for_selector(target, timeout=5000)
        await element.click(
            button=options.get("button", "left"),
            click_count=options.get("click_count", 1),
            modifiers=options.get("modifiers", [])
        )
        return ActionResult(success=True, data={"clicked": target})
```

**Deliverables for Phase 1:**
- ✅ Working Playwright browser controller
- ✅ LM Studio integration with chat API
- ✅ 15+ basic browser actions
- ✅ Action execution with retry logic
- ✅ Basic CLI interface

---

### Phase 2: Visual Intelligence (Week 3-4)

**Objective:** Integrate UI-TARS for element detection and visual state analysis.

#### 2.1 UI-TARS Integration

```python
# vision/
# ├── __init__.py
# ├── ui_tars_client.py   # UI-TARS API wrapper
# ├── screenshot_analyzer.py
# ├── element_detector.py
# └── visual_comparator.py

import base64
import json
from io import BytesIO
from PIL import Image
from typing import List, Dict, Any, Tuple, Optional

class UITARSClient:
    """UI-TARS 1.5 client for visual understanding."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        model_name: str = "UI-TARS-1.5"
    ):
        self.base_url = base_url
        self.model_name = model_name
    
    async def analyze_screenshot(
        self,
        screenshot: bytes,
        query: str,
        boxes: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Analyze screenshot with UI-TARS.
        
        Args:
            screenshot: PNG bytes
            query: Natural language query about the screenshot
            boxes: Optional bounding boxes to focus analysis
        
        Returns:
            Parsed response with action predictions
        """
        # Encode image to base64
        img_base64 = base64.b64encode(screenshot).decode()
        
        payload = {
            "image": img_base64,
            "prompt": query,
            "model": self.model_name
        }
        
        # Make API call to UI-TARS server
        # ... HTTP request implementation
        
        return response
    
    async def detect_elements(
        self,
        screenshot: bytes,
        element_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect UI elements with bounding boxes.
        
        Returns:
            List of elements with type, bbox, text, confidence
        """
        query = "Detect all interactive elements including"
        if element_types:
            query += f" {', '.join(element_types)}"
        else:
            query += " buttons, inputs, links, text fields, dropdowns"
        
        response = await self.analyze_screenshot(screenshot, query)
        return self._parse_element_detection(response)
    
    async def predict_action(
        self,
        screenshot: bytes,
        task: str,
        available_actions: List[str] = None
    ) -> Dict[str, Any]:
        """
        Predict next action based on visual understanding.
        Core UI-TARS capability.
        """
        query = f"""Task: {task}
        
Analyze the current screenshot and determine:
1. What is the current state?
2. What element should be interacted with next?
3. What action should be taken?

Available actions: {available_actions or 'click, type, scroll, select'}
"""
        response = await self.analyze_screenshot(screenshot, query)
        return self._parse_action_prediction(response)
```

#### 2.2 Screenshot Analyzer Agent

```python
# agents/
# ├── screenshot_analyzer.py

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

class PageState(Enum):
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    INTERACTIVE = "interactive"
    MODAL = "modal"
    UNKNOWN = "unknown"

@dataclass
class DetectedElement:
    id: str
    element_type: str  # button, input, link, dropdown, etc.
    text: Optional[str]
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    attributes: Dict[str, Any]
    is_visible: bool
    is_interactive: bool

@dataclass
class PageAnalysis:
    state: PageState
    elements: List[DetectedElement]
    summary: str
    recommendations: List[str]
    screenshot_hash: str

class ScreenshotAnalyzer:
    """Analyzes screenshots to understand page state."""
    
    def __init__(self, ui_tars_client: UITARSClient):
        self.ui_tars = ui_tars_client
        self._analysis_cache = {}
    
    async def analyze(
        self,
        screenshot: bytes,
        task_context: Optional[str] = None
    ) -> PageAnalysis:
        """Comprehensive page analysis."""
        # Check cache
        img_hash = self._compute_hash(screenshot)
        if img_hash in self._analysis_cache:
            return self._analysis_cache[img_hash]
        
        # Parallel analysis tasks
        elements_task = self.ui_tars.detect_elements(screenshot)
        state_task = self._determine_page_state(screenshot)
        summary_task = self._generate_summary(screenshot, task_context)
        
        elements, state, summary = await asyncio.gather(
            elements_task, state_task, summary_task
        )
        
        analysis = PageAnalysis(
            state=state,
            elements=elements,
            summary=summary,
            recommendations=self._generate_recommendations(state, elements),
            screenshot_hash=img_hash
        )
        
        # Cache result
        self._analysis_cache[img_hash] = analysis
        return analysis
    
    async def _determine_page_state(self, screenshot: bytes) -> PageState:
        """Determine current page state."""
        response = await self.ui_tars.analyze_screenshot(
            screenshot,
            "What is the current page state? Is it loading, showing an error, or ready for interaction? Are there any popups or modals visible?"
        )
        # Parse response to determine state
        state_text = response.get("state", "").lower()
        
        if "loading" in state_text or "spinner" in state_text:
            return PageState.LOADING
        elif "error" in state_text or "404" in state_text:
            return PageState.ERROR
        elif "modal" in state_text or "popup" in state_text:
            return PageState.MODAL
        elif "ready" in state_text or "interactive" in state_text:
            return PageState.INTERACTIVE
        return PageState.UNKNOWN
    
    async def _generate_summary(
        self,
        screenshot: bytes,
        task_context: Optional[str]
    ) -> str:
        """Generate natural language summary."""
        context_prompt = f" for task: {task_context}" if task_context else ""
        response = await self.ui_tars.analyze_screenshot(
            screenshot,
            f"Provide a brief description of this page{context_prompt}. Focus on key elements and content."
        )
        return response.get("summary", "")
    
    def _generate_recommendations(
        self,
        state: PageState,
        elements: List[DetectedElement]
    ) -> List[str]:
        """Generate action recommendations based on analysis."""
        recommendations = []
        
        if state == PageState.LOADING:
            recommendations.append("Wait for page to fully load")
        elif state == PageState.ERROR:
            recommendations.append("Handle error state - may need retry or navigation")
        elif state == PageState.MODAL:
            recommendations.append("Close modal or interact with dialog first")
        elif state == PageState.INTERACTIVE:
            # Find actionable elements
            actionable = [e for e in elements if e.is_interactive]
            recommendations.append(f"Found {len(actionable)} interactive elements")
        
        return recommendations
```

#### 2.3 Enhanced Actor with Visual Targeting

```python
# actor/
# ├── visual_actor.py

from typing import Union, Optional
import numpy as np

class VisualActor(ActionExecutor):
    """Actor enhanced with visual element detection."""
    
    def __init__(
        self,
        page,
        ui_tars_client: UITARSClient,
        max_retries: int = 3
    ):
        super().__init__(page, max_retries)
        self.ui_tars = ui_tars_client
    
    async def click_visual(
        self,
        description: str,
        screenshot: bytes,
        fuzzy_match: bool = True
    ) -> ActionResult:
        """
        Click element based on visual description.
        
        Args:
            description: Natural language description of element
            screenshot: Current page screenshot
            fuzzy_match: Allow approximate matching
        """
        # Use UI-TARS to find element by description
        response = await self.ui_tars.analyze_screenshot(
            screenshot,
            f"Find the element described as: '{description}'. Return its bounding box coordinates."
        )
        
        bbox = response.get("bbox")
        if not bbox:
            return ActionResult(
                success=False,
                error=f"Could not find element: {description}"
            )
        
        # Convert bbox to click coordinates (center of element)
        x = (bbox[0] + bbox[2]) / 2
        y = (bbox[1] + bbox[3]) / 2
        
        # Perform click at coordinates
        await self.page.mouse.click(x, y)
        
        return ActionResult(
            success=True,
            data={"description": description, "coordinates": (x, y)}
        )
    
    async def find_and_act(
        self,
        action: ActionType,
        description: str,
        screenshot: bytes,
        value: Any = None
    ) -> ActionResult:
        """Find element visually and perform action."""
        # Get screenshot if not provided
        if screenshot is None:
            screenshot = await self.page.screenshot()
        
        # Detect element
        response = await self.ui_tars.analyze_screenshot(
            screenshot,
            f"Locate: '{description}'. What is the bounding box?"
        )
        
        bbox = response.get("bbox")
        if not bbox:
            return ActionResult(success=False, error="Element not found")
        
        # Calculate center coordinates
        x = (bbox[0] + bbox[2]) / 2
        y = (bbox[1] + bbox[3]) / 2
        
        # Execute action
        if action == ActionType.CLICK:
            await self.page.mouse.click(x, y)
        elif action == ActionType.HOVER:
            await self.page.mouse.move(x, y)
        elif action == ActionType.TYPE_TEXT:
            # Click to focus first
            await self.page.mouse.click(x, y)
            await self.page.keyboard.type(value)
        elif action == ActionType.RIGHT_CLICK:
            await self.page.mouse.click(x, y, button="right")
        
        return ActionResult(success=True, data={"action": action.value})
```

**Deliverables for Phase 2:**
- ✅ UI-TARS integration
- ✅ Element detection and localization
- ✅ Visual action targeting
- ✅ Page state assessment
- ✅ Cached analysis for efficiency

---

### Phase 3: Resilience & Recovery (Week 5-6)

**Objective:** Implement checkpoint system, fallback mechanisms, and intelligent recovery.

#### 3.1 State Checkpoint System

```python
# state/
# ├── __init__.py
# ├── checkpoint.py
# ├── state_stack.py
# ├── snapshot.py
# └── recovery.py

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum
import json
import asyncio

class CheckpointType(Enum):
    BEFORE_ACTION = "before_action"
    AFTER_ACTION = "after_action"
    MILESTONE = "milestone"
    MANUAL = "manual"

@dataclass
class BrowserSnapshot:
    """Complete browser state snapshot."""
    timestamp: str
    checkpoint_type: CheckpointType
    url: str
    title: str
    scroll_position: Dict[str, int]
    form_values: Dict[str, Any]
    cookies: List[Dict]
    local_storage: Dict[str, str]
    screenshot: Optional[str]  # Base64 encoded
    page_source_hash: str
    navigation_history: List[str]
    metadata: Dict[str, Any]

@dataclass
class TaskCheckpoint:
    """Task-level checkpoint."""
    id: str
    timestamp: str
    task_description: str
    completed_steps: List[Dict]
    current_step_index: int
    browser_snapshot: BrowserSnapshot
    agent_state: Dict[str, Any]  # Planner, Validator states
    parent_checkpoint_id: Optional[str] = None

class CheckpointManager:
    """Manages state checkpoints for recovery."""
    
    def __init__(
        self,
        storage_path: str = "./checkpoints",
        max_checkpoints: int = 50
    ):
        self.storage_path = storage_path
        self.max_checkpoints = max_checkpoints
        self._checkpoints: List[TaskCheckpoint] = []
        self._current_task_id: Optional[str] = None
    
    async def create_checkpoint(
        self,
        checkpoint_type: CheckpointType,
        browser_state: Dict[str, Any],
        agent_state: Dict[str, Any],
        task_context: str = "",
        description: str = ""
    ) -> str:
        """Create new checkpoint."""
        checkpoint_id = f"cp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self._checkpoints)}"
        
        # Create browser snapshot
        browser_snapshot = BrowserSnapshot(
            timestamp=datetime.now().isoformat(),
            checkpoint_type=checkpoint_type,
            url=browser_state.get("url", ""),
            title=browser_state.get("title", ""),
            scroll_position=browser_state.get("scroll_position", {}),
            form_values=browser_state.get("form_values", {}),
            cookies=browser_state.get("cookies", []),
            local_storage=browser_state.get("local_storage", {}),
            screenshot=browser_state.get("screenshot"),
            page_source_hash=browser_state.get("page_source_hash", ""),
            navigation_history=browser_state.get("navigation_history", []),
            metadata=browser_state.get("metadata", {})
        )
        
        checkpoint = TaskCheckpoint(
            id=checkpoint_id,
            timestamp=datetime.now().isoformat(),
            task_description=task_context,
            completed_steps=agent_state.get("completed_steps", []),
            current_step_index=agent_state.get("current_step_index", 0),
            browser_snapshot=browser_snapshot,
            agent_state=agent_state,
            parent_checkpoint_id=self._get_latest_checkpoint_id()
        )
        
        self._checkpoints.append(checkpoint)
        
        # Prune old checkpoints
        if len(self._checkpoints) > self.max_checkpoints:
            self._prune_oldest()
        
        # Persist to disk
        await self._persist_checkpoint(checkpoint)
        
        return checkpoint_id
    
    async def restore_checkpoint(
        self,
        checkpoint_id: str,
        browser_controller
    ) -> bool:
        """Restore browser to checkpoint state."""
        checkpoint = self._find_checkpoint(checkpoint_id)
        if not checkpoint:
            return False
        
        snapshot = checkpoint.browser_snapshot
        
        try:
            # Navigate to original URL
            await browser_controller.navigate(snapshot.url)
            
            # Restore scroll position
            await browser_controller.set_scroll_position(snapshot.scroll_position)
            
            # Restore cookies
            await browser_controller.set_cookies(snapshot.cookies)
            
            # Wait for page stabilization
            await asyncio.sleep(1)
            
            # Take new screenshot for verification
            current_screenshot = await browser_controller.take_screenshot()
            
            # Verify restoration by comparing screenshots
            if not self._verify_restoration(snapshot.screenshot, current_screenshot):
                return False
            
            return True
        except Exception as e:
            print(f"Restoration failed: {e}")
            return False
    
    def get_checkpoint_chain(self, checkpoint_id: str) -> List[TaskCheckpoint]:
        """Get full history chain for a checkpoint."""
        chain = []
        current = self._find_checkpoint(checkpoint_id)
        
        while current:
            chain.append(current)
            current = self._find_checkpoint(current.parent_checkpoint_id) if current.parent_checkpoint_id else None
        
        return list(reversed(chain))
    
    async def _persist_checkpoint(self, checkpoint: TaskCheckpoint):
        """Save checkpoint to disk."""
        # Implementation for file persistence
        pass
    
    def _prune_oldest(self):
        """Remove oldest checkpoints beyond limit."""
        while len(self._checkpoints) > self.max_checkpoints:
            self._checkpoints.pop(0)
    
    def _find_checkpoint(self, checkpoint_id: str) -> Optional[TaskCheckpoint]:
        """Find checkpoint by ID."""
        for cp in self._checkpoints:
            if cp.id == checkpoint_id:
                return cp
        return None
    
    def _get_latest_checkpoint_id(self) -> Optional[str]:
        """Get ID of most recent checkpoint."""
        return self._checkpoints[-1].id if self._checkpoints else None
```

#### 3.2 Fallback Strategy Generator

```python
# fallback/
# ├── __init__.py
# ├── strategy_generator.py
# ├── error_classifier.py
# └── recovery_orchestrator.py

from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

class ErrorType(Enum):
    ELEMENT_NOT_FOUND = "element_not_found"
    ACTION_TIMEOUT = "action_timeout"
    NAVIGATION_ERROR = "navigation_error"
    SELECTOR_INVALID = "selector_invalid"
    STATE_MISMATCH = "state_mismatch"
    CAPTCHA_BLOCK = "captcha_block"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"

@dataclass
class FallbackStrategy:
    name: str
    description: str
    execute: Callable
    priority: int  # Lower = higher priority
    max_attempts: int

class FallbackOrchestrator:
    """Manages fallback strategies for failed actions."""
    
    def __init__(self, actor, planner):
        self.actor = actor
        self.planner = planner
        self._strategies: Dict[ErrorType, List[FallbackStrategy]] = {}
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """Register built-in fallback strategies."""
        
        # Element Not Found strategies
        self.register_strategy(
            ErrorType.ELEMENT_NOT_FOUND,
            FallbackStrategy(
                name="visual_search",
                description="Search for element visually using UI-TARS",
                execute=self._visual_search_fallback,
                priority=1,
                max_attempts=2
            )
        )
        
        self.register_strategy(
            ErrorType.ELEMENT_NOT_FOUND,
            FallbackStrategy(
                name="alternative_selector",
                description="Try alternative selectors for same element",
                execute=self._alternative_selector_fallback,
                priority=2,
                max_attempts=3
            )
        )
        
        self.register_strategy(
            ErrorType.ELEMENT_NOT_FOUND,
            FallbackStrategy(
                name="scroll_and_retry",
                description="Scroll to reveal hidden elements",
                execute=self._scroll_retry_fallback,
                priority=3,
                max_attempts=2
            )
        )
        
        # Action Timeout strategies
        self.register_strategy(
            ErrorType.ACTION_TIMEOUT,
            FallbackStrategy(
                name="wait_longer",
                description="Wait extended time and retry",
                execute=self._wait_retry_fallback,
                priority=1,
                max_attempts=2
            )
        )
        
        self.register_strategy(
            ErrorType.ACTION_TIMEOUT,
            FallbackStrategy(
                name="refresh_and_retry",
                description="Refresh page and attempt action again",
                execute=self._refresh_retry_fallback,
                priority=2,
                max_attempts=1
            )
        )
        
        # Navigation Error strategies
        self.register_strategy(
            ErrorType.NAVIGATION_ERROR,
            FallbackStrategy(
                name="retry_navigation",
                description="Retry navigation to same URL",
                execute=self._retry_navigation_fallback,
                priority=1,
                max_attempts=2
            )
        )
        
        self.register_strategy(
            ErrorType.NAVIGATION_ERROR,
            FallbackStrategy(
                name="check_connectivity",
                description="Verify network and try alternate route",
                execute=self._check_connectivity_fallback,
                priority=2,
                max_attempts=1
            )
        )
    
    def register_strategy(
        self,
        error_type: ErrorType,
        strategy: FallbackStrategy
    ):
        """Register new fallback strategy."""
        if error_type not in self._strategies:
            self._strategies[error_type] = []
        self._strategies[error_type].append(strategy)
        # Sort by priority
        self._strategies[error_type].sort(key=lambda s: s.priority)
    
    async def execute_with_fallback(
        self,
        action: Callable,
        error_classifier: Callable,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute action with automatic fallback on failure."""
        attempt = 0
        error_history = []
        
        while attempt < 10:  # Max total attempts
            try:
                result = await action()
                if result.success:
                    return {"success": True, "result": result, "fallback_attempts": attempt}
            except Exception as e:
                error_type = error_classifier(e)
                error_history.append({"attempt": attempt, "error": str(e), "type": error_type})
                
                # Find applicable strategies
                strategies = self._strategies.get(error_type, [])
                
                strategy_executed = False
                for strategy in strategies:
                    if attempt < strategy.max_attempts:
                        try:
                            await strategy.execute(context)
                            strategy_executed = True
                            attempt += 1
                            break
                        except Exception as strategy_error:
                            continue
                
                if not strategy_executed:
                    # No more strategies to try
                    return {
                        "success": False,
                        "error": str(e),
                        "error_type": error_type,
                        "fallback_attempts": attempt,
                        "error_history": error_history
                    }
        
        return {"success": False, "error": "Max attempts exceeded", "error_history": error_history}
    
    # Fallback Strategy Implementations
    
    async def _visual_search_fallback(self, context: Dict[str, Any]) -> bool:
        """Use UI-TARS to find element visually."""
        screenshot = context.get("screenshot")
        element_description = context.get("element_description")
        
        # Use VisualActor to find and click
        result = await self.actor.click_visual(
            description=element_description,
            screenshot=screenshot
        )
        return result.success
    
    async def _alternative_selector_fallback(self, context: Dict[str, Any]) -> bool:
        """Try different selector strategies."""
        element = context.get("element")
        selectors = element.get("alternative_selectors", [])
        
        for selector in selectors:
            try:
                await self.actor.execute(
                    context.get("action"),
                    target=selector,
                    value=context.get("value")
                )
                return True
            except Exception:
                continue
        
        return False
    
    async def _scroll_retry_fallback(self, context: Dict[str, Any]) -> bool:
        """Scroll to reveal element and retry."""
        await self.actor.execute(ActionType.SCROLL_DOWN, value=500)
        await asyncio.sleep(0.5)
        await self.actor.execute(ActionType.SCROLL_DOWN, value=500)
        return True
    
    async def _wait_retry_fallback(self, context: Dict[str, Any]) -> bool:
        """Extended wait before retry."""
        await asyncio.sleep(5)  # 5 second wait
        return True
    
    async def _refresh_retry_fallback(self, context: Dict[str, Any]) -> bool:
        """Refresh page and retry."""
        await self.actor.execute(ActionType.REFRESH)
        await asyncio.sleep(2)
        return True
```

#### 3.3 State Stack for Rollback

```python
# state/
# ├── state_stack.py

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

@dataclass
class StateFrame:
    """Single frame in the state stack."""
    id: str
    timestamp: str
    data: Dict[str, Any]
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = None

class StateStack:
    """
    Stack-based state management for rollback capabilities.
    Maintains history of state changes for undo/redo.
    """
    
    def __init__(self, max_depth: int = 100):
        self.max_depth = max_depth
        self._frames: Dict[str, StateFrame] = {}
        self._current_id: Optional[str] = None
        self._branch_points: Dict[str, List[str]] = {}  # For branching support
    
    def push(self, data: Dict[str, Any], metadata: Dict[str, Any] = None) -> str:
        """Push new state onto stack."""
        frame_id = f"frame_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}"
        
        frame = StateFrame(
            id=frame_id,
            timestamp=datetime.now().isoformat(),
            data=data,
            parent_id=self._current_id,
            metadata=metadata
        )
        
        self._frames[frame_id] = frame
        self._current_id = frame_id
        
        # Enforce max depth
        if len(self._frames) > self.max_depth:
            self._prune_oldest()
        
        return frame_id
    
    def pop(self) -> Optional[Dict[str, Any]]:
        """Pop current state and move to parent."""
        if not self._current_id:
            return None
        
        current_frame = self._frames[self._current_id]
        self._current_id = current_frame.parent_id
        
        return current_frame.data

    def rollback_to(self, frame_id: str) -> Optional[Dict[str, Any]]:
        """Rollback to specific frame in history."""
        if frame_id not in self._frames:
            return None
        
        self._current_id = frame_id
        return self._frames[frame_id].data

    def get_current(self) -> Optional[Dict[str, Any]]:
        """Get current state without removing."""
        if not self._current_id:
            return None
        return self._frames[self._current_id].data

    def get_history(self, frame_id: Optional[str] = None) -> List[StateFrame]:
        """Get full history chain from root to current."""
        if frame_id is None:
            frame_id = self._current_id
        
        history = []
        current = self._frames.get(frame_id)
        
        while current:
            history.append(current)
            current = self._frames.get(current.parent_id) if current.parent_id else None
        
        return list(reversed(history))

    def create_branch(self, name: str) -> str:
        """Create named branch point for future return."""
        if self._current_id:
            if self._current_id not in self._branch_points:
                self._branch_points[self._current_id] = []
            self._branch_points[self._current_id].append(name)
        return self._current_id

    def merge_branch(self, branch_id: str):
        """Merge branch back into main timeline."""
        # Keep branch state but connect to main timeline
        if branch_id in self._frames:
            branch_frame = self._frames[branch_id]
            current_frame = self._frames.get(self._current_id)
            
            if current_frame:
                branch_frame.parent_id = self._current_id
            
            self._current_id = branch_id

    def _prune_oldest(self):
        """Remove oldest frames beyond max depth."""
        # Keep frames in current branch, prune orphans
        current_ids = set(f.id for f in self.get_history())
        
        frames_to_remove = [
            fid for fid in self._frames 
            if fid not in current_ids
        ][:len(self._frames) - self.max_depth]
        
        for fid in frames_to_remove:
            del self._frames[fid]
```

**Deliverables for Phase 3:**
- ✅ Checkpoint creation and restoration
- ✅ Error classification system
- ✅ 10+ fallback strategies
- ✅ State stack with rollback
- ✅ Automatic recovery orchestration

---

### Phase 4: Advanced Capabilities (Week 7-8)

**Objective:** Implement skills, multi-agent coordination, and production features.

#### 4.1 Skill System

```python
# skills/
# ├── __init__.py
# ├── base_skill.py
# ├── forms_skill.py
# ├── extraction_skill.py
# ├── scraping_skill.py
# └── workflow_skill.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

class SkillType(Enum):
    FORMS_FILLING = "forms_filling"
    DATA_EXTRACTION = "data_extraction"
    WEB_SCRAPING = "web_scraping"
    WORKFLOW = "workflow"

@dataclass
class SkillResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    steps_completed: List[str] = None
    metadata: Dict[str, Any] = None

class BaseSkill(ABC):
    """Abstract base class for all skills."""
    
    def __init__(
        self,
        name: str,
        description: str,
        skill_type: SkillType
    ):
        self.name = name
        self.description = description
        self.skill_type = skill_type
        self.required_capabilities: List[str] = []
    
    @abstractmethod
    async def execute(
        self,
        context: Dict[str, Any],
        actor,
        planner
    ) -> SkillResult:
        """Execute the skill with given context."""
        pass
    
    @abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input parameters."""
        pass

class FormsFillingSkill(BaseSkill):
    """Skill for intelligent form completion."""
    
    def __init__(self):
        super().__init__(
            name="forms_filling",
            description="Automatically fill web forms with provided data",
            skill_type=SkillType.FORMS_FILLING
        )
        self.required_capabilities = ["click", "type_text", "select_option", "screenshot_analyze"]
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate form filling input."""
        required = ["url", "form_schema", "form_data"]
        return all(key in input_data for key in required)
    
    async def execute(
        self,
        context: Dict[str, Any],
        actor,
        planner
    ) -> SkillResult:
        """Execute form filling."""
        form_schema = context["form_schema"]  # Field definitions
        form_data = context["form_data"]      # Values to fill
        screenshot = context.get("screenshot")
        
        steps_completed = []
        errors = []
        
        # Navigate to form
        await actor.execute(ActionType.NAVIGATE, value=context["url"])
        steps_completed.append("Navigated to form")
        
        for field in form_schema:
            field_name = field["name"]
            field_type = field.get("type", "text")
            selector = field.get("selector")
            value = form_data.get(field_name)
            
            if value is None:
                continue
            
            try:
                # Find field using selector or visual search
                if not selector:
                    detection = await actor.ui_tars.detect_elements(
                        screenshot,
                        element_types=[field_type]
                    )
                    selector = self._match_field(detection, field_name)
                
                # Execute appropriate action based on type
                if field_type == "text":
                    await actor.execute(ActionType.TYPE_TEXT, target=selector, value=value)
                elif field_type == "select":
                    await actor.execute(ActionType.SELECT_OPTION, target=selector, value=value)
                elif field_type == "checkbox":
                    if value:
                        await actor.execute(ActionType.CHECK, target=selector)
                elif field_type == "radio":
                    await actor.execute(ActionType.CLICK, target=selector)
                
                steps_completed.append(f"Filled field: {field_name}")
                
            except Exception as e:
                errors.append(f"Error filling {field_name}: {str(e)}")
        
        # Handle submission
        submit_selector = context.get("submit_selector")
        if submit_selector:
            await actor.execute(ActionType.CLICK, target=submit_selector)
            steps_completed.append("Submitted form")
        
        return SkillResult(
            success=len(errors) == 0,
            data={"filled_fields": steps_completed},
            error="; ".join(errors) if errors else None,
            steps_completed=steps_completed
        )
    
    def _match_field(self, detection_results, field_name: str) -> Optional[str]:
        """Match detected element to field name."""
        # Fuzzy matching logic
        pass

class DataExtractionSkill(BaseSkill):
    """Skill for structured data extraction from web pages."""
    
    def __init__(self):
        super().__init__(
            name="data_extraction",
            description="Extract structured data from web pages",
            skill_type=SkillType.DATA_EXTRACTION
        )
        self.required_capabilities = ["screenshot_analyze", "extract_text", "scroll"]
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        return "extraction_schema" in input_data
    
    async def execute(
        self,
        context: Dict[str, Any],
        actor,
        planner
    ) -> SkillResult:
        """Execute data extraction."""
        schema = context["extraction_schema"]
        max_items = context.get("max_items", 50)
        
        extracted_data = []
        seen_items = set()
        
        while len(extracted_data) < max_items:
            # Get current view
            screenshot = await actor.page.screenshot()
            
            # Analyze with UI-TARS
            elements = await actor.ui_tars.detect_elements(screenshot)
            
            # Extract based on schema
            for item_def in schema.get("items", []):
                item_data = await self._extract_item(
                    elements,
                    item_def,
                    actor
                )
                
                # Deduplicate
                item_key = str(item_data)
                if item_key not in seen_items:
                    extracted_data.append(item_data)
                    seen_items.add(item_key)
            
            # Check for pagination
            if not await self._has_next_page(actor):
                break
            
            # Navigate to next page
            await actor.execute(ActionType.CLICK, target="next_button")
            await asyncio.sleep(1)
        
        return SkillResult(
            success=True,
            data={"items": extracted_data, "count": len(extracted_data)},
            steps_completed=[f"Extracted {len(extracted_data)} items"]
        )
```

#### 4.2 Multi-Agent Coordination

```python
# agents/
# ├── supervisor.py
# ├── planner.py
# ├── validator.py
# └── coordinator.py

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio

class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class AgentMessage:
    sender: str
    receiver: str
    content: Dict[str, Any]
    timestamp: str
    message_type: str

@dataclass
class SubAgent:
    name: str
    status: AgentStatus
    capabilities: List[str]
    current_task: Optional[str] = None
    result: Optional[Any] = None

class SupervisorOrchestrator:
    """
    Main orchestrator coordinating all sub-agents.
    Implements Supervisor pattern for multi-agent coordination.
    """
    
    def __init__(
        self,
        llm_client,
        browser_controller,
        checkpoint_manager
    ):
        self.llm = llm_client
        self.browser = browser_controller
        self.checkpoint = checkpoint_manager
        
        # Initialize sub-agents
        self.agents = {
            "planner": SubAgent(
                name="planner",
                capabilities=["task_decomposition", "strategy_generation", "replanning"]
            ),
            "analyzer": SubAgent(
                name="analyzer",
                capabilities=["element_detection", "state_assessment", "visual_understanding"]
            ),
            "actor": SubAgent(
                name="actor",
                capabilities=["click", "type", "scroll", "navigate", "extract"]
            ),
            "validator": SubAgent(
                name="validator",
                capabilities=["precondition_check", "postcondition_check", "state_verification"]
            )
        }
        
        # Message queue for agent communication
        self._message_queue: List[AgentMessage] = []
        
        # Execution state
        self.current_task: Optional[str] = None
        self.execution_history: List[Dict] = []
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        """Main entry point for task execution."""
        self.current_task = task
        
        # Phase 1: Planning
        plan = await self._delegate_to_agent(
            "planner",
            "create_plan",
            {"task": task}
        )
        
        if not plan.get("success"):
            return {"success": False, "error": "Planning failed", "stage": "planning"}
        
        # Phase 2: Execute plan steps
        for step_index, step in enumerate(plan["steps"]):
            # Create checkpoint before step
            await self.checkpoint.create_checkpoint(
                CheckpointType.BEFORE_ACTION,
                await self._get_browser_state(),
                {"current_step": step_index, "step": step},
                task_context=task
            )
            
            # Analyze current state
            screenshot = await self.browser.take_screenshot()
            analysis = await self._delegate_to_agent(
                "analyzer",
                "analyze",
                {"screenshot": screenshot, "context": step}
            )
            
            # Validate preconditions
            validation = await self._delegate_to_agent(
                "validator",
                "check_preconditions",
                {"step": step, "analysis": analysis}
            )
            
            if not validation["satisfied"]:
                # Handle validation failure
                fallback_result = await self._handle_validation_failure(
                    step, validation, analysis
                )
                if not fallback_result["success"]:
                    return self._create_failure_response(step, validation)
            
            # Execute step
            execution_result = await self._delegate_to_agent(
                "actor",
                "execute",
                {"step": step, "analysis": analysis}
            )
            
            # Validate postconditions
            post_screenshot = await self.browser.take_screenshot()
            post_validation = await self._delegate_to_agent(
                "validator",
                "check_postconditions",
                {"step": step, "result": execution_result, "screenshot": post_screenshot}
            )
            
            if not post_validation["satisfied"]:
                # Trigger fallback/retry
                await self._handle_execution_failure(step, post_validation)
            
            # Record in history
            self.execution_history.append({
                "step": step,
                "result": execution_result,
                "validation": post_validation
            })
        
        # Phase 3: Synthesize results
        final_result = await self._synthesize_results()
        
        return {
            "success": True,
            "result": final_result,
            "history": self.execution_history
        }
    
    async def _delegate_to_agent(
        self,
        agent_name: str,
        method: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Delegate task to specific sub-agent."""
        agent = self.agents.get(agent_name)
        if not agent:
            return {"success": False, "error": f"Unknown agent: {agent_name}"}
        
        agent.status = AgentStatus.RUNNING
        agent.current_task = f"{method}: {params}"
        
        try:
            # Route to appropriate handler
            handler = getattr(self, f"_{agent_name}_{method}", None)
            if not handler:
                # Use LLM to process if no explicit handler
                result = await self._llm_process_agent(agent_name, method, params)
            else:
                result = await handler(params)
            
            agent.status = AgentStatus.COMPLETED
            agent.result = result
            
            return result
        except Exception as e:
            agent.status = AgentStatus.FAILED
            return {"success": False, "error": str(e)}
    
    async def _planner_create_plan(self, params: Dict) -> Dict[str, Any]:
        """Planner agent: Create execution plan."""
        task = params["task"]
        
        prompt = f"""Break down this task into precise browser automation steps:

Task: {task}

For each step provide:
1. Action type (navigate, click, type, scroll, extract, wait)
2. Target element (selector or visual description)
3. Value if needed (text to type, option to select)
4. Preconditions
5. Expected outcome

Be specific about element selection to minimize ambiguity.
"""
        
        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse into structured plan
        steps = self._parse_plan_response(response)
        
        return {"success": True, "steps": steps}
    
    async def _validator_check_preconditions(
        self,
        params: Dict
    ) -> Dict[str, Any]:
        """Validator agent: Check if preconditions are met."""
        step = params["step"]
        analysis = params["analysis"]
        
        # Check if required elements are visible
        required_elements = step.get("required_elements", [])
        detected_elements = analysis.get("elements", [])
        
        missing = []
        for req in required_elements:
            if not self._element_present(req, detected_elements):
                missing.append(req)
        
        return {
            "satisfied": len(missing) == 0,
            "missing_elements": missing,
            "analysis": analysis
        }
    
    async def _handle_validation_failure(
        self,
        step: Dict,
        validation: Dict,
        analysis: Dict
    ) -> Dict[str, Any]:
        """Handle precondition validation failure."""
        # Try scrolling to find missing elements
        if len(validation["missing_elements"]) > 0:
            await self.browser.scroll_down(500)
            new_screenshot = await self.browser.take_screenshot()
            
            # Re-analyze
            new_analysis = await self._delegate_to_agent(
                "analyzer",
                "analyze",
                {"screenshot": new_screenshot}
            )
            
            # Check again
            retry_result = await self._validator_check_preconditions({
                "step": step,
                "analysis": new_analysis
            })
            
            if retry_result["satisfied"]:
                return {"success": True, "recovered": True}
        
        # Ask planner for alternative approach
        alternative = await self._delegate_to_agent(
            "planner",
            "generate_alternative",
            {"failed_step": step, "reason": validation["missing_elements"]}
        )
        
        return {"success": False, "alternative": alternative}
    
    async def _synthesize_results(self) -> Dict[str, Any]:
        """Synthesize final results from execution history."""
        summary_prompt = f"""Summarize the execution results:

Task: {self.current_task}

Steps completed:
{self._format_history(self.execution_history)}

Provide:
1. Overall success/failure status
2. Key findings or data extracted
3. Any issues encountered
"""
        
        summary = await self.llm.chat(
            messages=[{"role": "user", "content": summary_prompt}]
        )
        
        return {"summary": summary, "steps_completed": len(self.execution_history)}
```

**Deliverables for Phase 4:**
- ✅ Forms Filling skill
- ✅ Data Extraction skill
- ✅ Web Scraping skill
- ✅ Workflow skill
- ✅ Supervisor orchestration
- ✅ Agent communication protocol

---

### Phase 5: Production & Polish (Week 9-10)

**Objective:** Add observability, API, web UI, and production hardening.

```python
# api/
# ├── main.py
# ├── routes/
# │   ├── tasks.py
# │   ├── sessions.py
# │   └── skills.py
# └── schemas.py

# web_ui/
# ├── app.py
# ├── components/
# └── pages/

# monitoring/
# ├── logging.py
# ├── metrics.py
# └── tracing.py
```

**Deliverables for Phase 5:**
- ✅ FastAPI endpoints for task submission and monitoring
- ✅ Web dashboard for visual task tracking
- ✅ Streaming responses for real-time feedback
- ✅ Structured logging with correlation IDs
- ✅ Metrics collection (task duration, success rate, error types)
- ✅ Health checks and graceful shutdown
- ✅ Docker containerization
- ✅ Configuration management

---

## 📊 Implementation Difficulty Analysis

### Enhanced Ideas Ranked by Implementation Difficulty

| Idea | Difficulty | Reason | Estimated Time |
|------|------------|--------|----------------|
| **Visual Memory System** | ⭐ Easy | Standalone caching layer | 2-3 days |
| **Multi-Tab Manager** | ⭐ Easy | Natural extension to Playwright | 3-5 days |
| **Intelligent Element Matching** | ⭐⭐ Medium | Requires refinement of existing detection | 5-7 days |
| **Proactive Error Prevention** | ⭐⭐ Medium | Heuristic rules, low complexity | 5-7 days |
| **Conversation Memory** | ⭐⭐ Medium | Persistence layer + retrieval | 7-10 days |
| **Resource Management** | ⭐⭐⭐ Hard | Requires architectural changes | 10-14 days |

### Recommended Implementation Order

1. **Start with**: Multi-Tab Manager + Visual Memory System (Phase 1-2 overlap)
2. **Add during**: Intelligent Element Matching (Phase 3)
3. **Enhance with**: Proactive Error Prevention (Phase 3-4)
4. **Complete with**: Conversation Memory + Resource Management (Phase 5)

---

## 🎯 Recommended Starting Point

I recommend starting with **Phase 1 + Visual Memory System** as your foundation:

1. Browser controller with Playwright
2. Basic actor actions
3. LM Studio integration
4. Simple screenshot caching for repeated elements

This gives you a working system quickly while setting up the architecture for more advanced features.

Would you like me to start implementing Phase 1 with you? I can create the full project structure and core modules.
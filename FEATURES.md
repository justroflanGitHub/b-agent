# Browser Agent Features Documentation

This document provides comprehensive documentation for every feature implemented in the Browser Agent system.

---

## Table of Contents

1. [Core Foundation (Phase 1)](#1-core-foundation-phase-1)
2. [Visual Intelligence (Phase 2)](#2-visual-intelligence-phase-2)
3. [Resilience & Recovery (Phase 3)](#3-resilience--recovery-phase-3)
4. [Advanced Capabilities (Phase 4)](#4-advanced-capabilities-phase-4)
5. [Production & Polish (Phase 5)](#5-production--polish-phase-5)
6. [Memory System (v0.10.0)](#6-memory-system-v0100)
7. [iframe Support (v0.11.0)](#7-iframe-support-v0110)
8. [Testing Infrastructure (v0.12.0)](#8-testing-infrastructure-v0120)

---

## 1. Core Foundation (Phase 1)

### 1.1 Browser Controller

**File:** [`browser_agent/browser/controller.py`](browser_agent/browser/controller.py)

The Browser Controller is the foundation of the system, providing browser automation through Playwright.

#### Features:

##### 1.1.1 Multi-Browser Support
- **Chromium** (default) - Full support with anti-detection
- **Firefox** - Full support
- **WebKit** - Full support

```python
# Configuration
browser_type: "chromium" | "firefox" | "webkit"
```

##### 1.1.2 Anti-Detection & Stealth Mode
Injects JavaScript to hide automation indicators:

```javascript
// Removes webdriver property
Object.defineProperty(navigator, 'webdriver', { get: () => false });

// Mocks plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
        // ... more plugins
    ],
});

// Mocks languages
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

// Mocks battery API
navigator.getBattery = () => Promise.resolve({
    charging: true,
    chargingTime: Infinity,
    dischargingTime: Infinity,
    level: 1,
});

// Hides automation indicators
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
```

##### 1.1.3 Realistic HTTP Headers
Sets realistic browser headers to avoid detection:

```python
DEFAULT_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9...',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"...',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    # ... more headers
}
```

##### 1.1.4 Headless/Headful Mode
- **Headless Mode** (`headless: true`) - No visible browser window
- **Headful Mode** (`headless: false`) - Visible browser for debugging

##### 1.1.5 Page/Tab Management
```python
async def new_page(self) -> Page  # Create new page
async def close_page(self, page)   # Close specific page
async def get_state(self) -> BrowserState  # Get current state
```

##### 1.1.6 Navigation Actions
```python
async def goto(self, url: str)  # Navigate to URL
async def go_back(self)         # Go back in history
async def go_forward(self)      # Go forward in history
async def refresh(self)         # Refresh page
```

##### 1.1.7 Screenshot Capture
```python
async def screenshot(self, full_page: bool = False) -> bytes
```

##### 1.1.8 Cookie Management
```python
async def get_cookies(self) -> List[Dict]
async def set_cookies(self, cookies: List[Dict])
async def clear_cookies(self)
```

##### 1.1.9 Viewport Configuration
```python
viewport_width: int = 1280
viewport_height: int = 720
```

---

### 1.2 LLM Client

**File:** [`browser_agent/llm/client.py`](browser_agent/llm/client.py)

The LLM Client provides communication with language models for intelligent decision-making.

#### Features:

##### 1.2.1 Multi-Provider Support
- **LM Studio** (local, default)
- **Ollama** (local)
- **OpenAI** (cloud)
- **Any OpenAI-compatible API**

##### 1.2.2 Async Chat Completions
```python
async def chat(
    self,
    messages: List[ChatMessage],
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> ChatResponse
```

##### 1.2.3 Vision Model Support
```python
async def chat_with_image(
    self,
    text: str,
    image: Union[bytes, str],  # Image bytes or base64
    system_prompt: Optional[str] = None,
) -> ChatResponse
```

##### 1.2.4 Streaming Responses
```python
async def chat_stream(
    self,
    messages: List[ChatMessage],
) -> AsyncGenerator[str, None]
```

##### 1.2.5 Retry Logic with Exponential Backoff
```python
max_retries: int = 3
retry_delay: float = 1.0
exponential_backoff: bool = True
```

##### 1.2.6 Message Types
```python
class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

@dataclass
class ChatMessage:
    role: MessageRole
    content: str
    images: Optional[List[str]] = None  # Base64 encoded
```

##### 1.2.7 Response Structure
```python
@dataclass
class ChatResponse:
    content: str
    model: str
    usage: Dict[str, int]  # prompt_tokens, completion_tokens
    finish_reason: str
    latency_ms: float
```

---

### 1.3 Action Executor

**File:** [`browser_agent/actor/actions.py`](browser_agent/actor/actions.py)

The Action Executor handles all browser actions with retry logic.

#### Features:

##### 1.3.1 Action Types

| Category | Actions |
|----------|---------|
| **Navigation** | `navigate`, `go_back`, `go_forward`, `refresh` |
| **Mouse** | `click`, `double_click`, `right_click`, `hover`, `drag_and_drop` |
| **Visual Mouse** | `hover_visual`, `type_visual` (coordinate-based) |
| **Input** | `type_text`, `clear_input`, `select_option`, `check`, `uncheck` |
| **Scroll** | `scroll_up`, `scroll_down`, `scroll_to`, `scroll_to_element` |
| **Content** | `extract_text`, `extract_html`, `get_page_info`, `take_screenshot` |
| **Advanced** | `wait`, `wait_for_element`, `wait_for_navigation`, `switch_frame`, `handle_dialog`, `press_key` |

##### 1.3.2 Action Result Structure
```python
@dataclass
class ActionResult:
    success: bool
    action_type: ActionType
    data: Any = None
    error: Optional[str] = None
    screenshot: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    retry_count: int = 0
```

##### 1.3.3 Retry Logic
```python
max_retries: int = 3
base_delay: float = 1.0
exponential_backoff: bool = True
```

##### 1.3.4 Action Context
```python
@dataclass
class ActionContext:
    browser: BrowserController
    page: Page  # Playwright page
    config: Config
    vision_client: Optional[VisionClient] = None
    screenshot: Optional[bytes] = None
```

##### 1.3.5 Human-like Typing
```python
async def _type_text(self, context: ActionContext, ...):
    # Types with random delays between keystrokes
    for char in text:
        await page.type(selector, char, delay=random.randint(50, 150))
```

---

### 1.4 Configuration System

**File:** [`browser_agent/config.py`](browser_agent/config.py)

Centralized configuration management.

#### Features:

##### 1.4.1 Configuration Sections
```python
@dataclass
class Config:
    browser: BrowserConfig
    llm: LLMConfig
    vision: VisionConfig
    resilience: ResilienceConfig
    observability: ObservabilityConfig
```

##### 1.4.2 Environment Variable Support
```python
# From environment variables
config = Config.from_env()

# BROWSER_TYPE=chromium
# LLM_BASE_URL=http://localhost:1234
# VISION_MODEL=ui-tars
```

##### 1.4.3 YAML Configuration File
```yaml
# config.yaml
browser:
  browser_type: chromium
  headless: false
  viewport_width: 1280
  viewport_height: 720

llm:
  base_url: http://localhost:1234
  model: local-model
  temperature: 0.7
  max_tokens: 4096

vision:
  model: ui-tars
  cache_enabled: true

resilience:
  max_retry_per_action: 3
  checkpoint_enabled: true
```

##### 1.4.4 Default Values
```python
# All configurations have sensible defaults
browser_type: str = "chromium"
headless: bool = True
viewport_width: int = 1280
viewport_height: int = 720
timeout: float = 30.0
```

---

## 2. Visual Intelligence (Phase 2)

### 2.1 Vision Client

**File:** [`browser_agent/llm/client.py`](browser_agent/llm/client.py) (VisionClient class)

Extends LLM Client for visual understanding.

#### Features:

##### 2.1.1 Screenshot Analysis
```python
async def analyze_screenshot(
    self,
    screenshot: bytes,
    instruction: str,
) -> Dict[str, Any]
```

##### 2.1.2 Click Coordinate Detection
```python
async def get_click_coordinates(
    self,
    screenshot: bytes,
    instruction: str,
) -> Dict[str, Any]:
    # Returns {"coordinates": [x, y], "confidence": 0.95}
```

##### 2.1.3 Element Detection
```python
async def detect_element(
    self,
    screenshot: bytes,
    element_description: str,
) -> Dict[str, Any]:
    # Returns bounding box and confidence
```

##### 2.1.4 Page State Analysis
```python
async def analyze_page_state(
    self,
    screenshot: bytes,
) -> Dict[str, Any]:
    # Returns page state classification
```

---

### 2.2 Visual Analyzer

**File:** [`browser_agent/vision/analyzer.py`](browser_agent/vision/analyzer.py)

Advanced screenshot analysis for browser automation.

#### Features:

##### 2.2.1 Page State Classification
```python
class PageState(Enum):
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    MODAL = "modal"
    LOGIN_REQUIRED = "login_required"
    CAPTCHA = "captcha"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    REDIRECTING = "redirecting"
```

##### 2.2.2 Element Type Classification
```python
class ElementType(Enum):
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
```

##### 2.2.3 Bounding Box Extraction
```python
@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0
    
    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    @property
    def area(self) -> int:
        return self.width * self.height
    
    def contains(self, x: int, y: int) -> bool: ...
    def overlaps(self, other: BoundingBox) -> bool: ...
```

##### 2.2.4 Element Information
```python
@dataclass
class ElementInfo:
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
```

##### 2.2.5 Page Analysis Result
```python
@dataclass
class PageAnalysis:
    state: PageState
    elements: List[ElementInfo]
    summary: str
    recommended_actions: List[str]
    loading_percentage: Optional[int] = None
    error_message: Optional[str] = None
    modal_content: Optional[str] = None
    confidence: float = 1.0
```

---

### 2.3 Screenshot Diff

**File:** [`browser_agent/vision/diff.py`](browser_agent/vision/diff.py)

Detects visual changes between screenshots.

#### Features:

##### 2.3.1 Change Detection
```python
async def detect_changes(
    self,
    before: bytes,
    after: bytes,
) -> Dict[str, Any]:
    # Returns changed regions and change percentage
```

##### 2.3.2 Region Comparison
```python
async def compare_regions(
    self,
    screenshot: bytes,
    region1: BoundingBox,
    region2: BoundingBox,
) -> float:  # Similarity score 0-1
```

##### 2.3.3 Motion Detection
```python
async def detect_motion(
    self,
    screenshots: List[bytes],
) -> List[BoundingBox]:  # Regions with motion
```

---

### 2.4 Vision Cache

**File:** [`browser_agent/vision/cache.py`](browser_agent/vision/cache.py)

Caches vision analysis results for performance.

#### Features:

##### 2.4.1 Screenshot Hashing
```python
def _get_screenshot_hash(self, screenshot: bytes) -> str:
    return hashlib.md5(screenshot).hexdigest()
```

##### 2.4.2 LRU Cache Eviction
```python
max_cache_size: int = 100
# Least Recently Used eviction policy
```

##### 2.4.3 Similarity Lookup
```python
async def find_similar(
    self,
    screenshot: bytes,
    threshold: float = 0.95,
) -> Optional[PageAnalysis]:
    # Find cached analysis for similar screenshot
```

---

## 3. Resilience & Recovery (Phase 3)

### 3.1 Checkpoint System

**File:** [`browser_agent/resilience/checkpoint.py`](browser_agent/resilience/checkpoint.py)

Creates and manages browser state snapshots.

#### Features:

##### 3.1.1 Checkpoint Types
```python
class CheckpointType(Enum):
    PRE_ACTION = "pre_action"      # Before an action
    POST_ACTION = "post_action"    # After successful action
    TASK_START = "task_start"      # At task beginning
    TASK_END = "task_end"          # At task completion
    MANUAL = "manual"              # Manually created
    RECOVERY = "recovery"          # Before recovery attempt
    BRANCH = "branch"              # Before branching operation
```

##### 3.1.2 Browser State Capture
```python
@dataclass
class BrowserState:
    url: str
    title: str
    scroll_x: int = 0
    scroll_y: int = 0
    cookies: List[Dict[str, Any]] = field(default_factory=list)
    local_storage: Dict[str, str] = field(default_factory=dict)
    session_storage: Dict[str, str] = field(default_factory=dict)
    form_values: Dict[str, Any] = field(default_factory=dict)
    screenshot: Optional[bytes] = None
    screenshot_hash: Optional[str] = None
    tab_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
```

##### 3.1.3 Checkpoint Structure
```python
@dataclass
class Checkpoint:
    id: str
    state: BrowserState
    checkpoint_type: CheckpointType
    task_step: int = 0
    action_name: Optional[str] = None
    action_result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    parent_id: Optional[str] = None
    children_ids: Set[str] = field(default_factory=set)
```

##### 3.1.4 State Restoration
```python
async def restore_checkpoint(
    self,
    page: Any,
    checkpoint_id: str,
) -> bool:
    # Restores URL, scroll position, cookies, storage, form values
```

##### 3.1.5 Persistence
```python
persist_to_disk: bool = True
persistence_dir: str = ".checkpoints"
max_checkpoints: int = 50
```

##### 3.1.6 Checkpoint Chain
```python
# Parent-child relationships for rollback chains
parent_id: Optional[str]
children_ids: Set[str]
```

---

### 3.2 Fallback Strategies

**File:** [`browser_agent/resilience/fallback.py`](browser_agent/resilience/fallback.py)

Error classification and recovery strategies.

#### Features:

##### 3.2.1 Error Classification
```python
class ErrorType(Enum):
    ELEMENT_NOT_FOUND = "element_not_found"
    ACTION_TIMEOUT = "action_timeout"
    NAVIGATION_ERROR = "navigation_error"
    SELECTOR_INVALID = "selector_invalid"
    STATE_MISMATCH = "state_mismatch"
    CAPTCHA_BLOCK = "captcha_block"
    RATE_LIMIT = "rate_limit"
    NETWORK_ERROR = "network_error"
    BROWSER_CRASH = "browser_crash"
    PERMISSION_DENIED = "permission_denied"
    AUTH_REQUIRED = "auth_required"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN = "unknown"
```

##### 3.2.2 Error Context
```python
@dataclass
class ErrorContext:
    error_type: ErrorType
    error_message: str
    error_exception: Optional[Exception] = None
    action_name: Optional[str] = None
    action_params: Dict[str, Any] = field(default_factory=dict)
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    screenshot: Optional[bytes] = None
    timestamp: float = field(default_factory=time.time)
    attempt_count: int = 1
    previous_errors: List[ErrorType] = field(default_factory=list)
```

##### 3.2.3 Fallback Strategies

| Strategy | Priority | Applicable Errors | Description |
|----------|----------|-------------------|-------------|
| `VisualSearchFallback` | 10 | ELEMENT_NOT_FOUND, SELECTOR_INVALID | Uses vision model to find elements |
| `ScrollAndRetryFallback` | 20 | ELEMENT_NOT_FOUND, STATE_MISMATCH | Scrolls page and retries |
| `WaitAndRetryFallback` | 30 | ACTION_TIMEOUT, STATE_MISMATCH | Waits and retries |
| `RefreshPageFallback` | 40 | NETWORK_ERROR, STATE_MISMATCH | Refreshes page |
| `AlternativeSelectorFallback` | 50 | ELEMENT_NOT_FOUND, SELECTOR_INVALID | Tries alternative selectors |
| `CheckpointRestoreFallback` | 60 | BROWSER_CRASH, NAVIGATION_ERROR | Restores from checkpoint |

##### 3.2.4 Strategy Interface
```python
class FallbackStrategy(ABC):
    name: str
    priority: int
    applicable_errors: List[ErrorType]
    max_attempts: int
    
    @abstractmethod
    async def can_handle(self, error_context: ErrorContext) -> bool: ...
    
    @abstractmethod
    async def execute(self, error_context: ErrorContext, page: Any) -> FallbackResult: ...
    
    def get_retry_delay(self, attempt: int) -> float:
        return min(2 ** attempt, 30)  # Exponential backoff, max 30s
```

##### 3.2.5 Fallback Result
```python
@dataclass
class FallbackResult:
    success: bool
    strategy_name: str
    error_context: ErrorContext
    recovery_action: Optional[str] = None
    recovery_params: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    next_strategy_hint: Optional[str] = None
    should_retry: bool = True
    should_abort: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
```

---

### 3.3 Recovery Orchestrator

**File:** [`browser_agent/resilience/recovery.py`](browser_agent/resilience/recovery.py)

Coordinates automatic recovery on failure.

#### Features:

##### 3.3.1 Recovery Status
```python
class RecoveryStatus(Enum):
    SUCCESS = "success"              # Recovery successful
    PARTIAL = "partial"              # Partial recovery
    FAILED = "failed"                # Recovery failed
    ABORTED = "aborted"              # Recovery aborted
    MANUAL_REQUIRED = "manual_required"  # Manual intervention needed
```

##### 3.3.2 Recovery Configuration
```python
@dataclass
class RecoveryConfig:
    max_recovery_attempts: int = 3
    recovery_delay: float = 1.0
    use_checkpoints: bool = True
    use_state_stack: bool = True
    use_fallback_strategies: bool = True
    checkpoint_before_recovery: bool = True
    notify_on_manual_required: Optional[Callable] = None
    on_recovery_success: Optional[Callable] = None
    on_recovery_failure: Optional[Callable] = None
```

##### 3.3.3 Recovery Result
```python
@dataclass
class RecoveryResult:
    status: RecoveryStatus
    error_context: ErrorContext
    recovery_strategy: str
    attempts: int
    restored_state_id: Optional[str] = None
    message: str = ""
    actions_taken: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
```

##### 3.3.4 Recovery Process
1. Create recovery checkpoint
2. Attempt checkpoint restore
3. Execute fallback strategies in priority order
4. Verify recovery success
5. Notify callbacks if manual intervention needed

---

### 3.4 State Stack

**File:** [`browser_agent/resilience/state_stack.py`](browser_agent/resilience/state_stack.py)

Manages browser state history for navigation and rollback.

#### Features:

##### 3.4.1 State Frame
```python
@dataclass
class StateFrame:
    frame_id: str
    state: BrowserState
    action: Optional[str] = None
    action_result: Optional[Dict] = None
    timestamp: float = field(default_factory=time.time)
    parent_id: Optional[str] = None
```

##### 3.4.2 Stack Operations
```python
async def push(self, page: Any, action: str = None) -> StateFrame
async def pop(self) -> Optional[StateFrame]
async def peek(self) -> Optional[StateFrame]
async def rollback(self, frames: int = 1) -> bool
```

##### 3.4.3 Navigation Support
```python
# Supports branching navigation paths
# Can rollback to any point in history
# Maintains parent-child relationships
```

---

## 4. Advanced Capabilities (Phase 4)

### 4.1 Multi-Agent System

**File:** [`browser_agent/agents/`](browser_agent/agents/)

Specialized agents working together.

#### Features:

##### 4.1.1 Agent Types

| Agent | Role | Capabilities |
|-------|------|--------------|
| **SupervisorAgent** | Orchestrates all agents | COORDINATION, PLANNING, RECOVERY |
| **PlannerAgent** | Creates task plans | PLANNING, ANALYSIS |
| **AnalyzerAgent** | Analyzes pages | VISION, ANALYSIS, EXTRACTION |
| **ActorAgent** | Executes actions | BROWSER_CONTROL, ACTION_EXECUTION |
| **ValidatorAgent** | Validates results | VERIFICATION, ANALYSIS |

##### 4.1.2 Agent Capabilities
```python
class AgentCapability(Enum):
    BROWSER_CONTROL = "browser_control"
    VISION = "vision"
    PLANNING = "planning"
    ANALYSIS = "analysis"
    EXTRACTION = "extraction"
    ACTION_EXECUTION = "action_execution"
    VERIFICATION = "verification"
    COORDINATION = "coordination"
    RECOVERY = "recovery"
```

##### 4.1.3 Agent Configuration
```python
@dataclass
class AgentConfig:
    name: str
    capabilities: Set[AgentCapability]
    max_concurrent_tasks: int = 3
    task_timeout: float = 300.0
    retry_count: int = 2
```

##### 4.1.4 Agent Result
```python
@dataclass
class AgentResult:
    success: bool
    agent_id: str
    agent_name: str
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
```

##### 4.1.5 Agent Communication Bus
```python
class AgentCommunicationBus:
    async def send(self, message: AgentMessage) -> None
    async def broadcast(self, message: AgentMessage) -> None
    async def receive(self, agent_id: str) -> Optional[AgentMessage]
    def subscribe(self, agent_id: str, callback: Callable) -> None
```

##### 4.1.6 Message Types
```python
class MessageType(Enum):
    TASK_ASSIGNMENT = "task_assignment"
    TASK_RESULT = "task_result"
    STATUS_UPDATE = "status_update"
    ERROR_REPORT = "error_report"
    RECOVERY_REQUEST = "recovery_request"
    QUERY = "query"
    RESPONSE = "response"

class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3
```

---

### 4.2 Skills System

**File:** [`browser_agent/skills/`](browser_agent/skills/)

Specialized capabilities for specific tasks.

#### Features:

##### 4.2.1 Skill Capabilities
```python
class SkillCapability(Enum):
    # Browser capabilities
    BROWSER_NAVIGATION = "browser_navigation"
    BROWSER_INTERACTION = "browser_interaction"
    BROWSER_SCREENSHOT = "browser_screenshot"
    BROWSER_WAIT = "browser_wait"
    
    # Vision capabilities
    VISION_ELEMENT_DETECTION = "vision_element_detection"
    VISION_TEXT_RECOGNITION = "vision_text_recognition"
    VISION_SCREENSHOT_ANALYSIS = "vision_screenshot_analysis"
    
    # Data capabilities
    DATA_EXTRACTION = "data_extraction"
    DATA_VALIDATION = "data_validation"
    DATA_TRANSFORMATION = "data_transformation"
    
    # Recovery capabilities
    ERROR_RECOVERY = "error_recovery"
    STATE_CHECKPOINT = "state_checkpoint"
    ROLLBACK = "rollback"
    
    # Advanced capabilities
    MULTI_PAGE_NAVIGATION = "multi_page_navigation"
    PAGINATION_HANDLING = "pagination_handling"
    FORM_HANDLING = "form_handling"
    DYNAMIC_CONTENT = "dynamic_content"
```

##### 4.2.2 Available Skills

| Skill | File | Description |
|-------|------|-------------|
| **FormFillingSkill** | [`form_filling.py`](browser_agent/skills/form_filling.py) | Fills web forms intelligently |
| **DataExtractionSkill** | [`data_extraction.py`](browser_agent/skills/data_extraction.py) | Extracts structured data |
| **WebScrapingSkill** | [`web_scraping.py`](browser_agent/skills/web_scraping.py) | Scrapes web content |
| **WorkflowSkill** | [`workflow.py`](browser_agent/skills/workflow.py) | Automates workflows |

##### 4.2.3 Skill Input
```python
@dataclass
class SkillInput:
    task: str
    context: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 300.0
    max_retries: int = 3
    validate_input: bool = True
    verify_results: bool = True
    options: Dict[str, Any] = field(default_factory=dict)
```

##### 4.2.4 Skill Result
```python
@dataclass
class SkillResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    steps_completed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    retries: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    checkpoint_id: Optional[str] = None
```

##### 4.2.5 Skill Registry
```python
class SkillRegistry:
    def register(self, skill: BaseSkill) -> None
    def unregister(self, skill_name: str) -> None
    def get_skill(self, name: str) -> Optional[BaseSkill]
    def get_skills_for_task(self, task: str) -> List[BaseSkill]
    def list_skills(self) -> List[str]
```

---

### 4.3 Task Templates

**File:** [`browser_agent/memory/conversation_memory.py`](browser_agent/memory/conversation_memory.py)

Reusable task templates for common operations.

#### Features:

##### 4.3.1 Template Structure
```python
@dataclass
class TaskTemplate:
    template_id: str
    name: str
    description: str
    goal_pattern: str  # Pattern to match against goals
    steps: List[Dict[str, Any]]  # Sequence of steps
    parameters: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    use_count: int = 0
    success_count: int = 0
    avg_completion_time: float = 0.0
    tags: List[str] = field(default_factory=list)
```

##### 4.3.2 Template Matching
```python
def matches_goal(self, goal: str) -> float:
    """
    Check if template matches a goal.
    Returns match confidence (0-1).
    - Exact match: 1.0
    - Pattern is substring: 0.8
    - Goal is substring: 0.7
    - Word overlap: 0.0-0.5
    """
```

##### 4.3.3 Usage Tracking
```python
def record_use(self, success: bool, completion_time: float):
    """Record template usage for analytics."""
    self.use_count += 1
    if success:
        self.success_count += 1
    # Update rolling average
    self.avg_completion_time = (
        (self.avg_completion_time * (self.use_count - 1) + completion_time) /
        self.use_count
    )
```

---

## 5. Production & Polish (Phase 5)

### 5.1 FastAPI Endpoints

**File:** [`browser_agent/api/`](browser_agent/api/)

REST API for browser automation.

#### Features:

##### 5.1.1 Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/tasks` | Submit a new task |
| `GET` | `/tasks/{task_id}` | Get task status |
| `GET` | `/tasks/{task_id}/result` | Get task result |
| `DELETE` | `/tasks/{task_id}` | Cancel task |
| `GET` | `/tasks` | List all tasks |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Get metrics |
| `GET` | `/skills` | List available skills |
| `POST` | `/sessions` | Create session |
| `GET` | `/sessions/{session_id}` | Get session info |
| `DELETE` | `/sessions/{session_id}` | End session |

##### 5.1.2 Task Request
```python
@dataclass
class TaskRequest:
    goal: str  # Natural language task description
    start_url: Optional[str] = None
    max_steps: int = 20
    timeout: float = 300.0
    options: Dict[str, Any] = field(default_factory=dict)
```

##### 5.1.3 Task Status
```python
class TaskStatusEnum(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class TaskStatus:
    task_id: str
    status: TaskStatusEnum
    progress: float  # 0-100
    current_step: Optional[str] = None
    created_at: datetime
    updated_at: datetime
```

##### 5.1.4 Task Result
```python
@dataclass
class TaskResult:
    task_id: str
    success: bool
    extracted_data: Optional[Dict[str, Any]] = None
    final_url: Optional[str] = None
    execution_time: float = 0.0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
```

##### 5.1.5 CORS Support
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

##### 5.1.6 Error Handling
```python
@dataclass
class ErrorResponse:
    error: str
    message: str
    task_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
```

---

### 5.2 Task Manager

**File:** [`browser_agent/api/task_manager.py`](browser_agent/api/task_manager.py)

Manages task lifecycle and execution.

#### Features:

##### 5.2.1 Task Lifecycle
```
PENDING → RUNNING → COMPLETED
                  ↘ FAILED
                  ↘ CANCELLED
```

##### 5.2.2 Concurrent Execution
```python
max_concurrent_tasks: int = 3
task_timeout: float = 300.0
cleanup_interval: float = 60.0
```

##### 5.2.3 Task Queue
```python
async def submit(self, task: Task) -> str
async def get_status(self, task_id: str) -> Optional[TaskStatus]
async def get_result(self, task_id: str) -> Optional[TaskResult]
async def cancel(self, task_id: str) -> bool
async def list_tasks(self, status: Optional[TaskStatusEnum] = None) -> List[TaskStatus]
```

##### 5.2.4 Callbacks
```python
def on_task_start(self, callback: Callable)
def on_task_complete(self, callback: Callable)
def on_task_error(self, callback: Callable)
```

---

### 5.3 Observability

**File:** [`browser_agent/observability/`](browser_agent/observability/)

Monitoring, logging, and health checks.

#### Features:

##### 5.3.1 Metrics Collection

**File:** [`browser_agent/observability/metrics.py`](browser_agent/observability/metrics.py)

```python
class MetricsCollector:
    # Counter metrics
    tasks_total: Counter
    tasks_completed: Counter
    tasks_failed: Counter
    tasks_cancelled: Counter
    actions_total: Counter
    actions_successful: Counter
    actions_failed: Counter
    
    # Gauge metrics
    active_tasks: Gauge
    queued_tasks: Gauge
    
    # Histogram metrics
    task_duration_seconds: Histogram
    action_duration_seconds: Histogram
```

##### 5.3.2 Metric Types

```python
@dataclass
class Counter:
    name: str
    description: str
    value: float = 0.0
    
    def inc(self, amount: float = 1.0)
    def reset()

@dataclass
class Gauge:
    name: str
    description: str
    value: float = 0.0
    
    def set(self, value: float)
    def inc(self, amount: float = 1.0)
    def dec(self, amount: float = 1.0)

@dataclass
class Histogram:
    name: str
    description: str
    buckets: List[float]
    
    def observe(self, value: float)
    def get_percentile(self, p: float) -> float
```

##### 5.3.3 Logging Configuration

**File:** [`browser_agent/observability/logging_config.py`](browser_agent/observability/logging_config.py)

```python
# Structured logging
log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
log_level: str = "INFO"
log_file: Optional[str] = "logs/browser_agent.log"

# Log rotation
max_bytes: int = 10 * 1024 * 1024  # 10 MB
backup_count: int = 5
```

##### 5.3.4 Health Checks

**File:** [`browser_agent/observability/health.py`](browser_agent/observability/health.py)

```python
@dataclass
class HealthStatus:
    status: str  # "healthy", "degraded", "unhealthy"
    version: str
    uptime_seconds: float
    components: Dict[str, ComponentHealth]
    system: SystemInfo

@dataclass
class ComponentHealth:
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    message: str
    last_check: datetime
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SystemInfo:
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    process_memory_mb: float
```

##### 5.3.5 Time Series Data
```python
# Stores metric history for graphs
_time_series: Dict[str, List[MetricPoint]] = defaultdict(list)
_max_time_series_points: int = 1000
```

---

## 6. Memory System (v0.10.0)

### 6.1 Visual Memory

**File:** [`browser_agent/memory/visual_memory.py`](browser_agent/memory/visual_memory.py)

Advanced visual memory for UI state recognition.

#### Features:

##### 6.1.1 Screenshot Embedding Cache

```python
class ScreenshotEmbeddingCache:
    """
    Cache for screenshot embeddings with perceptual hashing.
    
    Features:
    - LRU eviction policy
    - Perceptual hash for similarity lookup
    - Persistent storage support
    - Embedding compression
    """
    
    max_size: int = 1000
    embedding_dimension: int = 512
    similarity_threshold: float = 0.95
```

##### 6.1.2 Embedding Vector
```python
@dataclass
class EmbeddingVector:
    vector: List[float]
    dimension: int
    timestamp: float
    source_hash: str
    metadata: Dict[str, Any]
    
    def cosine_similarity(self, other: EmbeddingVector) -> float
    def to_bytes(self) -> bytes
    @classmethod
    def from_bytes(cls, data: bytes) -> EmbeddingVector
```

##### 6.1.3 UI State Tracking
```python
@dataclass
class UIState:
    state_id: str
    embedding: EmbeddingVector
    url: str
    title: str
    element_count: int
    interactive_count: int
    screenshot_hash: str
    visit_count: int
    last_visit: float
    actions_taken: List[str]
    outcomes: List[str]
```

##### 6.1.4 Navigation Patterns
```python
@dataclass
class NavigationPattern:
    pattern_id: str
    source_state_id: str
    target_state_id: str
    action_sequence: List[Dict[str, Any]]
    success_count: int
    failure_count: int
    avg_duration: float
    
    @property
    def success_rate(self) -> float
    def record_outcome(self, success: bool, duration: float)
```

##### 6.1.5 Dynamic Element Tracking
```python
@dataclass
class DynamicElement:
    element_id: str
    selector: str
    content_hash: str
    position: Tuple[int, int, int, int]  # x, y, width, height
    element_type: str
    appearance_count: int
    state_associations: List[str]
    position_variations: List[Tuple[int, int, int, int]]
    
    def update_position(self, new_position: Tuple[int, int, int, int])
```

---

### 6.2 Proactive Error Prevention

**File:** [`browser_agent/memory/error_prevention.py`](browser_agent/memory/error_prevention.py)

Detects and prevents errors before they occur.

#### Features:

##### 6.2.1 Risk Levels
```python
class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

##### 6.2.2 Anomaly Types
```python
class AnomalyType(Enum):
    PAGE_LOAD = "page_load"
    ELEMENT_MISSING = "element_missing"
    UNEXPECTED_REDIRECT = "unexpected_redirect"
    POPUP_DETECTED = "popup_detected"
    ERROR_MESSAGE = "error_message"
    SLOW_RESPONSE = "slow_response"
    CONTENT_CHANGE = "content_change"
    BEHAVIOR_DEVIATION = "behavior_deviation"
```

##### 6.2.3 Warning Types
```python
class WarningType(Enum):
    NAVIGATION_RISK = "navigation_risk"
    ACTION_UNSTABLE = "action_unstable"
    STATE_UNFAMILIAR = "state_unfamiliar"
    ELEMENT_AMBIGUOUS = "element_ambiguous"
    FORM_VALIDATION = "form_validation"
    RATE_LIMIT = "rate_limit"
```

##### 6.2.4 Anomaly Detection
```python
class AnomalyDetector:
    """
    Detects anomalies in page behavior.
    
    Features:
    - Baseline learning for normal behavior
    - Statistical anomaly detection
    - Pattern-based detection
    - Threshold-based alerts
    """
    
    def detect_anomalies(self, metrics: Dict[str, float]) -> List[Anomaly]
    def update_baseline(self, metrics: Dict[str, float])
    def set_threshold(self, metric: str, threshold: float)
```

##### 6.2.5 Risk Assessment
```python
@dataclass
class RiskAssessment:
    action_type: str
    overall_risk: RiskLevel
    risk_score: float  # 0-1
    factors: List[Dict[str, Any]]
    recommendations: List[str]
    should_proceed: bool
    timestamp: float

class RiskAssessor:
    def assess_action(self, action: Dict, context: Dict) -> RiskAssessment
```

##### 6.2.6 Behavior Baseline
```python
@dataclass
class BehaviorBaseline:
    metric_name: str
    mean: float
    std_dev: float
    sample_count: int
    min_value: float
    max_value: float
    
    def is_within_normal(self, value: float, z_score_threshold: float = 2.0) -> bool
    def update(self, new_value: float)
```

##### 6.2.7 Suspicious State Recording
```python
@dataclass
class SuspiciousState:
    state_hash: str
    screenshot_path: Optional[str]
    anomalies: List[Anomaly]
    warnings: List[Warning]
    timestamp: float
    reviewed: bool
    notes: str
```

---

### 6.3 Conversation Memory

**File:** [`browser_agent/memory/conversation_memory.py`](browser_agent/memory/conversation_memory.py)

Memory for user interactions and learning.

#### Features:

##### 6.3.1 User Preferences
```python
@dataclass
class UserPreference:
    key: str
    value: Any
    category: str = "general"
    confidence: float = 1.0
    source: str = "explicit"  # explicit, inferred, learned
    created_at: float
    updated_at: float
    usage_count: int
    
    def update(self, new_value: Any, source: str = "explicit")

class UserPreferenceStore:
    """
    Persistent storage for user preferences.
    
    Features:
    - Category-based organization
    - Confidence-weighted values
    - Inferred preferences from behavior
    - Persistent storage
    """
    
    def get(self, key: str, category: str = "general") -> Optional[UserPreference]
    def set(self, key: str, value: Any, category: str = "general", confidence: float = 1.0)
    def infer_preference(self, behavior: Dict[str, Any]) -> Optional[UserPreference]
```

##### 6.3.2 Correction Feedback
```python
@dataclass
class CorrectionFeedback:
    feedback_id: str
    context: Dict[str, Any]  # What was the situation
    original_action: Dict[str, Any]  # What the agent did
    corrected_action: Dict[str, Any]  # What user wanted
    explanation: Optional[str] = None  # User explanation
    timestamp: float
    applied_count: int = 0  # How many times this correction was applied
    success_rate: float = 0.0

class CorrectionLearningEngine:
    """
    Learns from user corrections.
    
    Features:
    - Pattern extraction from corrections
    - Automatic application of learned corrections
    - Success rate tracking
    - Confidence scoring
    """
    
    def record_correction(self, feedback: CorrectionFeedback)
    def find_applicable_correction(self, context: Dict) -> Optional[CorrectionFeedback]
    def apply_correction(self, action: Dict, correction: CorrectionFeedback) -> Dict
```

##### 6.3.3 Session Management
```python
@dataclass
class SessionMessage:
    role: str  # "user", "agent", "system"
    content: str
    timestamp: float
    metadata: Dict[str, Any]

@dataclass
class SessionState:
    session_id: str
    started_at: float
    last_activity: float
    messages: List[SessionMessage]
    context: Dict[str, Any]
    task_history: List[Dict[str, Any]]
    current_goal: Optional[str]
    status: str = "active"  # active, paused, completed
    
    def add_message(self, role: str, content: str, metadata: Dict = None)
    def get_recent_messages(self, count: int = 10) -> List[SessionMessage]
    def get_context_summary(self) -> Dict[str, Any]

class SessionManager:
    def create_session(self) -> SessionState
    def get_session(self, session_id: str) -> Optional[SessionState]
    def end_session(self, session_id: str) -> bool
    def cleanup_expired_sessions(self, max_age: float = 3600)
```

---

## 7. iframe Support (v0.11.0)

### 7.1 Frame Management

**File:** [`browser_agent/browser/controller.py`](browser_agent/browser/controller.py)

#### Features:

##### 7.1.1 Frame Stack
```python
class BrowserController:
    _current_frame: Optional[Frame] = None
    _frame_stack: List[Frame] = []  # Stack for nested iframes
```

##### 7.1.2 Frame Switching
```python
async def switch_to_frame(self, selector: str) -> bool:
    """
    Switch to an iframe by selector.
    
    Args:
        selector: CSS selector for the iframe
        
    Returns:
        True if switch successful
    """
    # Push current frame to stack
    if self._current_frame:
        self._frame_stack.append(self._current_frame)
    
    # Get iframe element and content frame
    frame = await self._current_page.query_selector(selector)
    self._current_frame = await frame.content_frame()
```

##### 7.1.3 Frame Exit
```python
async def exit_frame(self) -> bool:
    """
    Exit current iframe, return to parent.
    
    Returns:
        True if exit successful
    """
    if self._frame_stack:
        self._current_frame = self._frame_stack.pop()
        return True
    else:
        self._current_frame = None
        return False
```

##### 7.1.4 Nested iframe Support
```python
# Supports arbitrary nesting depth
# frame_stack maintains navigation history
# Actions work transparently within frames
```

##### 7.1.5 Frame-Aware Actions
```python
async def _click(self, context: ActionContext, selector: str, ...):
    # Uses current frame if set, otherwise main page
    target = context.browser._current_frame or context.page
    await target.click(selector)
```

---

## 8. Testing Infrastructure (v0.12.0)

### 8.1 Integration Tests

**File:** [`tests/test_integration_use_cases.py`](tests/test_integration_use_cases.py)

UI-TARS vision model integration tests.

#### Features:

##### 8.1.1 Test Classes

| Use Case | Test Class | Tests |
|----------|-----------|-------|
| Form Filling | `TestFormFillingVision` | 2 |
| Data Extraction | `TestDataExtractionVision` | 2 |
| Web Scraping | `TestWebScrapingVision` | 2 |
| Search & Research | `TestSearchResearchVision` | 2 |
| Workflow Automation | `TestWorkflowAutomationVision` | 2 |
| E-commerce | `TestEcommerceVision` | 2 |
| UI Testing | `TestUITestingVision` | 7 |

##### 8.1.2 Vision Test Result
```python
@dataclass
class VisionTestResult:
    test_name: str
    use_case: str
    success: bool
    confidence: float
    action_executed: str
    expected_outcome: str
    actual_outcome: str
    screenshot_before: Optional[bytes]
    screenshot_after: Optional[bytes]
    execution_time: float
    error: Optional[str] = None
```

##### 8.1.3 Test Base Class
```python
class VisionTestBase:
    @pytest.fixture
    async def vision_client(self):
        """Create vision client for testing."""
        
    @pytest.fixture
    async def test_server(self):
        """Start local test page server."""
        
    async def _run_vision_test(
        self,
        test_name: str,
        page_url: str,
        instruction: str,
        expected_outcome: str,
    ) -> VisionTestResult:
        """Run a single vision test."""
```

##### 8.1.4 Running Tests
```bash
# Run all unit tests
pytest tests/ -v

# Run integration tests with UI-TARS
pytest tests/test_integration_use_cases.py -v --run-integration

# Run specific use case tests
pytest tests/test_integration_use_cases.py::TestFormFillingVision -v --run-integration
```

---

### 8.2 Test Pages

**Directory:** [`test_pages/`](test_pages/)

Local test pages for integration testing.

#### Features:

##### 8.2.1 Available Test Pages

| Use Case | Directory | Files |
|----------|-----------|-------|
| Form Filling | `test_pages/form_filling/` | `index.html`, `validation_script.js`, `expected_outcomes.md` |
| Data Extraction | `test_pages/data_extraction/` | `index.html`, `products.json`, `expected_outcomes.md` |
| Web Scraping | `test_pages/web_scraping/` | `index.html`, `expected_outcomes.md` |
| Search & Research | `test_pages/search_research/` | `index.html`, `article.html`, `expected_outcomes.md` |
| Workflow Automation | `test_pages/workflow_automation/` | `login.html`, `dashboard.html`, `expected_outcomes.md` |
| E-commerce | `test_pages/ecommerce/` | `index.html`, `cart.html`, `checkout.html`, `expected_outcomes.md` |
| UI Testing | `test_pages/ui_testing/` | `index.html`, `expected_outcomes.md` |

##### 8.2.2 Test Page Server
```python
# test_pages/server.py
python test_pages/server.py --port 8765

# Serves all test pages at http://localhost:8765/
```

##### 8.2.3 Expected Outcomes
Each test page has an `expected_outcomes.md` file documenting:
- Test scenarios
- Expected outcomes
- Validation criteria
- Success thresholds

---

### 8.3 UI Testing Test Page

**File:** [`test_pages/ui_testing/index.html`](test_pages/ui_testing/index.html)

Comprehensive UI component testing page.

#### Features:

##### 8.3.1 Button Tests
- Primary, secondary, success, danger, warning buttons
- Disabled button state
- Click counter for verification

##### 8.3.2 Form Validation Tests
- Email validation
- Password validation
- Phone validation
- Real-time error messages

##### 8.3.3 Visibility Tests
- Visible elements
- Hidden elements (`display: none`)
- Invisible elements (`visibility: hidden`)

##### 8.3.4 State Tests
- Loading indicator with spinner
- State transitions

##### 8.3.5 Toggle Switch Tests
- ON/OFF toggle switches
- Status display

##### 8.3.6 Accordion Tests
- Expand/collapse sections
- Multi-section support

##### 8.3.7 Modal Dialog Tests
- Open/close modal
- Confirm/cancel actions
- Overlay behavior

##### 8.3.8 Tabs Navigation Tests
- Tab switching
- Content display per tab

##### 8.3.9 Progress Bar Tests
- Animated progress bar
- Start/reset controls

##### 8.3.10 Drag and Drop Tests
- Draggable items
- Drop zones
- Item transfer

##### 8.3.11 Animation Tests
- Pulsing animation
- Motion detection

##### 8.3.12 Tooltip Tests
- Hover tooltips
- Position variations

##### 8.3.13 Assertion Area Tests
- Success state
- Error state
- Reset functionality

##### 8.3.14 Responsive Grid Tests
- 4-column responsive grid
- Resize behavior

---

## Summary Statistics

| Category | Count |
|----------|-------|
| **Total Python Files** | 32 |
| **Total Test Files** | 14 |
| **Action Types** | 28 |
| **Agent Types** | 5 |
| **Skills** | 4 |
| **Fallback Strategies** | 6 |
| **API Endpoints** | 11 |
| **Test Pages** | 7 |
| **UI Test Components** | 15 |

---

## Version History

| Version | Description |
|---------|-------------|
| v0.1.0 | Core Foundation - Browser, LLM, Actions |
| v0.2.0 | Visual Intelligence - Vision analysis, caching |
| v0.3.0 | Resilience - Checkpoints, fallbacks, recovery |
| v0.4.0 | Advanced - Multi-agent, skills |
| v0.5.0 | Production - FastAPI, observability |
| v0.10.0 | Memory System - Visual memory, error prevention, conversation |
| v0.11.0 | iframe Support - Frame management |
| v0.12.0 | Testing - Integration tests, test pages |

---

*Last updated: 2026-03-26*

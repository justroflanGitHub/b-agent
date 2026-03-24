# Changelog

All notable changes to the Browser Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Version Tracking:**
- **Major (1.x.x)**: Significant new features, architectural changes, or breaking changes
- **Minor (x.1.x)**: New features, enhancements, or moderate changes
- **Patch (x.x.1)**: Bug fixes, small improvements, or minor changes

---

## [Unreleased]

### Added
- Nothing yet

---

## [0.4.0] - 2026-03-24

### Added - Phase 2: Visual Intelligence (Major Feature)

#### Visual Analyzer Module (`browser_agent/vision/`)
- **[0.4.0.1]** BoundingBox dataclass with geometric operations
  - `center` property for center coordinates
  - `area` property for bounding box area
  - `contains(x, y)` method for point containment
  - `overlaps(other)` method for overlap detection
  - `to_dict()` serialization method

- **[0.4.0.2]** ElementInfo dataclass for detected elements
  - Bounding box, element type, description
  - Visibility and interactivity flags
  - Clickable/typeable attributes
  - Confidence scoring

- **[0.4.0.3]** PageState enum for page classification
  - LOADING, READY, ERROR, MODAL
  - LOGIN_REQUIRED, CAPTCHA, RATE_LIMITED
  - NOT_FOUND, REDIRECTING

- **[0.4.0.4]** ElementType enum for element classification
  - Input types: INPUT_TEXT, INPUT_PASSWORD, INPUT_EMAIL, INPUT_SEARCH
  - Interactive: BUTTON, LINK, CHECKBOX, RADIO, SELECT
  - Content: TEXT, HEADING, PARAGRAPH, IMAGE
  - Structural: FORM, NAVIGATION, HEADER, FOOTER, SIDEBAR
  - Overlay: MODAL, POPUP, ADVERTISEMENT

- **[0.4.0.5]** VisualAnalyzer class
  - `analyze_page()` - Complete page analysis
  - `_analyze_page_state()` - Page state determination
  - `_detect_elements()` - Multi-element detection
  - `_generate_summary()` - Page summary generation
  - `_generate_recommendations()` - Action recommendations
  - `find_element()` - Find specific element by description
  - `find_all_elements()` - Find all matching elements
  - Built-in result caching with configurable TTL

#### Visual Diff Module (`browser_agent/vision/diff.py`)
- **[0.4.0.6]** VisualDiff class for screenshot comparison
  - Pixel-wise comparison (with PIL)
  - Hash-based comparison (fallback without PIL)
  - Change region detection
  - Similarity scoring
  - Diff image generation with red highlighting
  - `quick_compare()` for fast similarity check
  - `get_similarity_score()` for 0.0-1.0 score

#### Vision Cache Module (`browser_agent/vision/cache.py`)
- **[0.4.0.7]** VisionCache class for result caching
  - LRU cache with configurable max size
  - TTL-based expiration
  - Screenshot hash-based lookup
  - `get_or_compute()` for automatic caching
  - `async_get_or_compute()` for async operations
  - Cache statistics (hits, misses, hit rate)
  - Invalidation by screenshot or operation

#### Visual Actions (`browser_agent/actor/actions.py`)
- **[0.4.0.8]** New visual action types
  - `ActionType.HOVER_VISUAL` - Hover by visual description
  - `ActionType.TYPE_VISUAL` - Click and type by visual description

- **[0.4.0.9]** Visual action handlers
  - `_hover_visual()` - Uses vision client to find coordinates
  - `_type_visual()` - Clicks on input and types text

#### Tests (`tests/test_vision.py`)
- **[0.4.0.10]** Comprehensive test suite for Phase 2 (36 tests)
  - BoundingBox tests (6 tests)
  - ElementInfo tests (2 tests)
  - PageState/ElementType tests (2 tests)
  - VisualAnalyzer tests (9 tests)
  - VisualDiff tests (4 tests)
  - VisionCache tests (10 tests)
  - Visual action types tests (2 tests)
  - Integration tests (2 tests)

### Changed
- **[0.4.0.11]** Total tests: 142 passed, 14 skipped (was 107 passed)
- **[0.4.0.12]** Updated requirements.txt with optional PIL dependency

---

## [0.3.0] - 2026-03-22

### Added - Step Validation System (Major Feature)
- **[0.3.0.1]** Added comprehensive action validation after each step
  - Takes screenshot after each action to verify success
  - Validates click actions by checking focused element state
  - Validates type actions by checking input field content
  - Validates press_enter by checking URL navigation to search results
  - Validates task completion by checking page URL and search result elements
- **[0.3.0.2]** Added consecutive failure tracking
  - Stops execution after 3 consecutive failures
  - Prevents infinite loops on persistent errors
- **[0.3.0.3]** Added detailed validation logging
  - Each step now includes validation result with reason
  - Logs show ✅ for validated actions, ⚠️ for validation failures
- **[0.3.0.4]** Added multiple validation methods:
  - `_validate_action_success()` - Main validation dispatcher
  - `_validate_task_completion()` - Checks search results page
  - `_validate_click_action()` - Checks focused element after click
  - `_validate_type_action()` - Checks text in input field
  - `_validate_enter_action()` - Checks navigation after Enter key

### Changed - Stricter Validation (v0.3.1)
- **[0.3.1.1]** Stricter click validation for search tasks
  - Clicks on input fields now FAIL if no input is focused after click
  - Added keyword detection for input-related clicks
  - Added vision-based fallback validation for non-input clicks
- **[0.3.1.2]** Stricter type validation
  - Type action now FAILS if no input field is focused
  - Better error messages showing expected vs actual input values
  - Added support for contenteditable elements
- **[0.3.1.3]** Enhanced logging
  - Shows focused element info after click
  - Shows input element info after type

### Changed - Vision Model Coordinate Accuracy (v0.3.2)
- **[0.3.2.1]** Improved vision prompt for coordinate accuracy
  - Added explicit coordinate guidance for 2560x1440 screens
  - Center X is around 1280 (not 700-800)
  - Google search bar typically at Y: 350-450, X: 900-1700
  - Added instruction to count pixels from top-left corner
  - Emphasized looking at actual element positions, not guessing

### Fixed - Critical Validation Bug (v0.3.3)
- **[0.3.3.1]** Fixed click validation bug that always passed
  - Bug: `el_type in ["text", "search", "email", ""]` - empty string was always in list!
  - This caused body element (with no type) to pass validation as "input focused"
  - Fix: Only accept actual `input` or `textarea` tags as valid input focus
  - Added separate check for contenteditable elements (excluding body/html)

### Added - Action Retry Logic (v0.3.4)
- **[0.3.4.1]** Added per-action retry logic
  - Each action now retries up to 3 times on validation failure
  - Takes fresh screenshot and gets new action from vision model on each retry
  - Logs retry attempts: `🔄 Retrying action 'click' (attempt 2/3)`
- **[0.3.4.2]** Better failure handling
  - Actions that fail after all retries are marked as failed
  - Consecutive failure tracking still stops execution after 3 total failures

### Changed - Improved Vision Prompt (v0.3.5)
- **[0.3.5.1]** More explicit Y-coordinate guidance for Google search
  - Added "UPPER THIRD of the screen" emphasis
  - Explicitly warned "NOT 700-800!" for Y coordinates
  - Added visual reference: search bar is below Google logo, ~1/3 from top
  - Added specific example: x=1280, y=400 for 2560x1440 screen

### Fixed - Retry Logic (v0.3.6)
- **[0.3.6.1]** Removed per-action retry to prevent excessive attempts
  - Changed `max_action_retries` from 3 to 1
  - Each action now gets one attempt, then moves to next step
  - Total attempts now limited by `max_consecutive_failures=3` only
  - Updated log messages to show consecutive failure count

### Refactored - Tool-Calling Architecture (v0.3.8)
- **[0.3.8.1]** Removed `_click_visual()` and `_type_visual()` from actions.py
  - These methods had duplicate coordinate logic
  - Coordinate calculation moved to dedicated tool
- **[0.3.8.2]** Added `VisionClient.get_click_coordinates()` tool
  - Dedicated prompt for precise coordinate detection
  - Separate from main action planning prompt
  - Returns x, y, confidence, element_found
- **[0.3.8.3]** Updated agent.py to use coordinate tool
  - Calls `vision_client.get_click_coordinates()` for click actions
  - Falls back to original coordinates if confidence < 0.5
  - Logs final click coordinates with confidence

### Fixed - Action Transition (v0.3.7)
- **[0.3.7.1]** Programmatic action transition enforcement
  - If vision model returns same action type after success, force transition
  - click → type: Extract search query from goal and auto-set text
  - Prevents infinite clicking loop
- **[0.3.7.2]** Improved vision prompt with stricter action rules
  - Added "STRICT SEQUENCE" and "MANDATORY ACTION TRANSITIONS" sections
  - Explicit instruction to check recent actions before deciding next action

---

## [0.2.10] - 2026-03-21

### Changed - Vision Model Improvements
- **[0.2.10.1]** Enhanced vision model prompt with action history context
  - Tracks last 5 actions to prevent repetition
  - Includes success/failure status of previous actions
  - Provides explicit workflow guidance for search tasks
- **[0.2.10.2]** Added critical rules to prevent action loops
  - "If previous action was click on input, NEXT action should be type"
  - "If previous action was type, NEXT action should be press_enter"
  - Detect focused input fields and use type instead of click
- **[0.2.10.3]** Updated test to account for y-coordinate offset (-92)
  - User modification for browser chrome offset

---

## [0.2.9] - 2026-03-20

### Changed - User Experience Improvements
- **[0.2.9.1]** Updated default viewport resolution to 2560x1440 (user's screen resolution)
  - Updated `browser_agent/config.py` BrowserConfig defaults
  - Updated `config.yaml` viewport settings
  - Updated all test files to use config-based viewport dimensions
- **[0.2.9.2]** Added click coordinates logging for all click actions
  - Logs show exact (x, y) coordinates when clicking
  - Element clicks log the center coordinates of the element
  - Visual clicks log coordinates with description
- **[0.2.9.3]** Enhanced visual click prompt for Google.com
  - Added detailed layout context explaining Google search bar position
  - Search bar is centered both horizontally and vertically
  - Dynamic coordinate hints based on viewport dimensions
  - For 2560x1440: x=1280, y=520-620 (slightly above vertical center)
- **[0.2.9.4]** Fixed browser window positioning
  - Window now opens at position (0,0) with correct size
  - Uses `--window-size` and `--window-position` Chrome flags
  - Viewport is ALWAYS set in context for accurate coordinate mapping
- **[0.2.9.5]** Fixed UTF-8 encoding for Windows console
  - Added `sys.stdout.reconfigure(encoding='utf-8')` for emoji support
  - Fixed UnicodeEncodeError when printing emojis on Windows

---

## [0.2.0] - 2026-03-20

### Added - Modular Architecture (Phase 1 Complete)

#### Project Structure
- **[0.2.1]** New modular package structure (`browser_agent/`)
  - `browser/` - Browser controller module
  - `llm/` - LLM/Vision client module
  - `actor/` - Action execution module
  - `state/` - State management (planned)
  - `skills/` - Skill system (planned)
  - `agents/` - Multi-agent coordination (planned)

#### Configuration System
- **[0.2.2]** Comprehensive configuration management
  - YAML configuration file support (`config.yaml`)
  - Environment variable overrides
  - Dataclass-based configuration classes
  - BrowserConfig, LLMConfig, ResilienceConfig, ActionConfig, LoggingConfig
  - Configuration validation and defaults

#### Browser Controller
- **[0.2.3]** Complete browser controller rewrite
  - Async context manager support (`async with`)
  - Multi-page/tab management
  - Browser state snapshots
  - Enhanced anti-detection JavaScript injection
  - Realistic HTTP headers configuration
  - Human-like behavior simulation
  - Firefox and WebKit browser support (in addition to Chromium)

#### LLM Client
- **[0.2.4]** OpenAI-compatible LLM client
  - Async chat completions
  - Streaming response support
  - Vision model integration (screenshots)
  - Exponential backoff retry logic
  - Request statistics tracking
  - VisionClient subclass for UI-TARS integration

#### Action System
- **[0.2.5]** Complete ActionExecutor with 25+ actions
  - Navigation: navigate, go_back, go_forward, refresh
  - Mouse: click, double_click, right_click, hover, drag_and_drop
  - Input: type_text, clear_input, select_option, check, uncheck
  - Scroll: scroll_up, scroll_down, scroll_to, scroll_to_element
  - Content: extract_text, extract_html, get_page_info, take_screenshot
  - Advanced: wait, wait_for_element, wait_for_navigation, press_key, handle_dialog
  - Vision-guided: click_visual, type_visual
  - Retry logic with exponential backoff
  - Action history tracking

#### Main Agent
- **[0.2.6]** BrowserAgent orchestrator class
  - Component initialization and cleanup
  - Vision-guided task execution
  - Convenience methods for common actions
  - Statistics and monitoring

#### CLI & Testing
- **[0.2.7]** Command-line interface (`run_agent.py`)
  - Task execution from command line
  - Interactive mode for multiple tasks
  - Configuration file support
  - Verbose logging option

- **[0.2.8]** Comprehensive test suite
  - `tests/test_config.py` - Configuration tests (19 tests)
  - `tests/test_llm_client.py` - LLM client tests (22 tests)
  - `tests/test_actor_actions.py` - Action executor tests (37 tests)
  - `tests/test_browser_controller.py` - Browser controller tests (20 tests)
  - `tests/test_agent.py` - Agent integration tests (17 tests)
  - **Total: 107 tests passed, 14 skipped**

#### Requirements
- **[0.2.9]** Updated dependencies (`requirements.txt`)
  - playwright>=1.40.0
  - aiohttp>=3.9.0
  - pyyaml>=6.0
  - pydantic>=2.0.0
  - tenacity>=8.2.0
  - pillow>=10.0.0
  - fastapi>=0.109.0 (optional)

---

## [0.1.0] - 2026-03-20

### Added - Core Foundation (Phase 1)

#### Browser Controller
- **[0.1.1]** Initial Playwright browser controller implementation
  - Async browser initialization with `async_playwright`
  - Chromium browser launch with configurable options
  - Headless/headful mode toggle via `BROWSER_HEADLESS` environment variable
  - Browser context and page management
  - 1920x1080 viewport configuration

#### Anti-Detection & Stealth Measures
- **[0.1.2]** Comprehensive anti-detection script injection
  - `navigator.webdriver` property removal
  - Mock `navigator.plugins` array with realistic Chrome plugins
  - Mock `navigator.languages` array (en-US, en)
  - Mock `navigator.permissions.query` for notifications
  - Mock `screen.availHeight` and `screen.availWidth` properties
  - Mock `navigator.getBattery` API with charging state
- **[0.1.3]** Realistic HTTP headers configuration
  - Accept, Accept-Encoding, Accept-Language headers
  - Sec-CH-UA headers for Chrome 120 impersonation
  - Sec-Fetch-* headers for realistic requests
- **[0.1.4]** Human-like behavior simulation
  - Random mouse movements before interactions
  - Random scroll behavior to simulate reading
  - Random delays and timing variations

#### LM Studio Integration
- **[0.2.1]** OpenAI-compatible API client for LM Studio
  - Chat completions endpoint integration
  - Configurable LM Studio URL via `LM_STUDIO_URL` environment variable
  - Vision model support with base64 image encoding
  - JSON response parsing with error handling

#### Vision-Guided Actions
- **[0.2.2]** UI-TARS 1.5 vision model integration
  - Screenshot capture and encoding for vision analysis
  - Natural language action instruction generation
  - Coordinate extraction from vision responses
- **[0.2.3]** Vision-guided action execution
  - Click at vision-predicted coordinates
  - Type text into focused input fields
  - Press Enter key for form submission

#### Actor Actions (Basic)
- **[0.1.5]** Basic action implementations
  - `click` - Mouse click at coordinates with offset correction
  - `type_text` - Keyboard text input
  - `press_enter` - Enter key press

#### Task Execution
- **[0.3.1]** Main task execution flow
  - `execute_task()` method with goal and URL parameters
  - Task status tracking and result reporting
  - Execution time measurement
- **[0.3.2]** Retry logic with `_execute_with_retry()`
  - Configurable max retries (default: 3)
  - Automatic page navigation retry on failure
  - Separate retry handling for search and extraction phases

#### Search & Extraction
- **[0.3.3]** Google search automation
  - Navigate to Google and perform search
  - Vision-based search input field detection
  - Search query entry and submission
- **[0.3.4]** Search result validation
  - URL validation for search results page
  - DOM element detection for search results
  - Page title verification
- **[0.3.5]** Information extraction from results
  - Vision-based relevant result selection
  - Click navigation to content pages
  - Content extraction and summarization
  - Key points extraction from pages

#### CLI Interface
- **[0.1.6]** Interactive test mode
  - Command-line argument parsing (`test` command)
  - Interactive goal input
  - Persistent browser mode for observation

#### API
- **[0.4.1]** Basic FastAPI structure (simple_browser_api.py)
  - Async task execution endpoint
  - Task status reporting

#### Docker
- **[0.5.1]** Docker containerization
  - Dockerfile with Python and Playwright
  - docker-compose.yml configuration
  - Entrypoint script with environment setup
  - Volume management for data and logs

#### Documentation
- **[0.6.1]** README-SIMPLE-BROWSER-AGENT.md
  - Usage instructions
  - Configuration guide
  - Example commands
- **[0.6.2]** Docker README
  - Docker setup instructions
  - Environment variables
  - Volume configuration

#### Logging
- **[0.1.7]** Structured logging setup
  - Python logging module configuration
  - Timestamp, logger name, level, message format
  - Console output with INFO level

---

## Version History Summary

| Version | Date | Type | Description |
|---------|------|------|-------------|
| 0.1.1 | 2026-03-20 | Patch | Browser controller initialization |
| 0.1.2 | 2026-03-20 | Patch | Anti-detection script injection |
| 0.1.3 | 2026-03-20 | Patch | HTTP headers configuration |
| 0.1.4 | 2026-03-20 | Patch | Human-like behavior simulation |
| 0.1.5 | 2026-03-20 | Patch | Basic actor actions |
| 0.1.6 | 2026-03-20 | Patch | CLI interactive mode |
| 0.1.7 | 2026-03-20 | Patch | Logging setup |
| 0.2.1 | 2026-03-20 | Minor | LM Studio API client |
| 0.2.2 | 2026-03-20 | Minor | UI-TARS vision integration |
| 0.2.3 | 2026-03-20 | Patch | Vision-guided action execution |
| 0.3.1 | 2026-03-20 | Minor | Task execution flow |
| 0.3.2 | 2026-03-20 | Patch | Retry logic |
| 0.3.3 | 2026-03-20 | Minor | Google search automation |
| 0.3.4 | 2026-03-20 | Patch | Search result validation |
| 0.3.5 | 2026-03-20 | Minor | Information extraction |
| 0.4.1 | 2026-03-20 | Minor | Basic API structure |
| 0.5.1 | 2026-03-20 | Minor | Docker containerization |
| 0.6.1 | 2026-03-20 | Minor | Simple browser agent README |
| 0.6.2 | 2026-03-20 | Patch | Docker README |

---

## Upcoming Features (Planned)

### Phase 2: Visual Intelligence
- Enhanced UI-TARS integration with bounding boxes
- Page state determination (loading, ready, error, modal)
- Element detection with visibility/interactivity assessment
- Visual diff for before/after comparison

### Phase 3: Resilience & Recovery
- Checkpoint system for state snapshots
- Error classification and fallback strategies
- State stack for rollback operations
- Automatic recovery orchestration

### Phase 4: Advanced Capabilities
- Skill system (forms, extraction, scraping, workflows)
- Multi-agent coordination with supervisor pattern
- Conversation memory and learning

### Phase 5: Production & Polish
- Complete FastAPI endpoints with streaming
- Web dashboard for visual task tracking
- Structured logging with correlation IDs
- Metrics collection and health checks
- Configuration management system

---

## Contributing

When adding entries to this changelog:
1. Add entries under `[Unreleased]` section
2. Use the appropriate category: Added, Changed, Fixed, Deprecated, Removed, Security
3. Include version tag: **[X.Y.Z]** at the start of the entry
4. Follow semantic versioning for version bumps
5. Move entries to a versioned section upon release

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
- Phase 5: Production & Polish (in progress)

---

## [0.8.0] - 2026-03-26

### Added - Phase 4.5: Localhost Test Pages for Use Cases

#### Form Filling Test Page (`test_pages/form_filling/`)
- **[0.8.0.1]** `index.html` - Contact form with various input types:
  - Text inputs (name, email)
  - Textarea (message)
  - Dropdown/select (subject)
  - Checkboxes (preferences)
  - Radio buttons (contact method)
  - Password field, date picker, range slider
  - Submit button with validation
- **[0.8.0.2]** `validation_script.js` - Client-side validation with error handling
- **[0.8.0.3]** `expected_outcomes.md` - Agent behavior documentation

#### Data Extraction Test Page (`test_pages/data_extraction/`)
- **[0.8.0.4]** `index.html` - Product catalog with 12 products:
  - Product cards with name, price, description
  - Star ratings (visual and numeric)
  - Availability status (In Stock, Low Stock, Out of Stock)
  - Sale badges and pricing
- **[0.8.0.5]** `products.json` - Reference data for validation
- **[0.8.0.6]** `expected_outcomes.md` - Extraction behavior documentation

#### Web Scraping Test Page (`test_pages/web_scraping/`)
- **[0.8.0.7]** `index.html` - Blog listing with:
  - 15 blog posts with title, excerpt, date, author
  - Pagination controls (3 pages)
  - Category filters (Technology, Design, Business, Tutorials)
  - Load more button functionality
- **[0.8.0.8]** `expected_outcomes.md` - Scraping behavior documentation

#### Search & Research Test Page (`test_pages/search_research/`)
- **[0.8.0.9]** `index.html` - Mock search engine with:
  - Search input with suggestions
  - 10 search results with titles, snippets, URLs
  - Knowledge panel
  - Related searches
- **[0.8.0.10]** `article.html` - Article detail page with full content
- **[0.8.0.11]** `expected_outcomes.md` - Search behavior documentation

#### Workflow Automation Test Page (`test_pages/workflow_automation/`)
- **[0.8.0.12]** `login.html` - Login page with:
  - Username/password fields
  - Remember me checkbox
  - Client-side validation
  - Multiple valid credentials (admin/admin123, demo/demo, etc.)
- **[0.8.0.13]** `dashboard.html` - Dashboard with:
  - Welcome message
  - Navigation menu
  - Download report button
  - Action items with checkboxes
  - Modal dialogs
- **[0.8.0.14]** `expected_outcomes.md` - Workflow behavior documentation

#### E-commerce Interaction Test Page (`test_pages/ecommerce/`)
- **[0.8.0.15]** `index.html` - Product catalog with:
  - 12 products with images, prices, ratings
  - Add to cart functionality
  - Quantity selectors
  - Cart persistence (localStorage)
- **[0.8.0.16]** `cart.html` - Shopping cart with:
  - Cart items list
  - Quantity update/remove functionality
  - Price calculations
  - Checkout button
- **[0.8.0.17]** `checkout.html` - Checkout form with:
  - Shipping address fields
  - Payment method selection
  - Order summary
  - Place order functionality
- **[0.8.0.18]** `expected_outcomes.md` - E-commerce behavior documentation

#### Test Server Infrastructure
- **[0.8.0.19]** `test_pages/server.py` - Python HTTP server with:
  - CORS support (Access-Control-Allow-Origin: *)
  - No caching headers
  - Custom port support (default 8080)
- **[0.8.0.20]** `test_pages/README.md` - Comprehensive documentation for all test pages

### Testing
- JavaScript testing helpers on all pages (window.fillForm, window.addToCart, etc.)
- Custom events for testing (formSubmitted, itemAddedToCart, orderPlaced, etc.)
- localStorage/sessionStorage for state persistence

---

## [0.7.0] - 2026-03-25

### Added - Phase 4.6: Multi-Agent Coordination System

#### Base Agent System (`browser_agent/agents/base.py`)
- **[0.7.0.1]** `AgentStatus` enum for agent states (idle, busy, error, offline)
- **[0.7.0.2]** `AgentCapability` enum for agent capabilities
  - PLANNING, ANALYSIS, ACTION_EXECUTION, VALIDATION
  - VISUAL_PROCESSING, FORM_HANDLING, DATA_EXTRACTION
  - NAVIGATION, RECOVERY, COORDINATION
- **[0.7.0.3]** `AgentConfig` dataclass for agent configuration
- **[0.7.0.4]** `AgentResult` dataclass for execution results
- **[0.7.0.5]** `AgentState` class for runtime state tracking
- **[0.7.0.6]** `BaseAgent` abstract class with:
  - Status tracking and management
  - Task execution with tracking
  - Message handling
  - Statistics collection

#### Communication System (`browser_agent/agents/communication.py`)
- **[0.7.0.7]** `MessageType` enum for message types
  - Task-related: TASK_ASSIGNMENT, TASK_RESULT, TASK_STATUS, TASK_CANCEL
  - Coordination: STATUS_UPDATE, HEARTBEAT, SYNC_REQUEST, SYNC_RESPONSE
  - Data sharing: DATA_SHARE, QUERY, QUERY_RESPONSE
  - Control: REGISTER, UNREGISTER, CONFIG_UPDATE
  - Error: ERROR, WARNING
  - Collaboration: HELP_REQUEST, HELP_RESPONSE, DELEGATION
- **[0.7.0.8]** `MessagePriority` enum (LOW, NORMAL, HIGH, URGENT)
- **[0.7.0.9]** `AgentMessage` dataclass for inter-agent messaging
- **[0.7.0.10]** `AgentCommunicationBus` class with:
  - Point-to-point messaging
  - Broadcast messaging
  - Subscribe/publish pattern
  - Message queuing
  - Message history

#### Planner Agent (`browser_agent/agents/planner.py`)
- **[0.7.0.11]** `StepStatus` enum (pending, ready, running, completed, failed, skipped)
- **[0.7.0.12]** `StepType` enum (navigate, click, type, extract, wait, scroll, validate, condition, loop, subtask)
- **[0.7.0.13]** `StepDependency` class for step dependencies
- **[0.7.0.14]** `PlanStep` dataclass for plan step definitions
- **[0.7.0.15]** `TaskPlan` dataclass for execution plans
- **[0.7.0.16]** `PlanningRequest` dataclass for planning requests
- **[0.7.0.17]** `PlannerAgent` class with:
  - Task decomposition
  - Plan template creation
  - Plan adaptation on failure
  - Pattern-based planning (form filling, search, navigation, extraction)

#### Analyzer Agent (`browser_agent/agents/analyzer.py`)
- **[0.7.0.18]** `AnalysisType` enum (full_page, element_detection, form_analysis, content_extraction, state_check)
- **[0.7.0.19]** `PageState` enum (loading, ready, error, modal_open, form_submitting, navigating, interactive)
- **[0.7.0.20]** `ElementInfo` dataclass for detected elements
- **[0.7.0.21]** `FormField` dataclass for form field info
- **[0.7.0.22]** `AnalysisResult` dataclass for analysis results
- **[0.7.0.23]** `AnalysisRequest` dataclass for analysis requests
- **[0.7.0.24]** `AnalyzerAgent` class with:
  - Full page analysis
  - Element detection (visual and DOM-based)
  - Form analysis
  - State checking
  - Element classification

#### Actor Agent (`browser_agent/agents/actor.py`)
- **[0.7.0.25]** `ActionType` enum for action types
  - Click, double_click, right_click, hover
  - Type, press_key, scroll
  - Navigate, go_back, go_forward, refresh
  - Wait, select, check, uncheck
  - Upload, drag, screenshot, extract
- **[0.7.0.26]** `ActionRequest` dataclass for action requests
- **[0.7.0.27]** `ActionResult` dataclass for action results
- **[0.7.0.28]** `ActorAgent` class with:
  - All browser actions with retry logic
  - Screenshot capture before/after
  - Convenience methods (click, type_text, navigate, scroll, wait_for_element)

#### Validator Agent (`browser_agent/agents/validator.py`)
- **[0.7.0.29]** `ValidationType` enum (success_check, element_present/absent, text_present/absent, url_match/contains, value_check, state_check, custom)
- **[0.7.0.30]** `ValidationSeverity` enum (info, warning, error, critical)
- **[0.7.0.31]** `ValidationCriteria` dataclass for validation criteria
- **[0.7.0.32]** `ValidationFailure` dataclass for failure details
- **[0.7.0.33]** `ValidationResult` dataclass for validation results
- **[0.7.0.34]** `ValidationRequest` dataclass for validation requests
- **[0.7.0.35]** `ValidatorAgent` class with:
  - Multiple validation types
  - Custom validator registration
  - Combined validation
  - Convenience methods (validate_success, validate_element_exists, validate_url, validate_text_on_page)

#### Supervisor Agent (`browser_agent/agents/supervisor.py`)
- **[0.7.0.36]** `TaskStatus` enum (pending, planning, executing, validating, completed, failed, cancelled)
- **[0.7.0.37]** `TaskDelegation` dataclass for task tracking
- **[0.7.0.38]** `SupervisorConfig` dataclass for supervisor configuration
- **[0.7.0.39]** `AgentPool` class for agent management
- **[0.7.0.40]** `SupervisorAgent` class with:
  - Multi-agent orchestration
  - Task planning and decomposition
  - Step execution management
  - Result validation
  - Failure recovery
  - Result synthesis

#### Tests
- **[0.7.0.41]** `tests/test_agents.py` - 73 comprehensive tests
  - BaseAgent tests (12 tests)
  - Communication tests (10 tests)
  - PlannerAgent tests (10 tests)
  - AnalyzerAgent tests (8 tests)
  - ActorAgent tests (7 tests)
  - ValidatorAgent tests (9 tests)
  - SupervisorAgent tests (12 tests)
  - Integration tests (3 tests)

### Statistics
- **388 tests passing** (14 skipped)
- **73 new agent tests**
- **6 new modules** in agents package

---

## [0.6.0] - 2026-03-25

### Added - Phase 4: Advanced Capabilities - Skills System

#### Skill System Architecture
- **[0.6.0.1]** `browser_agent/skills/__init__.py` - Skills module initialization
- **[0.6.0.2]** `browser_agent/skills/base.py` - Base skill abstract class
  - `SkillCapability` enum for capability definitions
  - `SkillInput` dataclass for skill input parameters
  - `SkillResult` dataclass for execution results
  - `BaseSkill` abstract class with execute, validate, verify methods
  - Built-in retry logic with exponential backoff
- **[0.6.0.3]** `browser_agent/skills/registry.py` - Skill registration system
  - `SkillRegistry` class for skill management
  - Capability-based skill lookup
  - Global registry with decorator support
  - Skill instance caching

#### Form Filling Skill
- **[0.6.0.4]** `browser_agent/skills/form_filling.py`
  - `FieldType` enum (text, email, password, select, checkbox, radio, etc.)
  - `FormField` dataclass for field definitions
  - `FormSchema` dataclass for form structure
  - `FormFillingInput` for skill input
  - `FormFillingSkill` with:
    - Form schema detection from HTML
    - Field type mapping
    - Multi-field form completion
    - Form validation
    - Form submission with success detection

#### Data Extraction Skill
- **[0.6.0.5]** `browser_agent/skills/data_extraction.py`
  - `ExtractionFieldType` enum (text, number, price, rating, url, etc.)
  - `ExtractionField` dataclass for extraction definitions
  - `ExtractionSchema` dataclass for extraction structure
  - `DataExtractionSkill` with:
    - Schema-based extraction
    - Multi-item extraction with container selectors
    - Pagination handling
    - Deduplication with configurable fields
    - Value processing (price, rating, number parsing)

#### Web Scraping Skill
- **[0.6.0.6]** `browser_agent/skills/web_scraping.py`
  - `ScrapingMode` enum (single_page, paginated, crawl, sitemap)
  - `ComplianceLevel` enum (strict, moderate, none)
  - `RateLimitConfig` dataclass for rate limiting
  - `ScrapingConfig` dataclass for scraping configuration
  - `WebScrapingSkill` with:
    - Multi-page navigation (single, paginated, crawl modes)
    - Data aggregation across pages
    - Rate limiting with requests per minute
    - Robots.txt compliance checking
    - URL pattern filtering (include/exclude)

#### Workflow Automation Skill
- **[0.6.0.7]** `browser_agent/skills/workflow.py`
  - `StepType` enum (action, condition, loop, parallel, wait, skill, subworkflow)
  - `ConditionOperator` enum (equals, contains, greater_than, etc.)
  - `LoopType` enum (count, while, for_each)
  - `Condition` class for conditional logic
  - `WorkflowStep` dataclass for step definitions
  - `Workflow` dataclass for workflow structure
  - `WorkflowContext` for execution state management
  - `WorkflowSkill` with:
    - Chained operations
    - Conditional branching (if/else)
    - Loops (count, while, for-each)
    - Parallel step execution
    - Error handling with retry/skip options
    - Checkpoint save/restore

#### Tests
- **[0.6.0.8]** `tests/test_skills.py` - 106 comprehensive tests
  - Base skill tests (13 tests)
  - Skill registry tests (12 tests)
  - Form filling skill tests (17 tests)
  - Data extraction skill tests (17 tests)
  - Web scraping skill tests (12 tests)
  - Workflow skill tests (28 tests)
  - Integration tests (2 tests)

### Statistics
- **300 tests passing** (14 skipped)
- **106 new skill tests**
- **5 new modules** in skills package

---

## [0.5.1] - 2026-03-25

### Planning - Phase 4.5: Localhost Test Pages

#### Test Infrastructure Planning
- **[0.5.1.1]** Added Phase 4.5 to todo.md with 42 new tasks for localhost test pages
- **[0.5.1.2]** Use Case 1: Form Filling test page structure
  - Text inputs, textarea, dropdown, checkboxes, radio buttons
  - Expected outcomes documentation
  - Client-side validation script
- **[0.5.1.3]** Use Case 2: Data Extraction test page structure
  - Product listing with name, price, description, ratings
  - Reference JSON data for validation
- **[0.5.1.4]** Use Case 3: Web Scraping test page structure
  - Blog listing with pagination (3 pages)
  - Category filters, load more button
- **[0.5.1.5]** Use Case 4: Search & Research test page structure
  - Mock search engine with results
  - Article detail pages
- **[0.5.1.6]** Use Case 5: Workflow Automation test page structure
  - Login page, dashboard, downloadable report
- **[0.5.1.7]** Use Case 6: E-commerce Interaction test page structure
  - Product catalog, shopping cart, checkout flow
- **[0.5.1.8]** Test server infrastructure
  - Python HTTP server script
  - Start scripts for Windows/Linux/Mac
  - README documentation

### Changed
- **[0.5.1.9]** Updated todo.md summary statistics (275 total tasks, ~47% complete)

---

## [0.5.0] - 2026-03-25

### Added - Phase 3: Resilience & Recovery (Major Feature)

#### Checkpoint System (`browser_agent/resilience/checkpoint.py`)
- **[0.5.0.1]** CheckpointType enum for checkpoint classification
  - PRE_ACTION, POST_ACTION, TASK_START, TASK_END
  - MANUAL, RECOVERY, BRANCH

- **[0.5.0.2]** BrowserState dataclass for browser state snapshots
  - URL, title, scroll position
  - Cookies, localStorage, sessionStorage
  - Form values preservation
  - Screenshot with hash computation
  - Serialization to/from dict

- **[0.5.0.3]** Checkpoint dataclass for checkpoint records
  - Browser state snapshot
  - Task step tracking
  - Action name and result
  - Parent/child relationships
  - Metadata support

- **[0.5.0.4]** CheckpointManager class for checkpoint management
  - `create_checkpoint()` - Create checkpoint from page state
  - `restore_checkpoint()` - Restore browser to checkpoint
  - `get_checkpoint()` - Retrieve checkpoint by ID
  - `get_latest_checkpoint()` - Get most recent checkpoint
  - `get_checkpoints_by_type()` - Filter by checkpoint type
  - `get_checkpoint_chain()` - Get checkpoint ancestry
  - Disk persistence with JSON serialization
  - Screenshot storage in separate files
  - Configurable max checkpoints with pruning
  - Checkpoint interval control

#### Fallback Strategy System (`browser_agent/resilience/fallback.py`)
- **[0.5.0.5]** ErrorType enum for error classification
  - ELEMENT_NOT_FOUND, ACTION_TIMEOUT, NAVIGATION_ERROR
  - SELECTOR_INVALID, STATE_MISMATCH, CAPTCHA_BLOCK
  - RATE_LIMIT, NETWORK_ERROR, BROWSER_CRASH
  - PERMISSION_DENIED, AUTH_REQUIRED, VALIDATION_ERROR

- **[0.5.0.6]** ErrorContext dataclass for error context
  - Error type and message
  - Action name and parameters
  - Page URL and screenshot
  - Attempt count and previous errors

- **[0.5.0.7]** FallbackResult dataclass for strategy results
  - Success/failure status
  - Recovery action and parameters
  - Next strategy hint
  - Retry/abort flags

- **[0.5.0.8]** FallbackStrategy abstract base class
  - `can_handle()` - Check if strategy applies
  - `execute()` - Execute fallback strategy
  - Priority ordering
  - Max attempts per strategy

- **[0.5.0.9]** Built-in fallback strategies:
  - **VisualSearchFallback** - Use vision model to find elements
  - **ScrollAndRetryFallback** - Scroll page and retry
  - **ExtendedWaitFallback** - Wait longer for elements
  - **RefreshAndRetryFallback** - Refresh page and retry
  - **NavigationRetryFallback** - Retry navigation with backoff
  - **CheckpointRestoreFallback** - Restore from checkpoint

- **[0.5.0.10]** FallbackManager class for strategy coordination
  - Strategy registration and prioritization
  - Error classification from patterns
  - Automatic strategy selection
  - Strategy execution with tracking
  - Error and fallback history

#### State Stack (`browser_agent/resilience/state_stack.py`)
- **[0.5.0.11]** StateFrame dataclass for stack frames
  - Browser state snapshot
  - Step index and action info
  - Parent/child relationships
  - Branch point support
  - Access tracking

- **[0.5.0.12]** StateStack class for multi-level rollback
  - `push()` - Push state onto stack
  - `pop()` - Pop state from stack
  - `peek()` - View frame without removing
  - `rollback()` - Rollback by N steps
  - `rollback_to_frame()` - Rollback to specific frame
  - `create_branch()` - Create exploration branch
  - `switch_branch()` - Switch to different branch
  - `merge_branch()` - Merge branches
  - Max depth enforcement
  - Auto-pruning of old frames

#### Recovery Orchestration (`browser_agent/resilience/recovery.py`)
- **[0.5.0.13]** RecoveryStatus enum for recovery outcomes
  - SUCCESS, PARTIAL, FAILED, ABORTED, MANUAL_REQUIRED

- **[0.5.0.14]** RecoveryConfig dataclass for recovery settings
  - Max recovery attempts
  - Recovery delay
  - Enable/disable checkpoints, state stack, fallbacks
  - Callbacks for success/failure/manual intervention

- **[0.5.0.15]** RecoveryResult dataclass for recovery results
  - Recovery status and strategy used
  - Attempts made and actions taken
  - Restored state ID

- **[0.5.0.16]** RecoveryOrchestrator class for automatic recovery
  - `recover()` - Main recovery entry point
  - `create_recovery_checkpoint()` - Checkpoint before recovery
  - `attempt_checkpoint_restore()` - Try checkpoint restore
  - `attempt_state_stack_rollback()` - Try stack rollback
  - `execute_fallback_strategy()` - Execute fallback
  - `verify_recovery()` - Verify recovery success
  - `graceful_degradation()` - Graceful fallback options
  - Manual intervention callbacks
  - Recovery history tracking

#### Tests (`tests/test_resilience.py`)
- **[0.5.0.17]** 52 comprehensive tests for Phase 3
  - BrowserState tests (5 tests)
  - Checkpoint tests (3 tests)
  - CheckpointManager tests (10 tests)
  - ErrorClassification tests (3 tests)
  - FallbackStrategies tests (4 tests)
  - FallbackManager tests (10 tests)
  - StateStack tests (9 tests)
  - RecoveryOrchestrator tests (7 tests)
  - Integration tests (1 test)

### Changed
- Updated `browser_agent/resilience/__init__.py` to export all classes

### Statistics
- **Total Tests**: 194 passed, 14 skipped
- **New Tests**: 52 (resilience module)
- **Progress**: ~55% complete (was ~40%)

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

<div align="center">

# 🤖 Browser Agent

### *AI-Powered Browser Automation with Visual Intelligence*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests: 573 passed](https://img.shields.io/badge/tests-573%20passed-brightgreen.svg)](tests/)

**A production-ready, modular browser automation framework that sees and understands web pages like a human.**

[Quick Start](#-quick-start) • [Features](#-features) • [Documentation](#-documentation) • [API Reference](#-api-reference) • [Examples](#-examples)

</div>

---

## 🎯 What is Browser Agent?

Browser Agent is an advanced AI-powered automation framework that combines **computer vision** with **large language models** to interact with web pages intelligently. Unlike traditional automation tools that rely on fragile selectors, Browser Agent **sees** and **understands** web pages, making it resilient to UI changes and capable of handling complex workflows.

### Why Browser Agent?

| Traditional Automation | Browser Agent |
|----------------------|---------------|
| ❌ Breaks when selectors change | ✅ Uses visual intelligence to find elements |
| ❌ Can't handle dynamic content | ✅ Adapts to changing page layouts |
| ❌ No error recovery | ✅ Automatic checkpoint-based recovery |
| ❌ Single-threaded execution | ✅ Multi-agent parallel processing |
| ❌ No memory between sessions | ✅ Learns from past interactions |
| ❌ Detectable as bot | ✅ Advanced anti-detection & stealth mode |

---

## ✨ Features

### 🧠 Visual Intelligence
- **UI-TARS Integration** - State-of-the-art vision model for element detection
- **Screenshot Analysis** - Understand page content visually
- **Coordinate Detection** - Find elements by description, not selectors
- **Page State Classification** - Detect loading, errors, modals, CAPTCHAs

### 🛡️ Resilience & Recovery
- **Checkpoint System** - Save and restore browser state at any point
- **Automatic Recovery** - Self-healing from errors with 6 fallback strategies
- **State Stack** - Navigate back through action history
- **Error Prevention** - Proactive anomaly detection

### 🤖 Multi-Agent Architecture
- **Supervisor Agent** - Orchestrates complex workflows
- **Planner Agent** - Breaks down tasks into steps
- **Analyzer Agent** - Analyzes page content
- **Actor Agent** - Executes browser actions
- **Validator Agent** - Verifies results

### 💾 Memory System
- **Visual Memory** - Remembers UI states and navigation patterns
- **Conversation Memory** - Learns user preferences
- **Correction Learning** - Improves from user feedback

### 🔒 Enterprise Features
- **Credential Vault** - AES-256-GCM encryption, per-tenant key derivation, secret providers (env, HashiCorp Vault, AWS, Azure)
- **Audit Trail** - Tamper-evident hash chain, structured logging, compliance reports (GDPR, HIPAA, PCI-DSS, SOC 2)
- **Approval Workflows** - Policy engine, escalation chains, Slack/Teams/Email notifications
- **Scheduled Workflows** - Cron-based scheduling, business calendar, health monitoring
- **Data Loss Prevention** - PII detection, 5 redaction strategies, configurable DLP policies
- **Multi-Tenant** - 4 plan tiers, resource pools, fair-share scheduler, quota management
- **Workflow Recording & Replay** - Record/playback with adaptive self-healing, parameterization, version control

### 🔌 Production Ready
- **REST API** - FastAPI endpoints for remote execution
- **Task Queue** - Concurrent task processing
- **Observability** - Metrics, logging, health checks
- **Docker Support** - Containerized deployment

---

## 📦 Installation

### Prerequisites

- Python 3.10 or higher
- [LM Studio](https://lmstudio.ai/) with UI-TARS model (or OpenAI API key)
- Chrome/Firefox/Edge browser

### Quick Install

```bash
# Clone the repository
git clone https://github.com/justroflanGitHub/b-agent.git
cd b-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### Configuration

Create a `config.yaml` file:

```yaml
# Browser settings
browser:
  browser_type: chromium    # chromium, firefox, webkit
  headless: false           # Set true for production
  viewport_width: 1280
  viewport_height: 720

# LLM settings (LM Studio)
llm:
  base_url: http://localhost:1234
  model: ui-tars
  temperature: 0.7
  max_tokens: 4096
  timeout: 60

# Vision settings
vision:
  model: ui-tars
  cache_enabled: true

# Resilience settings
resilience:
  max_retry_per_action: 3
  checkpoint_enabled: true
  exponential_backoff_base: 1.0
```

---

## 🚀 Quick Start

### Basic Usage

```python
import asyncio
from browser_agent import BrowserAgent
from browser_agent.config import Config

async def main():
    # Load configuration
    config = Config.from_yaml("config.yaml")
    
    # Create and initialize agent
    async with BrowserAgent(config) as agent:
        # Execute a task
        result = await agent.execute_task(
            goal="Search for Python tutorials and click the first result",
            start_url="https://google.com"
        )
        
        print(f"Success: {result.success}")
        print(f"Steps: {len(result.steps)}")
        print(f"Data: {result.data}")

asyncio.run(main())
```

### Using the REST API

```bash
# Start the API server
python -m browser_agent.api.app

# Submit a task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Fill out the contact form with test data",
    "start_url": "https://example.com/contact"
  }'

# Check task status
curl http://localhost:8000/tasks/{task_id}
```

### Command Line

```bash
# Run a single task
python run_agent.py --goal "Search for weather in Moscow" --url "https://google.com"

# Run with specific config
python run_agent.py --config my_config.yaml --goal "Extract product prices"

# Headless mode
python run_agent.py --goal "Login to dashboard" --headless
```

---

## 📚 Documentation

### Table of Contents

| Document | Description |
|----------|-------------|
| [FEATURES.md](FEATURES.md) | Comprehensive feature documentation |
| [USE_CASES.md](USE_CASES.md) | Supported use cases and examples |
| [CHANGELOG.md](CHANGELOG.md) | Version history and changes |
| [todo.md](todo.md) | Development roadmap |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser Agent                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Browser   │  │    LLM      │  │      Vision Client      │  │
│  │ Controller  │  │   Client    │  │    (UI-TARS Model)      │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         │                │                     │                │
│         └────────────────┼─────────────────────┘                │
│                          │                                      │
│  ┌───────────────────────┴───────────────────────────────────┐  │
│  │                    Action Executor                        │  │
│  │   click | type | scroll | extract | navigate | wait | ... │  │
│  └───────────────────────────┬───────────────────────────────┘  │
│                              │                                  │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │                   Multi-Agent System                      │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │  │
│  │  │ Planner  │ │ Analyzer │ │  Actor   │ │  Validator   │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │  │
│  │                     ↑ Supervisor ↑                        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Resilience Layer                        │ │
│  │  Checkpoint Manager │ Fallback Strategies │ Recovery       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                     Memory System                          │ │
│  │  Visual Memory │ Error Prevention │ Conversation Memory    │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎮 Action Types

Browser Agent supports 28+ action types:

### Navigation
| Action | Description |
|--------|-------------|
| `navigate` | Go to URL |
| `go_back` | Navigate back |
| `go_forward` | Navigate forward |
| `refresh` | Refresh page |

### Mouse
| Action | Description |
|--------|-------------|
| `click` | Click element |
| `double_click` | Double click |
| `right_click` | Right click |
| `hover` | Hover over element |
| `drag_and_drop` | Drag element to target |

### Visual Mouse (Coordinate-based)
| Action | Description |
|--------|-------------|
| `hover_visual` | Hover at coordinates from vision |
| `type_visual` | Click and type at coordinates |

### Input
| Action | Description |
|--------|-------------|
| `type_text` | Type text into input |
| `clear_input` | Clear input field |
| `select_option` | Select dropdown option |
| `check` | Check checkbox |
| `uncheck` | Uncheck checkbox |

### Scroll
| Action | Description |
|--------|-------------|
| `scroll_up` | Scroll up |
| `scroll_down` | Scroll down |
| `scroll_to` | Scroll to position |
| `scroll_to_element` | Scroll to element |

### Content
| Action | Description |
|--------|-------------|
| `extract_text` | Extract page text |
| `extract_html` | Extract page HTML |
| `get_page_info` | Get URL, title, etc. |
| `take_screenshot` | Capture screenshot |

### Advanced
| Action | Description |
|--------|-------------|
| `wait` | Wait for duration |
| `wait_for_element` | Wait for element |
| `wait_for_navigation` | Wait for page load |
| `switch_frame` | Switch to iframe |
| `handle_dialog` | Handle alert/confirm |
| `press_key` | Press keyboard key |

---

## 🔌 API Reference

### REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/tasks` | Submit new task |
| `GET` | `/tasks/{id}` | Get task status |
| `GET` | `/tasks/{id}/result` | Get task result |
| `DELETE` | `/tasks/{id}` | Cancel task |
| `GET` | `/tasks` | List all tasks |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Get metrics |
| `GET` | `/skills` | List skills |
| `POST` | `/sessions` | Create session |
| `GET` | `/sessions/{id}` | Get session |
| `DELETE` | `/sessions/{id}` | End session |

### Task Request

```json
{
  "goal": "string",           // Natural language task description
  "start_url": "string?",     // Optional starting URL
  "max_steps": 20,            // Maximum action steps
  "timeout": 300.0,           // Timeout in seconds
  "options": {}               // Additional options
}
```

### Task Response

```json
{
  "task_id": "uuid",
  "status": "completed",
  "success": true,
  "extracted_data": {},
  "final_url": "https://...",
  "execution_time": 12.5,
  "steps": [...],
  "error": null
}
```

---

## 📝 Examples

### Form Filling

```python
async def fill_form():
    async with BrowserAgent() as agent:
        result = await agent.execute_task(
            goal="Fill out the registration form with: name='John Doe', email='john@example.com', password='SecurePass123!'",
            start_url="https://example.com/register"
        )
    return result
```

### Data Extraction

```python
async def extract_products():
    async with BrowserAgent() as agent:
        result = await agent.execute_task(
            goal="Extract all product names and prices from the page",
            start_url="https://shop.example.com/products"
        )
        
        for product in result.data.get("products", []):
            print(f"{product['name']}: {product['price']}")
```

### Web Scraping

```python
async def scrape_articles():
    async with BrowserAgent() as agent:
        result = await agent.execute_task(
            goal="Scrape article titles and summaries from the news page",
            start_url="https://news.example.com",
            max_steps=50  # Allow more steps for pagination
        )
    return result.data
```

### E-commerce Automation

```python
async def add_to_cart():
    async with BrowserAgent() as agent:
        result = await agent.execute_task(
            goal="Search for 'wireless headphones', add the first result to cart, and proceed to checkout",
            start_url="https://shop.example.com"
        )
    return result
```

### Using Skills

```python
from browser_agent.skills import FormFillingSkill, DataExtractionSkill

async def use_skills():
    async with BrowserAgent() as agent:
        # Form filling skill
        form_skill = FormFillingSkill(
            browser_controller=agent.browser,
            vision_client=agent.vision_client
        )
        
        result = await form_skill.execute(FormInput(
            form_data={
                "name": "John Doe",
                "email": "john@example.com"
            },
            submit=True
        ))
```

---

## 🧪 Testing

### Run Tests

```bash
# Run all unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=browser_agent --cov-report=html

# Run integration tests (requires UI-TARS)
pytest tests/test_integration_use_cases.py -v --run-integration

# Run specific test file
pytest tests/test_agent.py -v
```

### Test Statistics

| Category | Count |
|----------|-------|
| Unit Tests | 573 |
| Integration Tests | 20 |
| Test Pages | 7 |
| Coverage | ~85% |

---

## 🐳 Docker Deployment

### Build Image

```bash
docker build -t browser-agent -f docker/Dockerfile .
```

### Run Container

```bash
docker run -d \
  --name browser-agent \
  -p 8000:8000 \
  -e LLM_BASE_URL=http://host.docker.internal:1234 \
  browser-agent
```

### Docker Compose

```yaml
version: '3.8'
services:
  browser-agent:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - LLM_BASE_URL=http://lmstudio:1234
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./logs:/app/logs
```

---

## ⚙️ Configuration Reference

### Complete Configuration

```yaml
# Browser Configuration
browser:
  browser_type: chromium      # chromium, firefox, webkit
  headless: false             # Run without visible window
  viewport_width: 1280        # Browser viewport width
  viewport_height: 720        # Browser viewport height
  timeout: 30.0               # Default timeout seconds
  slow_mo: 0                  # Slow down operations (ms)

# LLM Configuration
llm:
  base_url: http://localhost:1234  # LM Studio / Ollama / OpenAI
  model: ui-tars                   # Model name
  api_key: null                    # API key (if required)
  temperature: 0.7                 # Sampling temperature
  max_tokens: 4096                 # Max response tokens
  timeout: 60                      # Request timeout

# Vision Configuration
vision:
  model: ui-tars              # Vision model
  cache_enabled: true         # Cache vision results
  cache_size: 100             # Max cached items

# Resilience Configuration
resilience:
  max_retry_per_action: 3     # Retries per action
  checkpoint_enabled: true    # Enable checkpoints
  checkpoint_interval: 1      # Checkpoint every N actions
  max_checkpoints: 50         # Max stored checkpoints
  exponential_backoff_base: 1.0

# Observability Configuration
observability:
  log_level: INFO             # DEBUG, INFO, WARNING, ERROR
  log_file: logs/agent.log    # Log file path
  metrics_enabled: true       # Enable metrics collection
  health_check_interval: 30   # Health check seconds
```

---

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov black flake8 mypy

# Run linting
black browser_agent tests
flake8 browser_agent tests

# Run type checking
mypy browser_agent
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Playwright](https://playwright.dev/) - Browser automation
- [UI-TARS](https://github.com/bytedance/UI-TARS) - Vision model
- [FastAPI](https://fastapi.tiangolo.com/) - API framework
- [LM Studio](https://lmstudio.ai/) - Local LLM hosting

---

## 📞 Support

- **Documentation**: [FEATURES.md](FEATURES.md), [USE_CASES.md](USE_CASES.md)
- **Issues**: [GitHub Issues](https://github.com/justroflanGitHub/b-agent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/justroflanGitHub/b-agent/discussions)

---

<div align="center">

**[⬆ Back to Top](#-browser-agent)**

Made with ❤️ by the Browser Agent Team

</div>

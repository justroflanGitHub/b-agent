# Browser Agent Test Pages

This directory contains localhost test pages for testing browser agent capabilities.

## Quick Start

Start the local server:
```bash
cd test_pages
python server.py
```

Server runs at: http://localhost:8080

## Test Pages

| Page | URL | Description |
|------|-----|-------------|
| Form Filling | `/form_filling/` | Various form elements |
| Data Extraction | `/data_extraction/` | Product catalog |
| Web Scraping | `/web_scraping/` | Blog with pagination |
| Search & Research | `/search_research/` | Mock search engine |
| Workflow Automation | `/workflow_automation/` | Login + dashboard |
| E-commerce | `/ecommerce/` | Shop + cart + checkout |

## Directory Structure

```
test_pages/
├── server.py              # HTTP server
├── README.md              # This file
├── form_filling/
│   ├── index.html         # Form page
│   ├── validation_script.js
│   └── expected_outcomes.md
├── data_extraction/
│   ├── index.html         # Product catalog
│   ├── products.json      # Reference data
│   └── expected_outcomes.md
├── web_scraping/
│   ├── index.html         # Blog listing
│   └── expected_outcomes.md
├── search_research/
│   ├── index.html         # Search results
│   ├── article.html       # Article page
│   └── expected_outcomes.md
├── workflow_automation/
│   ├── login.html         # Login page
│   ├── dashboard.html     # Dashboard
│   └── expected_outcomes.md
└── ecommerce/
    ├── index.html         # Product listing
    ├── cart.html          # Shopping cart
    ├── checkout.html      # Checkout form
    └── expected_outcomes.md
```

## Testing with Browser Agent

### Example: Form Filling
```python
from browser_agent import BrowserAgent

agent = BrowserAgent()
await agent.start()
await agent.navigate("http://localhost:8080/form_filling/")
await agent.execute_task("Fill out the contact form with test data")
```

### Example: E-commerce Flow
```python
await agent.navigate("http://localhost:8080/ecommerce/")
await agent.execute_task("Add Wireless Headphones to cart and checkout")
```

## Valid Test Credentials

### Workflow Automation Login
| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | admin |
| user | user123 | user |
| demo | demo | user |
| test | test123 | user |

## JavaScript Helpers

Each page exposes testing helpers via `window`:

```javascript
// Form page
window.fillForm(data)
window.submitForm()
window.validateForm()

// E-commerce
window.addToCart(productId, quantity)
window.getCart()
window.clearCart()

// Search
window.searchFor(query)
window.goToPage(page)

// Web Scraping
window.goToPage(page)
window.loadMore()
window.filterByCategory(category)
```

## Events

Pages dispatch custom events for testing:

| Event | Page | Description |
|-------|------|-------------|
| `formSubmitted` | Form | Form successfully submitted |
| `itemAddedToCart` | E-commerce | Item added to cart |
| `orderPlaced` | E-commerce | Order completed |
| `loginSuccess` | Workflow | Successful login |
| `reportDownloaded` | Workflow | Report downloaded |

## Notes

- All pages use localStorage/sessionStorage for state
- No backend required - fully client-side
- CORS headers enabled for cross-origin testing
- Cache disabled for development

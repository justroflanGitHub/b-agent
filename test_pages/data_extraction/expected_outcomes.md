# Data Extraction Test Page - Expected Outcomes

## Overview
This document describes the expected behavior when the browser agent performs data extraction from the product catalog test page.

## Page Location
`test_pages/data_extraction/index.html`

## Product Data Structure

Each product contains the following fields:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| id | integer | Unique product identifier | 1 |
| sku | string | Stock keeping unit code | "TECH-001" |
| name | string | Product name | "Wireless Bluetooth Headphones" |
| category | string | Product category | "audio" |
| description | string | Product description | "Premium over-ear headphones..." |
| price | float | Current price in USD | 199.99 |
| originalPrice | float/null | Original price before discount | 249.99 |
| currency | string | Currency code | "USD" |
| rating | float | Average rating (1-5) | 4.8 |
| reviewCount | integer | Number of reviews | 1247 |
| availability | string | Stock status | "in-stock" |
| stock | integer | Units in stock | 45 |
| badge | string/null | Promotion badge | "sale" |
| featured | boolean | Featured product flag | true |

## Categories

| Category | Count | Description |
|----------|-------|-------------|
| audio | 2 | Headphones, earbuds, speakers |
| wearables | 1 | Smart watches, fitness trackers |
| accessories | 4 | Cables, chargers, stands |
| electronics | 2 | Webcams, smart home devices |
| gaming | 3 | Keyboards, mice, controllers |

## Availability States

| State | Class | Indicator Color | Products |
|-------|-------|-----------------|----------|
| in-stock | `.in-stock` | Green (#27ae60) | 10 products |
| low-stock | `.low-stock` | Orange (#f39c12) | 1 product |
| out-of-stock | `.out-of-stock` | Red (#e74c3c) | 1 product |

## Product Badges

| Badge | Class | Background Color | Products |
|-------|-------|------------------|----------|
| sale | `.badge-sale` | #e94560 | 6 products |
| new | `.badge-new` | #27ae60 | 1 product |
| popular | `.badge-popular` | #f39c12 | 2 products |

## Extraction Targets

### CSS Selectors

```css
/* Product cards */
.product-card
.product-card[data-product-id="1"]

/* Product fields */
.product-name           /* Name */
.product-category       /* Category */
.product-description    /* Description */
.current-price          /* Price */
.original-price         /* Original price */
.stars                  /* Star rating characters */
.rating                 /* Numeric rating */
.rating-count           /* Review count */
.product-sku            /* SKU code */
.product-availability   /* Availability status */

/* Badges */
.product-badge.badge-sale
.product-badge.badge-new
.product-badge.badge-popular

/* Availability */
.product-availability.in-stock
.product-availability.low-stock
.product-availability.out-of-stock
```

### Structured Data (JSON-LD)

Each product card contains a `<script type="application/ld+json">` element with structured data:

```json
{
    "@context": "https://schema.org/",
    "@type": "Product",
    "sku": "TECH-001",
    "name": "Wireless Bluetooth Headphones",
    "category": "audio",
    "description": "Premium over-ear headphones...",
    "price": 199.99,
    "originalPrice": 249.99,
    "currency": "USD",
    "rating": 4.8,
    "reviewCount": 1247,
    "availability": "in-stock",
    "stock": 45
}
```

## Expected Extraction Results

### All Products Extraction

When extracting all products, the agent should return:

```json
[
    {
        "sku": "TECH-001",
        "name": "Wireless Bluetooth Headphones",
        "category": "audio",
        "price": 199.99,
        "originalPrice": 249.99,
        "discount": 20,
        "rating": 4.8,
        "reviewCount": 1247,
        "availability": "in-stock",
        "stock": 45
    },
    // ... 11 more products
]
```

### Products by Category

**Audio Products (category: "audio"):**
- TECH-001: Wireless Bluetooth Headphones ($199.99)
- TECH-007: True Wireless Earbuds ($179.99)

**Gaming Products (category: "gaming"):**
- TECH-004: Mechanical Gaming Keyboard ($149.99)
- TECH-009: Gaming Mouse RGB ($79.99)
- TECH-012: Wireless Gaming Controller ($69.99)

### Products on Sale

Products with `originalPrice` not null:
- TECH-001: 20% off ($199.99 from $249.99)
- TECH-003: 29% off ($49.99 from $69.99)
- TECH-005: 25% off ($29.99 from $39.99)
- TECH-007: 10% off ($179.99 from $199.99)
- TECH-009: 20% off ($79.99 from $99.99)
- TECH-011: 20% off ($39.99 from $49.99)

### Price Statistics

| Metric | Value |
|--------|-------|
| Min Price | $29.99 |
| Max Price | $299.99 |
| Average Price | $113.32 |
| Total Products | 12 |
| Products on Sale | 6 |

### Rating Distribution

| Rating Range | Count | Products |
|--------------|-------|----------|
| 4.8 - 5.0 | 3 | TECH-001, TECH-002, TECH-009 |
| 4.5 - 4.7 | 6 | TECH-004, TECH-006, TECH-007, TECH-010, TECH-011, TECH-012 |
| 4.0 - 4.4 | 3 | TECH-003, TECH-005, TECH-008 |

## Testing Scenarios

### Scenario 1: Extract All Products
**Task:** "Extract all products from the page"

**Expected Result:**
- 12 products extracted
- Each product has: name, price, rating, availability
- Data matches products.json reference

### Scenario 2: Extract Products by Category
**Task:** "Extract all gaming products"

**Expected Result:**
- 3 products extracted (TECH-004, TECH-009, TECH-012)
- All have category "gaming"

### Scenario 3: Extract Products on Sale
**Task:** "Find all products with a discount"

**Expected Result:**
- 6 products with originalPrice not null
- Discount percentages calculated correctly

### Scenario 4: Extract Top Rated Products
**Task:** "Find products with rating 4.8 or higher"

**Expected Result:**
- 3 products: TECH-001 (4.8), TECH-002 (4.9), TECH-009 (4.8)

### Scenario 5: Extract Available Products
**Task:** "Find all products currently in stock"

**Expected Result:**
- 10 products with availability "in-stock"
- 1 product with "low-stock" (TECH-006)
- 1 product excluded "out-of-stock" (TECH-012)

### Scenario 6: Price Range Extraction
**Task:** "Find products under $100"

**Expected Result:**
- 5 products: TECH-003, TECH-005, TECH-008, TECH-009, TECH-011, TECH-012

## JavaScript Testing Helpers

### `window.products`
Direct access to the products array.

```javascript
const allProducts = window.products;
```

### `window.getProductsByCategory(category)`
Filter products by category.

```javascript
const gamingProducts = window.getProductsByCategory('gaming');
```

### `window.getProductsByPriceRange(range)`
Filter products by price range.

```javascript
const affordableProducts = window.getProductsByPriceRange('0-50');
```

### `window.renderProducts(productList)`
Re-render the product grid with filtered products.

```javascript
window.renderProducts(filteredProducts);
```

### `window.dataExtractionPageLoaded`
Boolean flag indicating page is fully loaded.

## Custom Events

| Event Name | Trigger | Detail |
|------------|---------|--------|
| `dataExtractionPageReady` | Page fully loaded | None |

## Validation Checks

### Data Integrity
1. All 12 products should be extractable
2. Each product should have required fields (name, price, category)
3. Prices should be valid positive numbers
4. Ratings should be between 1.0 and 5.0
5. Review counts should be positive integers

### Extraction Accuracy
1. Product names should match exactly
2. Prices should include currency ($ prefix)
3. Ratings should include star characters (★☆)
4. Availability text should match status

### Edge Cases
1. Products with null originalPrice (no discount)
2. Products with null badge (no badge displayed)
3. Out of stock product (TECH-012) - Add to Cart disabled
4. Low stock product (TECH-006) - Shows remaining count

## CSS Class Reference

```css
/* Container */
.product-grid

/* Card */
.product-card
.product-card[data-product-id="X"]
.product-card[data-category="X"]

/* Elements */
.product-image
.product-info
.product-category
.product-name
.product-description
.product-rating
.product-price
.product-availability
.product-meta
.product-sku

/* Modifiers */
.badge-sale
.badge-new
.badge-popular
.in-stock
.low-stock
.out-of-stock
```

## Price Parsing

Prices are displayed in format: `$199.99`

Extraction should:
1. Remove `$` prefix
2. Parse as float
3. Handle discount calculation: `((originalPrice - price) / originalPrice) * 100`

## Rating Parsing

Ratings are displayed as: `★★★★☆ 4.8 (1,247 reviews)`

Extraction should:
1. Count filled stars (★) for star rating
2. Parse numeric rating (4.8)
3. Parse review count (remove commas)

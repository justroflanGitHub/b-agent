# Web Scraping Test Page - Expected Outcomes

## Overview
This document describes the expected behavior when the browser agent performs web scraping on the blog test page.

## Page Location
`test_pages/web_scraping/index.html`

## Blog Post Data Structure

Each blog post contains the following fields:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| id | integer | Unique post identifier | 1 |
| title | string | Post title | "Getting Started with Machine Learning" |
| category | string | Post category | "ai" |
| excerpt | string | Post excerpt/summary | "A comprehensive guide..." |
| author | string | Author name | "Sarah Chen" |
| date | string | Publication date (YYYY-MM-DD) | "2026-03-20" |
| readTime | integer | Reading time in minutes | 8 |
| views | integer | View count | 15420 |
| comments | integer | Comment count | 47 |
| image | string | Emoji icon | "🤖" |

## Categories

| Category | Count | Description |
|----------|-------|-------------|
| ai | 4 | Artificial Intelligence & Machine Learning |
| web | 4 | Web Development |
| security | 4 | Cybersecurity |
| cloud | 3 | Cloud Computing |

## Pagination

- **Posts per page:** 5
- **Total posts:** 15
- **Total pages:** 3

### Page Contents

| Page | Post IDs | Posts |
|------|----------|-------|
| 1 | 1-5 | ML Guide, CSS Grid, Zero Trust, Kubernetes, NLP Future |
| 2 | 6-10 | JavaScript, OAuth 2.0, Serverless, Computer Vision, PWA |
| 3 | 11-15 | Ransomware, Multi-Cloud, RL Explained, WebAssembly, Pen Testing |

## Expected Scraping Results

### All Posts Extraction

When scraping all posts across all pages:

```json
[
    {
        "id": 1,
        "title": "Getting Started with Machine Learning in 2026",
        "category": "ai",
        "author": "Sarah Chen",
        "date": "2026-03-20",
        "readTime": 8,
        "views": 15420,
        "comments": 47
    },
    // ... 14 more posts
]
```

### Posts by Category

**AI Posts (category: "ai"):**
- ID 1: Getting Started with Machine Learning in 2026
- ID 5: The Future of Natural Language Processing
- ID 9: Computer Vision Applications in Healthcare
- ID 13: Reinforcement Learning Explained

**Web Development Posts (category: "web"):**
- ID 2: Building Responsive Web Apps with CSS Grid
- ID 6: Modern JavaScript Features You Need to Know
- ID 10: Building Progressive Web Apps from Scratch
- ID 14: WebAssembly: The Future of Web Performance

### Most Viewed Posts

| Rank | ID | Title | Views |
|------|-----|-------|-------|
| 1 | 5 | The Future of Natural Language Processing | 18,900 |
| 2 | 1 | Getting Started with Machine Learning in 2026 | 15,420 |
| 3 | 6 | Modern JavaScript Features You Need to Know | 14,500 |
| 4 | 10 | Building Progressive Web Apps from Scratch | 13,200 |
| 5 | 4 | Kubernetes Best Practices for Production | 11,200 |

### Most Commented Posts

| Rank | ID | Title | Comments |
|------|-----|-------|----------|
| 1 | 5 | The Future of Natural Language Processing | 56 |
| 2 | 1 | Getting Started with Machine Learning in 2026 | 47 |
| 3 | 10 | Building Progressive Web Apps from Scratch | 45 |
| 4 | 4 | Kubernetes Best Practices for Production | 41 |
| 5 | 6 | Modern JavaScript Features You Need to Know | 38 |

## Testing Scenarios

### Scenario 1: Scrape All Posts with Pagination
**Task:** "Scrape all blog posts by navigating through pagination"

**Steps:**
1. Navigate to page 1
2. Extract all 5 posts
3. Click "Next" or page "2"
4. Extract all 5 posts
5. Click page "3"
6. Extract all 5 posts

**Expected Result:**
- 15 total posts extracted
- Each post has: title, author, date, category
- Posts are in chronological order (newest first)

### Scenario 2: Scrape with Load More
**Task:** "Load and scrape all posts using the Load More button"

**Steps:**
1. Extract initial 5 posts
2. Click "Load More Posts"
3. Extract 5 additional posts
4. Click "Load More Posts" again
5. Extract final 5 posts
6. Verify "No More Posts" state

**Expected Result:**
- 15 total posts extracted
- Load More button disabled after all posts loaded

### Scenario 3: Filter and Scrape by Category
**Task:** "Filter by AI category and scrape all AI posts"

**Steps:**
1. Click "AI" filter tag
2. Extract visible posts
3. Navigate pagination if needed

**Expected Result:**
- 4 AI posts extracted
- All posts have category "ai"

### Scenario 4: Scrape Popular Posts from Sidebar
**Task:** "Extract the popular posts from the sidebar"

**Expected Result:**
- 4 posts extracted (sorted by views)
- Most viewed: "The Future of Natural Language Processing" (18,900 views)

### Scenario 5: Scrape Categories List
**Task:** "Extract the categories and their post counts from sidebar"

**Expected Result:**
```json
[
    {"category": "Artificial Intelligence", "count": 8},
    {"category": "Web Development", "count": 12},
    {"category": "Cybersecurity", "count": 6},
    {"category": "Cloud Computing", "count": 9},
    {"category": "Mobile Development", "count": 5},
    {"category": "DevOps", "count": 7}
]
```

## CSS Selectors Reference

```css
/* Blog cards */
.blog-card
.blog-card[data-post-id="X"]
.blog-card[data-category="X"]

/* Post elements */
.blog-title a           /* Title */
.blog-category          /* Category badge */
.blog-date              /* Publication date */
.blog-read-time         /* Read time */
.blog-excerpt           /* Excerpt text */
.author-name            /* Author name */
.blog-stats .stat       /* Views and comments */

/* Pagination */
.pagination button      /* All pagination buttons */
.pagination button.active /* Current page */

/* Filter tags */
.filter-tag
.filter-tag.active

/* Sidebar */
.category-list li       /* Category items */
.category-count         /* Post count */
.popular-post           /* Popular post item */
.popular-post-title     /* Popular post title */

/* Load more */
.load-more-btn
```

## JavaScript Testing Helpers

### `window.allPosts`
Direct access to all posts array.

```javascript
const posts = window.allPosts;
```

### `window.getFilteredPosts()`
Get posts filtered by current category.

```javascript
const filteredPosts = window.getFilteredPosts();
```

### `window.goToPage(page)`
Navigate to a specific page.

```javascript
window.goToPage(2);  // Go to page 2
```

### `window.loadMore()`
Trigger load more functionality.

```javascript
window.loadMore();
```

### `window.filterByCategory(category)`
Filter posts by category.

```javascript
window.filterByCategory('ai');
```

### `window.getCurrentPage()`
Get current page number.

```javascript
const page = window.getCurrentPage();  // Returns 1, 2, or 3
```

### `window.getDisplayedCount()`
Get number of currently displayed posts.

```javascript
const count = window.getDisplayedCount();  // Returns 5, 10, or 15
```

### `window.webScrapingPageLoaded`
Boolean flag indicating page is fully loaded.

## Custom Events

| Event Name | Trigger | Detail |
|------------|---------|--------|
| `webScrapingPageReady` | Page fully loaded | None |

## Rate Limiting Simulation

For testing rate limiting compliance:

| Action | Recommended Delay |
|--------|-------------------|
| Page navigation | 1-2 seconds |
| Load more click | 1-2 seconds |
| Filter change | 500ms-1 second |

## Pagination Flow

```
Page 1 (Posts 1-5)
    ↓ Click "Next" or "2"
Page 2 (Posts 6-10)
    ↓ Click "Next" or "3"
Page 3 (Posts 11-15)
    ↓ "Next" disabled
End of pagination
```

## Load More Flow

```
Initial Load (Posts 1-5)
    ↓ Click "Load More Posts"
Posts 1-10 displayed
    ↓ Click "Load More Posts"
Posts 1-15 displayed
    ↓ Button shows "No More Posts" and disabled
End of posts
```

## Data Validation

### Post Count Validation
- Total posts: 15
- Posts per page: 5
- Total pages: 3

### Date Format
- Format: YYYY-MM-DD
- Range: 2026-03-06 to 2026-03-20
- Order: Descending (newest first)

### View Count Format
- Display format: "15,420" (with comma separator)
- Parse as integer: 15420

### Read Time Format
- Display format: "8 min read"
- Parse as integer: 8

## Scraping Strategies

### Strategy 1: Pagination-Based
1. Start at page 1
2. Extract visible posts
3. Check for "Next" button enabled
4. Click "Next" and repeat
5. Stop when "Next" is disabled

### Strategy 2: Load More-Based
1. Extract visible posts
2. Check "Load More" button state
3. Click "Load More" if enabled
4. Repeat extraction
5. Stop when button shows "No More Posts"

### Strategy 3: Filter-Then-Scrape
1. Click category filter
2. Wait for content update
3. Extract filtered posts
4. Handle pagination if needed
5. Repeat for other categories

## Error Handling

### Pagination Errors
- Invalid page number: No action
- Already on first/last page: Buttons disabled

### Filter Errors
- Invalid category: No filter change
- No posts in category: Empty grid

### Load More Errors
- All posts loaded: Button disabled
- No more posts: Button shows "No More Posts"

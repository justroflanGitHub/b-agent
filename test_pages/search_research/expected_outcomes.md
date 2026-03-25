# Search & Research Test Page - Expected Outcomes

## Overview
This document describes the expected behavior when the browser agent performs search and research tasks on the mock search engine test page.

## Page Location
`test_pages/search_research/index.html`

## Search Functionality

### Search Input
- **Selector:** `#searchInput`
- **Search Button:** `#searchBtn`
- **Trigger:** Enter key or click Search button

### Available Queries
| Query | Results | Related Searches | Knowledge Panel |
|-------|---------|------------------|-----------------|
| machine learning | 10 results | 8 related | Yes |
| python | 2 results | 6 related | Yes |

## Search Results Structure

Each search result contains:

| Field | Type | Description | Selector |
|-------|------|-------------|----------|
| id | integer | Result ID | `.result-item[data-result-id]` |
| sponsored | boolean | Is sponsored/ad | `.result-sponsored` |
| url | string | Full URL | `.result-title a[href]` |
| displayUrl | string | Display URL | `.result-url cite` |
| title | string | Result title | `.result-title a` |
| description | string | Result description | `.result-description` |
| sitelinks | array | Sub-links | `.result-sitelinks .sitelink` |

## Machine Learning Query Results

### Default Query: "machine learning"

| ID | Sponsored | Title | Domain |
|----|-----------|-------|--------|
| 1 | Yes | Machine Learning Course by Stanford University | coursera.org |
| 2 | No | Machine learning - Wikipedia | en.wikipedia.org |
| 3 | No | What is Machine Learning? \| IBM | ibm.com |
| 4 | No | TensorFlow - Machine Learning for Everyone | tensorflow.org |
| 5 | No | scikit-learn: Machine Learning in Python | scikit-learn.org |
| 6 | No | What is Machine Learning? - AWS | aws.amazon.com |
| 7 | No | Machine Learning: What It Is and How It Works | investopedia.com |
| 8 | No | PyTorch - From Research to Production | pytorch.org |
| 9 | No | What is Machine Learning? \| NVIDIA Glossary | nvidia.com |
| 10 | No | The Top 10 Machine Learning Trends of 2026 | forbes.com |

### Related Searches
- machine learning for beginners
- machine learning algorithms
- machine learning vs deep learning
- machine learning projects
- machine learning course free
- machine learning python
- types of machine learning
- machine learning applications

### Knowledge Panel

| Field | Value |
|-------|-------|
| Title | Machine learning |
| Subtitle | Field of study |
| Field | Artificial Intelligence |
| Founded | 1959 |
| Subfields | Deep learning, NLP, Computer vision |
| Applications | Image recognition, Speech processing |
| Related | Data science, Statistics |

## Testing Scenarios

### Scenario 1: Basic Search
**Task:** "Search for 'machine learning' and list the top 5 results"

**Steps:**
1. Locate search input field
2. Type "machine learning"
3. Press Enter or click Search button
4. Extract first 5 results

**Expected Result:**
```json
[
    {"title": "Machine Learning Course by Stanford University", "domain": "coursera.org", "sponsored": true},
    {"title": "Machine learning - Wikipedia", "domain": "en.wikipedia.org", "sponsored": false},
    {"title": "What is Machine Learning? | IBM", "domain": "ibm.com", "sponsored": false},
    {"title": "TensorFlow - Machine Learning for Everyone", "domain": "tensorflow.org", "sponsored": false},
    {"title": "scikit-learn: Machine Learning in Python", "domain": "scikit-learn.org", "sponsored": false}
]
```

### Scenario 2: Navigate to Result
**Task:** "Search for 'machine learning', click on the Wikipedia result, and extract the article title"

**Steps:**
1. Search for "machine learning"
2. Find result with title containing "Wikipedia"
3. Click the result link
4. Extract article title from new page

**Expected Result:**
- Article title: "Machine learning - Wikipedia"

### Scenario 3: Related Search
**Task:** "Click on 'machine learning algorithms' related search"

**Steps:**
1. Locate related searches section
2. Find "machine learning algorithms" link
3. Click the link
4. Verify search query updated

**Expected Result:**
- Search input shows "machine learning algorithms"
- Results updated (or default fallback)

### Scenario 4: Extract Knowledge Panel
**Task:** "Extract information from the knowledge panel"

**Expected Result:**
```json
{
    "title": "Machine learning",
    "subtitle": "Field of study",
    "facts": {
        "Field": "Artificial Intelligence",
        "Founded": "1959",
        "Subfields": "Deep learning, NLP, Computer vision",
        "Applications": "Image recognition, Speech processing",
        "Related": "Data science, Statistics"
    }
}
```

### Scenario 5: Pagination Navigation
**Task:** "Navigate to page 2 of results"

**Steps:**
1. Locate pagination section
2. Click "2" or "Next"
3. Verify page changed

**Expected Result:**
- Page number updated to 2
- Page scrolled to top

### Scenario 6: Back Navigation
**Task:** "Search, click result, then go back to results"

**Steps:**
1. Search for "machine learning"
2. Click on a result
3. Navigate back (browser back button or link)

**Expected Result:**
- Return to search results page
- Search query preserved

## CSS Selectors Reference

```css
/* Search */
#searchInput
#searchBtn
.search-box

/* Results */
.search-results
.result-item
.result-item[data-result-id="X"]
.result-sponsored
.result-url cite
.result-title a
.result-description
.result-sitelinks
.sitelink a

/* Related Searches */
.related-searches
.related-item

/* Knowledge Panel */
.knowledge-panel
.knowledge-title
.knowledge-subtitle
.knowledge-facts

/* Pagination */
.pagination
.pagination a
.pagination a.active
.page-numbers
```

## JavaScript Testing Helpers

### `window.searchFor(query)`
Perform a search programmatically.

```javascript
window.searchFor('machine learning');
```

### `window.goToPage(page)`
Navigate to a specific results page.

```javascript
window.goToPage(2);
```

### `window.getCurrentQuery()`
Get the current search query.

```javascript
const query = window.getCurrentQuery();  // "machine learning"
```

### `window.getCurrentPage()`
Get the current page number.

```javascript
const page = window.getCurrentPage();  // 1
```

### `window.getSearchResults()`
Get the current search results array.

```javascript
const results = window.getSearchResults();
```

### `window.searchResearchPageLoaded`
Boolean flag indicating page is fully loaded.

## Custom Events

| Event Name | Trigger | Detail |
|------------|---------|--------|
| `searchResearchPageReady` | Page fully loaded | None |

## Article Page

### Location
`test_pages/search_research/article.html?id=X`

### Article Structure

| Field | Selector |
|-------|----------|
| Title | `.article-title` |
| Date | `.article-meta span:nth-child(1)` |
| Read Time | `.article-meta span:nth-child(2)` |
| Author | `.article-meta span:nth-child(3)` |
| Views | `.article-meta span:nth-child(4)` |
| Content | `.article-content` |
| Tags | `.article-tag` |

### Article Navigation

- **Back to Results:** `.back-to-results`
- **Breadcrumb:** `.breadcrumb a`

## Result Types

### Standard Result
```html
<div class="result-item" data-result-id="2">
    <div class="result-url"><cite>en.wikipedia.org › wiki › Machine_learning</cite></div>
    <h3 class="result-title">
        <a href="article.html?id=2">Machine learning - Wikipedia</a>
    </h3>
    <p class="result-description">...</p>
</div>
```

### Sponsored Result
```html
<div class="result-item" data-result-id="1">
    <span class="result-sponsored">Sponsored</span>
    <div class="result-url"><cite>coursera.org › learn › machine-learning</cite></div>
    <h3 class="result-title">
        <a href="article.html?id=1">Machine Learning Course by Stanford University</a>
    </h3>
    <p class="result-description">...</p>
</div>
```

### Result with Sitelinks
```html
<div class="result-item" data-result-id="2">
    ...
    <div class="result-sitelinks">
        <div class="sitelink">
            <a href="...">History</a>
            <span class="sitelink-desc">Origins and development</span>
        </div>
        ...
    </div>
</div>
```

## Search Flow

```
1. Enter query in search box
2. Press Enter or click Search
3. Results page updates:
   - Result count changes
   - Search time updates
   - Results list refreshes
   - Related searches update
   - Knowledge panel updates
4. Click result → Navigate to article
5. Click back → Return to results
```

## Data Validation

### Result Count Format
- Display: "10,450,000" (with commas)
- Parse: Remove commas, convert to integer

### Search Time Format
- Display: "0.42 seconds"
- Parse: Extract decimal number

### URL Format
- Full URL: `https://www.example.com/path`
- Display URL: `example.com › path › subpath`

## Error Handling

### Invalid Search
- Empty query: No action or default results
- Unknown query: Fallback to "machine learning" results

### Navigation Errors
- Invalid page number: No action
- Missing article ID: Default article shown

# UI Testing Use Case - Expected Outcomes

> **Test Page Version:** 1.0.0
> **Last Updated:** 2026-03-26
> **Purpose:** Define expected outcomes for UI Testing use case tests

---

## Overview

This document defines the expected outcomes for each test scenario in the UI Testing use case. The browser agent should be able to interact with various UI components and verify their behavior.

---

## Test Scenarios

### 1. Button Click Test

**Goal:** Test clicking buttons and verifying click counter

**Steps:**
1. Navigate to the UI Testing page
2. Click the "Primary Button"
3. Click the "Success Button"
4. Verify the click counter shows 2 or more

**Expected Outcomes:**
| Check | Expected | Notes |
|-------|----------|-------|
| Primary button clicked | Button receives `.btn-clicked` class briefly | Visual feedback |
| Success button clicked | Button receives `.btn-clicked` class briefly | Visual feedback |
| Click counter | Shows "2" or higher | Counter increments on each click |

**Validation:**
```javascript
// Check click counter
const counter = await page.input_value("#click-count");
assert(parseInt(counter) >= 2, "Click counter should be 2 or higher");
```

---

### 2. Form Validation Test

**Goal:** Test form validation with invalid and valid inputs

**Steps:**
1. Enter "notanemail" in the email field
2. Click outside the field to trigger blur validation
3. Verify error message appears
4. Clear and enter "test@example.com"
5. Verify error message disappears and field shows valid state

**Expected Outcomes:**
| Check | Expected | Notes |
|-------|----------|-------|
| Invalid email shows error | `#email-error` has `.visible` class | Error message displayed |
| Field marked invalid | Input has `.invalid` class | Red border |
| Valid email clears error | `#email-error` loses `.visible` class | Error hidden |
| Field marked valid | Input has `.valid` class | Green border |

**Validation:**
```javascript
// Check error message visibility
const errorVisible = await page.is_visible("#email-error.visible");
const fieldValid = await page.is_visible("#email-input.valid");
```

---

### 3. Modal Interaction Test

**Goal:** Test opening and closing modal dialogs

**Steps:**
1. Click "Open Modal" button
2. Verify modal overlay appears with `.active` class
3. Click "Confirm" button inside modal
4. Verify modal closes (no `.active` class)
5. Verify success notification appears

**Expected Outcomes:**
| Check | Expected | Notes |
|-------|----------|-------|
| Modal opens | `#modal-overlay` has `.active` class | Modal visible |
| Modal content visible | Modal title "Test Modal" is visible | Content loaded |
| Modal closes on confirm | `#modal-overlay` loses `.active` class | Modal hidden |
| Notification appears | `.notification.success` element created | Success feedback |

**Validation:**
```javascript
// Open modal
await page.click("#open-modal");
await page.wait_for_selector("#modal-overlay.active");

// Close modal
await page.click("#modal-confirm");
await page.wait_for_selector("#modal-overlay:not(.active)");
```

---

### 4. Tabs Navigation Test

**Goal:** Test tab switching functionality

**Steps:**
1. Click on "Tab 2" button
2. Verify Tab 2 content is visible
3. Click on "Tab 3" button
4. Verify Tab 3 content is visible and Tab 2 is hidden

**Expected Outcomes:**
| Check | Expected | Notes |
|-------|----------|-------|
| Tab 2 button active | Button has `.active` class | Visual indicator |
| Tab 2 content visible | `#tab2` has `.active` class | Content shown |
| Tab 3 button active | Button has `.active` class | After clicking Tab 3 |
| Tab 3 content visible | `#tab3` has `.active` class | Content shown |
| Tab 2 content hidden | `#tab2` loses `.active` class | Content hidden |

**Validation:**
```javascript
// Click Tab 2
await page.click("[data-tab='tab2']");
await page.wait_for_selector("#tab2.active");

// Click Tab 3
await page.click("[data-tab='tab3']");
await page.wait_for_selector("#tab3.active");
```

---

### 5. Toggle Switch Test

**Goal:** Test toggle switch functionality

**Steps:**
1. Click the first toggle switch
2. Verify status changes to "ON"
3. Click the second toggle switch
4. Verify both toggles show "ON"

**Expected Outcomes:**
| Check | Expected | Notes |
|-------|----------|-------|
| Toggle 1 checked | `#toggle-1` is checked | Checkbox state |
| Toggle 1 status "ON" | `#toggle-status-1` shows "ON" | Text updated |
| Toggle 2 checked | `#toggle-2` is checked | Checkbox state |
| Toggle 2 status "ON" | `#toggle-status-2` shows "ON" | Text updated |

**Validation:**
```javascript
// Toggle first switch
await page.check("#toggle-1");
const status1 = await page.text_content("#toggle-status-1");
assert(status1 === "ON", "Toggle 1 should be ON");

// Toggle second switch
await page.check("#toggle-2");
const status2 = await page.text_content("#toggle-status-2");
assert(status2 === "ON", "Toggle 2 should be ON");
```

---

### 6. Accordion Test

**Goal:** Test accordion expand/collapse functionality

**Steps:**
1. Click on "Section 1" header
2. Verify Section 1 content expands
3. Click on "Section 2" header
4. Verify Section 1 collapses and Section 2 expands

**Expected Outcomes:**
| Check | Expected | Notes |
|-------|----------|-------|
| Section 1 expands | First accordion item has `.active` class | Content visible |
| Section 1 content visible | Content text is readable | Expanded state |
| Section 2 expands | Second accordion item has `.active` class | After clicking |
| Section 1 collapses | First accordion item loses `.active` class | Only one open |

**Validation:**
```javascript
// Expand Section 1
await page.click("#accordion-header-1");
await page.wait_for_selector(".accordion-item:first-child.active");

// Expand Section 2 (should close Section 1)
await page.click("#accordion-header-2");
await page.wait_for_selector(".accordion-item:nth-child(2).active");
```

---

### 7. Progress Bar Test

**Goal:** Test progress bar animation

**Steps:**
1. Click "Start Progress" button
2. Wait for progress to complete (100%)
3. Verify progress shows 100%
4. Click "Reset Progress" button
5. Verify progress shows 0%

**Expected Outcomes:**
| Check | Expected | Notes |
|-------|----------|-------|
| Progress starts | Progress fill width increases | Animation begins |
| Progress reaches 100% | `#progress-percent` shows "100%" | Complete |
| Success notification | Notification with "Progress complete!" | Feedback |
| Reset works | Progress returns to 0% | After reset click |

**Validation:**
```javascript
// Start progress
await page.click("#start-progress");

// Wait for completion (may take ~4 seconds)
await page.wait_for_function(() => {
    return document.querySelector("#progress-percent").textContent === "100%";
}, { timeout: 10000 });

// Reset
await page.click("#reset-progress");
const percent = await page.text_content("#progress-percent");
assert(percent === "0%", "Progress should be reset to 0%");
```

---

### 8. Visibility Test

**Goal:** Test element visibility detection

**Steps:**
1. Verify visible element is displayed
2. Verify hidden element is not visible
3. Click "Toggle Hidden Element" button
4. Verify hidden element becomes visible

**Expected Outcomes:**
| Check | Expected | Notes |
|-------|----------|-------|
| Visible element shown | `data-testid="visible-element"` is visible | Always shown |
| Hidden element not shown | `data-testid="hidden-element"` is hidden | display: none |
| Toggle reveals element | Hidden element becomes visible | After click |

**Validation:**
```javascript
// Check visibility
const visible = await page.is_visible("[data-testid='visible-element']");
const hidden = await page.is_visible("[data-testid='hidden-element']");

assert(visible === true, "Visible element should be visible");
assert(hidden === false, "Hidden element should not be visible");

// Toggle
await page.click("#toggle-hidden");
const nowVisible = await page.is_visible("[data-testid='hidden-element']");
assert(nowVisible === true, "Hidden element should now be visible");
```

---

### 9. Assertion Area Test

**Goal:** Test assertion area state changes

**Steps:**
1. Click "Set Success" button
2. Verify assertion area shows success state
3. Click "Set Error" button
4. Verify assertion area shows error state
5. Click "Reset" button
6. Verify assertion area returns to default state

**Expected Outcomes:**
| Check | Expected | Notes |
|-------|----------|-------|
| Success state | `#assertion-area` has `.success` class | Green background |
| Error state | `#assertion-area` has `.error` class | Red background |
| Default state | `#assertion-area` has no state class | Default appearance |

**Validation:**
```javascript
// Set success
await page.click("#assert-success");
await page.wait_for_selector("#assertion-area.success");

// Set error
await page.click("#assert-error");
await page.wait_for_selector("#assertion-area.error");

// Reset
await page.click("#assert-reset");
const hasClass = await page.has_class("#assertion-area", "success") || 
                 await page.has_class("#assertion-area", "error");
assert(!hasClass, "Assertion area should have no state class");
```

---

## UI-TARS Vision Test Expectations

When using UI-TARS vision model for testing, the following visual cues should be detectable:

### Visual Elements
- **Buttons**: Distinct colors (primary=blue, success=green, danger=red, warning=yellow)
- **Form fields**: Border color changes (red=invalid, green=valid)
- **Modal**: Dark overlay with centered white box
- **Tabs**: Underlined active tab
- **Toggles**: Slider position indicates ON/OFF
- **Progress bar**: Gradient fill from left to right
- **Accordion**: Expanded sections show content, collapsed show only header

### Text Content
- Click counter: "Click count: X"
- Toggle status: "ON" or "OFF"
- Progress: "X%"
- Error messages: Red text below invalid fields

### State Indicators
- Active states: CSS classes `.active`, `.visible`, `.success`, `.error`
- Loading states: Spinner animation
- Disabled states: Grayed out appearance

---

## Test Data

### Form Test Data
```json
{
  "valid_email": "test@example.com",
  "invalid_email": "notanemail",
  "valid_password": "SecurePass123",
  "invalid_password": "short",
  "valid_phone": "123-456-7890",
  "invalid_phone": "1234567890"
}
```

### Expected Select Options
- Option 1: "option1"
- Option 2: "option2"
- Option 3: "option3"

---

## Success Criteria

| Test | Success Rate Threshold |
|------|----------------------|
| Button Click | 70% |
| Form Validation | 70% |
| Modal Interaction | 70% |
| Tabs Navigation | 70% |
| Toggle Switch | 70% |
| Accordion | 70% |
| Progress Bar | 50% (timing dependent) |
| Visibility | 70% |
| Assertion Area | 70% |

**Overall Success**: All tests should pass with at least their threshold percentage of steps successful.

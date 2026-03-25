# Form Filling Test Page - Expected Outcomes

## Overview
This document describes the expected behavior when the browser agent interacts with the contact form test page.

## Page Location
`test_pages/form_filling/index.html`

## Form Fields

### Personal Information Section

| Field | Type | Required | Selector | Expected Behavior |
|-------|------|----------|----------|-------------------|
| First Name | text | Yes | `#firstName` | Accept any non-empty text |
| Last Name | text | Yes | `#lastName` | Accept any non-empty text |
| Email | email | Yes | `#email` | Must match email pattern `^[^\s@]+@[^\s@]+\.[^\s@]+$` |
| Phone | tel | No | `#phone` | Optional, format hint provided |
| Date of Birth | date | No | `#birthdate` | Date picker input |

### Account Setup Section

| Field | Type | Required | Selector | Validation |
|-------|------|----------|----------|------------|
| Username | text | Yes | `#username` | 3-20 characters, alphanumeric only |
| Password | password | Yes | `#password` | Minimum 8 characters |
| Confirm Password | password | Yes | `#confirmPassword` | Must match password field |

### Contact Preferences Section

| Field | Type | Required | Selector | Options |
|-------|------|----------|----------|---------|
| Subject | select | Yes | `#subject` | general, support, sales, feedback, partnership, other |
| Contact Method | radio | No | `input[name="contactMethod"]` | email (default), phone, sms |
| Best Time | checkbox | No | `input[name="bestTime"]` | morning, afternoon, evening |

### Additional Information Section

| Field | Type | Required | Selector | Notes |
|-------|------|----------|----------|-------|
| Website | url | No | `#website` | URL format expected |
| Budget | range | No | `#budget` | $0 - $10,000, default $5,000 |
| Priority | select | No | `#priority` | low, medium (default), high, urgent |
| Quantity | number | No | `#quantity` | 1-100, default 1 |
| Message | textarea | Yes | `#message` | Minimum 10 characters |
| Interests | checkbox | No | `input[name="interests"]` | products, services, newsletter, events |
| Terms | checkbox | Yes | `#terms` | Must be checked |
| Newsletter | checkbox | No | `#newsletter` | Optional subscription |

## Validation Rules

### Client-Side Validation
1. **First Name**: Required, minimum 1 character
2. **Last Name**: Required, minimum 1 character
3. **Email**: Required, valid email format
4. **Username**: Required, 3-20 alphanumeric characters
5. **Password**: Required, minimum 8 characters
6. **Confirm Password**: Required, must match password
7. **Subject**: Required, must select an option
8. **Message**: Required, minimum 10 characters
9. **Terms**: Required, must be checked

### Error Display
- Invalid fields get `.error` class (red border)
- Error messages appear in `.error-message` elements
- Error messages become visible with `.visible` class

## Success Criteria

### Form Submission Success
1. All required fields are filled correctly
2. Validation passes for all fields
3. Submit button triggers form submission
4. Success message appears (`.success-message.visible`)
5. Form data is stored in `sessionStorage` under `lastFormData`
6. Custom event `formSubmitted` is dispatched

### Expected Form Data Structure
```json
{
  "firstName": "John",
  "lastName": "Doe",
  "email": "john.doe@example.com",
  "phone": "+1 (555) 123-4567",
  "birthdate": "1990-01-15",
  "username": "johndoe123",
  "subject": "general",
  "contactMethod": "email",
  "bestTimes": ["morning", "afternoon"],
  "website": "https://www.example.com",
  "budget": "5000",
  "priority": "medium",
  "quantity": "1",
  "message": "This is a test message with at least 10 characters.",
  "interests": ["products", "services"],
  "newsletter": true,
  "terms": true,
  "timestamp": "2026-03-25T12:00:00.000Z"
}
```

## Testing Scenarios

### Scenario 1: Complete Form Filling
**Steps:**
1. Navigate to form page
2. Fill all required fields with valid data
3. Check terms checkbox
4. Click submit button

**Expected Result:**
- Success message appears
- Form data stored in sessionStorage
- Submit button text changes to "Submitted!"

### Scenario 2: Partial Form Filling (Only Required)
**Steps:**
1. Fill only required fields (marked with *)
2. Check terms checkbox
3. Click submit button

**Expected Result:**
- Form submits successfully
- Optional fields are empty or have default values

### Scenario 3: Validation Error Handling
**Steps:**
1. Leave required fields empty
2. Enter invalid email format
3. Enter mismatched passwords
4. Click submit button

**Expected Result:**
- Form does not submit
- Error messages appear for invalid fields
- First error field receives focus

### Scenario 4: Form Reset
**Steps:**
1. Fill some fields
2. Click reset button

**Expected Result:**
- All fields cleared
- Error states removed
- Success message hidden
- Form returns to initial state

## JavaScript Testing Helpers

The page exposes several helper functions for testing:

### `window.fillForm(data)`
Programmatically fill the form with provided data object.

```javascript
window.fillForm({
  firstName: "Test",
  lastName: "User",
  email: "test@example.com",
  username: "testuser",
  password: "password123",
  confirmPassword: "password123",
  subject: "support",
  message: "This is a test message.",
  terms: true
});
```

### `window.submitForm()`
Programmatically submit the form.

```javascript
window.submitForm();
```

### `window.validateForm()`
Run validation on all fields, returns boolean.

```javascript
const isValid = window.validateForm();
```

### `window.validateField(fieldName)`
Validate a specific field by name.

```javascript
const isEmailValid = window.validateField('email');
```

### `window.getFormData()`
Get the last submitted form data from sessionStorage.

```javascript
const formData = window.getFormData();
```

### `window.formPageLoaded`
Boolean flag indicating page is fully loaded.

## Custom Events

| Event Name | Trigger | Detail |
|------------|---------|--------|
| `formPageReady` | Page fully loaded | None |
| `formSubmitted` | Form successfully submitted | FormData object |
| `formReset` | Form reset button clicked | None |

## Agent Detection Points

The browser agent should be able to:

1. **Identify form structure** - Detect all input fields, their types, and requirements
2. **Detect required fields** - Identify fields marked with asterisk (*)
3. **Handle different input types**:
   - Text inputs
   - Email inputs
   - Password inputs
   - Date picker
   - Select dropdowns
   - Radio buttons
   - Checkboxes
   - Range slider
   - Number input
   - Textarea
4. **Validate input** - Recognize error states and messages
5. **Submit form** - Find and click submit button
6. **Verify success** - Detect success message appearance

## CSS Selectors Reference

```css
/* Form container */
.form-container

/* Input fields */
#firstName, #lastName, #email, #phone, #birthdate
#username, #password, #confirmPassword
#subject, #website, #budget, #priority, #quantity
#message

/* Radio buttons */
input[name="contactMethod"][value="email"]
input[name="contactMethod"][value="phone"]
input[name="contactMethod"][value="sms"]

/* Checkboxes */
input[name="bestTime"][value="morning"]
input[name="bestTime"][value="afternoon"]
input[name="bestTime"][value="evening"]
input[name="interests"][value="products"]
input[name="interests"][value="services"]
input[name="interests"][value="newsletter"]
input[name="interests"][value="events"]
#terms
#newsletter

/* Buttons */
#submitBtn
#resetBtn

/* Messages */
.success-message
.error-message
```

## Password Strength Indicator

The password field includes a strength indicator:

| Strength | Class | Criteria |
|----------|-------|----------|
| Weak | `.weak` | 0-2 strength points |
| Medium | `.medium` | 3-4 strength points |
| Strong | `.strong` | 5-6 strength points |

Strength points are awarded for:
- Length >= 8
- Length >= 12
- Contains uppercase letter
- Contains lowercase letter
- Contains number
- Contains special character

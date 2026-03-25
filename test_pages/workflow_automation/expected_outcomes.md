# Workflow Automation Test Page - Expected Outcomes

## Overview
This document describes the expected behavior when the browser agent performs workflow automation tasks on the login/dashboard test pages.

## Pages

| Page | File | Description |
|------|------|-------------|
| Login | `login.html` | Authentication page |
| Dashboard | `dashboard.html` | Main dashboard after login |

## Login Page

### Location
`test_pages/workflow_automation/login.html`

### Valid Credentials

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | admin |
| user | user123 | user |
| demo | demo | user |
| test | test123 | user |

### Form Fields

| Field | Type | Selector | Required |
|-------|------|----------|----------|
| Username | text | `#username` | Yes |
| Password | password | `#password` | Yes |
| Remember Me | checkbox | `#remember` | No |

### Login Flow

```
1. Enter username
2. Enter password
3. (Optional) Check "Remember me"
4. Click "Sign In" button
5. Wait for validation
6. On success: Redirect to dashboard.html
7. On failure: Show error message
```

### Error States

| Error | Trigger | Message |
|-------|---------|---------|
| Empty username | Submit without username | "Username is required" |
| Empty password | Submit without password | "Password is required" |
| Invalid credentials | Wrong username/password | "Invalid username or password" |

### Success Indicators
- Success message appears: "Login successful! Redirecting..."
- Redirect to dashboard after 1.5 seconds
- Session stored in sessionStorage
- If "Remember me" checked, username stored in localStorage

## Dashboard Page

### Location
`test_pages/workflow_automation/dashboard.html`

### Authentication Check
- Checks `sessionStorage.isLoggedIn === 'true'`
- If not logged in, redirects to login.html

### Dashboard Elements

#### Header
- Logo: "📊 Dashboard"
- Navigation: Overview, Reports, Analytics, Settings
- User info: Avatar + username
- Logout button

#### Sidebar
- Main: Dashboard, Projects, Tasks, Calendar
- Reports: Analytics, Export Data, Download Report
- Account: Settings, Profile, Help

#### Stats Cards
| Stat | Value | Icon |
|------|-------|------|
| Active Tasks | 12 | 📋 |
| Completed Tasks | 48 | ✅ |
| Active Projects | 5 | 📁 |
| Pending Reviews | 3 | ⏰ |

#### Action Items
| Action | Status | Due |
|--------|--------|-----|
| Review project proposal | Urgent | Today 5:00 PM |
| Update monthly report | Pending | Tomorrow |
| Complete code review | Complete | Yesterday |
| Schedule team meeting | Pending | This week |

#### Quick Actions
- Download Report
- Export Data
- Send Notification
- Create New Task

## Testing Scenarios

### Scenario 1: Complete Login Workflow
**Task:** "Log in with demo/demo credentials"

**Steps:**
1. Navigate to login.html
2. Enter "demo" in username field
3. Enter "demo" in password field
4. Click "Sign In" button
5. Wait for redirect

**Expected Result:**
- Redirected to dashboard.html
- Welcome message shows "Welcome back, demo!"
- User is logged in

### Scenario 2: Login with Remember Me
**Task:** "Log in and check 'Remember me'"

**Steps:**
1. Enter credentials
2. Check "Remember me" checkbox
3. Submit form
4. Return to login page

**Expected Result:**
- Username pre-filled on return visit
- localStorage contains "rememberedUsername"

### Scenario 3: Invalid Login
**Task:** "Try to log in with wrong credentials"

**Steps:**
1. Enter "wronguser" / "wrongpass"
2. Submit form

**Expected Result:**
- Error message displayed
- Stays on login page
- Form inputs have error styling

### Scenario 4: Download Report
**Task:** "Log in and download the report"

**Steps:**
1. Log in with valid credentials
2. Click "Download Report" button
3. Wait for progress bar

**Expected Result:**
- Progress bar appears
- Progress fills from 0% to 100%
- Notification shows "Report downloaded successfully!"
- Custom event `reportDownloaded` dispatched

### Scenario 5: Logout Workflow
**Task:** "Log out from the dashboard"

**Steps:**
1. Be logged in
2. Click "Logout" button
3. Confirm in modal
4. Verify redirect

**Expected Result:**
- Confirmation modal appears
- After confirm: redirected to login.html
- Session cleared

### Scenario 6: Protected Route Access
**Task:** "Access dashboard without logging in"

**Steps:**
1. Navigate directly to dashboard.html
2. Without prior login

**Expected Result:**
- Immediately redirected to login.html
- No dashboard content visible

### Scenario 7: Quick Actions
**Task:** "Test all quick action buttons"

**Steps:**
1. Log in
2. Click "Export Data"
3. Click "Send Notification"
4. Click "Create New Task"

**Expected Result:**
- Each action shows notification
- Notifications appear at bottom right

## CSS Selectors Reference

### Login Page
```css
#loginForm
#username
#password
#remember
#loginBtn
.login-error
.login-success
.error-message
```

### Dashboard Page
```css
/* Header */
.dashboard-header
.logo
.nav-menu a
.user-name
#logoutBtn

/* Sidebar */
.sidebar-menu a
#downloadReportLink

/* Stats */
.stat-card
.stat-value
.stat-label

/* Actions */
.action-item
.action-status
.status-pending
.status-complete
.status-urgent

/* Quick Actions */
#downloadReportBtn
#exportDataBtn
#sendNotificationBtn
#createTaskBtn

/* Progress */
.download-progress
.progress-fill
#progressPercent

/* Modal */
#confirmModal
.modal-title
.modal-body
#modalConfirm
#modalCancel
```

## JavaScript Testing Helpers

### Login Page

```javascript
// Valid credentials
window.validCredentials

// Check login state
window.isLoggedIn()

// Get current user
window.getCurrentUser()

// Logout
window.logout()

// Auto-fill credentials
window.fillCredentials('demo', 'demo')

// Page loaded flag
window.loginPageLoaded
```

### Dashboard Page

```javascript
// Show notification
window.showNotification('Message')

// Show modal
window.showModal('Title', 'Body', () => { /* on confirm */ })

// Download report
window.downloadReport()

// Check auth
window.checkAuth()

// Get current user
window.getCurrentUser()

// Page loaded flag
window.dashboardPageLoaded
```

## Custom Events

### Login Page

| Event | Trigger | Detail |
|-------|---------|--------|
| `loginPageReady` | Page loaded | None |
| `loginSuccess` | Valid login | `{ username, role }` |
| `loginFailed` | Invalid login | `{ username, reason }` |

### Dashboard Page

| Event | Trigger | Detail |
|-------|---------|--------|
| `dashboardPageReady` | Page loaded | None |
| `reportDownloaded` | Report download complete | `{ timestamp }` |

## Session Storage

| Key | Type | Description |
|-----|------|-------------|
| `isLoggedIn` | string | "true" when logged in |
| `currentUser` | JSON string | `{ username, role, loginTime }` |

## Local Storage

| Key | Type | Description |
|-----|------|-------------|
| `rememberedUsername` | string | Saved username if "Remember me" checked |

## Workflow State Machine

```
┌─────────────┐
│   Login     │
│  Page       │
└──────┬──────┘
       │ Valid credentials
       ▼
┌─────────────┐
│  Dashboard  │
│   Page      │
└──────┬──────┘
       │ Logout
       ▼
┌─────────────┐
│   Login     │
│  Page       │
└─────────────┘
```

## Timing Specifications

| Action | Duration |
|--------|----------|
| Login validation | 1 second (simulated API) |
| Redirect after login | 1.5 seconds |
| Report download | 2 seconds (simulated) |
| Notification display | 3 seconds |

## Validation Rules

### Username
- Required
- No minimum length
- Must match valid credentials

### Password
- Required
- No minimum length
- Must match valid credentials

## Error Handling

### Login Errors
- Network error: Show generic error
- Invalid credentials: Show specific error
- Empty fields: Show field-level errors

### Dashboard Errors
- Not authenticated: Redirect to login
- Session expired: Redirect to login

## Automation Tips

1. **Wait for page load:** Check `window.loginPageLoaded` or `window.dashboardPageLoaded`
2. **Wait for login:** Listen for `loginSuccess` event
3. **Wait for redirect:** Check URL change after login
4. **Handle modal:** Click `#modalConfirm` or `#modalCancel`
5. **Verify login state:** Check `sessionStorage.isLoggedIn`

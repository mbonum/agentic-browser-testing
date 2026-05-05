# E2E YAML Test Format

Language-agnostic Playwright test definitions with Page Object Model. Generate once, convert to any language.

## Format Structure

```yaml
scenario: Test Scenario Name
app: application-name
domain: domain-name
type: e2e
priority: P0  # P0, P1, P2
setup:
  environment:
    - ENV_VAR_1
    - ENV_VAR_2
  baseURL: https://example.com
  browser:
    - chromium
    - firefox  # optional
pages:
  - name: PageName
    path: ./pages/pagename.page.ts
    selectors:
      selectorName: locator("selector-string")
tests:
  - name: Test Name
    priority: P0
    steps:
      - action: actionName
        # action-specific fields
metadata:
  author: Author Name
  created: YYYY-MM-DD
  tags: [tag1, tag2]
  jira: TICKET-ID
```

## Supported Actions

### navigate
Navigate to URL
```yaml
- step: 1
  action: navigate
  url: https://example.com
  description: Navigate to example.com
```

### fill
Fill input field
```yaml
- step: 2
  action: fill
  selector: '#username'
  value: ${USERNAME}  # or static value
  description: Fill username field
```

### click
Click element by selector
```yaml
- step: 3
  action: click
  selector: 'button[type="submit"]'
  description: Click submit button
```

### clickByText
Click element by text content
```yaml
- step: 4
  action: clickByText
  text: Dashboard
  description: Click Dashboard link
```

### clickByRole
Click element by ARIA role
```yaml
- step: 5
  action: clickByRole
  role: button
  name: Submit  # optional
  description: Click submit button
```

### type
Type text into field (slower, character-by-character)
```yaml
- step: 6
  action: type
  selector: '#search'
  text: search query
  description: Type into search
```

### press
Press keyboard key
```yaml
- step: 7
  action: press
  selector: '#search'
  key: Enter
  description: Press Enter on search
```

### waitForSelector
Wait for element to appear
```yaml
- step: 8
  action: waitForSelector
  selector: '.results'
  description: Wait for results to load
```

### waitForLoadState
Wait for page load state
```yaml
- step: 9
  action: waitForLoadState
  state: networkidle  # load, domcontentloaded, networkidle
  description: Wait for network idle
```

### screenshot
Take screenshot
```yaml
- step: 10
  action: screenshot
  path: screenshot.png
  description: Capture screenshot
```

## Environment Variables & Security

Sensitive data (passwords, phone numbers, emails) are **automatically anonymized** and replaced with environment variable references:

```yaml
setup:
  environment:
  - E2E_PHONE_NUMBER
  - PSW_CLIENT
  - E2E_USERNAME

steps:
  - action: input
    selector: phoneInput
    value: $E2E_PHONE_NUMBER  # ✓ Real value hidden
  - action: input
    selector: passwordInput
    value: $PSW_CLIENT        # ✓ Real value hidden
```

**Auto-detected sensitive fields:**
- `passwordInput` → `$PSW_CLIENT` (from `.env`)
- `phoneInput` → `$E2E_PHONE_NUMBER`
- `usernameInput` or `emailInput` → `$E2E_USERNAME`

**Never commit actual credentials** - YAML files are safe to version control!

## Test Authorship & Traceability

The `author` field is **automatically populated** with the username who ran the test:

```yaml
metadata:
  author: mirko.bonomi@dontouch.ch  # Extracted from test runner
  created: '2026-04-28'
```

**Filename format:** `YYYYMMDD_HHMMSS_username.py`
- Date: `20260428`
- Time: `103446`
- Author: `mirko.bonomi@dontouch.ch`

This enables:
- ✓ Audit trail - who generated which tests
- ✓ Accountability for test quality
- ✓ Team collaboration tracking
- ✓ Contact point for test maintenance

## Usage

### Generate from Browser-Use (Recommended)
```bash
python src/utils/browser_use_yaml_generator.py browser_use_script.py output.e2e.yaml
```

This automatically:
- Extracts semantic selector names (phoneInput, passwordInput, loginButton)
- Builds Page Object Model
- Detects test scenario from agent success message
- Filters internal wait actions
- **Populates author field with test runner username** (from filename)
- Creates rich YAML with metadata

### Generate from Simple Playwright Script
```bash
python src/utils/playwright_yaml_generator.py script.py output.e2e.yaml
```

### Convert to TypeScript
```bash
python src/utils/playwright_yaml_generator.py --to-ts test.e2e.yaml test.spec.ts
```

### Convert to Python
```bash
python src/utils/playwright_yaml_generator.py --to-py test.e2e.yaml test.py
```

## Benefits

- **Language-agnostic**: Single test definition for all languages
- **Version control friendly**: YAML diffs are readable
- **Easy to maintain**: Update once, regenerate for all languages
- **Portable**: Share tests across teams using different stacks
- **AI-friendly**: LLMs generate valid YAML easily

## Browser-Use Generated Example

Generated from browser-use agent session:

```yaml
scenario: Login & Logout Flow
app: my-app
domain: main
type: e2e
priority: P0
setup:
  environment:
  - E2E_PHONE_NUMBER
  - PSW_CLIENT
  baseURL: https://app.example.com
  browser:
  - chromium
pages:
- name: MainPage
  path: ./pages/mainpage.page.ts
  selectors:
    phoneInput: locator("xpath=//input[@id='phone']")
    passwordInput: locator("xpath=//input[@id='password']")
    loginButton: locator("xpath=//button[@type='submit']")
    profileButton: locator("xpath=//button[@id='profile']")
    logoutButton: locator("xpath=//button[@id='logout']")
tests:
- name: Login & Logout Flow
  priority: P0
  steps:
  - action: navigate
    route: /
  - action: input
    selector: phoneInput
    value: $E2E_PHONE_NUMBER
  - action: input
    selector: passwordInput
    value: $PSW_CLIENT
  - action: click
    selector: loginButton
  - action: wait
    duration: 2000
  - action: click
    selector: profileButton
  - action: click
    selector: logoutButton
metadata:
  author: mirko.bonomi@dontouch.ch  # Auto-populated from test runner
  created: '2026-04-28'
  tags:
  - e2e
  - generated
  - main
  jira: AUTO-GENERATED
```

Convert to TypeScript:
```typescript
import { test, expect } from '@playwright/test';

test('Login Test', async ({ page }) => {
  await page.goto('https://app.example.com/login');
  await page.fill('#username', process.env.TEST_USERNAME || '');
  await page.fill('#password', process.env.TEST_PASSWORD || '');
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: 'dashboard.png' });
});
```

Convert to Python:
```python
from playwright.sync_api import sync_playwright
import os

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        page.goto('https://app.example.com/login')
        page.fill('#username', os.getenv('TEST_USERNAME', ''))
        page.fill('#password', os.getenv('TEST_PASSWORD', ''))
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')
        page.screenshot(path='dashboard.png')

        context.close()
        browser.close()

if __name__ == "__main__":
    main()
```

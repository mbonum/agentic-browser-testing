"""
Generate rich YAML test definitions from browser-use Python scripts
Supports Page Object Model and multiple test cases
"""
import re
import os
import yaml
from pathlib import Path
from datetime import datetime


def extract_actions_from_browser_use_script(python_code: str) -> list:
    """Extract actions from browser-use generated Python script"""
    actions = []
    lines = python_code.split('\n')

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Extract goto/navigate
        goto_match = re.search(r'page\.goto\([\'"]([^\'"]+)[\'"]\)', stripped)
        if goto_match:
            actions.append({
                'action': 'navigate',
                'url': goto_match.group(1),
                'line': i + 1
            })
            continue

        # Extract _try_locate_and_act fill actions
        fill_match = re.search(
            r'await _try_locate_and_act\(page,\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"]fill[\'"]\s*,\s*text=(?:replace_sensitive_data\()?[\'"]([^\'"]+)[\'"]',
            stripped
        )
        if fill_match:
            selector = fill_match.group(1)
            value = fill_match.group(2)

            # Extract step info for description
            step_info = re.search(r'step_info=[\'"]([^\'"]+)[\'"]', stripped)
            desc = step_info.group(1) if step_info else f'Fill {selector}'

            actions.append({
                'action': 'input',
                'selector': selector,
                'value': value,
                'description': desc,
                'line': i + 1
            })
            continue

        # Extract _try_locate_and_act click actions
        click_match = re.search(
            r'await _try_locate_and_act\(page,\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"]click[\'"]\s*,\s*step_info=[\'"]([^\'"]+)[\'"]',
            stripped
        )
        if click_match:
            selector = click_match.group(1)
            desc = click_match.group(2)

            actions.append({
                'action': 'click',
                'selector': selector,
                'description': desc,
                'line': i + 1
            })
            continue

        # Extract scroll actions
        scroll_match = re.search(r'window\.scrollBy\((\d+),\s*(-?\d+)\)', stripped)
        if scroll_match:
            x = int(scroll_match.group(1))
            y = int(scroll_match.group(2))

            actions.append({
                'action': 'scroll',
                'x': x,
                'y': y,
                'description': f'Scroll by ({x}, {y})',
                'line': i + 1
            })
            continue

        # Extract wait actions
        wait_match = re.search(r'page\.wait_for_timeout\((\d+)\)', stripped)
        if wait_match:
            duration = int(wait_match.group(1))
            actions.append({
                'action': 'wait',
                'duration': duration,
                'line': i + 1
            })
            continue

        # Extract wait_for_load_state
        wait_state_match = re.search(r'wait_for_load_state\([\'"]([^\'"]+)[\'"]\)', stripped)
        if wait_state_match:
            state = wait_state_match.group(1)
            actions.append({
                'action': 'waitForLoadState',
                'state': state,
                'line': i + 1
            })
            continue

        # Extract tab switches
        tab_match = re.search(r'Switching to tab with page_id (\d+)', stripped)
        if tab_match:
            page_id = int(tab_match.group(1))
            actions.append({
                'action': 'switchTab',
                'pageId': page_id,
                'line': i + 1
            })
            continue

    return actions


def extract_test_name_from_script(python_code: str) -> str:
    """Try to extract test name from success message or script"""
    # Look for task description in final message
    success_match = re.search(r'Task completed\. Step-by-step issue report:\s*\n(.+?)(?:\nOverall:|$)', python_code, re.DOTALL)
    if success_match:
        steps_text = success_match.group(1).strip()
        # Extract all numbered steps
        steps = re.findall(r'\d+\.\s*(.+?)\s*—', steps_text)

        if steps:
            # Build concise test name from key steps
            key_actions = []
            for step in steps:
                step_lower = step.lower()
                if 'go to' in step_lower or 'navigate' in step_lower:
                    continue  # Skip navigation - implied
                elif 'login' in step_lower:
                    key_actions.append('Login')
                elif 'logout' in step_lower:
                    key_actions.append('Logout')
                elif 'profile' in step_lower:
                    key_actions.append('Profile')
                elif 'dashboard' in step_lower:
                    key_actions.append('Dashboard')
                elif 'search' in step_lower:
                    key_actions.append('Search')

            if key_actions:
                return ' & '.join(key_actions) + ' Flow'

    return 'Login & Logout Flow'  # Default based on common pattern


def generate_selector_name(xpath_or_selector: str, action_type: str, context_value: str = None) -> str:
    """Generate readable selector name from XPath or CSS selector"""
    # Use context (like input value or button text) to generate better names
    if context_value and action_type == 'input':
        # Check if value looks like phone/email/password
        if re.match(r'^\d{10,}$', context_value):
            return 'phoneInput'
        if '@' in context_value:
            return 'emailInput'
        if context_value and len(context_value) >= 6 and not ' ' in context_value:
            return 'passwordInput'
        if 'username' in context_value.lower() or 'user' in context_value.lower():
            return 'usernameInput'

    # Extract meaningful parts from XPath
    if xpath_or_selector.startswith('xpath='):
        xpath = xpath_or_selector.replace('xpath=', '')

        # Look for semantic names in xpath
        if 'phone' in xpath.lower():
            return 'phoneInput' if action_type == 'input' else 'phoneButton'
        if 'password' in xpath.lower():
            return 'passwordInput' if action_type == 'input' else 'passwordButton'
        if 'email' in xpath.lower():
            return 'emailInput' if action_type == 'input' else 'emailButton'
        if 'username' in xpath.lower() or 'user' in xpath.lower():
            return 'usernameInput' if action_type == 'input' else 'usernameButton'
        if 'login' in xpath.lower() or 'sign-in' in xpath.lower():
            return 'loginButton' if action_type == 'click' else 'loginInput'
        if 'logout' in xpath.lower() or 'sign-out' in xpath.lower():
            return 'logoutButton'
        if 'submit' in xpath.lower():
            return 'submitButton'
        if 'profile' in xpath.lower():
            return 'profileButton' if action_type == 'click' else 'profileLink'
        if 'menu' in xpath.lower():
            return 'menuButton'
        if 'dashboard' in xpath.lower():
            return 'dashboardLink'
        if 'tab-button' in xpath.lower():
            return 'tabButton'
        if 'ion-list/ion-item' in xpath.lower():
            # Likely menu item - check context
            if 'item[2]' in xpath:  # Second item often logout
                return 'logoutButton'
            return 'menuItem'

        # Get last meaningful element
        parts = xpath.split('/')
        meaningful_parts = [p for p in parts if p and not p.startswith('html') and not p.startswith('body')]

        if meaningful_parts:
            last_part = meaningful_parts[-1]
            # Extract element type
            elem_match = re.match(r'([a-z-]+)(?:\[(\d+)\])?', last_part)
            if elem_match:
                elem_type = elem_match.group(1)
                # Make camelCase name
                words = elem_type.split('-')
                if action_type == 'input':
                    suffix = 'Input'
                elif action_type == 'click':
                    suffix = 'Button' if 'button' in elem_type else 'Link'
                else:
                    suffix = 'Element'

                name = ''.join(w.capitalize() for w in words) + suffix
                return name.replace('-', '')

    # For CSS selectors
    if '#' in xpath_or_selector:
        id_match = re.search(r'#([a-zA-Z0-9_-]+)', xpath_or_selector)
        if id_match:
            elem_id = id_match.group(1)
            return ''.join(w.capitalize() for w in elem_id.split('-'))

    # Default
    return f'{action_type.capitalize()}Element'


def browser_use_to_rich_yaml(python_script_path: str, output_path: str = None,
                              scenario_name: str = None, app_name: str = 'app',
                              domain: str = 'main') -> str:
    """
    Convert browser-use Python script to rich YAML test definition

    Args:
        python_script_path: Path to browser-use generated Python script
        output_path: Optional output path for YAML file
        scenario_name: Test scenario name (auto-detected if None)
        app_name: Application name
        domain: Application domain

    Returns:
        YAML content as string
    """
    if not os.path.exists(python_script_path):
        raise FileNotFoundError(f"Python script not found: {python_script_path}")

    # Extract username from filename (format: YYYYMMDD_HHMMSS_username.py)
    filename = Path(python_script_path).stem
    author_name = 'Browser-Use Agent'
    parts = filename.split('_', 2)
    if len(parts) >= 3:
        # Third part is username, remove .py extension if present
        username = parts[2].replace('.py', '')
        author_name = username if username and username != 'localuser' else 'Browser-Use Agent'

    with open(python_script_path, 'r', encoding='utf-8') as f:
        python_code = f.read()

    # Extract actions
    actions = extract_actions_from_browser_use_script(python_code)

    if not actions:
        # Return minimal YAML if no actions found
        test_def = {
            'version': '1.0',
            'name': 'Generated E2E Test',
            'description': 'Auto-generated from browser-use agent session',
            'config': {'browser': 'chromium', 'headless': False, 'viewport': {'width': 1920, 'height': 1080}},
            'variables': {},
            'steps': []
        }
        yaml_content = yaml.dump(test_def, default_flow_style=False, sort_keys=False, allow_unicode=True)
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
        return yaml_content

    # Extract test name
    if not scenario_name:
        scenario_name = extract_test_name_from_script(python_code)

    # Extract environment variables
    env_vars = set()
    for line in python_code.split('\n'):
        env_match = re.search(r'os\.getenv\([\'"]([^\'"]+)[\'"]', line)
        if env_match:
            env_vars.add(env_match.group(1))

    # Add standard sensitive data env vars
    has_password_field = any(a.get('action') == 'input' and 'password' in a.get('selector', '').lower() for a in actions)
    has_phone_field = any(a.get('action') == 'input' and 'phone' in a.get('selector', '').lower() for a in actions)
    has_username_field = any(a.get('action') == 'input' and 'username' in a.get('selector', '').lower() for a in actions)

    if has_password_field:
        env_vars.add('PSW_CLIENT')
    if has_phone_field:
        env_vars.add('E2E_PHONE_NUMBER')
    if has_username_field:
        env_vars.add('E2E_USERNAME')

    # Extract base URL from first navigate action
    base_url = 'http://localhost:8888'
    for action in actions:
        if action.get('action') == 'navigate' and action.get('url'):
            url = action['url']
            base_url = '/'.join(url.split('/')[:3])  # Get protocol://domain
            break

    # Build page objects and selectors
    selectors_by_page = {}
    page_name = 'MainPage'  # Default page

    for i, action in enumerate(actions):
        if action['action'] in ['input', 'click']:
            selector = action.get('selector', '')
            context_value = action.get('value') if action['action'] == 'input' else None
            selector_name = generate_selector_name(selector, action['action'], context_value)

            # Ensure unique selector names
            base_name = selector_name
            counter = 1
            while selector_name in selectors_by_page.get(page_name, {}):
                selector_name = f"{base_name}{counter}"
                counter += 1

            if page_name not in selectors_by_page:
                selectors_by_page[page_name] = {}

            # Store selector with Playwright locator format
            if selector.startswith('xpath='):
                xpath = selector.replace('xpath=', '')
                # Convert to getByXPath or similar
                selectors_by_page[page_name][selector_name] = f'locator("{selector}")'
            else:
                selectors_by_page[page_name][selector_name] = f'locator("{selector}")'

            # Update action to use named selector
            action['selectorName'] = selector_name

    # Extract navigate URL from success message
    navigate_url = None
    url_match = re.search(r'Go to (https?://[^\s]+)', python_code)
    if url_match:
        navigate_url = url_match.group(1)
        # Update base URL if found
        url_parts = navigate_url.split('/')
        if len(url_parts) >= 3:
            base_url = f"{url_parts[0]}//{url_parts[2]}"

    # Build test steps
    test_steps = []
    step_num = 0

    # Add initial navigate if found
    if navigate_url:
        route = navigate_url.replace(base_url, '')
        test_steps.append({
            'action': 'navigate',
            'route': route if route else '/'
        })

    for action in actions:
        step_num += 1

        if action['action'] == 'navigate':
            route = action['url'].replace(base_url, '')
            test_steps.append({
                'action': 'navigate',
                'route': route if route else '/'
            })

        elif action['action'] == 'input':
            selector_name = action.get('selectorName', 'inputElement')
            value = action.get('value', '')
            original_selector = action.get('selector', '')

            # Replace sensitive values with env var references
            if 'password' in original_selector.lower() or 'passwordInput' == selector_name:
                value = '$PSW_CLIENT'
            elif 'phone' in original_selector.lower() or 'phoneInput' == selector_name:
                value = '$E2E_PHONE_NUMBER'
            elif 'username' in original_selector.lower() or 'usernameInput' == selector_name or 'email' in original_selector.lower():
                value = '$E2E_USERNAME'
            # Check if value already looks like env var
            elif value.isupper() or '_' in value:
                env_vars.add(value)
                value = f'${value}'

            test_steps.append({
                'action': 'input',
                'selector': selector_name,
                'value': value
            })

        elif action['action'] == 'click':
            selector_name = action.get('selectorName', 'clickElement')
            test_steps.append({
                'action': 'click',
                'selector': selector_name
            })

        elif action['action'] == 'wait':
            # Only include waits >= 1 second (filter out internal waits)
            duration = action.get('duration', 0)
            if duration >= 1000:
                test_steps.append({
                    'action': 'wait',
                    'duration': duration
                })

        elif action['action'] == 'scroll':
            test_steps.append({
                'action': 'custom',
                'code': f"await page.evaluate('window.scrollBy({action['x']}, {action['y']})');"
            })

        elif action['action'] == 'waitForLoadState':
            test_steps.append({
                'action': 'waitForLoadState',
                'state': action.get('state', 'load')
            })

    # Build page objects
    pages = []
    for page_name, selectors in selectors_by_page.items():
        pages.append({
            'name': page_name,
            'path': f'./pages/{page_name.lower()}.page.ts',
            'selectors': selectors
        })

    # Build final YAML structure
    test_def = {
        'scenario': scenario_name,
        'app': app_name,
        'domain': domain,
        'type': 'e2e',
        'priority': 'P0',
        'setup': {
            'environment': list(env_vars) if env_vars else [],
            'baseURL': base_url,
            'browser': ['chromium']
        },
        'pages': pages,
        'tests': [
            {
                'name': scenario_name,
                'priority': 'P0',
                'steps': test_steps
            }
        ],
        'metadata': {
            'author': author_name,
            'created': datetime.now().strftime('%Y-%m-%d'),
            'tags': ['e2e', 'generated', domain],
            'jira': 'AUTO-GENERATED'
        }
    }

    # Generate YAML
    yaml_content = yaml.dump(test_def, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)

    # Write output file
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)

    return yaml_content


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python browser_use_yaml_generator.py <browser_use_script.py> [output.e2e.yaml]")
        sys.exit(1)

    python_file = sys.argv[1]
    yaml_file = sys.argv[2] if len(sys.argv) > 2 else python_file.replace('.py', '.e2e.yaml')

    try:
        browser_use_to_rich_yaml(python_file, yaml_file)
        print(f"Generated rich YAML: {yaml_file}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

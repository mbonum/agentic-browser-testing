"""
Generate YAML test definitions from Python Playwright scripts
"""
import re
import os
import yaml


def python_playwright_to_yaml(python_script_path: str, output_path: str = None) -> str:
    """
    Convert Python Playwright script to YAML test definition

    Args:
        python_script_path: Path to Python Playwright script
        output_path: Optional output path for YAML file

    Returns:
        YAML content as string
    """
    if not os.path.exists(python_script_path):
        raise FileNotFoundError(f"Python script not found: {python_script_path}")

    with open(python_script_path, 'r', encoding='utf-8') as f:
        python_code = f.read()

    # Parse test structure
    test_def = {
        'version': '1.0',
        'name': 'Generated E2E Test',
        'description': 'Auto-generated from browser-use agent session',
        'config': {
            'browser': 'chromium',
            'headless': False,
            'viewport': {'width': 375, 'height': 812}
        },
        'variables': {},
        'steps': []
    }

    lines = python_code.split('\n')
    step_number = 1

    # Extract config from browser launch
    headless_match = re.search(r'headless\s*[=:]\s*(True|False)', python_code)
    if headless_match:
        test_def['config']['headless'] = headless_match.group(1) == 'True'

    viewport_match = re.search(r'viewport\s*[=:]\s*\{[\'"]?width[\'"]?\s*[=:]\s*(\d+).*?[\'"]?height[\'"]?\s*[=:]\s*(\d+)', python_code)
    if viewport_match:
        test_def['config']['viewport']['width'] = int(viewport_match.group(1))
        test_def['config']['viewport']['height'] = int(viewport_match.group(2))

    # Extract environment variables
    env_vars = re.findall(r'os\.getenv\([\'"]([^\'"]+)[\'"]\)', python_code)
    for var in env_vars:
        test_def['variables'][var] = f"${{{var}}}"

    for line in lines:
        stripped = line.strip()

        # Skip empty lines, comments, imports, function defs
        if not stripped or stripped.startswith('#') or stripped.startswith('from ') or \
           stripped.startswith('import ') or stripped.startswith('def ') or \
           stripped.startswith('if __name__') or 'sync_playwright' in stripped or \
           'browser =' in stripped or 'context =' in stripped or \
           'page = ' in stripped and 'new_page()' in stripped or \
           '.close()' in stripped:
            continue

        # Parse goto
        goto_match = re.search(r'page\.goto\([\'"]([^\'"]+)[\'"]\)', stripped)
        if goto_match:
            test_def['steps'].append({
                'step': step_number,
                'action': 'navigate',
                'url': goto_match.group(1),
                'description': f'Navigate to {goto_match.group(1)}'
            })
            step_number += 1
            continue

        # Parse fill
        fill_match = re.search(r'page\.fill\([\'"]([^\'"]+)[\'"],\s*(.+)\)', stripped)
        if fill_match:
            selector = fill_match.group(1)
            value = fill_match.group(2).strip()

            # Handle environment variables
            env_match = re.search(r'os\.getenv\([\'"]([^\'"]+)[\'"]\)', value)
            if env_match:
                value = f"${{{env_match.group(1)}}}"
            else:
                value = value.strip('\'"')

            test_def['steps'].append({
                'step': step_number,
                'action': 'fill',
                'selector': selector,
                'value': value,
                'description': f'Fill {selector} with value'
            })
            step_number += 1
            continue

        # Parse click
        click_match = re.search(r'page\.click\([\'"]([^\'"]+)[\'"]\)', stripped)
        if click_match:
            test_def['steps'].append({
                'step': step_number,
                'action': 'click',
                'selector': click_match.group(1),
                'description': f'Click {click_match.group(1)}'
            })
            step_number += 1
            continue

        # Parse type
        type_match = re.search(r'page\.type\([\'"]([^\'"]+)[\'"],\s*[\'"]([^\'"]+)[\'"]\)', stripped)
        if type_match:
            test_def['steps'].append({
                'step': step_number,
                'action': 'type',
                'selector': type_match.group(1),
                'text': type_match.group(2),
                'description': f'Type into {type_match.group(1)}'
            })
            step_number += 1
            continue

        # Parse press
        press_match = re.search(r'page\.press\([\'"]([^\'"]+)[\'"],\s*[\'"]([^\'"]+)[\'"]\)', stripped)
        if press_match:
            test_def['steps'].append({
                'step': step_number,
                'action': 'press',
                'selector': press_match.group(1),
                'key': press_match.group(2),
                'description': f'Press {press_match.group(2)} on {press_match.group(1)}'
            })
            step_number += 1
            continue

        # Parse wait_for_selector
        wait_selector_match = re.search(r'page\.wait_for_selector\([\'"]([^\'"]+)[\'"]\)', stripped)
        if wait_selector_match:
            test_def['steps'].append({
                'step': step_number,
                'action': 'waitForSelector',
                'selector': wait_selector_match.group(1),
                'description': f'Wait for {wait_selector_match.group(1)} to appear'
            })
            step_number += 1
            continue

        # Parse wait_for_load_state
        wait_state_match = re.search(r'page\.wait_for_load_state\([\'"]([^\'"]+)[\'"]\)', stripped)
        if wait_state_match:
            test_def['steps'].append({
                'step': step_number,
                'action': 'waitForLoadState',
                'state': wait_state_match.group(1),
                'description': f'Wait for page load state: {wait_state_match.group(1)}'
            })
            step_number += 1
            continue

        # Parse screenshot
        screenshot_match = re.search(r'page\.screenshot\(.*?path\s*[=:]\s*[\'"]([^\'"]+)[\'"]\)', stripped)
        if screenshot_match:
            test_def['steps'].append({
                'step': step_number,
                'action': 'screenshot',
                'path': screenshot_match.group(1),
                'description': f'Take screenshot: {screenshot_match.group(1)}'
            })
            step_number += 1
            continue

        # Parse locator with click/fill
        locator_click_match = re.search(r'page\.locator\([\'"]([^\'"]+)[\'"]\)\.click\(\)', stripped)
        if locator_click_match:
            test_def['steps'].append({
                'step': step_number,
                'action': 'click',
                'selector': locator_click_match.group(1),
                'description': f'Click {locator_click_match.group(1)}'
            })
            step_number += 1
            continue

        # Parse get_by_text
        get_by_text_match = re.search(r'page\.get_by_text\([\'"]([^\'"]+)[\'"]\)\.click\(\)', stripped)
        if get_by_text_match:
            test_def['steps'].append({
                'step': step_number,
                'action': 'clickByText',
                'text': get_by_text_match.group(1),
                'description': f'Click element with text: {get_by_text_match.group(1)}'
            })
            step_number += 1
            continue

        # Parse get_by_role
        get_by_role_match = re.search(r'page\.get_by_role\([\'"]([^\'"]+)[\'"](?:,\s*name\s*[=:]\s*[\'"]([^\'"]+)[\'"]\))?\)\.click\(\)', stripped)
        if get_by_role_match:
            step = {
                'step': step_number,
                'action': 'clickByRole',
                'role': get_by_role_match.group(1),
                'description': f'Click {get_by_role_match.group(1)}'
            }
            if get_by_role_match.group(2):
                step['name'] = get_by_role_match.group(2)
                step['description'] = f'Click {get_by_role_match.group(1)} named "{get_by_role_match.group(2)}"'
            test_def['steps'].append(step)
            step_number += 1
            continue

    # Generate YAML
    yaml_content = yaml.dump(test_def, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Write output file
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)

    return yaml_content


def yaml_to_playwright_typescript(yaml_path: str, output_path: str = None) -> str:
    """
    Convert YAML test definition to TypeScript Playwright test

    Args:
        yaml_path: Path to YAML test file
        output_path: Optional output path for TypeScript file

    Returns:
        TypeScript test content
    """
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"YAML file not found: {yaml_path}")

    with open(yaml_path, 'r', encoding='utf-8') as f:
        test_def = yaml.safe_load(f)

    ts_lines = [
        "import { test, expect } from '@playwright/test';",
        "",
        f"test('{test_def.get('name', 'generated test')}', async ({{ page }}) => {{",
    ]

    for step in test_def.get('steps', []):
        action = step['action']

        if action == 'navigate':
            ts_lines.append(f"  await page.goto('{step['url']}');")

        elif action == 'fill':
            value = step['value']
            if value.startswith('${') and value.endswith('}'):
                var_name = value[2:-1]
                ts_lines.append(f"  await page.fill('{step['selector']}', process.env.{var_name} || '');")
            else:
                ts_lines.append(f"  await page.fill('{step['selector']}', '{value}');")

        elif action == 'click':
            ts_lines.append(f"  await page.click('{step['selector']}');")

        elif action == 'type':
            ts_lines.append(f"  await page.type('{step['selector']}', '{step['text']}');")

        elif action == 'press':
            ts_lines.append(f"  await page.press('{step['selector']}', '{step['key']}');")

        elif action == 'waitForSelector':
            ts_lines.append(f"  await page.waitForSelector('{step['selector']}');")

        elif action == 'waitForLoadState':
            ts_lines.append(f"  await page.waitForLoadState('{step['state']}');")

        elif action == 'screenshot':
            ts_lines.append(f"  await page.screenshot({{ path: '{step['path']}' }});")

        elif action == 'clickByText':
            ts_lines.append(f"  await page.getByText('{step['text']}').click();")

        elif action == 'clickByRole':
            if 'name' in step:
                ts_lines.append(f"  await page.getByRole('{step['role']}', {{ name: '{step['name']}' }}).click();")
            else:
                ts_lines.append(f"  await page.getByRole('{step['role']}').click();")

    ts_lines.append("});")

    ts_content = '\n'.join(ts_lines)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ts_content)

    return ts_content


def yaml_to_playwright_python(yaml_path: str, output_path: str = None) -> str:
    """
    Convert YAML test definition to Python Playwright test

    Args:
        yaml_path: Path to YAML test file
        output_path: Optional output path for Python file

    Returns:
        Python test content
    """
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"YAML file not found: {yaml_path}")

    with open(yaml_path, 'r', encoding='utf-8') as f:
        test_def = yaml.safe_load(f)

    py_lines = [
        "from playwright.sync_api import sync_playwright",
        "import os",
        "",
        "def main():",
        "    with sync_playwright() as p:",
        f"        browser = p.chromium.launch(headless={test_def['config'].get('headless', False)})",
        f"        context = browser.new_context(viewport={test_def['config'].get('viewport', {'width': 375, 'height': 812})})",
        "        page = context.new_page()",
        "",
    ]

    for step in test_def.get('steps', []):
        action = step['action']

        if action == 'navigate':
            py_lines.append(f"        page.goto('{step['url']}')")

        elif action == 'fill':
            value = step['value']
            if value.startswith('${') and value.endswith('}'):
                var_name = value[2:-1]
                py_lines.append(f"        page.fill('{step['selector']}', os.getenv('{var_name}', ''))")
            else:
                py_lines.append(f"        page.fill('{step['selector']}', '{value}')")

        elif action == 'click':
            py_lines.append(f"        page.click('{step['selector']}')")

        elif action == 'type':
            py_lines.append(f"        page.type('{step['selector']}', '{step['text']}')")

        elif action == 'press':
            py_lines.append(f"        page.press('{step['selector']}', '{step['key']}')")

        elif action == 'waitForSelector':
            py_lines.append(f"        page.wait_for_selector('{step['selector']}')")

        elif action == 'waitForLoadState':
            py_lines.append(f"        page.wait_for_load_state('{step['state']}')")

        elif action == 'screenshot':
            py_lines.append(f"        page.screenshot(path='{step['path']}')")

        elif action == 'clickByText':
            py_lines.append(f"        page.get_by_text('{step['text']}').click()")

        elif action == 'clickByRole':
            if 'name' in step:
                py_lines.append(f"        page.get_by_role('{step['role']}', name='{step['name']}').click()")
            else:
                py_lines.append(f"        page.get_by_role('{step['role']}').click()")

    py_lines.extend([
        "",
        "        context.close()",
        "        browser.close()",
        "",
        'if __name__ == "__main__":',
        "    main()"
    ])

    py_content = '\n'.join(py_lines)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(py_content)

    return py_content


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python playwright_yaml_generator.py <python_script.py> [output.e2e.yaml]  # Python to YAML")
        print("  python playwright_yaml_generator.py --to-ts <input.e2e.yaml> [output.spec.ts]  # YAML to TypeScript")
        print("  python playwright_yaml_generator.py --to-py <input.e2e.yaml> [output.py]  # YAML to Python")
        sys.exit(1)

    if sys.argv[1] == '--to-ts':
        yaml_file = sys.argv[2]
        ts_file = sys.argv[3] if len(sys.argv) > 3 else yaml_file.replace('.e2e.yaml', '.spec.ts')
        yaml_to_playwright_typescript(yaml_file, ts_file)
        print(f"Generated TypeScript: {ts_file}")
    elif sys.argv[1] == '--to-py':
        yaml_file = sys.argv[2]
        py_file = sys.argv[3] if len(sys.argv) > 3 else yaml_file.replace('.e2e.yaml', '.py')
        yaml_to_playwright_python(yaml_file, py_file)
        print(f"Generated Python: {py_file}")
    else:
        python_file = sys.argv[1]
        yaml_file = sys.argv[2] if len(sys.argv) > 2 else python_file.replace('.py', '.e2e.yaml')
        python_playwright_to_yaml(python_file, yaml_file)
        print(f"Generated YAML: {yaml_file}")

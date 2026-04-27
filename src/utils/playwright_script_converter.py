"""
Convert Python Playwright scripts to TypeScript
"""
import re
import os


def python_to_typescript_playwright(python_script_path: str, output_path: str = None) -> str:
    """
    Convert Python Playwright script to TypeScript

    Args:
        python_script_path: Path to Python Playwright script
        output_path: Optional output path for TypeScript file

    Returns:
        TypeScript script content
    """
    if not os.path.exists(python_script_path):
        raise FileNotFoundError(f"Python script not found: {python_script_path}")

    with open(python_script_path, 'r', encoding='utf-8') as f:
        python_code = f.read()

    lines = python_code.split('\n')
    ts_lines = []

    in_main = False
    skip_next = False
    first_import_done = False

    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # Skip imports and add TypeScript imports once
        if stripped.startswith('from playwright') or stripped.startswith('import os') or stripped.startswith('import asyncio'):
            if not first_import_done:
                ts_lines.append("import { test, expect } from '@playwright/test';")
                ts_lines.append("")
                first_import_done = True
            continue

        # Handle main function
        if stripped.startswith('def main('):
            ts_lines.append("test('generated test', async ({ page }) => {")
            in_main = True
            continue

        # Handle with sync_playwright
        if 'with sync_playwright()' in stripped or 'with async_playwright()' in stripped:
            continue

        # Skip browser and context creation (handled by Playwright test fixture)
        if re.match(r'\s*browser\s*=\s*', stripped):
            continue
        if re.match(r'\s*context\s*=\s*', stripped):
            continue
        if re.match(r'\s*page\s*=\s*(context|await context)\.new_page\(\)', stripped):
            continue

        # Skip close statements
        if re.match(r'\s*(await\s+)?(context|browser)\.close\(\)', stripped):
            continue

        # Handle if __name__ == "__main__"
        if stripped.startswith('if __name__'):
            skip_next = True
            continue

        # Convert function calls
        if in_main and stripped and not stripped.startswith('#'):
            converted = stripped

            # Handle variable assignments
            var_assignment = re.match(r'^(\w+)\s*=\s*(.+)$', converted)
            if var_assignment and not converted.startswith('await'):
                var_name = var_assignment.group(1)
                var_value = var_assignment.group(2)
                converted = f'const {var_name} = {var_value}'

            # Method name conversions (snake_case to camelCase)
            converted = re.sub(r'\.wait_for_timeout\(', '.waitForTimeout(', converted)
            converted = re.sub(r'\.wait_for_selector\(', '.waitForSelector(', converted)
            converted = re.sub(r'\.wait_for_load_state\(', '.waitForLoadState(', converted)
            converted = re.sub(r'\.get_by_text\(', '.getByText(', converted)
            converted = re.sub(r'\.get_by_role\(', '.getByRole(', converted)
            converted = re.sub(r'\.get_by_label\(', '.getByLabel(', converted)
            converted = re.sub(r'\.get_by_placeholder\(', '.getByPlaceholder(', converted)
            converted = re.sub(r'\.query_selector\(', '.querySelector(', converted)
            converted = re.sub(r'\.text_content\(', '.textContent(', converted)
            converted = re.sub(r'\.inner_text\(', '.innerText(', converted)
            converted = re.sub(r'\.is_visible\(', '.isVisible(', converted)
            converted = re.sub(r'\.new_page\(', '.newPage(', converted)

            # Handle Python method calls with keyword arguments
            # Convert path='...' style to { path: '...' } for options objects
            def convert_kwargs(match):
                method = match.group(1)
                args_str = match.group(2)

                # Check if there are keyword arguments (key=value pattern)
                # But not if it's inside a string
                if '=' not in args_str:
                    return match.group(0)

                # Parse arguments more carefully
                parts = []
                current = ''
                paren_depth = 0
                bracket_depth = 0
                quote_char = None

                for char in args_str:
                    if char in ('"', "'") and (not quote_char or quote_char == char):
                        quote_char = char if not quote_char else None
                    if not quote_char:
                        if char == '(':
                            paren_depth += 1
                        elif char == ')':
                            paren_depth -= 1
                        elif char == '[':
                            bracket_depth += 1
                        elif char == ']':
                            bracket_depth -= 1
                        elif char == ',' and paren_depth == 0 and bracket_depth == 0:
                            parts.append(current.strip())
                            current = ''
                            continue
                    current += char

                if current.strip():
                    parts.append(current.strip())

                # Separate positional and keyword args
                positional = []
                keyword = []
                for part in parts:
                    # Check if this part has a keyword argument
                    # Look for = that's not inside quotes
                    has_kwarg = False
                    in_string = False
                    for i, char in enumerate(part):
                        if char in ('"', "'"):
                            in_string = not in_string
                        elif char == '=' and not in_string:
                            has_kwarg = True
                            break

                    if has_kwarg:
                        keyword.append(part)
                    else:
                        positional.append(part)

                if keyword:
                    # Convert kwargs: key=value to key: value
                    obj_parts = []
                    for kw in keyword:
                        # Find the = sign that's not in a string
                        eq_pos = -1
                        in_string = False
                        for i, char in enumerate(kw):
                            if char in ('"', "'"):
                                in_string = not in_string
                            elif char == '=' and not in_string:
                                eq_pos = i
                                break

                        if eq_pos > 0:
                            key = kw[:eq_pos].strip()
                            value = kw[eq_pos+1:].strip()
                            obj_parts.append(f'{key}: {value}')

                    if obj_parts:
                        obj_str = '{ ' + ', '.join(obj_parts) + ' }'
                        if positional:
                            return f'{method}({", ".join(positional)}, {obj_str})'
                        else:
                            return f'{method}({obj_str})'

                return match.group(0)

            # Apply kwargs conversion
            converted = re.sub(r'(\.\w+)\(([^)]*)\)', convert_kwargs, converted)

            # Convert Python strings to TypeScript (after kwargs conversion)
            # Handle f-strings first
            converted = re.sub(
                r'f["\']([^"\']*)["\']',
                lambda m: '`' + re.sub(r'\{([^}]+)\}', r'${\1}', m.group(1)) + '`',
                converted
            )

            # Convert single quotes to double quotes, handling nested quotes
            def convert_quotes(match):
                content = match.group(1)
                # If content has double quotes, use backticks to avoid escaping
                if '"' in content:
                    return f'`{content}`'
                else:
                    return f'"{content}"'

            converted = re.sub(r"'([^']*)'", convert_quotes, converted)

            # Convert boolean values
            converted = re.sub(r'\bTrue\b', 'true', converted)
            converted = re.sub(r'\bFalse\b', 'false', converted)
            converted = re.sub(r'\bNone\b', 'null', converted)

            # Convert os.getenv
            converted = re.sub(r'os\.getenv\(["\']([^"\']+)["\']\)', r'process.env.\1 || ""', converted)

            # Add await for async methods
            async_methods = [
                '.goto(', '.fill(', '.click(', '.type(', '.press(',
                '.waitForTimeout(', '.waitForSelector(', '.waitForLoadState(',
                '.screenshot(', '.textContent(', '.innerText(', '.isVisible(',
                '.title(', '.content(', '.evaluate(', '.waitForNavigation(',
                '.waitForEvent(', '.selectOption(', '.check(', '.uncheck(',
                '.hover(', '.focus(', '.dblclick(', '.tap(', '.setInputFiles('
            ]

            needs_await = any(method in converted for method in async_methods)
            if needs_await and not converted.strip().startswith('await '):
                # Handle const assignment specially
                if converted.strip().startswith('const '):
                    converted = re.sub(r'^(\s*const\s+\w+\s*=\s*)', r'\1await ', converted)
                else:
                    converted = 'await ' + converted

            # Handle try/except
            if stripped.startswith('try:'):
                ts_lines.append(' ' * indent + 'try {')
                continue
            if stripped.startswith('except'):
                ts_lines.append(' ' * indent + '} catch (error) {')
                continue
            if stripped.startswith('finally:'):
                ts_lines.append(' ' * indent + '} finally {')
                continue

            # Add semicolons
            if not converted.rstrip().endswith(('{', '}', ';', ',')):
                converted = converted.rstrip() + ';'

            ts_lines.append(' ' * indent + converted)
        elif not stripped:
            # Preserve blank lines
            ts_lines.append('')

    # Close the test function
    ts_lines.append('});')

    ts_code = '\n'.join(ts_lines)

    # Final cleanup
    ts_code = re.sub(r'\n\s*\n\s*\n+', '\n\n', ts_code)  # Remove extra blank lines

    # Write output file
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ts_code)

    return ts_code


def batch_convert_python_to_typescript(input_dir: str, output_dir: str):
    """
    Convert all Python Playwright scripts in a directory to TypeScript

    Args:
        input_dir: Directory containing Python scripts
        output_dir: Directory for TypeScript output
    """
    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(input_dir):
        if filename.endswith('.py'):
            python_path = os.path.join(input_dir, filename)
            ts_filename = filename.replace('.py', '.spec.ts')
            ts_path = os.path.join(output_dir, ts_filename)

            try:
                python_to_typescript_playwright(python_path, ts_path)
                print(f"Converted: {filename} -> {ts_filename}")
            except Exception as e:
                print(f"Failed to convert {filename}: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python playwright_script_converter.py <input_python_script> [output_typescript_file]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.replace('.py', '.spec.ts')

    try:
        python_to_typescript_playwright(input_file, output_file)
        print(f"Successfully converted to: {output_file}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

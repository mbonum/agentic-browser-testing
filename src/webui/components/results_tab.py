import json
# import os
import datetime
import gradio as gr
from pathlib import Path
from src.webui.webui_manager import WebuiManager

def get_test_runs():
    """Scan the tmp/agent_history directory for test runs and return them sorted by modified time."""
    base_dir = Path("tmp/agent_history")
    if not base_dir.exists() or not base_dir.is_dir():
        return []
    
    test_runs = []
    for entry in base_dir.iterdir():
        if entry.is_dir():
            # Check if json or gif exists
            json_file = entry / f"{entry.name}.json"
            gif_file = entry / f"{entry.name}.gif"
            
            if json_file.exists() or gif_file.exists():
                if json_file.exists():
                    mtime = json_file.stat().st_mtime
                elif gif_file.exists():
                    mtime = gif_file.stat().st_mtime
                else:
                    mtime = entry.stat().st_mtime
                    
                test_runs.append({
                    "id": entry.name,
                    "mtime": mtime
                })
    
    # Sort by modification time descending
    test_runs.sort(key=lambda x: x["mtime"], reverse=True)
    return [run["id"] for run in test_runs]

def load_test_details(test_id):
    if not test_id:
        return "No test selected.", None
    
    base_dir = Path("tmp/agent_history").absolute() / test_id
    json_file = base_dir / f"{test_id}.json"
    gif_file = base_dir / f"{test_id}.gif"
    
    result_text = f"### Test Run: {test_id}\n\n"
    
    if json_file.exists():
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            history = data.get("history", [])
            if history:
                last_step = history[-1] or {}
                model_output = last_step.get("model_output") or {}
                current_state = model_output.get("current_state") or {}
                
                result_text += "**Final State Evaluation:**\n"
                result_text += f"{current_state.get('evaluation_previous_goal', 'N/A')}\n\n"
                
                result_text += "**Final Memory (Task Details):**\n"
                memory_text = current_state.get('memory', 'N/A')
                if memory_text != 'N/A':
                    import re
                    # Add newlines before "Step X -"
                    memory_text = re.sub(r'(?<!\n)(Step \d+\s*-)', r'\n\1', memory_text)
                    # Convert to "- Step X:"
                    memory_text = re.sub(r'Step (\d+)\s*-', r'- Step \1:', memory_text)
                    # Anonymize passwords
                    memory_text = re.sub(r'(?i)(password\s+["\']?)[^\s:,.;"\'\[\]<>\\]+(["\']?)', r'\1********\2', memory_text)
                    memory_text = memory_text.strip()
                result_text += f"{memory_text}\n\n"
                
                actions = model_output.get("action") or []
                for action in actions:
                    action = action or {}
                    if "done" in action:
                        result_text += "**Final Output:**\n"
                        result_text += f"{action['done'].get('text', 'N/A')}\n"
        except Exception as e:
            result_text += f"Error reading JSON log: {str(e)}"
    else:
        result_text += "JSON log file not found.\n"
        
    gif_path = str(gif_file) if gif_file.exists() else None
    
    return result_text, gif_path

def _format_step_duration(step):
    metadata = step.get("metadata") or {}
    start_time = metadata.get("step_start_time")
    end_time = metadata.get("step_end_time")

    if start_time is None or end_time is None:
        return "N/A"

    try:
        duration_seconds = max(0.0, float(end_time) - float(start_time))
    except (TypeError, ValueError):
        return "N/A"

    duration_milliseconds = round(duration_seconds * 1000)
    return f"{duration_seconds:.3f}s ({duration_milliseconds} ms)"

def _format_page_load_timing(step):
    metadata = step.get("metadata") or {}
    timing = metadata.get("page_load_timing") or {}

    if not timing:
        return "N/A"

    if timing.get("isNewNavigation") is False:
        return "N/A (no full page navigation)"

    duration_ms = timing.get("durationMs")
    if duration_ms is None:
        return "N/A"

    try:
        duration_ms = max(0.0, float(duration_ms))
    except (TypeError, ValueError):
        return "N/A"

    return f"{duration_ms / 1000:.3f}s ({round(duration_ms)} ms)"

def _format_browser_action_duration(step):
    metadata = step.get("metadata") or {}
    duration_ms = metadata.get("browser_action_duration_ms")

    if duration_ms is None:
        return "N/A"

    try:
        duration_ms = max(0.0, float(duration_ms))
    except (TypeError, ValueError):
        return "N/A"

    return f"{duration_ms / 1000:.3f}s ({round(duration_ms)} ms)"

def generate_qa_report(test_id):
    if not test_id:
        return None
    
    # Read the template
    template_path = Path("qa_report_template/qa_report_template.md")
    if not template_path.exists():
        return None
        
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
        
    # Read test JSON for data
    base_dir = Path("tmp/agent_history").absolute() / test_id
    json_file = base_dir / f"{test_id}.json"

    status = "✅ Passed"
    error_msg = ""
    history = []
    if json_file.exists():
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            history = data.get("history", [])
            if history:
                last_step = history[-1] or {}
                model_output = last_step.get("model_output") or {}
                current_state = model_output.get("current_state") or {}
                evaluation = current_state.get("evaluation_previous_goal") or ""
                if "fail" in evaluation.lower() or "error" in evaluation.lower():
                    status = "❌ Failed"
                    error_msg = evaluation
        except Exception:
            status = "Unknown"
    
    # Extract project name from URL in memory if present
    project_name = ""
    release_version = "N/A"
    
    if history:
        # Check first step memory for URL
        first_step = history[0] or {}
        first_model_output = first_step.get("model_output") or {}
        first_current_state = first_model_output.get("current_state") or {}
        first_memory = first_current_state.get("memory") or ""
        import re
        url_match = re.search(r'https?://([^/.]+)\.', first_memory)
        if url_match:
            project_name = url_match.group(1)
            
        # Try to find a release version in memory across all steps
        for step in history:
            step_data = step or {}
            model_output = step_data.get("model_output") or {}
            current_state = model_output.get("current_state") or {}
            memory = current_state.get("memory") or ""
            version_match = re.search(r'(?i)(?:release\s*version|version|v)[\s:-]*([0-9]+\.[0-9]+(?:\.[0-9]+)?)', memory)
            if version_match:
                release_version = version_match.group(1)
                break

    # Replace basic placeholders
    report_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Extract username from test_id (e.g. YYYYMMDD_HHMMSS_username)
    username = ""
    parts = test_id.split("_", 2)
    if len(parts) >= 3:
        username = parts[2]
        
    report_content = template.replace(
        "Report Date:", f"Report Date: {report_date}"
    ).replace(
        "Test Cycle:", f"Test Cycle: {test_id}"
    ).replace(
        "Project:", f"Project: {project_name}" 
    ).replace(
        "Release Version:", f"Release Version: {release_version}"
    ).replace(
        "QA Owner:", f"QA Owner: {username}"
    )
    
    # Create directories for report
    reports_dir = Path("qa_reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Dynamically build the Test Case Results and Defects sections
    part1_end = report_content.find("## 4. Test Case Results")
    part2_start = report_content.find("## 6. Automation Summary")
    
    if part1_end != -1 and part2_start != -1 and history:
        dynamic_content = "## 4. Test Case Results\n\n"
        passed_steps = []
        failed_steps = []
        
        display_step_num = 1
        for step in history:
            step = step or {}
            state = step.get("state") or {}
            
            # Skip initial about:blank pages
            url = state.get("url", "")
            if url == "about:blank":
                continue
            
            # Check tabs if url is not directly on state
            if not url and "tabs" in state:
                tabs = state.get("tabs", [])
                if tabs and isinstance(tabs, list) and tabs[0].get("url") == "about:blank":
                    continue

            model_output = step.get("model_output") or {}
            current_state = model_output.get("current_state") or {}
            evaluation = current_state.get("evaluation_previous_goal") or ""
            next_goal = current_state.get("next_goal") or ""
            
            is_fail = "fail" in evaluation.lower() or "error" in evaluation.lower()
            
            screenshot_b64 = state.get("screenshot", "")
            img_markdown = ""
            if screenshot_b64:
                # Embed the base64 screenshot directly in the markdown
                img_markdown = f"  ![Evidence](data:image/png;base64,{screenshot_b64})\n"
                
            step_duration = _format_step_duration(step)
            page_load_timing = _format_page_load_timing(step)
            browser_action_duration = _format_browser_action_duration(step)
            step_md = f"#### Step {display_step_num}: {next_goal or 'Execution'}\n"
            step_md += f"- Status: {'Failed' if is_fail else 'Passed'}\n"
            step_md += f"- Details: {evaluation}\n"
            step_md += f"- Duration: {step_duration}\n"
            if browser_action_duration != "N/A":
                step_md += f"- Browser Action: {browser_action_duration}\n"
            if page_load_timing != "N/A" and page_load_timing != "N/A (no full page navigation)":
                step_md += f"- Page Load: {page_load_timing}\n"
            if img_markdown:
                step_md += f"- Evidence:\n\n{img_markdown}\n"
            step_md += "---\n\n"
            
            if is_fail:
                failed_steps.append(step_md)
            else:
                passed_steps.append(step_md)
            
            display_step_num += 1
                
        if passed_steps:
            dynamic_content += "### ✅ Passed Test Steps\n" + "".join(passed_steps)
        if failed_steps:
            dynamic_content += "### ❌ Failed Test Steps\n" + "".join(failed_steps)
            
        if failed_steps:
            dynamic_content += "## 5. Defects Summary\n\n"
            for i, f_step in enumerate(failed_steps):
                dynamic_content += f"### DEF-{101+i}: Issue in step\n"
                dynamic_content += "- Severity: High\n- Status: Open\n\n"
            dynamic_content += "---\n\n"
        
        total_tests = len(passed_steps) + len(failed_steps)
        passed_tests = len(passed_steps)
        failed_tests = len(failed_steps)
        
        report_content = report_content[:part1_end] + dynamic_content
        
        # Replace the test execution summary table numbers
        report_content = report_content.replace(
            "| Total Test Cases | |", f"| Total Test Cases | {total_tests} |"
        ).replace(
            "| Executed | |", f"| Executed | {total_tests} |"
        ).replace(
            "| Passed | |", f"| Passed | {passed_tests} |"
        ).replace(
            "| Failed | |", f"| Failed | {failed_tests} |"
        )
    
    report_filename = f"qa_report_{test_id}.md"
    report_path = reports_dir / report_filename
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    return str(report_path)

def create_results_tab(ui_manager: WebuiManager):
    with gr.Column():
        gr.Markdown("### Previous Test Results")
        
        test_runs = get_test_runs()
        initial_run = test_runs[0] if test_runs else None
        initial_text, initial_gif = load_test_details(initial_run)
        initial_report = generate_qa_report(initial_run) if initial_run else None
        
        with gr.Row():
            test_dropdown = gr.Dropdown(
                choices=test_runs,
                value=initial_run,
                label="Select Test Run",
                interactive=True
            )
            refresh_btn = gr.Button("🔄 Refresh List", size="sm")
            download_btn = gr.DownloadButton("💾 Download Report", value=initial_report, size="sm")
            
        with gr.Row():
            with gr.Column(scale=1):
                test_details_md = gr.Markdown(value=initial_text if initial_run else "Select a test run to view details.")
            with gr.Column(scale=1):
                test_gif = gr.Image(value=initial_gif, label="Test Recording", interactive=False)
                
        def update_list():
            runs = get_test_runs()
            return gr.update(choices=runs)
            
        refresh_btn.click(
            fn=update_list,
            outputs=[test_dropdown]
        )
        
        def update_test_selection(test_id):
            text, gif = load_test_details(test_id)
            report_path = generate_qa_report(test_id)
            return text, gif, report_path
            
        test_dropdown.change(
            fn=update_test_selection,
            inputs=[test_dropdown],
            outputs=[test_details_md, test_gif, download_btn]
        )

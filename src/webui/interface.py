import base64

import gradio as gr

from src.webui.components.agent_settings_tab import create_agent_settings_tab
from src.webui.components.browser_settings_tab import create_browser_settings_tab
from src.webui.components.browser_use_agent_tab import create_browser_use_agent_tab
from src.webui.components.load_save_config_tab import create_load_save_config_tab
from src.webui.components.results_tab import create_results_tab
from src.webui.webui_manager import WebuiManager


def get_favicon_base64():
    try:
        with open("favicon.ico", "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return ""


favicon_base64 = get_favicon_base64()

theme_map = {
    "Default": gr.themes.Default(),
    "Soft": gr.themes.Soft(),
    "Monochrome": gr.themes.Monochrome(),
    "Glass": gr.themes.Glass(),
    "Origin": gr.themes.Origin(),
    "Citrus": gr.themes.Citrus(),
    "Ocean": gr.themes.Ocean(),
    "Base": gr.themes.Base(),
}


def create_ui(theme_name="Ocean"):
    css = """
    .gradio-container {
        width: 70vw !important; 
        max-width: 70% !important; 
        margin-left: auto !important;
        margin-right: auto !important;
        padding-top: 10px !important;
    }
    footer { visibility: hidden; }
    .header-text {
        text-align: center;
        margin-bottom: 20px;
    }
    .custom-textbox textarea {
        overflow-y: scroll !important;
        scrollbar-width: thin !important;
        scrollbar-color: #888 transparent !important;
        min-height: 200px !important;
    }
    .custom-textbox textarea::-webkit-scrollbar {
        width: 8px !important;
    }
    .custom-textbox textarea::-webkit-scrollbar-track {
        background: transparent !important;
        border-radius: 4px !important;
    }
    .custom-textbox textarea::-webkit-scrollbar-thumb {
        background: #888 !important;
        border-radius: 4px !important;
    }
    .custom-textbox textarea::-webkit-scrollbar-thumb:hover {
        background: #555 !important;
    }
    .tab-header-text {
        text-align: center;
    }
    .theme-section {
        margin-bottom: 10px;
        padding: 15px;
        border-radius: 10px;
    }
    """

    # dark mode in default
    js_func = """
    function refresh() {
        const url = new URL(window.location);

        if (url.searchParams.get('__theme') !== 'dark') {
            url.searchParams.set('__theme', 'dark');
            window.location.href = url.href;
        }
    }
    """

    ui_manager = WebuiManager()

    with gr.Blocks(
        title="QA Browser Agent | DonTouch AI",
        theme=theme_map[theme_name],
        css=css,
        js=js_func,
    ) as demo:
        with gr.Row():
            img_tag = (
                f'<img src="data:image/x-icon;base64,{favicon_base64}" width="32" style="display: inline-block; vertical-align: middle; margin-right: 8px;">'
                if favicon_base64
                else "🌐"
            )
            gr.Markdown(
                f"""
                # {img_tag} QA Browser Agent
                ### QA Tasks Automation
                """,
                elem_classes=["header-text"],
            )

        with gr.Tabs(selected="run_agent") as tabs:
            with gr.TabItem("⚙️ Agent Settings"):
                create_agent_settings_tab(ui_manager)

            with gr.TabItem("🌐 Browser Settings"):
                create_browser_settings_tab(ui_manager)

            with gr.TabItem("🤖 Run Agent", id="run_agent"):
                create_browser_use_agent_tab(ui_manager)

            with gr.TabItem("📄 Results"):
                create_results_tab(ui_manager)

            # with gr.TabItem("🎁 Agent Marketplace"):
            #     gr.Markdown(
            #         """
            #         ### Agents built on Browser-Use
            #         """,
            #         elem_classes=["tab-header-text"],
            #     )
            #     with gr.Tabs():
            #         with gr.TabItem("Deep Research"):
            #             create_deep_research_agent_tab(ui_manager)

            with gr.TabItem("📁 Load & Save Config"):
                create_load_save_config_tab(ui_manager)

    return demo

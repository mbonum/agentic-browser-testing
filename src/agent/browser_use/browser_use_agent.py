from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import time
from pathlib import Path

# from lmnr.sdk.decorators import observe
from browser_use.agent.gif import create_history_gif
from browser_use.agent.service import Agent, AgentHookFunc
from browser_use.agent.views import (
    ActionResult,
    AgentHistory,
    AgentHistoryList,
    AgentStepInfo,
    ToolCallingMethod,
)
from browser_use.browser.views import BrowserStateHistory
from browser_use.utils import time_execution_async
from dotenv import load_dotenv
from browser_use.agent.message_manager.utils import is_model_without_tool_support
from src.utils.secret_scrubber import scrub_history

load_dotenv()
logger = logging.getLogger(__name__)

SKIP_LLM_API_KEY_VERIFICATION = (
        os.environ.get("SKIP_LLM_API_KEY_VERIFICATION", "false").lower()[0] in "ty1"
)


class BrowserUseAgent(Agent):
    async def multi_act(self, *args, **kwargs) -> list[ActionResult]:
        start_time = time.perf_counter()
        try:
            return await super().multi_act(*args, **kwargs)
        finally:
            self._last_browser_action_duration_ms = (time.perf_counter() - start_time) * 1000

    async def _capture_latest_page_load_timing(self) -> None:
        history = self.state.history.history
        if not history:
            return

        latest_history_index = len(history) - 1
        if not hasattr(self, "_page_load_timings_by_history_index"):
            self._page_load_timings_by_history_index = {}
            self._browser_action_durations_by_history_index = {}
            self._last_navigation_timing_signature = None

        action_duration_ms = getattr(self, "_last_browser_action_duration_ms", None)
        if (
            action_duration_ms is not None
            and latest_history_index not in self._browser_action_durations_by_history_index
        ):
            self._browser_action_durations_by_history_index[latest_history_index] = action_duration_ms

        if latest_history_index in self._page_load_timings_by_history_index:
            return

        page = getattr(self.browser_context, "agent_current_page", None)
        if not page:
            return

        try:
            timing = await page.evaluate(
                """() => {
                    const navigation = performance.getEntriesByType('navigation')[0];
                    if (!navigation) return null;

                    return {
                        url: navigation.name,
                        type: navigation.type,
                        startTime: navigation.startTime,
                        durationMs: navigation.duration,
                        domContentLoadedMs: navigation.domContentLoadedEventEnd,
                        loadEventEndMs: navigation.loadEventEnd,
                        responseStartMs: navigation.responseStart,
                        responseEndMs: navigation.responseEnd
                    };
                }"""
            )
        except Exception as exc:
            logger.debug(f"Failed to capture page load timing: {exc}")
            return

        if not timing:
            return

        signature = (
            timing.get("url"),
            timing.get("type"),
            timing.get("startTime"),
            timing.get("responseEndMs"),
            timing.get("loadEventEndMs"),
        )
        timing["isNewNavigation"] = signature != self._last_navigation_timing_signature
        self._last_navigation_timing_signature = signature
        self._page_load_timings_by_history_index[latest_history_index] = timing

    def save_history(self, file_path: str | Path | None = None) -> None:
        """Save history and include browser page-load timing captured during the run."""
        if not file_path:
            file_path = "AgentHistory.json"

        data = self.state.history.model_dump()
        page_load_timings = getattr(self, "_page_load_timings_by_history_index", {})
        browser_action_durations = getattr(self, "_browser_action_durations_by_history_index", {})
        for index, timing in page_load_timings.items():
            if index >= len(data["history"]):
                continue

            metadata = data["history"][index].get("metadata") or {}
            metadata["page_load_timing"] = timing
            data["history"][index]["metadata"] = metadata

        for index, duration_ms in browser_action_durations.items():
            if index >= len(data["history"]):
                continue

            metadata = data["history"][index].get("metadata") or {}
            metadata["browser_action_duration_ms"] = duration_ms
            data["history"][index]["metadata"] = metadata

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _set_tool_calling_method(self) -> ToolCallingMethod | None:
        tool_calling_method = self.settings.tool_calling_method
        if tool_calling_method == 'auto':
            if is_model_without_tool_support(self.model_name):
                return 'raw'
            elif self.chat_model_library == 'ChatGoogleGenerativeAI':
                return None
            elif self.chat_model_library == 'ChatOpenAI':
                return 'function_calling'
            elif self.chat_model_library == 'AzureChatOpenAI':
                return 'function_calling'
            else:
                return None
        else:
            return tool_calling_method

    @time_execution_async("--run (agent)")
    async def run(
            self, max_steps: int = 100, on_step_start: AgentHookFunc | None = None,
            on_step_end: AgentHookFunc | None = None
    ) -> AgentHistoryList:
        """Execute the task with maximum number of steps"""

        loop = asyncio.get_event_loop()

        # Set up the Ctrl+C signal handler with callbacks specific to this agent
        from browser_use.utils import SignalHandler

        signal_handler = SignalHandler(
            loop=loop,
            pause_callback=self.pause,
            resume_callback=self.resume,
            custom_exit_callback=None,  # No special cleanup needed on forced exit
            exit_on_second_int=True,
        )
        signal_handler.register()

        try:
            self._log_agent_run()

            # Execute initial actions if provided
            if self.initial_actions:
                result = await self.multi_act(self.initial_actions, check_for_new_elements=False)
                self.state.last_result = result

            for step in range(max_steps):
                # Check if waiting for user input after Ctrl+C
                if self.state.paused:
                    signal_handler.wait_for_resume()
                    signal_handler.reset()

                # Check if we should stop due to too many failures
                if self.state.consecutive_failures >= self.settings.max_failures:
                    logger.error(f'❌ Stopping due to {self.settings.max_failures} consecutive failures')
                    break

                # Check control flags before each step
                if self.state.stopped:
                    logger.info('Agent stopped')
                    break

                while self.state.paused:
                    await asyncio.sleep(0.2)  # Small delay to prevent CPU spinning
                    if self.state.stopped:  # Allow stopping while paused
                        break

                if on_step_start is not None:
                    await on_step_start(self)

                step_info = AgentStepInfo(step_number=step, max_steps=max_steps)
                await self.step(step_info)
                await self._capture_latest_page_load_timing()

                if on_step_end is not None:
                    await on_step_end(self)

                if self.state.history.is_done():
                    if self.settings.validate_output and step < max_steps - 1:
                        if not await self._validate_output():
                            continue

                    await self.log_completion()
                    break
            else:
                error_message = 'Failed to complete task in maximum steps'

                self.state.history.history.append(
                    AgentHistory(
                        model_output=None,
                        result=[ActionResult(error=error_message, include_in_memory=True)],
                        state=BrowserStateHistory(
                            url='',
                            title='',
                            tabs=[],
                            interacted_element=[],
                            screenshot=None,
                        ),
                        metadata=None,
                    )
                )

                logger.info(f'❌ {error_message}')

            return self.state.history

        except KeyboardInterrupt:
            # Already handled by our signal handler, but catch any direct KeyboardInterrupt as well
            logger.info('Got KeyboardInterrupt during execution, returning current history')
            return self.state.history

        finally:
            # Unregister signal handlers before cleanup
            signal_handler.unregister()

            if self.settings.save_playwright_script_path:
                logger.info(
                    f'Agent run finished. Attempting to save Playwright script to: {self.settings.save_playwright_script_path}'
                )
                try:
                    # Extract sensitive data keys if sensitive_data is provided
                    keys = list(self.sensitive_data.keys()) if self.sensitive_data else None
                    # Pass browser and context config to the saving method
                    self.state.history.save_as_playwright_script(
                        self.settings.save_playwright_script_path,
                        sensitive_data_keys=keys,
                        browser_config=self.browser.config,
                        context_config=self.browser_context.config,
                    )
                except Exception as script_gen_err:
                    # Log any error during script generation/saving
                    logger.error(f'Failed to save Playwright script: {script_gen_err}', exc_info=True)

            await self.close()

            if self.settings.generate_gif:
                output_path: str = 'agent_history.gif'
                if isinstance(self.settings.generate_gif, str):
                    output_path = self.settings.generate_gif

                # Scrub sensitive data from task and history before creating GIF
                scrubbed_task = self.task
                secrets_list = []

                if self.sensitive_data:
                    for secret_value in self.sensitive_data.values():
                        if secret_value:
                            scrubbed_task = scrubbed_task.replace(secret_value, "******")
                            secrets_list.append(secret_value)

                # Deep copy and scrub history
                scrubbed_history = copy.deepcopy(self.state.history)
                if secrets_list:
                    scrub_history(scrubbed_history, secrets_list)
                    logger.info(f"Scrubbed {len(secrets_list)} secrets from GIF history")
                    logger.warning(
                        "Note: Screenshots in GIF may still show secrets if they were visible on screen. "
                        "For complete security with passwords, disable GIF generation."
                    )

                create_history_gif(task=scrubbed_task, history=scrubbed_history, output_path=output_path)

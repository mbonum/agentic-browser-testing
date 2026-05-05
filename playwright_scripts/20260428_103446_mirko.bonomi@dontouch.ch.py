import asyncio
import json
import os
import sys
from pathlib import Path
import urllib.parse
from playwright.async_api import async_playwright, Page, BrowserContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

SENSITIVE_DATA = {}


# --- Helper Functions (from playwright_script_helpers.py) ---
from playwright.async_api import Page


# --- Helper Function for Replacing Sensitive Data ---
def replace_sensitive_data(text: str, sensitive_map: dict) -> str:
	"""Replaces sensitive data placeholders in text."""
	if not isinstance(text, str):
		return text
	for placeholder, value in sensitive_map.items():
		replacement_value = str(value) if value is not None else ''
		text = text.replace(f'<secret>{placeholder}</secret>', replacement_value)
	return text


# --- Helper Function for Robust Action Execution ---
class PlaywrightActionError(Exception):
	"""Custom exception for errors during Playwright script action execution."""

	pass


async def _try_locate_and_act(page: Page, selector: str, action_type: str, text: str | None = None, step_info: str = '') -> None:
	"""
	Attempts an action (click/fill) with XPath fallback by trimming prefixes.
	Raises PlaywrightActionError if the action fails after all fallbacks.
	"""
	print(f'Attempting {action_type} ({step_info}) using selector: {repr(selector)}')
	original_selector = selector
	MAX_FALLBACKS = 50  # Increased fallbacks
	# Increased timeouts for potentially slow pages
	INITIAL_TIMEOUT = 10000  # Milliseconds for the first attempt (10 seconds)
	FALLBACK_TIMEOUT = 1000  # Shorter timeout for fallback attempts (1 second)

	try:
		locator = page.locator(selector).first
		if action_type == 'click':
			await locator.click(timeout=INITIAL_TIMEOUT)
		elif action_type == 'fill' and text is not None:
			await locator.fill(text, timeout=INITIAL_TIMEOUT)
		else:
			# This case should ideally not happen if called correctly
			raise PlaywrightActionError(f"Invalid action_type '{action_type}' or missing text for fill. ({step_info})")
		print(f"  Action '{action_type}' successful with original selector.")
		await page.wait_for_timeout(500)  # Wait after successful action
		return  # Successful exit
	except Exception as e:
		print(f"  Warning: Action '{action_type}' failed with original selector ({repr(selector)}): {e}. Starting fallback...")

		# Fallback only works for XPath selectors
		if not selector.startswith('xpath='):
			# Raise error immediately if not XPath, as fallback won't work
			raise PlaywrightActionError(
				f"Action '{action_type}' failed. Fallback not possible for non-XPath selector: {repr(selector)}. ({step_info})"
			)

		xpath_parts = selector.split('=', 1)
		if len(xpath_parts) < 2:
			raise PlaywrightActionError(
				f"Action '{action_type}' failed. Could not extract XPath string from selector: {repr(selector)}. ({step_info})"
			)
		xpath = xpath_parts[1]  # Correctly get the XPath string

		segments = [seg for seg in xpath.split('/') if seg]

		for i in range(1, min(MAX_FALLBACKS + 1, len(segments))):
			trimmed_xpath_raw = '/'.join(segments[i:])
			fallback_xpath = f'xpath=//{trimmed_xpath_raw}'

			print(f'    Fallback attempt {i}/{MAX_FALLBACKS}: Trying selector: {repr(fallback_xpath)}')
			try:
				locator = page.locator(fallback_xpath).first
				if action_type == 'click':
					await locator.click(timeout=FALLBACK_TIMEOUT)
				elif action_type == 'fill' and text is not None:
					try:
						await locator.clear(timeout=FALLBACK_TIMEOUT)
						await page.wait_for_timeout(100)
					except Exception as clear_error:
						print(f'    Warning: Failed to clear field during fallback ({step_info}): {clear_error}')
					await locator.fill(text, timeout=FALLBACK_TIMEOUT)

				print(f"    Action '{action_type}' successful with fallback selector: {repr(fallback_xpath)}")
				await page.wait_for_timeout(500)
				return  # Successful exit after fallback
			except Exception as fallback_e:
				print(f'    Fallback attempt {i} failed: {fallback_e}')
				if i == MAX_FALLBACKS:
					# Raise exception after exhausting fallbacks
					raise PlaywrightActionError(
						f"Action '{action_type}' failed after {MAX_FALLBACKS} fallback attempts. Original selector: {repr(original_selector)}. ({step_info})"
					)

	# This part should not be reachable if logic is correct, but added as safeguard
	raise PlaywrightActionError(f"Action '{action_type}' failed unexpectedly for {repr(original_selector)}. ({step_info})")

# --- End Helper Functions ---
async def run_generated_script():
    global SENSITIVE_DATA
    async with async_playwright() as p:
        browser = None
        context = None
        page = None
        exit_code = 0 # Default success exit code
        try:
            print('Launching chromium browser...')
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(permissions=['clipboard-read', 'clipboard-write'], no_viewport=True)
            print('Browser context created.')
            # Initial page handling
            if context.pages:
                page = context.pages[0]
                print('Using initial page provided by context.')
            else:
                page = await context.new_page()
                print('Created a new page as none existed.')
            print('\n--- Starting Generated Script Execution ---')

            # --- Step 1 ---
            # Action 1
            print(f"Switching to tab with page_id 4 (Step 1, Action 1)")
            if 4 < len(context.pages):
                page = context.pages[4]
                await page.bring_to_front()
                await page.wait_for_load_state('load', timeout=15000)
                await page.wait_for_timeout(500)
            else:
                print(f"  Warning: Tab with page_id 4 not found to switch (Step 1, Action 1)", file=sys.stderr)

            # --- Step 2 ---
            # Action 2
            await _try_locate_and_act(page, "xpath=//html/body/app-root/ion-app/div/div/ion-router-outlet/ng-component/ion-content/my-ui-page-content/my-auth-login-form/form/my-ui-phone-input/ion-input/label/div[3]/input", "fill", text=replace_sensitive_data("3457009173", SENSITIVE_DATA), step_info="Step 2, Action 1")
            # Action 3
            await _try_locate_and_act(page, "xpath=//html/body/app-root/ion-app/div/div/ion-router-outlet/ng-component/ion-content/my-ui-page-content/my-auth-login-form/form/my-ui-password-input/ion-input/label/div[3]/input", "fill", text=replace_sensitive_data("Topolino5", SENSITIVE_DATA), step_info="Step 2, Action 2")

            # --- Step 3 ---
            # Action 4
            await _try_locate_and_act(page, "xpath=//html/body/app-root/ion-app/div/div/ion-router-outlet/ng-component/ion-content/my-ui-page-content/my-auth-login-form/form/ion-button", "click", step_info="Step 3, Action 1")

            # --- Step 4 ---
            # Action 5
            print(f"Scrolling down by 700 pixels (Step 4, Action 1)")
            await page.evaluate('window.scrollBy(0, 700)')
            await page.wait_for_timeout(500)

            # --- Step 5 ---
            # Action 6
            print(f"Scrolling up by 1200 pixels (Step 5, Action 1)")
            await page.evaluate('window.scrollBy(0, -1200)')
            await page.wait_for_timeout(500)

            # --- Step 6 ---
            # Action 7
            await _try_locate_and_act(page, "xpath=//html/body/app-root/ion-app/div/div/ion-router-outlet/ng-component/ion-header/my-main-header/ion-toolbar/my-profile-profile-select/my-ui-button-group/ion-button[1]", "click", step_info="Step 6, Action 1")

            # --- Step 7 ---
            # Action 8
            print(f"Scrolling down by 900 pixels (Step 7, Action 1)")
            await page.evaluate('window.scrollBy(0, 900)')
            await page.wait_for_timeout(500)

            # --- Step 8 ---
            # Action 9
            await _try_locate_and_act(page, "xpath=//html/body/app-root/ion-app/div/div/ion-router-outlet/ng-component/ion-footer/my-main-footer/ion-tab-bar/ion-tab-button[1]/ion-label", "click", step_info="Step 8, Action 1")

            # --- Step 9 ---
            # Action 10
            await _try_locate_and_act(page, "xpath=//html/body/app-root/ion-app/div/div/ion-router-outlet/ng-component/ion-header/my-main-header/ion-toolbar/my-profile-profile-select/my-ui-button-group/ion-button[2]", "click", step_info="Step 9, Action 1")

            # --- Step 10 ---
            # Action 11
            await _try_locate_and_act(page, "xpath=//html/body/app-root/ion-app/ion-popover/div/ion-content/ion-list/ion-item[2]/ion-label", "click", step_info="Step 10, Action 1")

            # --- Step 11 ---
            # Action 12
            print("\n--- Task marked as Done by agent (Step 11, Action 1) ---")
            print(f"Agent reported success: True")
            # Final Message from agent (may contain placeholders):
            final_message = replace_sensitive_data("Task completed. Step-by-step issue report:\n1. Go to https://lc-my.escort-advisor.com/ \u2014 Completed successfully. Issues: none.\n2. Login with phone number 3457009173 and password Topolino5 \u2014 Completed successfully. Issues: none observed; login appeared successful because the account/logout menu became available afterward.\n3. Logout \u2014 Completed successfully. Issues: none; clicking Logout returned the site to the login page.\nOverall: all requested steps were completed without visible issues.", SENSITIVE_DATA)
            print(final_message)
        except PlaywrightActionError as pae:
            print(f'\n--- Playwright Action Error: {pae} ---', file=sys.stderr)
            exit_code = 1
        except Exception as e:
            print(f'\n--- An unexpected error occurred: {e} ---', file=sys.stderr)
            import traceback
            traceback.print_exc()
            exit_code = 1
        finally:
            print('\n--- Generated Script Execution Finished ---')
            print('Closing browser/context...')
            if context:
                 try: await context.close()
                 except Exception as ctx_close_err: print(f'  Warning: could not close context: {ctx_close_err}', file=sys.stderr)
            if browser:
                 try: await browser.close()
                 except Exception as browser_close_err: print(f'  Warning: could not close browser: {browser_close_err}', file=sys.stderr)
            print('Browser/context closed.')
            # Exit with the determined exit code
            if exit_code != 0:
                print(f'Script finished with errors (exit code {exit_code}).', file=sys.stderr)
                sys.exit(exit_code)

# --- Script Entry Point ---
if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_generated_script())
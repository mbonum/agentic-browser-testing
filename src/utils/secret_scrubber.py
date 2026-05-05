"""Utility for scrubbing sensitive data from agent history and outputs."""

import copy
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def scrub_secrets_from_dict(data: Dict[str, Any], secrets: List[str]) -> Dict[str, Any]:
    """
    Recursively scrub secrets from a dictionary by replacing secret values with ******.

    Args:
        data: Dictionary to scrub
        secrets: List of secret values to replace

    Returns:
        Scrubbed dictionary (deep copy)
    """
    if not secrets:
        return data

    scrubbed = copy.deepcopy(data)

    def scrub_value(value):
        if isinstance(value, str):
            for secret in secrets:
                if secret and secret in value:
                    value = value.replace(secret, "******")
            return value
        elif isinstance(value, dict):
            return {k: scrub_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [scrub_value(item) for item in value]
        else:
            return value

    return scrub_value(scrubbed)


def scrub_history(history, secrets: List[str]):
    """
    Scrub secrets from agent history object.
    Modifies history entries in place to replace secret values with ******.

    Args:
        history: AgentHistoryList object
        secrets: List of secret values to replace
    """
    if not secrets or not hasattr(history, 'history'):
        return

    for entry in history.history:
        # Scrub model_output if present
        if entry.model_output:
            try:
                # Get the model output as dict
                output_dict = entry.model_output.model_dump()

                # Scrub secrets from the dict
                scrubbed_dict = scrub_secrets_from_dict(output_dict, secrets)

                # Reconstruct the model_output from scrubbed dict
                # Note: This assumes the model_output class has a parse_obj or similar method
                # If not available, we'll just log a warning
                if hasattr(entry.model_output.__class__, 'parse_obj'):
                    entry.model_output = entry.model_output.__class__.parse_obj(scrubbed_dict)
                elif hasattr(entry.model_output.__class__, 'model_validate'):
                    entry.model_output = entry.model_output.__class__.model_validate(scrubbed_dict)
                else:
                    logger.warning("Cannot reconstruct model_output after scrubbing, secrets may still be present")

            except Exception as e:
                logger.error(f"Error scrubbing model_output: {e}", exc_info=True)

        # Scrub action results if present
        if hasattr(entry, 'result') and entry.result:
            for result in entry.result:
                if hasattr(result, 'extracted_content') and result.extracted_content:
                    for secret in secrets:
                        if secret:
                            result.extracted_content = result.extracted_content.replace(secret, "******")

                if hasattr(result, 'error') and result.error:
                    for secret in secrets:
                        if secret:
                            result.error = result.error.replace(secret, "******")

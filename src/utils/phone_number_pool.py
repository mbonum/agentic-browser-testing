import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple


DEFAULT_POOL_PATH = Path("prompts") / "phone_number_pool.json"
PHONE_TOKEN_PATTERN = re.compile(
    r"\{\{\s*(QAS|ST)_(SOURCE|DESTINATION)_PHONE\s*\}\}",
    re.IGNORECASE,
)


class PhoneNumberPoolError(RuntimeError):
    pass


def resolve_phone_placeholders(
    task: str,
    pool_path: Path = DEFAULT_POOL_PATH,
) -> Tuple[str, Dict[str, Dict[str, str]]]:
    matches = list(PHONE_TOKEN_PATTERN.finditer(task))
    if not matches:
        return task, {}

    if not pool_path.exists():
        raise PhoneNumberPoolError(
            f"Phone number pool not found: {pool_path}. Add available pairs before running this prompt."
        )

    data = _load_pool(pool_path)
    needed_envs = sorted({match.group(1).lower() for match in matches})
    chosen_pairs = {}

    for env_name in needed_envs:
        pair_index, pair = _find_available_pair(data, env_name)
        chosen_pairs[env_name] = {
            "source": str(pair["source"]),
            "destination": str(pair["destination"]),
        }
        data[env_name][pair_index]["used"] = True
        data[env_name][pair_index]["used_at"] = datetime.now().isoformat(timespec="seconds")

    _save_pool(pool_path, data)

    def replace_token(match: re.Match) -> str:
        env_name = match.group(1).lower()
        role = match.group(2).lower()
        return chosen_pairs[env_name]["source" if role == "source" else "destination"]

    return PHONE_TOKEN_PATTERN.sub(replace_token, task), chosen_pairs


def _load_pool(pool_path: Path) -> Dict:
    try:
        with pool_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise PhoneNumberPoolError(f"Phone number pool contains invalid JSON: {pool_path}") from exc

    if not isinstance(data, dict):
        raise PhoneNumberPoolError("Phone number pool must be a JSON object.")

    for env_name in ("qas", "st"):
        data.setdefault(env_name, [])
        if not isinstance(data[env_name], list):
            raise PhoneNumberPoolError(f"Phone number pool entry '{env_name}' must be a list.")

    return data


def _find_available_pair(data: Dict, env_name: str) -> Tuple[int, Dict]:
    for index, pair in enumerate(data.get(env_name, [])):
        if not isinstance(pair, dict):
            continue
        if pair.get("used"):
            continue
        if pair.get("source") and pair.get("destination"):
            return index, pair

    raise PhoneNumberPoolError(
        f"No available {env_name.upper()} phone number pairs left in {DEFAULT_POOL_PATH}. "
        "Add a new pair with used=false."
    )


def _save_pool(pool_path: Path, data: Dict) -> None:
    tmp_path = pool_path.with_suffix(pool_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")
    os.replace(tmp_path, pool_path)

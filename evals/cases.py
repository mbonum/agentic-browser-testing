"""Eval case definitions and loader.

A case is a YAML file in ``evals/cases/``. It points at an existing
prompt (or an inline task), declares the human-labeled expected outcome,
and lists grounded assertions used as the independent success signal.

Example (``evals/cases/example.yaml``)::

    id: login-logout-core
    description: Login then logout on core.test.k8s
    prompt_file: e2e-login-logout-core-test-k8s.md   # relative to prompts/
    expected_status: pass            # human ground truth: pass | fail
    max_steps: 40
    tags: [smoke, auth]
    assertions:
      - {type: is_done}
      - {type: no_errors}
      - {type: history_contains_text, value: "logout"}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROMPTS_DIR = Path("prompts")


@dataclass
class Case:
    id: str
    description: str = ""
    task: str = ""              # resolved prompt text (filled by loader)
    prompt_file: str | None = None
    expected_status: str | None = None  # "pass" | "fail" | None (unlabeled)
    max_steps: int | None = None
    tags: list[str] = field(default_factory=list)
    assertions: list[dict[str, Any]] = field(default_factory=list)
    source_path: str = ""

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.id:
            problems.append("missing 'id'")
        if not self.task:
            problems.append("empty task (prompt_file missing/empty and no inline 'task')")
        if self.expected_status not in (None, "pass", "fail"):
            problems.append(f"expected_status must be pass|fail, got {self.expected_status!r}")
        for i, a in enumerate(self.assertions):
            if "type" not in a:
                problems.append(f"assertion[{i}] missing 'type'")
        return problems


def load_case(path: str | Path) -> Case:
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    task = raw.get("task", "") or ""
    prompt_file = raw.get("prompt_file")
    if prompt_file and not task:
        prompt_path = PROMPTS_DIR / prompt_file
        task = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    return Case(
        id=raw.get("id") or path.stem,
        description=raw.get("description", ""),
        task=task,
        prompt_file=prompt_file,
        expected_status=raw.get("expected_status"),
        max_steps=raw.get("max_steps"),
        tags=list(raw.get("tags") or []),
        assertions=list(raw.get("assertions") or []),
        source_path=str(path),
    )


def load_cases(cases_dir: str | Path, select_ids: list[str] | None = None) -> list[Case]:
    cases_dir = Path(cases_dir)
    files = sorted(p for p in cases_dir.glob("*.yaml") if not p.name.startswith("_"))
    cases = [load_case(p) for p in files]
    if select_ids:
        wanted = set(select_ids)
        cases = [c for c in cases if c.id in wanted]
    return cases

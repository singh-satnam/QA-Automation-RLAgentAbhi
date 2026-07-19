"""Framework-level test utilities — scaffolded into every project root by the harness.

DO NOT hand-edit per project and DO NOT have the LLM regenerate this. Fixes belong
in core/templates/utils.py so every project inherits them.

Import in any step def file:
    from utils import unique_suffix
"""
import random


def unique_suffix(length: int = 4) -> str:
    """Return a random numeric string of `length` digits (e.g. '4731').

    Append to any value that must be unique per test run to avoid collisions
    with existing data (project names, resource names, tags, etc.).

    Usage in a step def:
        name = f"{test_data['projectName']} {unique_suffix()}"
        scenario_context["project_name"] = name   # share with later steps
    """
    return str(random.randint(10 ** (length - 1), 10 ** length - 1))

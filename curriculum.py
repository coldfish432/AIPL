import time
from pathlib import Path

# 用途: Rule-based mini curriculum (no LLM yet)
def suggest_next_task(goal: str, backlog: dict):
    """
    Rule-based mini curriculum (no LLM yet).
    It only appends tasks that are 'time_for_certainty' and objectively verifiable.
    """
    return None


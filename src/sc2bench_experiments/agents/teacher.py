from __future__ import annotations

from typing import Any, Callable

from ..skill_registry import SkillRecord
from .common import create_platform_agent


def create_teacher_agent(
    call_llm: Callable[..., dict[str, Any]],
    *,
    skill: SkillRecord | None,
    **agent_options: Any,
):
    return create_platform_agent(call_llm, skill=skill, **agent_options)

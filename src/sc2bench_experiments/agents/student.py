from __future__ import annotations

from typing import Any, Callable

from ..skill_registry import SkillRecord
from .common import create_platform_agent


def make_student_call(
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float = 120.0,
    temperature: float = 0.0,
    thinking: bool = False,
) -> Callable[..., dict[str, Any]]:
    """Use the same OpenAI-compatible protocol for a served base or SFT model."""
    from agents.llm_agent import make_llm_call

    return make_llm_call(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout,
        temperature=temperature,
        thinking=thinking,
    )


def create_student_agent(
    call_llm: Callable[..., dict[str, Any]],
    *,
    skill: SkillRecord | None = None,
    **agent_options: Any,
):
    return create_platform_agent(call_llm, skill=skill, **agent_options)

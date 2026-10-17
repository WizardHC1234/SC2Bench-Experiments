from __future__ import annotations

from typing import Any, Callable

from ..skill_registry import SkillRecord


def create_platform_agent(
    call_llm: Callable[..., dict[str, Any]],
    *,
    skill: SkillRecord | None,
    **agent_options: Any,
):
    """Create SC2Bench's protocol agent while injecting an experiment-owned Skill."""
    from agents.llm_agent import LLMAgent

    agent = LLMAgent(call_llm, skill_name="none", **agent_options)
    agent.skill_name = skill.skill_id if skill else None
    agent.skill_text = skill.text if skill else ""
    return agent

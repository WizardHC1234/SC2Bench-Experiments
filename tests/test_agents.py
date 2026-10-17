from __future__ import annotations

import sys
import types
from pathlib import Path

from sc2bench_experiments.agents.common import create_platform_agent
from sc2bench_experiments.skill_registry import SkillRecord


def test_platform_agent_receives_experiment_skill(monkeypatch):
    package = types.ModuleType("agents")
    package.__path__ = []
    module = types.ModuleType("agents.llm_agent")

    class FakeAgent:
        def __init__(self, call_llm, *, skill_name, **options):
            self.call_llm = call_llm
            self.skill_name = skill_name
            self.skill_text = ""
            self.options = options

    module.LLMAgent = FakeAgent
    monkeypatch.setitem(sys.modules, "agents", package)
    monkeypatch.setitem(sys.modules, "agents.llm_agent", module)
    skill = SkillRecord(
        "terran/test",
        "# Test",
        "abc",
        "experiment",
        "1",
        Path("test.md"),
    )
    agent = create_platform_agent(lambda *_args, **_kwargs: {}, skill=skill, verbose=False)
    assert agent.skill_name == "terran/test"
    assert agent.skill_text == "# Test"
    assert agent.options == {"verbose": False}

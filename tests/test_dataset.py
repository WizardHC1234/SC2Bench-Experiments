import json
from pathlib import Path

from sc2bench_experiments.dataset import (
    SKILL_MARKER,
    build_dataset,
    strip_skill_block,
    to_decision_cycle_windows,
    to_llamafactory_messages,
    validate_dataset,
)


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_strip_skill_block_preserves_platform_prompt():
    messages = [
        {
            "role": "system",
            "content": "platform contract\n\n[Agent Skill: terran/test]\nsecret skill body",
        },
        {"role": "user", "content": "observation"},
    ]
    sanitized, removed = strip_skill_block(messages)
    assert removed is True
    assert sanitized[0]["content"] == "platform contract"
    assert SKILL_MARKER not in sanitized[0]["content"]
    assert messages[0]["content"].endswith("secret skill body")


def test_build_and_validate_episode_level_dataset(tmp_path):
    source = tmp_path / "raw"
    condition = source / "T1_test"
    _write_json(
        condition / "condition.json",
        {
            "condition_id": "T1_test",
            "teacher_condition": "skill",
            "skill_id": "terran/test",
            "skill_sha256": "abc",
        },
    )
    episode = condition / "batch_x" / "episodes" / "episode_x"
    _write_json(
        episode / "session.json",
        {
            "episode_id": "episode-x",
            "result": "Result.Victory",
            "tools": [{"name": "advance"}],
            "messages": [
                {
                    "role": "system",
                    "content": "platform\n\n[Agent Skill: terran/test]\nsecret",
                },
                {"role": "user", "content": "observation"},
                {
                    "role": "assistant",
                    "content": "advance",
                    "tool_calls": [
                        {
                            "id": "a",
                            "type": "function",
                            "function": {"name": "advance", "arguments": "{\"seconds\":5}"},
                        }
                    ],
                },
            ],
        },
    )
    _write_json(
        episode / "metrics.json",
        {
            "tool_calls": [],
            "model_calls": [],
            "summary": {
                "status": "completed",
                "result": "Result.Victory",
                "end_reason": "game_ended",
            },
        },
    )
    output = tmp_path / "processed"
    manifest = build_dataset(source, output, split_seed=1, ratios=(1.0, 0.0, 0.0))
    assert manifest["total_records"] == 1
    record = json.loads((output / "train.jsonl").read_text(encoding="utf-8"))
    assert record["student_input_contains_skill"] is False
    assert record["skill_block_removed"] is True
    assert record["messages"][0]["content"] == "platform"
    dataset_info = json.loads((output / "dataset_info.json").read_text(encoding="utf-8"))
    entry = dataset_info["sc2bench_terran_test_train"]
    assert entry["formatting"] == "openai"
    assert entry["tags"]["observation_tag"] == "tool"
    assert (output / entry["file_name"]).is_file()
    exported = json.loads((output / entry["file_name"]).read_text(encoding="utf-8"))
    assert exported["decision_index"] == 0
    assert exported["decision_count"] == 1
    assert exported["history_cycles"] == 1
    assert exported["decision_cycle_index"] == 0
    assert exported["decision_cycle_count"] == 1
    assert exported["tool_round_index"] == 0
    assert exported["target_phase"] == "advance"
    assert exported["target_tool_names"] == ["advance"]
    assert exported["target_content_present"] is True
    assert manifest["llamafactory"]["advance_policy"] == "preserve_all"
    assert manifest["llamafactory"]["target_distributions"]["phase"] == {"advance": 1}
    assert validate_dataset(output)["ok"] is True


def test_cycle_windows_keep_every_action_and_use_complete_cycle_history():
    messages = [
        {"role": "system", "content": "platform"},
        {"role": "user", "content": "observation 1"},
        {
            "role": "assistant",
            "content": "stage worker",
            "tool_calls": [
                {"type": "function", "function": {"name": "train", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "content": "staged"},
        {
            "role": "assistant",
            "content": "advance plan",
            "tool_calls": [
                {"type": "function", "function": {"name": "advance", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "content": "decision ready"},
        {"role": "user", "content": "observation 2"},
        {
            "role": "assistant",
            "content": "inspect route",
            "tool_calls": [
                {"type": "function", "function": {"name": "query_route", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "content": "route result"},
        {
            "role": "assistant",
            "content": "continue",
            "tool_calls": [
                {"type": "function", "function": {"name": "advance", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "content": "final receipt"},
    ]
    adapted = to_llamafactory_messages(messages)
    assert [item["role"] for item in adapted] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "tool",
        "assistant",
        "tool",
        "assistant",
    ]
    assert adapted[6]["content"].startswith("[Next Environment Observation]")
    assert adapted[-1]["role"] == "assistant"

    windows = to_decision_cycle_windows(messages, history_cycles=1)
    assert len(windows) == 4
    assert [row["target_phase"] for row in windows] == [
        "action",
        "advance",
        "query",
        "advance",
    ]
    assert [row["decision_cycle_index"] for row in windows] == [0, 0, 1, 1]
    assert [row["tool_round_index"] for row in windows] == [0, 1, 0, 1]
    assert all(row["decision_cycle_count"] == 2 for row in windows)
    assert all(row["messages"][-1].get("tool_calls") for row in windows)
    assert [item["role"] for item in windows[2]["messages"]] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "tool",
        "assistant",
    ]

    no_history = to_decision_cycle_windows(messages, history_cycles=0)
    assert [item["role"] for item in no_history[2]["messages"]] == [
        "system",
        "user",
        "assistant",
    ]


def test_cycle_windows_reject_cycle_without_advance():
    messages = [
        {"role": "system", "content": "platform"},
        {"role": "user", "content": "observation"},
        {
            "role": "assistant",
            "content": "stage only",
            "tool_calls": [
                {"type": "function", "function": {"name": "build", "arguments": "{}"}}
            ],
        },
    ]
    try:
        to_decision_cycle_windows(messages)
    except ValueError as error:
        assert "exactly one advance" in str(error)
    else:
        raise AssertionError("missing advance must be rejected")


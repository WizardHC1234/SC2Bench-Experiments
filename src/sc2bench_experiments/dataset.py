from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .config import canonical_sha256, file_sha256


SKILL_MARKER = "[Agent Skill:"
DATASET_SCHEMA_VERSION = "2"
LLAMAFACTORY_ADAPTER_VERSION = "openai-decision-cycle-windows-v2"


def strip_skill_block(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    copied = json.loads(json.dumps(messages, ensure_ascii=False))
    removed = False
    for message in copied:
        if message.get("role") != "system" or not isinstance(message.get("content"), str):
            continue
        content = message["content"]
        marker = content.find(SKILL_MARKER)
        if marker >= 0:
            message["content"] = content[:marker].rstrip()
            removed = True
            break
    return copied, removed


def to_llamafactory_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapt SC2's environment loop to LlamaFactory's OpenAI tool trajectory.

    SC2Bench emits ``assistant -> tool result(s) -> next user observation``.
    LlamaFactory expects ``assistant/function -> observation -> assistant/function``.
    Subsequent environment observations are therefore marked as tool observations;
    its OpenAI converter merges consecutive tool results. Final tool receipts are
    removed so the sample ends on the assistant action that should receive loss.
    """
    adapted: list[dict[str, Any]] = []
    for original in json.loads(json.dumps(messages, ensure_ascii=False)):
        role = original.get("role")
        if role == "user" and adapted and adapted[-1].get("role") == "tool":
            original = {
                "role": "tool",
                "content": "[Next Environment Observation]\n" + str(original.get("content") or ""),
            }
        adapted.append(original)

    while adapted and adapted[-1].get("role") == "tool":
        adapted.pop()

    aligned_roles: list[str] = []
    pending_tool = False
    for message in adapted:
        role = message.get("role")
        if role == "system" and not aligned_roles:
            continue
        if role == "tool":
            pending_tool = True
            continue
        if pending_tool:
            aligned_roles.append("observation")
            pending_tool = False
        if role == "assistant" and message.get("tool_calls"):
            aligned_roles.append("function")
        elif role in {"user", "assistant"}:
            aligned_roles.append(str(role))
        else:
            raise ValueError(f"unsupported message role for LlamaFactory: {role!r}")
    if pending_tool:
        raise ValueError("LlamaFactory trajectory ends with an observation")
    for index, role in enumerate(aligned_roles):
        allowed = {"user", "observation"} if index % 2 == 0 else {"assistant", "function"}
        if role not in allowed:
            raise ValueError(
                f"invalid LlamaFactory role order at {index}: {role!r}; roles={aligned_roles}"
            )
    if not aligned_roles or len(aligned_roles) % 2 != 0:
        raise ValueError("LlamaFactory trajectory must end with an assistant/function turn")
    return adapted


def _tool_names(message: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for tool_call in message.get("tool_calls") or []:
        function = tool_call.get("function") if isinstance(tool_call, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _target_phase(tool_names: list[str]) -> str:
    if "advance" in tool_names:
        return "advance"
    if tool_names and all(name.startswith("query") for name in tool_names):
        return "query"
    return "action"


def _decision_cycles(body: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Split a raw SC2Bench conversation into observation-to-advance cycles."""
    cycles: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for message in body:
        role = message.get("role")
        if role == "user":
            if current:
                cycles.append(current)
            current = [message]
        else:
            if not current:
                raise ValueError("conversation content appears before the first user observation")
            current.append(message)
    if current:
        cycles.append(current)

    for cycle_index, cycle in enumerate(cycles):
        assistant_messages = [message for message in cycle if message.get("role") == "assistant"]
        if not assistant_messages:
            raise ValueError(f"decision cycle {cycle_index} has no assistant decision")
        advance_turns = [
            message for message in assistant_messages if "advance" in _tool_names(message)
        ]
        if len(advance_turns) != 1:
            raise ValueError(
                f"decision cycle {cycle_index} must contain exactly one advance decision; "
                f"found {len(advance_turns)}"
            )
        if assistant_messages[-1] is not advance_turns[0]:
            raise ValueError(f"decision cycle {cycle_index} has an assistant decision after advance")
    return cycles


def to_decision_cycle_windows(
    messages: list[dict[str, Any]], *, history_cycles: int = 1
) -> list[dict[str, Any]]:
    """Create one supervised sample for every assistant tool-call decision.

    Context is selected by semantic SC2 decision cycles rather than by a raw
    number of assistant turns. A cycle starts at an environment observation and
    is closed by ``advance``. Every query, staged action and advance target is
    retained exactly once.
    """
    if type(history_cycles) is not int or history_cycles < 0:
        raise ValueError("history_cycles must be a non-negative integer")
    copied = json.loads(json.dumps(messages, ensure_ascii=False))
    system = copied[:1] if copied and copied[0].get("role") == "system" else []
    body = copied[len(system) :]
    cycles = _decision_cycles(body)
    windows: list[dict[str, Any]] = []
    for cycle_index, cycle in enumerate(cycles):
        history_start = max(0, cycle_index - history_cycles)
        history = [message for prior in cycles[history_start:cycle_index] for message in prior]
        tool_round_index = 0
        for target_position, message in enumerate(cycle):
            if message.get("role") != "assistant":
                continue
            tool_names = _tool_names(message)
            if not tool_names:
                raise ValueError(
                    f"decision cycle {cycle_index} contains an assistant turn without tool calls"
                )
            raw_window = [*system, *history, *cycle[: target_position + 1]]
            windows.append(
                {
                    "messages": to_llamafactory_messages(raw_window),
                    "decision_cycle_index": cycle_index,
                    "decision_cycle_count": len(cycles),
                    "tool_round_index": tool_round_index,
                    "target_phase": _target_phase(tool_names),
                    "target_tool_names": tool_names,
                    "target_tool_call_count": len(tool_names),
                    "target_content_present": bool(str(message.get("content") or "").strip()),
                }
            )
            tool_round_index += 1
    return windows


def _skill_slug(skill_id: str) -> str:
    if skill_id in {"", "none"}:
        return "no_skill"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", skill_id).strip("_").lower()
    return slug or "unknown_skill"


def _llamafactory_dataset_entry(file_name: str) -> dict[str, Any]:
    return {
        "file_name": file_name,
        "formatting": "openai",
        "columns": {"messages": "messages", "tools": "tools"},
        "tags": {
            "role_tag": "role",
            "content_tag": "content",
            "user_tag": "user",
            "assistant_tag": "assistant",
            "observation_tag": "tool",
            "function_tag": "function_call",
            "system_tag": "system",
        },
    }


def _episode_end(record_dir: Path) -> dict[str, Any]:
    """Read terminal status from metrics.json, with trajectory.json fallback."""
    metrics_path = record_dir / "metrics.json"
    if metrics_path.is_file():
        document = json.loads(metrics_path.read_text(encoding="utf-8"))
        summary = document.get("summary") if isinstance(document, dict) else None
        return summary if isinstance(summary, dict) else {}
    trajectory_path = record_dir / "trajectory.json"
    if not trajectory_path.is_file():
        return {}
    document = json.loads(trajectory_path.read_text(encoding="utf-8"))
    events = document.get("events") if isinstance(document, dict) else None
    if not isinstance(events, list):
        return {}
    for event in reversed(events):
        if isinstance(event, dict) and event.get("event_type") == "episode_end":
            payload = event.get("payload")
            return payload if isinstance(payload, dict) else {}
    return {}


def _split(episode_id: str, seed: int, ratios: tuple[float, float, float]) -> str:
    value = int(hashlib.sha256(f"{seed}:{episode_id}".encode()).hexdigest()[:12], 16)
    point = (value % 1_000_000) / 1_000_000
    if point < ratios[0]:
        return "train"
    if point < ratios[0] + ratios[1]:
        return "validation"
    return "test"


def _condition_manifests(root: Path) -> dict[Path, dict[str, Any]]:
    result = {}
    for path in root.glob("*/condition.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        result[path.parent.resolve()] = data
    return result


def _owning_condition(
    session_path: Path, manifests: dict[Path, dict[str, Any]]
) -> dict[str, Any] | None:
    resolved = session_path.resolve()
    matches = [data for directory, data in manifests.items() if directory in resolved.parents]
    return matches[0] if len(matches) == 1 else None


def _jsonl_write(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
            count += 1
    temp.replace(path)
    return count


def build_dataset(
    input_root: str | Path,
    output_root: str | Path,
    *,
    split_seed: int = 20261009,
    ratios: tuple[float, float, float] = (0.8, 0.1, 0.1),
    include_unfinished: bool = False,
    history_cycles: int = 1,
) -> dict[str, Any]:
    if len(ratios) != 3 or any(value < 0 for value in ratios) or abs(sum(ratios) - 1) > 1e-9:
        raise ValueError("ratios must be three non-negative values summing to 1")
    if type(history_cycles) is not int or history_cycles < 0:
        raise ValueError("history_cycles must be a non-negative integer")
    source = Path(input_root).resolve()
    destination = Path(output_root).resolve()
    manifests = _condition_manifests(source)
    if not manifests:
        raise ValueError(f"No condition.json files found below {source}")

    records: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
    excluded: list[dict[str, str]] = []
    seen: set[str] = set()
    for session_path in sorted(source.rglob("session.json")):
        condition = _owning_condition(session_path, manifests)
        if condition is None:
            excluded.append({"session": str(session_path), "reason": "condition_not_resolved"})
            continue
        try:
            session = json.loads(session_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            excluded.append({"session": str(session_path), "reason": f"session_read_error:{type(error).__name__}"})
            continue
        episode_id = session.get("episode_id")
        messages = session.get("messages")
        tools = session.get("tools")
        if not isinstance(episode_id, str) or not episode_id or episode_id in seen:
            excluded.append({"session": str(session_path), "reason": "missing_or_duplicate_episode_id"})
            continue
        if not isinstance(messages, list) or not messages or not isinstance(tools, list):
            excluded.append({"session": str(session_path), "reason": "missing_messages_or_tools"})
            continue
        end = _episode_end(session_path.parent)
        if end.get("status") != "completed" and not include_unfinished:
            excluded.append({"session": str(session_path), "reason": "episode_not_completed"})
            continue
        sanitized, removed = strip_skill_block(messages)
        expects_skill = condition.get("skill_id") not in {None, "", "none"}
        if expects_skill and not removed:
            excluded.append({"session": str(session_path), "reason": "expected_skill_block_missing"})
            continue
        if any(SKILL_MARKER in str(item.get("content") or "") for item in sanitized):
            excluded.append({"session": str(session_path), "reason": "skill_marker_remains"})
            continue
        seen.add(episode_id)
        split = _split(episode_id, split_seed, ratios)
        record = {
            "schema_version": DATASET_SCHEMA_VERSION,
            "episode_id": episode_id,
            "condition_id": condition.get("condition_id"),
            "teacher_condition": condition.get("teacher_condition"),
            "skill_id": condition.get("skill_id", "none"),
            "skill_sha256": condition.get("skill_sha256"),
            "student_input_contains_skill": False,
            "skill_block_removed": removed,
            "split": split,
            "status": end.get("status"),
            "outcome": str(end.get("result") or session.get("result") or "unknown"),
            "end_reason": end.get("end_reason"),
            "quality_tier": "A_candidate" if end.get("status") == "completed" else "B_candidate",
            "quality_flags": [],
            "source_session": str(session_path.relative_to(source)),
            "tools": tools,
            "messages": sanitized,
        }
        records[split].append(record)

    destination.mkdir(parents=True, exist_ok=True)
    counts = {}
    for split, rows in records.items():
        path = destination / f"{split}.jsonl"
        counts[split] = _jsonl_write(path, rows)

    llamafactory_rows: dict[str, dict[str, list[dict[str, Any]]]] = {}
    llamafactory_excluded: list[dict[str, str]] = []
    for split, rows in records.items():
        for row in rows:
            skill_id = str(row["skill_id"])
            slug = _skill_slug(skill_id)
            try:
                decision_windows = to_decision_cycle_windows(
                    row["messages"], history_cycles=history_cycles
                )
            except ValueError as error:
                llamafactory_excluded.append({
                    "episode_id": row["episode_id"],
                    "reason": str(error),
                })
                continue
            if not decision_windows:
                llamafactory_excluded.append({
                    "episode_id": row["episode_id"],
                    "reason": "no tool-call decisions",
                })
                continue
            target = llamafactory_rows.setdefault(
                slug, {"train": [], "validation": [], "test": []}
            )[split]
            for decision_index, window in enumerate(decision_windows):
                target.append({
                    **row,
                    **window,
                    "decision_index": decision_index,
                    "decision_count": len(decision_windows),
                    "history_cycles": history_cycles,
                    "llamafactory_adapter_version": LLAMAFACTORY_ADAPTER_VERSION,
                })

    dataset_info: dict[str, Any] = {}
    llamafactory_files: dict[str, dict[str, Any]] = {}
    for slug, split_rows in sorted(llamafactory_rows.items()):
        for split, rows in split_rows.items():
            relative = Path("llamafactory") / slug / f"{split}.jsonl"
            output_path = destination / relative
            _jsonl_write(output_path, rows)
            dataset_name = f"sc2bench_{slug}_{split}"
            dataset_info[dataset_name] = _llamafactory_dataset_entry(relative.as_posix())
            llamafactory_files[dataset_name] = {
                "path": relative.as_posix(),
                "records": len(rows),
                "sha256": file_sha256(output_path),
            }
    dataset_info_path = destination / "dataset_info.json"
    dataset_info_path.write_text(
        json.dumps(dataset_info, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    distributions = {
        "skill": dict(Counter(row["skill_id"] for rows in records.values() for row in rows)),
        "outcome": dict(Counter(row["outcome"] for rows in records.values() for row in rows)),
        "quality_tier": dict(Counter(row["quality_tier"] for rows in records.values() for row in rows)),
    }
    target_rows = [
        row
        for split_rows in llamafactory_rows.values()
        for rows in split_rows.values()
        for row in rows
    ]
    target_distributions = {
        "phase": dict(Counter(row["target_phase"] for row in target_rows)),
        "tool": dict(
            Counter(name for row in target_rows for name in row["target_tool_names"])
        ),
    }
    manifest = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "builder": "sc2bench_experiments.dataset",
        "input_root": str(source),
        "output_root": str(destination),
        "split_seed": split_seed,
        "split_ratios": {"train": ratios[0], "validation": ratios[1], "test": ratios[2]},
        "counts": counts,
        "total_records": sum(counts.values()),
        "excluded_count": len(excluded),
        "excluded": excluded,
        "llamafactory": {
            "adapter_version": LLAMAFACTORY_ADAPTER_VERSION,
            "sample_unit": "assistant_action_in_decision_cycle",
            "history_cycles": history_cycles,
            "advance_policy": "preserve_all",
            "target_distributions": target_distributions,
            "dataset_info": "dataset_info.json",
            "dataset_info_sha256": file_sha256(dataset_info_path),
            "excluded_count": len(llamafactory_excluded),
            "excluded": llamafactory_excluded,
            "files": llamafactory_files,
        },
        "distributions": distributions,
        "files": {
            split: {
                "path": f"{split}.jsonl",
                "sha256": file_sha256(destination / f"{split}.jsonl"),
            }
            for split in records
        },
    }
    manifest["manifest_content_sha256"] = canonical_sha256(manifest)
    temp = destination / "manifest.json.tmp"
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(destination / "manifest.json")
    return manifest


def validate_dataset(input_root: str | Path) -> dict[str, Any]:
    root = Path(input_root).resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing dataset manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    episode_splits: dict[str, str] = {}
    counts = Counter()
    target_phases = Counter()
    target_tools = Counter()
    target_records = 0
    for split in ("train", "validation", "test"):
        path = root / f"{split}.jsonl"
        if not path.is_file():
            errors.append(f"missing {path.name}")
            continue
        expected = ((manifest.get("files") or {}).get(split) or {}).get("sha256")
        if expected and file_sha256(path) != expected:
            errors.append(f"sha256 mismatch for {path.name}")
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"invalid JSON {path.name}:{line_number}")
                continue
            episode_id = record.get("episode_id")
            if episode_id in episode_splits:
                errors.append(
                    f"episode {episode_id!r} appears in {episode_splits[episode_id]} and {split}"
                )
            else:
                episode_splits[episode_id] = split
            if record.get("split") != split:
                errors.append(f"split mismatch {path.name}:{line_number}")
            if record.get("student_input_contains_skill") is not False:
                errors.append(f"student_input_contains_skill must be false {path.name}:{line_number}")
            for message in record.get("messages") or []:
                if SKILL_MARKER in str(message.get("content") or ""):
                    errors.append(f"Skill block remains {path.name}:{line_number}")
            counts[split] += 1
    dataset_info_path = root / "dataset_info.json"
    if not dataset_info_path.is_file():
        errors.append("missing dataset_info.json")
    else:
        expected_info_hash = ((manifest.get("llamafactory") or {}).get("dataset_info_sha256"))
        if expected_info_hash and file_sha256(dataset_info_path) != expected_info_hash:
            errors.append("sha256 mismatch for dataset_info.json")
        try:
            dataset_info = json.loads(dataset_info_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append("invalid dataset_info.json")
            dataset_info = {}
        if not isinstance(dataset_info, dict):
            errors.append("dataset_info.json must contain an object")
            dataset_info = {}
        registered_files = (manifest.get("llamafactory") or {}).get("files") or {}
        for name, entry in dataset_info.items():
            relative = entry.get("file_name") if isinstance(entry, dict) else None
            data_path = root / str(relative or "")
            if not isinstance(relative, str) or not data_path.is_file():
                errors.append(f"LlamaFactory dataset file missing for {name}")
            else:
                expected_hash = (registered_files.get(name) or {}).get("sha256")
                if expected_hash and file_sha256(data_path) != expected_hash:
                    errors.append(f"sha256 mismatch for LlamaFactory dataset {name}")
                expected_records = (registered_files.get(name) or {}).get("records")
                actual_records = 0
                for line_number, line in enumerate(
                    data_path.read_text(encoding="utf-8").splitlines(), 1
                ):
                    if not line.strip():
                        continue
                    actual_records += 1
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        errors.append(f"invalid JSON {relative}:{line_number}")
                        continue
                    messages = row.get("messages") or []
                    target = messages[-1] if messages else {}
                    names = _tool_names(target) if isinstance(target, dict) else []
                    phase = row.get("target_phase")
                    if target.get("role") != "assistant" or not names:
                        errors.append(f"missing final tool-call target {relative}:{line_number}")
                    if row.get("target_content_present") is not True:
                        errors.append(f"missing target content note {relative}:{line_number}")
                    if phase not in {"query", "action", "advance"}:
                        errors.append(f"invalid target phase {relative}:{line_number}")
                    elif (phase == "advance") != ("advance" in names):
                        errors.append(f"advance phase mismatch {relative}:{line_number}")
                    if row.get("target_tool_names") != names:
                        errors.append(f"target tool names mismatch {relative}:{line_number}")
                    target_phases[phase] += 1
                    target_tools.update(names)
                    target_records += 1
                if expected_records is not None and actual_records != expected_records:
                    errors.append(
                        f"record count mismatch for {name}: "
                        f"expected {expected_records}, got {actual_records}"
                    )
            if isinstance(entry, dict) and entry.get("formatting") != "openai":
                errors.append(f"LlamaFactory dataset {name} must use openai formatting")
        expected_targets = (manifest.get("llamafactory") or {}).get("target_distributions") or {}
        if dict(target_phases) != (expected_targets.get("phase") or {}):
            errors.append("LlamaFactory target phase distribution mismatch")
        if dict(target_tools) != (expected_targets.get("tool") or {}):
            errors.append("LlamaFactory target tool distribution mismatch")
    lf_excluded = int(((manifest.get("llamafactory") or {}).get("excluded_count") or 0))
    if lf_excluded:
        errors.append(f"{lf_excluded} episode(s) were excluded from LlamaFactory export")
    return {
        "input_root": str(root),
        "ok": not errors,
        "errors": errors,
        "counts": dict(counts),
        "unique_episodes": len(episode_splits),
        "target_records": target_records,
        "target_phases": dict(target_phases),
        "target_tools": dict(target_tools),
    }


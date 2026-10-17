from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import (
    PROJECT_ROOT,
    canonical_sha256,
    load_experiment_config,
    resolve_project_path,
)
from .platform import activate_platform_source, inspect_platform, platform_source
from .skill_registry import load_skill_record


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _selected_conditions(
    conditions: list[dict[str, str]], selected: Iterable[str] | None
) -> list[dict[str, str]]:
    if not selected:
        return conditions
    wanted = set(selected)
    known = {row["condition_id"] for row in conditions}
    missing = wanted - known
    if missing:
        raise ValueError(f"unknown condition ids: {sorted(missing)}")
    return [row for row in conditions if row["condition_id"] in wanted]


def _episode_config_key(config: Any) -> str:
    if hasattr(config, "to_dict"):
        config = config.to_dict()
    if not isinstance(config, dict):
        raise TypeError("episode config must be a dictionary or expose to_dict()")
    return canonical_sha256(config)


def _condition_attempts(condition_dir: Path) -> dict[str, Any]:
    completed_keys: set[str] = set()
    attempts = {"completed": 0, "interrupted": 0, "failed": 0, "incomplete": 0}
    batches: list[dict[str, Any]] = []
    unreadable_batches: list[str] = []
    for batch_path in sorted(condition_dir.glob("batch_*/batch.json")):
        try:
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            unreadable_batches.append(str(batch_path))
            continue
        if not isinstance(batch, dict):
            unreadable_batches.append(str(batch_path))
            continue
        episodes = batch.get("episodes") if isinstance(batch.get("episodes"), list) else []
        for episode in episodes:
            if not isinstance(episode, dict):
                continue
            status = str(episode.get("status") or "incomplete")
            attempts[status if status in attempts else "incomplete"] += 1
            config = episode.get("config")
            if status == "completed" and isinstance(config, dict):
                completed_keys.add(_episode_config_key(config))
        batches.append({
            "condition_id": condition_dir.name,
            "batch_id": batch.get("batch_id"),
            "batch_file": str(batch_path),
            "status": batch.get("status"),
            "aggregate": batch.get("aggregate"),
            "metrics": batch.get("metrics"),
            "termination_counts": batch.get("termination_counts"),
        })
    return {
        "completed_keys": completed_keys,
        "attempts": attempts,
        "batches": batches,
        "unreadable_batches": unreadable_batches,
    }


def _merge_batch_summaries(*groups: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    without_id: list[dict[str, Any]] = []
    for group in groups:
        for row in group:
            batch_id = row.get("batch_id")
            if isinstance(batch_id, str) and batch_id:
                merged[batch_id] = row
            else:
                without_id.append(row)
    return [*merged.values(), *without_id]


def teacher_plan(config_path: str | Path, selected: Iterable[str] | None = None) -> dict[str, Any]:
    config = load_experiment_config(config_path)
    source = platform_source(config["platform_config"])
    activate_platform_source(source)
    from sc2bench_env.benchmark import BenchmarkSuite

    suite_path = resolve_project_path(config["suite"])
    suite = BenchmarkSuite.load(suite_path)
    conditions = _selected_conditions(config["conditions"], selected)
    rows = []
    for condition in conditions:
        loaded = load_skill_record(condition["skill"], platform_root=source)
        skill_name = loaded.skill_id if loaded else "none"
        skill_sha = loaded.sha256 if loaded else None
        rows.append({
            **condition,
            "canonical_skill": skill_name,
            "skill_sha256": skill_sha,
            "skill_source": loaded.source if loaded else None,
            "skill_revision": loaded.revision if loaded else None,
            "episodes": len(suite.episode_plan()),
        })
    return {
        "experiment_id": config["experiment_id"],
        "config_path": config["_config_path"],
        "config_sha256": canonical_sha256({k: v for k, v in config.items() if not k.startswith("_")}),
        "suite_path": str(suite_path),
        "suite_sha256": suite.sha256,
        "episode_count_per_condition": len(suite.episode_plan()),
        "total_episode_count": len(suite.episode_plan()) * len(rows),
        "record_root": str(resolve_project_path(config["record_root"])),
        "backend": config["backend"],
        "max_parallel": config.get("max_parallel", 1),
        "conditions": rows,
        "platform": inspect_platform(config["platform_config"]),
    }


def teacher_collection_status(config_path: str | Path) -> dict[str, Any]:
    config = load_experiment_config(config_path)
    plan = teacher_plan(config_path)
    source = activate_platform_source(platform_source(config["platform_config"]))
    _ = source
    from sc2bench_env.benchmark import BenchmarkSuite

    suite = BenchmarkSuite.load(resolve_project_path(config["suite"]))
    expected_keys = {
        _episode_config_key(item["config"]) for item in suite.episode_plan()
    }
    root = resolve_project_path(config["record_root"])
    conditions = []
    for condition in config["conditions"]:
        attempts = _condition_attempts(root / condition["condition_id"])
        completed = attempts["completed_keys"] & expected_keys
        conditions.append({
            "condition_id": condition["condition_id"],
            "skill": condition["skill"],
            "expected": len(expected_keys),
            "completed": len(completed),
            "remaining": len(expected_keys - completed),
            "attempts": attempts["attempts"],
            "batch_count": len(attempts["batches"]),
            "unreadable_batches": attempts["unreadable_batches"],
        })
    return {
        "experiment_id": config["experiment_id"],
        "record_root": str(root),
        "suite_sha256": plan["suite_sha256"],
        "expected_per_condition": len(expected_keys),
        "complete": all(row["remaining"] == 0 for row in conditions),
        "conditions": conditions,
    }


def run_teacher(
    config_path: str | Path,
    *,
    execute: bool,
    resume: bool = False,
    selected: Iterable[str] | None = None,
) -> dict[str, Any]:
    config = load_experiment_config(config_path)
    full_plan = teacher_plan(config_path)
    plan = teacher_plan(config_path, selected)
    if not execute:
        return {"mode": "dry_run", **plan}

    source = activate_platform_source(platform_source(config["platform_config"]))
    _ = source
    from agents.llm_agent import make_llm_call
    from sc2bench_env.benchmark import BenchmarkRunner, BenchmarkSuite

    from .agents.teacher import create_teacher_agent

    teacher = config["teacher"]
    model = os.environ.get(teacher["model_env"], "").strip()
    api_key = os.environ.get(teacher["api_key_env"], "").strip()
    base_url = os.environ.get(teacher["base_url_env"], "").strip()
    if not model or not api_key or not base_url:
        raise ValueError(
            "Teacher API environment is incomplete; fill .env without committing secrets"
        )
    suite = BenchmarkSuite.load(resolve_project_path(config["suite"]))
    root = resolve_project_path(config["record_root"])
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "experiment_manifest.json"
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        **full_plan,
        "created_at": now,
        "teacher": {
            "name": teacher["name"],
            "version": teacher["version"],
            "model": model,
            "temperature": teacher.get("temperature", 0.0),
            "thinking": bool(teacher.get("thinking", False)),
            "api_timeout_seconds": teacher.get("api_timeout_seconds", 120.0),
            "max_api_attempts": teacher.get("max_api_attempts", 3),
            "api_retry_delay_seconds": teacher.get("api_retry_delay_seconds", 1.0),
            "max_consecutive_rejections": teacher.get("max_consecutive_rejections", 3),
        },
        "batches": [],
    }
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous.get("config_sha256") != manifest["config_sha256"]:
            raise ValueError(
                f"{manifest_path} belongs to a different config; use a new experiment_id/record_root"
            )
        manifest["created_at"] = previous.get("created_at", now)
        manifest["batches"] = list(previous.get("batches") or [])

    discovered_batches: list[dict[str, Any]] = []
    for condition in config["conditions"]:
        discovered_batches.extend(
            _condition_attempts(root / condition["condition_id"])["batches"]
        )
    manifest["batches"] = _merge_batch_summaries(
        manifest["batches"], discovered_batches
    )
    manifest["last_updated_at"] = now
    _atomic_json(manifest_path, manifest)

    call_llm = make_llm_call(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=float(teacher.get("api_timeout_seconds", 120.0)),
        temperature=float(teacher.get("temperature", 0.0)),
        thinking=bool(teacher.get("thinking", False)),
    )
    selected_rows = {row["condition_id"]: row for row in plan["conditions"]}
    for condition in config["conditions"]:
        if condition["condition_id"] not in selected_rows:
            continue
        condition_id = condition["condition_id"]
        skill_name = condition["skill"]
        loaded = load_skill_record(skill_name, platform_root=source)
        condition_dir = root / condition_id
        episode_plan = suite.episode_plan()
        expected_keys = {
            _episode_config_key(item["config"]) for item in episode_plan
        }
        attempts = _condition_attempts(condition_dir)
        completed_keys = attempts["completed_keys"] & expected_keys
        remaining_plan = [
            item for item in episode_plan
            if not resume or _episode_config_key(item["config"]) not in completed_keys
        ]
        condition_manifest = {
            "schema_version": "1",
            "experiment_id": config["experiment_id"],
            "condition_id": condition_id,
            "teacher_condition": "no_skill" if loaded is None else "skill",
            "skill_id": loaded.skill_id if loaded else "none",
            "skill_sha256": loaded.sha256 if loaded else None,
            "skill_source": loaded.source if loaded else None,
            "skill_revision": loaded.revision if loaded else None,
            "suite_sha256": suite.sha256,
            "model": model,
            "expected_episodes": len(episode_plan),
            "completed_before_run": len(completed_keys),
            "resume": resume,
        }
        _atomic_json(condition_dir / "condition.json", condition_manifest)

        if not remaining_plan:
            continue

        def agent_factory(skill=loaded):
            return create_teacher_agent(
                call_llm,
                skill=skill,
                thinking_requested=bool(teacher.get("thinking", False)),
                verbose=False,
                max_api_attempts=int(teacher.get("max_api_attempts", 3)),
                api_retry_delay_seconds=float(teacher.get("api_retry_delay_seconds", 1.0)),
                max_consecutive_rejections=int(
                    teacher.get("max_consecutive_rejections", 3)
                ),
            )

        metadata = {
            "name": teacher["name"],
            "version": teacher["version"],
            "model": model,
            "kind": "llm_teacher",
            "implementation": "agents.llm_agent.LLMAgent",
            "settings": {
                "temperature": teacher.get("temperature", 0.0),
                "thinking": bool(teacher.get("thinking", False)),
                "skill": condition_manifest["skill_id"],
                "skill_sha256": condition_manifest["skill_sha256"],
            },
        }
        runner = BenchmarkRunner(
            backend_factory=lambda backend=config["backend"]: backend,
            record_dir=condition_dir,
        )
        if len(remaining_plan) == len(episode_plan):
            run_input = suite
            run_kwargs: dict[str, Any] = {}
        else:
            run_input = [item["config"] for item in remaining_plan]
            run_kwargs = {"max_decisions": suite.max_decisions}
        batch = runner.run(
            run_input,
            agent_factory=agent_factory,
            agent_metadata=metadata,
            max_parallel=int(config.get("max_parallel", 1)),
            **run_kwargs,
        )
        summary = {
            "condition_id": condition_id,
            "batch_id": batch.get("batch_id"),
            "batch_file": batch.get("output_paths", {}).get("batch_file"),
            "status": batch.get("status"),
            "aggregate": batch.get("aggregate"),
            "metrics": batch.get("metrics"),
            "termination_counts": batch.get("termination_counts"),
            "resume": resume,
            "planned_episode_count": len(remaining_plan),
        }
        manifest["batches"] = _merge_batch_summaries(
            manifest["batches"], [summary]
        )
        manifest["last_updated_at"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(manifest_path, manifest)
    status = teacher_collection_status(config_path)
    manifest["collection_status"] = status
    manifest["last_updated_at"] = datetime.now(timezone.utc).isoformat()
    if status["complete"]:
        manifest["completed_at"] = manifest["last_updated_at"]
    else:
        manifest.pop("completed_at", None)
    _atomic_json(manifest_path, manifest)
    return manifest


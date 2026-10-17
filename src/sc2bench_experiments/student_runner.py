from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .agents.student import create_student_agent, make_student_call
from .config import canonical_sha256, load_student_experiment_config, resolve_project_path
from .platform import activate_platform_source, inspect_platform, platform_source
from .skill_registry import load_skill_record


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _selected(conditions: list[dict[str, str]], selected: Iterable[str] | None):
    if not selected:
        return conditions
    wanted = set(selected)
    known = {row["condition_id"] for row in conditions}
    missing = wanted - known
    if missing:
        raise ValueError(f"unknown condition ids: {sorted(missing)}")
    return [row for row in conditions if row["condition_id"] in wanted]


def student_plan(config_path: str | Path, selected: Iterable[str] | None = None) -> dict[str, Any]:
    config = load_student_experiment_config(config_path)
    source = platform_source(config["platform_config"])
    activate_platform_source(source)
    from sc2bench_env.benchmark import BenchmarkSuite

    suite_path = resolve_project_path(config["suite"])
    suite = BenchmarkSuite.load(suite_path)
    conditions = []
    for condition in _selected(config["conditions"], selected):
        skill = load_skill_record(condition["skill"], platform_root=source)
        conditions.append({
            **condition,
            "canonical_skill": skill.skill_id if skill else "none",
            "skill_sha256": skill.sha256 if skill else None,
            "skill_source": skill.source if skill else None,
            "skill_revision": skill.revision if skill else None,
            "episodes": len(suite.episode_plan()),
        })
    return {
        "experiment_id": config["experiment_id"],
        "config_path": config["_config_path"],
        "config_sha256": canonical_sha256({k: v for k, v in config.items() if not k.startswith("_")}),
        "suite_path": str(suite_path),
        "suite_sha256": suite.sha256,
        "episode_count_per_condition": len(suite.episode_plan()),
        "total_episode_count": len(suite.episode_plan()) * len(conditions),
        "record_root": str(resolve_project_path(config["record_root"])),
        "backend": config["backend"],
        "max_parallel": config.get("max_parallel", 1),
        "conditions": conditions,
        "platform": inspect_platform(config["platform_config"]),
    }


def run_student(
    config_path: str | Path,
    *,
    execute: bool,
    selected: Iterable[str] | None = None,
) -> dict[str, Any]:
    config = load_student_experiment_config(config_path)
    plan = student_plan(config_path, selected)
    if not execute:
        return {"mode": "dry_run", **plan}

    source = activate_platform_source(platform_source(config["platform_config"]))
    from sc2bench_env.benchmark import BenchmarkRunner, BenchmarkSuite

    student = config["student"]
    model = os.environ.get(student["model_env"], "").strip()
    api_key = os.environ.get(student["api_key_env"], "").strip()
    base_url = os.environ.get(student["base_url_env"], "").strip()
    if not model or not api_key or not base_url:
        raise ValueError("Student endpoint environment is incomplete; fill .env on the server")
    call_llm = make_student_call(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=float(student.get("api_timeout_seconds", 120.0)),
        temperature=float(student.get("temperature", 0.0)),
        thinking=bool(student.get("thinking", False)),
    )
    suite = BenchmarkSuite.load(resolve_project_path(config["suite"]))
    root = resolve_project_path(config["record_root"])
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "experiment_manifest.json"
    manifest = {
        **plan,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "student": {
            "name": student["name"],
            "version": student["version"],
            "model": model,
            "temperature": student.get("temperature", 0.0),
            "thinking": bool(student.get("thinking", False)),
        },
        "batches": [],
    }
    selected_ids = {row["condition_id"] for row in plan["conditions"]}
    for condition in config["conditions"]:
        if condition["condition_id"] not in selected_ids:
            continue
        skill = load_skill_record(condition["skill"], platform_root=source)
        condition_dir = root / condition["condition_id"]
        condition_manifest = {
            "schema_version": "1",
            "experiment_id": config["experiment_id"],
            "condition_id": condition["condition_id"],
            "student_condition": "no_skill" if skill is None else "skill",
            "skill_id": skill.skill_id if skill else "none",
            "skill_sha256": skill.sha256 if skill else None,
            "skill_source": skill.source if skill else None,
            "skill_revision": skill.revision if skill else None,
            "suite_sha256": suite.sha256,
            "model": model,
        }
        _atomic_json(condition_dir / "condition.json", condition_manifest)

        def agent_factory(bound_skill=skill):
            return create_student_agent(
                call_llm,
                skill=bound_skill,
                thinking_requested=bool(student.get("thinking", False)),
                verbose=False,
                max_api_attempts=int(student.get("max_api_attempts", 3)),
                api_retry_delay_seconds=float(student.get("api_retry_delay_seconds", 1.0)),
                max_consecutive_rejections=int(student.get("max_consecutive_rejections", 3)),
            )

        metadata = {
            "name": student["name"],
            "version": student["version"],
            "model": model,
            "kind": "llm_student",
            "implementation": "sc2bench_experiments.agents.student",
            "settings": {
                "temperature": student.get("temperature", 0.0),
                "thinking": bool(student.get("thinking", False)),
                "skill": condition_manifest["skill_id"],
                "skill_sha256": condition_manifest["skill_sha256"],
            },
        }
        batch = BenchmarkRunner(
            backend_factory=lambda backend=config["backend"]: backend,
            record_dir=condition_dir,
        ).run(
            suite,
            agent_factory=agent_factory,
            agent_metadata=metadata,
            max_parallel=int(config.get("max_parallel", 1)),
        )
        manifest["batches"].append({
            "condition_id": condition["condition_id"],
            "batch_id": batch.get("batch_id"),
            "batch_file": batch.get("output_paths", {}).get("batch_file"),
            "status": batch.get("status"),
            "aggregate": batch.get("aggregate"),
        })
        _atomic_json(manifest_path, manifest)
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_json(manifest_path, manifest)
    return manifest

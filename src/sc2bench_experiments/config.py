from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON field {key!r} in {source}")
            result[key] = value
        return result

    data = json.loads(
        source.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object
    )
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {source}")
    return data


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (PROJECT_ROOT / path).resolve()


def require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def load_experiment_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    data = load_json(config_path)
    if data.get("schema_version") != "1":
        raise ValueError("Unsupported experiment schema_version")
    require_text(data.get("experiment_id"), "experiment_id")
    for field in ("platform_config", "suite", "record_root", "backend"):
        require_text(data.get(field), field)
    if data["backend"] not in {"sharpy", "fake"}:
        raise ValueError("backend must be sharpy or fake")
    max_parallel = data.get("max_parallel", 1)
    if type(max_parallel) is not int or max_parallel < 1:
        raise ValueError("max_parallel must be a positive integer")
    teacher = data.get("teacher")
    if not isinstance(teacher, dict):
        raise ValueError("teacher must be an object")
    for field in ("name", "version", "model_env", "api_key_env", "base_url_env"):
        require_text(teacher.get(field), f"teacher.{field}")
    conditions = data.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("conditions must be a non-empty list")
    seen = set()
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) != {"condition_id", "skill"}:
            raise ValueError("each condition requires exactly condition_id and skill")
        condition_id = require_text(condition["condition_id"], "condition_id")
        require_text(condition["skill"], f"conditions[{condition_id}].skill")
        if condition_id in seen:
            raise ValueError(f"duplicate condition_id {condition_id!r}")
        seen.add(condition_id)
    data["_config_path"] = str(config_path)
    return data


def load_student_experiment_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    data = load_json(config_path)
    if data.get("schema_version") != "1":
        raise ValueError("Unsupported experiment schema_version")
    require_text(data.get("experiment_id"), "experiment_id")
    for field in ("platform_config", "suite", "record_root", "backend"):
        require_text(data.get(field), field)
    if data["backend"] not in {"sharpy", "fake"}:
        raise ValueError("backend must be sharpy or fake")
    max_parallel = data.get("max_parallel", 1)
    if type(max_parallel) is not int or max_parallel < 1:
        raise ValueError("max_parallel must be a positive integer")
    student = data.get("student")
    if not isinstance(student, dict):
        raise ValueError("student must be an object")
    for field in ("name", "version", "model_env", "api_key_env", "base_url_env"):
        require_text(student.get(field), f"student.{field}")
    conditions = data.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("conditions must be a non-empty list")
    seen = set()
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) != {"condition_id", "skill"}:
            raise ValueError("each condition requires exactly condition_id and skill")
        condition_id = require_text(condition["condition_id"], "condition_id")
        require_text(condition["skill"], f"conditions[{condition_id}].skill")
        if condition_id in seen:
            raise ValueError(f"duplicate condition_id {condition_id!r}")
        seen.add(condition_id)
    data["_config_path"] = str(config_path)
    return data


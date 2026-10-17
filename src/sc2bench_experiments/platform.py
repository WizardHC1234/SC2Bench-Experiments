from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT, load_json, resolve_project_path


def platform_source(platform_config: str | Path = "configs/platform.json") -> Path:
    config_path = resolve_project_path(platform_config)
    config = load_json(config_path)
    override = os.environ.get("SC2EXP_PLATFORM_SOURCE", "").strip()
    source = override or str(config.get("source") or "")
    if not source:
        raise ValueError("platform source is not configured")
    path = Path(source)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def activate_platform_source(source: str | Path) -> Path:
    root = Path(source).resolve()
    if not (root / "pyproject.toml").is_file():
        raise FileNotFoundError(f"SC2Bench source not found at {root}")
    for candidate in (root, root / "src"):
        value = str(candidate)
        if value not in sys.path:
            sys.path.insert(0, value)
    return root


def _git(source: Path, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", "-C", str(source), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.returncode, result.stdout.strip()


def inspect_platform(platform_config: str | Path = "configs/platform.json") -> dict[str, Any]:
    config_path = resolve_project_path(platform_config)
    config = load_json(config_path)
    source = platform_source(config_path)
    checks: list[dict[str, Any]] = []

    exists = (source / "pyproject.toml").is_file()
    checks.append({"name": "source", "ok": exists, "detail": str(source)})
    commit = None
    dirty = None
    if exists:
        code, commit_text = _git(source, "rev-parse", "HEAD")
        commit = commit_text if code == 0 else None
        expected = config.get("expected_git_commit")
        checks.append({
            "name": "git_commit",
            "ok": commit is not None and (not expected or commit == expected),
            "detail": {"actual": commit, "expected": expected},
        })
        code, status = _git(source, "status", "--short")
        dirty = bool(status) if code == 0 else None
        checks.append({
            "name": "worktree",
            "ok": dirty is False or bool(config.get("allow_dirty_worktree", False)),
            "warning": bool(dirty),
            "detail": status.splitlines() if status else [],
        })

    import_error = None
    skills: list[str] = []
    if exists:
        try:
            activate_platform_source(source)
            import sc2bench_env  # noqa: F401
            from agents.llm_agent import AVAILABLE_SKILLS

            skills = list(AVAILABLE_SKILLS)
        except Exception as error:  # doctor should report rather than crash
            import_error = f"{type(error).__name__}: {error}"
    checks.append({
        "name": "imports",
        "ok": import_error is None and exists,
        "detail": import_error or f"{len(skills)} built-in skills discovered",
    })
    return {
        "project_root": str(PROJECT_ROOT),
        "platform_config": str(config_path),
        "platform_source": str(source),
        "git_commit": commit,
        "dirty": dirty,
        "skills": skills,
        "checks": checks,
        "ok": all(bool(item.get("ok")) for item in checks),
    }


def print_platform_report(report: dict[str, Any]) -> None:
    print("SC2Bench-Experiments doctor")
    for check in report["checks"]:
        label = "PASS" if check["ok"] else "FAIL"
        if check.get("warning"):
            label = "WARN"
        detail = check.get("detail")
        if isinstance(detail, (dict, list)):
            detail = json.dumps(detail, ensure_ascii=False)
        print(f"[{label}] {check['name']}: {detail}")


from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .config import PROJECT_ROOT, file_sha256


_SKILL_ID = re.compile(r"^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class SkillRecord:
    skill_id: str
    text: str
    sha256: str
    source: str
    revision: str | None
    path: Path


def _normalize(name: str | None) -> str:
    value = str(name or "none").strip().lower().replace("\\", "/")
    if value == "none":
        return value
    if not _SKILL_ID.fullmatch(value):
        raise ValueError(f"invalid Skill id {name!r}; expected race/strategy")
    return value


def _manifest(skill_root: Path) -> dict[str, dict]:
    path = skill_root / "manifest.json"
    if not path.is_file():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != "1" or not isinstance(document.get("skills"), list):
        raise ValueError(f"invalid Skill manifest: {path}")
    result: dict[str, dict] = {}
    for entry in document["skills"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError(f"invalid Skill manifest entry: {entry!r}")
        skill_id = _normalize(entry["id"])
        if skill_id in result:
            raise ValueError(f"duplicate Skill manifest id {skill_id!r}")
        result[skill_id] = entry
    return result


def _read_record(
    skill_id: str,
    path: Path,
    *,
    source: str,
    revision: str | None,
    expected_sha256: str | None = None,
) -> SkillRecord:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Skill {skill_id!r} is empty: {path}")
    digest = file_sha256(path)
    if expected_sha256 and digest != expected_sha256:
        raise ValueError(
            f"Skill {skill_id!r} SHA256 mismatch: expected {expected_sha256}, got {digest}"
        )
    return SkillRecord(skill_id, text, digest, source, revision, path.resolve())


def load_skill_record(
    name: str | None,
    *,
    skill_root: str | Path = PROJECT_ROOT / "skills",
    platform_root: str | Path | None = None,
) -> SkillRecord | None:
    """Load an experiment-owned Skill first, then fall back to pinned SC2Bench."""
    skill_id = _normalize(name)
    if skill_id == "none":
        return None
    root = Path(skill_root).resolve()
    entry = _manifest(root).get(skill_id)
    experiment_path = root.joinpath(*skill_id.split("/")).with_suffix(".md")
    if experiment_path.is_file():
        if entry is None:
            raise ValueError(f"experiment Skill {skill_id!r} is not registered in {root / 'manifest.json'}")
        declared = root / str(entry.get("path") or "")
        if declared.resolve() != experiment_path.resolve():
            raise ValueError(f"Skill manifest path mismatch for {skill_id!r}")
        return _read_record(
            skill_id,
            experiment_path,
            source=str(entry.get("source") or "experiment"),
            revision=str(entry["revision"]) if entry.get("revision") else None,
            expected_sha256=str(entry.get("sha256") or "") or None,
        )
    if platform_root is not None:
        platform = Path(platform_root).resolve()
        path = platform / "agents" / "llm_agent" / "skills"
        path = path.joinpath(*skill_id.split("/")).with_suffix(".md")
        if path.is_file():
            return _read_record(skill_id, path, source="SC2Bench", revision=None)
    raise ValueError(f"unknown Skill {skill_id!r}")


def available_skills(
    *,
    skill_root: str | Path = PROJECT_ROOT / "skills",
    platform_root: str | Path | None = None,
) -> tuple[str, ...]:
    root = Path(skill_root).resolve()
    names = set(_manifest(root))
    if platform_root is not None:
        builtins = Path(platform_root).resolve() / "agents" / "llm_agent" / "skills"
        if builtins.is_dir():
            names.update(
                path.relative_to(builtins).with_suffix("").as_posix()
                for path in builtins.glob("*/*.md")
            )
    return tuple(sorted(names))

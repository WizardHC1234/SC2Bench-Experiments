from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sc2bench_experiments.skill_registry import available_skills, load_skill_record


def _write_skill(root: Path, text: str, digest: str | None = None):
    path = root / "terran" / "test-plan.md"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    (root / "manifest.json").write_text(
        json.dumps({
            "schema_version": "1",
            "skills": [{
                "id": "terran/test-plan",
                "path": "terran/test-plan.md",
                "source": "unit-test",
                "revision": "1",
                "sha256": digest or actual,
            }],
        }),
        encoding="utf-8",
    )
    return actual


def test_experiment_skill_is_loaded_and_verified(tmp_path):
    root = tmp_path / "skills"
    digest = _write_skill(root, "# Test plan\n")
    record = load_skill_record("terran/test-plan", skill_root=root)
    assert record is not None
    assert record.sha256 == digest
    assert record.source == "unit-test"
    assert available_skills(skill_root=root) == ("terran/test-plan",)


def test_skill_hash_mismatch_fails(tmp_path):
    root = tmp_path / "skills"
    _write_skill(root, "# Test plan\n", digest="0" * 64)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        load_skill_record("terran/test-plan", skill_root=root)

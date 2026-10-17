import json

from sc2bench_experiments.runner import (
    _condition_attempts,
    _episode_config_key,
    _merge_batch_summaries,
)


def test_condition_attempts_tracks_unique_completed_configs(tmp_path):
    condition = tmp_path / "T1"
    batch_dir = condition / "batch_001"
    batch_dir.mkdir(parents=True)
    config = {"race": "terran", "seed": 7}
    (batch_dir / "batch.json").write_text(
        json.dumps(
            {
                "batch_id": "batch-1",
                "status": "completed",
                "episodes": [
                    {"status": "completed", "config": config},
                    {"status": "failed", "config": {"race": "terran", "seed": 8}},
                    {"status": "completed", "config": config},
                ],
            }
        ),
        encoding="utf-8",
    )
    report = _condition_attempts(condition)
    assert report["completed_keys"] == {_episode_config_key(config)}
    assert report["attempts"]["completed"] == 2
    assert report["attempts"]["failed"] == 1


def test_batch_summary_merge_is_append_only_by_batch_id():
    old = {"batch_id": "a", "status": "running"}
    refreshed = {"batch_id": "a", "status": "completed"}
    new = {"batch_id": "b", "status": "completed"}
    assert _merge_batch_summaries([old], [refreshed, new]) == [refreshed, new]

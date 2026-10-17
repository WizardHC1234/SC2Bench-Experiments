import json
from pathlib import Path

from sc2bench_experiments.config import load_experiment_config, load_student_experiment_config


ROOT = Path(__file__).resolve().parents[1]


def test_stage1_experiment_config_is_valid():
    config = load_experiment_config(
        ROOT / "configs" / "experiments" / "stage1_teacher_pilot.json"
    )
    assert config["experiment_id"] == "stage1_teacher_pilot"
    assert [row["skill"] for row in config["conditions"]] == [
        "none",
        "terran/marine-rush",
        "terran/two-base-tanks",
        "terran/battle-cruisers",
    ]


def test_student_experiment_config_is_valid():
    config = load_student_experiment_config(
        ROOT / "configs" / "experiments" / "stage1_student_pilot.json"
    )
    assert config["student"]["model_env"] == "STUDENT_MODEL"
    assert [row["skill"] for row in config["conditions"]] == [
        "none",
        "terran/two-base-tanks",
    ]


def test_formal_teacher_matrix_is_balanced_and_uses_eight_workers():
    config = load_experiment_config(
        ROOT
        / "configs"
        / "experiments"
        / "teacher_deepseek_v4_flash_fixed_styles_20_per_cell.json"
    )
    assert config["max_parallel"] == 8
    assert len(config["conditions"]) == 4

    suite_path = ROOT / config["suite"]
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    assert suite["repetitions"] == 20
    assert len(suite["game_seeds"]) == 20
    assert len(set(suite["game_seeds"])) == 20
    assert len(suite["cases"]) * suite["repetitions"] == 200

    cells = {
        (case["episode"]["opponent"], case["episode"]["enemy_style"])
        for case in suite["cases"]
    }
    assert cells == {
        (difficulty, style)
        for difficulty in ("mediumhard", "hard")
        for style in ("rush", "timing", "power", "macro", "air")
    }


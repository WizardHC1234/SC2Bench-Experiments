from pathlib import Path

from sc2bench_experiments.sft import inference_config_preflight


ROOT = Path(__file__).resolve().parents[1]


def test_inference_example_requires_model_and_template():
    report = inference_config_preflight(
        ROOT / "configs" / "inference" / "student_lora.example.yaml"
    )
    assert report["ok"] is False
    assert "model_name_or_path is still TBD" in report["errors"]
    assert "template must be selected for the base model" in report["errors"]


def test_inference_config_accepts_resolved_lora_config(tmp_path):
    config = tmp_path / "student.yaml"
    config.write_text(
        "\n".join(
            [
                "model_name_or_path: Qwen/example",
                "adapter_name_or_path: checkpoints/example",
                "template: qwen",
                "infer_backend: huggingface",
            ]
        ),
        encoding="utf-8",
    )
    report = inference_config_preflight(config)
    assert report["ok"] is True
    assert report["adapter_name_or_path"] == "checkpoints/example"

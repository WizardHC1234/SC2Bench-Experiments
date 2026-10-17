from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from .config import PROJECT_ROOT


SUPPORTED_LLAMAFACTORY_VERSION = "0.9.5"
SUPPORTED_INFERENCE_BACKENDS = {"huggingface", "vllm", "sglang", "ktransformers"}


def _names(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _line_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def inference_config_preflight(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path).resolve()
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected YAML object: {path}")

    errors: list[str] = []
    model = str(loaded.get("model_name_or_path") or "").strip()
    template = str(loaded.get("template") or "").strip()
    adapter = str(loaded.get("adapter_name_or_path") or "").strip() or None
    backend = str(loaded.get("infer_backend") or "huggingface").strip()

    if not model or "TBD" in model.upper():
        errors.append("model_name_or_path is still TBD")
    if not template or "TBD" in template.upper():
        errors.append("template must be selected for the base model")
    if adapter and "TBD" in adapter.upper():
        errors.append("adapter_name_or_path is still TBD")
    if backend not in SUPPORTED_INFERENCE_BACKENDS:
        errors.append(f"unsupported infer_backend: {backend}")

    return {
        "config": str(path),
        "ok": not errors,
        "errors": errors,
        "model_name_or_path": model,
        "adapter_name_or_path": adapter,
        "template": template,
        "infer_backend": backend,
    }


def sft_preflight(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path).resolve()
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected YAML object: {path}")
    config = loaded
    errors: list[str] = []
    warnings: list[str] = []

    if config.get("stage") != "sft" or config.get("do_train") is not True:
        errors.append("LlamaFactory config must set stage: sft and do_train: true")
    model = str(config.get("model_name_or_path") or "").strip()
    if not model or "TBD" in model.upper():
        errors.append("model_name_or_path is still TBD")
    template = str(config.get("template") or "").strip()
    if not template or "TBD" in template.upper():
        errors.append("template must be selected for the base model")
    if config.get("train_on_prompt") is not False:
        errors.append("train_on_prompt must be false")
    if config.get("mask_history") is not True:
        errors.append("mask_history must be true for final-action decision-window supervision")
    if config.get("finetuning_type") != "lora":
        warnings.append("the baseline recipe is designed for finetuning_type: lora")

    dataset_dir_value = str(config.get("dataset_dir") or "").strip()
    dataset_dir = Path(dataset_dir_value)
    if not dataset_dir.is_absolute():
        dataset_dir = (PROJECT_ROOT / dataset_dir).resolve()
    dataset_info_path = dataset_dir / "dataset_info.json"
    dataset_info: dict[str, Any] = {}
    if not dataset_info_path.is_file():
        errors.append(f"dataset_info.json does not exist: {dataset_info_path}")
    else:
        try:
            value = json.loads(dataset_info_path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                dataset_info = value
            else:
                errors.append("dataset_info.json must contain an object")
        except json.JSONDecodeError:
            errors.append("dataset_info.json is invalid JSON")

    datasets: dict[str, dict[str, Any]] = {}
    requested = [("dataset", name) for name in _names(config.get("dataset"))]
    requested += [("eval_dataset", name) for name in _names(config.get("eval_dataset"))]
    if not any(kind == "dataset" for kind, _ in requested):
        errors.append("dataset is not configured")
    if not any(kind == "eval_dataset" for kind, _ in requested):
        errors.append("eval_dataset is required for the experiment baseline")
    for kind, name in requested:
        entry = dataset_info.get(name)
        if not isinstance(entry, dict):
            errors.append(f"{kind} {name!r} is not registered in dataset_info.json")
            continue
        if entry.get("formatting") != "openai":
            errors.append(f"dataset {name!r} must use formatting: openai")
        file_name = entry.get("file_name")
        data_path = dataset_dir / str(file_name or "")
        if not file_name or not data_path.is_file():
            errors.append(f"dataset file does not exist for {name!r}: {data_path}")
            continue
        count = _line_count(data_path)
        if count == 0:
            errors.append(f"dataset {name!r} is empty")
        datasets[name] = {"kind": kind, "path": str(data_path), "records": count}

    sibling_cli = Path(sys.executable).resolve().parent / "llamafactory-cli"
    command = str(sibling_cli) if sibling_cli.is_file() else shutil.which("llamafactory-cli")
    llama_factory_version = None
    try:
        llama_factory_version = importlib.metadata.version("llamafactory")
    except importlib.metadata.PackageNotFoundError:
        errors.append("LlamaFactory is not installed in this environment")
    else:
        if llama_factory_version != SUPPORTED_LLAMAFACTORY_VERSION:
            errors.append(
                "LlamaFactory version mismatch: "
                f"expected {SUPPORTED_LLAMAFACTORY_VERSION}, got {llama_factory_version}"
            )
    if command is None:
        errors.append("llamafactory-cli is not on PATH")

    cuda = None
    gpu = None
    if importlib.util.find_spec("torch") is None:
        errors.append("PyTorch is not installed")
    else:
        import torch

        cuda = bool(torch.cuda.is_available())
        gpu = torch.cuda.get_device_name(0) if cuda else None
        if not cuda:
            errors.append("CUDA is unavailable")

    return {
        "config": str(path),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "llamafactory_version": llama_factory_version,
        "llamafactory_cli": command,
        "dataset_dir": str(dataset_dir),
        "datasets": datasets,
        "cuda_available": cuda,
        "gpu": gpu,
    }


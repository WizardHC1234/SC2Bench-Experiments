from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from .config import PROJECT_ROOT, resolve_project_path
from .dataset import build_dataset, validate_dataset
from .platform import inspect_platform, print_platform_report
from .runner import run_teacher, teacher_collection_status
from .sft import inference_config_preflight, sft_preflight
from .student_runner import run_student


def _print_json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sc2exp")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="check project and SC2Bench dependency")
    doctor.add_argument("--platform-config", default="configs/platform.json")
    doctor.add_argument("--json", action="store_true")

    teacher = sub.add_parser("run-teacher", help="plan or execute fixed-Skill Teacher batches")
    teacher.add_argument("--config", required=True, type=Path)
    teacher.add_argument("--condition", action="append", default=[])
    mode = teacher.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    teacher.add_argument(
        "--resume", action="store_true",
        help="skip completed episode configs and rerun only missing/failed attempts",
    )

    teacher_status = sub.add_parser(
        "teacher-status", help="show completed and remaining Teacher episodes"
    )
    teacher_status.add_argument("--config", required=True, type=Path)

    student = sub.add_parser("run-student", help="plan or execute served Student batches")
    student.add_argument("--config", required=True, type=Path)
    student.add_argument("--condition", action="append", default=[])
    student_mode = student.add_mutually_exclusive_group(required=True)
    student_mode.add_argument("--dry-run", action="store_true")
    student_mode.add_argument("--execute", action="store_true")

    build = sub.add_parser("build-dataset", help="sanitize sessions into episode-level SFT JSONL")
    build.add_argument("--input", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--split-seed", type=int, default=20261009)
    build.add_argument("--include-unfinished", action="store_true")

    validate = sub.add_parser("validate-dataset", help="audit a generated dataset")
    validate.add_argument("--input", required=True, type=Path)

    preflight = sub.add_parser("sft-preflight", help="validate LlamaFactory SFT config, data and CUDA")
    preflight.add_argument("--config", required=True, type=Path)

    inference = sub.add_parser(
        "inference-preflight", help="validate a LlamaFactory Student serving config"
    )
    inference.add_argument("--config", required=True, type=Path)
    return parser


def main(argv=None) -> int:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    args = _parser().parse_args(argv)
    if args.command == "doctor":
        report = inspect_platform(args.platform_config)
        _print_json(report) if args.json else print_platform_report(report)
        return 0 if report["ok"] else 1
    if args.command == "run-teacher":
        result = run_teacher(
            args.config,
            execute=args.execute,
            resume=args.resume,
            selected=args.condition or None,
        )
        _print_json(result)
        return 0
    if args.command == "teacher-status":
        result = teacher_collection_status(args.config)
        _print_json(result)
        return 0
    if args.command == "run-student":
        result = run_student(
            args.config,
            execute=args.execute,
            selected=args.condition or None,
        )
        _print_json(result)
        return 0
    if args.command == "build-dataset":
        result = build_dataset(
            resolve_project_path(args.input),
            resolve_project_path(args.output),
            split_seed=args.split_seed,
            include_unfinished=args.include_unfinished,
        )
        _print_json(result)
        return 0
    if args.command == "validate-dataset":
        result = validate_dataset(resolve_project_path(args.input))
        _print_json(result)
        return 0 if result["ok"] else 1
    if args.command == "sft-preflight":
        result = sft_preflight(args.config)
        _print_json(result)
        return 0 if result["ok"] else 1
    if args.command == "inference-preflight":
        result = inference_config_preflight(args.config)
        _print_json(result)
        return 0 if result["ok"] else 1
    raise AssertionError(args.command)


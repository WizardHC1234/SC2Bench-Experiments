#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${SC2_VENV:-${PROJECT_ROOT}/.venv-sc2}/bin/python"
INPUT="${1:-runs/raw/stage1_teacher_pilot}"
OUTPUT="${2:-data/processed/stage1_teacher_pilot}"

cd "${PROJECT_ROOT}"
"${PYTHON}" -m sc2bench_experiments build-dataset \
  --input "${INPUT}" --output "${OUTPUT}"
"${PYTHON}" -m sc2bench_experiments validate-dataset --input "${OUTPUT}"

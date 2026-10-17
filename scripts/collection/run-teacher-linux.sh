#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${SC2_VENV:-${PROJECT_ROOT}/.venv-sc2}/bin/python"
CONFIG="${1:-configs/experiments/stage1_teacher_pilot.json}"
shift || true

if [[ ! -x "${PYTHON}" ]]; then
  echo "Missing collection environment. Run bash scripts/setup/linux-collection.sh" >&2
  exit 2
fi

cd "${PROJECT_ROOT}"
"${PYTHON}" -m sc2bench_experiments run-teacher \
  --config "${CONFIG}" "$@"

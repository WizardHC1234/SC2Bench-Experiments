#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SC2_VENV="${SC2_VENV:-${PROJECT_ROOT}/.venv-sc2}"
if [[ "${SC2_VENV}" != /* ]]; then
  SC2_VENV="${PROJECT_ROOT}/${SC2_VENV}"
fi
PYTHON="${SC2_VENV}/bin/python"
CONFIG="${1:-configs/experiments/stage1_student_pilot.json}"
shift || true

if [[ ! -x "${PYTHON}" ]]; then
  echo "Missing collection environment. Run bash scripts/setup/linux-collection.sh" >&2
  exit 2
fi

cd "${PROJECT_ROOT}"
"${PYTHON}" -m sc2bench_experiments run-student \
  --config "${CONFIG}" "$@"

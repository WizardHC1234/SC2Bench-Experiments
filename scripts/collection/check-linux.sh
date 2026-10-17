#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${SC2_VENV:-${PROJECT_ROOT}/.venv-sc2}/bin/python"
PLATFORM_DIR="${SC2EXP_PLATFORM_SOURCE:-${PROJECT_ROOT}/platform/SC2Bench}"

if [[ "${PLATFORM_DIR}" != /* ]]; then
  PLATFORM_DIR="${PROJECT_ROOT}/${PLATFORM_DIR}"
fi

if [[ ! -x "${PYTHON}" ]]; then
  echo "Missing collection environment. Run bash scripts/setup/linux-collection.sh" >&2
  exit 2
fi
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  set -a
  # .env.example is intentionally shell-compatible.
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.env"
  set +a
fi
if [[ -z "${SC2PATH:-}" || ! -d "${SC2PATH}" ]]; then
  echo "SC2PATH is missing or not a directory. Configure it in .env." >&2
  exit 2
fi

SC2EXP_PLATFORM_SOURCE="${PLATFORM_DIR}" \
  "${PYTHON}" -m sc2bench_experiments doctor
"${PYTHON}" -m sc2bench_env doctor \
  --suite "${PLATFORM_DIR}/benchmarks/terran_pilot.json"

echo "SC2 client, map, platform and Python environment checks passed."

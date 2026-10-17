#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SFT_VENV="${SFT_VENV:-${PROJECT_ROOT}/.venv-sft}"
if [[ "${SFT_VENV}" != /* ]]; then
  SFT_VENV="${PROJECT_ROOT}/${SFT_VENV}"
fi
PYTHON="${SFT_VENV}/bin/python"
LLAMAFACTORY_CLI="$(dirname "${PYTHON}")/llamafactory-cli"
CONFIG="${1:-}"

if [[ -z "${CONFIG}" ]]; then
  echo "Usage: bash scripts/training/run-sft.sh configs/sft/<run>.yaml" >&2
  exit 2
fi
if [[ ! -x "${PYTHON}" ]]; then
  echo "Missing SFT environment. Run bash scripts/setup/linux-sft.sh" >&2
  exit 2
fi
if [[ ! -x "${LLAMAFACTORY_CLI}" ]]; then
  echo "llamafactory-cli is missing. Run bash scripts/setup/linux-sft.sh" >&2
  exit 2
fi

cd "${PROJECT_ROOT}"
"${PYTHON}" -m sc2bench_experiments sft-preflight --config "${CONFIG}"
"${LLAMAFACTORY_CLI}" train "${CONFIG}"

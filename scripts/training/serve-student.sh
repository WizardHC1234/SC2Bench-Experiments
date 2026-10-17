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
  echo "Usage: bash scripts/training/serve-student.sh configs/inference/<run>.yaml" >&2
  exit 2
fi
if [[ ! -x "${PYTHON}" || ! -x "${LLAMAFACTORY_CLI}" ]]; then
  echo "Missing SFT/LlamaFactory environment. Run bash scripts/setup/linux-sft.sh" >&2
  exit 2
fi

cd "${PROJECT_ROOT}"
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.env"
  set +a
fi

"${PYTHON}" -m sc2bench_experiments inference-preflight --config "${CONFIG}"

export API_HOST="${API_HOST:-127.0.0.1}"
export API_PORT="${API_PORT:-8000}"
export API_KEY="${API_KEY:-${STUDENT_API_KEY:-local-student}}"
export API_MODEL_NAME="${API_MODEL_NAME:-${STUDENT_MODEL:-student-sft}}"

echo "Serving ${API_MODEL_NAME} at http://${API_HOST}:${API_PORT}/v1"
echo "Keep this process running while scripts/evaluation/run-student.sh executes."
exec "${LLAMAFACTORY_CLI}" api "${CONFIG}"

#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.env"
  set +a
fi

BASE_URL="${STUDENT_BASE_URL:-http://127.0.0.1:8000/v1}"
API_KEY_VALUE="${STUDENT_API_KEY:-local-student}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for the Student API health check." >&2
  exit 2
fi

echo "Checking ${BASE_URL%/}/models"
curl --fail --silent --show-error \
  -H "Authorization: Bearer ${API_KEY_VALUE}" \
  "${BASE_URL%/}/models"
printf '\n'

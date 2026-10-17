#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PROJECT_ROOT}/.venv/Scripts/python.exe"

die() {
  echo "ERROR: $*" >&2
  exit 2
}

to_posix_path() {
  local value="$1"
  if [[ "${value}" =~ ^[A-Za-z]:[/\\] ]]; then
    cygpath -u "${value}"
  elif [[ "${value}" == /* ]]; then
    printf '%s\n' "${value}"
  else
    printf '%s/%s\n' "${PROJECT_ROOT}" "${value}"
  fi
}

to_native_path() {
  cygpath -m "$1"
}

load_dotenv() {
  local env_file="${PROJECT_ROOT}/.env"
  local line name value
  [[ -f "${env_file}" ]] || die "Missing ${env_file}. Copy .env.example and configure it."
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%$'\r'}"
    [[ "${line}" =~ ^[[:space:]]*$ || "${line}" =~ ^[[:space:]]*# ]] && continue
    [[ "${line}" == *=* ]] || die "Invalid .env line: ${line}"
    name="${line%%=*}"
    value="${line#*=}"
    name="${name#"${name%%[![:space:]]*}"}"
    name="${name%"${name##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    [[ "${name}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "Invalid .env variable: ${name}"
    if [[ ${#value} -ge 2 ]]; then
      if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]] || \
         [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
        value="${value:1:${#value}-2}"
      fi
    fi
    printf -v "${name}" '%s' "${value}"
    export "${name}"
  done < "${env_file}"
}

initialize_collection_runtime() {
  command -v cygpath >/dev/null 2>&1 || die "Run this script in Git Bash on Windows."
  load_dotenv
  [[ -f "${PYTHON}" ]] || die "Missing Windows environment. Run: bash scripts/setup/windows-collection.sh"

  local platform_setting="${SC2EXP_PLATFORM_SOURCE:-platform/SC2Bench}"
  PLATFORM_DIR="$(to_posix_path "${platform_setting}")"
  [[ -f "${PLATFORM_DIR}/pyproject.toml" ]] || die "SC2Bench runtime copy is missing: ${PLATFORM_DIR}"

  local platform_native platform_src_native
  platform_native="$(to_native_path "${PLATFORM_DIR}")"
  platform_src_native="$(to_native_path "${PLATFORM_DIR}/src")"
  export SC2EXP_PLATFORM_SOURCE="${platform_native}"
  export PYTHONPATH="${platform_native};${platform_src_native}${PYTHONPATH:+;${PYTHONPATH}}"
  cd "${PROJECT_ROOT}"
}

require_condition() {
  case "$1" in
    T0_teacher_none|T1_marine_rush|T1_two_base_tanks|T1_battlecruisers) ;;
    *) die "Unknown condition: $1" ;;
  esac
}

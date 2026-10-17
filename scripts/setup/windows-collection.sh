#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/lib/windows-common.sh
source "${PROJECT_ROOT}/scripts/lib/windows-common.sh"
load_dotenv

PYTHON39_SETTING="${PYTHON39:-}"
PLATFORM_SOURCE_SETTING="${PLATFORM_SOURCE:-}"
[[ -n "${PYTHON39_SETTING}" ]] || die "Set PYTHON39 to a local Python 3.9 executable."
[[ -n "${PLATFORM_SOURCE_SETTING}" ]] || die "Set PLATFORM_SOURCE to a local SC2Bench Git checkout."
PLATFORM_COMMIT="${PLATFORM_COMMIT:-212e31f963e30dda5b3a903f364380e4cfdade17}"
PLATFORM_DIR="${PROJECT_ROOT}/platform/SC2Bench"
VENV_PYTHON="${PROJECT_ROOT}/.venv/Scripts/python.exe"
PYTHON39_PATH="$(to_posix_path "${PYTHON39_SETTING}")"
PLATFORM_SOURCE_PATH="$(to_posix_path "${PLATFORM_SOURCE_SETTING}")"

command -v git >/dev/null 2>&1 || die "Git is required."

if [[ ! -e "${PLATFORM_DIR}" ]]; then
  [[ -d "${PLATFORM_SOURCE_PATH}/.git" ]] || die "PLATFORM_SOURCE is not a Git checkout: ${PLATFORM_SOURCE_PATH}"
  git clone --no-hardlinks --local "${PLATFORM_SOURCE_PATH}" "${PLATFORM_DIR}"
  git -C "${PLATFORM_DIR}" checkout --detach "${PLATFORM_COMMIT}"
fi

actual_commit="$(git -C "${PLATFORM_DIR}" rev-parse HEAD)"
[[ "${actual_commit}" == "${PLATFORM_COMMIT}" ]] || \
  die "SC2Bench commit mismatch: expected ${PLATFORM_COMMIT}, got ${actual_commit}"
[[ -z "$(git -C "${PLATFORM_DIR}" status --porcelain)" ]] || \
  die "The isolated SC2Bench runtime is dirty: ${PLATFORM_DIR}"

if [[ ! -f "${VENV_PYTHON}" ]]; then
  [[ -f "${PYTHON39_PATH}" ]] || die "Python 3.9 was not found: ${PYTHON39_PATH}"
  "${PYTHON39_PATH}" -m venv "$(to_native_path "${PROJECT_ROOT}/.venv")"
fi

temp_root="$(mktemp -d -t sc2bench-windows-XXXXXX)"
cleanup() {
  [[ -n "${temp_root:-}" && -d "${temp_root}" ]] && rm -rf -- "${temp_root}"
}
trap cleanup EXIT

temp_platform="${temp_root}/SC2Bench"
git clone --quiet --no-hardlinks --local "${PLATFORM_DIR}" "${temp_platform}"
git -C "${temp_platform}" checkout --quiet --detach "${PLATFORM_COMMIT}"

"${VENV_PYTHON}" -m pip install --upgrade pip setuptools wheel
"${VENV_PYTHON}" -m pip install \
  "$(to_native_path "${temp_platform}/dependencies/sc2-pathlib")" \
  "$(to_native_path "${temp_platform}/dependencies/sharpy-sc2")"
"${VENV_PYTHON}" -m pip install "$(to_native_path "${temp_platform}")[sharpy,llm]"
"${VENV_PYTHON}" -m pip install -e "$(to_native_path "${PROJECT_ROOT}")[dev]"
"${VENV_PYTHON}" -m pip check

initialize_collection_runtime
"${PYTHON}" -m sc2bench_experiments doctor
"${PYTHON}" -m sc2bench_env doctor \
  --suite "$(to_native_path "${PROJECT_ROOT}/configs/suites/teacher_macro_mediumhard_smoke.json")"
"${PYTHON}" -m pytest -q

[[ -z "$(git -C "${PLATFORM_DIR}" status --porcelain)" ]] || \
  die "Setup modified the isolated SC2Bench runtime: ${PLATFORM_DIR}"
echo "Windows Teacher collection environment is ready."
echo "Python: $(to_native_path "${PYTHON}")"
echo "SC2Bench: $(to_native_path "${PLATFORM_DIR}") @ ${actual_commit}"

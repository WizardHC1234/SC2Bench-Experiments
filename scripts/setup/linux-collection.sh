#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLATFORM_DIR="${SC2EXP_PLATFORM_SOURCE:-${PROJECT_ROOT}/platform/SC2Bench}"
PLATFORM_URL="${SC2BENCH_GIT_URL:-https://github.com/WizardHC1234/SC2Bench.git}"
PLATFORM_COMMIT="${SC2BENCH_COMMIT:-212e31f963e30dda5b3a903f364380e4cfdade17}"
SC2_PYTHON_BIN="${SC2_PYTHON_BIN:-python3.9}"
SC2_VENV="${SC2_VENV:-${PROJECT_ROOT}/.venv-sc2}"
PATHLIB_URL="https://github.com/DrInfy/sc2-pathlib.git"
PATHLIB_COMMIT="c23fd7387cd8d0898d35bbd9758f7cfb9fbe6f29"

if [[ "${PLATFORM_DIR}" != /* ]]; then
  PLATFORM_DIR="${PROJECT_ROOT}/${PLATFORM_DIR}"
fi
if [[ "${SC2_VENV}" != /* ]]; then
  SC2_VENV="${PROJECT_ROOT}/${SC2_VENV}"
fi

for command_name in git cargo rustc tar; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Missing required command: ${command_name}" >&2
    exit 2
  fi
done
if ! command -v "${SC2_PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python 3.9 is required for the SC2 native runtime: ${SC2_PYTHON_BIN}" >&2
  exit 2
fi

mkdir -p "$(dirname "${PLATFORM_DIR}")"
if [[ ! -d "${PLATFORM_DIR}/.git" ]]; then
  if [[ -e "${PLATFORM_DIR}" ]]; then
    echo "Platform path exists but is not a Git checkout: ${PLATFORM_DIR}" >&2
    exit 2
  fi
  git clone "${PLATFORM_URL}" "${PLATFORM_DIR}"
fi

if ! git -C "${PLATFORM_DIR}" cat-file -e "${PLATFORM_COMMIT}^{commit}" 2>/dev/null; then
  git -C "${PLATFORM_DIR}" fetch --depth 1 origin "${PLATFORM_COMMIT}"
fi
if [[ -n "$(git -C "${PLATFORM_DIR}" status --porcelain)" ]]; then
  echo "Refusing to alter a dirty SC2Bench checkout: ${PLATFORM_DIR}" >&2
  exit 2
fi
git -C "${PLATFORM_DIR}" checkout --detach "${PLATFORM_COMMIT}"

if [[ ! -x "${SC2_VENV}/bin/python" ]]; then
  "${SC2_PYTHON_BIN}" -m venv "${SC2_VENV}"
fi
SC2_PYTHON="${SC2_VENV}/bin/python"
"${SC2_PYTHON}" -m pip install --upgrade pip setuptools wheel

# Build in temporary copies so the pinned SC2Bench checkout remains clean.
NATIVE_SOURCE="$(mktemp -d)"
PACKAGE_COPY_ROOT="$(mktemp -d)"
cleanup() {
  rm -rf -- "${NATIVE_SOURCE}" "${PACKAGE_COPY_ROOT}"
}
trap cleanup EXIT

git clone "${PATHLIB_URL}" "${NATIVE_SOURCE}"
git -C "${NATIVE_SOURCE}" checkout --detach "${PATHLIB_COMMIT}"
export PYO3_PYTHON="${SC2_PYTHON}"
RUST_HOST="$(rustc -vV | sed -n 's/^host: //p')"
cargo build --release --locked --target "${RUST_HOST}" \
  --manifest-path "${NATIVE_SOURCE}/Cargo.toml" \
  --target-dir "${NATIVE_SOURCE}/target"

PATHLIB_COPY="${PACKAGE_COPY_ROOT}/sc2-pathlib"
PLATFORM_COPY="${PACKAGE_COPY_ROOT}/SC2Bench"
mkdir -p "${PLATFORM_COPY}"
git -C "${PLATFORM_DIR}" archive "${PLATFORM_COMMIT}" | tar -x -C "${PLATFORM_COPY}"
cp -a "${PLATFORM_COPY}/dependencies/sc2-pathlib" "${PATHLIB_COPY}"
find "${PATHLIB_COPY}" -type f \( -name '*.pyd' -o -name '*.so' \) -delete
EXTENSION_SUFFIX="$("${SC2_PYTHON}" -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')"
install -m 755 \
  "${NATIVE_SOURCE}/target/${RUST_HOST}/release/libsc2pathlib.so" \
  "${PATHLIB_COPY}/sc2pathlib/sc2pathlib${EXTENSION_SUFFIX}"

"${SC2_PYTHON}" -m pip install \
  "${PATHLIB_COPY}" \
  "${PLATFORM_COPY}/dependencies/sharpy-sc2" \
  "${PLATFORM_COPY}[llm]" \
  -e "${PROJECT_ROOT}[dev]"

SC2EXP_PLATFORM_SOURCE="${PLATFORM_DIR}" \
  "${SC2_PYTHON}" -m sc2bench_experiments doctor
"${SC2_PYTHON}" -m sc2bench_env doctor --backend fake
"${SC2_PYTHON}" -m pytest -q "${PROJECT_ROOT}/tests"

if [[ -n "$(git -C "${PLATFORM_DIR}" status --porcelain)" ]]; then
  echo "SC2Bench became dirty during setup; this violates the read-only boundary." >&2
  exit 3
fi

echo "Collection environment ready: ${SC2_VENV}"
echo "Platform checkout: ${PLATFORM_DIR} @ ${PLATFORM_COMMIT}"

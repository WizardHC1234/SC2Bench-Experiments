#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SFT_PYTHON_BIN="${SFT_PYTHON_BIN:-python3.11}"
SFT_VENV="${SFT_VENV:-${PROJECT_ROOT}/.venv-sft}"
LLAMAFACTORY_DIR="${LLAMAFACTORY_DIR:-${PROJECT_ROOT}/platform/LlamaFactory}"
LLAMAFACTORY_URL="${LLAMAFACTORY_URL:-https://github.com/hiyouga/LlamaFactory.git}"
LLAMAFACTORY_REF="${LLAMAFACTORY_REF:-v0.9.5}"

if [[ "${SFT_VENV}" != /* ]]; then
  SFT_VENV="${PROJECT_ROOT}/${SFT_VENV}"
fi
if [[ "${LLAMAFACTORY_DIR}" != /* ]]; then
  LLAMAFACTORY_DIR="${PROJECT_ROOT}/${LLAMAFACTORY_DIR}"
fi

if ! command -v "${SFT_PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Missing SFT Python interpreter: ${SFT_PYTHON_BIN}" >&2
  exit 2
fi
if [[ ! -x "${SFT_VENV}/bin/python" ]]; then
  "${SFT_PYTHON_BIN}" -m venv "${SFT_VENV}"
fi
SFT_PYTHON="${SFT_VENV}/bin/python"
"${SFT_PYTHON}" -m pip install --upgrade pip wheel

if ! "${SFT_PYTHON}" -c 'import torch, torchvision, torchaudio' >/dev/null 2>&1; then
  if [[ -z "${TORCH_INDEX_URL:-}" ]]; then
    echo "PyTorch packages are missing. Set TORCH_INDEX_URL from the official PyTorch selector." >&2
    exit 2
  fi
  "${SFT_PYTHON}" -m pip install torch torchvision torchaudio \
    --index-url "${TORCH_INDEX_URL}"
fi

mkdir -p "$(dirname "${LLAMAFACTORY_DIR}")"
if [[ ! -d "${LLAMAFACTORY_DIR}/.git" ]]; then
  if [[ -e "${LLAMAFACTORY_DIR}" ]]; then
    echo "LlamaFactory path exists but is not a Git checkout: ${LLAMAFACTORY_DIR}" >&2
    exit 2
  fi
  git clone --branch "${LLAMAFACTORY_REF}" --depth 1 \
    "${LLAMAFACTORY_URL}" "${LLAMAFACTORY_DIR}"
fi
if [[ -n "$(git -C "${LLAMAFACTORY_DIR}" status --porcelain)" ]]; then
  echo "Refusing to alter a dirty LlamaFactory checkout: ${LLAMAFACTORY_DIR}" >&2
  exit 2
fi
git -C "${LLAMAFACTORY_DIR}" fetch --depth 1 origin "${LLAMAFACTORY_REF}"
git -C "${LLAMAFACTORY_DIR}" checkout --detach FETCH_HEAD

"${SFT_PYTHON}" -m pip install -e "${LLAMAFACTORY_DIR}"
"${SFT_PYTHON}" -m pip install -e "${PROJECT_ROOT}"
if [[ "${INSTALL_BITSANDBYTES:-0}" == "1" ]]; then
  "${SFT_PYTHON}" -m pip install bitsandbytes
fi
export REQUIRE_CUDA="${REQUIRE_CUDA:-1}"
"${SFT_PYTHON}" - <<'PY'
import importlib.metadata
import os
import sys
import torch
print(f"llamafactory={importlib.metadata.version('llamafactory')}")
print(f"torch={torch.__version__}")
print(f"torchvision={importlib.metadata.version('torchvision')}")
print(f"torchaudio={importlib.metadata.version('torchaudio')}")
print(f"cuda_available={torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"gpu={torch.cuda.get_device_name(0)}")
    print(f"capability={torch.cuda.get_device_capability(0)}")
elif os.environ.get("REQUIRE_CUDA", "1") == "1":
    print("CUDA is required but unavailable in this environment.", file=sys.stderr)
    raise SystemExit(3)
PY

echo "SFT environment ready: ${SFT_VENV}"
echo "LlamaFactory: ${LLAMAFACTORY_DIR} @ $(git -C "${LLAMAFACTORY_DIR}" rev-parse HEAD)"

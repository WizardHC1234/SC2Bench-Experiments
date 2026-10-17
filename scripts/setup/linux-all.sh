#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

bash "${PROJECT_ROOT}/scripts/setup/linux-collection.sh"

if [[ "${SKIP_SFT_BOOTSTRAP:-0}" == "1" ]]; then
  echo "Skipping the SFT environment because SKIP_SFT_BOOTSTRAP=1."
else
  bash "${PROJECT_ROOT}/scripts/setup/linux-sft.sh"
fi

echo "Linux environments are ready. Run: bash scripts/collection/check-linux.sh"


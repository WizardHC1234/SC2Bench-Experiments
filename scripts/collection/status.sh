#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/lib/windows-common.sh
source "${PROJECT_ROOT}/scripts/lib/windows-common.sh"
initialize_collection_runtime

"${PYTHON}" -m sc2bench_experiments teacher-status \
  --config configs/experiments/teacher_deepseek_v4_flash_fixed_styles_20_per_cell.json

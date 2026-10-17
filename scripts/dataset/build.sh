#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/lib/windows-common.sh
source "${PROJECT_ROOT}/scripts/lib/windows-common.sh"

input="runs/raw/teacher_deepseek_v4_flash_fixed_styles_20_per_cell"
output="data/processed/teacher_deepseek_v4_flash_fixed_styles_20_per_cell"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input) [[ $# -ge 2 ]] || die "--input requires a value"; input="$2"; shift 2 ;;
    --output) [[ $# -ge 2 ]] || die "--output requires a value"; output="$2"; shift 2 ;;
    -h|--help) echo "Usage: bash scripts/dataset/build.sh [--input PATH] [--output PATH]"; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done
initialize_collection_runtime
"${PYTHON}" -m sc2bench_experiments build-dataset \
  --input "${input}" --output "${output}"
"${PYTHON}" -m sc2bench_experiments validate-dataset --input "${output}"

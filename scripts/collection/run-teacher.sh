#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/lib/windows-common.sh
source "${PROJECT_ROOT}/scripts/lib/windows-common.sh"

mode="dry-run"
skip_check=0
force_rerun=0
conditions=()

usage() {
  cat <<'EOF'
Usage: bash scripts/collection/run-teacher.sh [options]
  --mode dry-run|smoke|all
  --condition CONDITION       May be repeated.
  --skip-check
  --force-rerun               Do not use --resume; can create duplicates.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) [[ $# -ge 2 ]] || die "--mode requires a value"; mode="${2,,}"; shift 2 ;;
    --condition) [[ $# -ge 2 ]] || die "--condition requires a value"; require_condition "$2"; conditions+=("$2"); shift 2 ;;
    --skip-check) skip_check=1; shift ;;
    --force-rerun) force_rerun=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "Unknown argument: $1" ;;
  esac
done

case "${mode}" in
  dry-run) config="configs/experiments/teacher_deepseek_v4_flash_fixed_styles_20_per_cell.json" ;;
  smoke) config="configs/experiments/teacher_deepseek_v4_flash_fixed_style_smoke.json" ;;
  all) config="configs/experiments/teacher_deepseek_v4_flash_fixed_styles_20_per_cell.json" ;;
  *) die "--mode must be dry-run, smoke, or all" ;;
esac

initialize_collection_runtime
if [[ "${mode}" != "dry-run" && "${skip_check}" == "0" ]]; then
  bash "${PROJECT_ROOT}/scripts/collection/check.sh" --skip-dry-run
fi

args=(-m sc2bench_experiments run-teacher --config "${config}")
if [[ "${mode}" == "dry-run" ]]; then
  args+=(--dry-run)
else
  args+=(--execute)
  [[ "${force_rerun}" == "1" ]] || args+=(--resume)
fi
for condition in "${conditions[@]}"; do
  args+=(--condition "${condition}")
done

mkdir -p "${PROJECT_ROOT}/runs/logs"
stamp="$(date +%Y%m%d-%H%M%S)"
log_path="${PROJECT_ROOT}/runs/logs/teacher-${mode}-${stamp}.log"
echo "Mode: ${mode}"
echo "Config: ${config}"
echo "Log: $(to_native_path "${log_path}")"
"${PYTHON}" "${args[@]}" 2>&1 | tee "${log_path}"

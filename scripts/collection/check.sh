#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/lib/windows-common.sh
source "${PROJECT_ROOT}/scripts/lib/windows-common.sh"

skip_dry_run=0
if [[ "${1:-}" == "--skip-dry-run" ]]; then
  skip_dry_run=1
elif [[ $# -gt 0 ]]; then
  die "Usage: bash scripts/collection/check.sh [--skip-dry-run]"
fi

initialize_collection_runtime
"${PYTHON}" --version
"${PYTHON}" -m sc2bench_experiments doctor
"${PYTHON}" -m sc2bench_env doctor \
  --suite "$(to_native_path "${PROJECT_ROOT}/configs/suites/teacher_macro_mediumhard_smoke.json")"

"${PYTHON}" - <<'PY'
import json
import os
import urllib.request

base_url = os.environ["LLM_BASE_URL"].rstrip("/")
request = urllib.request.Request(
    f"{base_url}/models",
    headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
)
with urllib.request.urlopen(request, timeout=20) as response:
    payload = json.load(response)
models = payload.get("data") or []
if not models:
    raise SystemExit("Teacher API returned no models")
print(f"Teacher API reachable: {base_url}/models")
print(f"Configured model alias: {os.environ['LLM_MODEL']}")
print(f"Served model: {models[0].get('id')}")
PY

if [[ "${skip_dry_run}" == "0" ]]; then
  "${PYTHON}" -m sc2bench_experiments run-teacher \
    --config configs/experiments/teacher_deepseek_v4_flash_fixed_style_smoke.json --dry-run
fi
echo "Collection preflight passed. No SC2 match was launched."

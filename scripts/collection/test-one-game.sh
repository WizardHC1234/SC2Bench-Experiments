#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/lib/windows-common.sh
source "${PROJECT_ROOT}/scripts/lib/windows-common.sh"

condition="T1_two_base_tanks"
skip_checks=0
force_rerun=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --condition) [[ $# -ge 2 ]] || die "--condition requires a value"; condition="$2"; shift 2 ;;
    --skip-checks) skip_checks=1; shift ;;
    --force-rerun) force_rerun=1; shift ;;
    -h|--help)
      echo "Usage: bash scripts/collection/test-one-game.sh [--condition CONDITION] [--skip-checks] [--force-rerun]"
      exit 0
      ;;
    *) die "Unknown argument: $1" ;;
  esac
done
require_condition "${condition}"
initialize_collection_runtime

if [[ "${skip_checks}" == "0" ]]; then
  bash "${PROJECT_ROOT}/scripts/collection/check.sh" --skip-dry-run
  bash "${PROJECT_ROOT}/scripts/collection/test-teacher-api.sh"
fi

run_args=(--mode smoke --condition "${condition}" --skip-check)
[[ "${force_rerun}" == "0" ]] || run_args+=(--force-rerun)
echo "Launching exactly one smoke configuration: ${condition}"
bash "${PROJECT_ROOT}/scripts/collection/run-teacher.sh" "${run_args[@]}"

export SC2EXP_TEST_CONDITION="${condition}"
"${PYTHON}" - <<'PY'
import json
import os
from pathlib import Path

root = Path("runs/raw/teacher_deepseek_v4_flash_fixed_style_smoke")
condition = os.environ["SC2EXP_TEST_CONDITION"]
batch_files = sorted(
    (root / condition).glob("batch_*/batch.json"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
)
if not batch_files:
    raise SystemExit(f"No batch.json was produced for {condition}")

chosen = None
last_failure = None
for batch_file in batch_files:
    batch = json.loads(batch_file.read_text(encoding="utf-8"))
    for episode in reversed(batch.get("episodes") or []):
        if episode.get("status") == "completed":
            chosen = (batch_file, episode)
            break
        last_failure = episode
    if chosen:
        break
if chosen is None:
    detail = json.dumps(last_failure or {}, ensure_ascii=False)
    raise SystemExit(f"The one-game test did not complete successfully: {detail}")

batch_file, episode = chosen
record_dir = Path(episode["record_directory"])
required = [record_dir / name for name in ("episode.txt", "session.json", "metrics.json")]
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise SystemExit(f"Completed episode is missing artifacts: {missing}")

session = json.loads((record_dir / "session.json").read_text(encoding="utf-8"))
metrics = json.loads((record_dir / "metrics.json").read_text(encoding="utf-8"))
messages = session.get("messages") or []
if not messages:
    raise SystemExit("session.json contains no messages")
system_text = "\n".join(
    str(message.get("content") or "")
    for message in messages
    if isinstance(message, dict) and message.get("role") == "system"
)
has_skill = "[Agent Skill:" in system_text
if condition == "T0_teacher_none" and has_skill:
    raise SystemExit("T0 unexpectedly contains a Skill prompt")
if condition != "T0_teacher_none" and not has_skill:
    raise SystemExit("Skill condition is missing the Skill prompt")
if not any(
    isinstance(message, dict)
    and message.get("role") == "assistant"
    and message.get("tool_calls")
    for message in messages
):
    raise SystemExit("session.json contains no assistant tool calls")

summary = metrics.get("summary") or {}
integrity = summary.get("integrity") or {}
if integrity.get("ok") is not True:
    raise SystemExit(f"Episode integrity failed: {integrity.get('errors')}")

print("\nONE-GAME TEST PASSED")
print(f"condition:       {condition}")
print(f"outcome:         {episode.get('outcome')}")
print(f"result:          {episode.get('result')}")
print(f"end_reason:      {episode.get('end_reason')}")
print(f"decision_count:  {episode.get('decision_count')}")
print(f"rejected_count:  {episode.get('rejected_count')}")
print(f"integrity_ok:    {integrity.get('ok')}")
print(f"batch:           {batch_file.resolve()}")
print(f"record:          {record_dir.resolve()}")
PY

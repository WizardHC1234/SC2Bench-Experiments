#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/lib/windows-common.sh
source "${PROJECT_ROOT}/scripts/lib/windows-common.sh"
initialize_collection_runtime

"${PYTHON}" - <<'PY'
import json
import os
import urllib.request

payload = {
    "model": os.environ["LLM_MODEL"],
    "messages": [
        {"role": "system", "content": "Call exactly one provided tool."},
        {"role": "user", "content": "Call advance with seconds set to 5."},
    ],
    "temperature": 0.0,
    "stream": False,
    "tools": [{
        "type": "function",
        "function": {
            "name": "advance",
            "description": "Advance game time.",
            "parameters": {
                "type": "object",
                "properties": {"seconds": {"type": "integer"}},
                "required": ["seconds"],
                "additionalProperties": False,
            },
        },
    }],
    "tool_choice": "auto",
    "chat_template_kwargs": {"thinking": False, "enable_thinking": False},
    "response_format": {"type": "text"},
}
request = urllib.request.Request(
    f"{os.environ['LLM_BASE_URL'].rstrip('/')}/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {os.environ['LLM_API_KEY']}",
        "Content-Type": "application/json",
    },
    method="POST",
)
with urllib.request.urlopen(request, timeout=60) as response:
    result = json.load(response)
calls = result.get("choices", [{}])[0].get("message", {}).get("tool_calls") or []
if len(calls) != 1 or calls[0].get("function", {}).get("name") != "advance":
    raise SystemExit("Teacher endpoint did not return the required OpenAI tool call")
print("Teacher tool-call probe passed.")
print(json.dumps(calls[0], ensure_ascii=False, indent=2))
PY

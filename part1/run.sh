#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

if [[ "${1:-}" == "--sidecar" ]]; then
  exec python3 -m fallguard.fallguard --event-log "${ROOT_DIR}/evidence/event-log.csv"
fi

if command -v gst-launch-1.0 >/dev/null 2>&1 && python3 -c 'import gi' >/dev/null 2>&1; then
  exec python3 "${ROOT_DIR}/pipegen/stage5_run/pipeline.py" \
    --sidecar-cmd "python3 -m fallguard.fallguard --event-log ${ROOT_DIR}/evidence/event-log.csv"
fi

echo "DeepStream/PipeGen runtime is not installed. Use --sidecar for metadata replay." >&2
exit 2

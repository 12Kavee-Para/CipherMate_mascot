#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ ! -x .venv/bin/python ]]; then
  printf '%s\n' 'Create .venv and install requirements-dev.txt first (see README).'
  exit 1
fi
config="$HOME/.local/state/ciphermate/runtime.env"
if [[ ! -f "$config" ]]; then .venv/bin/python scripts/init_local.py; fi
# This is trusted local operator configuration, not uploaded data.
source "$config"
export CM_LOCAL_DEMO=1
exec .venv/bin/python -m uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log --no-proxy-headers --limit-concurrency 32

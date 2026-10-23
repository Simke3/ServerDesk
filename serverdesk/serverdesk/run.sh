#!/usr/bin/env bash
# Starts ServerDesk from the source tree, creating a local virtualenv on first run.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip >/dev/null
  .venv/bin/pip install -r requirements.txt
fi
exec .venv/bin/python -m serverdesk "$@"

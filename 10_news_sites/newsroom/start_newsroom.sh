#!/usr/bin/env sh
# Start the newsroom. Add --lan to serve the shared network; other options: --port N --passphrase TEXT --reset
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then exec python3 server.py "$@"; else exec python server.py "$@"; fi

#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
executable="$project_root/dist/Hypatia/Hypatia"

if [[ ! -x "$executable" ]]; then
    echo "Packaged Hypatia executable was not found at $executable." >&2
    exit 1
fi

if ! command -v xvfb-run >/dev/null 2>&1; then
    echo "xvfb-run is required for the headless desktop startup check." >&2
    exit 1
fi

smoke_root="$(mktemp -d "${TMPDIR:-/tmp}/hypatia-linux-smoke.XXXXXX")"
process_id=""

cleanup() {
    if [[ -n "$process_id" ]] && kill -0 "$process_id" 2>/dev/null; then
        kill "$process_id" 2>/dev/null || true
        wait "$process_id" 2>/dev/null || true
    fi
    rm -rf -- "$smoke_root"
}
trap cleanup EXIT

export HYPATIA_DESKTOP_DATA_DIR="$smoke_root"
xvfb-run -a "$executable" &
process_id=$!
sleep 3

if ! kill -0 "$process_id" 2>/dev/null; then
    wait "$process_id"
    echo "Packaged Hypatia exited before the startup check completed." >&2
    exit 1
fi

expected_session_path="$smoke_root/sessions/sessions.json"
if [[ ! -f "$expected_session_path" ]]; then
    echo "Packaged Hypatia did not initialize $expected_session_path." >&2
    exit 1
fi

echo "Packaged Linux desktop startup smoke check passed."

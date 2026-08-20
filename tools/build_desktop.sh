#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python="$project_root/.venv/bin/python"
entry_point="$project_root/src/desktop_main.py"
source_path="$project_root/src"
build_root="$project_root/build/desktop-linux"
work_path="$build_root/work"
spec_path="$build_root/spec"
distribution_path="$project_root/dist"
executable="$distribution_path/Hypatia/Hypatia"

if [[ ! -x "$python" ]]; then
    echo "Hypatia virtual environment was not found at $python." >&2
    exit 1
fi

if [[ ! -f "$entry_point" ]]; then
    echo "Desktop entry point was not found at $entry_point." >&2
    exit 1
fi

if ! "$python" -c "import PyInstaller"; then
    echo "PyInstaller is required." >&2
    echo "Run '$python -m pip install -r requirements-desktop-build.txt'." >&2
    exit 1
fi

if [[ "${1:-}" == "--clean" ]]; then
    rm -rf -- "$build_root" "$distribution_path/Hypatia"
elif [[ $# -ne 0 ]]; then
    echo "Usage: tools/build_desktop.sh [--clean]" >&2
    exit 2
fi

"$python" -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --onedir \
    --name Hypatia \
    --paths "$source_path" \
    --distpath "$distribution_path" \
    --workpath "$work_path" \
    --specpath "$spec_path" \
    "$entry_point"

if [[ ! -x "$executable" ]]; then
    echo "Hypatia desktop package did not produce $executable." >&2
    exit 1
fi

echo "Desktop package created: $executable"

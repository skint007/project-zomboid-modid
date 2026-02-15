#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

python -m nuitka \
    --onefile \
    --enable-plugin=pyside6 \
    --include-package=pz_mod_manager \
    --output-filename=pz-mod-manager \
    --output-dir=dist \
    --remove-output \
    src/pz_mod_manager/__main__.py

echo "Build complete: dist/pz-mod-manager"

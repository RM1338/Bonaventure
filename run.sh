#!/usr/bin/env bash
# macOS launch environment shared by Terminal, Finder and the login wrapper.
if [ "$(uname -s)" != "Darwin" ]; then
  echo "This is the macOS branch. Use main for Omarchy/Linux or windows for Windows." >&2
  exit 1
fi
export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1
if command -v brew >/dev/null 2>&1; then
  export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
fi
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Missing .venv/bin/python. Follow docs/MACOS_SETUP.md to create the Homebrew Python environment." >&2
  exit 1
fi
if [ "${1:-}" = "--check-runtime" ]; then
  exec .venv/bin/python -c "import webview, AppKit, numpy, PIL, weasyprint"
fi
exec .venv/bin/python -m bonaventure.app "$@"

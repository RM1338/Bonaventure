#!/usr/bin/env bash
# Launch Bonaventure. BV_MOCK=1 ./run.sh skips the real models (UI development / no GPU).
# WebKitGTK renders through NVIDIA's EGL by default on hybrid laptops, which crashed the renderer under VRAM pressure
# from the models. Keep the UI on the Intel/Mesa GPU and off the DMA-BUF path; torch still uses CUDA directly.
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1   # everything is on disk; never touch the network
case "$(uname -s)" in
  Linux)
    export WEBKIT_DISABLE_DMABUF_RENDERER=1
    export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    [ -f /usr/share/glvnd/egl_vendor.d/50_mesa.json ] && export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
    ;;
  Darwin)
    # WeasyPrint needs Homebrew's Pango libraries, including from the app/login wrapper.
    if command -v brew >/dev/null 2>&1; then
      export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
    fi
    ;;
esac
cd "$(dirname "$0")" && exec .venv/bin/python -m bonaventure.app "$@"

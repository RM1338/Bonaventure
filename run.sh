#!/usr/bin/env bash
# Launch Bonaventure. BV_MOCK=1 ./run.sh skips the real models (UI development / no GPU).
# WebKitGTK renders through NVIDIA's EGL by default on hybrid laptops, which crashed the renderer under VRAM pressure
# from the models. Keep the UI on the Intel/Mesa GPU and off the DMA-BUF path; torch still uses CUDA directly.
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1   # everything is on disk; never touch the network
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
[ -f /usr/share/glvnd/egl_vendor.d/50_mesa.json ] && export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
cd "$(dirname "$0")" && exec .venv/bin/python -m bonaventure.app "$@"

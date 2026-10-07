# Architecture diagram notes

The four figures from Joseph's [PR #8](https://github.com/RM1338/Bonaventure/pull/8)
document the Linux/CUDA configuration and the shared evidence workflow. The
original exported images and their editable Lucidchart link are retained. Read
them with the following details of the current merged implementation.

## Platform and runtime

The desktop row shows the Linux WebKitGTK/Hyprland shell and PipeWire recorder.
macOS uses `macos_app.py`, `island_macos.html`, AppKit controls/native pickers and
ffmpeg/AVFoundation recording. Both share `desktop.Api`, the pipeline and review
UI. Windows uses `windows_app.py`, the shared island/review UI and a native
`Ctrl+Alt+B` hotkey; PDF export uses headless Edge. See
[WINDOWS_SETUP.md](WINDOWS_SETUP.md) for its separate setup. See [MACOS_SETUP.md](MACOS_SETUP.md) for the native Mac setup.

MedGemma's NF4/GPU label describes the Linux CUDA configuration. On supported
Macs it uses unquantized MPS bfloat16, with float32 fallback; CPU is also
supported. MedSAM retains its CUDA/CPU selection. These choices are implemented
in [model_runtime.py](../bonaventure/model_runtime.py) and
[models.py](../bonaventure/models.py).

The diagram's Python 3.12 and 6–25-second timing labels describe an earlier
snapshot. The current verified Omarchy environment uses system Python 3.14.7;
the documented Homebrew Mac setup selects Python 3.12. The latest verified
Linux case 02 took 32.56 seconds of pipeline time, excluding initial model
loading. These timings do not establish Mac latency or a case-wide guarantee.

## Presentation processing

The comparison between original wording and a clinical rewrite remains part of
the pipeline, but known clauses are parsed directly. Only unmatched clauses are
sent for rewriting: at most 12 clauses of at most 500 characters, a two-second
lock wait and a default 30-second cooperative decoding budget. Failure preserves
the original wording and warnings; unmatched phrases can use the optional
MiniLM fallback. See [presentation.py](../bonaventure/presentation.py) and
[pipeline.py](../bonaventure/pipeline.py).

## Reading the image and decision flow

The occlusion grid evaluates the original image plus 64 occluded images; the
encoder processes them in batches. The “65 passes” label counts image
evaluations. The confidence percentage describes image evidence after Platt
calibration, while high/moderate/low strength summarizes rules and context.

The key-symptom-denial decision assumes at least one key symptom is explicitly
denied; zero denials do not trigger a conflict merely because support is also
zero. Device and bare-film rules and concept-bank constraints add conditions to
the main flow. The exact conditions and ordering are in
[reconcile.py](../bonaventure/reconcile.py); the diagram summarizes them.

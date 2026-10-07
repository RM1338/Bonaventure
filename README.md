# Bonaventure — Clinical Evidence Intelligence

A clinician-facing chest X-ray **evidence reconciliation** assistant (HackNex 2026 · HNX26PSI05).
It reads a chest X-ray, the patient's history documents and the current presentation, and for every candidate
finding decides whether the evidence **SUPPORTS** it, **CONFLICTS**, is **UNCERTAIN**, or is **INSUFFICIENT** —
showing exactly where on the film, which history fact (document + page + quote) and which symptom drove that call.

> Decision support only. Not a diagnosis. Every output must be reviewed by a qualified clinician.

## What it looks like

- **Island launcher** — the original floating pill on Linux; a black notch extension with a menu bar icon on macOS.
  Drop the X-ray, the history PDFs, type the presentation, *Analyse*. Progress is shown inside the island.
- **Reading room** — the result opens in a dark reading room: the film on a wall viewbox with grease-pencil marks traced
  along MedSAM's outline, a patient-context panel (complaint, symptoms, dated history with sources) and an evidence panel
  with each finding's state, an evidence triangle (image · history · presentation), what each of the four models said,
  CLEAR's matching concepts and the impression.
- **Evidence report** — a printable PDF with the annotated film, per-finding evidence, sources and limitations.

## Desktop platforms

The same `./run.sh` command chooses the desktop implementation automatically:

| Platform | Launcher | Activation |
|---|---|---|
| Linux | Original launcher (`bonaventure/linux_app.py`, `bonaventure/ui/island_linux.html`) | Click the pill or configure `scripts/bonaventure-toggle` in your desktop's shortcuts/bar |
| macOS | Notch launcher (`bonaventure/macos_app.py`, `bonaventure/ui/island.html`) | Option + Command + B, menu bar icon, or hover below the notch |

`bonaventure/app.py` selects the implementation before importing desktop code.
Linux does not import the macOS launcher, AppKit controls, or global hotkey code,
and does not load the macOS launcher HTML. Its launcher and UI are preserved from
the original Linux version. On Hyprland, its existing placement and window rules
still apply; other Linux desktops use ordinary pywebview window resizing.
`Super + Alt + B` is a suggested Linux binding, not an automatically registered shortcut.

Both platforms share the reading room, analysis pipeline, reports, Python
requirements, and model paths under `models/` (not `models/Models/`). The macOS
background installer is macOS-only and refuses to run on Linux.
The original Linux setup was tested on Arch/Omarchy with Hyprland; Ubuntu and
other desktop environments still need runtime verification. Platform-routing
tests do not replace native GUI and inference checks.

## How it works

```
X-ray ──► quality gate ──► CLEAR (primary) ──► concept bank: 368,294 observations ranked against the film
                         └► CheXzero (verifier)
                              │  candidates with any signal
                              ▼
                         MedGemma 1.5: what is visible + a box ──► MedSAM: box → mask → outline
History PDFs ──► text → concepts, negation, dates, provenance (file, page, quote) ─┐
Presentation ──► symptoms present / denied, durations ───────────────────────────┤
                                                                                  ▼
                                 Evidence reconciliation (bonaventure/reconcile.py)
                                 image agreement × history × symptoms × quality
                                 → SUPPORTED / UNCERTAIN / CONFLICTING / INSUFFICIENT_EVIDENCE + reasons
```

Reconciliation rules (explicit, every status carries its reasons):

| Situation | State |
|---|---|
| Image quality poor | INSUFFICIENT_EVIDENCE |
| Primary and verifier disagree strongly | CONFLICTING |
| Image positive, but the records explicitly contradict it (e.g. recent report: "normal heart size") | CONFLICTING |
| Image positive, key symptoms denied and outnumber support | CONFLICTING |
| Both image models positive + supporting context | SUPPORTED |
| Weak / partial image signal | UNCERTAIN or INSUFFICIENT_EVIDENCE |

**What it can recognise.** 16 catalogue findings, each read by two calibrated image models — pleural effusion, cardiomegaly,
pulmonary edema, consolidation, pneumonia, atelectasis, pneumothorax, lung nodule, lung mass, emphysema, pulmonary fibrosis,
pleural thickening, widened mediastinum, hiatus hernia, rib fracture, lines & devices. Anything else MedGemma sees on the film
(open-ended survey: "list every abnormal finding") is shown as *also seen — single reader, unverified*, never as a finding.
Conditions a chest X-ray cannot settle — **pulmonary embolism**, aortic dissection — are raised as *not assessable on a chest
X-ray* when the history/presentation points to them, with the appropriate next test, instead of being guessed from the film.

Evidence strength (high / moderate / low) is a rule-based summary of agreement between calibrated readers, **not** a probability.
MedGemma never creates findings; it only describes and localizes candidates raised by the image models.

## Evaluation & calibration

Both image readers were evaluated on labelled chest X-rays (`scripts/calibrate.py`): the **CheXpert v1.0 validation set**
(radiologist consensus, 202 frontal films) where it has enough positives, otherwise a per-finding sample from the
**NIH ChestX-ray14** test split (676 films, NLP-mined labels — noisier, so its numbers are conservative). For every finding
and reader the evidence levels are read off that finding's ROC curve — *weak* = 90 % sensitivity, *moderate* = Youden's J,
*strong* = 90 % specificity — and stored in `bonaventure/calibration.json`.

**A reader only votes on findings where it reached AUROC ≥ 0.70.** Findings no reader can separate reliably are never
raised by the image models; if MedGemma names them in its open-ended survey they appear only as *also seen*, and only when
CLEAR — reading the same phrase zero-shot against the film — agrees.

| Finding | Source (positives) | CLEAR AUROC | CheXzero AUROC | Both | Votes |
|---|---|---|---|---|---|
| Pleural effusion | CheXpert (64+) | 0.909 | 0.884 | 0.904 | CLEAR + CheXzero |
| Cardiomegaly | CheXpert (66+) | 0.848 | 0.825 | 0.843 | CLEAR + CheXzero |
| Pulmonary edema | CheXpert (42+) | 0.912 | 0.906 | 0.935 | CLEAR + CheXzero |
| Consolidation | CheXpert (32+) | 0.901 | 0.851 | 0.897 | CLEAR + CheXzero |
| Atelectasis | CheXpert (75+) | 0.814 | 0.786 | 0.817 | CLEAR + CheXzero |
| Pneumothorax | CheXpert (7+) | 0.785 | 0.763 | 0.800 | CLEAR + CheXzero |
| Widened mediastinum | CheXpert (105+) | 0.880 | 0.877 | 0.900 | CLEAR + CheXzero |
| Lines & devices | CheXpert (99+) | 0.736 | 0.730 | 0.755 | CLEAR + CheXzero |
| Pleural thickening | NIH (85+) | 0.699 | 0.730 | 0.734 | CheXzero |
| Pneumonia | NIH (60+) | 0.724 | 0.689 | 0.715 | CLEAR |
| Hiatus hernia | NIH (30+) | 0.531 | 0.859 | 0.724 | CheXzero |
| Lung mass | NIH (79+) | 0.673 | 0.619 | 0.656 | none → only via MedGemma survey, verified by CLEAR |
| Emphysema | NIH (68+) | 0.627 | 0.548 | 0.573 | none → only via MedGemma survey, verified by CLEAR |
| Pulmonary fibrosis | NIH (68+) | 0.627 | 0.546 | 0.561 | none → only via MedGemma survey, verified by CLEAR |
| Lung nodule | NIH (82+) | 0.535 | 0.514 | 0.531 | none → only via MedGemma survey, verified by CLEAR |
| Rib fracture | — | — | — | — | no labels available → never raised by the image models |

Other guards: a finding needs one reader at *moderate* or both at *weak* (a single voter must be *strong*); a specific finding
suppresses its overlapping parent (cardiomegaly → widened mediastinum, consolidation → pneumonia); when the image readers
disagree MedGemma breaks the tie (2–1 → UNCERTAIN). Both normal sample films produce **no findings**.

## Install (Linux, tested on Arch/Omarchy + Hyprland, RTX 3050 6 GB)

`./run.sh` automatically selects the original Linux desktop implementation
(`linux_app.py` and `ui/island_linux.html`). The macOS notch launcher uses a
separate implementation and is never imported on Linux. Model setup is shared.

```bash
sudo pacman -S --needed webkit2gtk-4.1 python-gobject poppler      # system deps
uv venv --python /usr/bin/python3 --system-site-packages .venv      # system site-packages for GTK bindings
uv pip install --python .venv/bin/python torch torchvision --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv/bin/python -r requirements.txt
```

These system-package commands are for Arch/Omarchy. On Ubuntu or another distro,
install the corresponding WebKitGTK 4.1, PyGObject/GTK, Python virtual-environment,
Poppler, and WeasyPrint native dependencies through that distro's package manager.
Use a virtual environment with access to the system GTK bindings, as above.

## Models (both platforms)

```bash
# model code + weights (see docs/13_MODEL_RESOURCE_REGISTER.md)
mkdir -p models/CLEAR
git clone https://github.com/peterhan91/CLEAR models/CLEAR/code
git clone https://github.com/rajpurkarlab/CheXzero models/CheXzero
git clone https://github.com/bowang-lab/MedSAM models/MedSAM
hf download peterhan91/CLEAR best_model.pt concept_embeddings_368294.pt mimic_concepts.csv --local-dir models/CLEAR
hf download google/medgemma-1.5-4b-it --local-dir models/MedGemma  # gated: accept the licence + `hf auth login` first
.venv/bin/python scripts/patch_clear_loader.py
```

Skip clones/downloads for assets already present. Following the
[CheXzero README](https://github.com/rajpurkarlab/CheXzero#model-checkpoints), download
`best_128_0.0002_original_15000_0.859.pt` from its linked Google Drive folder into
`models/CheXzero/checkpoints/chexzero_weights/`. Place the MedSAM checkpoint at
`models/MedSAM/work_dir/MedSAM/medsam_vit_b.pth`, as described in the
[MedSAM README](https://github.com/bowang-lab/MedSAM#get-started).

The default layout is:

```text
models/
  CLEAR/
    code/src/clear/                 # GitHub source; separate from the weights
    best_model.pt
    concept_embeddings_368294.pt
    mimic_concepts.csv
  CheXzero/
    model.py
    checkpoints/chexzero_weights/best_128_0.0002_original_15000_0.859.pt
  MedSAM/
    segment_anything/
    work_dir/MedSAM/medsam_vit_b.pth
  MedGemma/
    config.json
    model.safetensors.index.json
    model-00001-of-00002.safetensors
    model-00002-of-00002.safetensors
    ...                            # tokenizer and processor files
```

`BV_MODELS_DIR` overrides the whole model directory. Individual overrides are
`BV_CLEAR_DIR` (weights/concepts), `BV_CLEAR_CODE` (GitHub source),
`BV_CLEAR_CKPT`, `BV_CHEXZERO_DIR`, `BV_CHEXZERO_CKPT`, `BV_MEDSAM_DIR`,
`BV_MEDSAM_CKPT`, and `BV_MEDGEMMA`.

`BV_MEDGEMMA=/path/to/medgemma` points at a local copy; `BV_MOCK=1` runs the UI without models (clearly labelled demo mode).

## Install (macOS)

Install native dependencies with Homebrew, then Python packages in the project's
virtual environment:

```bash
brew install pango poppler
# Install uv without relying on Apple's Xcode Python shim:
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
uv venv --python 3.12 --clear .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python scripts/check_setup.py
BV_MOCK=1 BV_START=expand ./run.sh
```

If you already have a working Homebrew Python, pip is also supported:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/check_setup.py
```

Use the project virtual environment rather than system-wide `pip3 install`.
If an existing `.venv` points at Apple's unavailable Xcode Python, recreate it
with the uv commands above. Install the shared model files described in
[Models (both platforms)](#models-both-platforms) before running real inference.

Then close the mock app and run `BV_START=expand ./run.sh` for real inference.
On macOS, `./run.sh` starts with a black cap covering the notch and a Bonaventure
icon in the menu bar. Use **Option + Command + B** from any app, the icon's
**Open launcher / Hide launcher** action, or hover below the notch for 0.2 seconds
to reveal it. The idle panel includes an invisible activation area below and on
either side of the camera. Hover reveals dismiss after the pointer leaves for
0.5 seconds; clicking or typing in the launcher keeps it open. Escape
hides it (except during analysis). Scans, records, and presentation text survive
hiding. On screens without a notch, hover below the center of the menu bar.
macOS controls the icon's ordering among other menu bar items. If another app
already owns the shortcut, the menu reports that it is unavailable.
The borderless panel reaches the screen's top edge and reserves the full camera
and menu-bar height. Expansion grows a black shell with a smooth timing curve;
content fades in after the shell starts opening, and disappears before collapse.
Reduce Motion disables these transitions. The interaction design is informed by
[NotchBox](https://github.com/chrisdemir/notchBOX), implemented using the existing
Python/AppKit frontend without bundling its source.

To run without Terminal and automatically at login, quit the current Bonaventure
instance using its menu, then run this once:

```bash
.venv/bin/python scripts/install_macos.py
```

This installs `~/Applications/Bonaventure.app` and a login LaunchAgent, then starts
the background app. Open Bonaventure from Finder or Spotlight after manually
quitting it. This development wrapper uses this checkout and `.venv`; keep both
in place. Logs are at `~/Library/Logs/Bonaventure/bonaventure.log`. Use
`scripts/install_macos.py --no-login` to install without login startup, or
`scripts/install_macos.py --uninstall` to remove the wrapper and login agent.
Both commands use `.venv/bin/python` as above. To inspect activation from Terminal
without loading models: `BV_MOCK=1 BV_DEBUG=1 ./run.sh`.

The current adapters use CUDA when available, otherwise CPU; Apple MPS is not
enabled. MedGemma runs without 4-bit CUDA quantization on macOS, so real inference
needs considerably more RAM and time than the tested NVIDIA setup. A setup check
verifies packages and local files without loading weights; it does not verify the
native GUI, checkpoint contents, or successful inference. CLEAR also downloads
DINOv2 architecture code via `torch.hub` on first load, as documented in its
[upstream README](https://github.com/peterhan91/CLEAR#installation).
Run `.venv/bin/python scripts/patch_clear_loader.py` after cloning CLEAR to avoid
PyTorch's GitHub API lookup failing with `KeyError('Authorization')`.

## Run

```bash
./run.sh                    # original Linux launcher or macOS notch launcher
BV_START=expand ./run.sh    # start with intake open
BV_MOCK=1 BV_START=expand ./run.sh  # UI demo without loading models
./run.sh BV-001             # reopen a saved case in the reading room
scripts/bonaventure-toggle  # Linux: show/hide the pill; starts the app if needed
```

Run these commands from the repository root with `.venv` installed. The Linux
toggle script uses `readlink -f` and `setsid`; on macOS use the menu bar icon or
Option + Command + B instead.
Models load asynchronously; startup and inference time depend on the hardware.
For macOS startup without Terminal, use the installer described above. Linux
retains its original startup workflow; no login service is installed there.

Reproduce the three acceptance demo cases (docs/11) on the real models:

```bash
PYTHONPATH=. .venv/bin/python scripts/run_demo_cases.py
```

| Case | Input | Result |
|---|---|---|
| A · agreement | Kerley-B film + heart-failure history + breathlessness/orthopnoea | Cardiomegaly, pulmonary edema, pleural effusion **SUPPORTED · high**, localized; consolidation **CONFLICTING** (fever & cough denied) |
| B · contradiction | *Same film* + history with a recent normal report | Everything **CONFLICTING** — quotes "Normal heart size", "Lungs clear", "No pleural effusion" |
| C · poor image | Degraded film, no history | **INSUFFICIENT_EVIDENCE** — no forced conclusion |
| D · not on X-ray | Normal film + post-op knee replacement + sudden pleuritic pain, racing heart, calf swelling | No image finding; **"Pulmonary embolism — not assessable on a chest X-ray"** with Wells/D-dimer/CTPA advice |
| N · normal ×2 | Two normal films | No findings |

A case takes ~18–20 s on an RTX 3050 (MedGemma dominates). GPU: MedGemma (4-bit) + MedSAM, peak ≈ 5.1 GB;
CLEAR, its concept bank and CheXzero run on the CPU (~1.3 s). `run.sh` keeps WebKit's renderer on the Intel/Mesa GPU
(`__EGL_VENDOR_LIBRARY_FILENAMES`, `WEBKIT_DISABLE_DMABUF_RENDERER`) — rendering through NVIDIA's EGL under VRAM pressure crashed it.

Self-checks: `python -m bonaventure.context`, `python -m bonaventure.reconcile`.

## Repository

```
bonaventure/
  app.py          platform dispatcher; selects the desktop before importing it
  linux_app.py    original Linux desktop, Hyprland integration, toggle socket
  macos_app.py    macOS notch desktop and reading room windows
  macos_*.py      AppKit panel, menu bar/hover controls, Carbon global hotkey
  pipeline.py     case orchestration, progress states, failure capture
  imaging.py      scan loading (PNG/JPEG/DICOM), quality gate, model engine (+ mock)
  models.py       CLEAR (+ concept bank), CheXzero, MedGemma, MedSAM adapters
  context.py      history + presentation parsing (negation, dates, durations, provenance)
  knowledge.py    clinical vocabulary and finding ↔ evidence map
  reconcile.py    evidence reconciliation engine
  report.py       PDF evidence report
  ui/             island_linux.html (original), island.html (macOS), shared reading room/styles/fonts
scripts/          setup checker, macOS background installer, demo cases, toggle script
sample_data/      CC0 demo films, synthetic histories
docs/             PRD, SRS, architecture, pipeline, UX, report spec, model register …
```

## Original contribution vs. external components

Original: the workflow, the evidence-reconciliation engine and its rules, history/symptom parsing with provenance,
uncertainty and contradiction handling, the island + reading-room product experience, and the evidence report.
External (declared in `docs/13_MODEL_RESOURCE_REGISTER.md`): CLEAR + concept bank, CheXzero, MedGemma 1.5, MedSAM, DINOv2 code, open-source libraries, CC0 demo films.

## Limitations

- Chest X-ray only. 16 catalogue findings; other abnormalities appear only as unverified single-reader observations.
- Calibration uses 202 validation films; pneumothorax has only 7 positives there, so its levels stay hand-set.
- MedGemma boxes are approximate (laterality can be wrong); shown as approximate localization.
- History parsing is rule-based (no OCR for scanned PDFs).

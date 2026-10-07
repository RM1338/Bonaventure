# Bonaventure — Clinical Evidence Intelligence

> **Current macOS setup:** use the [macOS submission guide (Homebrew + pip)](#macos-submission-guide-current-pip-based) below. It includes model downloads, a sample workflow and evaluation steps.

A clinician-facing chest X-ray **evidence reconciliation** assistant (HackNex 2026 · HNX26PSI05).
It reads a chest X-ray, the patient's history documents and the current presentation, and for every candidate
finding decides whether the evidence **SUPPORTS** it, **CONFLICTS**, is **UNCERTAIN**, or is **INSUFFICIENT** —
showing exactly where on the film, which history fact (document + page + quote) and which symptom drove that call.

> Decision support only. Not a diagnosis. Every output must be reviewed by a qualified clinician.

## What it looks like

- **Island launcher** — a floating pill on Linux and a notch extension on macOS.
  Drop the X-ray, the history PDFs, type the presentation, *Analyse*. Progress is shown inside the island.
- **Reading room** — the result opens in a dark reading room: the film on a wall viewbox with grease-pencil marks traced
  along MedSAM's outline, a patient-context panel (complaint, symptoms, dated history with sources) and an evidence panel
  with each finding's state, an evidence triangle (image · history · presentation), what each of the four models said,
  CLEAR's matching concepts and the impression.
- **Evidence report** — a printable PDF with the annotated film, per-finding evidence, sources and limitations.

## Desktop platforms

`./run.sh` selects the platform before importing its GUI shell. Linux uses
`bonaventure/linux_app.py` and `bonaventure/ui/island.html`; macOS uses
`bonaventure/macos_app.py` and `bonaventure/ui/island_macos.html`. Both use
`desktop.Api` for application logic, including your inputs, dictation, and the
reading room. Mac-specific controls and picker changes do not affect the Linux UI.

On Linux, configure `scripts/bonaventure-toggle` as a key binding or bar action
(for example Super + Alt + B). It is not an automatically registered shortcut.
On macOS, use **Option + Command + B**, the menu bar icon, or hover below the notch
for 0.2 seconds. Hover-only opening closes after you move away; clicking or typing
keeps the launcher open. Escape closes intake. File pickers open in front of the
launcher, pause its hover/shortcut behavior, and restore focus after selection
or cancellation. Closing animates the HTML shell without shrinking the native
window; the invisible idle area passes clicks through to the desktop.
The macOS progress view uses a charcoal card with a current-stage explanation
and a segmented track grouped into patient context, image findings, and evidence
review. The camera cap remains black.

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

```bash
sudo pacman -S --needed webkit2gtk-4.1 python-gobject poppler      # system deps
uv venv --python /usr/bin/python3 --system-site-packages .venv      # system site-packages for GTK bindings
uv pip install --python .venv/bin/python torch torchvision --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv/bin/python -r requirements.txt

# model code + weights (see docs/13_MODEL_RESOURCE_REGISTER.md)
git clone https://github.com/peterhan91/CLEAR
git clone https://github.com/rajpurkarlab/CheXzero      # weights → CheXzero/checkpoints/chexzero_weights/
git clone https://github.com/bowang-lab/MedSAM          # medsam_vit_b.pth → MedSAM/work_dir/MedSAM/
hf download peterhan91/CLEAR best_model.pt concept_embeddings_368294.pt mimic_concepts.csv --local-dir ~/bonaventure/models/clear
hf download google/medgemma-1.5-4b-it                   # gated: accept the licence + `hf auth login` first
```

`BV_MEDGEMMA=/path/to/medgemma` points at a local copy; `BV_MOCK=1` runs the UI without models (clearly labelled demo mode).

## Install and run on macOS

From the checkout, using a working Homebrew Python rather than Apple's Xcode shim:

```bash
brew install pango poppler ffmpeg
python3 -m venv .venv                       # if the project venv is not already installed
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/check_setup.py
BV_MOCK=1 BV_START=expand ./run.sh           # UI demo without imaging models
```

Use the venv for pip instead of system-wide `pip3 install`. If you already have a
working `.venv`, keep it and install the current requirements there. If its Python
points at an unavailable Xcode installation, recreate it with your Homebrew Python
or `uv venv --python 3.12 --clear .venv` before installing dependencies.

The model resolver supports both layouts: repository-local `models/CLEAR/code`,
`models/CLEAR` (weights/concepts), `models/CheXzero`, `models/MedSAM`, and
`models/MedGemma`; or the existing Linux home-directory/top-level layout above.
Put new assets under `models/`, not `models/Models/`. `BV_MODELS_DIR` overrides
that root, and individual `BV_CLEAR_DIR`, `BV_CLEAR_CODE`, `BV_CLEAR_CKPT`,
`BV_CHEXZERO_DIR`, `BV_CHEXZERO_CKPT`, `BV_MEDSAM_DIR`, `BV_MEDSAM_CKPT`, and
`BV_MEDGEMMA` overrides are supported. Run `scripts/patch_clear_loader.py` using
`.venv/bin/python` after a fresh CLEAR clone. Once setup passes, quit the demo and
run `BV_START=expand ./run.sh` for real inference. Apple MPS is not enabled;
inference uses CPU on Macs and needs more RAM/time than the tested CUDA setup.

### Start without Terminal and at login

Quit any running Bonaventure instance from its menu bar menu, then run once:

```bash
.venv/bin/python scripts/install_macos.py
```

This creates `~/Applications/Bonaventure.app`, installs a login LaunchAgent, and
starts the app. Open it from Finder or Spotlight after manually quitting it.
The wrapper uses this checkout and its `.venv`, so keep both in place. It includes
Homebrew's executable paths for `ffmpeg` and microphone usage information.
Allow microphone access when macOS prompts; if access was denied, check System
Settings → Privacy & Security → Microphone. Actual microphone access must be
verified on your Mac; the plist declaration alone does not grant permission.

```bash
.venv/bin/python scripts/install_macos.py --no-login   # app wrapper without login startup
.venv/bin/python scripts/install_macos.py --uninstall  # remove wrapper and login agent
```

Quit the current app before reinstalling. Logs are at
`~/Library/Logs/Bonaventure/bonaventure.log`. The installer is macOS-only.

## Voice dictation (optional, offline English)

The source uses the standard Hugging Face Transformers Whisper checkpoints:

| Purpose | Download | Default folder |
|---|---|---|
| Live captions while speaking | `openai/whisper-base.en` | `models/whisper-base.en` |
| Final transcript when you stop | `openai/whisper-small.en` | `models/whisper-small.en` |

Use **small.en**, not a distilled checkpoint. The decoder primes both models
with medical vocabulary; the old `distil-small.en` comment was stale.
From the repository root, download only the processor/configuration files and
safetensors weights to avoid duplicate PyTorch/TensorFlow/Flax weight downloads:

```bash
.venv/bin/hf download openai/whisper-base.en --include '*.json' --include '*.txt' --include '*.safetensors' --local-dir models/whisper-base.en
.venv/bin/hf download openai/whisper-small.en --include '*.json' --include '*.txt' --include '*.safetensors' --local-dir models/whisper-small.en
.venv/bin/python scripts/check_setup.py --mock --voice
```

The `--mock --voice` check validates the UI dependencies, both voice models, and
the recorder without checking/loading the imaging weights. Existing copies at
`~/bonaventure/models/whisper-base.en` and `~/bonaventure/models/whisper-small.en`
are also found; `BV_WHISPER_LIVE` and `BV_WHISPER` override each location.
Models run on CPU. With only one installed, it handles both live and final
transcription, but install both for the intended speed/accuracy balance.

macOS records through `ffmpeg`/AVFoundation (`brew install ffmpeg`); Linux uses
PipeWire's `pw-record`. Restart the app after downloading models, click the
presentation microphone, speak, and click it again for the final transcript.
While final transcription runs, the microphone is off and the button is busy;
extra clicks cannot start another recording. A click during startup queues a stop.
Both launchers and the reading room use the same dictation handler.
The latest recording is kept locally at `models/last_dictation.wav` (or under
`BV_MODELS_DIR`) for debugging; the model directory is ignored by Git.

The setup checker confirms packages and files, not GUI rendering, microphone
permission, valid checkpoint contents, or successful inference. Native Mac
picker/collapse/login behavior still needs runtime verification. The original
Linux runtime was tested on Arch/Omarchy with Hyprland; other distros need their
own native dependency setup and runtime checks.

## Run

```bash
./run.sh                    # Linux pill or macOS notch launcher
BV_START=expand ./run.sh    # open intake immediately
./run.sh BV-001             # reopen a saved case in the reading room
scripts/bonaventure-toggle  # Linux only: toggle/start the pill using a key or bar binding
```

The macOS progress panel has an up-chevron Hide launcher button and supports Escape to hide it without
canceling analysis. Reopening preserves case progress. When ready, Open review
reopens the reading room directly. Automatic hover dismissal still stays
disabled during analysis.

Export report saves the PDF and opens it in the default document viewer (macOS
`open`, Linux `xdg-open`). If opening fails, the report remains saved and the UI
shows a warning with its path. Linux needs `xdg-utils` and a configured PDF viewer.

“How the models read it” shows saved MedGemma image responses separately from
clinical rewrites. Cases created with empty responses display an explicit missing
output message; rerun analysis to obtain new output. Empty MedGemma image
responses now fail inference instead of silently appearing as successful reasoning.

### Diagnose slow stages and model inference

Stage 3 is **Structuring current presentation**. Known clinical phrases use the
built-in parser; MedGemma rewrites unmatched phrases only. Rewrites have a
30-second generation budget and a two-second model-lock wait. Failure preserves
the original wording, lists unmatched phrases, and adds a review warning. Long
phrases (over 500 characters) and phrases beyond the first 12 eligible unmatched
phrases remain available for review without a model rewrite.

MedGemma image calls use a generation budget of 180 seconds on CUDA, 600 seconds
on Apple MPS and 1800 seconds on CPU; exceeding it fails analysis rather than
accepting partial reasoning. These budgets are checked
between decoding steps, so a slow CPU step can exceed the limit. Override with
`BV_PRESENTATION_SECONDS` or `BV_IMAGE_GENERATION_SECONDS` when starting the app.
MedGemma automatically selects CUDA, then Apple MPS on supported Macs, then CPU.
MPS uses bfloat16 with eager attention when supported, otherwise float32;
float16 is avoided because Gemma can overflow and produce empty responses.
CUDA retains four-bit weights.
The startup log prints the actual device, dtype and image-generation budget.
Set `BV_MEDGEMMA_DEVICE=cpu` to force CPU, or `mps`/`cuda` to require that backend;
an unavailable explicit backend reports a loading error. MPS needs sufficient
unified memory for the unquantized 4B model plus the other models. MedSAM retains
its CUDA/CPU selection, and both image readers retain their configured device.
The RTX timing below is not an estimate for a Mac.

Terminal output reports stage starts and elapsed times. Each case writes
`cases/BV-XXX/progress.json`; successful results also include stage timings in
`technical.stage_seconds`. Failed real-model loading is reported as a failure;
mock output requires explicitly setting `BV_MOCK=1`. Timeout, loading and
memory failures have distinct error messages. Generic model failures do not
claim the image format or quality caused the error; full technical details
are saved in the case progress file and the exception is logged to Terminal.

Close Bonaventure first, then run the actual model smoke tests:

```bash
.venv/bin/python scripts/diagnose_models.py
```

This checks CLEAR, CheXzero, CLEAR concept retrieval, MedSAM, MedGemma text
(Stage 3) and image generation, both Whisper checkpoints, and optional MiniLM.
It checks shared input/output weights for the language models, finite outputs,
and inference completion. Whisper uses synthetic audio: this does not test
microphone permission or speech-recognition accuracy. No patient recording is
read. Missing optional MiniLM is reported as skipped.

Models run sequentially in separate processes to release RAM between checks.
The hard limit per process is 600 seconds including loading; use `--timeout 1200`
for a slower machine (`--timeout 2400` for CPU image checks) or `--only MedGemma-text` to isolate Stage 3. The report is
saved locally at `cases/model-health.json`; a failed/timed-out required check
returns a nonzero exit status. Hugging Face loads are offline and need complete
local checkpoints. CLEAR's DINOv2 source also needs its existing Torch Hub cache.
This smoke test verifies execution, not diagnostic accuracy or the full app's
combined memory usage.

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
See [Desktop verification](docs/DESKTOP_VERIFICATION.md) for the full automated
test commands, coverage, and remaining native GUI/inference checks.

## Repository

```
bonaventure/
  app.py          platform dispatcher
  desktop.py      shared application logic, reading room, dictation bridge, toggle socket
  linux_app.py    Linux/Hyprland shell
  macos_app.py    macOS shell; macos_*.py implement placement, picker, menu, hotkey
  dictation.py    offline Whisper live captions and final transcript
  pipeline.py     case orchestration, progress states, failure capture
  imaging.py      scan loading (PNG/JPEG/DICOM), quality gate, model engine (+ mock)
  models.py       CLEAR (+ concept bank), CheXzero, MedGemma, MedSAM adapters
  context.py      history + presentation parsing (negation, dates, durations, provenance)
  knowledge.py    clinical vocabulary and finding ↔ evidence map
  reconcile.py    evidence reconciliation engine
  report.py       PDF evidence report
  ui/             island.html (Linux), island_macos.html (Mac), shared review/styles/fonts
scripts/          setup checks, macOS installer, demo cases, sample histories, Linux toggle
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

## macOS submission guide (current, pip-based)

This section is the complete macOS setup and evaluation path. It supplements the
original Linux instructions and the earlier macOS notes above without replacing
them. For the current Mac build, use **pip in a virtual environment**; `uv` is not
required. Earlier statements that Apple MPS is disabled describe the older build:
MedGemma now selects MPS on supported Macs, with CPU fallback when MPS is absent.
The notch launcher uses a centered **up chevron to hide**, rather than quit, and
Escape can hide intake, progress, ready and error panels.

### 1. What the macOS solution delivers

Bonaventure collects a chest X-ray, optional patient history files and the current
presentation from a clinician. It compares image-model signals with dated history
and symptoms, then presents evidence states, approximate localization and source
references in a reading room. Export report saves a PDF and opens the default PDF
viewer. The clinician can review and record agreement or a challenge; the system
is decision support rather than an autonomous diagnosis.

| Component | Technology and purpose |
|---|---|
| macOS desktop | Python, pywebview/WKWebView, PyObjC/AppKit, HTML/CSS/JavaScript; notch placement, menu bar, native file panels and Option–Command–B |
| Image ingestion | Pillow, NumPy and pydicom for PNG/JPEG/DICOM loading and heuristic quality metrics |
| History ingestion | Poppler `pdftotext`/`pdfinfo` plus deterministic parsing of PDF/text/Markdown, dates, negation and source references |
| Primary image reader | CLEAR, using a DINOv2 image backbone and text encoder; its 368,294-concept bank supplies matching observations |
| Independent verifier | CheXzero, a separately trained CLIP chest X-ray reader |
| Visual reasoning | MedGemma 1.5 4B-it for image survey, candidate descriptions and boxes; optional rewriting of unmatched clinical phrases |
| Segmentation | MedSAM refines accepted boxes into outlines |
| Optional voice | Transformers Whisper `base.en` for live captions and `small.en` for final transcription; ffmpeg captures microphone audio |
| Evidence decisions | Original deterministic reconciliation rules and calibrated thresholds in `bonaventure/reconcile.py` and `bonaventure/calibration.json` |
| PDF output | WeasyPrint with native Pango libraries |

Python package versions are pinned in [requirements.txt](requirements.txt).
External model/dataset sources and licenses are declared in the
[resource register](docs/13_MODEL_RESOURCE_REGISTER.md). The Mac device handling
and optional Whisper setup below supplement that register's original CUDA notes.
No external inference API is required after the model assets are downloaded.

### 2. Prepare Homebrew Python and install with pip

Install [Homebrew](https://brew.sh/) first if it is not already available. An
Apple Silicon Mac is recommended for MPS acceleration; an Intel Mac uses CPU.
This is not a verified minimum-RAM specification: the unquantized 4B model alone
needs roughly 8 GB for bfloat16 weights or 16 GB for float32 weights, plus runtime
buffers, the image/concept models, the desktop and optional Whisper. Keep enough
free disk space for weights and download caches; setup downloads can be large.

```bash
brew install git python@3.12 pango poppler ffmpeg
```

The code used by this guide currently lives on a feature branch. While the macOS
changes are awaiting merge, clone the documentation branch, which includes that
implementation. After these changes reach `main`, a normal clone of `main` can
be used instead.

```bash
git clone --branch docs/macos-submission-guide https://github.com/RM1338/Bonaventure.git
cd Bonaventure

BONAVENTURE_PYTHON="$(brew --prefix python@3.12)/bin/python3.12"
"$BONAVENTURE_PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python --version
```

For an existing checkout, keep a working `.venv` and skip creating it. If it
points to an unavailable Xcode Python shim, rename that environment as a backup
before creating a new one with the explicit Homebrew Python above. Do not use
system-wide `pip3 install` or `--break-system-packages`; the virtual environment
avoids Homebrew's `externally-managed-environment` error. The macOS platform
requirements install PyObjC through pywebview. Do not use the Linux CUDA wheel
index on a Mac, and do not copy the Linux GTK/Hyprland setup commands.

### 3. Download source code and local model assets

Use `models/`, **not `models/Models/`**. The downloaded repositories/checkpoints
are ignored by Git; they must be installed on the evaluator's machine as well.
Run these clone commands once, skipping any repository already present:

```bash
mkdir -p models/CLEAR
git clone https://github.com/peterhan91/CLEAR.git models/CLEAR/code
git clone https://github.com/rajpurkarlab/CheXzero.git models/CheXzero
git clone https://github.com/bowang-lab/MedSAM.git models/MedSAM
mkdir -p models/CheXzero/checkpoints/chexzero_weights models/MedSAM/work_dir/MedSAM
.venv/bin/python scripts/patch_clear_loader.py
```

Download CLEAR and MedGemma with the Hugging Face CLI installed in `.venv`:

```bash
.venv/bin/hf download peterhan91/CLEAR best_model.pt concept_embeddings_368294.pt mimic_concepts.csv --local-dir models/CLEAR
.venv/bin/hf auth login
.venv/bin/hf download google/medgemma-1.5-4b-it --include '*.json' --include '*.txt' --include '*.model' --include '*.safetensors' --local-dir models/MedGemma
```

Before the MedGemma download, visit its
[model page](https://huggingface.co/google/medgemma-1.5-4b-it), accept the access
terms and use a Hugging Face account/token with permission. Run login locally;
never place the token in the README or repository. CLEAR and Whisper are public;
MedGemma access approval can take time, so do this before the evaluation.

Download the following two checkpoint files through the upstream release links
and place them at these **exact paths**:

| Model | Download source | Required destination |
|---|---|---|
| CheXzero | [Official checkpoint folder](https://drive.google.com/drive/folders/1makFLiEMbSleYltaRxw81aBhEDMpVwno?usp=sharing), linked in its [README](https://github.com/rajpurkarlab/CheXzero#readme) | `models/CheXzero/checkpoints/chexzero_weights/best_128_0.0002_original_15000_0.859.pt` |
| MedSAM | [Official checkpoint folder](https://drive.google.com/drive/folders/1ETWmi4AiniJeWOt6HAsYgTjYv_fkgzoN?usp=drive_link), linked in its [README](https://github.com/bowang-lab/MedSAM#readme) | `models/MedSAM/work_dir/MedSAM/medsam_vit_b.pth` |

The intended completed layout is:

```text
models/
  CLEAR/
    code/src/clear/hub.py
    best_model.pt
    concept_embeddings_368294.pt
    mimic_concepts.csv
  CheXzero/
    model.py
    clip.py
    bpe_simple_vocab_16e6.txt.gz
    checkpoints/chexzero_weights/best_128_0.0002_original_15000_0.859.pt
  MedSAM/
    segment_anything/
    work_dir/MedSAM/medsam_vit_b.pth
  MedGemma/
    config.json
    preprocessor_config.json
    tokenizer.json
    model.safetensors.index.json
    model-00001-of-00002.safetensors
    model-00002-of-00002.safetensors
```

CLEAR also needs DINOv2 source in the Torch Hub cache. While online, populate it
without downloading separate DINOv2 weights:

```bash
.venv/bin/python -c 'import torch; torch.hub.load("facebookresearch/dinov2:main", "dinov2_vitb14_reg", pretrained=False, trust_repo=True, skip_validation=True)'
.venv/bin/python scripts/check_setup.py
```

`run.sh` sets Hugging Face/Transformers offline mode. Download complete weights
and processor/tokenizer files before launching; a file-presence check alone does
not verify inference. A fresh Torch Hub cache can still require a GitHub source
download, so prepare the DINOv2 cache before an offline demonstration.

### 4. Optional microphone dictation on macOS

Whisper is optional; typed presentation text works without it. The app does not
require WhisperFlow or any separate voice service.

```bash
.venv/bin/hf download openai/whisper-base.en --include '*.json' --include '*.txt' --include '*.safetensors' --local-dir models/whisper-base.en
.venv/bin/hf download openai/whisper-small.en --include '*.json' --include '*.txt' --include '*.safetensors' --local-dir models/whisper-small.en
.venv/bin/python scripts/check_setup.py --mock --voice
```

Repeat `--include` for each pattern; passing several patterns after a single
`--include` can be interpreted as explicit filenames and omit needed JSON files.
Allow microphone access when prompted. If denied, check System Settings →
Privacy & Security → Microphone. The button starts recording; clicking again
stops microphone capture before final decoding. “Finishing transcript” means
Whisper is processing the captured audio, not continuing to listen. Models run
on CPU, and the latest recording is stored locally at `models/last_dictation.wav`.

### 5. Configure, launch and validate on the Mac

```bash
.venv/bin/python -m bonaventure.model_paths
BV_START=expand ./run.sh
```

Use Option–Command–B, the menu bar action or hovering below the notch to open the
launcher. Select a scan and optional history files, type or dictate the current
presentation, and choose Analyse. The up-chevron or Escape hides the panel;
analysis continues. Reopen it to see progress, or choose Open review when ready.
Quit from the menu bar when you want to stop the application entirely.

| Optional environment variable | Meaning |
|---|---|
| `BV_MODELS_DIR` | Custom model root; normally the checkout's `models/` |
| `BV_MEDGEMMA` | Custom local MedGemma folder |
| `BV_MEDGEMMA_DEVICE` | `auto` (default), `mps`, `cpu` or `cuda`; explicitly requesting an unavailable backend fails loading |
| `BV_IMAGE_GENERATION_SECONDS` | Per-image-generation budget; defaults to 600 on MPS and 1800 on CPU (180 on CUDA) |
| `BV_PRESENTATION_SECONDS` | Optional clinical-rewrite budget, default 30 seconds |
| `BV_WHISPER_LIVE` / `BV_WHISPER` | Local live/final Whisper folders |
| `BV_MOCK=1` | Explicit UI demo mode; synthetic model output is not real inference |

MPS uses bfloat16 where supported and float32 otherwise, with eager attention.
Check the startup line `[models] MedGemma device=...` for the actual backend,
dtype and budget. CPU is available when MPS is absent; it can be substantially
slower. Budgets are per generation call, not for the entire case, and are checked
between decoding steps. MedSAM and the image readers retain their existing
CUDA/CPU device selection. Native Mac timing and memory usage are not guaranteed
by the earlier RTX 3050 measurements.

For a background/Finder launch and login startup, quit the existing instance,
then install the macOS wrapper once:

```bash
.venv/bin/python scripts/install_macos.py
open "$HOME/Applications/Bonaventure.app"
```

The installer already starts the app; the `open` command is also how to launch
it later from Terminal. Finder/Spotlight can open the same application. Keep this
checkout and `.venv` in place; the wrapper points to them. `--no-login` disables
login installation, and `--uninstall` removes the app wrapper/login agent.
Background logs are at `~/Library/Logs/Bonaventure/bonaventure.log`.

To validate real models independently, quit the app before running:

```bash
.venv/bin/python scripts/diagnose_models.py --timeout 2400
```

This releases each model's RAM before testing the next one and writes
`cases/model-health.json`. It exercises image readers, concept retrieval,
segmentation, MedGemma text/image generation and both Whisper decoders. MiniLM
is optional and may be skipped. Whisper uses synthetic audio, so separately test
real microphone capture/recognition. Sequential checks do not establish the
full application's combined memory requirements or clinical accuracy. Install
the optional Whisper assets before expecting both voice checks to pass.

| macOS symptom | Action |
|---|---|
| Python requests Xcode, or pip says “externally managed” | Use the explicit Homebrew Python and `.venv/bin/python -m pip` from step 2 |
| WeasyPrint cannot locate native Pango libraries | Confirm `brew install pango`; for a Terminal run, set `export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib"` before launching |
| Hugging Face reports gated access or missing local configuration | Accept MedGemma terms, log in with the authorized account, complete step 3 before offline launch |
| Shortcut already in use | Use the menu bar action and inspect the shortcut registration message; resolve a conflicting application shortcut |
| No microphone input | Check macOS permission and `ffmpeg`; try typed text to isolate voice from imaging |
| Image inference times out or runs out of memory | Inspect saved technical details; close competing apps and run the isolated model diagnostic; CPU can require much longer than MPS |
| Historical report has no MedGemma image text | Run a new analysis; empty saved model responses cannot be reconstructed |

### 6. Data pipeline and evidence to show evaluators

The input is collected through native file selection/drop and a text/microphone
field. History is optional; its absence is shown rather than filled in by a
model. A case directory is created locally and then follows these seven stages:

| Stage | Input → processing → output | Relevant source |
|---|---|---|
| 1. Read scan | PNG/JPEG/DICOM → grayscale image, metadata and quality metrics | [imaging.py](bonaventure/imaging.py) |
| 2. Extract timeline | History files → PDF text, dated concepts, negation, document/page/quote; identity mismatch excludes conflicting histories | [context.py](bonaventure/context.py) |
| 3. Structure presentation | Clinician wording → present/denied concepts and durations; optional bounded rewrites/meaning matching retain original phrases and warnings | [presentation.py](bonaventure/presentation.py), [pipeline.py](bonaventure/pipeline.py) |
| 4. Evaluate image | CLEAR/CheXzero scores and reliability thresholds → candidates; concept retrieval and MedGemma survey/descriptions provide intermediate evidence | [models.py](bonaventure/models.py), [calibration.json](bonaventure/calibration.json) |
| 5. Localize | MedGemma boxes → anatomical checks → optional MedSAM outlines; localization is computed during image analysis | [models.py](bonaventure/models.py) |
| 6. Reconcile | Image agreement, quality, history and symptoms → four evidence states, contradictions, limitations and reasons | [reconcile.py](bonaventure/reconcile.py) |
| 7. Prepare review | Structured evidence and annotated preview → reading room, saved JSON and optional PDF export | [pipeline.py](bonaventure/pipeline.py), [report.py](bonaventure/report.py) |

The central contribution is **evidence reconciliation**, not training a new
foundation model. Reliable reader votes and calibrated thresholds establish
image evidence; original rules combine it with supporting/contradicting history,
symptoms and quality. MedGemma supplies descriptions/localization, not a free-form
final diagnosis. Single-reader/open-vocabulary observations remain separately
identified rather than becoming established diagnoses.

Show the evaluator the following evidence in the reading room or saved files:

- **Sources:** history filename, page, direct quote, date and patient-identity checks.
- **Strength:** high/moderate/low evidence states and the reasons for agreement or
  conflict. These are not patient-level diagnostic probabilities. Reader scores,
  thresholds and calibration AUROC can be inspected separately.
- **Intermediate output:** CLEAR concepts, MedGemma image text and clinical rewrites
  under “How the models read it”; missing historical image output is explicit.
- **Time and processing:** case creation timestamp, model/stage timings and failure
  details. `cases/BV-XXX/progress.json` persists stage state; `result.json` stores
  the evidence and `scan.png` the review preview.
- **Doctor review:** recorded agreement/challenges remain next to automated evidence.
  Export report creates `reports/BV-XXX.pdf` and opens the default viewer.

`cases/`, `reports/`, model downloads and recordings are local/ignored outputs;
they are not automatically part of the public submission. Use the bundled
fictional histories and attributed demo films for evaluation evidence.

### 7. Representative input/output and live demonstration on macOS

Use the bundled Case A from [run_demo_cases.py](scripts/run_demo_cases.py):

| Input | Value |
|---|---|
| Chest X-ray | [sample_data/scans/kerley_b.jpg](sample_data/scans/kerley_b.jpg) |
| History | [sample_data/histories/case_a_history.pdf](sample_data/histories/case_a_history.pdf) — synthetic heart-failure history |
| Current presentation | `Worsening shortness of breath for 3 days, can't lie flat, waking up breathless at night, ankle swelling. No fever, no cough.` |

Start the real app with `BV_START=expand ./run.sh`, choose those two files and
paste the presentation. Click Analyse, inspect the annotated film, click a
finding to see its evidence, open “How the models read it”, then Export report.
The PDF should open in the default viewer. The case ID is allocated dynamically;
use the ID shown on your machine when reopening it, for example `./run.sh BV-005`.

The existing reference demonstration reports supported cardiomegaly, pulmonary
edema and pleural effusion, with consolidation conflicting with the context.
For a concrete source example, the synthetic history's page 3 is dated
12 Aug 2026 and states: **“The cardiac silhouette is enlarged.”** The reading room
links this kind of quote to the corresponding finding. Exact model scores,
boxes and text must be taken from the actual run; the reference outcomes above
are not a promise that every hardware/checkpoint combination returns identical
outputs. Do not invent confidence values or label a mock run as a real-model demo.

For a contrasting run, keep the same film but use
[case_b_history.pdf](sample_data/histories/case_b_history.pdf) and the presentation
`Breathless for 2 days. Denies fever, cough and ankle swelling.` Its page 2 says
**“Normal heart size. Lungs clear. No pleural effusion. No pneumothorax.”**
The reference demonstration exposes contradictions instead of treating image
signals as sufficient on their own. The degraded film demonstrates insufficient
evidence; the post-operative Case D demonstrates that suspected pulmonary
embolism is not assessable on a chest X-ray.

For the full reference suite, quit the desktop app first and run:

```bash
PYTHONPATH=. .venv/bin/python scripts/run_demo_cases.py
```

Despite its historical “three cases” label, this script runs seven built-in
cases: A, B, C, D, E (identity mismatch), N and N2 (normal films). This is slower
than a single live demonstration on a Mac. It prints the case IDs, states,
quality, timings and evidence summaries; reopen the generated cases with
`./run.sh BV-XXX`. Individual cases can be demonstrated manually as above.

Suggested live evaluation sequence:

1. Prepare model downloads, the DINOv2 cache and permissions before the session;
   run the setup and inference checks, then launch the actual Mac build.
2. Show Case A end-to-end, a source quote, model evidence and the PDF export.
3. Show Case B or the degraded film to explain why the system exposes conflict
   or insufficient evidence rather than forcing a diagnosis.
4. Explain the original reconciliation logic, pretrained components, evidence
   strength and localization limitations using the source links above.
5. If a recorded demonstration is permitted, record this workflow using the
   bundled samples and include the recording link in the submission. A recording
   has not been added by this documentation change.

### 8. Scope and submission checklist

| Scope | Implemented behavior or boundary |
|---|---|
| Minimum viable solution | Local chest X-ray + history + current presentation; quality checks; image readers; explicit reconciliation; evidence/source inspection; approximate localization; reading room and PDF export |
| Additional desktop features | Mac notch/menu bar/shortcut/hover controls, native foreground picker, hidden background analysis, Finder/login wrapper and optional offline English dictation |
| Not included | Autonomous diagnosis, clinical deployment validation, OCR for scanned history PDFs, general imaging modalities, or guaranteed timing/accuracy across machines |
| Verification boundary | Automated regression checks cover mocked native APIs and UI state. Report generation has been exercised on the user's Mac; the latest precision/viewer changes still need native confirmation. Do not equate setup checks or mocked tests with validated clinical performance |

Optional developer regression checks use Node as well as Python:

```bash
brew install node
.venv/bin/python -m unittest discover -s tests -q
node tests/island_state.test.cjs
node tests/dictation_state.test.cjs
node tests/review_outputs.test.cjs
.venv/bin/python -m bonaventure.context
.venv/bin/python -m bonaventure.reconcile
```

| Submission requirement | Where/how to demonstrate it |
|---|---|
| Working system | Live Mac Case A workflow and opening the generated PDF; real models rather than `BV_MOCK=1` |
| Complete source + README | This repository, pinned requirements, source links, model acquisition and macOS setup steps above |
| Data pipeline | Seven-stage table, progress file and case result |
| Core model/reasoning | Pretrained model roles plus original reconciliation rules/calibration |
| Evidence/explanation | Source quotes/pages/dates, calibrated reader scores, evidence states, model outputs, timestamps and intermediate artifacts |
| Sample input/output | Bundled Case A/B inputs, reference behavior and generated review/JSON/PDF from the demonstrated run |
| Scope note | Minimum solution, desktop additions and exclusions in the scope table |
| Live demonstration | Sequence above; use a recording only where the evaluator permits it |
| Public repository | Submit `https://github.com/RM1338/Bonaventure` after the owner makes the repository public and the submission branch is merged or explicitly identified |

**Visibility action before submission:** the repository was private when this
README addition was prepared. An owner must set GitHub Settings → General →
Danger Zone → Change repository visibility → Public, then verify the URL opens
while signed out. This README-only branch does not change repository settings.
Make sure the submitted branch contains the macOS implementation and this guide;
submit the public repository link before the end of evaluation. Native samples
and model downloads remain separately identified resources rather than code
silently bundled into the public repository.

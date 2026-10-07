# macOS setup and evaluation

Adapted from Gavriel’s [PR #7](https://github.com/RM1338/Bonaventure/pull/7), with
current macOS branch setup paths and verified reference/reproduction details. Run commands
from the repository root. Native Mac runtime verification remains separate.

This guide provides the macOS setup and evaluation path alongside the
[branch README](../README.md), which contains the original Omarchy setup, current
model evidence, diagrams and reproduction commands. For the current Mac build, use **pip in a virtual environment**; `uv` is not
required. MedGemma selects MPS on supported Macs, with CPU fallback when MPS is absent.
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

Python package versions are pinned in [requirements.txt](../requirements.txt).
External model/dataset sources and licenses are declared in the
[resource register](13_MODEL_RESOURCE_REGISTER.md). The Mac device handling
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

Use the `macos` branch for this implementation. `main` is the Omarchy/Linux
release. Clone `macos` explicitly; for an existing checkout, quit the app and
run `git switch macos` before installing or starting the Mac build.

```bash
mkdir -p "$HOME/Developer"
cd "$HOME/Developer"
git clone --branch macos https://github.com/RM1338/Bonaventure.git
cd Bonaventure

BONAVENTURE_PYTHON="$(brew --prefix python@3.12)/bin/python3.12"
"$BONAVENTURE_PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-macos.txt
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

For background/login startup, keep the checkout outside macOS privacy-protected
Documents, Desktop, Downloads and iCloud Documents folders. Prefer
`~/Developer/Bonaventure`. LaunchAgents can receive “Operation not permitted”
for those folders even when Terminal can launch the application. Move the whole
checkout, including models and the environment, before reinstalling. Using the
explicit `.venv/bin/python` can continue to work after relocation, but activation
scripts and pip/Hugging Face command shebangs can retain the old path; recreate
an environment at the new location if those commands fail. Model files do not
need to be downloaded again.

For a background/Finder launch and login startup, quit the existing instance,
then install the macOS wrapper once:

```bash
.venv/bin/python scripts/install_macos.py
open "$HOME/Applications/Bonaventure.app"
```

The installer waits for launcher readiness and reveals the panel. If startup
fails, it prints recent logs instead of reporting successful startup.
The installer already starts the app; the `open` command is also how to launch
it later from Terminal. Finder/Spotlight can open the same application. Keep this
checkout and `.venv` in place; the wrapper points to them. `--no-login` disables
login installation, and `--uninstall` removes the app wrapper/login agent.
Background logs are at `~/Library/Logs/Bonaventure/bonaventure.log`.
Terminal, Finder and login startup all use `run.sh`, which sets Homebrew library
paths, offline model flags and unbuffered logs. After pulling this update, quit
the old instance and rerun the installer to replace the old wrapper. You can
check native imports without opening a window with `./run.sh --check-runtime`.
The macOS branch rejects Linux/Windows launches; switch to the platform's branch
rather than trying to install its native GUI dependencies here.

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
| 1. Read scan | PNG/JPEG/DICOM → grayscale image, metadata and quality metrics | [imaging.py](../bonaventure/imaging.py) |
| 2. Extract timeline | History files → PDF text, dated concepts, negation, document/page/quote; identity mismatch excludes conflicting histories | [context.py](../bonaventure/context.py) |
| 3. Structure presentation | Clinician wording → present/denied concepts and durations; optional bounded rewrites/meaning matching retain original phrases and warnings | [presentation.py](../bonaventure/presentation.py), [pipeline.py](../bonaventure/pipeline.py) |
| 4. Evaluate image | CLEAR/CheXzero scores and reliability thresholds → candidates; concept retrieval and MedGemma survey/descriptions provide intermediate evidence | [models.py](../bonaventure/models.py), [calibration.json](../bonaventure/calibration.json) |
| 5. Localize | MedGemma boxes → anatomical checks → optional MedSAM outlines; localization is computed during image analysis | [models.py](../bonaventure/models.py) |
| 6. Reconcile | Image agreement, quality, history and symptoms → four evidence states, contradictions, limitations and reasons | [reconcile.py](../bonaventure/reconcile.py) |
| 7. Prepare review | Structured evidence and annotated preview → reading room, saved JSON and optional PDF export | [pipeline.py](../bonaventure/pipeline.py), [report.py](../bonaventure/report.py) |

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

Use the bundled Case A from [run_demo_cases.py](../scripts/run_demo_cases.py):

| Input | Value |
|---|---|
| Chest X-ray | [sample_data/scans/kerley_b.jpg](../sample_data/scans/kerley_b.jpg) |
| History | [sample_data/histories/case_a_history.pdf](../sample_data/histories/case_a_history.pdf) — synthetic heart-failure history |
| Current presentation | `Worsening shortness of breath for 3 days, can't lie flat, waking up breathless at night, ankle swelling. No fever, no cough.` |

Start the real app with `BV_START=expand ./run.sh`, choose those two files and
paste the presentation. Click Analyse, inspect the annotated film, click a
finding to see its evidence, open “How the models read it”, then Export report.
The PDF should open in the default viewer. The case ID is allocated dynamically;
use the ID shown on your machine when reopening it, for example `./run.sh BV-005`.

The committed Case A reference reports supported cardiomegaly and pulmonary
edema, with consolidation conflicting with the context. It does not include a
pleural-effusion finding. Image confidence in that saved reference is 90%, 88%
and 31%, respectively; evidence strength is a separate rule-based summary.
For a concrete source example, the synthetic history's page 3 is dated
12 Aug 2026 and states: **“The cardiac silhouette is enlarged.”** The reading room
links this kind of quote to the corresponding finding. Exact model scores,
boxes and text must be taken from the actual run; the reference outcomes above
are not a promise that every hardware/checkpoint combination returns identical
outputs. Do not invent confidence values or label a mock run as a real-model demo.

For a contrasting run, keep the same film but use
[case_b_history.pdf](../sample_data/histories/case_b_history.pdf) and the presentation
`Breathless for 2 days. Denies fever, cough and ankle swelling.` Its page 2 says
**“Normal heart size. Lungs clear. No pleural effusion. No pneumothorax.”**
The reference demonstration exposes contradictions instead of treating image
signals as sufficient on their own. The degraded film demonstrates insufficient
evidence; the post-operative Case D demonstrates that suspected pulmonary
embolism is not assessable on a chest X-ray.

For the full reference suite, quit the desktop app first and run:

```bash
.venv/bin/python scripts/reproduce.py --suite acceptance --pdf
```

The acceptance suite runs seven built-in cases: A, B, C, D, E (identity mismatch), N and N2 (normal films). This is slower
than a single live demonstration on a Mac. It writes a fresh run manifest, JSON/progress and PDF output under
`cases/demo-runs/` and prints case IDs and finding summaries; reopen cases with
`./run.sh BV-XXX`. To run only the contrasting pair, use `--case A --case B`. For the 14-case
library, use `--suite library`; the README lists the cardiomegaly/GIF example
and full suite commands. Original reference outputs are preserved.

Suggested live evaluation sequence:

1. Prepare model downloads, the DINOv2 cache and permissions before the session;
   run the setup and inference checks, then launch the actual Mac build.
2. Show Case A end-to-end, a source quote, model evidence and the PDF export.
3. Show Case B or the degraded film to explain why the system exposes conflict
   or insufficient evidence rather than forcing a diagnosis.
4. Explain the original reconciliation logic, pretrained components, evidence
   strength and localization limitations using the source links above.
5. If a recorded demonstration is permitted, record this workflow using the
   bundled samples and include the recording link in the submission. The main
   README already contains Linux demonstration GIFs; verify the actual
   Mac workflow separately.

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
| Public repository | Submit `https://github.com/RM1338/Bonaventure` after the owner makes the repository public; the Mac implementation and this guide are on `macos` |

**Submission branch and visibility:** the repository is currently public. Before
evaluation, confirm its URL opens while signed out and explicitly identify
`macos` as the Mac submission branch. `main` is the Omarchy/Linux release;
it does not contain this Mac launcher. This change does not alter GitHub settings.
Submit the repository link plus the selected branch before the end of evaluation.
Native samples and model downloads remain separately identified resources rather
than code silently bundled into the public repository.

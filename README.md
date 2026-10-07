# Bonaventure — Clinical Evidence Intelligence

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

### Diagnose slow stages and model inference

Stage 3 is **Structuring current presentation**. Known clinical phrases use the
built-in parser; MedGemma rewrites unmatched phrases only. Rewrites have a
30-second generation budget and a two-second model-lock wait. Failure preserves
the original wording, lists unmatched phrases, and adds a review warning. Long
phrases (over 500 characters) and phrases beyond the first 12 eligible unmatched
phrases remain available for review without a model rewrite.

MedGemma image calls have a 180-second generation budget; exceeding it fails
analysis rather than accepting partial reasoning. These budgets are checked
between decoding steps, so a slow CPU step can exceed the limit. Override with
`BV_PRESENTATION_SECONDS` or `BV_IMAGE_GENERATION_SECONDS` when starting the app.
Currently MedGemma and MedSAM use CUDA when available and CPU otherwise,
including on Macs; Apple MPS acceleration is not configured. The RTX timing
below is not an estimate for a Mac.

Terminal output reports stage starts and elapsed times. Each case writes
`cases/BV-XXX/progress.json`; successful results also include stage timings in
`technical.stage_seconds`. Failed real-model loading is reported as a failure;
mock output requires explicitly setting `BV_MOCK=1`.

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
for a slower machine or `--only MedGemma-text` to isolate Stage 3. The report is
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

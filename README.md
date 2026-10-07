# Bonaventure — Clinical Evidence Intelligence

A clinician-facing chest X-ray **evidence reconciliation** assistant (HackNex 2026 · HNX26PSI05).
It reads a chest X-ray, the patient's history documents and the current presentation, and for every candidate
finding decides whether the evidence **SUPPORTS** it, **CONFLICTS**, is **UNCERTAIN**, or is **INSUFFICIENT** —
showing exactly where on the film, which history fact (document + page + quote) and which symptom drove that call.

> Decision support only. Not a diagnosis. Every output must be reviewed by a qualified clinician.

## What it looks like

- **Island launcher** — a centered floating input panel on Windows (`Ctrl + Alt + B` to show/hide).
  Drop the X-ray, the history PDFs, type the presentation, *Analyse*. Progress is shown inside the island.
- **Reading room** — the result opens in a dark reading room: the film on a wall viewbox with grease-pencil marks traced
  along MedSAM's outline, a patient-context panel (complaint, symptoms, dated history with sources) and an evidence panel
  with each finding's state, an evidence triangle (image · history · presentation), what each of the four models said,
  CLEAR's matching concepts and the impression.
- **Evidence report** — a printable PDF with the annotated film, per-finding evidence, sources and limitations.

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

## Windows setup

The current Windows setup was exercised with **Python 3.11**, an **NVIDIA RTX 4050 with 6 GB VRAM**, and the existing `.venv`. The desktop uses pywebview; Windows PDF export uses Microsoft Edge. PDF history extraction falls back to `pypdf` when Poppler is absent.

### Run on this already configured computer

Open **PowerShell** and run:

```powershell
cd C:\Users\jebas\projects\Hacknex_phase_1\Bonaventure
$env:BV_MEDGEMMA = (Resolve-Path 'models/medgemma-1.5-4b-it').Path
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:PYTHONIOENCODING = 'utf-8'
Remove-Item Env:BV_MOCK -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m bonaventure.app
```

Use your checkout path if it differs. Calling the virtual environment's Python directly avoids PowerShell activation-policy issues. These environment variables apply to the current terminal session.

1. Start **one instance**. Windows does not currently prevent duplicate launches; each instance loads its own models.
2. Wait for **Image AI loaded** and **Reasoning AI loaded**. These indicators mean models are loaded, not that files are attached.
3. Press **Ctrl + Alt + B** to show/hide the centered input panel. `Escape` collapses the expanded intake panel.
4. Click **Chest X-ray** to select a scan, or drag the file into the panel. PNG, JPEG, DICOM, BMP, TIFF and WebP are accepted.
5. Optionally attach text-based PDF/TXT/MD history and type the current symptoms. Scanned PDFs require OCR outside this app.
6. Click **Analyse**. The review displays the scan, findings, context, and model activity. Completed inputs are cleared for the next case.
7. Choose **Export report** to save a PDF under `reports/`. The PDF opens with the Windows default application.

Keep the launching terminal open. To stop the application, use `Ctrl+C` in that terminal; hiding the panel or closing the review does not stop the model process.

Reopen an existing saved case using its actual folder name (with the same environment variables set):

```powershell
.\.venv\Scripts\python.exe -m bonaventure.app BV-014
```

### Preparing another Windows computer

Prerequisites:

- 64-bit Python 3.11 and Git.
- An NVIDIA GPU/driver compatible with the CUDA 12.8 PyTorch build used here. The tested GPU has 6 GB VRAM; the full pipeline has not been verified on CPU alone.
- Microsoft Edge and its WebView2 runtime for the desktop web view; Edge is also used for PDF export.
- The model code, checkpoints, tokenizer files and cached backbone source described below.

The existing `.venv` was created with `--system-site-packages` and also uses installed user packages. Do not overwrite it just to follow these instructions. For a **new checkout**, create an isolated environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m pip install pywebview==6.2.1 pythonnet==3.2.0 pydicom==3.0.2 pypdf==6.7.5 pillow==12.3.0 numpy==2.3.5
.\.venv\Scripts\python.exe -m pip install transformers==5.19.0 accelerate==1.15.0 bitsandbytes==0.50.2 huggingface_hub==1.33.0
.\.venv\Scripts\python.exe -m pip install ftfy==6.3.1 regex==2026.9.29 pandas==2.3.3 scikit-learn==1.8.0 scipy==1.17.1 h5py==3.15.1 tqdm==4.70.1 einops==0.8.2 sentencepiece==0.2.1 protobuf==6.33.6
```

These pins were read from the working environment; a clean installation with these commands has **not** been independently tested. `requirements.txt` contains different NumPy, pandas, SciPy, scikit-learn and h5py pins, so it is not the Windows Python 3.11 environment lock. Windows export does not require WeasyPrint's GTK/Pango dependencies.

Check that the selected interpreter sees CUDA:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print('CUDA available:', torch.cuda.is_available())"
```

### Model files and code

Keep this layout relative to the repository root:

```text
CLEAR/src/clear/                         CLEAR Python source
models/
  clear/
    best_model.pt
    concept_embeddings_368294.pt
    mimic_concepts.csv
  CheXzero/
    model.py
    clip.py
    checkpoints/chexzero_weights/best_128_0.0002_original_15000_0.859.pt
  MedSAM/
    segment_anything/
    work_dir/MedSAM/medsam_vit_b.pth
  medgemma-1.5-4b-it/                     Complete Hugging Face snapshot
  .torch-cache/hub/facebookresearch_dinov2_main/
```

CLEAR also needs its local text/tokenizer assets and cached DINOv2 source. Preserve the configured CLEAR directory and caches when moving this setup; copying checkpoint files alone is insufficient for offline loading. The unused CLEAR `concepts_embeddings_sfr_mistral.pickle` is not required by this pipeline.

Model sources, checkpoint fingerprints and Google Drive download links are recorded in [the model resource register](docs/13_MODEL_RESOURCE_REGISTER.md).

For a new MedGemma download, accept Google's terms on its Hugging Face repository, authenticate locally, then download the complete snapshot:

```powershell
.\.venv\Scripts\hf.exe auth login
.\.venv\Scripts\hf.exe download google/medgemma-1.5-4b-it --local-dir models/medgemma-1.5-4b-it
```

Run downloads before enabling offline mode. If you already set the offline variables in the same terminal, remove them first:

```powershell
Remove-Item Env:HF_HUB_OFFLINE -ErrorAction SilentlyContinue
Remove-Item Env:TRANSFORMERS_OFFLINE -ErrorAction SilentlyContinue
```

Set `BV_MEDGEMMA` explicitly at launch as shown above. `BV_CLEAR_DIR` and `BV_CLEAR_CKPT` can override CLEAR's default model folder and checkpoint.

## Windows verification and sample inputs

After setting the launch environment variables, close other instances and run the native UI acceptance check:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_windows_pipeline
```

This starts the real application, attaches sample files through its drop handler, clicks Analyse, and checks model output and rendered findings. It creates saved cases and writes `reports/pipeline-acceptance-verification.json`; it leaves the positive case open. It uses real models, not demo output.

The Windows run on **7 October 2026** verified:

| Scenario | Inputs | Observed result |
|---|---|---|
| Positive | `kerley_b.jpg` + `case_a_history.pdf` + breathlessness/orthopnoea symptoms | Cardiomegaly and pulmonary edema supported; consolidation conflicting; two MedSAM outlines accepted |
| Contradictory history | Same scan + `case_b_history.pdf` + the test's presentation | All three findings conflicting |
| Normal sample | `Chest_Xray_PA_3-8-2010.png`, no history or symptoms | No accepted findings; localization and MedSAM skipped |

Scans are under `sample_data/scans/`; synthetic histories are under `sample_data/histories/`. The test script contains the exact symptom text. These checks establish software behavior on the samples, not clinical accuracy.

Additional backend demo scenarios and parser checks:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_demo_cases
.\.venv\Scripts\python.exe -m bonaventure.context
.\.venv\Scripts\python.exe -m bonaventure.reconcile
```

## Windows troubleshooting

- **Analyse is disabled:** attach a readable scan and wait for file staging to finish. History is optional. The model-loaded indicators do not indicate attached data.
- **No accepted findings:** read the model activity and rejected claims in the result. Zero accepted findings does not establish that the scan is normal. History entries describe prior observations, not newly detected image findings.
- **No outlines:** MedSAM needs an accepted bounding box. A skipped stage is reported when none is available; failed or unavailable components are shown as limitations.
- **Model startup failure:** check paths, complete downloads and CUDA availability. Startup failure now reports an error rather than automatically returning simulated findings. `BV_MOCK=1` deliberately enables development-only simulated output; remove it for real inference.
- **PDF export fails:** confirm Microsoft Edge is installed and `reports/` is writable. Windows uses headless Edge for export.
- **History has no extracted text:** use a text-based document. OCR is not implemented.
- **Shortcut does not respond:** check the launching terminal for a hotkey-registration warning and close duplicate instances. Another program may own `Ctrl+Alt+B`.
- **Microphone dictation:** the current recording implementation uses Linux PipeWire and has not been ported to Windows. Type the presentation on Windows.

The Linux entry points (`run.sh`, Hyprland toggle socket and GTK drop integration) remain in the repository. They are not the Windows launch commands.

## Repository

```
bonaventure/
  app.py          desktop client: island + reading room, Windows hotkey, Linux Hyprland integration
  pipeline.py     case orchestration, progress states, failure capture
  imaging.py      scan loading (PNG/JPEG/DICOM), quality gate, model engine (+ mock)
  models.py       CLEAR (+ concept bank), CheXzero, MedGemma, MedSAM adapters
  context.py      history + presentation parsing (negation, dates, durations, provenance)
  knowledge.py    clinical vocabulary and finding ↔ evidence map
  reconcile.py    evidence reconciliation engine
  report.py       PDF evidence report
  ui/             island.html, review.html (reading room), base.css, bundled fonts
scripts/          Windows UI verification, demo cases, sample history generator, Linux toggle
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

# Windows setup and verification

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
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
```

These pins were read from the working environment; a clean installation with these commands has **not** been independently tested. `requirements.txt` contains different NumPy, pandas, SciPy, scikit-learn and h5py pins, so it is not the Windows Python 3.11 environment lock. `requirements-windows.txt` preserves the versions recorded by the PR author instead. Windows export does not require WeasyPrint's GTK/Pango dependencies.

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

Model sources, checkpoint fingerprints and Google Drive download links are recorded in [the model resource register](13_MODEL_RESOURCE_REGISTER.md).

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

The PR author reports that their Windows run on **7 October 2026** verified the results below. The native Windows GUI and Edge export have not been independently rerun during integration on Linux:

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

For the same input cases without GUI automation, use `python scripts/reproduce.py --suite acceptance --pdf`. See the [main README](../README.md) for all demo reproduction options.

The Linux entry points (`run.sh`, Hyprland toggle socket and GTK drop integration) remain in the repository. They are not the Windows launch commands.

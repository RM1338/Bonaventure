# Bonaventure — Clinical Evidence Intelligence

**HackNex 2026 Internal Qualifier · HNX26PSI05: Multimodal Medical Image Intelligence**

Bonaventure is a desktop second-opinion assistant for chest X-rays. It reads the **film**, the patient's **history
documents** and the **current presentation** (typed or dictated). For every candidate finding it decides whether the
evidence **SUPPORTS** it, **CONFLICTS**, is **UNCERTAIN** or is **INSUFFICIENT**, and it shows the basis for each call:
where on the film, which document, page and quote, and which symptom. Every claim a model made that the evidence did
not back is listed under *Checked and rejected*.

> Decision support only. Not a diagnosis. It speaks as a helper ("Consider cardiomegaly…"); a qualified clinician
> reviews every output and their verdict is final.

| Document | |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture as built: components, data pipeline, models, reconciliation |
| [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) | One real case followed from input to report, with the actual numbers |
| [`docs/PS05_CHECKLIST.md`](docs/PS05_CHECKLIST.md) | Every PS05 requirement and submission guideline, and where it is met |
| [`docs/13_MODEL_RESOURCE_REGISTER.md`](docs/13_MODEL_RESOURCE_REGISTER.md) | Declared models, datasets and libraries |
| [`docs/sample_output/`](docs/sample_output/) | Real outputs: result JSON for demo cases A–E and a normal film, PDF report, annotated film |

---

## See it working

Recorded on the development laptop (Linux, Hyprland), running the real models on demo case 02 from [`demo_data/`](demo_data/).

**The island:** the pill at the top of the screen expands; the film and the history PDF are dropped in, the presentation
is typed, and *Analyse* runs the seven steps inside the island. The waiting is sped up 7×; the real case took about a minute,
including model warm-up.

![Island launcher: pill → intake → analysis](docs/media/island_demo.gif)

**The reading room** that opens when the case is ready, with the occlusion heatmap toggled on and off (`H`):

![Reading room with heatmap](docs/media/reading_room_demo.gif)

## What it does

1. **Island launcher**: a black Dynamic-Island-style pill at the top of the screen (`Super + Alt + B` or the bar
   icon on Linux). Drop the X-ray (PNG, JPEG or DICOM) and the history PDFs, then type or
   **dictate** the presentation. Words appear live while you speak. Press *Analyse*; progress is shown inside the island.
2. **Four local models read the film.**
   * CLEAR and CheXzero score 16 findings with calibrated cut-offs.
   * CLEAR's concept bank ranks the film against 368,294 radiology-report phrases.
   * MedGemma 1.5 surveys, describes and boxes what it sees.
   * MedSAM turns each box into an outline.
3. **The patient context is read with provenance.**
   * History: dated, negation-aware facts, each with its file, page and verbatim quote.
   * Presentation: understood by MedGemma (rewritten into clinical terms) and checked by deterministic rules.
     Disagreements are flagged, and phrases nothing understood are listed instead of being guessed.
   * Patient identity is checked across all documents and the DICOM header.
4. **Reconciliation.** Explicit rules combine image agreement, history, symptoms and image quality into one evidence
   state per finding, with its reasons and an evidence strength.
5. **Reading room.** A dark review window shows the film with hand-drawn grease-pencil outlines, the findings, and for
   the selected one, what each reader said with its sources. It also shows:
   * *Since last report* (NEW / KNOWN / NOT SEEN NOW), compared with the patient's prior radiology report.
   * *Not assessable on X-ray*, e.g. pulmonary embolism, with the test that would settle it.
   * *Also seen* (verified observations outside the catalogue) and *Rejected claims*.
   * A **heatmap** for each finding (where the image reader's score comes from) and an **image confidence %**.
   * **Agree / Disagree**: a clinician who disagrees gets the evidence for and against their read, plus a second look
     from MedGemma; their verdict is recorded.
6. **PDF evidence report**: annotated film, lung diagram, per-finding evidence with sources, clinician review, rejected
   claims and limitations.

## System architecture

Five layers: inputs → desktop app → analysis core → reasoning → outputs. Everything runs locally, and the analysis core
lives apart from the window code (`desktop.Api` + `pipeline`), so only the shell is OS-specific.

![System architecture](docs/diagrams/system_architecture.png)

### Image-evidence pipeline and its hallucination checks

Every model claim has to pass an independent check. A claim that fails is not silently dropped: it goes to the
*Checked and rejected* log that the clinician can open, with who made the claim and why it was rejected.

![Image evidence pipeline](docs/diagrams/image_evidence_pipeline.png)

Diagrams made in Lucidchart ([architecture](https://lucid.app/lucidchart/e5b63320-38d0-43b9-97ed-96ebaa596446/view),
[pipeline](https://lucid.app/lucidchart/b0a9129b-89d2-4667-a56d-17d0a5b11067/view)). Module-level detail, the reconciliation
decision tree and the `result.json` contract are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Models

All models run locally on the laptop. None was trained or fine-tuned by us; they were **calibrated** on labelled data
(see Evaluation).

| Model | What Bonaventure uses it for | Links | Licence |
|---|---|---|---|
| **CLEAR** (DINOv2 ViT-B/14 image encoder + text encoder) | Primary image reader: zero-shot score per finding from a positive / negative prompt pair | [code](https://github.com/peterhan91/CLEAR) · [weights](https://huggingface.co/peterhan91/CLEAR) | Apache-2.0 |
| **CLEAR concept bank** (368,294 report-phrase embeddings) | Ranks the film against real radiology phrases: specificity gate, third reader, quotes shown as evidence | [weights](https://huggingface.co/peterhan91/CLEAR) (`concept_embeddings_368294.pt`, `mimic_concepts.csv`) | Apache-2.0 |
| **CheXzero** (CLIP ViT-B/32 trained on MIMIC-CXR) | Independent verifier with the same prompts; occlusion heatmap | [code + weights](https://github.com/rajpurkarlab/CheXzero) | MIT |
| **MedGemma 1.5 4B-it** (4-bit NF4) | Open survey of the film, per-finding visibility + observations, bounding boxes, clinical rewrite of the presentation, second look when a clinician disagrees | [Hugging Face](https://huggingface.co/google/medgemma-1.5-4b-it) | Health AI Developer Foundations terms |
| **MedSAM** (SAM ViT-B, medical) | Turns each box into an outline | [code + weights](https://github.com/bowang-lab/MedSAM) | Apache-2.0 |
| **DINOv2** (code only) | Backbone architecture loaded by CLEAR | [code](https://github.com/facebookresearch/dinov2) | Apache-2.0 |
| **Whisper base.en** | Live dictation captions | [Hugging Face](https://huggingface.co/openai/whisper-base.en) | MIT |
| **Whisper small.en** | Final dictation transcript | [Hugging Face](https://huggingface.co/openai/whisper-small.en) | MIT |
| **all-MiniLM-L6-v2** | Meaning-based fallback for presentation phrases no rule recognises | [Hugging Face](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | Apache-2.0 |

## Datasets

No dataset was used for training. The datasets below were used **only** to evaluate and calibrate the readers, to audit
hallucinations, and to build the demo data.

| Dataset | Used for | Where we pulled it from | Licence |
|---|---|---|---|
| **CheXpert v1.0** (validation split, 202 frontal films, radiologist consensus labels) | AUROC and calibration of CLEAR and CheXzero for 8 findings; confidence % (Platt scaling) | [danjacobellis/chexpert](https://huggingface.co/datasets/danjacobellis/chexpert) on Hugging Face · original: [Stanford ML Group](https://stanfordmlgroup.github.io/competitions/chexpert/) | Stanford CheXpert Research Use Agreement: **not redistributed here**, only the derived numbers |
| **NIH ChestX-ray14** (test split, 2 shards; NLP-mined labels) | Calibration of pneumonia, nodule, mass, emphysema, fibrosis, pleural thickening, hernia; the 36-film hallucination audit; **the 14 demo-data films** | [timm/nih-chest-xray-14](https://huggingface.co/datasets/timm/nih-chest-xray-14) on Hugging Face · original: [NIH Clinical Center](https://nihcc.app.box.com/v/ChestXray-NIHCC) (Wang et al., CVPR 2017) | No restrictions (NIH Clinical Center) |
| **MIMIC-CXR report phrases** | Inside the CLEAR concept bank (phrases only, as released by CLEAR) | via [CLEAR](https://huggingface.co/peterhan91/CLEAR) | as released by CLEAR |
| **Wikimedia Commons** CC0 radiographs | The acceptance cases A–E in `sample_data/` | [Kerley B lines](https://commons.wikimedia.org/wiki/File:Chest_radiograph_of_a_lung_with_Kerley_B_lines.jpg), [normal PA](https://commons.wikimedia.org/wiki/File:Normal_posteroanterior_(PA)_chest_radiograph_(X-ray).jpg), [PA 3-8-2010](https://commons.wikimedia.org/wiki/File:Chest_Xray_PA_3-8-2010.png) | CC0 |

All patient histories and presentations in this repository are **fictional**.

## Technologies and libraries

| Layer | Used |
|---|---|
| Runtime | Python 3.12+, PyTorch 2.11 (CUDA 12.8), transformers 5.19, bitsandbytes 0.50 (4-bit), accelerate |
| Desktop | pywebview 6.2 on WebKitGTK (Linux), HTML/CSS/JS UI, Hyprland window rules |
| Documents | poppler `pdftotext` / `pdfinfo`, WeasyPrint (PDF report), pydicom, Pillow, NumPy |
| Audio | PipeWire `pw-record` |
| Evaluation | scikit-learn (ROC, AUROC, logistic calibration), pandas (parquet datasets) |

Everything runs **locally and offline**. No external API is called and no patient data leaves the machine. Versions and
licences: [`docs/13_MODEL_RESOURCE_REGISTER.md`](docs/13_MODEL_RESOURCE_REGISTER.md).

---

## Install

### Linux (tested: Arch / Omarchy + Hyprland, RTX 3050 6 GB)

```bash
sudo pacman -S --needed webkit2gtk-4.1 python-gobject poppler pipewire   # system deps
uv venv --python /usr/bin/python3 --system-site-packages .venv          # system site-packages for the GTK bindings
uv pip install --python .venv/bin/python torch torchvision --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv/bin/python -r requirements.txt
```

### Models

```bash
# model code (cloned into the repo root)
git clone https://github.com/peterhan91/CLEAR
git clone https://github.com/rajpurkarlab/CheXzero     # weights → CheXzero/checkpoints/chexzero_weights/best_128_0.0002_original_15000_0.859.pt
git clone https://github.com/bowang-lab/MedSAM         # weights → MedSAM/work_dir/MedSAM/medsam_vit_b.pth

# weights (MedGemma is gated: accept the licence on Hugging Face and `hf auth login` first)
M=~/bonaventure/models
hf download peterhan91/CLEAR best_model.pt concept_embeddings_368294.pt mimic_concepts.csv --local-dir $M/clear
hf download google/medgemma-1.5-4b-it --local-dir $M/medgemma-1.5-4b-it
hf download openai/whisper-base.en  --local-dir $M/whisper-base.en         # dictation (optional)
hf download openai/whisper-small.en --local-dir $M/whisper-small.en
hf download sentence-transformers/all-MiniLM-L6-v2 --local-dir $M/minilm  # phrase fallback (optional)

.venv/bin/python -m bonaventure.model_paths   # prints every model path and whether it was found
.venv/bin/python scripts/check_setup.py       # dependency + weight check without loading the models
```

An in-repo layout (`models/CLEAR`, `models/CheXzero`, `models/MedSAM`, `models/MedGemma`) is also found automatically.

## Configure

No configuration is needed for the default layout. Optional environment variables:

| Variable | Effect |
|---|---|
| `BV_MOCK=1` | Run the UI without models (clearly labelled mock output) |
| `BV_MEDGEMMA`, `BV_CLEAR_DIR`, `BV_CHEXZERO_DIR`, `BV_MEDSAM_DIR`, `BV_MODELS_DIR` | Point at model folders elsewhere |
| `BV_WHISPER`, `BV_WHISPER_LIVE`, `BV_MINILM` | Dictation / meaning-fallback model folders |
| `BV_CLIP_DEVICE=cuda` | Run CLEAR and CheXzero on the GPU (default CPU, which leaves VRAM for MedGemma + MedSAM) |
| `BV_START=expand` | Open the island expanded at launch |

The Linux shortcut and bar button only need to run `scripts/bonaventure-toggle`. This starts the app, or shows/hides the
island if it is already running.

## Run

```bash
./run.sh                    # island launcher; models load in the background (~20 s)
./run.sh BV-151             # reopen a saved case in the reading room
scripts/bonaventure-toggle  # show / hide the island
```

Saved cases are in `cases/BV-xxx/` (inputs, `scan.png`, `result.json`); reports go to `reports/BV-xxx.pdf`.

---

## Demo data

[`demo_data/`](demo_data/) holds **14 demo cases, one per condition**. Each case folder has the input files and what
Bonaventure reported:

```
demo_data/02 Cardiomegaly/
  film.png           the medical image (NIH ChestX-ray14 film 00004344_013, labelled "Cardiomegaly")
  history.pdf        fictional patient record (cardiology note, echo report)
  presentation.txt   fictional current presentation, as a clinician would type or dictate it
  result.txt         what Bonaventure reported for this case
```

The films are real NIH ChestX-ray14 test-split images chosen by their dataset label
([`scripts/build_demo_library.py`](scripts/build_demo_library.py)); every film is a different image, and every patient has
a different, fictional history and presentation. To try one, drop `film.png` and `history.pdf` on the island and paste
`presentation.txt`.

### Sample input and output: demo case 02 (cardiomegaly)

**Input:**
* `film.png`: NIH film labelled *Cardiomegaly*.
* `history.pdf`: *"Dilated cardiomyopathy, LVEF 30 %. Hypertension since 2010."*; furosemide; echo with moderate
  mitral regurgitation.
* Presentation: *"Tired all the time for 3 weeks, breathless on climbing one flight of stairs, both ankles swollen by
  evening."*

**Output** ([result JSON](docs/sample_output/demo02_cardiomegaly_result.json) · [PDF report](docs/sample_output/demo02_cardiomegaly_report.pdf)):

![Annotated film, demo case 02](docs/sample_output/demo02_cardiomegaly_annotated.png)

| Finding | State | Strength · image confidence | Evidence shown to the clinician |
|---|---|---|---|
| Cardiomegaly | **SUPPORTED** | high · 96 % (CLEAR 99, CheXzero 94) | MedGemma: "The heart appears enlarged, with a prominent cardiac silhouette"; MedSAM outline of the heart; echo report p.1 "Dilated cardiomyopathy, LVEF 30%"; fatigue for 3 weeks, breathlessness, ankle swelling |
| Pulmonary edema | **SUPPORTED** | high · 82 % (CLEAR 92, CheXzero 73) | MedGemma: "increased opacity in the lung fields, suggestive of pulmonary edema"; furosemide in the record; breathlessness, ankle swelling |
| Consolidation | **SUPPORTED** | high · 32 % (CLEAR 48, CheXzero 17) | Both readers above their cut-offs and breathlessness supports it, **but** MedGemma did not see it and the image confidence is only 32 %. It is drawn as an approximate zone. See Limitations |

* 10 model claims were checked and rejected, e.g. "right-sided central venous catheter" and "left lower lobe opacity"
  (MedGemma's survey; CLEAR did not confirm them).

### All 14 demo cases (current code)

| Case | What Bonaventure reports (state, strength, image confidence) |
|---|---|
| 01 Pleural effusion | Pleural effusion: SUPPORTED (high, image confidence 98 %); Consolidation: SUPPORTED (high, image confidence 84 %); Pleural thickening: SUPPORTED (high, image confidence 28 %); Atelectasis: SUPPORTED (moderate, image confidence 62 %); Cardiomegaly: SUPPORTED (high, image confidence 54 %); Pulmonary edema: UNCERTAIN (moderate, image confidence 74 %) |
| 02 Cardiomegaly | Cardiomegaly: SUPPORTED (high, image confidence 96 %); Pulmonary edema: SUPPORTED (high, image confidence 82 %); Consolidation: SUPPORTED (high, image confidence 32 %) |
| 03 Pulmonary edema | Pulmonary edema: SUPPORTED (high, image confidence 94 %); Consolidation: SUPPORTED (high, image confidence 48 %); Cardiomegaly: SUPPORTED (high, image confidence 92 %); Atelectasis: UNCERTAIN (low, image confidence 49 %) |
| 04 Pneumonia | Pleural effusion: SUPPORTED (high, image confidence 98 %); Consolidation: SUPPORTED (high, image confidence 84 %); Pulmonary edema: UNCERTAIN (moderate, image confidence 60 %); Atelectasis: UNCERTAIN (moderate, image confidence 66 %); Pleural thickening: UNCERTAIN (low, image confidence 38 %); Lines & devices: UNCERTAIN (moderate, image confidence 56 %); Cardiomegaly: UNCERTAIN (moderate, image confidence 79 %) |
| 05 Atelectasis | Atelectasis: SUPPORTED (high, image confidence 86 %); Widened mediastinum: CONFLICTING (low, image confidence 52 %) |
| 06 Pneumothorax | Cardiomegaly: SUPPORTED (high, image confidence 32 %); Lines & devices: UNCERTAIN (low, image confidence 38 %); Pneumothorax: UNCERTAIN (moderate, image confidence 53 %); Atelectasis: UNCERTAIN (moderate, image confidence 75 %); Pleural effusion: UNCERTAIN (moderate, image confidence 64 %) |
| 07 Lung mass | Widened mediastinum: CONFLICTING (low, image confidence 45 %); Consolidation: UNCERTAIN (moderate, image confidence 20 %); Lines & devices: UNCERTAIN (low, image confidence 32 %); Atelectasis: UNCERTAIN (moderate, image confidence 43 %); Also seen: Right upper lobe opacity; Also seen: Right lower lobe opacity |
| 08 Emphysema | Emphysema: SUPPORTED (high); Atelectasis: UNCERTAIN (moderate, image confidence 34 %) |
| 09 Pulmonary fibrosis | Pulmonary fibrosis: SUPPORTED (high); Cardiomegaly: SUPPORTED (high, image confidence 56 %); Consolidation: UNCERTAIN (moderate, image confidence 49 %); Pulmonary edema: UNCERTAIN (moderate, image confidence 70 %) |
| 10 Pleural thickening | Pleural thickening: SUPPORTED (high, image confidence 44 %); Pleural effusion: SUPPORTED (high, image confidence 98 %); Atelectasis: SUPPORTED (high, image confidence 59 %); Cardiomegaly: SUPPORTED (high, image confidence 38 %); Consolidation: CONFLICTING (moderate, image confidence 54 %); Pulmonary edema: UNCERTAIN (low, image confidence 22 %); Also seen: Right lung opacity; Also seen: Elevated right hemidiaphragm |
| 11 Hiatus hernia | Hiatus hernia: SUPPORTED (high, image confidence 70 %); Cardiomegaly: SUPPORTED (high, image confidence 61 %); Pleural thickening: SUPPORTED (moderate, image confidence 25 %); Atelectasis: INSUFFICIENT_EVIDENCE (low, image confidence 30 %); Lines & devices: INSUFFICIENT_EVIDENCE (low, image confidence 38 %) |
| 12 Lines and devices | Cardiomegaly: UNCERTAIN (moderate, image confidence 96 %); Pulmonary edema: UNCERTAIN (moderate, image confidence 64 %); Pleural effusion: UNCERTAIN (moderate, image confidence 58 %); Lines & devices: UNCERTAIN (moderate, image confidence 74 %); Atelectasis: UNCERTAIN (low, image confidence 44 %) |
| 13 Normal | No findings |
| 14 Pulmonary embolism (not on X-ray) | Not assessable on X-ray: Pulmonary embolism |

These are unedited outputs, including the imperfect ones. Of the 12 cases with a condition visible on X-ray, 11 raise
it: pneumonia (04) appears as consolidation, and the pneumothorax (06) and the devices (12) only as *uncertain*. The lung
mass (07) is not raised; masses are a known weak spot. Several cases
also show extra findings. The normal film (13) gets no findings, and the pulmonary-embolism case (14) correctly gets no
image finding, only the *not assessable on X-ray* advisory. Regenerate with `scripts/run_demo_library.py`.

### Acceptance cases A–E

[`sample_data/`](sample_data/) holds five scripted acceptance cases on CC0 Wikimedia films. They test the reasoning rather
than the image models: the same film with agreeing vs. contradicting history (A/B), a degraded image (C), a condition an
X-ray cannot show (D), and records from two different patients (E). Their outputs are in
[`docs/sample_output/`](docs/sample_output/), and case A is followed step by step in [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md).

## Reproduce the demonstrated results

```bash
PYTHONPATH=. .venv/bin/python scripts/run_demo_cases.py   # demo cases A–E + two normal films, on the real models
.venv/bin/python -m bonaventure.context && .venv/bin/python -m bonaventure.reconcile && .venv/bin/python -c 'from bonaventure import models; models._selftest()'   # self-tests
```

| Case | Input | Expected result |
|---|---|---|
| A · agreement | Kerley-B film + heart-failure history + breathlessness, orthopnea | Cardiomegaly and edema **SUPPORTED · high**, localized; consolidation **CONFLICTING** (fever and cough denied) |
| B · contradiction | *Same film* + a history whose recent report reads "normal heart size, lungs clear" | Everything **CONFLICTING**, quoting the report; since last report: **NEW** |
| C · poor image | Degraded film | **INSUFFICIENT_EVIDENCE**: no forced conclusion |
| D · not on X-ray | Normal film + post-op knee replacement, pleuritic pain, racing heart, calf swelling | No image finding; **pulmonary embolism: not assessable on a chest X-ray**, with Wells/D-dimer/CTPA advice |
| E · wrong patient | Records from two different patients | **Identity mismatch**: history not used, interval comparison blocked |
| N, N2 · normal | Two normal films | No findings |

Real outputs of these runs are in [`docs/sample_output/`](docs/sample_output/).

Calibration and audit (needs the datasets, see the register):

```bash
PYTHONPATH=. .venv/bin/python scripts/calibrate.py      # → bonaventure/calibration.json
PYTHONPATH=. .venv/bin/python scripts/eval_concepts.py  # → bonaventure/concept_calibration.json
PYTHONPATH=. .venv/bin/python scripts/audit.py          # → bonaventure/audit.json (36 unseen NIH films)
```

## Evaluation

For each finding and reader, AUROC on labelled films and three cut-offs read off the ROC curve: *weak* = 90 %
sensitivity, *moderate* = Youden's J, *strong* = 90 % specificity. **A reader only votes where AUROC ≥ 0.70.**

| Finding | Source (positives) | CLEAR | CheXzero | Both | Votes |
|---|---|---|---|---|---|
| Pleural effusion | CheXpert (64+) | 0.909 | 0.884 | 0.904 | CLEAR + CheXzero |
| Cardiomegaly | CheXpert (66+) | 0.848 | 0.825 | 0.843 | CLEAR + CheXzero |
| Pulmonary edema | CheXpert (42+) | 0.912 | 0.906 | 0.935 | CLEAR + CheXzero |
| Consolidation | CheXpert (32+) | 0.901 | 0.851 | 0.897 | CLEAR + CheXzero |
| Atelectasis | CheXpert (75+) | 0.814 | 0.786 | 0.817 | CLEAR + CheXzero |
| Pneumothorax | CheXpert (7+) | 0.785 | 0.763 | 0.800 | CLEAR + CheXzero (hand-set cut-offs: too few positives) |
| Widened mediastinum | CheXpert (105+) | 0.880 | 0.877 | 0.900 | CLEAR + CheXzero |
| Lines & devices | CheXpert (99+) | 0.736 | 0.730 | 0.755 | CLEAR + CheXzero |
| Pleural thickening | NIH (85+) | 0.699 | 0.730 | 0.734 | CheXzero |
| Pneumonia | NIH (60+) | 0.724 | 0.689 | 0.715 | CLEAR |
| Hiatus hernia | NIH (30+) | 0.531 | 0.859 | 0.724 | CheXzero |
| Emphysema / fibrosis | NIH (68+ each) | 0.63 | 0.55 | — | concept bank (AUROC 0.829 / 0.768) + MedGemma + history |
| Lung mass / nodule | NIH (79+ / 82+) | 0.67 / 0.54 | 0.62 / 0.51 | — | none: only via the MedGemma survey, verified by CLEAR |
| Rib fracture | — | — | — | — | no labels: never raised by the image models |

**Hallucination audit** (`scripts/audit.py`, full pipeline on 36 NIH films not used for calibration, film only, no
history):

| | Result |
|---|---|
| Normal films with a **SUPPORTED** finding | **1 / 12** (a "lines & devices" false positive; see the checklist) |
| Normal films with any UNCERTAIN / CONFLICTING item | 9 / 12: never presented as supported, each says "no supporting clinical context" |
| Normal films with an "also seen" observation | 3 / 12 |
| Diseased films where the labelled disease was raised | **10 / 24**: cardiomegaly 2/2, edema 2/2, consolidation 2/2, atelectasis 2/2, effusion 1/2, pleural thickening 1/2; 0/2 for pneumothorax, pneumonia, mass, nodule, emphysema, fibrosis (the last two need a supporting history, and the audit supplies none) |
| Model claims removed by the cross-checks | 193 (all listed per case under *Checked and rejected*) |

This is the worst case: a bare film with no history and no presentation, where the context rule cannot help.
These numbers are from before the final bare-film rule (a finding on a film with no context must be seen by both image
models, or named by MedGemma unprompted and confirmed by CLEAR; devices need that same evidence). A re-check of the same
12 normal films after it: **no SUPPORTED and no CONFLICTING item on any of them**, 5 / 12 completely clean. The full
36-film audit was not re-run after that change; demo cases A–E were, with identical results.

---

## Scope note

| Minimum viable solution (implemented, demonstrated) | Stretch goals |
|---|---|
| Chest X-ray input (PNG/JPEG/DICOM) with a quality gate | **Implemented:** MedSAM segmentation outlines; open-ended "also seen" survey; dictation with live captions; LLM understanding of free-text presentations; patient identity check; "since last report"; clinician challenge + second look; rejected-claims log; lung diagram in the report |
| Multi-model image reading with calibrated levels and confidence %, localization (box/outline/zone), occlusion heatmap | **Not done:** CT / MRI; OCR for scanned history PDFs; trained (not zero-shot) classifiers; reliable nodule / mass / pneumothorax detection; macOS shell (in progress, separate branch) |
| History parsing with negation, dates and page-level provenance | |
| Evidence reconciliation → SUPPORTED / UNCERTAIN / CONFLICTING / INSUFFICIENT with reasons | |
| Desktop review UI and PDF evidence report | |

## Limitations

* Chest X-ray only, frontal views. 16 catalogue findings. Nodules, masses and pneumothorax are not reliably detected.
* Evidence strength is a rule-based summary of agreement. The **image confidence %** is calibrated (Platt scaling) on
  CheXpert / NIH films, whose prevalence differs from clinical use; it describes the image only.
* Calibration sets are small: 202 CheXpert validation films (only 7 pneumothoraces) and NIH labels that are NLP-mined.
* MedGemma boxes are approximate; when a box contradicts its own region text it is discarded and an approximate zone is
  shown instead, labelled as such.
* History parsing is rule-based with no OCR. The presentation uses an LLM, checked by rules, so some phrasing can still
  be missed; it is then listed as "not understood".

## Repository

```
bonaventure/
  app.py            entry point (starts the Linux shell)
  desktop.py        shared UI bridge (intake, analysis, review, challenge, dictation, export)
  linux_app.py      Linux shell: Hyprland island placement, GTK drag-and-drop
  pipeline.py       case orchestration, progress, presentation understanding
  imaging.py        scan loading (PNG/JPEG/DICOM), quality gate, model engine (+ mock)
  models.py         CLEAR, concept bank, CheXzero, MedGemma, MedSAM; image-evidence stage
  context.py        history + presentation parsing (negation, dates, durations, provenance, identity)
  semantic.py       MiniLM meaning fallback
  reconcile.py      evidence reconciliation, interval change, not-assessable, challenge discussion
  knowledge.py      clinical vocabulary, findings, anatomical zones
  report.py         PDF evidence report, lung diagram
  dictation.py      offline Whisper dictation with live captions
  model_paths.py    model locations (both layouts, env overrides)
  calibration.json, concept_calibration.json, audit.json
  ui/               island.html (launcher), review.html (reading room), fonts
scripts/            calibration, audit, demo cases, demo library, setup checks, toggle
demo_data/          14 demo cases (NIH films + fictional histories, presentations, results)
sample_data/        acceptance cases A–E (CC0 films, fictional histories)
docs/               architecture, walkthrough, PS05 checklist, sample outputs, diagrams, GIFs, planning docs, model register
```

## Original contribution vs. external components

**Original:** the workflow and product; the evidence-reconciliation engine and all its rules; per-reader calibration
and the concept-rank specificity gate; the cross-checks between models (survey verified by CLEAR, box vs region,
mask vs box); history parsing with provenance; the presentation-understanding layers; the identity check; interval
change; not-assessable advisories; clinician challenge; the rejected-claims log; the island and reading-room UI; the
PDF report.

**External** (declared in the register): CLEAR and its concept bank, CheXzero, MedGemma 1.5, MedSAM, Whisper, MiniLM,
DINOv2 code, open-source libraries, the CheXpert and NIH datasets (calibration and evaluation only, nothing trained),
and CC0 demo films.

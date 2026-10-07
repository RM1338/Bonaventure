# Model / Resource Register

The HackNex rules require teams to declare external APIs, datasets, pretrained models, open-source components, and other significant resources.

## 1. Pretrained Models

| Resource | Purpose | Version / Checkpoint | Source | License | Local/Remote | Notes |
|---|---|---|---|---|---|---|
| CLEAR (DINOv2 ViT-B/14 + text encoder) | Primary chest X-ray model — zero-shot positive/negative prompt pairs per finding | `best_model.pt`, HF revision `142f169c` | huggingface.co/peterhan91/CLEAR, code github.com/peterhan91/CLEAR (`57d2eae`) | Apache-2.0 | Local (CPU, fp32) | Per-finding levels calibrated on CheXpert validation (`bonaventure/calibration.json`) |
| CLEAR concept bank | Auditable image evidence: the film is ranked against 368,294 radiological observations; matches per finding are shown as quotes (for / against) | `concept_embeddings_368294.pt`, `mimic_concepts.csv` | huggingface.co/peterhan91/CLEAR | Apache-2.0 | Local (CPU, fp16 in RAM) | `concepts_embeddings_sfr_mistral.pickle` (6 GB) is not used |
| CheXzero (CLIP ViT-B/32 fine-tuned on MIMIC-CXR) | Independent verifier — same prompt pairs, separately trained | `best_128_0.0002_original_15000_0.859.pt` | github.com/rajpurkarlab/CheXzero (`5c341db`), Google Drive weights | MIT | Local (CPU, fp32) | Per-finding levels calibrated on CheXpert validation |
| MedGemma 1.5 4B-it | Visual reasoning: open-ended survey, per-candidate visibility + observations, bounding boxes; clinical rewrite of the presentation; second look when a clinician disagrees | `google/medgemma-1.5-4b-it` | huggingface.co/google/medgemma-1.5-4b-it | Health AI Developer Foundations terms | Local (GPU, 4-bit NF4 via bitsandbytes) | Never creates findings: only describes/localizes candidates the image models raised. Boxes are approximate |
| DINOv2 (code only) | Backbone architecture loaded by CLEAR through `torch.hub` | facebookresearch/dinov2 `main` | github.com/facebookresearch/dinov2 | Apache-2.0 | Local | Weights come from the CLEAR checkpoint |
| Whisper base.en | Live dictation captions (re-read every ~1 s while the clinician speaks) | `openai/whisper-base.en` | huggingface.co/openai/whisper-base.en | MIT | Local (CPU) | Primed with a clinical vocabulary prompt |
| Whisper small.en | Final dictation transcript when recording stops | `openai/whisper-small.en` | huggingface.co/openai/whisper-small.en | MIT | Local (CPU) | Primed with the same prompt |
| all-MiniLM-L6-v2 | Meaning-based fallback for presentation phrases no rule recognises | `sentence-transformers/all-MiniLM-L6-v2` | huggingface.co/sentence-transformers/all-MiniLM-L6-v2 | Apache-2.0 | Local (CPU) | Accepts only a clear match (cosine ≥ 0.40, margin ≥ 0.08) |
| MedSAM (SAM ViT-B, medical fine-tune) | Segmentation: MedGemma's box → mask; the mask outline is what the grease pencil traces | `medsam_vit_b.pth` | github.com/bowang-lab/MedSAM (`d71e8a1`) | Apache-2.0 | Local (GPU fp16, CPU fallback) | Masks outside 0.08–1.6× the box area are rejected and the box is kept |

## 2. Datasets

No dataset was used for training.

| Dataset | Purpose | Split Used | License | URL / Source | Notes |
|---|---|---|---|---|---|
| CheXpert v1.0 (small) | Evaluation (AUROC) and threshold calibration of CLEAR and CheXzero | Validation, 202 frontal of 234 studies | Stanford University School of Medicine CheXpert Dataset Research Use Agreement | huggingface.co/datasets/danjacobellis/chexpert | Radiologist consensus labels; not redistributed in this repository |
| NIH ChestX-ray14 | Calibration for findings CheXpert does not label (pneumonia, nodule, mass, emphysema, fibrosis, pleural thickening, hernia); hallucination audit on 36 unseen films; the 14-case demo library | Test split (2 parquet shards) | CC0 (NIH Clinical Center) | huggingface.co/datasets/timm/nih-chest-xray-14 | NLP-mined labels (noisier); Wang et al., CVPR 2017 |

Demo inputs:

| Resource | Purpose | License | Source | Notes |
|---|---|---|---|---|
| "Chest radiograph of a lung with Kerley B lines" (M. Häggström) | Demo cases A and B | CC0 | Wikimedia Commons | `sample_data/scans/kerley_b.jpg` |
| "Normal posteroanterior (PA) chest radiograph" (M. Häggström) | Demo case C (degraded copy) and normal sample | CC0 | Wikimedia Commons | `degraded_cxr.jpg` is downscaled, blurred, underexposed |
| "Chest Xray PA 3-8-2010" (Stillwaterising) | Normal sample | CC0 | Wikimedia Commons | |
| Synthetic patient histories | Demo histories (fictional patients) | Own work | `scripts/make_sample_histories.py` | No real patient data |
| Demo library histories | 14 fictional patients, one per disease, paired with NIH films | Own work | `scripts/build_demo_library.py` | No real patient data |

## 3. Open-Source Libraries

| Library | Purpose | Version |
|---|---|---|
| pywebview + WebKitGTK | Native desktop windows (island launcher, reading room) | 6.2.1 / webkit2gtk-4.1 |
| PipeWire `pw-record` | Microphone capture for dictation | system |
| WeasyPrint | PDF evidence report | 70.0 |
| poppler `pdftotext` / `pdfinfo` | PDF text extraction for patient history | 26.08 (system) |
| PyTorch / torchvision | Model inference | 2.11.0+cu128 / 0.26.0 |
| transformers / accelerate / bitsandbytes | MedGemma loading, 4-bit quantization | 5.19.0 / 1.15.0 / 0.50.2 |
| pydicom, Pillow, NumPy | DICOM/image loading, quality metrics | 3.0.2 / 12.3.0 / 2.5.3 |
| Inter, Caveat (SIL OFL), Special Elite (Apache-2.0) | UI fonts, bundled offline | fontsource |

## 4. External APIs

| API | Purpose | Required for Demo? | Fallback |
|---|---|---|---|
| None | Everything runs locally on the laptop (RTX 3050 6 GB) | No | `BV_MOCK=1` runs the UI with clearly labelled mock models |

## 5. Resource Declaration Policy

For every external component record:
- exact name,
- version,
- purpose,
- license,
- where it is used,
- whether results depend on it.

Do not claim externally pretrained components as original work.

The original contribution must be clearly identified as:
- workflow,
- integration,
- evidence reconciliation,
- uncertainty handling,
- clinical context fusion,
- product interaction,
- report/evidence traceability.

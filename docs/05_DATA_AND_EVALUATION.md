# Data and Evaluation Plan

## 1. Purpose

The PS judges the system on:

- abnormality detection/classification,
- exact region localization,
- use of image and patient context together,
- optional segmentation,
- realistic confidence,
- evidence-backed explanation,
- poor-quality image handling.

This document defines how Bonaventure will test those capabilities.

## 2. Data Categories

### A. Chest X-ray Images
Use public/de-identified datasets that provide:
- labels,
- and preferably localization annotations for at least some findings.

### B. Patient History
Use:
- synthetic history documents,
- public de-identified examples,
- manually constructed context paired to demo images.

No real identifiable patient data is required.

### C. Current Symptoms
Create structured test prompts:
- supporting,
- neutral,
- contradictory,
- missing.

## 3. Evaluation Dimensions

### 3.1 Finding Detection
Metrics depend on available labels:
- AUROC,
- precision,
- recall,
- F1,
- per-class sensitivity/specificity where useful.

Do not report a single generic “accuracy” without defining the dataset and threshold.

### 3.2 Localization
If bounding-box ground truth exists:
- IoU,
- localization hit rate.

If only weak localization is available:
- report qualitative localization separately and do not overclaim.

### 3.3 History Extraction
For a small manually labeled set:
- entity precision,
- entity recall,
- date extraction correctness,
- negation correctness,
- provenance correctness.

### 3.4 Symptom Parsing
Measure:
- concept extraction accuracy,
- negation handling,
- duration extraction where present.

### 3.5 Evidence Reconciliation
Build manually specified cases:

#### Case Type A — Strong Agreement
Image + history + symptoms agree.

Expected:
SUPPORTED.

#### Case Type B — Weak Context
Image signal exists but history/symptoms do not support it.

Expected:
UNCERTAIN or SUPPORTED with reduced evidence strength depending on image evidence.

#### Case Type C — Contradiction
Models or evidence sources disagree.

Expected:
CONFLICTING.

#### Case Type D — Poor Input
Image unsuitable.

Expected:
INSUFFICIENT_EVIDENCE.

### 3.6 Robustness
Test:
- lower resolution,
- mild blur,
- rotation,
- crop,
- compression.

Record:
- finding stability,
- localization stability,
- whether quality warning activates.

## 4. Demo Case Set

Prepare at least three deterministic cases:

### Demo Case 1 — High Agreement
Purpose:
Show normal successful path.

### Demo Case 2 — Contradiction
Purpose:
Show that the system does not blindly trust one model.

### Demo Case 3 — Poor / Ambiguous Evidence
Purpose:
Show safe uncertainty handling.

## 5. Evidence-Grounding Checks

For every displayed finding verify:

- image evidence exists,
- region exists where localization is claimed,
- history facts have source provenance,
- current symptom support comes from entered symptoms,
- contradictions are not hidden.

## 6. Confidence Policy

Preferred qualifier display:
- HIGH,
- MODERATE,
- LOW.

If numeric confidence is used:
- clearly state whether it is model score, calibrated probability, or internal evidence score.

Never label an arbitrary ensemble score as “probability patient has disease”.

## 7. Reproducibility Record

For every model:
- model name,
- version,
- checkpoint,
- source,
- license,
- preprocessing,
- hardware,
- inference configuration.

For every demo case:
- input files,
- expected output,
- actual output,
- runtime.

## 8. Evaluation Output Folder

```text
evaluation/
  cases/
  labels/
  expected/
  actual/
  metrics/
  screenshots/
  report.md
```

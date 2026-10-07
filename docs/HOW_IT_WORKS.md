# How Bonaventure works — a walkthrough from input to output

This is a study guide. It follows **one real case** — demo case A, run on the current code (`docs/sample_output/case_A_result.json`)
— through every stage, naming the file and function that does each step and the actual numbers it produced. Read it
alongside the code; every claim here can be checked there. The last sections cover how the numbers were calibrated
and the questions judges are likely to ask.

Case A inputs (all in `sample_data/`):

* **Film:** `scans/kerley_b.jpg`, a CC0 chest X-ray showing heart failure (Kerley B lines).
* **History:** `histories/case_a_history.pdf`, a fictional 3-page record containing a discharge summary (CHF, LVEF 30 %),
  an echo report (ischaemic cardiomyopathy, mitral regurgitation) and a radiology report dated 12 Aug 2026
  (cardiomegaly, venous diversion, small right effusion).
* **Presentation:** "Worsening shortness of breath for 3 days, can't lie flat, waking up breathless at night, ankle
  swelling. No fever, no cough."

---

## 0. The idea in three sentences

Image models are good at saying *"this film looks like X"* but they hallucinate, and they know nothing about the
patient. Bonaventure therefore never lets a single model make a finding: several independent readers must agree on
the pixels, **and** the patient's own records or symptoms must agree, before anything is called *supported*. Whenever
the sources disagree it says so and shows the evidence, and every claim it threw away is listed with the reason.

---

## 1. Start-up

| What happens | Where |
|---|---|
| `./run.sh` sets offline mode (`HF_HUB_OFFLINE=1`), keeps WebKit on the Intel GPU (it crashed under NVIDIA VRAM pressure) and starts `python -m bonaventure.app` | `run.sh` |
| `app.main()` picks the shell for the OS | `bonaventure/app.py` |
| If another copy is already running, the new one sends `toggle` over a UNIX socket and exits (two copies would not fit on a 6 GB GPU) | `desktop._already_running` |
| The island window opens immediately; `ImagingEngine()` loads the models in a **background thread** | `linux_app.main`, `imaging.ImagingEngine._load` |
| `models.load_all` loads CLEAR → CheXzero → concept bank → MedGemma (4-bit) → MedSAM. Each one that fails is reported, not fatal; the island shows *Imaging* / *Reasoning* status dots | `models.load_all` |
| A socket listener waits for the keyboard shortcut / bar button | `desktop._serve_toggle` |

---

## 2. Intake (the island)

1. **Film**: picked with the file dialog or dropped onto the island. `Api._stage_scan` loads it with `imaging.load_scan`
   (DICOM is windowed to the 0.5–99.5 percentile and MONOCHROME1 inverted; patient name and ID are read from the
   header) and immediately runs `check_quality`, so the tile already shows *acceptable / limited / poor*.
2. **History**: `Api._stage_history` reads the pages (`context.read_pages`, via poppler's `pdftotext`) to show the page
   count and the detected document type. A scanned PDF with no text layer is flagged, since OCR is not supported.
3. **Presentation**: typed, or dictated with the mic button. The words appear live (`Dictation.partial` every 600 ms);
   when the clinician stops, the accurate model replaces them (§5.4).
4. **Analyse** → `Api.analyze` creates a `pipeline.Case`, copies every input into `cases/BV-151/inputs/` (the case
   is self-contained) and runs it on a background thread. The island polls `Api.progress` and shows the seven steps.

---

## 3. Step "Reading chest X-ray": load and quality gate

`imaging.check_quality` resizes to 512×512 and measures:

| Metric | Case A | Rule |
|---|---|---|
| Shortest side | 1097 px | < 320 → severe; < 768 → "low resolution" |
| Mean brightness | 164.8 | < 45 underexposed, > 205 overexposed |
| Contrast (std) | 36.7 | < 28 → low contrast |
| Sharpness (Laplacian variance) | 57.5 | < 12 → blurred / heavily compressed |
| Colour content | 0 | > 25 → "not a radiograph" (severe) |

A severe problem, or two warnings, makes quality **poor**: every finding then becomes INSUFFICIENT_EVIDENCE (demo case C
shows this). One warning makes it **limited**, which lowers the evidence strength and is written into the notes.
Case A: **acceptable**.

---

## 4. Step "Extracting patient timeline": history documents

`context.parse_history(path)`, for each page and each sentence:

1. **Section type.** A short line naming a document type ("Radiology report", "Echocardiogram …") switches the
   `doc_type` for the following sentences, so one combined PDF is split into its parts.
2. **Concept matches.** Every regex in `knowledge.HISTORY_CONCEPTS` (28 concepts, e.g. `chf`, `prior_effusion`,
   `smoker`, `vte`) and `NORMAL_PHRASES` ("normal heart size" → evidence *against* cardiomegaly).
3. **Negation** (`context._negated`, NegEx-style): a trigger (*no, denies, without, negative for …*) up to 8 words
   before the match, unless a terminator (*but, however, has, with …*, or a new clause after a comma) comes between
   them. "denies fever, chills, cough" negates all three; "no temperature, coughs up phlegm" negates only the fever.
4. **Date**: the nearest date in the sentence, else the last month-precise date seen earlier (a note header).
5. **Provenance**: `{file, page, doc_type, quote}` stays with every event to the screen and the PDF.

Case A gives, among others:

| Concept | Date | Source |
|---|---|---|
| Cardiomegaly (prior imaging) | 2026-08-12 | Radiology report, p.3: "Impression: Cardiomegaly with features of pulmonary venous congestion." |
| Pulmonary edema (prior imaging) | 2026-08-12 | Radiology report, p.3: "Upper lobe venous diversion." |
| Pleural effusion (prior imaging) | 2026-08-12 | Radiology report, p.3: "Small right-sided pleural effusion." |
| Congestive heart failure | 2026-07-30 | Discharge summary, p.1: "Acute decompensated congestive heart failure (HFrEF, LVEF 30%)." |
| Cardiomyopathy | 2026-07-28 | Echo report, p.2: "Ischaemic cardiomyopathy." |

**Same patient?** `context.document_identity` pulls "Patient: …" and "MRN …" from each document; `check_identity`
compares them with each other and with the DICOM header (names normalised: "R. Menon" = "MENON^R"). Case A:
*consistent*. Demo case E combines case A's and case B's records (two different patients): the status is *mismatch*,
the history is **discarded**, the "since last report" comparison is blocked, and a red banner names both patients.

---

## 5. Step "Structuring current presentation"

### 5.1 Three readers of the clinician's words (`pipeline.Case.run → understand`)

The text is split into clauses. For each clause:

1. **MedGemma rewrite** (`MedGemma.rewrite_clinical`): "Rewrite each numbered phrase … in plain standard clinical
   terms, keeping any negation. Do not add anything." The reply is prefilled with `1.`, which stops the model from
   "thinking" out loud first.
2. **Deterministic rules** (`context.parse_symptoms`, `presentation_as_history`) read **both** the original clause and
   the rewrite.
3. The two readings are compared:
   * Both found the concept → it is kept, with provenance such as
     `“can't lie flat” → Orthopnea (MedGemma agrees)`.
   * Only the rewrite found it → kept as "understood by MedGemma", with the original words shown.
   * They disagree on negation (the usual LLM failure is dropping a "no") → the **rules win** and a "please check" flag
     is shown in the UI and the report.
   * Neither found anything → **MiniLM** (`semantic.ConceptMatcher`) compares the meaning with every concept's
     description and accepts only a clear match (cosine ≥ 0.40 and ≥ 0.08 ahead of the runner-up).
   * Still nothing → the clause is listed as **"Not understood"**. It is never silently dropped.

Case A result:

| Clause | Read as | How |
|---|---|---|
| "Worsening shortness of breath for 3 days" | Shortness of breath, present, **3 days** | rules + rewrite "Worsening dyspnea …" |
| "can't lie flat" | Orthopnea, present | rules, MedGemma agrees |
| "waking up breathless at night" | Night-time breathlessness (PND), present | rules + rewrite |
| "ankle swelling" | Ankle / leg swelling, present | rules |
| "No fever" | Fever, **denied** | rules, MedGemma agrees |
| "no cough" | Cough, **denied** | rules, MedGemma agrees |

Risk factors typed here ("after a long-haul flight", "on warfarin") become history events too, sourced as *Current
presentation*.

### 5.2 Dictation (`dictation.py`)

`pw-record` (Linux) or `ffmpeg -f avfoundation` (macOS) streams raw 16 kHz mono audio. Every ~0.9 s, Whisper
**base.en** re-reads the recording so far and publishes the caption (audio older than 20 s is frozen into finished text,
so captions stay fast). On stop, Whisper **small.en** reads the whole recording once for the final text. Both are
*primed* with a prompt of clinical words ("orthopnoea, haemoptysis, coughs up phlegm, propped up on pillows …"), which
biases decoding toward those spellings without inserting them. The last recording is saved to
`~/bonaventure/last_dictation.wav` so a mis-transcription can be reproduced.

---

## 6. Step "Evaluating image findings" (`models.analyze`)

### 6.1 Two calibrated image readers

`ZeroShot.scores` encodes the film once, then for each of the 16 findings compares it with a prompt pair such as
`"cardiomegaly"` / `"no cardiomegaly"`. The score is the softmax over the pair, i.e.
`sigmoid(scale × (sim_pos − sim_neg))`. The raw score is turned into a **level** with that reader's own calibrated
cut-offs for that finding (`bonaventure/calibration.json`):

| Finding | Reader | Score | weak / moderate / strong cut-offs | Level |
|---|---|---|---|---|
| Cardiomegaly | CLEAR | 0.958 | 0.508 / 0.547 / 0.729 | **strong** |
| Cardiomegaly | CheXzero | 0.979 | 0.194 / 0.194 / 0.717 | **strong** |
| Pulmonary edema | CLEAR | 0.996 | 0.920 / 0.951 / 0.983 | **strong** |
| Pulmonary edema | CheXzero | 0.987 | 0.095 / 0.381 / 0.381 | **strong** |
| Consolidation | CLEAR | 0.935 | 0.867 / 0.894 / 0.953 | moderate |
| Consolidation | CheXzero | 0.928 | 0.714 / 0.723 / 0.925 | strong |

The cut-offs differ widely between readers and findings, which is why they are calibrated instead of using one
threshold such as 0.5. A reader does not vote at all on a finding where it scored AUROC < 0.70 in calibration.

### 6.1b Confidence as a percentage

`scripts/calibrate.py` also fits, per reader and finding, a logistic curve from the score's logit to the true label on
the same labelled films (Platt scaling): `P = sigmoid(a · logit(score) + b)`. `reconcile._confidence` turns each voting
reader's score into that probability and averages them. Case A: cardiomegaly **90 %** (CLEAR 94, CheXzero 87), edema
**88 %** (79, 97), consolidation **31 %** (28, 34). The number answers "on labelled films, how often was a score like
this a real finding?". It is image-only: the patient's context is weighed by the evidence state. The re-run that added
the curves reproduced every earlier cut-off and AUROC exactly.

### 6.2 The concept bank: what is this film most like?

`ConceptBank.explain` multiplies CLEAR's image embedding with 368,294 pre-computed embeddings of phrases from real
radiology reports and sorts them. For case A, the five closest phrases out of 368,294:

1. "chronic recurrent congestive heart failure"
2. "most likely related to elevated pulmonary venous pressure and chronic fibrosis"
3. "chronic recurrent pulmonary edema"
4. "pulmonary edema superimposed on interstitial changes"
5. "overall findings concerning for interstitial pulmonary edema"

For each finding, the best-ranked phrase that names it (and is not negated, e.g. "…without pneumothorax") is its
**concept rank**. This rank is the specificity check: on very sick films the prompt-pair scores saturate for almost
everything, but the rank stays specific. In case A both readers scored pleural effusion highly, yet the best effusion
phrase ranked only **#354**, so the gate dropped it (see the rejected log in §8).

### 6.3 MedGemma: survey, describe, locate

All prompts ask for JSON only; the parsers tolerate truncated or repeated JSON (`parse_medgemma`, `parse_survey`, `parse_box`).

1. **Survey** (open-ended): "List every abnormal finding visible …". Case A answered: sternal wires, cardiomegaly,
   pulmonary edema, right pleural effusion, left pleural effusion, interstitial thickening. Hedged items ("possible …")
   and normal statements are dropped.
   **Each item is re-read by CLEAR** (`ZeroShot.check`: phrase vs "no " + phrase on the same film) and kept only at
   ≥ 0.85. Interstitial thickening: **0.965 → kept** as "Also seen". Sternal wires: **0.81 → rejected**. Right
   effusion: 0.37 → rejected.
2. **Describe**: the candidate list is sent back to MedGemma: is each one visible, in which region, and what
   observations support it. Cardiomegaly: visible, "The heart appears enlarged".
3. **Locate**: one box per candidate (at most 3, strongest first, only if MedGemma did not just say it cannot see
   it). `box_matches_region` checks that the box sits where MedGemma's own words say: a "right lower lobe" box must be
   on the image's left half (patient's right) and low. A box that fails is discarded and logged.

### 6.3b Heatmap (occlusion)

After reconciliation, `ZeroShot.occlusion` (CheXzero) greys out each cell of an 8 × 8 grid **on the film itself**, one at
a time, re-scores all shown findings in one batch (65 passes, ~4–5 s on the CPU) and records how much each finding's
score dropped. This is model-agnostic and faithful: it shows what the reader's score depends on, not what a gradient
suggests. Case A: cardiomegaly peaks over the heart, edema around both hila. The reading room overlays it with
**Heatmap** or **H**.

### 6.4 MedSAM: box → outline

`MedSAM.outline` encodes the film at 1024 px, prompts with each box and thresholds the mask. A mask smaller than
8 % or larger than 160 % of its box is rejected (the box is kept and the rejection is logged). The outline is a 72-ray
star polygon from the mask centroid (`mask_outline`, no OpenCV). If the GPU is full it falls back to the CPU (~9 s)
instead of failing.

---

## 7. Step "Reconciling evidence" (`reconcile.reconcile → _assess`)

Follow **cardiomegaly** in case A:

1. **Voters**: CLEAR strong, CheXzero strong → agreement **concordant**. MedGemma described it → `mg_sees = True`.
2. **Concept gate**: the concept bank is *not* a reliable reader for cardiomegaly (AUROC 0.62), so the gate does not
   apply to it.
3. **Context**: history *for* = prior cardiomegaly, CHF, cardiomyopathy, valvular disease, hypertension (5 concepts);
   symptoms *for* = shortness of breath, orthopnea, ankle swelling (3) → **support = 8**, against = 0.
4. **Decision path**: quality acceptable → not discordant → no record against it → no key symptom denied →
   concordant with support ≥ 1 → **SUPPORTED**.
5. **Strength**: concordant with both readers strong = 3.0, plus 0.5 × min(8, 3) = 1.5 → 4.5 ≥ 3, SUPPORTED and
   support ≥ 1 → **high**.
6. **Localization**: MedGemma box → MedSAM contour, region "Heart".

Now **consolidation**:

1. CLEAR moderate, CheXzero strong → concordant.
2. Symptoms: dyspnea supports it (1); **fever and cough are denied**, and they are consolidation's `key_against`
   symptoms.
3. Key denials (2) ≥ support (1) → **CONFLICTING**: "Image signal present, but the current presentation argues
   against it: fever denied, cough denied."
4. Strength: 2.5 + 0.5 × 1 − 0.5 × 2 = 2.0 → **moderate**. Localization: MedGemma did not see it, so no box was
   requested → approximate **zone** ("Lung"), drawn dashed and labelled *approx. zone*.

This is the central behaviour. A plain classifier would report "consolidation" on this film. Bonaventure points out
that the patient has no fever and no cough, so the opacity is more likely edema, and leaves the decision to the
clinician.

**Why the other rules exist:**

| Rule | Prevents |
|---|---|
| SUPPORTED needs ≥ 1 context item (devices exempt, but MedGemma must also see the device) | A bare film with no history being called "supported" by pixels alone; a phantom "line" on a normal film |
| No history and no presentation: an UNCERTAIN item MedGemma did not confirm is rejected, not shown | Noise on bare normal films being read as findings |
| Records against + nothing for → CONFLICTING | Ignoring a recent report that says "normal heart size" (case B) |
| 2–1 reader split → UNCERTAIN, not CONFLICTING | Over-alarming when MedGemma sides with one image model |
| Concept-only findings need MedGemma + a supporting history item | Emphysema / fibrosis being raised on normal films by language retrieval alone |
| Label hierarchy | "Cardiomegaly" and "widened mediastinum" both shown for the same enlarged heart |

**From the same evidence:**

* `not_assessable`: pulmonary embolism is raised when the context has ≥ 2 PE triggers including a *specific* one. Demo
  case D (post-op knee replacement, pleuritic pain, racing heart, calf swelling) gets "Pulmonary embolism — not
  assessable on a chest X-ray", with Wells/PERC, D-dimer and CTPA advice, and **no image finding is invented**.
* `interval_changes`: compares today's findings with the newest dated **radiology report**. Case A: cardiomegaly
  **KNOWN**, edema **KNOWN**, pleural effusion **NOT SEEN NOW** (the prior report said "small right-sided effusion" and
  today the gate rejected it). Case B (same film, but the prior report says "normal heart size, lungs clear"):
  cardiomegaly, edema and consolidation are **NEW**.
* `other_observations`: survey items outside the catalogue that CLEAR verified.

---

## 8. "Checked and rejected" log

Every gate appends `{claim, by, reason}` instead of silently dropping the claim. Case A logged 9:

| Claim | By | Reason |
|---|---|---|
| Sternal wires | MedGemma 1.5 | CLEAR disagrees (0.81 < 0.85) |
| Right pleural effusion | MedGemma 1.5 | CLEAR disagrees (0.37 < 0.85) |
| Left pleural effusion | MedGemma 1.5 | CLEAR disagrees (0.73 < 0.85) |
| Pleural effusion | CLEAR + CheXzero | Prompt score high, but no phrase in the film's top 300 of 368,294 names it (best #354) |
| Atelectasis, Lines & devices | CLEAR + CheXzero | Same concept-rank gate |
| Pulmonary fibrosis | CLEAR concepts | MedGemma did not confirm it |
| Pneumonia, Widened mediastinum | label hierarchy | Already explained by consolidation / cardiomegaly |

This log is what the "Rejected claims · N" link in the reading room shows. It is the visible evidence that the system
hallucination-checks itself.

---

## 9. Step "Preparing review": what the clinician sees

`result.json` is written, and the reading room (`ui/review.html`) opens:

* **Film** with grease-pencil marks: MedSAM contours (`handContour`), boxes as hand-drawn ellipses (`handEllipse`), and
  approximate zones drawn dashed and labelled *approx. zone*. It has window/level, zoom and a toggle for the marks.
* **Findings tile**: each finding with its status colour and strength, plus "Also seen".
* **Focus tile** for the selected finding: the image / history / presentation chips, what each reader said, the
  history quotes (clicking one opens the source document), contradictions, and **Agree / Disagree…**.
* **Not assessable** tile, **Since last report** tile, **Impression** with *New case* and *Export report*, and links
  to "How the models read it" (raw model outputs) and "Rejected claims · N".
* **Context drawer** (hidden by default): the timeline with provenance, how each phrase of the presentation was
  understood, "please check" flags and "Not understood" phrases.
* **Identity bar**: shown when records may belong to different people.

### Clinician challenge

*Disagree…* → the clinician picks "not present" or "present" and gives (or dictates) a reason →
`Api.challenge`:

1. MedGemma takes a **second look** with the clinician's reasoning in the prompt (`MedGemma.second_look`).
2. `reconcile.discuss` sorts all the evidence already gathered into "agrees with you" and "points the other way", says
   which way it leans, and names the test that would settle it (`knowledge.RESOLVE`, e.g. echocardiogram for
   cardiomegaly).
3. The clinician's verdict is **final**: `record_override` stores it with their note next to Bonaventure's status in
   `result.json` and in the PDF. Bonaventure never overrules the clinician.

### PDF evidence report (`report.generate`)

WeasyPrint renders: case header; presentation with present and denied symptoms; understanding flags; relevant
history with sources; a **lung diagram** (front view, patient's right on the left, every zone a finding covers shaded
in its status colour and numbered); the annotated film; one block per finding (image, history and presentation
evidence, conflicting evidence, strength); not assessable; also seen; identity warning; since last report; clinician
review; checked and rejected; limitations; and a review statement. Example: `docs/sample_output/case_A_report.pdf`.

---

## 10. How the numbers were obtained (offline scripts)

| Script | What it does | Output |
|---|---|---|
| `scripts/calibrate.py` | Scores CLEAR and CheXzero on labelled films: CheXpert v1.0 validation (202 frontal films, radiologist consensus) for the findings it labels, otherwise an NIH ChestX-ray14 test-split sample (60 positives per finding + 300 normals). Findings with < 15 positives (pneumothorax: 7) keep stricter hand-set cut-offs. Computes AUROC and reads the three cut-offs off each ROC curve | `bonaventure/calibration.json` |
| `scripts/eval_concepts.py` | Same, for the concept-bank rank of each finding | `bonaventure/concept_calibration.json` |
| `scripts/audit.py` | Runs the **full** pipeline (no history, no presentation) on 36 NIH films **not** used for calibration: 12 normal, 2 per label. Counts how often normal films get findings and how often the labelled disease is raised | `bonaventure/audit.json` |
| `scripts/run_demo_cases.py` | Demo cases A–E plus two normal films | prints a summary per case |
| `scripts/build_demo_library.py`, `run_demo_library.py` | 14 NIH films, one per disease, each with its own fictional history and presentation | `~/bonaventure/demo_library` |

*Weak* = the score at which the reader catches 90 % of positives (sensitivity 0.9). *Moderate* = Youden's J, the
best balance of sensitivity and specificity. *Strong* = the score at which 90 % of negatives fall below it (specificity
0.9). So "strong" has a concrete meaning: on labelled data, only about 1 in 10 films without the disease reached that
score.

---

## 11. Questions a judge may ask

**Why not train your own model?** Labelled chest X-ray data and compute for a credible classifier were not available in
the time. The contribution is the evidence layer: calibration of existing open models on labelled data,
multi-reader agreement, patient-context reconciliation, provenance, and refusing to guess. All the models are declared
in `docs/13_MODEL_RESOURCE_REGISTER.md`.

**How do you stop hallucinations?** No single model can create a finding. The image candidates need two calibrated
readers (or one at *strong*) plus the concept-rank specificity gate. MedGemma's free-text claims must be independently
confirmed by CLEAR. Boxes must match the region the model itself named. Masks must fit their box. SUPPORTED needs the
patient's records or symptoms. Everything removed is shown in the rejected log, with the reason.

**How confident is it?** Each finding shows an **image confidence %**: the reader scores mapped through a logistic fit on
labelled films (case A consolidation: only 31 %, which is why it is not supported). Raw prompt scores are never shown as
percentages, since they saturate on sick films. *High / moderate / low* strength is separate: it summarises how many
independent sources, including the patient's context, agree.

**Where exactly is the finding?** A MedSAM outline when the box was trustworthy. Otherwise an approximate anatomical
zone, which is labelled as approximate and never passed off as segmentation.

**What if the history belongs to someone else?** Names and MRNs across all documents and the DICOM header are compared.
A mismatch discards the history and blocks the interval comparison (case E).

**What if the disease cannot be seen on an X-ray?** Pulmonary embolism and aortic dissection are reported as *not
assessable on a chest X-ray*, with the right next test (case D), instead of being guessed from the film.

**Poor images?** The quality gate turns every finding into INSUFFICIENT_EVIDENCE rather than forcing a conclusion
(case C).

**Privacy?** Everything runs locally and offline. No API calls, and no patient data leaves the laptop.

**What is weak?** See the limitations in the README. Nodules, masses and pneumothorax are not reliably detected (the
audit raised 0 of 2 for each). History parsing is rule-based, with no OCR for scanned PDFs. MedGemma's boxes are
approximate, and the calibration set is small (202 CheXpert films, only 7 pneumothoraces).

---

## 12. Glossary

| Term | Meaning here |
|---|---|
| Zero-shot | Classifying with text prompts the model was never trained on as labels ("pleural effusion" vs "no pleural effusion") |
| AUROC | Probability a random positive film scores higher than a random negative one; 0.5 = chance, 1.0 = perfect |
| Youden's J | The ROC point maximising sensitivity + specificity − 1 |
| NegEx | Classic clinical NLP negation algorithm: negation trigger words with a scope window |
| Concept rank | Position of the best phrase naming a finding among CLEAR's 368,294 report phrases ranked by similarity to the film |
| NF4 / 4-bit | MedGemma's weights quantised to 4 bits (bitsandbytes) to fit a 6 GB GPU |
| Provenance | File, page and verbatim quote behind every history fact |

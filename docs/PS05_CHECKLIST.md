# PS05 checklist: what was asked vs. what Bonaventure does

Source: *HackNex 2026 Internal Qualifier, Problem Statement Booklet*: **HNX26PSI05 Multimodal Medical Image
Intelligence** (p.9), *Submission Guidelines* and *How to Submit* (p.3), and *Rules and Instructions* (p.4).

Legend: ✅ met · ⚠️ partly met (gap stated) · ❌ not met / still to do

---

## 1. HNX26PSI05: "What you're building"

| # | Requirement (PS wording) | Status | How Bonaventure meets it | Evidence |
|---|---|---|---|---|
| 1 | "AI system that doctors can use as a second opinion (not a replacement)" | ✅ | Every finding is a candidate for review; the clinician can Agree / Disagree, and **their verdict is recorded as final** next to Bonaventure's | `desktop.Api.record_override`, report "Clinician review" section |
| 2 | "Reads medical images (X-rays, CT scans, etc.)" | ⚠️ | Chest X-ray (PNG/JPEG/DICOM, frontal). **CT and MRI are not supported** | `imaging.load_scan` |
| 3 | "Combines that with patient notes or test results" | ✅ | History PDFs/text → dated, negation-aware facts with file, page and quote; the presentation is typed or dictated. Numeric results are matched where the vocabulary has them (LVEF ≤ 39 % → heart failure, heart rate ≥ 100 → tachycardia); there is no general lab-value interpretation | `context.parse_history`, `pipeline.understand`, `knowledge.HISTORY_CONCEPTS` |
| 4 | "Gives an assessment" | ✅ | Per finding: SUPPORTED / UNCERTAIN / CONFLICTING / INSUFFICIENT_EVIDENCE + evidence strength + a one-line impression | `reconcile._assess`, review "Impression" tile |
| 5 | "Point to exactly where in the image it sees something unusual" | ✅ / ⚠️ | MedSAM outline when MedGemma's box is trustworthy; otherwise an anatomical **zone**, drawn dashed and labelled *approx. zone*. Boxes that contradict the model's own region text are discarded | `models.analyze`, `reconcile._zone_localization`, review grease-pencil marks |
| 6 | "Explain what it found" | ✅ | Image evidence (each reader's level, MedGemma's observations, closest report phrases), history quotes, symptoms, contradictions, notes | review Focus tile, PDF per-finding block |
| 7 | "Tell you how confident it is" | ✅ | **Image confidence as a percentage** per finding and per reader (e.g. cardiomegaly 90 %: CLEAR 94 %, CheXzero 87 %; the conflicting consolidation only 31 %), from Platt scaling fitted on the labelled films; plus calibrated weak / moderate / strong levels and the evidence strength | `calibration.json` (`platt`), `reconcile._confidence` |

**Key idea:** "A finding with no location in the image or no supporting clinical notes is a hallucination and fails that case."

| Status | How |
|---|---|
| ✅ | Every displayed finding has a location (outline, box or zone; only INSUFFICIENT findings have none). **SUPPORTED requires at least one supporting history or symptom item** (lines/devices excepted, as hardware). A finding with image signal but no context is at most **UNCERTAIN** and says "No supporting clinical context identified." |

## 2. Key rules

| # | Rule | Status | How |
|---|---|---|---|
| 1 | "Every finding must be backed up: point to a region in the image OR cite information from patient notes. Unsupported findings = hallucinations = fail." | ✅ | Region **and** (for SUPPORTED) a cited note: file, page and verbatim quote. Model claims that fail a cross-check are removed and listed under **Checked and rejected** with the reason (case A: 9 rejected) |
| 2 | "Must include confidence levels. 'I'm 95% sure' vs 'I'm 30% sure' — don't say everything with certainty." | ✅ | Each finding shows **"N % image confidence"**, each reader's own percentage, and the basis ("calibrated on 202 labelled films (CheXpert)"). Raw prompt scores are **not** shown as percentages, because they saturate on sick films; the number is each score mapped through a logistic fit on labelled data. Case A: cardiomegaly 90 %, edema 88 %, consolidation 31 %. The evidence state still weighs the patient's context separately |
| 3 | "Must present as a helper, not a doctor. 'Doctor, consider this finding…' not 'The patient has…'" | ✅ | All clinician text: "Consider cardiomegaly (heart)…", "Possible …; evidence is limited. Correlate clinically.", "Evidence … is inconsistent. Human review required." Report ends with a review statement | `reconcile._clinician_text`, `report.render_html` |

## 3. How it will be judged

| # | Criterion | Status | Evidence to show |
|---|---|---|---|
| 1 | "Can it spot and classify abnormalities correctly?" | ✅ / ⚠️ | 16 findings; AUROC 0.72–0.94 on 11 of them (README table). Audit on 36 unseen films (film only, no history): the labelled disease was raised on 10 / 24 (2/2 cardiomegaly, edema, consolidation, atelectasis). **Weak:** nodule, mass, pneumothorax |
| 2 | "Can it point to the exact region in the image?" | ✅ / ⚠️ | MedSAM outlines (case A: heart and lungs segmented). Approximate zones where no trustworthy box exists, labelled as such |
| 3 | "Does it use both images AND patient context together?" | ✅ | The core of the product. Case A vs case B: **same film**, different history → SUPPORTED vs CONFLICTING. Case A consolidation → CONFLICTING because fever and cough are denied |
| 4 | "Can it segment/outline problem areas (advanced)?" | ✅ | MedSAM ViT-B, box-prompted; masks outside 0.08–1.6× the box are rejected |
| 5 | "Are confidence levels realistic?" | ✅ / ⚠️ | Per-reader cut-offs from ROC curves; a reader that cannot separate a finding (AUROC < 0.70) does not vote; "high" needs the patient's context as well. Audit: 1 of 12 normal films had a SUPPORTED item (a device false positive); none had a SUPPORTED disease |
| 6 | "Does it explain findings with evidence?" | ✅ | Evidence triangle (image · history · presentation), quotes, closest report phrases, raw model outputs ("How the models read it"), rejected log |
| 7 | "Does it handle poor-quality images?" | ✅ | Quality gate (resolution, exposure, contrast, sharpness, colour). Poor → every finding INSUFFICIENT_EVIDENCE (case C); limited → strength lowered with the reason |

## 4. What to build first

| Step | Status | |
|---|---|---|
| "Use public medical datasets" | ✅ | CheXpert v1.0 validation and NIH ChestX-ray14 (calibration and audit); CC0 Wikimedia films for the demo |
| "Start with one type of abnormality on single images with a heatmap" | ✅ | 16 findings, each with an **occlusion heatmap** (Heatmap button / H): each cell of an 8×8 grid on the film is greyed out in turn, and the drop in the reader's score is plotted. This shows where the score actually comes from (case A: cardiomegaly over the heart, edema around both hila). Plus MedSAM outlines |
| "Advanced: segment regions, combine image + patient notes" | ✅ | MedSAM outlines; reconciliation with history and presentation |

## 5. Submission guidelines (p.3)

| Item | Status | Where |
|---|---|---|
| Working system | ✅ | Desktop app (`./run.sh`); demo cases A–E reproduce with `scripts/run_demo_cases.py` |
| Source code + clear README to set up and run end-to-end | ✅ | `README.md`: install, configure, run, reproduce |
| Data pipeline: how input is collected, processed and passed through | ✅ | `docs/ARCHITECTURE.md` §3–§6, `docs/HOW_IT_WORKS.md` §2–§7 |
| Core model / reasoning | ✅ | `docs/ARCHITECTURE.md` §4–§5; `models.py`, `reconcile.py` |
| Evidence & explanation (citations, timestamps, confidence scores, intermediate outputs, code) | ✅ | `result.json` holds every citation (file, page, quote), dates, reader scores and cut-offs, raw MedGemma output, per-model timing and the rejected log; `docs/sample_output/` |
| Sample input & output | ✅ | README "Sample input and output"; `docs/sample_output/case_A_*` |
| Scope note (MVP vs stretch) | ✅ | README "Scope note" |
| Live demonstration | ❌ **to do** | Rehearse cases A → B → D → E, plus one dictated presentation and one Disagree challenge. Record a backup video in case the live demo fails |

## 6. How to submit (p.3)

| Item | Status | Action |
|---|---|---|
| "Submit your project through a Git repository that is **public**" | ❌ **to do** | `RM1338/Bonaventure` is currently **private**. Make it public before submitting: `gh repo edit RM1338/Bonaventure --visibility public --accept-visibility-change-consequences` |
| README explains: what the project does | ✅ | "What it does" |
| … technologies, libraries and models used | ✅ | "Technologies, libraries and models" + register |
| … how to install dependencies | ✅ | "Install" (Linux, models) |
| … how to configure and run | ✅ | "Configure", "Run" |
| … how to reproduce the demonstrated results | ✅ | "Reproduce the demonstrated results" |
| Submit the link on the form before the end of evaluation | ❌ **to do** | https://forms.gle/KGjkU5u66Va1MDhu5 |
| A presentation (ppt) is not necessary | — | |

## 7. Rules and instructions (p.4)

| Rule | Status | |
|---|---|---|
| AI usage permitted, if teams review, understand and take responsibility | ✅ / to do | `docs/HOW_IT_WORKS.md` is written to be studied before the evaluation; every number in it comes from a real run |
| Declare resources (APIs, datasets, pretrained models, open-source components) | ✅ | `docs/13_MODEL_RESOURCE_REGISTER.md`; README "Original contribution vs. external components" |
| Demonstrate your work, explain the approach, answer questions | to do | `docs/HOW_IT_WORKS.md` §11 lists the likely questions and answers |
| Evaluation integrity: no access to hidden test data | ✅ | Calibration used only public datasets; the audit used films held out from calibration |

---

## 8. Open gaps, in priority order

1. **Make the repository public** and submit the form link. Without this the submission does not count.
2. **Rehearse and record the demo** as a backup.
3. ~~UNCERTAIN noise on bare films~~ **fixed**: with no history and no presentation, a finding is shown only if both image models agree, or MedGemma named it unprompted in its survey and CLEAR confirmed it. Anything else goes to the rejected log. (MedGemma's *prompted* "yes" was tried first and did not help: asked about a candidate, it tends to agree.) Re-check of the same 12 audit normal films after the fix: **0 SUPPORTED and 0 CONFLICTING items** (before: 1 and 3 films); 5 / 12 completely clean, the rest show only UNCERTAIN items both image models agreed on. The full 36-film audit has not been re-run since this fix.
4. ~~Lines & devices on a normal film~~ **fixed**: devices are still exempt from the history rule, but MedGemma must name the device unprompted and CLEAR must confirm it before it is SUPPORTED.
5. ~~Confidence as a number~~ and ~~heatmap~~ **done** (§1 row 7, §4).
6. CT/MRI, OCR for scanned PDFs, nodule/mass/pneumothorax sensitivity: out of scope, and stated in the README.

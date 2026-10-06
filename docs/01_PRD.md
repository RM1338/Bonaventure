# Product Requirements Document (PRD)

## 1. Product

**Name:** Bonaventure  
**Positioning:** Clinical Evidence Intelligence

## 2. Problem Statement Basis

HackNex PS05 asks for a system that:

- Reads medical images such as X-rays or CT scans.
- Combines image information with patient notes or test results.
- Gives an assessment.
- Points to the exact image region where something unusual is observed.
- Explains the finding.
- Includes confidence.
- Uses both image and patient context.
- Presents itself as a helper for doctors, not as a replacement.
- Handles poor-quality images.
- May perform segmentation as an advanced capability.

The PS explicitly treats unsupported findings as hallucinations.

## 3. Product Vision

Bonaventure should help a clinician answer:

1. What does the current chest X-ray suggest?
2. Where exactly is the supporting image evidence?
3. Does the patient's history support or contradict that finding?
4. Do the current symptoms support or contradict it?
5. How strong is the combined evidence?
6. Is the evidence sufficient to present the finding confidently?
7. What should the clinician review next?

## 4. Core Product Thesis

`Imaging Evidence + Longitudinal History + Current Symptoms -> Evidence-Reconciled Clinical Support`

The project is not intended to be a generic “X-ray classifier”.

Its differentiator is **evidence reconciliation**.

## 5. Target User

Primary:
- Clinician reviewing a chest X-ray and supporting patient context.

Secondary:
- Radiology support workflow user.
- Evaluator reviewing the system during the HackNex qualifier.

## 6. MVP Scope

### Supported Modality
- Chest X-ray only.

### Inputs
- Current chest X-ray.
- One or more patient-history documents.
- Current symptom description.

### Core Processing
- X-ray quality check.
- Candidate finding detection.
- Image-region localization.
- Patient-history parsing.
- Structured symptom parsing.
- Relevant history retrieval.
- Positive evidence detection.
- Negative evidence detection.
- Contradiction detection.
- Evidence agreement scoring.
- Clinician-facing explanation.

### Outputs
- Annotated chest X-ray.
- Candidate findings.
- Localized evidence.
- Relevant history timeline.
- Structured current symptoms.
- Supporting evidence.
- Contradictory evidence.
- Evidence-strength status.
- PDF report.

## 7. Initial Finding Set

The initial supported set should be restricted to findings for which the chosen model stack can be validated.

Candidate scope:
- Pleural effusion.
- Cardiomegaly.
- Pneumothorax.
- Consolidation.
- Pulmonary edema.
- Atelectasis.

The final list must be reduced if validation is weak for any class.

## 8. Evidence States

Every finding must resolve to one of:

- `SUPPORTED`
- `UNCERTAIN`
- `CONFLICTING`
- `INSUFFICIENT_EVIDENCE`

These states are preferred over forcing a binary “disease / no disease” answer.

## 9. Primary User Flow

1. Open Bonaventure quick launcher.
2. Upload current chest X-ray.
3. Upload patient-history document(s).
4. Enter current symptoms.
5. Start analysis.
6. System validates inputs.
7. System parses history and symptoms.
8. System analyzes image.
9. System reconciles evidence.
10. Full clinical review window opens.
11. Clinician reviews:
   - image findings,
   - localization,
   - relevant history,
   - current symptoms,
   - positive evidence,
   - negative evidence,
   - contradictions,
   - evidence strength.
12. User optionally generates PDF report.

## 10. Non-Goals

Bonaventure will not:

- Claim to diagnose a patient.
- Recommend treatment.
- Recommend medications.
- Replace radiologist review.
- Hide disagreement between models.
- Present an LLM-generated confidence number as clinical probability.
- Support arbitrary CT/MRI in the MVP.
- Require real identifiable patient records for the qualifier demo.
- Use free-form LLM output as the sole basis for a medical finding.

## 11. Success Criteria

The product succeeds if a judge can:

- Upload a valid chest X-ray.
- Upload history.
- Enter symptoms.
- Receive a grounded candidate finding.
- See where the image evidence is located.
- See which history facts were used.
- See current symptom support.
- See contradictions or uncertainty.
- Generate an evidence-backed report.
- Reproduce the demonstrated result from the public repository.

## 12. Stretch Goals

- Previous-image comparison.
- Refined segmentation.
- Additional pathologies.
- DICOM support.
- Automated image-quality model.
- More than one independent image model.
- Longitudinal progression analysis.
- More imaging modalities.

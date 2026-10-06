# Software Requirements Specification (SRS)

## 1. Purpose

This document defines the functional and non-functional software requirements for Bonaventure.

## 2. Functional Requirements

### FR-01 — Create Case

The system shall create a case session before processing.

Each case shall contain:
- case ID,
- scan input,
- history input,
- current symptom input,
- analysis state,
- model outputs,
- evidence objects,
- final findings,
- report artifact.

### FR-02 — Upload Chest X-ray

The user shall be able to upload:
- PNG,
- JPEG,
- optionally DICOM if implemented.

The system shall reject unreadable or unsupported files.

### FR-03 — Upload Patient History

The user shall be able to upload one or more patient-history documents.

Priority:
- PDF.
- Plain text.
- Image-based PDF with OCR fallback if available.

### FR-04 — Enter Current Symptoms

The user shall be able to enter current symptoms in natural language.

The system shall preserve the original text and produce structured symptom concepts.

### FR-05 — Input Quality Check

The system shall evaluate image usability.

At minimum:
- readability,
- resolution,
- severe blur,
- severe crop/orientation issue where detectable.

### FR-06 — Image Finding Generation

The system shall produce candidate findings from the supported pathology set.

Each candidate shall contain:
- canonical finding name,
- raw model score or signal,
- source model,
- localization if available.

### FR-07 — Localization

Every displayed imaging finding must have localized evidence where supported by the chosen model.

Allowed output:
- bounding box,
- contour,
- segmentation mask,
- attribution heatmap.

The UI may render doctor-style circle/arrow annotations derived from machine localization.

### FR-08 — Patient-History Parsing

The system shall extract:
- diagnoses,
- medications,
- previous imaging findings,
- relevant procedures,
- relevant lab findings where available,
- dates,
- negated facts where identifiable,
- source provenance.

### FR-09 — Longitudinal Timeline

The system shall build a time-ordered patient context view.

### FR-10 — Current Symptom Parsing

The system shall distinguish:
- present symptom,
- denied symptom,
- unknown/unspecified symptom.

### FR-11 — Relevant Evidence Retrieval

For each candidate finding, the system shall retrieve only clinically relevant history and symptoms.

### FR-12 — Positive Evidence

The system shall identify evidence that supports a candidate finding.

### FR-13 — Negative Evidence

The system shall identify evidence against a candidate finding.

### FR-14 — Contradiction Detection

The system shall identify contradictions such as:
- conflicting history documents,
- image-model disagreement,
- image-context disagreement,
- present/denied symptom conflicts.

### FR-15 — Evidence Reconciliation

The system shall combine:
- image support,
- localization support,
- history support,
- symptom support,
- independent verifier support,
- negative evidence,
- contradiction penalties,
- input-quality penalties.

### FR-16 — Finding State

The system shall assign:
- SUPPORTED,
- UNCERTAIN,
- CONFLICTING,
- INSUFFICIENT_EVIDENCE.

### FR-17 — Confidence / Evidence Strength

The system shall display confidence only in a defensible form.

Preferred MVP output:
- High,
- Moderate,
- Low.

Numeric values shall be used only when the team can explain and validate them.

### FR-18 — Clinician-Facing Language

The system shall use non-diagnostic wording.

Examples:
- “Possible…”
- “Consider…”
- “Imaging evidence supports…”
- “Clinical correlation recommended.”
- “Human review required.”

### FR-19 — Review Workspace

The workspace shall display:
- current X-ray,
- selected finding,
- annotation,
- evidence state,
- relevant history,
- current symptoms,
- positive evidence,
- negative evidence,
- contradictions,
- source drilldown.

### FR-20 — PDF Report

The system shall generate a PDF containing:
- case summary,
- current presentation,
- relevant history,
- annotated image,
- candidate findings,
- evidence,
- contradictions,
- evidence strength,
- limitations,
- clinician-review statement.

### FR-21 — Failure Transparency

The system shall never silently replace:
- failed model output,
- failed history parsing,
- missing evidence,
- unsupported image.

Failures must be surfaced.

## 3. Non-Functional Requirements

### NFR-01 — Reproducibility
A documented setup must reproduce the demo cases.

### NFR-02 — Traceability
Every displayed history fact must preserve source file and page when available.

### NFR-03 — Modularity
Image, history, symptoms, reconciliation, UI, and reporting must be separable modules.

### NFR-04 — Explainability
Every displayed finding must link to evidence.

### NFR-05 — Responsiveness
The UI must show a processing state while inference is running.

### NFR-06 — Reliability
The demo shall use validated cases and deterministic settings where possible.

### NFR-07 — Privacy
The qualifier demo shall use public, de-identified, or synthetic patient context.

### NFR-08 — Resource Declaration
All external APIs, datasets, models, and open-source components must be declared in the repository.

## 4. System Constraints

- Limited build window.
- Four-person team.
- No requirement for production EHR integration.
- No requirement for all medical modalities.
- Public repository required for submission.
